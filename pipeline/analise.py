"""Análise do coorte — a casca que busca o dado, chama o núcleo e grava.

A conta mora em `egressos_core.analise`, que é pura: recebe os datasets já lidos e devolve o
dicionário que vira `analise.json`. Aqui ficam as três coisas que ela não faz — ler pelo
catálogo, contar as linhas dos dois arquivos de levantamento, e gravar.

Antes, este arquivo eram 657 linhas rodando **na importação**: cinco `dados.ler` no corpo do
módulo, doze seções de cálculo entre funções soltas, e um `dados.gravar` no fim. Não dava para
chamá-lo duas vezes, nem testá-lo sem gravar, nem importá-lo de um orquestrador — só disparar
um processo. Era o motivo de `build_report.py` orquestrar por `subprocess`.

## As duas datas

`hoje` é a competência de referência do estudo (`mes_base` do IBGE, jun/2026), e é dela que sai
o ano-corrente da linha do tempo. O tempo de **carreira** continua sendo medido contra
`REFERENCIA_ANOS_CARREIRA`, que é `2026 + 6/12` — a constante que morava na linha 20 deste
script. As duas divergem em um mês, e alinhar muda `anos_exp` de parte do coorte por causa do
`round(…, 1)`: é decisão de dado, e está registrada como pendência em `docs/ARQUITETURA.md`.

Uso:  python pipeline/analise.py     (de qualquer diretório)
"""
from __future__ import annotations

import json
import sys

from egressos_core import analise, dados, deflator
from egressos_core.deflator import Competencia
from egressos_core.paths import ROOT

#: Tempo de carreira é medido contra jul/2026 — não contra o `mes_base` do IBGE (jun/2026).
#: A divergência é deliberada e preserva os números publicados. Ver o docstring acima.
REFERENCIA_ANOS_CARREIRA = 2026 + 6 / 12

#: Levantamento de perfis: dois arquivos de texto na raiz, uma linha `->` por pessoa. Não são
#: dataset do catálogo (são anotação de trabalho), então a contagem é feita aqui, não no núcleo.
ARQUIVOS_DE_COBERTURA = {"encontrados": "encontrados.txt",
                         "nao_encontrados": "nao_encontrados.txt"}


def _linhas_de_levantamento(nome: str) -> int | None:
    """Quantas pessoas o arquivo de levantamento lista. `None` quando ele não existe."""
    caminho = ROOT / nome
    if not caminho.exists():
        return None
    return sum(1 for linha in caminho.read_text(encoding="utf-8").splitlines()
               if "->" in linha and not linha.startswith("#"))


def _outros_labs() -> dict | None:
    """Cross-ref de laboratórios além do LEDS — curado à mão, e pode não existir."""
    try:
        return dados.ler("outros_labs")
    except FileNotFoundError:
        return None


def insumos(*, hoje: Competencia) -> dict:
    """Tudo o que `analise.montar` precisa, já lido. É a metade "buscar o dado" da casca.

    Separada de `executar` para que a suíte possa montar o relatório **sem gravar** em `data/`,
    e ainda assim exercitar a ligação real: os mesmos datasets, a mesma contagem de cobertura e
    as mesmas duas datas que o build usa.
    """
    return {
        "cadastro": dados.ler("alunos"),
        "consolidado": dados.ler("consolidado"),
        "codigofonte_historico": dados.ler("codigofonte_historico"),
        "genero_map": dados.ler("genero_map"),
        "empresas_porte": dados.ler("empresas_porte"),
        "src_extensao": dados.ler("src_extensao"),
        "outros_labs": _outros_labs(),
        "cobertura": {chave: _linhas_de_levantamento(arquivo)
                      for chave, arquivo in ARQUIVOS_DE_COBERTURA.items()},
        "hoje": REFERENCIA_ANOS_CARREIRA,
        "ano_corrente": hoje.ano,
    }


def executar(*, hoje: Competencia) -> dict:
    relatorio = analise.montar(**insumos(hoje=hoje))
    dados.gravar("analise", relatorio)
    return relatorio


def main() -> int:
    relatorio = executar(hoje=deflator.data_referencia(dados.ler("ibge_series")))

    print("=== TECNOLOGIAS (top por nº de pessoas) ===")
    for t in relatorio["top_tech"]:
        print(f"  {t['tech']:<14} {t['pessoas']} pessoas / {t['mencoes']} menções")

    print("\n=== CLUSTERS (KMeans k=3) ===")
    for c, d in relatorio["clusters"].items():
        print(f"  Cluster {c}: {d['labels']} | {d['trilha']} | ~{d['anos_medio']}a | "
              f"exterior={d['exterior']} lideranca={d['lideranca']} em_tech={d['em_tech']}/{d['n']}")
        print(f"     cargos: {d['cargos']}")

    print("\n=== INSIGHTS ===")
    for k, v in relatorio["insights"].items():
        print(f"  {k}: {v}")

    comp = relatorio["comparacao"]
    print("\n=== COMPARAÇÃO EXTERNA ===")
    print(f"  egressos mediana atual R$ {comp['egressos_med_atual']} vs CF Sênior 2026 "
          f"R$ {comp['cf_senior_2026']} ({comp['egressos_vs_cf_senior_pct']:+d}%)")
    print("  trajetória (egressos valor da época vs mercado hoje):")
    for r in comp["por_exp"]:
        print(f"    exp {r['exp']:>2}: egressos R$ {r['egressos_epoca']:>6}  |  "
              f"mercado hoje R$ {r['mercado_hoje']:>6}")

    cruz = relatorio["cruzamento"]
    print("\n=== SENIORIDADE x ORIGEM (nacional / internacional) ===")
    for r in cruz["por_senioridade"]:
        print(f"  {r['senioridade']:<18} n={r['n']} {r['labels']} | nac={r['nac']} "
              f"intl={r['intl']} | mediana R$ {r['med_atual']}")
    print("  --- por origem ---")
    for o, d in cruz["por_origem"].items():
        print(f"  {o:<9} n={d['n']} | ~{d['anos_medio']}a | mediana R$ {d['med_atual']} | "
              f"{d['empresas']}")
    print(f"  prêmio internacional vs nacional: {cruz['premio_intl_vs_nac_pct']:+d}%")

    lid = relatorio["lideranca_gestao"]
    print("\n=== CARGOS / FUNÇÕES ATUAIS ===")
    for f in relatorio["funcoes"]:
        print(f"  {f['funcao']:<32} {f['n']}")
    print(f"  -> em liderança/gestão: {lid['total']} ({lid['gestao']} gestão + "
          f"{lid['lideranca_tecnica']} liderança técnica)")

    print("\n=== MÉTODOS / PRÁTICAS (presença por egresso) ===")
    for m in relatorio["metodos"]:
        print(f"  {m['metodo']:<32} {m['n']}")

    trajetoria = relatorio["trajetoria_destaque"]
    if trajetoria:
        print(f"\n=== TRAJETÓRIA DESTAQUE === {len(trajetoria)} anos "
              f"({trajetoria[0]['ano']}–{trajetoria[-1]['ano']}), "
              f"R$ {trajetoria[0]['med']} -> R$ {trajetoria[-1]['med']}")

    print("\n=== INDICADORES DE IMPACTO ===")
    print(json.dumps(relatorio["impacto"], ensure_ascii=False, indent=1))
    print(f"\nSalvo em {dados.caminho('analise')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

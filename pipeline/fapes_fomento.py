"""Fomento FAPES da coorte de egressos.

Lê a base da FAPES (`relatorio_alocacao_bolsas.json`, do fapes-dashboard) e agrega os
projetos-âncora que financiaram os egressos. O vínculo egresso↔projeto é **curado**, verificado
por projeto + período + sigla: cruzar por nome puro dá homônimo.

Saída: `fapes_fomento`.

Uso:  python pipeline/fapes_fomento.py     (de qualquer diretório)
"""
from __future__ import annotations

import re
import statistics
import sys
from typing import Any, Mapping, Sequence

from egressos_core import dados, deflator, io
from egressos_core.deflator import Competencia
from egressos_core.paths import FAPES_ALOCACAO as FAPES

#: projeto-âncora -> egressos (ids do `alunos.json`), verificados por projeto+período+sigla
ANCORA = {
    "34552": ["barbosa", "gary", "helen", "marialuiza", "icaro"],   # ES na Palma da Mão (BPIG)
    "39212": ["tarcisio"],                                          # Acesso Cidadão (AT-NM)
}

#: Ordem da anonimização, truncada nos 23 primeiros — é o alcance que este cálculo cobre.
#: O join com `consolidado["perfis"]` é **por índice**, e não por rótulo como no resto do
#: pipeline. Perfil pulado em `compute_all` deslocaria todos os seguintes, e cada egresso
#: herdaria a mediana do vizinho, calado. Trocar para join por rótulo muda número publicado:
#: é decisão de dado, registrada em `docs/ARQUITETURA.md`.
ORDEM_PARCIAL = ["barbosa", "gary", "possatti", "helen", "renan", "andre", "tarcisio", "joel",
                 "icaro", "gustavo", "marialuiza", "gabriel_barboza", "magnago",
                 "martins_miranda", "geann", "rodrigo_maia", "andre_aguiar", "guilherme_gatti",
                 "ivana", "joao_paulo", "lucas_coutinho", "marcos_dias", "phillipe"]

BOLSA_EPOCA, BOLSA_ANO = 800, 2018


def _valor_br(bruto: Any) -> float:
    """`"1.234,56"` -> `1234.56`. Sem dígito nenhum, zero — o campo vem vazio na base."""
    texto = str(bruto or "").strip()
    return float(texto.replace(".", "").replace(",", ".")) if re.search(r"\d", texto) else 0.0


def montar(*, base_fapes: Sequence[Mapping[str, Any]], alunos: Sequence[Mapping[str, Any]],
           consolidado: Mapping[str, Any], deflator_ipca: Mapping[str, float]) -> dict:
    projetos = []
    for pid, egressos in ANCORA.items():
        registros = [r for r in base_fapes if r.get("projeto_id") == pid]
        if not registros:
            continue
        primeiro = registros[0]
        projetos.append({
            "projeto_id": pid,
            "titulo": primeiro.get("projeto_titulo"),
            "situacao": primeiro.get("situacao_descricao"),
            "instituicao": primeiro.get("instituicao_sigla"),
            "bolsa_sigla": sorted({r.get("bolsa_sigla") for r in registros}),
            "bolsistas": len({r.get("bolsista_pesquisador_nome") for r in registros}),
            "valor_alocado": round(sum(_valor_br(r.get("valor_alocado_total"))
                                       for r in registros)),
            "periodo": [min(r.get("formulario_bolsa_inicio", "") for r in registros)[:7],
                        max(r.get("formulario_bolsa_termino", "") for r in registros)[:7]],
            "egressos": len(egressos),
        })
    total = {
        "valor_total": sum(p["valor_alocado"] for p in projetos),
        "bolsistas_total": sum(p["bolsistas"] for p in projetos),
        "egressos_total": sum(p["egressos"] for p in projetos),
        "n_projetos": len(projetos),
    }

    # DESFECHO (impacto): onde os egressos bolsistas FAPES estão hoje
    ids = [i for lista in ANCORA.values() for i in lista]
    perfis = consolidado["perfis"]
    med_por_id = {ORDEM_PARCIAL[i]: perfis[i]["med_atual"]
                  for i in range(min(len(ORDEM_PARCIAL), len(perfis)))}
    medianas = [med_por_id[i] for i in ids if i in med_por_id]
    # A bolsa em poder de compra de hoje vem do deflator do IPCA, não de constante: era 1187
    # cravado aqui e 1203 derivado no gen_impacto — o mesmo fato com dois números, e o cravado
    # envelhecendo em silêncio a cada mês de IPCA novo.
    bolsa_hoje = round(BOLSA_EPOCA * deflator_ipca[str(BOLSA_ANO)])
    med_hoje = round(statistics.median(medianas)) if medianas else None
    desfecho = {
        "egressos": len(ids),
        "em_tech": sum(1 for a in alunos if a["id"] in ids and a["ainda_em_tech"]),
        "mediana_hoje": med_hoje,
        "bolsa_epoca_mensal": BOLSA_EPOCA, "bolsa_ano": BOLSA_ANO, "bolsa_em_2026": bolsa_hoje,
        "mult_nominal": round(med_hoje / BOLSA_EPOCA) if med_hoje else None,
        "mult_real": round(med_hoje / bolsa_hoje) if med_hoje else None,
    }
    return {"projetos": projetos, "total": total, "desfecho": desfecho,
            "fonte": "FAPES · relatorio_alocacao_bolsas (via PRODEST); "
                     "vínculo egresso↔projeto curado"}


def executar(*, hoje: Competencia) -> dict:   # noqa: ARG001 - fronteira única das etapas
    """`hoje` não é usado: o fomento é histórico e o deflator vem de `ibge_series`.

    A base da FAPES vive em outro repositório e nem sempre está montada (no CI não está). Sem
    ela, o artefato já gerado é mantido — o dado é histórico e não muda de mês para mês. Só
    levanta se nunca tiver sido gerado, porque aí "sem fomento" seria indistinguível de "sem a
    fonte".
    """
    if not FAPES.exists():
        alvo = dados.caminho("fapes_fomento")
        if alvo.exists():
            print(f"base FAPES não encontrada ({FAPES}) — mantendo {alvo.name} existente")
            return dados.ler("fapes_fomento")
        raise FileNotFoundError(
            f"base FAPES não encontrada em {FAPES} e não há {alvo.name} versionado. "
            "Monte o fapes-dashboard ou defina EGRESSOS_FAPES_ALOCACAO.")

    saida = montar(
        base_fapes=io.load_json(FAPES),
        alunos=dados.ler("alunos")["alunos"],
        consolidado=dados.ler("consolidado"),
        deflator_ipca=dados.ler("ibge_series")["series"]["ipca"]["deflator_para_base"],
    )
    dados.gravar("fapes_fomento", saida)
    return saida


def main() -> int:
    saida = executar(hoje=deflator.data_referencia(dados.ler("ibge_series")))
    for p in saida["projetos"]:
        print(f"  {p['projeto_id']} {p['titulo'][:40]:<40} | {p['bolsistas']} bolsistas "
              f"({','.join(p['bolsa_sigla'])}) | R$ {p['valor_alocado']:,} | "
              f"{p['periodo'][0]}→{p['periodo'][1]} | egressos={p['egressos']}")
    t = saida["total"]
    print(f"TOTAL: R$ {t['valor_total']:,} | {t['bolsistas_total']} bolsistas | "
          f"{t['egressos_total']} egressos | {t['n_projetos']} projetos")
    d = saida["desfecho"]
    print(f"DESFECHO: {d['em_tech']}/{d['egressos']} em tech | "
          f"mediana hoje R$ {d['mediana_hoje']:,} | ~{d['mult_nominal']}x nominal / "
          f"~{d['mult_real']}x real vs bolsa")
    return 0


if __name__ == "__main__":
    sys.exit(main())

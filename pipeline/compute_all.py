#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Série salarial do coorte — a casca que busca o dado e chama o núcleo.

A conta mora em `egressos_core.salarios`, que é pura e testável. Aqui ficam as três coisas que
ela não faz: ler os CSVs de ~150 MB do Stack Overflow, resolver caminho de arquivo, e gravar.

Antes, este arquivo era 230 linhas que **só funcionavam com `cwd=data/`**: ele abria
`../alunos.json` e escrevia `consolidado.json` por caminho relativo. Rodar de qualquer outro
diretório produzia `FileNotFoundError` — ou, pior, gravava o consolidado no lugar errado. Agora
os dois passam pelo catálogo (`egressos_core.dados`), e a etapa roda de onde for chamada.

A porta que o núcleo recebe é `amostra(edicao, trilha, exp)`: devolve os quantis anuais em US$
da edição pedida, ou `None` quando há menos de cinco respondentes. Do lado de cá dela mora o
pandas; do lado de lá, a fixture de três linhas que a suíte usa.

Uso:  python pipeline/compute_all.py     (de qualquer diretório)
"""
from __future__ import annotations

import json
import sys

import pandas as pd

import so_dataset
from egressos_core import dados, fontes, salarios

# Edições do survey que o modelo usa. A tabela de nomes de coluna NÃO está aqui: ela mudou três
# vezes entre 2018 e 2025 e mora em `egressos_core.fontes`.
PRIMEIRA_EDICAO = 2018

# Edição usada como referência de mercado — para o ano corrente e para todo ano posterior a ela.
#
# Por que NÃO é a edição mais recente disponível — as duas exclusões têm motivos diferentes:
#
# * 2025 está fora por falta de COLUNA: removeu YearsCodePro, que é como este modelo casa a
#   experiência do egresso com a do mercado. WorkExp e YearsCode medem outra população.
# * 2024 está fora por AMOSTRA, e isso foi medido. Incorporá-la derrubaria a mediana do coorte
#   em 2026 de R$ 17.073 para R$ 14.413 (-15,6%). A queda vem da fonte, não do mercado: a
#   subamostra brasileira caiu de 852 para 474 respondentes, e a variação por faixa de
#   experiência ficou -23%, -3%, -31%, -17%, +3%, -0,1% — mercado não cai 31% aos 10 anos de
#   carreira e fica estável aos 13. A Pesquisa Código Fonte, fonte brasileira independente com
#   17.046 respostas, mostra -2,2% em pleno e -3,0% em sênior no mesmo período.
#
# Trocar esta constante muda o número central do estudo. Ver specs/004-vigia-fontes-anuais/
# research.md, D6 e D11 (a coluna que sumiu) e D14 (o cruzamento).
EDICAO_MERCADO = 2023

MIN_PARA_PUBLICAR = 5       # abaixo disso não há mediana de mercado para o ponto
MIN_ANTES_DE_ALARGAR = 8    # abaixo disso, a faixa de experiência abre de ±1 para ±2

SOFTWARE = ["back-end", "front-end", "full-stack", "back end", "front end", "full stack",
            "mobile developer", "developer, mobile"]
DADOS_ = ["data scientist", "machine learning", "data or business analyst", "engineer, data",
          "data engineer", "business analyst"]

# Ordem e rótulos da anonimização. Integrar egresso novo = acrescentar nos dois, na mesma ordem
# (ver docs/ARQUITETURA.md e pipeline/analise.py, que casa por rótulo).
ORDEM = ["barbosa", "gary", "possatti", "helen", "renan", "andre", "tarcisio", "joel", "icaro",
         "gustavo", "marialuiza", "gabriel_barboza", "magnago", "martins_miranda", "geann",
         "rodrigo_maia", "andre_aguiar", "guilherme_gatti", "ivana", "joao_paulo",
         "lucas_coutinho", "marcos_dias", "phillipe", "anne_caroline", "brendon", "cassiano",
         "jennifer", "ana_rubia", "diego", "edvaldo", "magno", "pedro", "antonio", "cristian",
         "danilo", "marlon", "breno", "caio", "lucas_gomes", "derick", "marcos_carneiro",
         "mateus_garcia", "ana_carolina", "david_pantaleao", "renato", "kleber", "rafael",
         "andreangelo", "icaro_gandine", "paulo_ricardo"]
ROTULOS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q",
           "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "AA", "AB", "AC", "AD", "AE", "AF",
           "AG", "AH", "AI", "AJ", "AK", "AL", "AM", "AN", "AO", "AP", "AQ", "AR", "AS", "AT",
           "AU", "AV", "AW", "AX"]

_cache: dict[int, pd.DataFrame] = {}


def edicao_em_disco(ano: int) -> pd.DataFrame:
    """Respondentes brasileiros de uma edição, já filtrados e com uma linha por DevType."""
    if ano in _cache:
        return _cache[ano]
    colunas = fontes.colunas_exigidas(ano)
    sal, exp = colunas["remuneracao"], colunas["experiencia"]
    df = pd.read_csv(so_dataset.caminho_da_edicao(ano),
                     usecols=["Country", "DevType", exp, sal], low_memory=False)
    df = df[(df.Country == "Brazil") & df[sal].notna()]
    df = df[df[sal].between(3000, 500000)]
    df = df.assign(DevType=df.DevType.astype(str).str.lower().str.split(";")).explode("DevType")
    df["DevType"] = df.DevType.str.strip()
    # 2018 traz a experiência em faixas de texto ("9-11 years"), não em número.
    df["_exp"] = None if ano == 2018 else pd.to_numeric(
        df[exp].replace({"Less than 1 year": "0", "More than 50 years": "51"}), errors="coerce")
    df["_expraw"] = df[exp].astype(str).str.strip()
    df["_sal"] = df[sal]
    _cache[ano] = df
    return df


def _faixa_de_2018(exp: int) -> str:
    for lo, hi, rotulo in [(0, 2, "0-2 years"), (3, 5, "3-5 years"), (6, 8, "6-8 years"),
                           (9, 11, "9-11 years"), (12, 14, "12-14 years"), (15, 17, "15-17 years")]:
        if lo <= exp <= hi:
            return rotulo
    return "18-20 years"


def _recorte(df, trilha: str, exp: int, edicao: int):
    palavras = SOFTWARE if trilha == "Software" else DADOS_
    m = df[df.DevType.str.contains("|".join(palavras), na=False, regex=True)]
    if edicao == 2018:
        return m[m._expraw == _faixa_de_2018(exp)]
    achado = m[(m._exp >= max(0, exp - 1)) & (m._exp <= exp + 1)]
    if len(achado) < MIN_ANTES_DE_ALARGAR:
        achado = m[(m._exp >= max(0, exp - 2)) & (m._exp <= exp + 2)]
    return achado


def amostra(edicao: int, trilha: str, exp: int):
    """Porta do núcleo: quantis anuais em US$, ou None se a amostra é pequena demais."""
    s = _recorte(edicao_em_disco(edicao), trilha, exp, edicao)._sal
    if len(s) < MIN_PARA_PUBLICAR:
        return None
    return {"n": int(len(s)), "p25": s.quantile(.25), "med": s.median(), "p75": s.quantile(.75)}


def mercado_hoje_factory(cambio_base: float):
    """O que o mercado paga HOJE para (trilha, experiência), em R$/mês do ano-base."""
    def mercado_hoje(trilha: str, exp: int):
        s = _recorte(edicao_em_disco(EDICAO_MERCADO), trilha, exp, EDICAO_MERCADO)._sal
        return round(s.median() * cambio_base / 12) if len(s) >= MIN_PARA_PUBLICAR else None
    return mercado_hoje


def executar() -> dict:
    """Recalcula e grava `consolidado.json`. Devolve o que gravou."""
    series = dados.ler("salario_minimo")
    sm = {int(k): v for k, v in series["sm_por_ano"].items()}
    fx = {int(k): v for k, v in series["cambio_por_ano"].items()}
    ipca = {int(k): v for k, v in series["deflator_ipca_por_ano"].items()}

    consolidado, pulados = salarios.consolidar(
        dados.ler("alunos")["alunos"], amostra, mercado_hoje_factory(fx[max(fx)]),
        ordem=ORDEM, rotulos=ROTULOS,
        cambio_por_ano=fx, deflator_por_ano=ipca, salario_minimo_por_ano=sm,
        primeira_edicao=PRIMEIRA_EDICAO, ultima_edicao=EDICAO_MERCADO)

    for rotulo, ident in pulados:
        print(f"  [skip perfil {rotulo}] {ident}: sem série de mercado")

    dados.gravar("consolidado", consolidado)
    return consolidado


def _js(itens, chaves):
    return ",".join("{" + ",".join(
        f'{k}:{o[k] if o[k] is not None else "null"}' for k in chaves) + "}" for o in itens)


def main() -> int:
    # Sem os CSVs (é o caso do CI), o consolidado já versionado continua válido: o survey é
    # anual, e quem detecta edição nova é pipeline/vigia_fontes.py. Este é um comportamento da
    # CASCA, não do domínio — o núcleo não sabe que existe arquivo.
    faltando = [a for a in range(PRIMEIRA_EDICAO, EDICAO_MERCADO + 1)
                if not so_dataset.caminho_da_edicao(a).exists()]
    if faltando:
        if dados.caminho("consolidado").exists():
            print(f"CSVs do Stack Overflow ausentes {faltando} — mantendo consolidado.json versionado")
            return 0
        raise SystemExit(
            f"ABORT: faltam os CSVs {faltando} e não há consolidado.json — obtenha as edições "
            "com `python pipeline/so_dataset.py --edicao <ano>` (verifica o sha256 da origem)")

    consolidado = executar()

    print("KPI:", json.dumps(consolidado["kpi"], ensure_ascii=False))
    print("\nPERFIS_JS:")
    for p in consolidado["perfis"]:
        bolsa = p["bolsa"] if p["bolsa"] is not None else "null"
        print(f'  {{perfil:"{p["perfil"]}",trilha:"{p["trilha"]}",'
              f'em_tech:{str(p["em_tech"]).lower()},anos:{p["anos"]},bolsa:{bolsa},'
              f'med_ini:{p["med_ini"]},med_atual:{p["med_atual"]},cresc:{p["cresc"]}}},')
    print("\nAGG_JS:")
    print(_js(consolidado["agregado"], ["exp", "lo", "hi", "med", "n"]))
    print("\nAGG_PV_JS:")
    print(_js(consolidado["pv"], ["exp", "med"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

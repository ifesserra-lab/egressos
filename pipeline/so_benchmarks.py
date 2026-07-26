#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrai do Stack Overflow Developer Survey os benchmarks internacionais em US$ e grava
data/so_benchmarks.json — para que o gerador da página não precise reler os CSVs de ~200 MB.

Produz:
  por_pais            mediana US$/mês por país, na faixa de experiência da mediana do coorte
  global              mediana US$/mês mundial na mesma faixa
  por_moeda_brasil    respondentes DO BRASIL separados pela moeda declarada (BRL x USD),
                      por faixa de experiência — mede o prêmio de receber em dólar
  serie_anual         mediana US$/mês por edição do survey (Brasil, global, EUA)

Filtros (iguais aos de compute_all.py, para os números conversarem entre si):
  - DevType contém back-end / front-end / full-stack / mobile
  - salário convertido entre US$ 3 mil e US$ 500 mil/ano (corta troll e estagiário sem salário)

Uso:  python pipeline/so_benchmarks.py
"""
import json, pathlib
import pandas as pd

BASE = pathlib.Path("/caminho/para/salario")
DATA = BASE / "data"

SAL = {2018: "ConvertedSalary", 2019: "ConvertedComp", 2020: "ConvertedComp",
       2021: "ConvertedCompYearly", 2022: "ConvertedCompYearly", 2023: "ConvertedCompYearly"}
ULT = 2023                      # edição mais recente disponível localmente
SW  = ["back-end", "front-end", "full-stack", "mobile"]

PAISES = [("United States of America", "Estados Unidos"), ("Canada", "Canadá"),
          ("United Kingdom of Great Britain and Northern Ireland", "Reino Unido"),
          ("Germany", "Alemanha"), ("Netherlands", "Holanda"), ("Poland", "Polônia"),
          ("Portugal", "Portugal"), ("Spain", "Espanha"), ("Mexico", "México"),
          ("Chile", "Chile"), ("Brazil", "Brasil"), ("India", "Índia")]
FAIXAS = [(0, 2, "0 a 2 anos"), (3, 5, "3 a 5 anos"), (6, 8, "6 a 8 anos"),
          (9, 13, "9 a 13 anos"), (14, 60, "14 anos ou mais")]
N_MIN = 12                      # abaixo disso a mediana não é publicável


def carrega(ano, com_moeda=False):
    """com_moeda só é pedido na edição de referência — o nome da coluna varia entre edições
    (2018: sem; 2019–2020: CurrencySymbol; 2021+: Currency)."""
    sal = SAL[ano]
    exp = "YearsCodingProf" if ano == 2018 else "YearsCodePro"
    cols = ["Country", "DevType", exp, sal]
    if com_moeda:
        cab = pd.read_csv(DATA / f"public-{ano}.csv", nrows=0).columns
        moeda = next((c for c in ("Currency", "CurrencySymbol", "CurrencyDesc") if c in cab), None)
        if not moeda:
            raise SystemExit(f"ABORT: edição {ano} não tem coluna de moeda")
        cols.append(moeda)
    df = pd.read_csv(DATA / f"public-{ano}.csv", usecols=cols, low_memory=False)
    df = df[df[sal].notna()]
    df = df[df[sal].between(3000, 500000)]
    df["dt"] = df.DevType.astype(str).str.lower()
    df = df[df.dt.str.contains("|".join(SW), na=False)]
    df["exp"] = pd.to_numeric(
        df[exp].replace({"Less than 1 year": "0", "More than 50 years": "51"}), errors="coerce")
    df["mes"] = df[sal] / 12
    if com_moeda:
        df["cur"] = df[moeda].astype(str).str[:3]
    return df


def med(s):
    return int(round(s.median())) if len(s) >= N_MIN else None


def main():
    falta = [a for a in SAL if not (DATA / f"public-{a}.csv").exists()]
    if falta:
        # ver nota em compute_all.py: os CSVs não são versionados e o survey não tem
        # edição nova desde 2023, então o benchmark já gerado continua válido.
        alvo = DATA / "so_benchmarks.json"
        if alvo.exists():
            print(f"CSVs do Stack Overflow ausentes {falta} — mantendo {alvo.name} versionado")
            return
        raise SystemExit(f"ABORT: faltam os CSVs {falta} e não há so_benchmarks.json — "
                         "baixe as edições em https://survey.stackoverflow.co/ para data/")

    df = carrega(ULT, com_moeda=True)
    faixa_ref = (9, 13)                       # mediana de carreira do coorte = 11 anos
    lo, hi = faixa_ref
    ref = df[(df.exp >= lo) & (df.exp <= hi)]

    por_pais = []
    for cod, nome in PAISES:
        s = ref[ref.Country == cod].mes
        m = med(s)
        if m:
            por_pais.append({"pais": nome, "usd_mes": m, "n": int(len(s))})
    por_pais.sort(key=lambda d: -d["usd_mes"])

    br = df[df.Country == "Brazil"]
    por_moeda = []
    for a, b, rot in FAIXAS:
        sub = br[(br.exp >= a) & (br.exp <= b)]
        brl, usdc = sub[sub.cur == "BRL"].mes, sub[sub.cur == "USD"].mes
        if med(brl) and med(usdc):
            por_moeda.append({"faixa": rot, "brl_usd_mes": med(brl), "n_brl": int(len(brl)),
                              "usd_usd_mes": med(usdc), "n_usd": int(len(usdc)),
                              "razao": round(med(usdc) / med(brl), 2)})
    tb, tu = br[br.cur == "BRL"].mes, br[br.cur == "USD"].mes
    por_moeda.append({"faixa": "Todos", "brl_usd_mes": med(tb), "n_brl": int(len(tb)),
                      "usd_usd_mes": med(tu), "n_usd": int(len(tu)),
                      "razao": round(med(tu) / med(tb), 2)})

    serie = []
    for ano in sorted(SAL):
        d = carrega(ano)
        us = d[d.Country.isin(["United States of America", "United States"])].mes
        serie.append({"ano": ano, "brasil_usd_mes": med(d[d.Country == "Brazil"].mes),
                      "global_usd_mes": med(d.mes), "eua_usd_mes": med(us),
                      "n_brasil": int((d.Country == "Brazil").sum()), "n_total": int(len(d))})

    out = {
        "titulo": "Benchmarks salariais internacionais — Stack Overflow Developer Survey",
        "fonte": f"Stack Overflow Developer Survey {min(SAL)}–{ULT} (survey.stackoverflow.co)",
        "gerado_por": "pipeline/so_benchmarks.py",
        "edicao_referencia": ULT,
        "unidade": "US$/mês (mediana) — ConvertedCompYearly ÷ 12, conversão do próprio survey",
        "filtros": {"devtype_contem": SW, "salario_anual_usd": [3000, 500000],
                    "n_minimo_para_publicar": N_MIN},
        "faixa_experiencia_referencia": f"{lo} a {hi} anos (mediana de carreira do coorte = 11)",
        "notas": [
            "por_moeda_brasil usa o campo Currency declarado pelo respondente: mesmo país e mesma "
            "experiência, separados por moeda do contracheque.",
            "Não há edição do survey após 2023 — a série anual termina nesse ano.",
        ],
        "global_usd_mes": med(ref.mes), "global_n": int(len(ref)),
        "por_pais": por_pais, "por_moeda_brasil": por_moeda, "serie_anual": serie,
    }
    (DATA / "so_benchmarks.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"OK — data/so_benchmarks.json")
    print(f"  global {lo}-{hi} anos: US$ {out['global_usd_mes']:,}/mês (n={out['global_n']})")
    print(f"  {len(por_pais)} países · {len(por_moeda)} faixas de moeda · {len(serie)} edições")
    for m in por_moeda:
        print(f"    {m['faixa']:18s} BRL US$ {m['brl_usd_mes']:6,} (n={m['n_brl']:4d})  "
              f"USD US$ {m['usd_usd_mes']:6,} (n={m['n_usd']:3d})  {m['razao']}x")


if __name__ == "__main__":
    main()

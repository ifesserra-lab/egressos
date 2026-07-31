#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baixa as séries macro oficiais usadas como régua do estudo e grava JSONs reprodutíveis:

  data/salario_minimo.json  -> salário mínimo nominal por ano + reajuste + ganho real + valor em R$ do ano-base
  data/ibge_series.json     -> IPCA e INPC (número-índice mensal + média anual + deflatores) e a série de SM

Fontes (todas públicas, sem chave de API):
  - Salário mínimo : IPEADATA, série MTE12_SALMIN12 ("Salário mínimo vigente", mensal, R$).
                     Fonte primária: Ministério da Economia/Trabalho.
  - Câmbio USD→BRL : IPEADATA, série BM12_ERV12 ("Taxa de câmbio - R$/US$ - comercial - venda -
                     média", mensal). Substitui a tabela de câmbio que estava fixa no código.
  - IPCA           : IBGE/SIDRA tabela 1737, variável 2266 (número-índice, base dez/1993 = 100).
  - INPC           : IBGE/SIDRA tabela 1736, variável 2289 (número-índice). É o índice usado na
                     política de valorização do mínimo (INPC do ano anterior + PIB de dois anos antes).

Por que INPC E IPCA: o ganho REAL do mínimo se mede contra o INPC (é a regra legal);
o resto do estudo deflaciona por IPCA (é o índice geral). Os dois ficam no JSON.

Uso:  python pipeline/ibge_series.py            (baixa e grava)
      python pipeline/ibge_series.py --offline  (só recalcula a partir do cache em data/_cache_ibge/)

Se a rede falhar e houver cache, usa o cache e avisa. Se não houver, aborta — o pipeline
NÃO deve seguir com número inventado.
"""
import datetime
import json
import sys
import urllib.error
import urllib.request

from egressos_core import dados, deflator
from egressos_core.paths import ROOT as BASE

DATA = BASE / "data"
CACHE = DATA / "_cache_ibge"

ANO_BASE = 2026          # tudo que for "em R$ de X" usa este ano
ANO_INI  = 2011          # o pipeline salarial começa aqui

SIDRA = "https://apisidra.ibge.gov.br/values/t/{t}/n1/all/v/{v}/p/all"
IPEA  = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{s}')"

FONTES = {
    "ipca": {"url": SIDRA.format(t=1737, v=2266), "cache": "ipca_1737.json",
             "titulo": "IPCA — número-índice (base dez/1993 = 100)",
             "fonte": "IBGE/SIDRA tabela 1737, variável 2266"},
    "inpc": {"url": SIDRA.format(t=1736, v=2289), "cache": "inpc_1736.json",
             "titulo": "INPC — número-índice",
             "fonte": "IBGE/SIDRA tabela 1736, variável 2289"},
    "sm":   {"url": IPEA.format(s="MTE12_SALMIN12"), "cache": "sm_ipea.json",
             "titulo": "Salário mínimo vigente (mensal, R$ nominais)",
             "fonte": "IPEADATA série MTE12_SALMIN12 — Min. Economia/Trabalho"},
    "fx":   {"url": IPEA.format(s="BM12_ERV12"), "cache": "fx_ipea.json",
             "titulo": "Taxa de câmbio R$/US$ — comercial, venda, média mensal",
             "fonte": "IPEADATA série BM12_ERV12 — Banco Central"},
}


def baixa(key, offline=False):
    """Retorna o JSON bruto da fonte. Usa cache quando offline ou quando a rede falha."""
    meta = FONTES[key]
    cache = CACHE / meta["cache"]
    if offline:
        if not cache.exists():
            sys.exit(f"ABORT: --offline mas não há cache em {cache}")
        print(f"  [cache] {key}")
        return json.loads(cache.read_text(encoding="utf-8"))
    try:
        with urllib.request.urlopen(meta["url"], timeout=90) as r:
            raw = r.read().decode("utf-8")
        CACHE.mkdir(parents=True, exist_ok=True)
        cache.write_text(raw, encoding="utf-8")
        print(f"  [rede ] {key}  ({len(raw)//1024} KB)")
        return json.loads(raw)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        if cache.exists():
            print(f"  [cache] {key}  (rede falhou: {e})")
            return json.loads(cache.read_text(encoding="utf-8"))
        sys.exit(f"ABORT: {key} indisponível e sem cache — {e}")


def parse_sidra(raw):
    """SIDRA devolve uma linha de cabeçalho + linhas com D3C = AAAAMM e V = valor."""
    out = {}
    for row in raw[1:]:
        v = row.get("V")
        if v in (None, "...", "..", "-", ""):
            continue
        out[row["D3C"]] = float(v)
    if not out:
        sys.exit("ABORT: SIDRA devolveu série vazia")
    return out


def parse_ipea(raw):
    """IPEADATA OData: VALDATA ISO + VALVALOR."""
    out = {}
    for row in raw["value"]:
        if row.get("VALVALOR") is None:
            continue
        out[row["VALDATA"][:7].replace("-", "")] = float(row["VALVALOR"])
    if not out:
        sys.exit("ABORT: IPEADATA devolveu série vazia")
    return out


def executar(*, hoje: datetime.date | None = None, offline: bool = False) -> None:
    """Baixa as séries e grava `salario_minimo` e `ibge_series`.

    Esta é a única etapa que **define** a data de referência do relatório em vez de recebê-la: o
    `mes_base` é o último mês publicado do IPCA, e sai daqui para as outras 15 etapas. O parâmetro
    `hoje` existe para a assinatura ser uniforme (ver o contrato das etapas) e é ignorado de
    propósito — usá-lo aqui seria deixar o relógio da máquina decidir até onde a série vai.
    """
    del hoje
    print("== séries macro (IBGE + IPEADATA) ==")
    ipca = parse_sidra(baixa("ipca", offline))
    inpc = parse_sidra(baixa("inpc", offline))
    sm   = parse_ipea(baixa("sm", offline))
    fx   = parse_ipea(baixa("fx", offline))

    ult_ipca = max(ipca)                 # ex.: "202606"
    ipca_ano = deflator.media_anual(ipca)
    inpc_ano = deflator.media_anual(inpc)
    # (não há mais `base_ipca` do último mês: a base virou a MÉDIA do ano-base, abaixo)

    # Deflatores, câmbio e a tabela do salário mínimo: a conta mora em egressos_core.deflator,
    # com teste de caracterização contra estes mesmos JSONs (tests/test_deflator.py).
    deflatores = deflator.deflatores_ipca(ipca, ano_ini=ANO_INI, ano_base=ANO_BASE)
    fx_ano = deflator.cambio_por_ano(fx, ano_ini=ANO_INI, ano_base=ANO_BASE)

    anos = deflator.salario_minimo_por_ano(sm, inpc, ipca, ano_ini=ANO_INI, ano_base=ANO_BASE)

    smj = {
        "titulo": "Salário mínimo nacional por ano — nominal, reajuste e ganho real",
        "fonte_salario_minimo": FONTES["sm"]["fonte"],
        "fonte_inflacao": FONTES["inpc"]["fonte"] + " (ganho real) · " + FONTES["ipca"]["fonte"] + " (deflator)",
        "url_salario_minimo": FONTES["sm"]["url"],
        "unidade": "R$/mês nominais; percentuais em % a.a.",
        "ano_base_deflator": ANO_BASE,
        "mes_base_deflator": ult_ipca,
        "notas": [
            "media_ponderada = média dos 12 valores mensais vigentes (anos com dois valores, "
            "como 2020 e 2023, ficam entre os dois).",
            "reajuste_pct = valor de janeiro sobre o último valor vigente de dezembro anterior — "
            "é o número do decreto.",
            "ganho_real_pct = reajuste deflacionado pelo INPC acumulado do ano anterior, que é o "
            "índice previsto na política de valorização do mínimo.",
            "Conferência: 2026 = R$ 1.621 (+6,79%, Decreto 12.797/2025); 2024 = +6,97%; 2018 = +1,81%.",
        ],
        "por_ano": anos,
        # atalhos para consumo direto no pipeline salarial
        "sm_por_ano": {a["ano"]: a["media_ponderada"] for a in anos},
        "deflator_ipca_por_ano": deflatores,
        "cambio_por_ano": fx_ano,
    }
    dados.gravar("salario_minimo", smj)

    ser = {
        "titulo": "Séries macroeconômicas de referência do estudo de egressos",
        "gerado_por": "pipeline/ibge_series.py",
        "ano_base": ANO_BASE, "mes_base": ult_ipca,
        "series": {
            "ipca": {"titulo": FONTES["ipca"]["titulo"], "fonte": FONTES["ipca"]["fonte"],
                     "url": FONTES["ipca"]["url"], "unidade": "número-índice (dez/1993 = 100)",
                     "primeiro": min(ipca), "ultimo": ult_ipca, "n_meses": len(ipca),
                     "mensal": {p: ipca[p] for p in sorted(ipca) if p >= f"{ANO_INI}01"},
                     "media_anual": {y: round(v, 2) for y, v in sorted(ipca_ano.items()) if y >= ANO_INI},
                     "deflator_para_base": deflatores},
            "inpc": {"titulo": FONTES["inpc"]["titulo"], "fonte": FONTES["inpc"]["fonte"],
                     "url": FONTES["inpc"]["url"], "unidade": "número-índice",
                     "primeiro": min(inpc), "ultimo": max(inpc), "n_meses": len(inpc),
                     "mensal": {p: inpc[p] for p in sorted(inpc) if p >= f"{ANO_INI}01"},
                     "media_anual": {y: round(v, 2) for y, v in sorted(inpc_ano.items()) if y >= ANO_INI}},
            "salario_minimo": {"titulo": FONTES["sm"]["titulo"], "fonte": FONTES["sm"]["fonte"],
                               "url": FONTES["sm"]["url"], "unidade": "R$/mês nominais",
                               "primeiro": min(sm), "ultimo": max(sm), "n_meses": len(sm),
                               "mensal": {p: sm[p] for p in sorted(sm) if p >= f"{ANO_INI}01"},
                               "por_ano": anos},
            "cambio": {"titulo": FONTES["fx"]["titulo"], "fonte": FONTES["fx"]["fonte"],
                       "url": FONTES["fx"]["url"], "unidade": "R$ por US$ 1",
                       "primeiro": min(fx), "ultimo": max(fx), "n_meses": len(fx),
                       "mensal": {p: fx[p] for p in sorted(fx) if p >= f"{ANO_INI}01"},
                       "media_anual": fx_ano}},
    }
    dados.gravar("ibge_series", ser)

    print(f"\nOK — IPCA até {ult_ipca} · INPC até {max(inpc)} · SM até {max(sm)} · câmbio até {max(fx)}")
    print(f"  data/salario_minimo.json  ({len(anos)} anos)")
    print("  data/ibge_series.json     (3 séries)")
    u = anos[-1]
    print(f"  {u['ano']}: SM R$ {u['media_ponderada']:.2f} · reajuste {u['reajuste_pct']}% · "
          f"real {u['ganho_real_pct']}% · em R$ de {ANO_BASE}: {u[f'em_reais_de_{ANO_BASE}']}")


if __name__ == "__main__":
    executar(offline="--offline" in sys.argv)

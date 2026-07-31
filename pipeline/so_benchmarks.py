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

DUAS EDIÇÕES, DOIS PAPÉIS — e a distinção é o que permite as edições novas entrarem:

  * `serie_anual` é mediana por edição, SEM corte de experiência. Vai até a edição mais
    recente (2025).
  * `por_pais`, `global` e `por_moeda_brasil` são calculados na faixa de experiência do
    coorte, e saem todos de UMA edição — a de referência.

A edição 2025 removeu `YearsCodePro`, então não pode ser a referência. As candidatas que ela
tem no lugar (`WorkExp`, `YearsCode`) medem outra população — trabalho de qualquer natureza, e
programação incluindo os anos de aprendizado. Usar uma delas mudaria O QUE a comparação mede
sem mudar o rótulo da página, então nenhuma substituta é inventada aqui.

A referência também NÃO é automaticamente a edição mais recente que tem a coluna. Ela é
escolhida por amostra, e o motivo está medido em `candidatas_a_referencia`, no arquivo gerado:
o recorte da referência é país × faixa de experiência × moeda do contracheque, isto é, uma
subamostra de subamostra. A edição 2024 tem menos da metade da amostra útil da 2023 — trocar a
referência por ela derrubaria o Chile da lista de países e apagaria as três faixas de BRL×USD,
publicando um número mais novo e mais barulhento. Recência não vale isso.

Ver specs/004-vigia-fontes-anuais/research.md, D6 (o achado), D11 (papéis separados) e
D12 (por que a referência é escolhida por amostra).

Os nomes das colunas vêm de `egressos_core.fontes`, não de um mapa local: eles mudaram três
vezes entre 2018 e 2025, e ter a tabela em dois lugares é ter duas versões dela.

Filtros (iguais aos de compute_all.py, para os números conversarem entre si):
  - DevType contém back-end / front-end / full-stack / mobile
  - salário convertido entre US$ 3 mil e US$ 500 mil/ano (corta troll e estagiário sem salário)

Uso:  python pipeline/so_benchmarks.py
      python pipeline/so_dataset.py --edicao <ano>   # para obter uma edição verificada
"""
import json

import pandas as pd

from egressos_core import fontes
from egressos_core.paths import ROOT as BASE

DATA = BASE / "data"

#: Edições usadas. A série cobre todas; a de referência é uma só.
EDICOES = tuple(range(2018, 2026))

#: Edição de referência dos recortes por experiência. MEDIDA, não "a mais nova":
#:
#:   edição  n da faixa 9-13   países publicáveis   faixas BRL×USD
#:   2023          6.350               12                  3
#:   2024          2.840               11                  0
#:
#: A 2024 é mais recente e tem menos da metade da amostra útil. Como o recorte é país × faixa
#: × moeda, essa perda não aparece como "menos precisão": aparece como país que sai da lista e
#: como tabela que fica vazia. Ver research.md D12.
EDICAO_REFERENCIA = 2023

#: Quais edições poderiam ser a referência (têm experiência profissional) e são recentes o
#: bastante para servir de comparação de mercado. O arquivo gerado grava a medição das três,
#: para a escolha ser auditável por quem baixa o dado — e para a próxima pessoa ver, no diff,
#: se uma edição nova passou a ser a melhor candidata.
AVALIADAS = (2022, 2023, 2024)

SW  = ["back-end", "front-end", "full-stack", "mobile"]

PAISES = [("United States of America", "Estados Unidos"), ("Canada", "Canadá"),
          ("United Kingdom of Great Britain and Northern Ireland", "Reino Unido"),
          ("Germany", "Alemanha"), ("Netherlands", "Holanda"), ("Poland", "Polônia"),
          ("Portugal", "Portugal"), ("Spain", "Espanha"), ("Mexico", "México"),
          ("Chile", "Chile"), ("Brazil", "Brasil"), ("India", "Índia")]
FAIXAS = [(0, 2, "0 a 2 anos"), (3, 5, "3 a 5 anos"), (6, 8, "6 a 8 anos"),
          (9, 13, "9 a 13 anos"), (14, 60, "14 anos ou mais")]
#: Faixa de experiência em que o mercado é comparado com o coorte. Ela **sai do coorte**, não
#: de um arredondamento: é o intervalo interquartil medido em consolidado.json — q1=8,
#: mediana=11, q3=13, n=49. Antes era (9, 13), um ±2 em volta da mediana escolhido à mão; a
#: mediana continua 11, mas a metade do meio do coorte começa em 8.
#:
#: Não é derivada aqui em tempo de execução de propósito: `so_benchmarks.py` roda ANTES de
#: `compute_all.py` no build (build_report.py, passos 50 e 53), então ler consolidado.json
#: daqui pegaria o coorte da execução anterior. Quem confere que a declaração continua igual ao
#: coorte é a suíte, que lê os dois artefatos sem depender de ordem.
FAIXA_REFERENCIA = (8, 13)
QUARTIS_DO_COORTE = {"q1": 8, "mediana": 11, "q3": 13, "n": 49}
N_MIN = 12                      # abaixo disso a mediana não é publicável

LICENCA = {
    "licenca": "ODbL 1.0 (base de dados) + DbCL 1.0 (conteúdo)",
    "licenca_url": "https://opendatacommons.org/licenses/odbl/1-0/",
    "atribuicao": "Stack Overflow Annual Developer Survey — survey.stackoverflow.co",
}


def cabecalho_local(ano):
    """Nomes das colunas do CSV em disco, tolerando BOM e aspas (a edição 2025 tem os dois)."""
    with (DATA / f"public-{ano}.csv").open("r", encoding="utf-8-sig") as f:
        return fontes.nomes_do_cabecalho(f.readline())


def carrega(ano, com_moeda=False, com_experiencia=True):
    """Lê a edição, já filtrada. Confere a estrutura ANTES de ler 200 MB.

    `com_experiencia=False` é o que permite usar uma edição que não publica experiência
    profissional na série anual — que não usa esse corte.
    """
    colunas = fontes.colunas_exigidas(ano)
    exigidas = {"pais": colunas["pais"], "atuacao": colunas["atuacao"],
                "remuneracao": colunas["remuneracao"]}

    if com_experiencia:
        if "experiencia" not in colunas:
            raise SystemExit(
                f"ABORT: a edição {ano} não publica experiência profissional "
                f"({fontes.COLUNA_EXPERIENCIA_PROFISSIONAL} ausente na origem), então ela não "
                "pode ser a edição de referência. Escolher uma coluna substituta é decisão de "
                "método: ver specs/004-vigia-fontes-anuais/research.md, D6 e D11."
            )
        exigidas["experiencia"] = colunas["experiencia"]

    if com_moeda:
        if "moeda" not in colunas:
            raise SystemExit(f"ABORT: edição {ano} não declara moeda do respondente")
        exigidas["moeda"] = colunas["moeda"]

    faltando = fontes.confere_estrutura(cabecalho_local(ano), exigidas)
    if faltando:
        raise SystemExit(
            f"ABORT: a edição {ano} em disco não tem as colunas {', '.join(faltando)}. "
            f"Rode `python pipeline/so_dataset.py --edicao {ano} --forca` para obter de novo."
        )

    sal = exigidas["remuneracao"]
    df = pd.read_csv(DATA / f"public-{ano}.csv", usecols=list(exigidas.values()),
                     low_memory=False, encoding="utf-8-sig")
    df = df[df[sal].notna()]
    df = df[df[sal].between(3000, 500000)]
    df["dt"] = df[exigidas["atuacao"]].astype(str).str.lower()
    df = df[df.dt.str.contains("|".join(SW), na=False)]
    if com_experiencia:
        df["exp"] = pd.to_numeric(
            df[exigidas["experiencia"]].replace(
                {"Less than 1 year": "0", "More than 50 years": "51"}), errors="coerce")
    df["mes"] = df[sal] / 12
    if com_moeda:
        df["cur"] = df[exigidas["moeda"]].astype(str).str[:3]
    df["pais"] = df[exigidas["pais"]]
    return df


def med(s):
    return int(round(s.median())) if len(s) >= N_MIN else None


def recortes(ano):
    """Os três recortes que saem da edição de referência, para um ano qualquer.

    Existe como função para que as candidatas sejam medidas pelo **mesmo** código que publica:
    uma avaliação feita com outra conta não avaliaria a escolha de verdade.
    """
    df = carrega(ano, com_moeda=True)
    lo, hi = FAIXA_REFERENCIA
    ref = df[(df.exp >= lo) & (df.exp <= hi)]

    por_pais = []
    for cod, nome in PAISES:
        s = ref[ref.pais == cod].mes
        m = med(s)
        if m:
            por_pais.append({"pais": nome, "usd_mes": m, "n": int(len(s))})
    por_pais.sort(key=lambda d: -d["usd_mes"])

    br = df[df.pais == "Brazil"]
    por_moeda = []
    for a, b, rot in FAIXAS:
        sub = br[(br.exp >= a) & (br.exp <= b)]
        brl, usdc = sub[sub.cur == "BRL"].mes, sub[sub.cur == "USD"].mes
        if med(brl) and med(usdc):
            por_moeda.append({"faixa": rot, "brl_usd_mes": med(brl), "n_brl": int(len(brl)),
                              "usd_usd_mes": med(usdc), "n_usd": int(len(usdc)),
                              "razao": round(med(usdc) / med(brl), 2)})
    faixas_com_dado = len(por_moeda)
    tb, tu = br[br.cur == "BRL"].mes, br[br.cur == "USD"].mes
    por_moeda.append({"faixa": "Todos", "brl_usd_mes": med(tb), "n_brl": int(len(tb)),
                      "usd_usd_mes": med(tu), "n_usd": int(len(tu)),
                      "razao": round(med(tu) / med(tb), 2)})

    # Corte AGRUPADO por moeda, do piso da faixa de referência em diante. Serve para uma coisa
    # só: comparar edições entre si. As faixas finas acima não existem nas edições recentes (a
    # 2024 tem 32 respondentes em dólar no Brasil INTEIRO, espalhados em cinco faixas), e sem um
    # corte que as duas edições sustentem não há como responder "o número de 2023 ainda vale?".
    grosso = br[br.exp >= lo]
    gb, gu = grosso[grosso.cur == "BRL"].mes, grosso[grosso.cur == "USD"].mes
    mgb, mgu = med(gb), med(gu)
    agrupado = None
    if mgb and mgu:
        agrupado = {"faixa": f"{lo} anos ou mais", "brl_usd_mes": mgb, "n_brl": int(len(gb)),
                    "usd_usd_mes": mgu, "n_usd": int(len(gu)), "razao": round(mgu / mgb, 2)}

    return {
        "edicao": ano,
        "global_usd_mes": med(ref.mes),
        "n_faixa_referencia": int(len(ref)),
        "paises_publicaveis": len(por_pais),
        "faixas_de_moeda_publicaveis": faixas_com_dado,
        "por_pais": por_pais,
        "por_moeda_brasil": por_moeda,
        "moeda_agrupada": agrupado,
    }


def main():
    falta = [a for a in EDICOES if not (DATA / f"public-{a}.csv").exists()]
    if falta:
        # Os CSVs não são versionados (~150 MB por edição, re-obteníveis). Sem eles, o
        # benchmark já commitado continua válido: quem detecta edição nova é o vigia mensal
        # (pipeline/vigia_fontes.py), não a ausência de arquivo aqui.
        alvo = DATA / "so_benchmarks.json"
        if alvo.exists():
            print(f"CSVs do Stack Overflow ausentes {falta} — mantendo {alvo.name} versionado")
            return
        raise SystemExit(f"ABORT: faltam os CSVs {falta} e não há so_benchmarks.json — "
                         "obtenha as edições com `python pipeline/so_dataset.py --edicao <ano>`")

    avaliadas = [recortes(a) for a in AVALIADAS]
    escolhida = next(r for r in avaliadas if r["edicao"] == EDICAO_REFERENCIA)
    melhor = max(avaliadas, key=lambda r: r["n_faixa_referencia"])
    if melhor["edicao"] != EDICAO_REFERENCIA:
        # Aviso, não falha: mudar a edição de referência muda número publicado, e isso é
        # decisão de quem revisa. O que o gerador faz é não deixar passar em silêncio.
        print(f"AVISO — a edição {melhor['edicao']} tem amostra maior na faixa de referência "
              f"({melhor['n_faixa_referencia']:,} contra {escolhida['n_faixa_referencia']:,} da "
              f"{EDICAO_REFERENCIA}). Reavalie EDICAO_REFERENCIA (research.md D12).")

    lo, hi = FAIXA_REFERENCIA
    por_pais = escolhida["por_pais"]
    por_moeda = escolhida["por_moeda_brasil"]

    serie = []
    for ano in EDICOES:
        # Sem experiência: a série é mediana por edição, sem corte de faixa. É isso que deixa
        # a edição 2025 entrar aqui sem participar dos recortes por país.
        d = carrega(ano, com_experiencia=False)
        us = d[d.pais.isin(["United States of America", "United States"])].mes
        serie.append({"ano": ano, "brasil_usd_mes": med(d[d.pais == "Brazil"].mes),
                      "global_usd_mes": med(d.mes), "eua_usd_mes": med(us),
                      "n_brasil": int((d.pais == "Brazil").sum()), "n_total": int(len(d))})

    ultima = max(EDICOES)
    out = {
        "titulo": "Benchmarks salariais internacionais — Stack Overflow Developer Survey",
        "fonte": f"Stack Overflow Developer Survey {min(EDICOES)}–{ultima} "
                 "(survey.stackoverflow.co)",
        "gerado_por": "pipeline/so_benchmarks.py",
        "edicao_referencia": EDICAO_REFERENCIA,
        "edicao_mais_recente_na_serie": ultima,
        "criterio_da_edicao_referencia":
            "amostra utilizável no recorte país × faixa de experiência × moeda, não recência: "
            "uma edição mais nova com metade da amostra derruba país da lista e esvazia a "
            "tabela por moeda. A medição das candidatas está em candidatas_a_referencia, e "
            "corroboracao mostra o que as outras edições dizem no corte que elas sustentam.",
        "faixa_referencia_derivada_de":
            "intervalo interquartil dos anos de carreira do coorte (consolidado.json): "
            f"q1={QUARTIS_DO_COORTE['q1']}, mediana={QUARTIS_DO_COORTE['mediana']}, "
            f"q3={QUARTIS_DO_COORTE['q3']}, n={QUARTIS_DO_COORTE['n']}. Antes era um ±2 em "
            "volta da mediana, escolhido à mão.",
        "corroboracao": {
            "o_que_e":
                f"O mesmo corte (Brasil, {lo} anos ou mais, BRL × USD) calculado em cada edição "
                "avaliada. Responde 'o número da edição de referência ainda vale?' com dado de "
                "outra amostra, em vez de trocar a referência por uma edição que não sustenta "
                "os recortes finos.",
            "por_edicao": [
                {"edicao": r["edicao"], **r["moeda_agrupada"]}
                for r in avaliadas if r["moeda_agrupada"]
            ],
        },
        "candidatas_a_referencia": [
            {k: r[k] for k in ("edicao", "n_faixa_referencia", "paises_publicaveis",
                               "faixas_de_moeda_publicaveis", "global_usd_mes")}
            for r in avaliadas
        ],
        **LICENCA,
        "unidade": "US$/mês (mediana) — remuneração anual convertida ÷ 12, conversão do "
                   "próprio survey",
        "filtros": {"devtype_contem": SW, "salario_anual_usd": [3000, 500000],
                    "n_minimo_para_publicar": N_MIN},
        # Curto de propósito: vai direto no título da página. A explicação fica no campo
        # `faixa_referencia_derivada_de`, e a forma legível por máquina em `faixa_referencia` —
        # antes, quem precisava dos números fatiava esta string (`[:11]` em gen_reguas.py).
        "faixa_experiencia_referencia": f"{lo} a {hi} anos",
        "faixa_referencia": {"de": lo, "ate": hi},
        # O corte por moeda do MESMO piso da faixa de referência. É o que a página usa para o
        # cenário "brasileiro pago em dólar": mesma edição, mesmo piso de experiência, e amostra
        # de dólar bem maior que a de qualquer faixa fina (44 contra 15 na edição de referência).
        "moeda_referencia": escolhida["moeda_agrupada"],
        "notas": [
            "por_moeda_brasil usa o campo de moeda declarado pelo respondente: mesmo país e "
            "mesma experiência, separados por moeda do contracheque.",
            f"A série anual passou a cobrir {min(EDICOES)}–{ultima}: entraram as edições 2024 "
            "e 2025, que faltavam. Nenhum valor de edição anterior mudou — é acréscimo.",
            f"Os recortes por país e por moeda continuam saindo da edição "
            f"{EDICAO_REFERENCIA}, e por dois motivos diferentes. A edição {ultima} não pode "
            "ser referência porque deixou de publicar experiência PROFISSIONAL, e as colunas "
            "que ela traz no lugar medem outra população (trabalho de qualquer natureza, ou "
            "programação incluindo os anos de estudo). A edição 2024 poderia, mas tem menos "
            "da metade da amostra utilizável: usá-la derrubaria um país da lista e esvaziaria "
            "a comparação BRL×USD por faixa. Ver candidatas_a_referencia.",
            f"A amostra do survey encolheu depois de 2023: {ultima} tem cerca de 40% do total "
            "filtrado de 2023. A queda aparece na série como n_total, e é por isso que a "
            "variação ano a ano das edições recentes não deve ser lida como movimento de "
            "mercado.",
            f"A faixa de referência passou de '9 a 13 anos' para '{lo} a {hi}': ela agora é o "
            "intervalo interquartil medido do coorte, não um ±2 em volta da mediana escolhido à "
            "mão. Os valores por país e a mediana global mudaram por isso — mesma edição, mesma "
            "conta, faixa derivada do dado. O recorte por moeda não muda: ele usa as faixas "
            "finas, que são outras.",
        ],
        "global_usd_mes": escolhida["global_usd_mes"],
        "global_n": escolhida["n_faixa_referencia"],
        "por_pais": por_pais, "por_moeda_brasil": por_moeda, "serie_anual": serie,
    }
    (DATA / "so_benchmarks.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("OK — data/so_benchmarks.json")
    print(f"  edição de referência: {EDICAO_REFERENCIA} · série até {ultima}")
    print(f"  global {lo}-{hi} anos: US$ {out['global_usd_mes']:,}/mês (n={out['global_n']})")
    print(f"  {len(por_pais)} países · {len(por_moeda)} faixas de moeda · {len(serie)} edições")
    for m in por_moeda:
        print(f"    {m['faixa']:18s} BRL US$ {m['brl_usd_mes']:6,} (n={m['n_brl']:4d})  "
              f"USD US$ {m['usd_usd_mes']:6,} (n={m['n_usd']:3d})  {m['razao']}x")


if __name__ == "__main__":
    main()

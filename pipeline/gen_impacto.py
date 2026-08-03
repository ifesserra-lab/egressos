#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Produz o dataset da página de impacto (a entrada do site).

    consolidado.json + analise.json  ->  este script  ->  data/impacto.json
                                                                |
                                                    index.astro <+

O que ele substitui: `old/pipeline/gen_executivo.py`, que fazia **substituição de constante
JS dentro de um HTML autoral de 93 KB** — dez `re.subn` com `assert n == 1`, mais uma dúzia
de regex que trocavam números soltos dentro de células de tabela. A fonte da verdade ficava
partida entre o script e o HTML, e nenhum dos dois contava a história inteira.

Aqui há pouca conta nova: quase tudo é PROJEÇÃO e ROTULAGEM do que `compute_all.py` e
`analise.py` já calcularam. O que muda é que a projeção passa a ser dado — inspecionável,
versionado e testável — em vez de f-string.

Uso:  python pipeline/gen_impacto.py
"""
from __future__ import annotations

import sys

from egressos_core import dados

#: Rótulo curto para porte de empresa, no eixo do mapa de calor. Nome inteiro não cabe numa
#: coluna de matriz, e abreviar dentro do componente esconderia a decisão.
PORTE_CURTO = {
    "Multinacional / BigTech": "Multi/BigTech",
    "Grande nacional": "Grande nac.",
    "Média nacional": "Média nac.",
    "Startup / scale-up": "Startup/SU",
    "Setor público": "Público",
    "Não classificada": "N/C",
}

#: A base de extensão do SRC grava função em caixa alta. A tradução é de apresentação, e fica
#: aqui em vez de no componente para o mesmo motivo: é decisão, não formatação.
FUNCAO_LEGIVEL = {
    "ALUNO(A) VOLUNTARIO": "Voluntário(a)", "ALUNO(A) BOLSISTA": "Bolsista",
    "PALESTRANTE": "Palestrante", "INSTRUTOR(A)": "Instrutor(a)",
    "EXPOSITOR(A)": "Expositor(a)", "ORGANIZADOR(A)": "Organizador(a)",
    "MONITOR(A)": "Monitor(a)", "COLABORADOR(A)": "Colaborador(a)",
    "AUXILIAR TÉCNICO": "Auxiliar técnico",
}

#: Bolsa de projeto FAPES, valor documentado. Ordem das vias é decisão editorial: extensão
#: vem primeiro porque é a maior.
BOLSA_FAPES, BOLSA_ANO = 800, 2018

#: REFERÊNCIAS EXTERNAS documentadas. Ficam aqui, com a fonte ao lado, e não dentro do
#: componente: número escrito em página é número que ninguém sabe de onde veio, e o FR-002
#: proíbe. Constante nomeada com fonte citada é o padrão da casa para valor documentado que
#: nenhum dataset traz.
BOLSA_EXTENSAO = {
    "valor": 400, "de": 2013, "ate": 2014,
    "fonte": "bolsa de extensão/IC do LEDS/IFES, valor documentado, cruzado com registros",
}
ICT_HOJE = {
    "valor": 900,
    "fonte": "tabela FAPES vigente (Res. 361/2026), Iniciação Científica e Tecnológica",
    "obs": "Os egressos não estavam nesta modalidade: estavam em bolsa de PROJETO de governo, "
           "de valor mais alto. A comparação serve para dimensionar a ordem de grandeza.",
}
GAP_GENERO_MERCADO = {
    "fonte": "Stack Overflow Developer Survey",
    "edicoes": [
        {"edicao": 2022, "homens": 28044, "mulheres": 24300, "gap_pct": -13},
        {"edicao": 2021, "homens": 23226, "mulheres": 19584, "gap_pct": -16},
    ],
    "medida": "mediana anual convertida para R$",
    "por_que_externo": "O coorte tem sete mulheres e não sustentaria uma medida dessas. A "
                       "referência grande diz que a diferença observada aqui não é "
                       "peculiaridade local.",
}

#: As quatro vias de formação, na ordem em que a página as apresenta.
VIAS = [
    ("Extensão — IFES (labs)", "extensao_leds"),
    ("Pesquisa — IC/FAPES/CAPES", "pesquisa_ic_fapes"),
    ("Ensino — monitoria", "monitoria_ensino"),
    ("Empresa júnior — Morpheus", "empresa_junior_morpheus"),
]


def _br(v: float, casas: int = 1) -> str:
    """Número no padrão brasileiro. O artefato circula sozinho — quem o baixa lê `8,0`, não
    `8.0`, e formatar no componente espalharia a decisão por cada página que consumir."""
    return f"{v:.{casas}f}".replace(".", ",")


def executar() -> dict:
    cons = dados.ler("consolidado")
    an = dados.ler("analise")
    cf = dados.ler("codigofonte_2026")
    cfh = dados.ler("codigofonte_historico")
    ipca = dados.ler("ibge_series")["series"]["ipca"]["deflator_para_base"]

    kpi, imp = cons["kpi"], an["impacto"]
    n_coorte = an["genero"]["n_total"]
    n_modelo = kpi["n"]

    dt, do = imp["dispersao_por_trilha"], imp["dispersao_por_origem"]
    emp = an["empresas"]
    rxp = emp["regiao_x_porte"]
    gen = an["genero"]
    det = gen["detalhe"]
    ext = an["extensao"]
    sen = {r["senioridade"]: r for r in an["cruzamento"]["por_senioridade"]}

    artefato = {
        "e_estimativa": True,
        "aviso": "ESTIMATIVA de mercado. Cada egresso é precificado pela mediana da faixa de "
                 "experiência dele — dois com os mesmos anos recebem o mesmo valor estimado. "
                 "Nenhum salário foi coletado de ninguém.",
        "coorte": {
            "n": n_coorte,
            "n_no_modelo_salarial": n_modelo,
            "por_que_dois_numeros":
                "O coorte tem os egressos localizados; o modelo salarial cobre os que têm "
                "trajetória suficiente para estimar renda. A diferença é declarada em vez de "
                "escondida atrás de um número só.",
        },

        # ---- os indicadores de topo. O texto de cada um é parte do dado: sem ele o número
        #      fica sem unidade e sem ressalva.
        "indicadores": [
            {"valor": f'{_br(imp["multiplicador_medio"])}×',
             "rotulo": f'crescimento real médio da renda (até {_br(kpi["cresc_max"])}×) — '
                       'da bolsa à posição atual'},
            {"valor": f'~{imp["tempo_ate_senior_mediana_anos"]} anos',
             "rotulo": "experiência mediana até nível Sênior ou superior"},
            {"valor": f'{imp["lideram_hoje"]}/{n_coorte}',
             "rotulo": f'lideram ou gerenciam hoje ({imp["passaram_lideranca"]} já passaram '
                       'por liderança)'},
            {"valor": f'{imp["intl_hoje"]}/{n_coorte}',
             "rotulo": 'em empregador internacional — 1º emprego internacional com '
                       f'~{int(imp["exp_medio_1o_emprego_intl"])} anos de carreira'},
            {"valor": f'+{imp["premio_intl_pct"]}%',
             "rotulo": "prêmio internacional vs. nacional (mediana estimada) — ver ressalva"},
            {"valor": f'{n_coorte}/{n_coorte}', "rotulo": "seguem em tecnologia"},
            {"valor": f'~{round(kpi["med_atual"] / (BOLSA_FAPES * ipca[str(BOLSA_ANO)]))}×',
             "rotulo": f'a renda de hoje sobre a bolsa da época — {gen["fapes"]["total"]} '
                       'egressos vieram de bolsa FAPES, e todos seguem em tecnologia'},
        ],
        # A bolsa em poder de compra de HOJE. Sem isso, comparar R$ 800 de 2018 com a renda
        # de agora embute a inflação do período na conclusão.
        "bolsa": {
            "valor_da_epoca": BOLSA_FAPES,
            "ano": BOLSA_ANO,
            "em_poder_de_compra_de_hoje": round(BOLSA_FAPES * ipca[str(BOLSA_ANO)]),
            "fonte": "Bolsa FAPES de projeto de governo (nível VI)",
            "extensao": {
                **BOLSA_EXTENSAO,
                "em_poder_de_compra_de_hoje": round(
                    BOLSA_EXTENSAO["valor"] * ipca[str(BOLSA_EXTENSAO["de"])]),
            },
            "ict_hoje": ICT_HOJE,
        },
        "premio_e_artefato":
            "O prêmio internacional é ARTEFATO do método: os dois grupos são precificados na "
            "mesma tabela brasileira, e o modelo não sabe em que moeda cada um recebe. Ver a "
            "trajetória salarial para o cenário com o padrão observado de pagamento em dólar.",

        # ---- a faixa por experiência: o gráfico principal da página
        "por_experiencia": cons["agregado"],
        "por_experiencia_hoje": cons["pv"],
        "o_que_sao_as_duas_linhas":
            "A trajetória REAL é o que o coorte ganhou em cada época, corrigido para hoje. A "
            "linha `a valores de hoje` é o que o mercado de agora paga por aquela experiência. "
            "No início elas se afastam — bolsa contra salário de iniciante — e convergem "
            "conforme o grupo entra no mercado.",

        # ---- A REFERÊNCIA NACIONAL. Três seções da página vivem disto, e a primeira
        #      migração as perdeu inteiras: sem elas o leitor vê a renda do coorte sem nada
        #      com que compará-la no próprio país.
        "mercado_br": {
            "fonte": cf["fonte"],
            "url": cf["url"],
            "amostra": cf["metodologia"]["amostra"],
            "coleta": cf["metodologia"]["periodo_coleta"],
            "metodo": cf["metodologia"]["metodo"],
            "medida": "média mensal em R$, auto-reportada",
            "por_senioridade": cf["por_senioridade"],
            "por_contrato": cf["por_contrato"],
            "por_regiao": cf["por_regiao_top10"],
            "por_linguagem": cf["por_linguagem"],
            "recortes_que_a_fonte_nao_publica": cf["recortes_indisponiveis_na_pagina"],
            "historico_por_senioridade": cfh["media_por_senioridade"],
            "historico_medida": cfh["medida"],
            "por_que_duas_leituras":
                "`a valores de hoje` usa a edição 2026 para todos os níveis; `valor da época` "
                "usa a edição do ano em que cada senioridade foi atingida, corrigida por "
                "IPCA. A primeira responde 'quanto vale hoje'; a segunda, 'quanto valia "
                "quando aconteceu' — e a distância entre elas é a inflação do período.",
            # Onde cada nível cai no eixo de EXPERIÊNCIA. Vem medido do coorte
            # (`exp_medio_*`), não de uma tabela de equivalência inventada. Só os dois níveis
            # que o coorte ocupa têm âncora — os outros não entram, em vez de serem chutados.
            "ancoras_de_experiencia": [
                {"nivel": "Sênior", "anos": imp["exp_medio_senior"]},
                {"nivel": "Espec./Tech Lead", "anos": imp["exp_medio_espec"]},
            ],
            "o_que_nao_veio":
                "A versão anterior desenhava uma sombra em volta da escada, com piso e teto "
                "ilustrativos (CLT no estado de menor média, PJ no de maior). O próprio "
                "rótulo dizia que não era intervalo de confiança. Ficou de fora: faixa "
                "desenhada em volta de um número convida a lê-la como incerteza medida.",
            "licenca": cf["licenca"],
            "licenca_obs": cf["licenca_obs"],
        },

        # ---- OS ACHADOS. Prosa, mas com número dentro — e o número sai do dado, senão
        #      envelhece em silêncio. Foi o que aconteceu na trajetória com a oscilação
        #      "de cerca de 10%", escrita quando a série ia até 2023.
        "achados": [
            {"titulo": f'Salto de {_br(imp["multiplicador_medio"])}× '
                       f'(até {_br(kpi["cresc_max"])}×) na renda real',
             "texto": "Da bolsa de pesquisa/extensão ao mercado sênior, já descontada a "
                      "inflação (poder de compra do ano-base)."},
            {"titulo": "A bolsa foi trampolim, não teto",
             "texto": "A trajetória real alcança o valor de mercado por volta de 3 anos de "
                      "experiência e cresce junto a partir daí — é o ponto em que as duas "
                      "linhas do primeiro gráfico se encontram."},
            {"titulo": f'{imp["tempo_ate_senior_mediana_anos"]} anos até sênior, na mediana',
             "texto": f'E {imp["lideram_hoje"]} dos {n_coorte} lideram ou gerenciam hoje; '
                      f'{imp["passaram_lideranca"]} já passaram por liderança.'},
            {"titulo": f'{imp["intl_hoje"]} em empregador internacional',
             "texto": "O primeiro emprego internacional aparece com cerca de "
                      f'{int(imp["exp_medio_1o_emprego_intl"])} anos de carreira — não na '
                      "entrada."},
        ],

        # ---- MÉTODO E RESSALVAS. Cada item é uma limitação declarada. A lista existe como
        #      dado para que uma ressalva não se perca numa remarcação de página, que é
        #      exatamente o que aconteceu na primeira migração desta página.
        "ressalvas": [
            {"titulo": "Estimativa, não salário real",
             "texto": "Cruza os anos de experiência de cada egresso com a mediana de "
                      "desenvolvedores e analistas de dados no Brasil (Stack Overflow "
                      "Developer Survey), por câmbio e IPCA da época, trazidos ao ano-base."},
            {"titulo": "Início com valor real de bolsa",
             "texto": "Os anos de bolsa e estágio usam o valor documentado, cruzado com os "
                      "registros da FAPES. É por isso que o ponto de partida é tão baixo — "
                      f'{imp["origem"]["pesquisa_ic_fapes"] + imp["origem"]["extensao_leds"]} '
                      "passaram por bolsa de pesquisa ou extensão."},
            {"titulo": "Bolsa de projeto, não iniciação científica comum",
             "texto": "Os egressos estavam em bolsas FAPES de PROJETO de governo "
                      f'(R$ {_br(BOLSA_FAPES, 0)}/mês) e de extensão '
                      f'(R$ {_br(BOLSA_EXTENSAO["valor"], 0)}/mês), não na IC padrão — que '
                      f'pela tabela vigente paga R$ {_br(ICT_HOJE["valor"], 0)}/mês. '
                      f'{ICT_HOJE["obs"]} De todo modo, o mercado paga a um iniciante bem '
                      "mais que qualquer uma delas: o ganho veio da QUALIFICAÇÃO, não do "
                      "valor da bolsa."},
            {"titulo": "Anonimizado",
             "texto": "Sem nomes, empresas ou localidades neste painel. Apenas trilha e anos "
                      "de experiência. Os perfis aparecem como rótulos A–AX."},
            {"titulo": "Amostra pequena na cauda",
             "texto": "Nas faixas de mais experiência há poucos egressos de carreira longa; a "
                      "curva ali é indicativa, e a faixa aparece tracejada por isso."},
        ],

        # ---- dispersão: onde a mediana esconde a variação
        "dispersao": [
            {"grupo": "Software", "eixo": "trilha", **dt["Software"]},
            {"grupo": "Dados", "eixo": "trilha", **dt["Dados"]},
            {"grupo": "Nacional", "eixo": "origem", **do["nacional"]},
            {"grupo": "Internacional", "eixo": "origem", **do["intl"]},
        ],

        # ---- de onde eles vieram
        "vias_de_formacao": [{"via": rot, "n": imp["origem"][chave]} for rot, chave in VIAS],
        "fluxo": {
            "colunas": [
                [{"nome": v["nome"], "n": v["n"]} for v in an["sankey"]["vias"]],
                [{"nome": t["nome"], "n": t["n"]} for t in an["sankey"]["trilhas"]],
                [{"nome": d["nome"], "n": d["n"]} for d in an["sankey"]["destinos"]],
            ],
            "ligacoes": [
                [{"de": x["de"], "para": x["para"], "n": x["n"]}
                 for x in an["sankey"]["via_trilha"]],
                [{"de": x["de"], "para": x["para"], "n": x["n"]}
                 for x in an["sankey"]["trilha_destino"]],
            ],
            "total": n_coorte,
        },

        # ---- internacionalização no tempo
        "internacional_no_tempo": an["intl_timeline"],

        # ---- onde estão hoje
        "empresas": {
            "regiao": emp["regiao"], "setor": emp["setor"], "porte": emp["porte"],
            "regiao_x_porte": {
                "regioes": rxp["regioes"],
                "portes": [PORTE_CURTO.get(p, p) for p in rxp["portes"]],
                "matriz": rxp["matriz"],
            },
        },

        # ---- gênero
        "genero": {
            "f": gen["F"], "m": gen["M"], "pct_f": gen["pct_f"],
            "mediana": {"f": det["F"]["med_atual"], "m": det["M"]["med_atual"]},
            "crescimento": {"f": det["F"]["cresc_mediano"], "m": det["M"]["cresc_mediano"]},
            "gestao": {"f": det["F"]["gestao_lideranca"], "m": det["M"]["gestao_lideranca"]},
            "exterior": {"f": det["F"]["exterior"], "m": det["M"]["exterior"]},
            "internacional": {"f": det["F"]["intl_empregador"], "m": det["M"]["intl_empregador"]},
            "inicial": {"f": det["F"]["med_ini"], "m": det["M"]["med_ini"]},
            "n_por_grupo": {"f": det["F"]["n"], "m": det["M"]["n"]},
            "fapes": gen["fapes"],
            "ressalva_da_fonte": gen["ressalva"],
            "leitura":
                "No coorte elas começaram ganhando menos e cresceram mais. Com "
                f'{det["F"]["n"]} mulheres em {n_coorte} pessoas, cada uma pesa muito na '
                "mediana — o recorte indica, não mede.",
            "como_foi_inferido":
                "Gênero inferido do primeiro nome, offline, por base pública de nomes. Não foi "
                "declarado por ninguém, e nome não determina identidade — o recorte serve a "
                "medir representação no agregado, nunca a classificar pessoa.",
        },

        # ---- extensão
        "extensao": {
            "na_base": ext["n_encontrados"],
            "bolsistas": ext["n_bolsistas_extensao"],
            "bolsa_documentada": ext["n_bolsa_documentada_oficial"],
            "de": n_coorte,
            "funcoes": [{"funcao": FUNCAO_LEGIVEL.get(f["funcao"], f["funcao"]), "n": f["n"]}
                        for f in ext["funcoes"]],
        },

        # ---- o que o grupo faz e com o que trabalha
        "funcoes": an["funcoes"],
        "metodos": an["metodos"],
        "tecnologias": an["top_tech"],
        "senioridade": [
            {"nivel": nome, "nacional": r["nac"], "internacional": r["intl"], "total": r["n"]}
            for nome, r in sen.items() if r["n"] > 0
        ],
        # Os perfis agrupados por comportamento de carreira, e a trilha início→meio→hoje.
        # Estavam no dataset e não eram mostrados — o que é a mesma coisa que não existirem.
        "perfis_agrupados": [
            {"n": c["n"], "trilha": c["trilha"], "anos_medio": c["anos_medio"],
             "em_tech": c["em_tech"], "exterior": c["exterior"], "lideranca": c["lideranca"],
             "cargos_distintos": sorted(set(c["cargos"]))}
            for c in an["clusters"].values()
        ],
        "trilha_no_tempo": an["trilha_carreira"],

        # ---- referência EXTERNA do gap de gênero. Não é do coorte: é o mercado, e serve para
        #      o leitor saber que a diferença observada aqui não é peculiaridade local.
        "gap_de_genero_no_mercado": {
            **GAP_GENERO_MERCADO,
            "faixa": "−13% a −16%",
        },
        # O que o mercado paga a um iniciante, contra a bolsa. É a comparação que separa
        # "a bolsa pagava bem" de "a bolsa abriu a porta".
        "iniciante_no_mercado": {
            "mercado": next(x["media"] for x in cf["por_senioridade"] if x["nivel"] == "Estágio"),
            "sobre_a_bolsa_de_hoje": round(
                next(x["media"] for x in cf["por_senioridade"] if x["nivel"] == "Estágio")
                / (BOLSA_FAPES * ipca[str(BOLSA_ANO)]), 1),
            "leitura": "O ganho dos egressos veio da QUALIFICAÇÃO, não do valor da bolsa.",
        },
        # Onde a mediana do coorte cai na escada nacional, em número e não em adjetivo.
        "coorte_na_escada": {
            "mediana_do_coorte": kpi["med_atual"],
            "senior_nacional": next(x["media"] for x in cf["por_senioridade"]
                                    if x["nivel"] == "Sênior"),
            "acima_do_senior_pct": round(
                (kpi["med_atual"] / next(x["media"] for x in cf["por_senioridade"]
                                         if x["nivel"] == "Sênior") - 1) * 100),
        },
    }
    dados.gravar("impacto", artefato)
    return artefato


def main() -> int:
    a = executar()
    print(f"OK — {dados.caminho('impacto')}")
    print(f"  coorte: {a['coorte']['n']} · modelo salarial: {a['coorte']['n_no_modelo_salarial']}")
    print(f"  indicadores: {len(a['indicadores'])} · dispersão: {len(a['dispersao'])} grupos")
    print(f"  faixa por experiência: {len(a['por_experiencia'])} pontos · "
          f"fluxo: {sum(len(c) for c in a['fluxo']['colunas'])} nós")
    print(f"  empresas: {len(a['empresas']['regiao'])} regiões, "
          f"{len(a['empresas']['setor'])} setores, {len(a['empresas']['porte'])} portes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

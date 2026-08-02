#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Produz o dataset da página de trajetória — tudo o que ela mostra, já calculado.

Por que existe: a página é Astro, e Astro não chama Python. O caminho do dado é

    data/*.json  ->  este script (usa egressos_core.trajetoria)  ->  data/trajetoria.json
                                                                          |
                                              trajetoria_salarial.astro  <+

Mesmo padrão de `gen_cargos.py`. O que muda em relação ao `old/pipeline/gen_reguas.py`, que
ele substitui: aquele CALCULAVA e RENDERIZAVA no mesmo arquivo, numa f-string de 757 linhas.
A conta foi para o núcleo, onde é testável; a marcação foi para o componente; e no meio
sobrou este script, que só junta os cinco datasets e grava um.

Uso:  python pipeline/gen_trajetoria.py
"""
from __future__ import annotations

import sys

from egressos_core import dados, deflator, trajetoria

#: Bolsa nível VI do projeto Prodest/FAPES, valor documentado de 2018. É o piso de onde a
#: maior parte do coorte partiu, e o contraste dela com o salário mínimo do MESMO ano é o que
#: a primeira seção da página mostra.
BOLSA_FAPES, BOLSA_ANO = 800, 2018

#: Mínimo de pessoas para o ano entrar na série. 38 dos 50 começaram a carreira antes de 2018;
#: com o corte em 20 o gráfico escondia 2012–2014, quando já havia de 12 a 16 no mercado.
N_MIN_ANO = 10


def executar() -> dict:
    cons = dados.ler("consolidado")
    smj = dados.ler("salario_minimo")
    so = dados.ler("so_benchmarks")
    cf = dados.ler("codigofonte_2026")
    an = dados.ler("analise")

    ano_base = smj["ano_base_deflator"]
    sm = {int(k): v for k, v in smj["sm_por_ano"].items()}
    fx = {int(k): v for k, v in cons["fx_por_ano"].items()}

    serie = trajetoria.serie_anual(cons["por_ano_sm"], cambio=fx, minimo=N_MIN_ANO)
    ultimo = serie[-1]

    traj = an["trajetoria_destaque"]
    if not traj:
        raise SystemExit("ABORT: analise.json sem `trajetoria_destaque`. Rode pipeline/analise.py.")
    for d in traj:
        d["sm"] = round(d["med"] / sm[d["ano"]], 2)

    global_usd = so["global_usd_mes"]
    eua = next(p["usd_mes"] for p in so["por_pais"] if p["pais"] == "Estados Unidos")
    moeda = so["moeda_referencia"]
    senior_cf = next(x["media"] for x in cf["por_senioridade"] if x["nivel"] == "Sênior")

    regua = trajetoria.regua_de_paises(
        paises=so["por_pais"], global_usd=global_usd, egressos_usd=ultimo["usd"],
        pago_em_dolar_usd=moeda["usd_usd_mes"], senior_br_brl=senior_cf,
        cambio_base=fx[ano_base])

    # A tabela em R$: as mesmas referências, na moeda de quem lê.
    tabela = sorted(
        [{"rotulo": f"Salário mínimo {ano_base}", "brl": sm[ano_base], "papel": "referencia"},
         *({"rotulo": f'{x["nivel"]} — Código Fonte {ano_base}', "brl": x["media"],
            "papel": "referencia"} for x in cf["por_senioridade"]),
         {"rotulo": f'Brasil — Stack Overflow ({trajetoria.rotulo_da_faixa(so["faixa_referencia"])})',
          "brl": next(p["usd_mes"] for p in so["por_pais"] if p["pais"] == "Brasil") * fx[ano_base],
          "papel": "referencia"},
         {"rotulo": "Egressos IFES (mediana do coorte)", "brl": ultimo["med_nominal"],
          "papel": "coorte"},
         {"rotulo": "Mediana global — Stack Overflow", "brl": global_usd * fx[ano_base],
          "papel": "referencia"},
         {"rotulo": "Brasileiro pago em US$ — Stack Overflow *",
          "brl": moeda["usd_usd_mes"] * fx[ano_base], "papel": "cenario"},
         {"rotulo": "Estados Unidos — Stack Overflow", "brl": eua * fx[ano_base],
          "papel": "referencia"}],
        key=lambda r: r["brl"])

    cruzamento = an["cruzamento"]["por_senioridade"]
    artefato = {
        "e_estimativa": True,
        "aviso": "ESTIMATIVA. A renda de cada ano é a mediana do coorte naquele ano, "
                 "convertida pelo câmbio do próprio ano e deflacionada. Para uma pessoa "
                 "concreta pode ser MAIOR ou MENOR.",
        "ano_base": ano_base,
        "referencia": deflator.data_referencia(dados.ler("ibge_series")).rotulo_pt(),
        "minimo_de_pessoas_por_ano": N_MIN_ANO,
        "por_que_o_minimo":
            "Ano com menos pessoas que isso não vira ponto: a mediana seria de um punhado de "
            "gente, com o rótulo do coorte inteiro.",
        "cambio_por_ano":
            "Cada ano converte pela taxa média DELE. Taxa única faria a série mostrar "
            "variação cambial como se fosse variação de salário.",

        "serie": serie,
        "bolsa": {
            "valor": BOLSA_FAPES, "ano": BOLSA_ANO,
            "em_sm": trajetoria.bolsa_em_salarios_minimos(BOLSA_FAPES, ano=BOLSA_ANO,
                                                          sm_por_ano=sm),
            "sm_do_ano": sm[BOLSA_ANO],
            # A distância para o piso legal, nos dois sentidos. É o contraste que abre a
            # página: a bolsa não pagava um mínimo; a renda de hoje paga dez.
            "abaixo_do_piso": round(sm[BOLSA_ANO] - BOLSA_FAPES),
            "acima_do_piso_hoje": ultimo["acima_sm_nominal"],
            "fonte": "Bolsa nível VI, projeto Prodest/FAPES (valor documentado)",
        },
        "trajetoria": traj,
        "trajetoria_indicadores": trajetoria.indicadores(traj),
        # Os dois extremos em valor NOMINAL — é o que o título da seção afirma, e é a leitura
        # de contracheque: o que a pessoa via na conta em cada época.
        "trajetoria_extremos": {"inicio_brl": traj[0]["med"], "fim_brl": traj[-1]["med"],
                                "de": traj[0]["ano"], "ate": traj[-1]["ano"]},
        "trajetoria_coorte": trajetoria.coorte_no_eixo(traj, cons["agregado"]),
        "salario_minimo": trajetoria.variacao_do_minimo(
            smj["por_ano"], ano_base=ano_base, desde=serie[0]["ano"]),
        "sm_por_ano": [a for a in smj["por_ano"] if a["ano"] >= serie[0]["ano"]],
        "regua": regua,
        "tabela_em_reais": tabela,
        "mundo": {
            "global_usd": global_usd, "eua_usd": eua,
            "egressos_usd": ultimo["usd"], "egressos_brl": ultimo["med_nominal"],
            "egressos_em_sm": ultimo["em_sm"],
            "pct_do_global": round(100 * ultimo["usd"] / global_usd),
            "pct_dos_eua": round(100 * ultimo["usd"] / eua),
            "faixa_de_experiencia": trajetoria.rotulo_da_faixa(so["faixa_referencia"]),
        },
        "moeda_do_contracheque": {
            "usd_pago_em_dolar": moeda["usd_usd_mes"],
            "usd_pago_em_real": moeda["brl_usd_mes"],
            "razao": moeda["razao"],
            "n_dolar": moeda.get("n_usd"), "n_real": moeda.get("n_brl"),
            "o_que_e": "Mesmo país, mesma faixa de experiência — o que muda é a moeda em que "
                       "o salário é pago.",
        },
        "por_origem_do_empregador": [
            {"senioridade": r["senioridade"], "nacional": r["nac"], "internacional": r["intl"]}
            for r in cruzamento if r["n"] > 0],
        "internacional": {
            "hoje": an["impacto"]["intl_hoje"], "total": an["impacto"]["n"],
            "senior_ou_acima": sum(r["intl"] for r in cruzamento
                                   if r["senioridade"] in ("Sênior", "Espec./Tech Lead")),
        },
        # Procedência, montada a partir do próprio dado. A página antiga trazia estes números
        # no texto; escrevê-los à mão aqui seria o defeito que o FR-002 proíbe.
        "fontes": {
            "salario_minimo": smj["fonte_salario_minimo"],
            "inflacao": smj["fonte_inflacao"],
            "ultimo_reajuste": {
                "ano": ano_base,
                "valor": next(x["jan"] for x in smj["por_ano"] if x["ano"] == ano_base),
                "reajuste_pct": next(x["reajuste_pct"] for x in smj["por_ano"]
                                     if x["ano"] == ano_base),
                "ganho_real_pct": next(x["ganho_real_pct"] for x in smj["por_ano"]
                                       if x["ano"] == ano_base),
            },
        },
        "multiplicadores": an["hist_multiplicadores"],
        "crescimento": {
            "minimo": min(p["cresc"] for p in cons["perfis"]),
            # O campo do KPI se chama `cresc_medio` e a página sempre o exibiu como
            # "mediana". A mediana real dos 49 valores é 7,0; este é 8,0. A divergência é de
            # NOME na origem, e trocar o número aqui mudaria valor publicado numa migração —
            # que é o que a caracterização existe para impedir. Fica registrado para virar
            # uma decisão própria, no lugar certo (compute_all.py).
            "central": cons["kpi"]["cresc_medio"],
            "rotulo_central": "mediana",
            "ressalva_do_rotulo":
                "O KPI de origem chama este valor de `cresc_medio`; a página o rotula como "
                "mediana desde a primeira versão. A mediana aritmética dos 49 perfis é 7,0. "
                "Reconciliar os dois é decisão de método, não de layout.",
            "maximo": cons["kpi"]["cresc_max"],
        },
        # A corroboração entre edições: o mesmo corte medido em amostras independentes. Foi
        # uma decisão de método (specs/004, D13) e a primeira reescrita a perdeu.
        "corroboracao_por_edicao": so["corroboracao"]["por_edicao"],
        "corroboracao_o_que_e": so["corroboracao"]["o_que_e"],
        # Por que NÃO projetar o número da edição de referência para hoje. A oscilação é
        # derivada da série — a versão anterior trazia "cerca de 10%" escrito no texto, e o
        # valor envelheceu quando entraram as edições de 2024 e 2025.
        "corroboracao_oscilacao_pct": trajetoria.oscilacao_media(
            so["serie_anual"], "brasil_usd_mes"),
        "edicao_de_referencia": so["edicao_referencia"],
        # Por que a referência não é a edição mais recente. Vem das notas do próprio artefato,
        # não escrito aqui: a razão mudou uma vez (2024 tinha amostra pequena; 2025 deixou de
        # publicar experiência profissional) e escrevê-la na página a congelaria.
        "por_que_esta_edicao": next(
            (n for n in so.get("notas", []) if "continuam saindo da edição" in n),
            "A edição de referência é a que sustenta todos os recortes finos."),

        # O prêmio internacional que o modelo calcula, e por que ele é artefato. Bloco
        # analítico da página antiga: sem ele, o leitor toma +6% como achado.
        "premio_internacional": {
            "pct": an["impacto"]["premio_intl_pct"],
            "por_que_e_artefato":
                "Os dois grupos são precificados na MESMA tabela brasileira: o modelo estima "
                "cada egresso pela mediana de mercado da faixa de experiência dele, e não "
                "sabe em que moeda ele recebe. O prêmio que sobra é resíduo de composição, "
                "não diferença de remuneração.",
            "cenario": {
                "usd_mes": moeda["usd_usd_mes"],
                "brl_mes": round(moeda["usd_usd_mes"] * fx[ano_base]),
                "em_sm": round(moeda["usd_usd_mes"] * fx[ano_base] / sm[ano_base], 1),
                "n_egressos": an["impacto"]["intl_hoje"],
                "o_que_e": "Se os egressos com empregador internacional fossem pagos no "
                           "padrão OBSERVADO de brasileiros que recebem em dólar.",
            },
        },
        # As faixas finas de experiência, dentro do Brasil, separadas pela moeda do
        # contracheque. É onde se vê que a razão não é uma só: vai de 2,5x a 3,5x.
        "moeda_por_faixa": so["por_moeda_brasil"],
    }
    dados.gravar("trajetoria", artefato)
    return artefato


def main() -> int:
    a = executar()
    ind = a["trajetoria_indicadores"]
    print(f"OK — {dados.caminho('trajetoria')}")
    print(f"  série: {len(a['serie'])} anos ({a['serie'][0]['ano']}–{a['serie'][-1]['ano']}), "
          f"mín. {a['minimo_de_pessoas_por_ano']} pessoas/ano")
    print(f"  trajetória: {ind['anos']} anos, {ind['mult_real']:.1f}× real, "
          f"{ind['cagr_pct']:.1f}% a.a.")
    print(f"  régua: {len(a['regua'])} barras · tabela: {len(a['tabela_em_reais'])} linhas")
    print(f"  coorte hoje: US$ {a['mundo']['egressos_usd']:,} = "
          f"{a['mundo']['pct_do_global']}% da mediana global")
    print(f"  corroboração: {len(a['corroboracao_por_edicao'])} edições · "
          f"moeda por faixa: {len(a['moeda_por_faixa'])} recortes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

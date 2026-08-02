#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a API estática do estudo de egressos em egressos/api/, servida pelo GitHub Pages
em https://ifesserra-lab.github.io/egressos/api/ — mesmo padrão do painel de Extensão
(ifesserra-lab/src, docs/api/).

Diferença entre api/ e dados/:
  dados/  são os JSON do pipeline como saem dele — bom para baixar e reprocessar.
  api/    é uma superfície estável e navegável: recortes pequenos, nomes de campo
          estáveis e um índice que lista todos os endpoints. É o que um site, um
          notebook ou um LLM consome sem precisar conhecer o pipeline.

Privacidade: a API é INTEIRAMENTE anonimizada. Nunca inclui nome, empresa ou local
por pessoa — só a coorte A–AX e dados públicos de empresa. A vitrine nomeada
(egressos-carreiras.html) não tem endpoint aqui, de propósito.

Uso:  python pipeline/gen_api.py
"""
import json
import shutil

from egressos_core.paths import PUB
from egressos_core.paths import ROOT as BASE
from egressos_core.text import slug, strip_accents

API = PUB / "api"
SITE = "https://ifesserra-lab.github.io/egressos"

L = lambda f: json.load(open(BASE / "data" / f, encoding="utf-8"))
cons, an, smj, so = L("consolidado.json"), L("analise.json"), L("salario_minimo.json"), L("so_benchmarks.json")
cf, cfh, emp, fap = L("codigofonte_2026.json"), L("codigofonte_historico.json"), L("empresas_porte.json"), L("fapes_fomento.json")
ibge, mapa = L("ibge_series.json"), L("mapa_mundi.json")
mapa_det = L("mapa_mundi_detalhe.json")
perfil, renda = L("egressos_perfil.json"), L("renda_por_senioridade.json")

ANO_BASE = smj["ano_base_deflator"]
endpoints = []


def escreve(rel, obj, descricao):
    """Grava um endpoint e registra no índice."""
    alvo = API / rel
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    endpoints.append({"endpoint": f"api/{rel}", "descricao": descricao,
                      "kb": round(alvo.stat().st_size / 1024, 1)})
    return alvo


META = {"fonte": "Estudo de egressos de TI — IFES Campus Serra",
        "licenca": "CC BY 4.0", "site": SITE, "ano_base": ANO_BASE}

if API.exists():
    shutil.rmtree(API)          # regenera do zero: endpoint removido do código some do ar

# ---------- coorte ----------
escreve("coorte.json", {**META,
    "descricao": "Coorte anonimizada. Cada item é um egresso identificado só por rótulo (A–AX).",
    "campos": {"perfil": "rótulo anônimo", "trilha": "Software/Dados/…", "anos": "anos de carreira",
               "bolsa": f"valor mensal da bolsa inicial em R$ de {ANO_BASE} (null se não teve)",
               "med_ini": "renda estimada inicial", "med_atual": "renda estimada atual",
               "cresc": "multiplicador de crescimento"},
    "unidade": f"R$/mês em reais de {ANO_BASE}",
    "n": len(cons["perfis"]), "kpi": cons["kpi"], "perfis": cons["perfis"]},
    "Coorte anonimizada A–AX: trilha, anos de carreira, bolsa inicial, renda estimada e crescimento.")

escreve("coorte/serie-por-experiencia.json", {**META,
    "descricao": "Renda estimada agregada por ANOS DE EXPERIÊNCIA — a curva de carreira.",
    "campos": {"exp": "anos de experiência", "lo": "menor p25 do grupo", "hi": "maior p75",
               "med": "mediana", "n": "quantos egressos no ponto"},
    "unidade": f"R$/mês em reais de {ANO_BASE}",
    "trajetoria_real": cons["agregado"],
    "mercado_hoje": cons["pv"]},
    "Curva de carreira por anos de experiência: trajetória real do coorte e o que o mercado paga hoje.")

escreve("coorte/serie-por-ano.json", {**META,
    "descricao": "Mediana do coorte em cada ANO CIVIL, em R$ e em salários mínimos da época.",
    "campos": {"ano": "ano civil", "n": "egressos com estimativa no ano",
               "med_nominal": "mediana em R$ da época", "med_real": f"mediana em R$ de {ANO_BASE}",
               "sm_ano": "salário mínimo médio do ano", "em_sm": "mediana ÷ salário mínimo",
               "acima_sm_nominal": "quanto a mediana está acima do piso, em R$ da época"},
    "serie": cons["por_ano_sm"]},
    "Mediana do coorte por ano civil, em R$ da época, em reais do ano-base e em salários mínimos.")

escreve("coorte/trajetoria-destaque.json", {**META,
    "descricao": "Uma trajetória individual anonimizada — a de maior multiplicador entre quem "
                 "começou com bolsa documentada. Escolhida deterministicamente pelo pipeline.",
    "campos": {"ano": "ano", "exp": "anos de experiência", "empresa": "tipo de empregador (anonimizado)",
               "p25": "p25 de mercado", "med": "renda estimada em R$ da época", "p75": "p75 de mercado",
               "real": f"renda em R$ de {ANO_BASE}", "usd": "renda em US$/mês pelo câmbio do ano",
               "fx": "câmbio médio do ano", "ex": "true = ano extrapolado", "bolsa": "true = ano de bolsa"},
    "serie": an["trajetoria_destaque"],
    "multiplicadores_do_coorte": an["hist_multiplicadores"]},
    "Trajetória individual anonimizada, ano a ano, mais a distribuição de multiplicadores do coorte.")

# ---------- réguas ----------
escreve("salario-minimo.json", {**META,
    "descricao": smj["titulo"], "fonte_primaria": smj["fonte_salario_minimo"],
    "notas": smj["notas"], "por_ano": smj["por_ano"],
    "sm_por_ano": smj["sm_por_ano"], "deflator_ipca_por_ano": smj["deflator_ipca_por_ano"],
    "cambio_por_ano": smj["cambio_por_ano"]},
    "Salário mínimo por ano: valor, reajuste do decreto, INPC, ganho real, deflator IPCA e câmbio.")

escreve("indices.json", {**META,
    "descricao": ibge["titulo"], "mes_base": ibge["mes_base"],
    "series": {k: {kk: vv for kk, vv in v.items() if kk != "mensal"}
               for k, v in ibge["series"].items()},
    "mensal": {k: v.get("mensal", {}) for k, v in ibge["series"].items()}},
    "IPCA, INPC e câmbio USD→BRL: número-índice mensal, médias anuais e deflatores (IBGE/IPEADATA).")

# ---------- mercado ----------
escreve("mercado/stackoverflow.json", {**META, **{k: v for k, v in so.items() if k != "titulo"},
    "descricao": so["titulo"]},
    "Benchmarks do Stack Overflow: mediana em US$ por país, global, e o corte por moeda do contracheque.")

escreve("mercado/codigofonte.json", {**META,
    "descricao": "Pesquisa Código Fonte — mercado brasileiro de tecnologia.",
    "edicao_2026": cf, "historico": cfh},
    "Pesquisa Código Fonte: escada de senioridade, contrato e região (2026 + série histórica).")

# ---------- empresas ----------
emp_itens = []
for nome, v in sorted(emp.items()):
    s = slug(nome)
    emp_itens.append({"empresa": nome, "slug": s, "endpoint": f"api/empresas/{s}.json",
                      "porte": v.get("porte_real") or v.get("porte"),
                      "origem": v.get("origem"), "setor": v.get("setor_real") or v.get("setor")})
    (API / "empresas").mkdir(parents=True, exist_ok=True)
    (API / "empresas" / f"{s}.json").write_text(
        json.dumps({**META, "empresa": nome, **v}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
escreve("empresas/index.json", {**META,
    "descricao": "Empresas onde os egressos passaram. Dado PÚBLICO de empresa, sem vínculo a pessoa.",
    "n": len(emp_itens), "detalhe_em": "api/empresas/<slug>.json", "empresas": emp_itens},
    "Índice das empresas: porte, origem e setor, com link para o detalhe de cada uma.")
endpoints.append({"endpoint": "api/empresas/<slug>.json",
                  "descricao": f"Detalhe de uma empresa ({len(emp_itens)} arquivos): headcount, sede, "
                               "setor, site, fundação, especialidades, vagas.", "kb": None})

# ---------- análises agregadas ----------
escreve("analise.json", {**META,
    "descricao": "Agregados do coorte: clusters, funções, senioridade × origem, gênero, "
                 "internacionalização, extensão e trilha de carreira. Tudo agregado.",
    **{k: v for k, v in an.items() if k not in ("rows", "trajetoria_destaque", "hist_multiplicadores")}},
    "Análises agregadas: clusters, sankey, funções, gênero, internacionalização, extensão.")

# A vitrine e a faixa por senioridade entram como DOIS endpoints, pelo mesmo motivo de serem dois
# arquivos: o perfil identifica e não tem renda; a faixa tem renda e não identifica. Juntá-los
# num endpoint só reconstruiria, na API, o vínculo que os dois arquivos existem para separar.
escreve("egressos/perfis.json", {**META, **perfil},
    "Perfil público de cada egresso: nome, curso, cargo, empresa, cidade e senioridade. "
    "Sem renda — a estimativa é por senioridade, no endpoint ao lado.")

escreve("egressos/renda-por-senioridade.json", {**META, **renda},
    "Faixa de renda ESTIMADA por senioridade, com as duas referências lado a lado: a Pesquisa "
    "Código Fonte (média, nativa em reais) e o modelo do estudo (mediana com p25–p75, nascida "
    "em dólar). Sem nenhuma chave de pessoa.")

escreve("fomento-fapes.json", {**META, **fap},
    "Fomento de bolsas FAPES recebido pela coorte (agregado por projeto).")

# ---------- mapa ----------
escreve("mapa/base.json", {**META, **{k: v for k, v in mapa.items() if k != "paths"},
    "descricao": mapa["titulo"], "paths": mapa["paths"]},
    "Contorno dos continentes projetado para SVG — resolução 110m, leve (domínio público).")
escreve("mapa/detalhe.json", {**META, **{k: v for k, v in mapa_det.items() if k != "paths"},
    "descricao": mapa_det["titulo"] + " — resolução fina, para zoom", "paths": mapa_det["paths"]},
    "Mesmo contorno em resolução 50m: o mapa da vitrine busca este arquivo ao aproximar.")

# ---------- índice ----------
n_intl = an["impacto"]["intl_hoje"]
indice = {
    "descricao": "API estática do estudo de egressos de TI — IFES Campus Serra",
    "privacidade": "Totalmente anonimizada: coorte identificada só por rótulo (A–AX) e dados "
                   "públicos de empresa. Nenhum nome, empresa ou local por pessoa.",
    "licenca": "Dados CC BY 4.0 · código MIT. Cite \"Egressos IFES — Campus Serra\".",
    "site": SITE, "dados_brutos": f"{SITE}/dados-abertos.html",
    "ano_base": ANO_BASE, "aviso": "Site experimental — dados preliminares, sujeitos a revisão.",
    "coorte": an["impacto"]["n"],
    "coorte_com_serie_salarial": cons["kpi"]["n"],
    "empresas": len(emp_itens),
    "em_empregador_internacional": n_intl,
    "mediana_atual_reais": cons["por_ano_sm"][-1]["med_nominal"],
    "mediana_atual_em_salarios_minimos": cons["por_ano_sm"][-1]["em_sm"],
    "endpoints": endpoints,
}
(API / "index.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------- porta de PII: nenhum nome de aluno pode ter vazado ----------
#
# UMA exceção, nomeada: o endpoint da vitrine. Publicar nome ali é a decisão da coordenação —
# cargo, empresa e cidade são o que a própria pessoa publica no LinkedIn. Se a varredura de
# nomes se aplicasse a ele, ele nunca sairia.
#
# Exceção sem portão é buraco, então ela vem com o seu: o endpoint da vitrine não pode ter
# NENHUM campo de dinheiro. O número de renda não é da pessoa — é a faixa de mercado da
# experiência dela —, e juntar identidade e dinheiro no mesmo registro foi exatamente como
# analise.json vazou. A faixa mora no endpoint ao lado, atrelada ao CARGO.
VITRINE_NOMEADA = {"egressos/perfis.json"}
CHEIRO_DE_RENDA = ("salario", "renda", "med_atual", "med_ini", "remunera", "p25", "p75",
                   "mediana", "cresc", "brl", "usd", "valor")


def _chaves_de_dinheiro(no):
    """Toda chave com cheiro de dinheiro, em QUALQUER profundidade.

    Recursivo porque a versão rasa deixava passar o caso real: `bolsa_valor_mensal` mora dentro
    de `experiencias[]`, não no topo do registro da pessoa. Portão que só olha o primeiro nível
    dá a impressão de proteger e não protege.
    """
    achadas = set()
    if isinstance(no, dict):
        for chave, valor in no.items():
            if any(t in chave.lower() for t in CHEIRO_DE_RENDA):
                achadas.add(chave)
            achadas |= _chaves_de_dinheiro(valor)
    elif isinstance(no, list):
        for item in no:
            achadas |= _chaves_de_dinheiro(item)
    return achadas


al = json.load(open(BASE / "alunos.json", encoding="utf-8"))
al = al if isinstance(al, list) else (al.get("alunos") or list(al.values())[0])
nomes = {strip_accents(a["nome"]).lower().strip() for a in al if a.get("nome")}
for arq in sorted(API.rglob("*.json")):
    rel = str(arq.relative_to(API))
    if rel in VITRINE_NOMEADA:
        com_renda = sorted(_chaves_de_dinheiro(
            json.loads(arq.read_text(encoding="utf-8")).get("egressos", [])))
        if com_renda:
            raise SystemExit(
                f"ABORT: {rel} é a vitrine NOMEADA e ganhou campo de renda: {com_renda}. "
                "Renda por pessoa é estimativa que a metodologia não mede no indivíduo — ela "
                "vai em egressos/renda-por-senioridade.json. API não publicada.")
        continue
    txt = strip_accents(arq.read_text(encoding="utf-8")).lower()
    achou = [n for n in nomes if n and n in txt]
    if achou:
        raise SystemExit(f"ABORT: PII em {arq.relative_to(PUB)}: {achou[:3]} — API não publicada")

n_arq = sum(1 for _ in API.rglob("*.json"))
kb = sum(f.stat().st_size for f in API.rglob("*.json")) / 1024
print(f"OK — api/ com {n_arq} arquivos ({kb:.0f} KB), {len(endpoints)} endpoints no índice")
print(f"     {SITE}/api/index.json")

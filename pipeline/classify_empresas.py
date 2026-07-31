#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classifica empresas por dados VERIFICADOS do LinkedIn (browser-use):
  - porte_real  <- headcount_linkedin  (bandas padrão do LinkedIn, determinístico)
  - setor_real  <- industry_linkedin + specialties  (regras por palavra-chave)

Aditivo em data/empresas_porte.json (não apaga a estimativa Mistral; marca fonte).
Imprime um resumo (contagem por porte_real e setor_real) p/ análise.

Só dados PÚBLICOS de empresa. Sem LLM (regras determinísticas). Sem rede.
Uso:  .venv/bin/python pipeline/classify_empresas.py
"""
import json
import os
import re
from collections import Counter

from egressos_core.paths import ROOT as _ROOT
from egressos_core.text import strip_accents

BASE = str(_ROOT)
PORTE = os.path.join(BASE, "data", "empresas_porte.json")

# Sem `.strip()` de propósito: NÃO é o `text.norm` do núcleo. Trocar mudaria a chave
# de agrupamento de todo valor com espaço nas pontas — e o dado do LinkedIn tem desses.
def norm(s):
    return strip_accents(s).lower()

# --- porte por headcount (bandas LinkedIn) ---
def porte_por_headcount(hc):
    if not hc:
        return None
    hc = re.sub(r"(\d)\s*[kK]\b", lambda m: m.group(1) + "000", hc)   # "1K"->"1000"
    dig = lambda s: int(re.sub(r"\D", "", s) or 0)
    # só a 1ª faixa X-Y (ignora "(12.000 especialistas)" e afins); senão X+ ; senão 1º número
    m = re.search(r"(\d[\d.,]*)\s*[-–]\s*(\d[\d.,]*)", hc)
    if m:
        top = dig(m.group(2))
    else:
        m = re.search(r"(\d[\d.,]*)\s*\+", hc) or re.search(r"\d[\d.,]*", hc)
        top = dig(m.group(m.lastindex or 0)) if m else 0
    if not top:
        return None
    if top <= 10:    return "Micro (1-10)"
    if top <= 50:    return "Pequena (11-50)"
    if top <= 200:   return "Pequena-Média (51-200)"
    if top <= 500:   return "Média (201-500)"
    if top <= 1000:  return "Média-Grande (501-1k)"
    if top <= 5000:  return "Grande (1k-5k)"
    if top <= 10000: return "Grande (5k-10k)"
    return "Enterprise (10k+)"

# --- setor por industry + specialties (regras; ordem específica -> genérica) ---
SETOR_RULES = [
    ("Fintech / Banco",        r"fintech|bank|banco|payment|pagament|credit|crédit|lending|empréstim|seguro|insurance|financ|wallet|carteira digital"),
    ("Games",                  r"\bgame|jogo|gaming|entertainment provider"),
    ("Saúde / Bio",            r"health|saúde|saude|medical|médic|hospital|pharma|farma|clinic|clínic|\bbio|life science|pet"),
    ("E-commerce / Varejo",    r"e-?commerce|retail|varejo|marketplace|\bloja|consumer goods|cosmétic|cosmetic|department store"),
    ("Consultoria / Serviços TI", r"consult|it services|outsourc|systems integrat|serviços de ti|integração de sistemas|professional services"),
    ("Dados / IA",             r"\bdata\b|dados|analytics|machine learning|artificial intelligence|inteligência artificial|\bai\b|\bia\b|big data"),
    ("Segurança / Cyber",      r"security|segurança|cyber|ciberseg|antifraud|antifraude"),
    ("Telecom / Redes",        r"telecom|telecommunicat|conectividade|network|redes|internet service"),
    ("Educação",               r"educat|educaç|edtech|ensino|e-learning|aprendizag"),
    ("Governo / Defesa",       r"government|govern|público|public administration|defense|defesa|marinha|tribunal|prefeitura|registro público"),
    ("Indústria / Energia / Logística", r"manufactur|indústr|industry|energy|energia|logístic|logistic|automotiv|petról|mineraç|construç"),
    ("Software / Produto",     r"software|technology|tecnologia|saas|\bapp\b|platform|plataforma|development|desenvolvimento de software|information technology"),
]
def setor_por_texto(industry, specialties):
    txt = norm(f"{industry or ''} ; {specialties or ''}")
    if not txt.strip(" ;"):
        return None
    for nome, pat in SETOR_RULES:
        if re.search(pat, txt):
            return nome
    return "Outros"

def main():
    porte = json.load(open(PORTE, encoding="utf-8"))
    n_hc = n_setor = 0
    for k, v in porte.items():
        hc = v.get("headcount_linkedin")
        pr = porte_por_headcount(hc)
        if pr:
            v["porte_real"] = pr; n_hc += 1
        sr = setor_por_texto(v.get("industry_linkedin"), v.get("specialties"))
        if sr:
            v["setor_real"] = sr; n_setor += 1
        if pr or sr:
            v["classificacao_fonte"] = "linkedin+regras"
    json.dump(porte, open(PORTE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"classificadas: {n_hc} por headcount (porte_real), {n_setor} por industry/specialties (setor_real)\n")
    pc = Counter(v["porte_real"] for v in porte.values() if v.get("porte_real"))
    sc = Counter(v["setor_real"] for v in porte.values() if v.get("setor_real"))
    order = ["Micro (1-10)","Pequena (11-50)","Pequena-Média (51-200)","Média (201-500)",
             "Média-Grande (501-1k)","Grande (1k-5k)","Grande (5k-10k)","Enterprise (10k+)"]
    print("== PORTE REAL (headcount LinkedIn) ==")
    for p in order:
        if pc.get(p): print(f"  {pc[p]:2}  {p}")
    print("\n== SETOR REAL (industry + specialties) ==")
    for s, n in sc.most_common():
        print(f"  {n:2}  {s}")

if __name__ == "__main__":
    main()

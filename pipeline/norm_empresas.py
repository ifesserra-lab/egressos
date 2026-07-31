#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Passo 0 — normaliza nomes de empresa e agrupa variantes/aliases.

Entrada: alunos.json (empresa_atual + experiencias[].empresa) e data/_empresas_lista.json
Saída:   data/empresas_aliases.json = { canonico: {"aliases":[...], "atual": bool, "n_egressos": int} }

Determín­istico, offline, sem rede. Base p/ resolve_company_urls.py não duplicar buscas
e p/ contagem correta de empresas distintas nas pesquisas.
"""
import json
import os
import re
from collections import defaultdict

from egressos_core.text import strip_accents

HERE = os.path.dirname(os.path.abspath(__file__))   # pipeline/
ROOT = os.path.dirname(HERE)                          # salario/
DATA = os.path.join(ROOT, "data")                     # salario/data/
OUT  = os.path.join(DATA, "empresas_aliases.json")

# nomes que NÃO são empregador (falsos positivos conhecidos — ver memória do projeto)
# NB: "MongoDB" é falso-positivo APENAS em listas de stack; aqui 2 egressos são
# empregados da MongoDB Inc (empresa real) -> mantido como empresa.
NAO_EMPRESA = {"alem", "autonomo", "freelance", "freelancer"}

# strip de sufixos corporativos e de localidade (tokens no fim do nome)
SUF_CORP = ["s/a", "s.a", "s a", "sa", "ltda", "ltda.", "me", "epp", "eireli",
            "inc", "inc.", "llc", "co", "co.", "corp", "corporation", "group",
            "consultoria & sistemas", "consultoria e sistemas"]
SUF_LOC  = ["chile", "brasil", "brazil", "do brasil", "of brazil", "us", "usa",
            "espirito santo"]
SUF_TAIL = [" ti"]  # "AEVO TI" -> "AEVO"

# fusões manuais (casos que a normalização automática não pega) -> chave canônica
MANUAL = {
    "banestes s/a – banco do estado do espírito santo": "Banestes",
    "banestes s/a - banco do estado do espírito santo": "Banestes",
    "getty/io chile": "Getty/IO",
    "will bank": "Will Bank",
    "conexos - consulting and systems": "CONEXOS",
    "vixteam consultoria & sistemas": "Vixteam",
    "facile soluções em sistemas": "Facile",
    "lifepet saúde": "Lifepet",
    "getty/io": "Getty/IO",
    "leds - ifes": "LEDS - IFES",
    "ifes - instituto federal do espírito santo": "Instituto Federal do Espírito Santo",
}


def key_of(nome):
    """chave de agrupamento: minúsculo, sem acento, sem pontuação, sem sufixo corp/loc/TI."""
    s = strip_accents(nome).lower().strip()
    s = re.sub(r"[–—\-]", " ", s)          # travessões -> espaço
    for suf in SUF_TAIL:
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
    # remove pontuação exceto / (usado em Getty/IO) — depois tira / p/ casar
    s = re.sub(r"[.,()]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # remove sufixo corporativo/localidade no fim (itera até estabilizar)
    changed = True
    while changed:
        changed = False
        for suf in SUF_CORP + SUF_LOC:
            if s.endswith(" " + suf) or s == suf:
                s = s[: len(s) - len(suf)].strip()
                changed = True
    s = s.replace("/", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ---- coleta nomes (atuais + histórico) ----
alunos = json.load(open(os.path.join(ROOT, "alunos.json"), encoding="utf-8"))
if isinstance(alunos, dict):
    alunos = alunos.get("alunos") or list(alunos.values())[0]

atuais = set()
counts_atual = defaultdict(int)          # canonico -> nº egressos com empresa atual
raw_names = set()
for a in alunos:
    ea = (a.get("empresa_atual") or "").strip()
    if ea:
        atuais.add(ea); raw_names.add(ea)
    for e in a.get("experiencias", []):
        emp = (e.get("empresa") or "").strip()
        if emp:
            raw_names.add(emp)

try:
    lista = json.load(open(os.path.join(DATA, "_empresas_lista.json"), encoding="utf-8"))
    raw_names.update(x.strip() for x in lista if x and x.strip())
except FileNotFoundError:
    pass

# ---- agrupa ----
groups = defaultdict(set)   # key -> {nomes crus}
for nome in raw_names:
    if key_of(nome) in NAO_EMPRESA or strip_accents(nome).lower().strip() in NAO_EMPRESA:
        continue
    low = strip_accents(nome).lower().strip()
    low2 = re.sub(r"[–—\-]", "-", nome).lower().strip()
    if low in MANUAL:
        k = key_of(MANUAL[low]); groups[k].add(nome); groups[k].add(MANUAL[low]); continue
    if low2 in MANUAL:
        k = key_of(MANUAL[low2]); groups[k].add(nome); groups[k].add(MANUAL[low2]); continue
    groups[key_of(nome)].add(nome)

def canonico(nomes):
    """escolhe o nome canônico: mais curto que não seja sigla-só, senão o mais comum."""
    nomes = sorted(nomes, key=lambda n: (len(n), n))
    # prefere nome com maiúscula/mista (evita 'will bank' vs 'Will Bank')
    caps = [n for n in nomes if n != n.lower()]
    return (caps or nomes)[0]

# nº egressos atuais por canonico
current_key = {}
for a in alunos:
    ea = (a.get("empresa_atual") or "").strip()
    if ea:
        current_key.setdefault(key_of(ea), 0)
        current_key[key_of(ea)] += 1

out = {}
for k, nomes in sorted(groups.items()):
    if not k:
        continue
    can = canonico(nomes)
    aliases = sorted(n for n in nomes if n != can)
    is_atual = any(n in atuais for n in nomes)
    out[can] = {
        "aliases": aliases,
        "atual": is_atual,
        "n_egressos_atual": current_key.get(k, 0),
    }

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

n_total = len(out)
n_atual = sum(1 for v in out.values() if v["atual"])
n_merged = sum(1 for v in out.values() if v["aliases"])
print(f"wrote {OUT}")
print(f"  {n_total} empresas canônicas ({n_atual} são empregador ATUAL de algum egresso)")
print(f"  {n_merged} tiveram variantes agrupadas")
print("  exemplos de merge:")
for can, v in out.items():
    if v["aliases"]:
        print(f"    {can!r} <- {v['aliases']}")

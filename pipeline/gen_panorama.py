"""Regenera o dashboard_alunos.html a partir dos JSON do pipeline, anonimizado:
  - DB.alunos  <- alunos.json (cards + linha do tempo), origem/porte via empresas_porte.json
  - SALTO      <- consolidado.json (início -> hoje de cada perfil, ordenado pelo multiplicador)
Nenhum dos dois é escrito à mão."""
import json, re, pathlib
S = pathlib.Path("/caminho/para/salario")
al = json.load(open(S/"alunos.json"))["alunos"]
por = json.load(open(S/"data/empresas_porte.json"))
order = ["barbosa","gary","possatti","helen","renan","andre","tarcisio","joel","icaro","gustavo","marialuiza",
         "gabriel_barboza","magnago","martins_miranda","geann","rodrigo_maia","andre_aguiar","guilherme_gatti",
         "ivana","joao_paulo","lucas_coutinho","marcos_dias","phillipe","anne_caroline","brendon","cassiano",
         "jennifer","ana_rubia","diego","edvaldo","magno","pedro","antonio","cristian","danilo","marlon","breno",
         "caio","lucas_gomes","derick","marcos_carneiro","mateus_garcia","ana_carolina","david_pantaleao","renato","kleber","rafael","andreangelo","icaro_gandine","paulo_ricardo"]
labels = ["A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z",
          "AA","AB","AC","AD","AE","AF","AG","AH","AI","AJ","AK","AL","AM","AN","AO","AP","AQ","AR","AS","AT","AU","AV","AW","AX"]
idlabel = dict(zip(order, labels))
byid = {a["id"]: a for a in al}

def clean(c): return re.sub(r"\s*\(.*?\)", "", (c or "")).strip()
def anon_emp(e):
    t = (e or ""); tl = t.lower(); c = clean(t)
    if "leds" in tl: return "LEDS/IFES · extensão", "Nacional"
    if "prodest" in tl: return "Prodest · bolsa FAPES", "Nacional"
    if "morpheus" in tl: return "Morpheus Jr. (empresa júnior)", "Nacional"
    if "capes" in tl: return "CAPES · bolsa IC", "Nacional"
    if tl.strip() in ("fapes",): return "FAPES · bolsa", "Nacional"
    if "cnpq" in tl: return "CNPq · bolsa", "Nacional"
    if re.search(r"\bifes\b", tl): return "IFES · estágio", "Nacional"
    if "ufes" in tl or "universidade" in tl or "lattes" in tl: return "Universidade", "Nacional"
    if tl.strip() in ("—", "", "autônomo", "autonomo", "freelance", "freelancer", "frelancers", "autônoma"):
        return "Autônomo", "Nacional"
    m = por.get(c, {})
    if m.get("porte") == "Setor público": return "Setor público", "Nacional"
    if m.get("origem") == "Internacional": return "Empresa internacional", "Internacional"
    return "Empresa nacional", "Nacional"
BRANDS = sorted([k for k in por if len(k) >= 4], key=len, reverse=True)
def scrub(c):
    c = re.split(r"\s+(?:na|no|em|at|@)\s+[A-Z0-9]", c or "")[0]
    for b in BRANDS:  # remove nome de empresa que vaze no cargo (ex.: "MongoDB Partner ...")
        c = re.sub(r"\b" + re.escape(b) + r"\b", "", c)
    return re.sub(r"\s{2,}", " ", c).strip(" -–|,")
def modalidade(local):
    t = (local or "").lower()
    return "Remoto" if "remot" in t else ("Híbrido" if ("híbr" in t or "hibr" in t) else "Presencial")
def q(s): return str(s).replace('"', "'")

def card(pid):
    a = byid[pid]; lab = idlabel[pid]
    exps = sorted(a["experiencias"], key=lambda e: e["inicio"], reverse=True)
    cur_emp, cur_org = anon_emp(a["empresa_atual"])
    exj = []
    for e in exps:
        emp, _ = anon_emp(e.get("empresa", ""))
        fim = "null" if e.get("fim") is None else '"'+e["fim"]+'"'
        exj.append(f'      {{cargo:"{q(scrub(e["cargo"]))}",empresa:"{emp}",tipo:"{e.get("tipo","Full-time")}",'
                   f'inicio:"{e["inicio"]}",fim:{fim},area:"{e.get("area","dev")}"}}')
    body = ",\n".join(exj)
    return (f'    {{id:"{lab.lower()}",nome:"Egresso {lab}",cargo_atual:"{q(scrub(a["cargo_atual"]))}",'
            f'empresa_atual:"{cur_emp}",local_atual:"{cur_org} · {modalidade(a.get("local_atual"))}",'
            f'area_atual:"{a["area_atual"]}",inicio_carreira_dev:"{a["inicio_carreira_dev"]}",'
            f'ainda_em_tech:{str(a["ainda_em_tech"]).lower()},experiencias:[\n{body}\n    ]}}')

cards = ",\n".join(card(pid) for pid in order if pid in byid)
H = S/"dashboard_alunos.html"; t = H.read_text(encoding="utf-8")
new, n = re.subn(r"(const DB = \{\n  alunos: \[\n).*?(\n  \]\n\};)",
                 lambda m: m.group(1) + cards + m.group(2), t, count=1, flags=re.S)
assert n == 1, "DB não casou"

# ---- SALTO: início -> hoje por perfil, direto do consolidado (era hardcoded) ----
cons = json.load(open(S/"data/consolidado.json"))
salto = sorted(cons["perfis"], key=lambda p: -p["cresc"])
js = "const SALTO=[" + ",".join(
    f'["{p["perfil"].replace("Perfil ", "")}",{p["med_ini"]},{p["med_atual"]},{p["cresc"]},"{p["trilha"]}"]'
    for p in salto) + "];"
new, n = re.subn(r"const SALTO=\[.*?\];", lambda m: js, new, count=1, flags=re.S)
assert n == 1, "SALTO não casou"

H.write_text(new, encoding="utf-8")
print(f"dashboard_alunos regenerado: {len(order)} cards (A–{labels[len(order)-1]}) + SALTO com {len(salto)} perfis")

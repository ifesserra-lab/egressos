#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_vitrine.py — gera a página-vitrine "Onde estão os egressos" (NOMEADA).

ATENÇÃO / PRIVACIDADE: esta página é a ÚNICA exceção autorizada ao boundary de
anonimização. Ela expõe nome + empresa + jornada de cada egresso (dados nível
LinkedIn público), a pedido explícito da coordenação. NÃO inclui salário por
nome (a série salarial fica só no relatório anonimizado). Egressos podem pedir
remoção (linha de opt-out no rodapé).

Lê (local, com PII):  alunos.json, data/analise.json, data/empresas_porte.json
Escreve (repo público): ../egressos/egressos-carreiras.html
"""
import json, os, unicodedata, re, html

HERE = os.path.dirname(os.path.abspath(__file__))   # pipeline/
ROOT = os.path.dirname(HERE)                          # salario/
DATA = os.path.join(ROOT, "data")                     # salario/data/
OUT  = os.path.abspath(os.path.join(ROOT, "..", "egressos", "egressos-carreiras.html"))

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

alunos = load(os.path.join(ROOT, "alunos.json"))
if isinstance(alunos, dict):
    alunos = alunos.get("alunos") or list(alunos.values())[0]
analise = load(os.path.join(DATA, "analise.json"))
porte   = load(os.path.join(DATA, "empresas_porte.json"))

def load_opt(p):
    try:
        return load(p)
    except FileNotFoundError:
        return {}

aliases_raw = load_opt(os.path.join(DATA, "empresas_aliases.json"))   # passo 0
li_urls     = load_opt(os.path.join(DATA, "empresas_linkedin_urls.json"))  # passo 1

# ---------- helpers ----------
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn")

def norm(s):
    return strip_accents(s).lower().strip()

def initials(nome):
    parts = [p for p in re.split(r"\s+", (nome or "").strip()) if p]
    stop = {"de","da","do","dos","das","e"}
    parts = [p for p in parts if p.lower() not in stop] or parts
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()

# 12 tons harmônicos (verde/teal/roxo/âmbar) p/ monograma
AVATAR_HUES = [158, 172, 190, 205, 220, 255, 270, 285, 42, 28, 340, 130]
def hue_for(seed):
    h = 0
    for ch in seed:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return AVATAR_HUES[h % len(AVATAR_HUES)]

# --- porte lookup (match por nome de empresa) ---
porte_idx = {}
for k, v in porte.items():
    porte_idx[norm(k)] = v
def porte_lookup(empresa):
    n = norm(empresa)
    if n in porte_idx:
        return porte_idx[n]
    # contains match
    for k, v in porte_idx.items():
        if k and (k in n or n in k):
            return v
    return None

# --- normalização de região / país (exterior) ---
COUNTRY = [
    (r"london|reino unido|united kingdom|\buk\b", "Reino Unido", "🇬🇧"),
    (r"lisbon|lisboa|oeiras|porto|portugal", "Portugal", "🇵🇹"),
    (r"berlim|berlin|alemanha|germany", "Alemanha", "🇩🇪"),
    (r"santiago|chile", "Chile", "🇨🇱"),
    (r"united states|estados unidos|florida|\bus\b|\busa\b|eua", "Estados Unidos", "🇺🇸"),
    (r"espanha|spain|madrid|barcelona", "Espanha", "🇪🇸"),
]
def region_of(local):
    n = norm(local)
    for pat, pais, flag in COUNTRY:
        if re.search(pat, n):
            return ("Exterior", pais, flag)
    if re.search(r"\bes\b|vitoria|vila velha|cariacica|serra|espirito|guarapari|linhares|colatina|viana", n):
        return ("Espírito Santo", "Espírito Santo", "")
    if re.search(r"sao paulo|\bsp\b", n): return ("São Paulo", "São Paulo", "")
    if re.search(r"rio de janeiro|\brj\b", n): return ("Rio de Janeiro", "Rio de Janeiro", "")
    if re.search(r"curitiba|parana", n): return ("Paraná", "Paraná", "")
    if re.search(r"florianopolis|santa catarina|\bsc\b", n): return ("Santa Catarina", "Santa Catarina", "")
    if re.search(r"brasilia|distrito federal|federal district", n): return ("Distrito Federal", "Distrito Federal", "")
    return ("Remoto / Brasil", "Brasil", "🌎")

# --- rótulo de local LIMPO p/ o card: "Cidade, UF" (BR) / "Cidade" (exterior) / "Remoto" ---
_UF = {"espirito santo":"ES","santa catarina":"SC","parana":"PR","sao paulo":"SP",
       "rio de janeiro":"RJ","federal district":"DF","distrito federal":"DF",
       "minas gerais":"MG","bahia":"BA","pernambuco":"PE","ceara":"CE"}
_CIDADE_EXT = {"london":"Londres","lisbon":"Lisboa",
               "united states":"Estados Unidos","estados unidos":"Estados Unidos"}
def clean_local(local, regiao, pais):
    t = local or ""
    # tira modalidade (· Remote / (Remoto) / etc.) e ruído
    t = re.sub(r"\s*[·|]\s*(remote|on-?site|remoto|h[íi]brido|hybrid|presencial).*$", "", t, flags=re.I)
    t = re.sub(r"\s*\((remoto|h[íi]brido|hybrid|remote|presencial)\)", "", t, flags=re.I)
    t = re.sub(r"metropolitan area", "", t, flags=re.I).strip(" ,·|")
    low = norm(t)
    if not t or low in ("remoto","remote","nao especificado","brazil","brasil"):
        return "Remoto" if regiao == "Remoto / Brasil" else regiao
    parts = [p.strip() for p in t.split(",") if p.strip() and norm(p.strip()) not in ("brazil","brasil")]
    if regiao == "Exterior":
        city = parts[0] if parts else pais
        return _CIDADE_EXT.get(norm(city), city)
    if len(parts) >= 2:
        city, estado = parts[0], parts[-1]
        uf = _UF.get(norm(estado), estado)
        return f"{city}, {uf}"
    # 1 parte só: é cidade/nome — não converte pra UF (evita "Rio de Janeiro"->"RJ")
    return parts[0]

# --- trilha / senioridade a partir de cargo+area ---
def trilha_of(area, cargo):
    a = norm(area); c = norm(cargo)
    if a == "data" or re.search(r"dados|\bdata\b|scientist|analista de dados", c):
        return "Dados"
    if a in ("gestao","lideranca") or re.search(r"gerente|manager|coordenador|\bhead\b|diretor", c):
        return "Gestão & Liderança"
    if a == "mobile" or re.search(r"android|ios\b|mobile", c):
        return "Mobile"
    if re.search(r"product manager|produto|designer|\bux\b|\bui\b", c):
        return "Produto & Design"
    if a == "academico" or re.search(r"professor|researcher|pesquisador|docente", c):
        return "Academia"
    return "Software"

def nivel_of(cargo):
    c = norm(cargo)
    if re.search(r"gerente|manager|coordenador|\bhead\b|diretor", c):
        return "Gestão"
    if re.search(r"staff|principal", c):
        return "Staff+"
    if re.search(r"senior|s[êe]nior|\bsr\b|lead|l[íi]der|leader|arquiteto|architect|tech lead", c):
        return "Sênior / Lead"
    return "Pleno"

# ---------- monta perfis ----------
perfis = []
for x in alunos:
    nome  = x.get("nome") or ""
    cargo = x.get("cargo_atual") or ""
    empresa = x.get("empresa_atual") or ""
    local = x.get("local_atual") or ""
    area  = x.get("area_atual") or ""
    reg, pais, flag = region_of(local)
    pinfo = porte_lookup(empresa) or {}
    exps = []
    for e in x.get("experiencias", []):
        exps.append({
            "cargo": e.get("cargo") or "",
            "empresa": e.get("empresa") or "",
            "tipo": e.get("tipo") or "",
            "inicio": e.get("inicio") or "",
            "fim": e.get("fim"),
            "duracao": e.get("duracao") or "",
            "local": e.get("local") or "",
            "desc": (e.get("descricao") or "")[:280],
            "skills": (e.get("skills") or [])[:8],
            "bolsa": bool(e.get("fonte_bolsa") or e.get("projeto_fapes") or e.get("bolsa_valor_mensal")),
            "fonte_bolsa": e.get("fonte_bolsa") or "",
        })
    perfis.append({
        "id": x.get("id"),
        "nome": nome,
        "ini": initials(nome),
        "hue": hue_for(x.get("id") or nome),
        "cargo": cargo,
        "empresa": empresa,
        "local": local,
        "local_disp": clean_local(local, reg, pais),
        "regiao": reg,
        "pais": pais,
        "flag": flag,
        "trilha": trilha_of(area, cargo),
        "nivel": nivel_of(cargo),
        "origem": pinfo.get("origem") or "",
        "porte": pinfo.get("porte") or "",
        "setor": pinfo.get("setor") or "",
        "inicio": x.get("inicio_carreira_dev") or "",
        "url": x.get("url") or "",
        "exp": exps,
    })

# ordena: exterior primeiro, depois sênior/gestão, depois nome
_niv_rank = {"Staff+":0,"Sênior / Lead":1,"Gestão":1,"Pleno":2}
perfis.sort(key=lambda p: (0 if p["regiao"]=="Exterior" else 1,
                           _niv_rank.get(p["nivel"],3),
                           norm(p["nome"])))

# ---------- empresas atuais distintas (nomeadas, dedup por alias — passo 0) ----------
# mapa alias/variante -> nome canônico e canônico -> URL LinkedIn (passo 1, se resolvido)
alias2canon = {}
for can, meta in aliases_raw.items():
    alias2canon[norm(can)] = can
    for al in meta.get("aliases", []):
        alias2canon[norm(al)] = can
canon2url = {can: (v.get("url")) for can, v in li_urls.items() if v.get("slug")}

# dado verificado do LinkedIn (browser-use) — casa por nome canônico (case-insensitive)
_porte_by_norm = {norm(k): v for k, v in porte.items()}
def verif_of(can):
    v = _porte_by_norm.get(norm(can), {})
    if not v.get("headcount_linkedin") and not v.get("hq_local"):
        return None
    return v

def _digits(s):
    return int(re.sub(r"\D", "", s) or 0)
def size_short(hc):
    if not hc:
        return None
    hc = re.sub(r"(\d)\s*[kK]\b", lambda m: m.group(1) + "000", hc)  # "1K-5K" -> "1000-5000"
    def k(n):
        return f"{n//1000}k" if n >= 1000 and n % 1000 == 0 else (f"{n/1000:.0f}k" if n >= 1000 else str(n))
    m = re.search(r"(\d[\d.,]*)\s*[-–]\s*(\d[\d.,]*)", hc)  # 1ª faixa "X-Y" (ignora "(12.000...)")
    if m:
        return f"{k(_digits(m.group(1)))}–{k(_digits(m.group(2)))}"
    m = re.search(r"(\d[\d.,]*)\s*\+", hc)                   # "10,001+"
    if m:
        return f"{k(_digits(m.group(1)))}+"
    m = re.search(r"\d[\d.,]*", hc)
    return k(_digits(m.group(0))) if m else None

def canon_of(nome):
    return alias2canon.get(norm(nome), nome)

seen=set(); empresas_cards=[]
for p in perfis:
    can = canon_of(p["empresa"])
    key = norm(can)
    if not key or key in seen:
        continue
    seen.add(key)
    v = verif_of(can) or {}
    empresas_cards.append({"nome": can, "origem": p["origem"], "porte": p["porte"],
                           "url": canon2url.get(can),
                           "size": size_short(v.get("headcount_linkedin")),
                           "hq": v.get("hq_local"), "industry": v.get("industry_linkedin"),
                           "hiring": v.get("contratando")})
# internacional primeiro, depois porte, depois nome
_porte_rank={"Multinacional / BigTech":0,"BigTech":0,"Grande nacional":1,"Scale-up":2,
             "Startup / scale-up":2,"Média":3,"Média nacional":3,"Setor público":4}
empresas_cards.sort(key=lambda e:(0 if norm(e["origem"]).startswith("intern") else 1,
                                  _porte_rank.get(e["porte"],5), norm(e["nome"])))

# ---------- números p/ hero (do analise.json, QA-validado) ----------
intl = analise["intl_timeline"][-1]           # 2026
setores = analise["empresas"]["setor"]
regioes = analise["empresas"]["regiao"]
porte_agg = analise["empresas"]["porte"]
sankey = analise["sankey"]
labs = analise["outros_labs"]
ext = analise["extensao"]
lid = analise["lideranca_gestao"]
trilha_carreira = analise["trilha_carreira"]

n_total = len(perfis)
n_exterior = sum(1 for p in perfis if p["regiao"]=="Exterior")   # local atual no exterior
n_ja_intl = intl["intl"]                                          # já atuaram no exterior
n_empresas = len(empresas_cards)
def _porte_n(label): return next((r["n"] for r in porte_agg if r["porte"]==label),0)
n_bigtech = _porte_n("Multinacional / BigTech")
n_lideranca = lid["total"]
n_extensao = next((v["n"] for v in sankey["vias"] if "Extens" in v["nome"]),0)
n_pesquisa = next((v["n"] for v in sankey["vias"] if "Pesquisa" in v["nome"]),0)

# países no exterior (distintos, com flag)
paises_ext = []
for p in perfis:
    if p["regiao"]=="Exterior" and p["pais"] not in [x[0] for x in paises_ext]:
        paises_ext.append((p["pais"], p["flag"]))

# ---------- HTML ----------
esc = lambda s: html.escape(str(s or ""))
DATA_JSON = json.dumps(perfis, ensure_ascii=False)

def bars(items, key, val, accent="var(--accent)"):
    mx = max((i[val] for i in items), default=1) or 1
    rows=[]
    for i in items:
        pct = round(i[val]/mx*100)
        rows.append(
          f'<div class="bar-row"><div class="bar-lab">{esc(i[key])}</div>'
          f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{accent}"></div></div>'
          f'<div class="bar-n">{i[val]}</div></div>')
    return "\n".join(rows)

import urllib.parse as _up
def linkedin_search(nome):
    # busca de EMPRESAS direto no LinkedIn -> abre a company page correta no navegador
    # do usuário (logado). Sem scraping, sem intermediário.
    q = _up.quote(nome)
    return f"https://www.linkedin.com/search/results/companies/?keywords={q}"

def _chip(e):
    intl = norm(e["origem"]).startswith("intern")
    cls = "ec intl" if intl else "ec"
    glob = "🌐 " if intl else ""
    size = e.get("size")
    sizespan = f'<span class="ecsz">· {esc(size)}</span>' if size else ""
    label = f'{glob}{esc(e["nome"])} {sizespan}'
    url = e.get("url") or linkedin_search(e["nome"])
    tip_bits = [b for b in (e.get("hq"), e.get("industry"),
                            (f'{esc(size)} func.' if size else None),
                            ("contratando" if e.get("hiring") else None)) if b]
    tip = (" · ".join(esc(x) for x in tip_bits)) if tip_bits else f'Ver {esc(e["nome"])} no LinkedIn'
    return (f'<a class="{cls} lk" href="{esc(url)}" target="_blank" '
            f'rel="noopener" title="{tip}">{label} ↗</a>')

emp_chips = "\n".join(_chip(e) for e in empresas_cards)
n_empresas_link = sum(1 for e in empresas_cards if e.get("url"))
n_empresas_dados = sum(1 for e in empresas_cards if e.get("size"))
link_note = " Clique pra abrir no LinkedIn ↗." + (
    f' <b style="color:var(--accent)">{n_empresas_dados} com tamanho verificado.</b>' if n_empresas_dados else "")

# --- tabela "As empresas" (dados verificados via browser-use) — p/ análise ---
def _rank(sz):
    if not sz: return -1
    tok = sz.lower().replace("–", "-").split("-")[0].strip()
    tok = tok.replace("+", "").replace("k", "000")
    n = re.sub(r"\D", "", tok)
    return int(n) if n else 0

def _name_cell(e):
    glob = "🌐 " if norm(e["origem"]).startswith("intern") else ""
    if e.get("url"):
        return f'{glob}<a href="{esc(e["url"])}" target="_blank" rel="noopener">{esc(e["nome"])} ↗</a>'
    return f'{glob}{esc(e["nome"])}'

_emp_data = sorted([e for e in empresas_cards if e.get("size")],
                   key=lambda e: (-_rank(e["size"]), norm(e["nome"])))
if _emp_data:
    _rows = "\n".join(
        f'<tr><td class="etn">{_name_cell(e)}</td>'
        f'<td class="etnum">{esc(e["size"])}</td>'
        f'<td>{esc(e.get("hq") or "—")}</td>'
        f'<td>{esc(e.get("industry") or "—")}</td>'
        f'<td class="etc">{"✅ sim" if e.get("hiring") else "—"}</td></tr>'
        for e in _emp_data)
    empresas_table = (
      '<section class="card">'
      '<h2>As empresas — dados verificados</h2>'
      f'<p class="hint">{len(_emp_data)} de {n_empresas} empresas com dados reais do LinkedIn '
      '(tamanho, sede, setor, vagas), coletados via browser-use. As demais seguem por estimativa de nome.</p>'
      '<div class="chart-scroll"><table class="etab">'
      '<thead><tr><th>Empresa</th><th>Tamanho</th><th>Sede</th><th>Setor</th><th>Vagas</th></tr></thead>'
      f'<tbody>{_rows}</tbody></table></div></section>')
else:
    empresas_table = ""

paises_chips = "  ".join(f'<span class="flagchip">{f} {esc(n)}</span>' for n,f in paises_ext)

HTML = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Onde estão os egressos — carreiras do IFES Campus Serra</title>
<meta name="description" content="Trajetórias reais de egressos de TI do IFES Campus Serra: onde estão hoje, em quais empresas e o caminho (extensão, pesquisa, monitoria) que os levou até lá.">
<style>
  .root{{
    color-scheme:light;
    --plane:#f3f6f4; --surface:#ffffff; --surface-2:#eef3f0;
    --ink:#122019; --ink-2:#4a5a53; --muted:#83918a;
    --line:#e1e8e4; --border:rgba(18,32,25,.10);
    --accent:#0e8a68; --accent-2:#0b6e53;
    --band:rgba(14,138,104,.15); --band-thin:rgba(14,138,104,.07);
    --amber:#bd7d00; --data:#5a4bc4; --intl:#2563c9; --bolsa:rgba(189,125,0,.11);
    --shadow:0 1px 2px rgba(18,32,25,.05),0 8px 24px rgba(18,32,25,.07);
    background:var(--plane); color:var(--ink);
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif; -webkit-font-smoothing:antialiased;
    min-height:100%; padding:16px 13px; box-sizing:border-box;
  }}
  @media (prefers-color-scheme:dark){{ :root:where(:not([data-theme="light"])) .root{{
    color-scheme:dark; --plane:#0a0e0c; --surface:#141a17; --surface-2:#1d2521;
    --ink:#eef3f0; --ink-2:#aebab4; --muted:#7a877f; --line:#242c28; --border:rgba(255,255,255,.10);
    --accent:#2fbc90; --accent-2:#37c99b; --band:rgba(47,188,144,.20); --band-thin:rgba(47,188,144,.08);
    --amber:#dda52f; --data:#9285ea; --intl:#5b9cf5; --bolsa:rgba(221,165,47,.15);
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.5);
  }}}}
  :root[data-theme="dark"] .root{{
    color-scheme:dark; --plane:#0a0e0c; --surface:#141a17; --surface-2:#1d2521;
    --ink:#eef3f0; --ink-2:#aebab4; --muted:#7a877f; --line:#242c28; --border:rgba(255,255,255,.10);
    --accent:#2fbc90; --accent-2:#37c99b; --band:rgba(47,188,144,.20); --band-thin:rgba(47,188,144,.08);
    --amber:#dda52f; --data:#9285ea; --intl:#5b9cf5; --bolsa:rgba(221,165,47,.15);
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.5);
  }}

  *{{ box-sizing:border-box; }}
  .wrap{{ max-width:1000px; margin:0 auto; display:flex; flex-direction:column; gap:18px; }}
  .eyebrow{{ font-size:12px; font-weight:700; letter-spacing:.11em; text-transform:uppercase; color:var(--accent); margin:0 0 10px; }}
  h1{{ font-size:clamp(26px,5vw,46px); line-height:1.06; margin:0 0 14px; font-weight:780; letter-spacing:-.022em; text-wrap:balance; }}
  h1 em{{ font-style:normal; color:var(--accent); }}
  .lede{{ font-size:clamp(15px,1.7vw,17.5px); line-height:1.58; color:var(--ink-2); margin:0; max-width:64ch; }}
  .lede b{{ color:var(--ink); }}

  .hero-kpi{{ display:grid; grid-template-columns:repeat(2,1fr); gap:1px; background:var(--border); border:1px solid var(--border); border-radius:16px; overflow:hidden; box-shadow:var(--shadow); }}
  .hk{{ background:var(--surface); padding:16px 15px; }}
  .hk .v{{ font-size:clamp(24px,3.6vw,34px); font-weight:780; letter-spacing:-.02em; line-height:1; font-variant-numeric:tabular-nums; white-space:nowrap; color:var(--accent); }}
  .hk .v small{{ font-size:14px; font-weight:600; color:var(--ink-2); letter-spacing:0; }}
  .hk .k{{ font-size:12px; color:var(--muted); margin-top:8px; line-height:1.35; }}

  .card{{ background:var(--surface); border:1px solid var(--border); border-radius:16px; box-shadow:var(--shadow); padding:clamp(18px,2.6vw,26px); }}
  .card>h2{{ font-size:12.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-2); margin:0 0 4px; font-weight:700; }}
  .card .hint{{ font-size:12.5px; color:var(--muted); margin:0 0 18px; }}
  .card p.body{{ font-size:14.5px; line-height:1.6; color:var(--ink-2); margin:0 0 12px; }}
  .card p.body b{{ color:var(--ink); }}

  .nav{{ display:flex; flex-wrap:wrap; gap:10px; }}
  .nav a{{ flex:1 1 220px; text-decoration:none; background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:13px 15px; box-shadow:var(--shadow); font-weight:650; font-size:13.5px; color:var(--accent); }}
  .nav a span{{ display:block; font-weight:400; color:var(--ink-2); font-size:12px; margin-top:3px; line-height:1.4; }}

  /* barras */
  .bar-row{{ display:grid; grid-template-columns:135px 1fr 34px; align-items:center; gap:10px; padding:6px 0; }}
  .bar-lab{{ font-size:12.5px; color:var(--ink-2); }}
  .bar-track{{ height:9px; background:var(--surface-2); border-radius:999px; overflow:hidden; }}
  .bar-fill{{ height:100%; border-radius:999px; }}
  .bar-n{{ font-size:12.5px; font-weight:700; text-align:right; font-variant-numeric:tabular-nums; color:var(--ink); }}
  .split{{ display:grid; grid-template-columns:1fr; gap:22px; }}
  @media (min-width:720px){{ .split{{ grid-template-columns:1fr 1fr; gap:34px; }} }}
  .subh{{ font-size:11px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:var(--muted); margin:0 0 10px; }}

  .flagrow{{ display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }}
  .flagchip{{ font-size:13px; font-weight:650; padding:7px 13px; border-radius:999px; background:rgba(37,99,201,.10); color:var(--intl); border:1px solid rgba(37,99,201,.22); }}

  /* empresas chips */
  .eclist{{ display:flex; flex-wrap:wrap; gap:8px; }}
  .ec{{ font-size:12.5px; font-weight:600; padding:6px 12px; border-radius:8px; background:var(--surface-2); color:var(--ink-2); border:1px solid var(--border); }}
  .ec.intl{{ background:rgba(37,99,201,.09); color:var(--intl); border-color:rgba(37,99,201,.20); }}
  a.ec.lk{{ text-decoration:none; cursor:pointer; transition:border-color .12s, color .12s; }}
  a.ec.lk:hover{{ border-color:var(--accent); color:var(--accent); }}
  .ecsz{{ font-weight:700; opacity:.62; font-variant-numeric:tabular-nums; margin-left:1px; }}
  .chart-scroll{{ overflow-x:auto; }}
  .etab{{ width:100%; border-collapse:collapse; font-size:13px; min-width:520px; }}
  .etab th,.etab td{{ text-align:left; padding:9px 11px; border-bottom:1px solid var(--border); vertical-align:top; }}
  .etab th{{ color:var(--muted); font-weight:700; font-size:10.5px; text-transform:uppercase; letter-spacing:.04em; }}
  .etab td.etn{{ font-weight:650; }}
  .etab td.etn a{{ color:var(--accent); text-decoration:none; }}
  .etab td.etn a:hover{{ text-decoration:underline; }}
  .etab td.etnum{{ font-variant-numeric:tabular-nums; font-weight:700; white-space:nowrap; }}
  .etab td.etc{{ white-space:nowrap; }}
  .etab tr:last-child td{{ border-bottom:none; }}

  /* trilhas / origem */
  .pillars{{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; margin-top:4px; }}
  .pillar{{ background:var(--surface-2); border:1px solid var(--border); border-radius:14px; padding:16px 18px; border-top:3px solid var(--pc,var(--accent)); }}
  .pillar .tag{{ font-size:11px; font-weight:700; color:var(--pc,var(--accent)); letter-spacing:.04em; text-transform:uppercase; }}
  .pillar h3{{ margin:5px 0 6px; font-size:16px; font-weight:730; }}
  .pillar h3 b{{ color:var(--pc,var(--accent)); }}
  .pillar p{{ margin:0; font-size:13px; line-height:1.5; color:var(--ink-2); }}

  /* filtros */
  .toolbar{{ display:flex; flex-direction:column; gap:12px; }}
  .search{{ width:100%; font-size:14.5px; padding:12px 15px; border-radius:12px; border:1px solid var(--border); background:var(--surface-2); color:var(--ink); }}
  .search::placeholder{{ color:var(--muted); }}
  .filters{{ display:flex; flex-wrap:wrap; gap:7px; }}
  .filt{{ font-size:12.5px; font-weight:650; padding:7px 13px; border-radius:999px; background:var(--surface-2); color:var(--ink-2); border:1px solid var(--border); cursor:pointer; user-select:none; }}
  .filt[aria-pressed="true"]{{ background:var(--accent); color:#fff; border-color:var(--accent); }}
  .count{{ font-size:12px; color:var(--muted); }}

  /* grid de perfis */
  .grid{{ display:grid; grid-template-columns:1fr; gap:12px; margin-top:16px; }}
  @media (min-width:560px){{ .grid{{ grid-template-columns:1fr 1fr; }} }}
  @media (min-width:880px){{ .grid{{ grid-template-columns:1fr 1fr 1fr; }} }}
  .pcard{{ background:var(--surface); border:1px solid var(--border); border-radius:14px; box-shadow:var(--shadow); padding:16px; text-align:left; cursor:pointer; display:flex; flex-direction:column; gap:11px; transition:transform .12s ease, box-shadow .12s ease; font:inherit; color:inherit; }}
  .pcard:hover{{ transform:translateY(-2px); box-shadow:0 4px 10px rgba(18,32,25,.10),0 14px 34px rgba(18,32,25,.12); }}
  .pcard:focus-visible{{ outline:2px solid var(--accent); outline-offset:2px; }}
  .pc-top{{ display:flex; gap:12px; align-items:center; }}
  .av{{ flex:none; width:46px; height:46px; border-radius:50%; display:grid; place-items:center; font-size:16px; font-weight:750; color:#fff; letter-spacing:.02em; overflow:hidden; position:relative; }}
  .av img{{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }}
  .pc-id{{ min-width:0; }}
  .pc-nome{{ font-size:14.5px; font-weight:720; line-height:1.2; }}
  .pc-cargo{{ font-size:12.5px; color:var(--ink-2); line-height:1.35; margin-top:2px; }}
  .pc-emp{{ color:var(--accent); font-weight:650; }}
  .pc-meta{{ display:flex; flex-wrap:wrap; gap:6px; }}
  .tg{{ font-size:11px; font-weight:600; padding:3px 9px; border-radius:999px; background:var(--surface-2); color:var(--muted); border:1px solid var(--border); }}
  .tg.loc{{ color:var(--ink-2); }}
  .tg.intl{{ background:rgba(37,99,201,.10); color:var(--intl); border-color:rgba(37,99,201,.20); }}
  .tg.tr{{ color:var(--accent); }}
  .pc-more{{ font-size:11.5px; color:var(--muted); margin-top:auto; }}

  /* modal */
  .ov{{ position:fixed; inset:0; background:rgba(10,14,12,.55); backdrop-filter:blur(3px); display:none; z-index:1000; padding:16px; overflow-y:auto; }}
  .ov.open{{ display:block; }}
  .modal{{ max-width:640px; margin:24px auto; background:var(--surface); border:1px solid var(--border); border-radius:18px; box-shadow:0 20px 60px rgba(0,0,0,.35); overflow:hidden; }}
  .m-head{{ padding:22px 22px 18px; border-bottom:1px solid var(--border); display:flex; gap:15px; align-items:center; position:relative; }}
  .m-head .av{{ width:60px; height:60px; font-size:21px; }}
  .m-nome{{ font-size:20px; font-weight:770; line-height:1.15; }}
  .m-cargo{{ font-size:13.5px; color:var(--ink-2); margin-top:3px; }}
  .m-cargo b{{ color:var(--accent); }}
  .m-loc{{ font-size:12.5px; color:var(--muted); margin-top:4px; }}
  .m-close{{ position:absolute; top:14px; right:14px; width:32px; height:32px; border-radius:50%; border:1px solid var(--border); background:var(--surface-2); color:var(--ink-2); font-size:17px; cursor:pointer; line-height:1; }}
  .m-body{{ padding:20px 22px 24px; }}
  .m-sec{{ font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin:0 0 14px; }}
  .tl{{ position:relative; padding-left:24px; }}
  .tl:before{{ content:""; position:absolute; left:6px; top:4px; bottom:4px; width:2px; background:var(--line); }}
  .tli{{ position:relative; padding:0 0 20px; }}
  .tli:last-child{{ padding-bottom:0; }}
  .tli:before{{ content:""; position:absolute; left:-22px; top:4px; width:11px; height:11px; border-radius:50%; background:var(--surface); border:2.5px solid var(--accent); }}
  .tli.bolsa:before{{ border-color:var(--amber); background:var(--bolsa); }}
  .tli-role{{ font-size:14px; font-weight:700; line-height:1.25; }}
  .tli-emp{{ font-size:13px; color:var(--accent); font-weight:650; }}
  .tli-when{{ font-size:11.5px; color:var(--muted); margin:2px 0 6px; font-variant-numeric:tabular-nums; }}
  .tli-desc{{ font-size:12.5px; line-height:1.5; color:var(--ink-2); margin:0 0 7px; }}
  .tli-sk{{ display:flex; flex-wrap:wrap; gap:5px; }}
  .sk{{ font-size:10.5px; padding:2px 8px; border-radius:6px; background:var(--surface-2); color:var(--muted); border:1px solid var(--border); }}
  .bpill{{ display:inline-block; font-size:10px; font-weight:700; padding:2px 8px; border-radius:999px; background:var(--bolsa); color:var(--amber); margin-left:6px; vertical-align:middle; }}
  .m-link{{ display:inline-flex; align-items:center; gap:6px; margin-top:16px; font-size:13px; font-weight:650; color:var(--intl); text-decoration:none; }}

  /* CTA */
  .cta{{ background:linear-gradient(135deg,var(--accent),var(--accent-2)); color:#fff; border:none; }}
  .cta h2{{ color:rgba(255,255,255,.85)!important; }}
  .cta h3{{ font-size:clamp(19px,2.6vw,26px); font-weight:770; margin:0 0 10px; letter-spacing:-.01em; }}
  .cta p{{ font-size:14.5px; line-height:1.6; color:rgba(255,255,255,.92); margin:0 0 18px; max-width:60ch; }}
  .cta .steps{{ display:grid; grid-template-columns:1fr; gap:12px; }}
  @media (min-width:640px){{ .cta .steps{{ grid-template-columns:repeat(3,1fr); }} }}
  .cta .step{{ background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.22); border-radius:13px; padding:15px 16px; }}
  .cta .step .n{{ font-size:11px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; opacity:.85; }}
  .cta .step h4{{ margin:5px 0 5px; font-size:15px; font-weight:730; }}
  .cta .step p{{ font-size:12.5px; margin:0; color:rgba(255,255,255,.9); }}

  .foot{{ font-size:11.5px; color:var(--muted); text-align:center; line-height:1.7; margin-top:4px; }}
  .foot a{{ color:var(--accent); }}
  .foot .opt{{ display:inline-block; margin-top:8px; padding:9px 14px; border:1px solid var(--border); border-radius:10px; background:var(--surface); }}

  .exp-banner{{position:fixed;top:0;left:0;right:0;z-index:99999;background:#c62828;color:#fff;
    font:600 13.5px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;text-align:center;
    padding:10px 18px;letter-spacing:.02em;box-shadow:0 2px 10px rgba(0,0,0,.28);
    background-image:repeating-linear-gradient(45deg,rgba(0,0,0,.14) 0 14px,transparent 14px 28px)}}
  .exp-banner strong{{font-weight:800;letter-spacing:.06em}}
  .root{{padding-top:clamp(60px,7vw,76px)!important}}
  @media(max-width:640px){{.exp-banner{{font-size:11.5px;padding:8px 12px}}}}

  @media (min-width:560px){{ .hero-kpi{{ grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); }} .hk{{ padding:20px 18px; }} }}
  @media (min-width:600px){{ .root{{ padding:32px 26px; }} .wrap{{ gap:26px; }} }}
  @media (min-width:960px){{ .root{{ padding:52px; }} }}
</style>
</head>
<body>

<div class="exp-banner" role="alert">
  ⚠️ <strong>SITE EXPERIMENTAL</strong> — em construção. Dados de perfil coletados de fontes públicas (LinkedIn); qualquer egresso pode pedir correção ou remoção.
</div>

<div class="root">
  <div class="wrap">

    <header>
      <p class="eyebrow">Egressos · IFES — Campus Serra</p>
      <h1>Eles começaram em Serra. Hoje estão <em>no mundo todo</em>.</h1>
      <p class="lede">Você está no IFES agora, na dúvida se esse caminho leva a algum lugar. Estes <b>{n_total} egressos de TI</b> sentaram na mesma cadeira — e hoje são engenheiros, tech leads e gestores em <b>{n_empresas} empresas</b>, de startups capixabas a gigantes globais, com gente em <b>{len(paises_ext)} países</b>. Esta página mostra <b>onde estão</b>, <b>em quais empresas</b> e — o mais importante — <b>o caminho que os levou até lá</b>.</p>
    </header>

    <nav class="nav" aria-label="Outras visões">
      <a href="index.html">📊 Impacto na carreira →<span>Trajetória de renda vs. mercado (anonimizado)</span></a>
      <a href="dashboard_alunos.html">👥 Panorama por egresso →<span>Linha do tempo e cards (A–…)</span></a>
      <a href="metodologia.html">🔬 Metodologia →<span>Como o estudo foi feito</span></a>
    </nav>

    <section class="hero-kpi">
      <div class="hk"><div class="v">{n_total}</div><div class="k">egressos mapeados</div></div>
      <div class="hk"><div class="v">{n_empresas}</div><div class="k">empresas diferentes</div></div>
      <div class="hk"><div class="v">{n_ja_intl}<small> ({intl['pct']}%)</small></div><div class="k">já atuaram no exterior</div></div>
      <div class="hk"><div class="v">{n_bigtech}</div><div class="k">em multinacional / BigTech</div></div>
      <div class="hk"><div class="v">{n_lideranca}</div><div class="k">em liderança ou gestão</div></div>
    </section>

    <!-- ONDE ESTÃO -->
    <section class="card">
      <h2>Onde estão hoje</h2>
      <p class="hint">Localização atual declarada — do Espírito Santo ao exterior</p>
      <div class="split">
        <div>
          <p class="subh">Por região</p>
          {bars(regioes, "regiao", "n")}
        </div>
        <div>
          <p class="subh">Modalidade de trabalho</p>
          {bars(analise["empresas"]["modalidade"], "modalidade", "n", "var(--data)")}
          <p class="subh" style="margin-top:22px">No exterior</p>
          <p class="body" style="margin:0 0 2px">{n_ja_intl} egressos já construíram carreira fora do Brasil — começou em 2020 e cresce todo ano.</p>
          <div class="flagrow">{paises_chips}</div>
        </div>
      </div>
    </section>

    <!-- EMPRESAS -->
    <section class="card">
      <h2>Em quais empresas</h2>
      <p class="hint">{n_empresas} empresas onde egressos atuam hoje — <span style="color:var(--intl)">🌐 = internacional</span>. De software house capixaba a BigTech.{link_note}</p>
      <div class="eclist">{emp_chips}</div>
      <div class="pillars" style="margin-top:20px">
        <div class="pillar" style="--pc:var(--intl)"><span class="tag">Global</span><h3><b>{n_bigtech}</b> em BigTech / multinacional</h3><p>Software global, consultoria internacional e fintechs com operação lá fora.</p></div>
        <div class="pillar"><span class="tag">Escala</span><h3><b>{_porte_n("Startup / scale-up")}</b> em startup / scale-up</h3><p>Produto e crescimento — onde engenheiro põe a mão em tudo.</p></div>
        <div class="pillar" style="--pc:var(--amber)"><span class="tag">Sólido</span><h3><b>{_porte_n("Grande nacional")}</b> em grande empresa nacional</h3><p>Bancos, indústria e serviços de grande porte no Brasil.</p></div>
      </div>
    </section>

    {empresas_table}

    <!-- TRILHAS -->
    <section class="card">
      <h2>O caminho até aqui</h2>
      <p class="hint">O que quase todos têm em comum: começaram dentro do IFES, antes do primeiro emprego</p>
      <p class="body">Não foi sorte. A maioria passou por <b>extensão, pesquisa ou monitoria</b> ainda na graduação — botando a mão em projeto real, com cliente, método e prazo, antes de assinar a primeira carteira. É esse repertório que abre a porta do primeiro emprego já em posição melhor.</p>
      <div class="pillars">
        <div class="pillar"><span class="tag">Extensão</span><h3><b>{n_extensao}</b> vieram da extensão</h3><p>Laboratórios do IFES (LEDS entre os principais) — projeto com cliente real, método ágil e liderança antes do emprego.</p></div>
        <div class="pillar" style="--pc:var(--data)"><span class="tag">Pesquisa</span><h3><b>{n_pesquisa}</b> passaram por pesquisa / IC</h3><p>Iniciação científica com bolsa (FAPES/Prodest) — primeiro contato com problema real em escala.</p></div>
        <div class="pillar" style="--pc:var(--amber)"><span class="tag">Liderança cedo</span><h3><b>{n_lideranca}</b> já lideram times</h3><p>De tech lead a gerente — a liderança começou coordenando colegas no laboratório.</p></div>
      </div>
      <p class="body" style="margin-top:16px"><b>Além do LEDS:</b> egressos passaram também por Nu(TeC)², LabTel, NEMO, LAR e NERA — o ecossistema de labs do IFES/UFES. <a href="metodologia.html" style="color:var(--accent)">Como medimos isso →</a></p>
    </section>

    <!-- PERFIS -->
    <section class="card">
      <h2>Conheça os egressos</h2>
      <p class="hint">Toque num card para ver a jornada completa — do primeiro projeto no IFES ao cargo de hoje</p>
      <div class="toolbar">
        <input id="q" class="search" type="search" placeholder="Buscar por nome, empresa, cargo ou tecnologia…" aria-label="Buscar egressos">
        <div class="filters" id="filters" role="group" aria-label="Filtros"></div>
        <div class="count" id="count"></div>
      </div>
      <div class="grid" id="grid"></div>
    </section>

    <!-- CTA -->
    <section class="card cta">
      <h2 style="color:rgba(255,255,255,.85)">Para quem está começando agora</h2>
      <h3>Quer trilhar esse caminho? Ele começa dentro do IFES.</h3>
      <p>Todo egresso desta página começou exatamente onde você está. A diferença: eles entraram cedo num laboratório, numa monitoria ou num projeto de pesquisa. Você pode fazer o mesmo neste semestre.</p>
      <div class="steps">
        <div class="step"><div class="n">Passo 1</div><h4>Entre num laboratório</h4><p>Procure LEDS, Nu(TeC)², LabTel, NERA e afins. Projeto real com cliente é o que mais pesa no primeiro currículo.</p></div>
        <div class="step"><div class="n">Passo 2</div><h4>Busque uma bolsa de IC</h4><p>Iniciação científica com bolsa FAPES/Prodest. Fale com professores sobre editais abertos.</p></div>
        <div class="step"><div class="n">Passo 3</div><h4>Seja monitor</h4><p>Ensinar consolida o fundamento — e é a primeira experiência de liderança que aparece no currículo.</p></div>
      </div>
    </section>

    <p class="foot">
      Vitrine de egressos de TI · IFES — Campus Serra · ensino, pesquisa e extensão.<br>
      Perfis a partir de fontes públicas (LinkedIn). Não exibimos remuneração individual — a análise de renda é agregada e anonimizada no <a href="index.html">relatório de impacto</a>.<br>
      <span class="opt">É egresso e quer corrigir ou remover seu perfil? Fale com a coordenação do curso.</span><br>
      <span style="opacity:.8">Gerado com apoio de Claude Code.</span>
    </p>

  </div>

  <!-- MODAL (DENTRO do .root p/ herdar as CSS vars do tema — fora dele o fundo fica transparente) -->
  <div class="ov" id="ov" role="dialog" aria-modal="true" aria-label="Jornada do egresso">
    <div class="modal" id="modal"></div>
  </div>
</div>

<script>
const PERFIS = {DATA_JSON};

function avatar(p, big){{
  const cls = big ? 'av' : 'av';
  return `<div class="${{cls}}" style="background:hsl(${{p.hue}} 52% 42%)">`+
    `<img src="img/egressos/${{p.id}}.jpg" alt="" loading="lazy" onerror="this.remove()">`+
    `<span>${{p.ini}}</span></div>`;
}}
const esc = s => (s==null?'':String(s)).replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));

// ---- filtros ----
const TRILHAS = [...new Set(PERFIS.map(p=>p.trilha))];
const REGIOES = ['Exterior','Espírito Santo','São Paulo','Remoto / Brasil'].filter(r=>PERFIS.some(p=>p.regiao===r));
const FILTERS = [{{k:'all',label:'Todos'}}]
  .concat(REGIOES.map(r=>({{k:'reg:'+r,label:r}})))
  .concat(TRILHAS.map(t=>({{k:'tr:'+t,label:t}})));
let active = 'all';
const fbox = document.getElementById('filters');
FILTERS.forEach(f=>{{
  const b=document.createElement('button');
  b.className='filt'; b.textContent=f.label; b.setAttribute('aria-pressed', f.k===active);
  b.onclick=()=>{{ active=f.k; [...fbox.children].forEach(c=>c.setAttribute('aria-pressed', c===b)); render(); }};
  fbox.appendChild(b);
}});

const q = document.getElementById('q');
q.addEventListener('input', render);

function matches(p){{
  if(active!=='all'){{
    if(active.startsWith('reg:') && p.regiao!==active.slice(4)) return false;
    if(active.startsWith('tr:') && p.trilha!==active.slice(3)) return false;
  }}
  const t = q.value.trim().toLowerCase();
  if(t){{
    const hay = (p.nome+' '+p.cargo+' '+p.empresa+' '+p.local+' '+p.trilha+' '+
      p.exp.map(e=>e.empresa+' '+e.cargo+' '+(e.skills||[]).join(' ')).join(' ')).toLowerCase();
    if(!hay.includes(t)) return false;
  }}
  return true;
}}

function card(p){{
  const intl = p.regiao==='Exterior';
  const loc = (p.flag?p.flag+' ':'') + esc(p.local_disp||p.local||p.regiao);
  return `<button class="pcard" onclick="openModal('${{p.id}}')" aria-label="Ver jornada de ${{esc(p.nome)}}">
    <div class="pc-top">${{avatar(p)}}
      <div class="pc-id">
        <div class="pc-nome">${{esc(p.nome)}}</div>
        <div class="pc-cargo">${{esc(p.cargo)}}<br><span class="pc-emp">${{esc(p.empresa)}}</span></div>
      </div>
    </div>
    <div class="pc-meta">
      <span class="tg loc ${{intl?'intl':''}}">${{loc}}</span>
      <span class="tg tr">${{esc(p.trilha)}}</span>
      <span class="tg">${{esc(p.nivel)}}</span>
    </div>
    <div class="pc-more">${{p.exp.length}} experiências · ver jornada →</div>
  </button>`;
}}

function render(){{
  const list = PERFIS.filter(matches);
  document.getElementById('grid').innerHTML = list.map(card).join('') ||
    '<p style="color:var(--muted);grid-column:1/-1">Nenhum egresso encontrado com esse filtro.</p>';
  document.getElementById('count').textContent =
    list.length + (list.length===1?' egresso':' egressos') + (active==='all'&&!q.value?'':` de ${{PERFIS.length}}`);
}}

// ---- modal ----
const ov = document.getElementById('ov');
function openModal(id){{
  const p = PERFIS.find(x=>x.id===id); if(!p) return;
  const tl = p.exp.map(e=>{{
    const when = [e.inicio, e.fim||'atual'].filter(Boolean).join(' — ') + (e.duracao?` · ${{esc(e.duracao)}}`:'');
    const sk = (e.skills||[]).map(s=>`<span class="sk">${{esc(s)}}</span>`).join('');
    const bolsa = e.bolsa?`<span class="bpill">🎓 bolsa${{e.fonte_bolsa?' '+esc(e.fonte_bolsa):''}}</span>`:'';
    return `<div class="tli ${{e.bolsa?'bolsa':''}}">
      <div class="tli-role">${{esc(e.cargo)}}${{bolsa}}</div>
      <div class="tli-emp">${{esc(e.empresa)}}${{e.tipo?` · ${{esc(e.tipo)}}`:''}}${{e.local?` · ${{esc(e.local)}}`:''}}</div>
      <div class="tli-when">${{when}}</div>
      ${{e.desc?`<p class="tli-desc">${{esc(e.desc)}}</p>`:''}}
      ${{sk?`<div class="tli-sk">${{sk}}</div>`:''}}
    </div>`;
  }}).join('');
  const link = p.url?`<a class="m-link" href="${{esc(p.url)}}" target="_blank" rel="noopener">🔗 Ver perfil no LinkedIn</a>`:'';
  document.getElementById('modal').innerHTML = `
    <div class="m-head">${{avatar(p,true)}}
      <div>
        <div class="m-nome">${{esc(p.nome)}}</div>
        <div class="m-cargo">${{esc(p.cargo)}} · <b>${{esc(p.empresa)}}</b></div>
        <div class="m-loc">${{p.flag?p.flag+' ':''}}${{esc(p.local_disp||p.local||p.regiao)}} · ${{esc(p.trilha)}}</div>
      </div>
      <button class="m-close" onclick="closeModal()" aria-label="Fechar">✕</button>
    </div>
    <div class="m-body">
      <p class="m-sec">Jornada — do IFES ao cargo de hoje</p>
      <div class="tl">${{tl}}</div>
      ${{link}}
    </div>`;
  ov.classList.add('open'); document.body.style.overflow='hidden';
}}
function closeModal(){{ ov.classList.remove('open'); document.body.style.overflow=''; }}
ov.addEventListener('click', e=>{{ if(e.target===ov) closeModal(); }});
document.addEventListener('keydown', e=>{{ if(e.key==='Escape') closeModal(); }});

render();
</script>

</body>
</html>
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print("wrote", OUT, f"({len(HTML)} bytes, {n_total} perfis, {n_empresas} empresas)")

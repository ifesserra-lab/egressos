"""Monta data/vitrine.json — o que a página "Onde estão os egressos" publica.

PRIVACIDADE: esta é uma das DUAS exceções nomeadas do princípio V da constituição. A página
mostra NOME, empresa e jornada — dado de nível LinkedIn, que a própria pessoa publica —, por
decisão explícita da coordenação. O que a torna aceitável não é a autorização: é a AUSÊNCIA DE
RENDA. Nenhum valor monetário entra neste arquivo, e é isso que `test_perfis_e_renda.py` e
`egressos_core.vitrine` verificam, cada um de um lado.

Substitui o antigo `gen_vitrine.py`, de 1242 linhas: as 568 primeiras calculavam, e as 674
seguintes montavam a página inteira numa f-string — 240 KB de HTML com 191 KB de JavaScript
embutido, sendo que 176 KB disso eram os próprios dados, colados dentro de `const PERFIS` e
`const MAPA`. Aqui as 568 viram dado, e a página em Astro o consome.

A classificação — região, trilha, nível, rótulo de lugar — saiu daqui para
`egressos_core.vitrine`, com teste. Eram cento e vinte linhas de expressão regular chamadas de
dentro da construção da string, onde a decisão e a serialização eram o mesmo trecho de código.
O que ficou aqui é o que é tabela de consulta, não decisão: o gazetteer de cidades e as sedes.
"""
import json
import os
import re

from egressos_core import vitrine
from egressos_core.paths import ROOT as _ROOT
from egressos_core.text import norm

ROOT = str(_ROOT)
DATA = os.path.join(ROOT, "data")
DESTINO = os.path.join(DATA, "vitrine.json")

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def load_opt(p):
    try:
        return load(p)
    except FileNotFoundError:
        return {}

alunos = load(os.path.join(ROOT, "alunos.json"))
if isinstance(alunos, dict):
    alunos = alunos.get("alunos") or list(alunos.values())[0]
analise = load(os.path.join(DATA, "analise.json"))
porte   = load(os.path.join(DATA, "empresas_porte.json"))
mapa_base_json = load(os.path.join(DATA, "mapa_mundi.json"))
aliases_raw = load_opt(os.path.join(DATA, "empresas_aliases.json"))
li_urls     = load_opt(os.path.join(DATA, "empresas_linkedin_urls.json"))

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

# ---------- monta perfis ----------
perfis = []
for x in alunos:
    nome  = x.get("nome") or ""
    cargo = x.get("cargo_atual") or ""
    empresa = x.get("empresa_atual") or ""
    local = x.get("local_atual") or ""
    area  = x.get("area_atual") or ""
    reg, pais, flag = vitrine.regiao_de(local)
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
        "ini": vitrine.monograma(nome),
        "hue": vitrine.tom(x.get("id") or nome),
        "cargo": cargo,
        "empresa": empresa,
        "local": local,
        "local_disp": vitrine.rotulo_do_lugar(local, regiao=reg, pais=pais),
        "regiao": reg,
        "pais": pais,
        "flag": flag,
        "trilha": vitrine.trilha_de(area, cargo),
        "nivel": vitrine.nivel_de(cargo),
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

# ---------- MAPA-MÚNDI: gazetteer + série ano a ano ----------
# Cada lugar citado nas experiências vira um ponto (lat, lon). A ordem importa:
# o primeiro padrão que casar vence, então o exterior e as cidades vêm antes dos
# estados, e o genérico ("Brasil", "Remoto") fica por último.
# grupo = como o lugar é agregado no zoom do Brasil (as 4 cidades da Grande Vitória
# viram um ponto só, senão viram um borrão de 1 px).
GRUPOS = {
    "Espírito Santo": (-19.75, -40.34), "São Paulo": (-22.50, -48.00),
    "Rio de Janeiro": (-22.30, -42.60), "Santa Catarina": (-27.30, -50.30),
    "Paraná": (-24.70, -51.50), "Distrito Federal": (-15.79, -47.88),
    "Minas Gerais": (-18.60, -44.50), "Bahia": (-12.60, -41.70),
    "Pernambuco": (-8.40, -37.90), "Ceará": (-5.20, -39.50),
    "Rio Grande do Sul": (-30.00, -53.20),
}
GAZ = [
    # --- exterior ---
    (r"london|londres",                     "Londres",           51.51,  -0.13, "🇬🇧", "Reino Unido"),
    (r"lisbo[an]|lisbon",                   "Lisboa",            38.72,  -9.14, "🇵🇹", "Portugal"),
    (r"oeiras",                             "Oeiras",            38.70,  -9.31, "🇵🇹", "Portugal"),
    (r"porto\b",                            "Porto",             41.15,  -8.61, "🇵🇹", "Portugal"),
    (r"portugal",                           "Portugal",          39.40,  -8.22, "🇵🇹", "Portugal"),
    (r"berlim|berlin",                      "Berlim",            52.52,  13.40, "🇩🇪", "Alemanha"),
    (r"alemanha|germany",                   "Alemanha",          51.17,  10.45, "🇩🇪", "Alemanha"),
    (r"estocolmo|stockholm",                "Estocolmo",         59.33,  18.07, "🇸🇪", "Suécia"),
    (r"su[ée]cia|sweden",                   "Suécia",            60.13,  18.64, "🇸🇪", "Suécia"),
    (r"santiago",                           "Santiago",         -33.45, -70.67, "🇨🇱", "Chile"),
    (r"chile",                              "Chile",            -35.68, -71.54, "🇨🇱", "Chile"),
    (r"armonk",                             "Armonk, NY",        41.13, -73.71, "🇺🇸", "Estados Unidos"),
    (r"new york|nova york|\bnyc\b|brooklyn|manhattan", "Nova York",  40.71, -74.01, "🇺🇸", "Estados Unidos"),
    (r"cambridge, ?ma|boston",              "Boston",            42.36, -71.06, "🇺🇸", "Estados Unidos"),
    (r"atlanta",                            "Atlanta",           33.75, -84.39, "🇺🇸", "Estados Unidos"),
    (r"san francisco|bay area|palo alto|mountain view", "São Francisco", 37.77, -122.42, "🇺🇸", "Estados Unidos"),
    (r"seattle|redmond",                    "Seattle",           47.61,-122.33, "🇺🇸", "Estados Unidos"),
    (r"austin",                             "Austin",            30.27,  -97.74, "🇺🇸", "Estados Unidos"),
    (r"chicago",                            "Chicago",           41.88,  -87.63, "🇺🇸", "Estados Unidos"),
    (r"florida",                            "Flórida (EUA)",     27.99, -81.76, "🇺🇸", "Estados Unidos"),
    (r"united states|estados unidos|\beua\b|\busa\b", "Estados Unidos", 39.83, -98.58, "🇺🇸", "Estados Unidos"),
    (r"madrid",                             "Madri",             40.42,  -3.70, "🇪🇸", "Espanha"),
    (r"barcelona",                          "Barcelona",         41.39,   2.17, "🇪🇸", "Espanha"),
    (r"espanha|spain",                      "Espanha",           40.46,  -3.75, "🇪🇸", "Espanha"),
    (r"irlanda|ireland|dublin",             "Dublin",            53.35,  -6.26, "🇮🇪", "Irlanda"),
    (r"canada|canad[áa]|toronto",           "Canadá",            56.13,-106.35, "🇨🇦", "Canadá"),
    (r"argentina|buenos aires",             "Buenos Aires",     -34.60, -58.38, "🇦🇷", "Argentina"),
    (r"m[ée]xico",                          "México",            23.63,-102.55, "🇲🇽", "México"),
    (r"israel|tel aviv",                    "Tel Aviv",          32.09,  34.78, "🇮🇱", "Israel"),
    (r"guatemala",                          "Guatemala",         14.63,  -90.51, "🇬🇹", "Guatemala"),
    # --- Espírito Santo (a origem do coorte) ---
    (r"vit[óo]ria",                         "Vitória, ES",      -20.32, -40.31, "", "Espírito Santo"),
    (r"vila velha",                         "Vila Velha, ES",   -20.33, -40.29, "", "Espírito Santo"),
    (r"cariacica",                          "Cariacica, ES",    -20.26, -40.42, "", "Espírito Santo"),
    (r"\bserra\b",                          "Serra, ES",        -20.12, -40.31, "", "Espírito Santo"),
    (r"guarapari",                          "Guarapari, ES",    -20.67, -40.50, "", "Espírito Santo"),
    (r"linhares",                           "Linhares, ES",     -19.39, -40.07, "", "Espírito Santo"),
    (r"colatina",                           "Colatina, ES",     -19.54, -40.63, "", "Espírito Santo"),
    (r"viana",                              "Viana, ES",        -20.39, -40.49, "", "Espírito Santo"),
    (r"esp[íi]rito santo|\bes\b",           "Espírito Santo",   -19.75, -40.34, "", "Espírito Santo"),
    # --- demais capitais/estados ---
    (r"s[ãa]o paulo|\bsp\b",                "São Paulo",        -23.55, -46.63, "", "São Paulo"),
    (r"rio de janeiro|\brj\b",              "Rio de Janeiro",   -22.91, -43.17, "", "Rio de Janeiro"),
    (r"florian[óo]polis|santa catarina|\bsc\b", "Florianópolis", -27.60, -48.55, "", "Santa Catarina"),
    (r"curitiba|paran[áa]|\bpr\b",           "Curitiba",         -25.43, -49.27, "", "Paraná"),
    (r"bras[íi]lia|distrito federal|federal district|\bdf\b", "Brasília", -15.79, -47.88, "", "Distrito Federal"),
    (r"belo horizonte|minas gerais|\bmg\b",  "Belo Horizonte",   -19.92, -43.94, "", "Minas Gerais"),
    (r"salvador|bahia|\bba\b",               "Salvador",         -12.97, -38.50, "", "Bahia"),
    (r"recife|pernambuco|\bpe\b",            "Recife",            -8.05, -34.88, "", "Pernambuco"),
    (r"fortaleza|cear[áa]|\bce\b",           "Fortaleza",         -3.73, -38.53, "", "Ceará"),
    (r"porto alegre|rio grande do sul|\brs\b","Porto Alegre",    -30.03, -51.23, "", "Rio Grande do Sul"),
    (r"campinas",                           "Campinas",         -22.91, -47.06, "", "São Paulo"),
]
SEM_LUGAR = ("remoto", "remote", "brasil", "brazil", "nao especificado", "")

# Sedes que a coleta do LinkedIn não trouxe e que são informação pública conhecida.
# Só entram aqui empresas cuja sede dá para afirmar sem chutar.
# Sede MUNDIAL, conferida na fonte primária (formulários da SEC / site oficial):
#   MongoDB, Inc. — 1633 Broadway, 38th Floor, New York, NY 10019
#   IBM (International Business Machines Corp.) — 1 New Orchard Road, Armonk, NY 10504
SEDE_MANUAL = {
    "mongodb": "New York, New York, United States",
    "ibm": "Armonk, New York, United States",
}

def geo_de(local):
    """Devolve (rótulo, lat, lon, bandeira) ou None quando o local não identifica cidade
    — 'Remoto', 'Brasil' e 'Não especificado' não viram ponto no mapa de propósito:
    colocá-los no centro geográfico do país diria algo que o dado não diz."""
    n = norm(local or "")
    if n.strip() in SEM_LUGAR:
        return None
    for pat, rot, lat, lon, flag, grupo in GAZ:
        if re.search(pat, n):
            return (rot, lat, lon, flag, grupo)
    return None

def _empresa_chave(nome):
    return norm(re.sub(r"\s*\(.*?\)", "", nome or "").strip())

_SEDES = {_empresa_chave(k): v.get("hq_local") for k, v in porte.items() if v.get("hq_local")}
_SEDES.update(SEDE_MANUAL)

def geo_da_experiencia(exp, aluno):
    """Onde essa experiência acontecia, em ordem de confiança:
       1. o local declarado na própria experiência;
       2. quando é 'Remoto'/vazio, a SEDE DA EMPRESA (é de onde o trabalho vem);
       3. em último caso, a cidade que o egresso declara morar hoje.
    Devolve (geo, base) — `base` diz qual das três respondeu, e vai para o tooltip."""
    g = geo_de(exp.get("local"))
    if g:
        return g, "local"
    g = geo_de(_SEDES.get(_empresa_chave(exp.get("empresa"))))
    if g:
        return g, "sede"
    g = geo_de(aluno.get("local_atual"))
    if g:
        return g, "egresso"
    return None, None


def _ym(s):
    return (int(s[:4]), int(s[5:7])) if s and len(s) >= 7 else (None, None)

ANO_MAP_FIM = 2026
_anos_ini = [int(a["inicio_carreira_dev"][:4]) for a in alunos if a.get("inicio_carreira_dev")]
ANO_MAP_INI = max(min(_anos_ini), 2012) if _anos_ini else 2012

# lugares (id estável) e, para cada ano, quantas pessoas estavam em cada lugar
lugares, por_ano, bases, sem_lugar_ano = {}, {}, {}, {}
for a in alunos:
    for Y in range(ANO_MAP_INI, ANO_MAP_FIM + 1):
        ativas = [e for e in a.get("experiencias", [])
                  if _ym(e.get("inicio"))[0] and _ym(e["inicio"])[0] <= Y
                  and (e.get("fim") is None or _ym(e["fim"])[0] >= Y)]
        if not ativas:
            continue
        # a experiência mais recente que tenha lugar identificável
        g = base = None
        for e in sorted(ativas, key=lambda e: e["inicio"], reverse=True):
            g, base = geo_da_experiencia(e, a)
            if g:
                break
        if not g:
            sem_lugar_ano.setdefault(Y, 0)
            sem_lugar_ano[Y] += 1
            continue
        bases[base] = bases.get(base, 0) + 1
        rot, lat, lon, flag, grupo = g
        glat, glon = GRUPOS.get(grupo, (lat, lon))
        lugares.setdefault(rot, {"rotulo": rot, "lat": lat, "lon": lon, "flag": flag,
                                 "exterior": bool(flag), "grupo": grupo,
                                 "glat": glat, "glon": glon})
        por_ano.setdefault(Y, {}).setdefault(rot, 0)
        por_ano[Y][rot] += 1

MAPA = {
    "viewBox": mapa_base_json["viewBox"], "lat_range": mapa_base_json["lat_range"],
    "paths": mapa_base_json["paths"], "fonte": mapa_base_json["fonte"],
    "origem": {"rotulo": "IFES — Campus Serra", "lat": -20.12, "lon": -40.31},
    "lugares": list(lugares.values()),
    "anos": [{"ano": Y, "pontos": por_ano.get(Y, {}),
              "total": sum(por_ano.get(Y, {}).values()),
              "sem": sem_lugar_ano.get(Y, 0),
              "exterior": sum(n for r, n in por_ano.get(Y, {}).items() if lugares[r]["exterior"])}
             for Y in range(ANO_MAP_INI, ANO_MAP_FIM + 1)],
}
_sem_ponto = sem_lugar_ano.get(ANO_MAP_FIM, 0)
_base_pct = {k: round(100 * v / max(sum(bases.values()), 1)) for k, v in bases.items()}

# países no exterior (distintos, com flag)
paises_ext = []
for p in perfis:
    if p["regiao"]=="Exterior" and p["pais"] not in [x[0] for x in paises_ext]:
        paises_ext.append((p["pais"], p["flag"]))

# ---------- projeção ----------
import urllib.parse as _up


def busca_no_linkedin(nome):
    """Busca de EMPRESA no LinkedIn, para quando não há a página canônica resolvida.

    Sem scraping e sem intermediário: abre a busca no navegador de quem clica, já logado.
    """
    return f"https://www.linkedin.com/search/results/companies/?keywords={_up.quote(nome)}"


def _ordem_de_tamanho(faixa):
    """A faixa de funcionários como número, para ordenar. "1k–5k" -> 1000."""
    if not faixa:
        return -1
    tok = faixa.lower().replace("\u2013", "-").split("-")[0].strip()
    tok = tok.replace("+", "").replace("k", "000")
    digitos = re.sub(r"\D", "", tok)
    return int(digitos) if digitos else 0


def _empresa_publicavel(e):
    return {
        "nome": e["nome"],
        "origem": e["origem"] or None,
        "porte": e["porte"] or None,
        "internacional": norm(e["origem"]).startswith("intern"),
        "url": e.get("url") or busca_no_linkedin(e["nome"]),
        "url_canonica": bool(e.get("url")),
        "vagas_url": (e["url"].rstrip("/") + "/jobs/") if e.get("url") else None,
        "tamanho": e.get("size"),
        "sede": e.get("hq"),
        "setor": e.get("industry"),
        "contratando": bool(e.get("hiring")),
    }


empresas = [_empresa_publicavel(e) for e in empresas_cards]
verificadas = sorted([e for e in empresas if e["tamanho"]],
                     key=lambda e: (-_ordem_de_tamanho(e["tamanho"]), norm(e["nome"])))
contratando = sorted([e for e in empresas if e["contratando"]],
                     key=lambda e: (0 if e["internacional"] else 1, norm(e["nome"])))

#: A jornada publicada. Construída campo por campo, e não copiada do cadastro: campo novo no
#: cadastro fica de fora até que alguém decida o contrário, que é a direção certa para o padrão
#: de uma vitrine nomeada. Mesma razão da forma de `vitrine.perfil_publicavel`.
def _jornada(x):
    return [
        {
            "cargo": e.get("cargo") or "",
            "empresa": e.get("empresa") or "",
            "tipo": e.get("tipo") or "",
            "de": e.get("inicio") or "",
            "ate": e.get("fim"),
            "duracao": e.get("duracao") or "",
            "local": e.get("local") or "",
            "descricao": (e.get("descricao") or "")[:280],
            "skills": (e.get("skills") or [])[:8],
            "bolsa": bool(e.get("fonte_bolsa") or e.get("projeto_fapes")
                          or e.get("bolsa_valor_mensal")),
            "fonte_bolsa": e.get("fonte_bolsa") or "",
        }
        for e in x.get("experiencias", [])
    ]


_por_nome = {a.get("nome"): a for a in alunos}
# O rótulo (A–AX) vem do catálogo `egressos_perfil`, que já o mantém, e o join é por NOME.
# Não pelo `id`: o slug do cadastro é identificador e não entra em arquivo publicável — e o
# rótulo é justamente o que permite cruzar esta página com as anonimizadas sem publicá-lo.
_rotulo_por_nome = {e["nome"]: e["label"]
                    for e in load(os.path.join(DATA, "egressos_perfil.json"))["egressos"]}
faltam_rotulo = [p["nome"] for p in perfis if p["nome"] not in _rotulo_por_nome]
if faltam_rotulo:
    raise SystemExit(
        f"{len(faltam_rotulo)} perfil(is) sem rótulo em egressos_perfil.json: {faltam_rotulo[:5]}. "
        "Rode pipeline/gen_perfis.py antes — sem rótulo a vitrine não cruza com as páginas "
        "anonimizadas, e publicar `null` esconderia isso."
    )

publicaveis = []
for p in perfis:
    bruto = _por_nome.get(p["nome"], {})
    saida = vitrine.perfil_publicavel({**bruto, "label": _rotulo_por_nome[p["nome"]]})
    # O `perfil_publicavel` não devolve jornada de propósito — ele é o guarda do que pode sair
    # sem decisão. A jornada é decisão desta página, e entra aqui, explícita.
    saida["jornada"] = _jornada(bruto)
    saida["porte_do_empregador"] = p["porte"] or None
    saida["setor_do_empregador"] = p["setor"] or None
    saida["origem_do_empregador"] = p["origem"] or None
    saida["inicio_carreira"] = p["inicio"]
    publicaveis.append(saida)

trilhas = sorted({p["trilha"] for p in publicaveis})
# `regioes` já é das EMPRESAS, lá em cima, vindo do analise.json. Sombrear aqui deixaria o
# dataset com a lista errada num dos dois lugares, e o erro seria silencioso: as duas são
# listas de nome de região.
regioes_dos_perfis = [r for r in ("Exterior", "Espírito Santo", "São Paulo", "Remoto / Brasil")
                      if any(p["regiao"] == r for p in publicaveis)]

saida = {
    "titulo": "Onde estão os egressos",
    "excecao": (
        "Página NOMEADA — uma das duas exceções autorizadas ao anonimato, por decisão da "
        "coordenação. Nome, cargo, empresa e cidade são dado de nível LinkedIn, que a própria "
        "pessoa publica. NÃO há renda por pessoa aqui, em nenhuma profundidade: a estimativa "
        "vive atrelada a cargo, em renda_por_senioridade. Egressos podem pedir remoção."
    ),
    "hoje": ANO_MAP_FIM,
    "indicadores": {
        "n": n_total,
        "exterior_hoje": n_exterior,
        "ja_atuaram_fora": n_ja_intl,
        "empresas": n_empresas,
        "bigtech": n_bigtech,
        "lideranca": n_lideranca,
        "da_extensao": n_extensao,
        "da_pesquisa": n_pesquisa,
    },
    "perfis": publicaveis,
    "trilhas": trilhas,
    "regioes": regioes_dos_perfis,
    "paises_no_exterior": [{"pais": n, "bandeira": f} for n, f in paises_ext],
    "mapa": MAPA,
    "mapa_confianca": _base_pct,
    "mapa_sem_ponto": _sem_ponto,
    "empresas": empresas,
    "empresas_verificadas": verificadas,
    "contratando": contratando,
    "porte": [{"porte": r["porte"], "n": r["n"]} for r in porte_agg],
    "setor": [{"setor": r["setor"], "n": r["n"]} for r in setores],
    "regiao_das_empresas": [{"regiao": r["regiao"], "n": r["n"]} for r in regioes],
    "fontes": {
        "perfis": "LinkedIn público dos egressos, curado",
        "empresas": "dado público de empresa (LinkedIn), coletado via browser-use",
        "mapa": mapa_base_json["fonte"],
        "agregados": "data/analise.json",
    },
}

if __name__ == "__main__":
    with open(DESTINO, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print(f"  perfis: {n_total} nomeados · {n_exterior} no exterior hoje · "
          f"{len(trilhas)} trilhas · {len(regioes_dos_perfis)} regiões")
    print(f"  empresas: {n_empresas} distintas · {len(verificadas)} com tamanho verificado · "
          f"{len(contratando)} contratando")
    print(f"  mapa: {len(MAPA['lugares'])} lugares · {len(MAPA['anos'])} anos "
          f"({MAPA['anos'][0]['ano']}–{MAPA['anos'][-1]['ano']}) · "
          f"{_sem_ponto} sem ponto em {ANO_MAP_FIM}")
    print(f"OK: {os.path.relpath(DESTINO, ROOT)}")

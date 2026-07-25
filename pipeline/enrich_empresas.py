"""
Enriquece dados de EMPRESA via browser-use (Chrome logado no LinkedIn) — passo 2.

Reusa o esqueleto de busca_egressos.py: Browser.from_system_chrome, login-gate,
pacing 25-55s, Agent(use_vision=False), navegar-direto-depois-Agent.
Só lê company pages (dado PÚBLICO de empresa) — nenhum nome de egresso é usado aqui.

Para cada empresa canônica (empresas_aliases.json): abre a busca de EMPRESAS do LinkedIn,
entra na company page certa, lê a aba "Sobre" (headcount, sede, setor, site, especialidades)
e a aba de vagas (contratando? política remoto). Faz MERGE em empresas_porte.json e grava
o slug em empresas_linkedin_urls.json (a vitrine passa a linkar a URL verificada).

Uso:  (Chrome logado no LinkedIn)
  .venv/bin/python data/enrich_empresas.py --limit 2      # teste
  .venv/bin/python data/enrich_empresas.py                # empregadores ATUAIS
  .venv/bin/python data/enrich_empresas.py --all          # todas
"""
import asyncio, random, json, re, sys, pathlib, datetime, glob, shutil, tempfile, time, os
from urllib.parse import quote
from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatMistral

def sweep_browseruse_temp(older_than=90):
    """browser-use copia o profile inteiro (~115MB) por sessão e NÃO limpa no kill().
    Remove as cópias órfãs (não tocadas há >older_than s) pra não estourar o disco."""
    now = time.time(); freed = 0
    for d in glob.glob(os.path.join(tempfile.gettempdir(), "browser-use-user-data-dir-*")):
        try:
            if now - os.path.getmtime(d) > older_than:
                shutil.rmtree(d, ignore_errors=True); freed += 1
        except OSError:
            pass
    if freed:
        print(f"  [limpeza] removidos {freed} profiles temporários órfãos")

BASE = pathlib.Path("/caminho/para/salario")
load_dotenv(str(BASE / ".env"))

ALIASES = BASE / "data" / "empresas_aliases.json"
PORTE   = BASE / "data" / "empresas_porte.json"
URLS    = BASE / "data" / "empresas_linkedin_urls.json"
DATA    = BASE / "data" / "empresas_linkedin_data.json"   # bruto por empresa
LOGIN_MARK = ("login", "authwall", "checkpoint", "signup", "uas/login")

def search_url(nome):
    return f"https://www.linkedin.com/search/results/companies/?keywords={quote(nome)}"

# slugs corretos p/ nomes ambíguos/genéricos (senão o chute pega a empresa ERRADA)
SLUG_OVERRIDE = {
    "Neon": "neon-pagamentos",              # fintech BR (não a advertising UK)
    "Mercado Livre": "mercadolibre",
    "MongoDB": "mongodb",
    "BTG Pactual": "btgpactual",
    "Pottencial": "pottencial-seguradora",
    "Coru": "coru-brasil",
    "velv": "wearevelv",
}

import unicodedata
def slugify(nome):
    """chute do slug LinkedIn a partir do nome (barato: evita o fluxo de busca)."""
    s = "".join(c for c in unicodedata.normalize("NFD", nome) if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[/&.,()']", " ", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s.strip("-")

def is_empty(parsed):
    """True se o parse não trouxe nenhum campo útil (slug errado / About vazia)."""
    if not parsed:
        return True
    keys = ("headcount_linkedin", "hq_local", "industry_linkedin", "website")
    return not any(parsed.get(k) for k in keys)

def task(nome):
    # sem URL literal no texto (browser-use navega pra 1ª URL do prompt)
    return f"""
Você JÁ está na página de resultados de EMPRESAS do LinkedIn para "{nome}". NÃO use a barra de busca,
NÃO use DuckDuckGo/Google, NÃO envie mensagens/convites.

PASSO 1 — Escolher a empresa certa: clique no resultado cujo nome bate com "{nome}". Se houver
vários, prefira o de mesmo país/UF dos egressos capixabas (Espírito Santo/Brasil) quando fizer
sentido, senão a empresa oficial de maior porte com esse nome. Abra a página da empresa.

PASSO 2 — Abrir a aba "Sobre": o endereço atual tem formato .../company/SLUG/. Use a ação
`navigate` (go_to_url) para ir a .../company/SLUG/about/ (essa página tem todos os campos).

PASSO 3 — Extrair (ação `extract`, NÃO role manualmente) da aba Sobre:
- nome oficial (cabeçalho)
- Industry / Setor
- Company size / tamanho ("X employees" e a faixa, ex.: "51-200 employees")
- Headquarters / Sede (cidade, UF, país)
- Website / site oficial
- Founded / fundação (ano), se houver
- Specialties / especialidades, se houver

PASSO 4 — Vagas: use `navigate` para .../company/SLUG/jobs/ e diga se há vagas abertas
(sim/não) e, se der pra ver, a política predominante (Remoto/Híbrido/Presencial).

No `done`, responda EXATAMENTE neste formato (uma linha cada; use "-" se não achar):
Nome oficial: <...>
Slug: company/SLUG
Industry: <...>
Company size: <faixa e/ou número, ex.: 51-200 employees>
Headquarters: <cidade, UF, país>
Website: <url>
Founded: <ano>
Specialties: <lista curta>
Contratando: sim|não
Politica remoto: Remoto|Híbrido|Presencial|não-declarado
Se não encontrar a empresa, diga "EMPRESA NAO ENCONTRADA".
"""

FIELDS = {
    "nome_oficial": r"Nome oficial:\s*(.+)",
    "slug_raw":     r"Slug:\s*(.+)",
    "industry_linkedin": r"Industry:\s*(.+)",
    "headcount_linkedin": r"Company size:\s*(.+)",
    "hq_local":     r"Headquarters:\s*(.+)",
    "website":      r"Website:\s*(.+)",
    "founded":      r"Founded:\s*(.+)",
    "specialties":  r"Specialties:\s*(.+)",
    "contratando_raw": r"Contratando:\s*(.+)",
    "politica_remoto": r"Politica remoto:\s*(.+)",
}

def parse(res):
    if not res or "EMPRESA NAO ENCONTRADA" in res.upper():
        return None
    out = {}
    for k, pat in FIELDS.items():
        m = re.search(pat, res, re.IGNORECASE)
        v = (m.group(1).strip() if m else "")
        if v in ("-", "—", "n/a", "N/A", "não-declarado", ""):
            v = None
        out[k] = v
    # slug
    slug = None
    if out.get("slug_raw"):
        ms = re.search(r"company/([A-Za-z0-9\-_%\.]+)", out["slug_raw"])
        slug = ms.group(1).strip("/").lower() if ms else None
    out["slug"] = slug
    out.pop("slug_raw", None)
    # contratando -> bool
    c = (out.pop("contratando_raw", None) or "").lower()
    out["contratando"] = True if c.startswith("s") or "sim" in c else (False if "n" in c else None)
    return out

def task_about(url_slug):
    # já estamos NA aba Sobre da empresa — só extrair (sem busca)
    return f"""
Você JÁ está na aba "Sobre" (About) de uma empresa no LinkedIn ({url_slug}). NÃO use a barra de busca,
NÃO envie mensagens. Use a ação `extract` para ler a página inteira e coletar os campos abaixo.
Se algum não existir, use "-". Depois use `navigate` para a aba de vagas (.../jobs/) e diga se há
vagas abertas.

No `done`, responda EXATAMENTE neste formato:
Nome oficial: <...>
Slug: {url_slug}
Industry: <...>
Company size: <faixa e/ou número, ex.: 51-200 employees>
Headquarters: <cidade, UF, país>
Website: <url>
Founded: <ano>
Specialties: <lista curta>
Contratando: sim|não
Politica remoto: Remoto|Híbrido|Presencial|não-declarado
"""

async def run_url(url, pdir, llm):
    """Extrai direto de uma company About URL (ex.: .../company/king/about/)."""
    ms = re.search(r"company/([A-Za-z0-9\-_%\.]+)", url)
    slug = ms.group(1).strip("/").lower() if ms else url
    about = f"https://www.linkedin.com/company/{slug}/about/"
    browser = Browser.from_system_chrome(profile_directory=pdir)
    try:
        await browser.start()
        await browser.navigate_to(about)
        for _ in range(60):
            ok, u = await logged_in(browser)
            if ok:
                break
            print(f"  [login] aguardando login manual... {u}")
            await asyncio.sleep(5)
        else:
            return slug, "(bloqueado: login/checkpoint)"
        await browser.navigate_to(about)
        agent = Agent(task=task_about(f"company/{slug}"), llm=llm, browser=browser, use_vision=False)
        hist = await agent.run(max_steps=14)   # About = poucos passos; poupa cota Mistral
        return slug, (hist.final_result() or "(sem resultado)")
    except Exception as e:
        return slug, f"(ERRO: {type(e).__name__}: {str(e)[:200]})"
    finally:
        try:
            await browser.kill()
        except Exception:
            pass

async def logged_in(browser):
    try:
        url = await browser.get_current_page_url()
    except Exception:
        return False, ""
    return (bool(url) and not any(x in url for x in LOGIN_MARK)), url

async def run_one(nome, pdir, llm):
    browser = Browser.from_system_chrome(profile_directory=pdir)
    try:
        await browser.start()
        await browser.navigate_to(search_url(nome))
        for _ in range(60):
            ok, url = await logged_in(browser)
            if ok:
                break
            print(f"  [login] aguardando login manual... {url}")
            await asyncio.sleep(5)
        else:
            return "(bloqueado: login/checkpoint)"
        await browser.navigate_to(search_url(nome))
        agent = Agent(task=task(nome), llm=llm, browser=browser, use_vision=False)
        hist = await agent.run(max_steps=30)
        return hist.final_result() or "(sem resultado)"
    except Exception as e:
        return f"(ERRO: {type(e).__name__}: {str(e)[:200]})"
    finally:
        try:
            await browser.kill()
        except Exception:
            pass

def load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default

def merge_outputs(nome, parsed):
    hoje = datetime.date.today().isoformat()
    # 1) dados brutos
    data = load(DATA, {})
    data[nome] = {**parsed, "verificado_em": hoje}
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    # 2) urls (vitrine linka URL verificada)
    if parsed.get("slug"):
        urls = load(URLS, {})
        urls[nome] = {"url": f"https://www.linkedin.com/company/{parsed['slug']}/",
                      "slug": parsed["slug"], "confianca": "alta", "via": "browser-use"}
        URLS.write_text(json.dumps(urls, ensure_ascii=False, indent=1), encoding="utf-8")
    # 3) merge aditivo em empresas_porte.json (não sobrescreve estimativa; marca fonte)
    porte = load(PORTE, {})
    rec = porte.get(nome, {"empresa": nome})
    for campo in ("nome_oficial","headcount_linkedin","hq_local","industry_linkedin",
                  "website","founded","specialties","contratando","politica_remoto","slug"):
        if parsed.get(campo) is not None:
            rec[campo] = parsed[campo]
    rec.setdefault("fonte", "linkedin")
    rec["verificado_em"] = hoje
    porte[nome] = rec
    PORTE.write_text(json.dumps(porte, ensure_ascii=False, indent=1), encoding="utf-8")

async def main():
    profiles = Browser.list_chrome_profiles()
    pdir = profiles[0]["directory"] if profiles else None
    llm = ChatMistral(model="mistral-large-latest", timeout=180, max_retries=5)

    # modo direto: --url <company about url>
    if "--url" in sys.argv:
        url = sys.argv[sys.argv.index("--url")+1]
        slug, res = await run_url(url, pdir, llm)
        print("\n--- RESULTADO BRUTO ---\n" + res + "\n-----------------------")
        parsed = parse(res)
        if parsed:
            nome = parsed.get("nome_oficial") or slug
            merge_outputs(nome, parsed)
            print(f"\n✓ {nome}: size={parsed.get('headcount_linkedin')} | hq={parsed.get('hq_local')} | "
                  f"industry={parsed.get('industry_linkedin')} | site={parsed.get('website')} | slug={parsed.get('slug')}")
        else:
            print("✗ não parseável")
        return

    only_all = "--all" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else None

    aliases = load(ALIASES, {})
    done = load(DATA, {})
    alvos = [k for k, v in aliases.items() if (only_all or v.get("atual")) and k not in done]
    if limit:
        alvos = alvos[:limit]

    print(f"enriquecendo {len(alvos)} empresas (já feitas: {len(done)})…")
    for i, nome in enumerate(alvos, 1):
        print(f"\n===== [{i}/{len(alvos)}] {nome} =====")
        # 1) tenta slug-direto (barato em chamadas Mistral) — override > chute
        slug = SLUG_OVERRIDE.get(nome) or slugify(nome)
        _, res = await run_url(f"company/{slug}/about/", pdir, llm)
        parsed = parse(res)
        via = f"slug-direto ({slug})"
        # 2) fallback: fluxo de busca (mais caro) só se o chute falhou
        if is_empty(parsed):
            print(f"  slug '{slug}' vazio/errado -> fallback busca")
            await asyncio.sleep(random.uniform(20, 40))   # respira o rate-limit Mistral
            res = await run_one(nome, pdir, llm)
            parsed = parse(res)
            via = "busca"
        print(res[:400])
        if not is_empty(parsed):
            merge_outputs(nome, parsed)
            print(f"  ✓ [{via}] size={parsed.get('headcount_linkedin')} | hq={parsed.get('hq_local')} | slug={parsed.get('slug')}")
        else:
            d = load(DATA, {}); d[nome] = {"nao_encontrado": True,
                    "verificado_em": datetime.date.today().isoformat()}
            DATA.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  ✗ não encontrada")
        sweep_browseruse_temp()   # apaga a cópia de profile (~115MB) que o browser-use deixou
        if i < len(alvos):
            pausa = random.uniform(45, 75)   # pacing maior: alivia rate-limit Mistral + LinkedIn
            print(f"  [pacing] {pausa:.0f}s…")
            await asyncio.sleep(pausa)
    print(f"\nfeito. brutos: {DATA}  | merge: {PORTE}  | urls: {URLS}")

if __name__ == "__main__":
    asyncio.run(main())

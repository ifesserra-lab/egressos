#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Passo 1 — resolve a URL canônica da company page no LinkedIn, SEM logar no LinkedIn.

Usa dork em mecanismo de busca (DuckDuckGo HTML, sem chave/sem login):
    site:linkedin.com/company "<nome>"
Pega o primeiro resultado linkedin.com/company/<slug>.

Entrada: data/empresas_aliases.json  (do passo 0)
Saída:   data/empresas_linkedin_urls.json = { canonico: {url, slug, confianca, via, query} }

Idempotente: pula quem já resolveu. Pacing educado com o buscador (não é o LinkedIn).
Uso:
    .venv/bin/python data/resolve_company_urls.py            # só empregadores ATUAIS
    .venv/bin/python data/resolve_company_urls.py --all      # todas as 206
    .venv/bin/python data/resolve_company_urls.py --limit 5  # teste
"""
import json
import os
import random
import re
import sys
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))   # pipeline/
DATA = os.path.join(os.path.dirname(HERE), "data")   # salario/data/
ALIASES = os.path.join(DATA, "empresas_aliases.json")
OUT     = os.path.join(DATA, "empresas_linkedin_urls.json")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
ENDPOINTS = ["https://html.duckduckgo.com/html/", "https://lite.duckduckgo.com/lite/"]

# slugs institucionais do próprio LinkedIn que não são empresa
SLUG_BLOCK = {"setup", "admin", "search", "signup", "login", "school", "showcase"}

def decode_ddg(href):
    """DDG embrulha o link em /l/?uddg=<url-encoded>. Devolve a URL real."""
    if "uddg=" in href:
        q = urllib.parse.urlparse(href).query
        u = urllib.parse.parse_qs(q).get("uddg", [None])[0]
        if u:
            return urllib.parse.unquote(u)
    return href

SLUG_RE = re.compile(r"linkedin\.com/company/([A-Za-z0-9\-\_%\.]+)")

def slug_from(url):
    """Extrai o slug de uma URL de company page — não gera slug a partir de nome.

    Não é substituível por `egressos_core.text.slug_linkedin`: aquela **adivinha** o
    slug a partir do nome da empresa; esta **lê** o slug que o LinkedIn já publicou.
    """
    m = SLUG_RE.search(url or "")
    if not m:
        return None
    slug = urllib.parse.unquote(m.group(1)).strip("/").lower()
    slug = slug.split("?")[0].split("/")[0]
    if not slug or slug in SLUG_BLOCK:
        return None
    return slug

def ddg_search(query, retries=3):
    """Retorna lista de URLs de resultado (na ordem), tentando os endpoints.
    Trata 202 (challenge) e ConnectionReset como retryable com backoff."""
    for ep in ENDPOINTS:
      for attempt in range(retries):
        try:
            r = requests.post(ep, data={"q": query, "kl": "br-pt"},
                              headers={"User-Agent": UA}, timeout=25)
            if r.status_code in (202, 429, 403):     # soft-block: espera e tenta de novo
                time.sleep(8 * (attempt + 1) + random.uniform(0, 4))
                continue
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            urls = []
            for a in soup.select("a.result__a, a.result-link, a[href]"):
                href = a.get("href", "")
                u = decode_ddg(href)
                if "linkedin.com/company/" in u:
                    urls.append(u)
            # fallback: regex no texto cru (a URL de display aparece)
            if not urls:
                for m in SLUG_RE.finditer(urllib.parse.unquote(r.text)):
                    urls.append("https://www.linkedin.com/company/" + m.group(1))
            if urls:
                return urls
        except Exception as e:
            print(f"    ! {ep} erro: {type(e).__name__}: {e}")
    return []

def resolve(nome):
    for q in (f'site:linkedin.com/company "{nome}"',
              f'site:linkedin.com/company {nome}'):
        urls = ddg_search(q)
        for u in urls:
            slug = slug_from(u)
            if slug:
                # confiança: alta se o 1º resultado bateu na query com aspas
                conf = "alta" if '"' in q and u is urls[0] else "media"
                return {"url": f"https://www.linkedin.com/company/{slug}/",
                        "slug": slug, "confianca": conf, "via": "ddg-dork", "query": q}
        time.sleep(random.uniform(1.5, 3.0))
    return None

def main():
    only_all = "--all" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    aliases = json.load(open(ALIASES, encoding="utf-8"))
    out = {}
    if os.path.exists(OUT):
        out = json.load(open(OUT, encoding="utf-8"))

    alvos = [(k, v) for k, v in aliases.items() if (only_all or v.get("atual"))]
    alvos = [(k, v) for k, v in alvos if k not in out]        # idempotente
    if limit:
        alvos = alvos[:limit]

    print(f"resolvendo {len(alvos)} empresas (já resolvidas: {len(out)})…\n")
    for i, (nome, meta) in enumerate(alvos, 1):
        res = resolve(nome)
        if res:
            out[nome] = {**res, "aliases": meta.get("aliases", [])}
            print(f"[{i}/{len(alvos)}] ✓ {nome}  ->  {res['slug']}  ({res['confianca']})")
        else:
            out[nome] = {"url": None, "slug": None, "confianca": "nao_encontrado",
                         "via": "ddg-dork", "aliases": meta.get("aliases", [])}
            print(f"[{i}/{len(alvos)}] ✗ {nome}  ->  não encontrado")
        json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)  # grava a cada empresa
        time.sleep(random.uniform(2.0, 4.5))                 # pacing educado com o buscador

    ok = sum(1 for v in out.values() if v.get("slug"))
    print(f"\nfeito. {ok}/{len(out)} com URL. saída: {OUT}")

if __name__ == "__main__":
    main()

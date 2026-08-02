#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fonte única do MENU do site: injeta a mesma navegação em TODAS as páginas.

Roda depois de todos os geradores (gen_executivo, gen_panorama, gen_vitrine, gen_reguas,
gen_dados_abertos) e antes do publish. Substitui o <nav aria-label="Outras visões"> onde
já existe; insere logo após o </header> onde não existe.

Estilos vão inline no próprio markup — assim o menu funciona igual em páginas com CSS
diferente (cada página tem sua paleta) sem depender de classe .nav definida no arquivo.

A página atual aparece no menu marcada e sem link, para o leitor saber onde está.

Uso:  python pipeline/gen_nav.py
"""
import json
import re
import sys

from egressos_core.paths import PUB
from egressos_core.paths import ROOT as BASE

# (raiz, arquivo, nome no site publicado, ícone, título, subtítulo)
# A LISTA vem de `paginas.json` — a mesma que o Astro e o portão leem. Enquanto esta tabela
# vivia aqui escrita à mão, ela era uma de duas que precisavam concordar (a outra está em
# build_report.py) e nada verificava que concordavam.
#
# Página já migrada para Astro é PULADA: o menu dela vem do `Base.astro`, e injetar aqui
# escreveria por cima de arquivo que este script não produz. Quando a última migrar, a lista
# fica vazia e o script deixa de ter o que fazer — é assim que ele morre, sem data marcada.
LISTA = json.loads(
    (BASE / "packages/egressos-site/app/src/lib/paginas.json").read_text(encoding="utf-8"))

#: (onde, arquivo na origem, nome publicado, ícone, título, subtítulo)
#: "L" = raiz do repo local · "P" = repo público, onde a página já é gerada
PAGES = [
    ("P" if p["origem"] == "publico" else "L",
     p.get("arquivo_fonte", f'{p["slug"]}.html'),
     f'{p["slug"]}.html',
     p["icone"], p["titulo"], p["subtitulo"])
    for p in LISTA["paginas"] if p["origem"] != "astro"
]

#: O menu precisa listar TODAS as páginas, inclusive as que já migraram — quem está numa
#: página antiga tem de conseguir chegar nas novas.
TODAS = [(f'{p["slug"]}.html', p["icone"], p["titulo"], p["subtitulo"]) for p in LISTA["paginas"]]

CARD = ("flex:1 1 210px;text-decoration:none;background:var(--surface,#fff);"
        "border:1px solid var(--border,rgba(0,0,0,.1));border-radius:12px;padding:12px 14px;"
        "box-shadow:var(--shadow,0 1px 2px rgba(0,0,0,.05));font-weight:650;font-size:13px;"
        "line-height:1.35;color:var(--accent,#2a78d6)")
CARD_ON = CARD + ";border-width:1.5px;border-color:var(--accent,#2a78d6);cursor:default"
SUB = ("display:block;font-weight:400;color:var(--ink-2,#52565e);font-size:11.5px;"
       "margin-top:3px;line-height:1.4")
WRAP = "display:flex;flex-wrap:wrap;gap:9px;margin:0 0 4px"


def nav_html(atual):
    # Itera TODAS as páginas, não só as legadas: quem está numa página antiga precisa
    # conseguir chegar nas que já migraram.
    itens = []
    for href, ico, tit, sub in TODAS:
        if href == atual:
            itens.append(f'      <span style="{CARD_ON}" aria-current="page">{ico} {tit}'
                         f'<span style="{SUB}">você está aqui</span></span>')
        else:
            itens.append(f'      <a href="{href}" style="{CARD}">{ico} {tit} →'
                         f'<span style="{SUB}">{sub}</span></a>')
    return ('    <nav aria-label="Seções do relatório" style="' + WRAP + '">\n'
            + "\n".join(itens) + "\n    </nav>\n")


NAV_RE = re.compile(r'[ \t]*<nav[^>]*aria-label="(?:Outras visões|Outras páginas|Seções do relatório)"[^>]*>.*?</nav>\s*\n',
                    re.S)


def inject(raiz, arq, atual):
    p = (BASE if raiz == "L" else PUB) / arq
    if not p.exists():
        print(f"  [pula ] {arq} (não existe)")
        return False
    t = p.read_text(encoding="utf-8")
    nav = nav_html(atual)
    novo, n = NAV_RE.subn(lambda m: nav, t, count=1)
    if n:
        acao = "substituído"
    else:
        # insere depois do </header>; se não houver, depois da abertura do container
        m = re.search(r"</header>\s*\n", t)
        if not m:
            print(f"  [FALHA] {arq}: sem <nav> e sem </header> — menu não inserido")
            return False
        novo = t[:m.end()] + "\n" + nav + "\n" + t[m.end():]
        acao = "inserido"
    if novo == t:
        print(f"  [igual] {arq}")
        return True
    p.write_text(novo, encoding="utf-8")
    print(f"  [{acao:11s}] {arq}  (marcado: {atual})")
    return True


def main():
    if not PAGES:
        print("== menu único: nenhuma página legada restou; o Base.astro cobre todas ==")
        return
    print(f"== menu único em {len(PAGES)} páginas legadas (de {len(TODAS)}) ==")
    ok = all([inject(raiz, arq, href) for raiz, arq, href, *_ in PAGES])
    if not ok:
        sys.exit("ABORT: alguma página ficou sem menu")
    print("OK — menu idêntico em todas as páginas")


if __name__ == "__main__":
    main()

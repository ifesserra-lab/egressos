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
import pathlib, re, sys

BASE = pathlib.Path("/caminho/para/salario")
PUB  = BASE.parent / "egressos"   # gen_vitrine e gen_dados_abertos escrevem direto aqui

# (raiz, arquivo, nome no site publicado, ícone, título, subtítulo)
# raiz "L" = repo local salario/ (a página é copiada no publish)
# raiz "P" = repo público egressos/ (a página já é gerada lá)
PAGES = [
    ("L", "dashboard_executivo.html",    "index.html",                   "📊", "Impacto na carreira",       "Visão executiva: renda estimada vs. mercado"),
    ("L", "trajetoria_salarial.html",    "trajetoria_salarial.html",     "📈", "Trajetória salarial",       "Ano a ano, em salários mínimos e vs. o mundo"),
    ("L", "dashboard_alunos.html",       "dashboard_alunos.html",        "👥", "Panorama por egresso",      "Linha do tempo e cards anonimizados (A–AX)"),
    ("P", "egressos-carreiras.html",     "egressos-carreiras.html",      "🌍", "Onde estão os egressos",    "Empresas, países e jornada de cada um"),
    ("L", "metodologia.html",            "metodologia.html",             "🔬", "Metodologia",               "Fontes, ETL, cálculo salarial e ressalvas"),
    ("P", "dados-abertos.html",          "dados-abertos.html",           "📂", "Dados abertos",             "Baixe os JSON e o código (CC BY / MIT)"),
]

CARD = ("flex:1 1 210px;text-decoration:none;background:var(--surface,#fff);"
        "border:1px solid var(--border,rgba(0,0,0,.1));border-radius:12px;padding:12px 14px;"
        "box-shadow:var(--shadow,0 1px 2px rgba(0,0,0,.05));font-weight:650;font-size:13px;"
        "line-height:1.35;color:var(--accent,#2a78d6)")
CARD_ON = CARD + ";border-width:1.5px;border-color:var(--accent,#2a78d6);cursor:default"
SUB = ("display:block;font-weight:400;color:var(--ink-2,#52565e);font-size:11.5px;"
       "margin-top:3px;line-height:1.4")
WRAP = "display:flex;flex-wrap:wrap;gap:9px;margin:0 0 4px"


def nav_html(atual):
    itens = []
    for _, _, href, ico, tit, sub in PAGES:
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
    print(f"== menu único em {len(PAGES)} páginas ==")
    ok = all([inject(raiz, arq, href) for raiz, arq, href, *_ in PAGES])
    if not ok:
        sys.exit("ABORT: alguma página ficou sem menu")
    print("OK — menu idêntico em todas as páginas")


if __name__ == "__main__":
    main()

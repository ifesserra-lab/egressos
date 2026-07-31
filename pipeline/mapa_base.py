#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera data/mapa_mundi.json — o contorno dos continentes já projetado, pronto para virar
<path> na página. Roda uma vez e fica em cache; o resultado é versionado.

Por que pré-processar em vez de carregar um mapa no navegador: a página é servida no
GitHub Pages e não deve depender de CDN nem baixar 500 KB de TopoJSON a cada visita.
Aqui o TopoJSON de 55 KB vira ~30 KB de paths SVG já em coordenadas de tela.

Fonte: world-atlas land-110m (Natural Earth 110m, domínio público) via jsDelivr.
Projeção: equirretangular (plate carrée) — simples, e a leitura aqui é "onde tem gente",
não distância nem área.

Uso:  python pipeline/mapa_base.py            (baixa e converte)
      python pipeline/mapa_base.py --offline  (só converte, a partir do cache)
"""
import json
import sys
import urllib.error
import urllib.request

from egressos_core.paths import ROOT as BASE

sys.setrecursionlimit(10000)

DATA = BASE / "data"
CACHE = DATA / "_cache_ibge"          # mesmo diretório de cache dos downloads
# Duas resoluções: a grossa vai embutida na página (leve, boa até ~3x de zoom) e a fina
# fica num arquivo à parte, buscado só quando o leitor aproxima. Sem isso, ou a página
# carrega meio mega de contorno que quase ninguém usa, ou o litoral vira um polígono tosco
# no zoom — que é o que acontecia.
CAMADAS = {
    "base":    {"url": "https://cdn.jsdelivr.net/npm/world-atlas@2/land-110m.json",
                "cache": "land110m.json", "eps": 0.7,  "area_min": 1.2,
                "saida": "mapa_mundi.json",         "detalhe": "Natural Earth 110m"},
    "detalhe": {"url": "https://cdn.jsdelivr.net/npm/world-atlas@2/land-50m.json",
                "cache": "land50m.json",  "eps": 0.10, "area_min": 0.15,
                "saida": "mapa_mundi_detalhe.json", "detalhe": "Natural Earth 50m"},
}

W, H = 1000, 420                       # viewBox do mapa
LAT_MAX = 83                           # corta a Antártida e o topo do Ártico (sem gente aqui)
LAT_MIN = -56
CASAS = 2                              # casas decimais nos paths


def proj(lon, lat):
    """Equirretangular, recortada na faixa de latitude que interessa."""
    x = (lon + 180) / 360 * W
    y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * H
    return x, y


def baixa(cam, offline):
    URL = cam["url"]
    cache = CACHE / cam["cache"]
    if offline:
        if not cache.exists():
            sys.exit(f"ABORT: --offline mas não há cache em {cache}")
        return json.loads(cache.read_text(encoding="utf-8"))
    try:
        with urllib.request.urlopen(URL, timeout=90) as r:
            raw = r.read().decode("utf-8")
        CACHE.mkdir(parents=True, exist_ok=True)
        cache.write_text(raw, encoding="utf-8")
        print(f"  [rede ] {cam['detalhe']} ({len(raw)//1024} KB)")
        return json.loads(raw)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        if cache.exists():
            print(f"  [cache] {cam['detalhe']} (rede falhou: {e})")
            return json.loads(cache.read_text(encoding="utf-8"))
        sys.exit(f"ABORT: mapa indisponível e sem cache — {e}")


def decodifica_arcos(topo):
    """TopoJSON guarda os arcos quantizados e em delta; devolve cada um em lon/lat."""
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    out = []
    for arco in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arco:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        out.append(pts)
    return out


def anel_para_pontos(indices, arcos):
    pts = []
    for i in indices:
        a = arcos[~i][::-1] if i < 0 else arcos[i]      # índice negativo = arco invertido
        pts.extend(a if not pts else a[1:])
    return pts


def area(pts):
    s = 0.0
    for i in range(len(pts) - 1):
        s += pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
    return abs(s) / 2


def simplifica(pts, eps):
    """Douglas-Peucker: tira os pontos que não mudam o traçado além de `eps` pixels.
    A tolerância vem da camada: grossa na base, fina no detalhe."""
    if len(pts) < 3:
        return pts
    ax, ay = pts[0]
    bx, by = pts[-1]
    dx, dy = bx - ax, by - ay
    norma = (dx * dx + dy * dy) ** 0.5
    pior, idx = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = (abs(dy * px - dx * py + bx * ay - by * ax) / norma if norma
             else ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5)
        if d > pior:
            pior, idx = d, i
    if pior <= eps:
        return [pts[0], pts[-1]]
    return simplifica(pts[:idx + 1], eps)[:-1] + simplifica(pts[idx:], eps)


def anel_para_path(pts, eps, area_min):
    proj_pts, ant = [], None
    for lon, lat in pts:
        lat = max(LAT_MIN, min(LAT_MAX, lat))
        x, y = proj(lon, lat)
        p = (round(x, CASAS), round(y, CASAS))
        if p != ant:                                    # tira pontos repetidos após arredondar
            proj_pts.append(p)
            ant = p
    if len(proj_pts) < 4 or area(proj_pts) < area_min:
        return None
    proj_pts = simplifica(proj_pts, eps)
    if len(proj_pts) < 4:
        return None
    d = "M" + " ".join(f"{x} {y}" for x, y in proj_pts) + "Z"
    return d.replace("M", "M", 1)


def gera(nome, cam, offline):
    topo = baixa(cam, offline)
    arcos = decodifica_arcos(topo)
    geoms = topo["objects"]["land"]["geometries"]

    paths, descartados = [], 0
    for g in geoms:
        poligonos = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        for poli in poligonos:
            for anel in poli:                           # anel 0 = contorno, demais = buracos
                d = anel_para_path(anel_para_pontos(anel, arcos), cam["eps"], cam["area_min"])
                if d:
                    paths.append(d)
                else:
                    descartados += 1

    out = {
        "titulo": "Contorno dos continentes, projetado para SVG",
        "fonte": f"{cam['detalhe']} (domínio público) via world-atlas",
        "url": cam["url"], "camada": nome,
        "gerado_por": "pipeline/mapa_base.py",
        "projecao": "equirretangular (plate carrée)",
        "viewBox": [0, 0, W, H],
        "lat_range": [LAT_MIN, LAT_MAX],
        "nota": "Use proj(lon,lat) = ((lon+180)/360*W, (LAT_MAX-lat)/(LAT_MAX-LAT_MIN)*H) "
                "para posicionar qualquer ponto sobre estes paths.",
        "paths": paths,
    }
    alvo = DATA / cam["saida"]
    alvo.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kb = alvo.stat().st_size / 1024
    print(f"  {alvo.name:28s} {len(paths):5d} polígonos  {kb:6.0f} KB  ({descartados} ilhotas fora)")


def main():
    offline = "--offline" in sys.argv
    print("== contorno dos continentes ==")
    for nome, cam in CAMADAS.items():
        gera(nome, cam, offline)


if __name__ == "__main__":
    main()

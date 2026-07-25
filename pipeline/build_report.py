"""
Orquestrador do relatório de egressos — gera TUDO a partir dos dados.

Ordem:
  1. genero.py            -> data/genero_map.json      (gênero inferido offline)
  2. compute_all.py       -> data/consolidado.json     (série salarial SO+FX+IPCA)
  3. src_extensao.py      -> data/src_extensao.json     (extensão SRC/IFES)
  4. fapes_fomento.py     -> data/fapes_fomento.json    (fomento FAPES)
  5. analise.py           -> data/analise.json          (clusters, gênero, empresas,
                                                          sankeys, trilha, labs, extensão)
  6. gen_executivo.py     -> reescreve os consts do dashboard_executivo.html
  7. gen_panorama.py      -> reescreve o DB.alunos do dashboard_alunos.html (A–…)
  8. qa_report.py         -> valida HTML × pipeline + varredura de PII

Uso:   python data/build_report.py            (gera + valida)
       python data/build_report.py --publish  (após validar, copia p/ os repos públicos)

IMPORTANTE — sincronia de order/labels:
  data/compute_all.py, data/analise.py e data/gen_panorama.py têm as listas
  order[]/labels[] dos egressos. Ao adicionar egresso, estender as TRÊS na mesma
  ordem (o join salário↔perfil em analise.py é por LABEL, robusto a perfis puladas).

  gen_executivo.py e gen_panorama.py lêem apenas consolidado.json/analise.json/
  alunos.json — os números do dashboard vêm SEMPRE do pipeline, nunca à mão.
"""
import subprocess, pathlib, sys

BASE = pathlib.Path("/caminho/para/salario")
PY = str(BASE / ".venv/bin/python")
NODE = "node"

PIPE = BASE / "pipeline"   # scripts moved out of data/ (code vs artefatos)
STEPS = [
    # compute_all.py roda com cwd=data/ (usa public-*.csv / ../alunos.json relativos); os demais
    # usam caminho absoluto S internamente, então cwd=BASE serve.
    ("Gênero (offline)",        [PY, str(PIPE/"genero.py")],        BASE),
    ("Série salarial",          [PY, str(PIPE/"compute_all.py")],   BASE / "data"),
    ("Extensão SRC/IFES",       [PY, str(PIPE/"src_extensao.py")],  BASE),
    ("Fomento FAPES",           [PY, str(PIPE/"fapes_fomento.py")], BASE),
    ("Análise",                 [PY, str(PIPE/"analise.py")],       BASE),
    ("Consts do executivo",     [PY, str(PIPE/"gen_executivo.py")], BASE),
    ("DB do panorama",          [PY, str(PIPE/"gen_panorama.py")],  BASE),
    ("QA + PII",                [PY, str(PIPE/"qa_report.py")],     BASE),
]

def run():
    for desc, args, cwd in STEPS:
        print(f"\n=== {desc} ===", flush=True)
        r = subprocess.run(args, cwd=str(cwd))
        if r.returncode != 0:
            print(f"FALHOU em: {desc} (exit {r.returncode})", flush=True)
            sys.exit(r.returncode)
    print("\nBUILD OK — relatórios gerados e validados.")

def publish():
    """Copia executivo→index (com nav), panorama, evolução e metodologia p/ egressos + diretoria.
    metodologia.html é página estática escrita à mão (não gerada) — só copiada aqui."""
    import re
    PUB = BASE.parent / "egressos"
    DIR = BASE.parent / "diretoria/docs/relatorios/egressos"
    exe = (BASE / "dashboard_executivo.html").read_text(encoding="utf-8")
    old = (PUB / "index.html").read_text(encoding="utf-8")
    nav = re.search(r'(    <nav aria-label="Outras visões".*?</nav>\n\n)', old, re.S).group(1)
    anchor = '    <section class="hero-kpi" id="kpi"></section>'
    (PUB / "index.html").write_text(exe.replace(anchor, nav + anchor, 1), encoding="utf-8")
    for f in ["dashboard_alunos.html", "evolucao_salario_local.html", "metodologia.html"]:
        (PUB / f).write_text((BASE / f).read_text(encoding="utf-8"), encoding="utf-8")
    for f in ["index.html", "dashboard_alunos.html", "evolucao_salario_local.html", "metodologia.html"]:
        (DIR / f).write_text((PUB / f).read_text(encoding="utf-8"), encoding="utf-8")
    print("Publicado em egressos/ e diretoria/docs/relatorios/egressos/ (falta git push + mkdocs gh-deploy).")

if __name__ == "__main__":
    run()
    if "--publish" in sys.argv:
        publish()

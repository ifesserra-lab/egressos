"""
Orquestrador do relatório de egressos — gera TUDO a partir dos dados.

Ordem:
  0. ibge_series.py       -> data/salario_minimo.json  (SM + IPCA + INPC, baixados do IBGE/IPEADATA)
     so_benchmarks.py     -> data/so_benchmarks.json   (medianas US$ por país e por moeda do contracheque)
     mapa_base.py         -> data/mapa_mundi.json      (contorno dos continentes já projetado p/ SVG)
  1. genero.py            -> data/genero_map.json      (gênero inferido offline)
  2. compute_all.py       -> data/consolidado.json     (série salarial SO+FX+IPCA+SM)
  3. src_extensao.py      -> data/src_extensao.json     (extensão SRC/IFES)
  4. fapes_fomento.py     -> data/fapes_fomento.json    (fomento FAPES)
  5. analise.py           -> data/analise.json          (clusters, gênero, empresas,
                                                          sankeys, trilha, labs, extensão)
  6. gen_executivo.py     -> reescreve os consts do dashboard_executivo.html
  7. gen_panorama.py      -> reescreve o DB.alunos do dashboard_alunos.html (A–…)
  8. gen_reguas.py        -> gera trajetoria_salarial.html (trajetória + SM + mundo);
                             as páginas antigas viram redirecionamento
     gen_nav.py           -> injeta o mesmo menu em TODAS as páginas
  9. gen_dados_abertos.py -> publica JSON + código no repo público
     gen_api.py           -> gera egressos/api/ (API estática, anonimizada, com índice)
 10. qa_report.py         -> valida HTML × pipeline + varredura de PII

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
# Interpretador dos subprocessos: o venv local quando existe, senão o próprio Python que
# está rodando (é o caso do CI, que instala as dependências no ambiente do runner).
_venv = BASE / ".venv/bin/python"
PY = str(_venv) if _venv.exists() else sys.executable
NODE = "node"

PIPE = BASE / "pipeline"   # scripts moved out of data/ (code vs artefatos)
STEPS = [
    # compute_all.py roda com cwd=data/ (usa public-*.csv / ../alunos.json relativos); os demais
    # usam caminho absoluto S internamente, então cwd=BASE serve.
    ("Séries IBGE/IPEADATA",    [PY, str(PIPE/"ibge_series.py")],   BASE),
    ("Benchmarks Stack Overflow",[PY, str(PIPE/"so_benchmarks.py")], BASE),
    ("Contorno do mapa-múndi",   [PY, str(PIPE/"mapa_base.py")],     BASE),
    ("Gênero (offline)",        [PY, str(PIPE/"genero.py")],        BASE),
    ("Série salarial",          [PY, str(PIPE/"compute_all.py")],   BASE / "data"),
    ("Extensão SRC/IFES",       [PY, str(PIPE/"src_extensao.py")],  BASE),
    ("Fomento FAPES",           [PY, str(PIPE/"fapes_fomento.py")], BASE),
    ("Análise",                 [PY, str(PIPE/"analise.py")],       BASE),
    ("Consts do executivo",     [PY, str(PIPE/"gen_executivo.py")], BASE),
    ("DB do panorama",          [PY, str(PIPE/"gen_panorama.py")],  BASE),
    ("Vitrine de carreiras",    [PY, str(PIPE/"gen_vitrine.py")],   BASE),
    ("Duas réguas (SM + mundo)",[PY, str(PIPE/"gen_reguas.py")],    BASE),
    ("Dados abertos",           [PY, str(PIPE/"gen_dados_abertos.py")], BASE),
    ("API estática",            [PY, str(PIPE/"gen_api.py")],       BASE),
    ("Menu único",              [PY, str(PIPE/"gen_nav.py")],       BASE),
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
    """Copia as páginas p/ o repo público (egressos/) e p/ o site da diretoria.

    O menu já vem injetado por gen_nav.py em todas elas — o publish só copia.
    egressos-carreiras.html e dados-abertos.html são gerados direto em egressos/,
    então aqui só seguem para o site da diretoria."""
    PUB = BASE.parent / "egressos"
    DIR = BASE.parent / "diretoria/docs/relatorios/egressos"
    (PUB / "index.html").write_text(
        (BASE / "dashboard_executivo.html").read_text(encoding="utf-8"), encoding="utf-8")
    for f in ["dashboard_alunos.html", "evolucao_salario_local.html", "metodologia.html",
              "trajetoria_salarial.html", "salario_minimo_mundo.html"]:
        (PUB / f).write_text((BASE / f).read_text(encoding="utf-8"), encoding="utf-8")
    # O portal da diretoria vive em outro repositório e nem sempre está montado (no CI não está).
    # Quando não estiver, publica só no repo do site e avisa — não cria diretório solto.
    if DIR.parent.parent.exists():
        for f in ["index.html", "dashboard_alunos.html", "evolucao_salario_local.html", "metodologia.html",
                  "trajetoria_salarial.html", "salario_minimo_mundo.html",
                  "egressos-carreiras.html", "dados-abertos.html"]:
            (DIR / f).write_text((PUB / f).read_text(encoding="utf-8"), encoding="utf-8")
        print("Publicado em egressos/ e diretoria/docs/relatorios/egressos/ (falta git push).")
    else:
        print(f"Publicado em egressos/. Portal da diretoria não montado ({DIR.parent.parent}) — ignorado.")

if __name__ == "__main__":
    run()
    if "--publish" in sys.argv:
        publish()

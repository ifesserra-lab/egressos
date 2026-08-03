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
  6. gen_impacto.py       -> data/impacto.json          (o que a página de entrada mostra)
  7. gen_panorama.py      -> data/panorama.json          (coorte anonimizada A–AX)
  8. gen_trajetoria.py    -> data/trajetoria.json       (trajetória + SM + mundo)
     gen_nav.py           -> injeta o mesmo menu nas páginas legadas que restarem
  9. gen_dados_abertos.py -> publica JSON + código no repo público
     gen_api.py           -> gera egressos/api/ (API estática, anonimizada, com índice)
 10. pytest P9            -> valida dataset × fonte (PII é P2, no portão)

Uso:   python data/build_report.py            (gera + valida)
       python data/build_report.py --publish  (após validar, copia p/ os repos públicos)

IMPORTANTE — sincronia de order/labels:
  data/compute_all.py, data/analise.py e data/gen_panorama.py têm as listas
  order[]/labels[] dos egressos. Ao adicionar egresso, estender as TRÊS na mesma
  ordem (o join salário↔perfil em analise.py é por LABEL, robusto a perfis puladas).

  gen_impacto.py e gen_panorama.py lêem apenas consolidado.json/analise.json/
  alunos.json — os números do dashboard vêm SEMPRE do pipeline, nunca à mão.
"""
import subprocess
import sys

from egressos_core.paths import ROOT as BASE

# Interpretador dos subprocessos: o venv local quando existe, senão o próprio Python que
# está rodando (é o caso do CI, que instala as dependências no ambiente do runner).
_venv = BASE / ".venv/bin/python"
PY = str(_venv) if _venv.exists() else sys.executable
NODE = "node"

PIPE = BASE / "pipeline"   # scripts moved out of data/ (code vs artefatos)
# Os geradores de HTML e o QA por engenharia reversa vivem em `old/`: têm sucessor nomeado
# (o Astro e `egressos_site.portao`) e data de morte por fatia. Ver old/README.md. Eles não
# foram desligados — enquanto a página deles não migrou, é o que mantém o site no ar.
OLD = BASE / "old/pipeline"
STEPS = [
    # Nenhuma etapa depende mais do diretório corrente: todas resolvem caminho pelo catálogo
    # (egressos_core.dados) ou pela raiz detectada. A `Série salarial` era a última que exigia
    # cwd=data/ — lia `../alunos.json` e gravava `consolidado.json` relativos — e deixou de
    # exigir na fatia C da F2. Passar BASE em todas é agora só uma escolha, não um requisito.
    ("Séries IBGE/IPEADATA",    [PY, str(PIPE/"ibge_series.py")],   BASE),
    ("Benchmarks Stack Overflow",[PY, str(PIPE/"so_benchmarks.py")], BASE),
    ("Contorno do mapa-múndi",   [PY, str(PIPE/"mapa_base.py")],     BASE),
    ("Gênero (offline)",        [PY, str(PIPE/"genero.py")],        BASE),
    ("Série salarial",          [PY, str(PIPE/"compute_all.py")],   BASE),
    ("Extensão SRC/IFES",       [PY, str(PIPE/"src_extensao.py")],  BASE),
    ("Fomento FAPES",           [PY, str(PIPE/"fapes_fomento.py")], BASE),
    ("Análise",                 [PY, str(PIPE/"analise.py")],       BASE),
    # Depois da análise: a vitrine nomeada e a faixa por cargo saem do cruzamento dela com o
    # consolidado. Dois arquivos, contratos diferentes — ver o docstring de gen_perfis.py.
    ("Perfis e renda por cargo", [PY, str(PIPE/"gen_perfis.py")],   BASE),
    # A página de entrada virou dado + Astro. O `gen_executivo.py` fazia substituição de
    # constante JS dentro de HTML autoral — dez `re.subn` com `assert n == 1`.
    ("Impacto (dataset)",      [PY, str(PIPE/"gen_impacto.py")], BASE),
    # O panorama virou dado + página Astro. O antigo trocava, por expressão regular, um objeto
    # JavaScript de 64 KB dentro do HTML — e a anonimização era montagem de string.
    ("Panorama (dataset)",      [PY, str(PIPE/"gen_panorama.py")], BASE),
    ("Vitrine de carreiras",    [PY, str(OLD/"gen_vitrine.py")],   BASE),
    # A trajetória virou dado + página Astro. O `gen_reguas.py` (757 linhas de conta e
    # marcação na mesma f-string) saiu: quem calcula é egressos_core.trajetoria, quem
    # mostra é trajetoria_salarial.astro.
    ("Trajetória (dataset)",    [PY, str(PIPE/"gen_trajetoria.py")], BASE),
    ("Dados abertos",           [PY, str(PIPE/"gen_dados_abertos.py")], BASE),
    ("API estática",            [PY, str(PIPE/"gen_api.py")],       BASE),
    ("Menu único",              [PY, str(OLD/"gen_nav.py")],       BASE),
    # P9 — números × fonte. Era o `qa_report.py`, que extraía constantes JS do HTML com `node`
    # e comparava. Duas coisas o mataram: a página não tem mais JS, e ele estava lendo um dump
    # de constantes de dois dias antes (gravava em old/pipeline/, lia em data/) — 71 checagens
    # verdes sem tocar no artefato. A varredura de PII que ele fazia numa página está no
    # portão, como P2, sobre a união das origens.
    ("Números × fonte (P9)",    [PY, "-m", "pytest", "-q", "tests/test_projecao_impacto.py"], BASE),
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
    """Publica pelo portão: build do site, verificação, e só então a cópia.

    Antes esta função tinha DUAS listas de arquivos escritas à mão — uma para o repositório
    público, outra para o portal da diretoria — e elas já divergiam entre si. Página nova
    exigia lembrar das duas; página migrada, das duas de novo.

    Agora quem sabe quais páginas existem é `paginas.json`, e quem sabe de ONDE cada uma sai é
    o portão (`site/` para as migradas, a raiz e o repositório público para as que ainda não).
    A cópia é consequência da aprovação, não um passo à parte que pode ser esquecido.
    """
    from egressos_site import build, publica

    print("\n== Site (Astro) ==")
    print(f"  {build.constroi()} arquivos em site/")
    try:
        copiados = publica.publica()
    except publica.NaoAprovado as e:
        print(e)
        sys.exit(1)
    print(f"  {len(copiados)} cópias:")
    for c in copiados:
        print(f"    {c}")

if __name__ == "__main__":
    run()
    if "--publish" in sys.argv:
        publish()

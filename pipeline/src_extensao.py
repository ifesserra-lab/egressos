"""Cruza os egressos com a base OFICIAL de extensão do IFES Serra (src_etl / SRC),
por nome completo normalizado. Descobre quem participou como equipe e quem foi
ALUNO(A) BOLSISTA de extensão — fomento além dos projetos FAPES de pesquisa.

Saída: data/src_extensao.json (AGREGADO + ids; privado — fica só no repo de dados).
Ressalva: match por nome completo (sem CPF no alunos.json) — possíveis homônimos;
tratar como piso (lower bound). Todos são egressos do IFES Serra, então o prior
de "mesmo nome = mesma pessoa" é alto."""
import collections
import glob
import json

from egressos_core.paths import ROOT as BASE
from egressos_core.paths import SRC_ETL_DATA as SRC
from egressos_core.text import norm_ws

FAPES_IDS = ["barbosa", "gary", "helen", "marialuiza", "icaro", "tarcisio"]  # cf. fapes_fomento.ANCORA

al = json.load(open(BASE / "alunos.json"))["alunos"]
egn = {norm_ws(a["nome"]): a["id"] for a in al}
gmap = json.load(open(BASE / "data/genero_map.json"))

hits = collections.defaultdict(list)  # id -> [(processo, funcao)]
# A base do SRC vive em outro repositório e nem sempre está montada (no CI não está).
# Degradar aqui é intencional — mas em voz alta: sem o aviso, "0 bolsistas de extensão"
# é indistinguível de "a fonte não estava lá".
if not SRC.exists():
    print(f"AVISO: base do SRC não montada em {SRC} — seguindo sem a seção de extensão. "
          f"Defina EGRESSOS_SRC_ETL se ela estiver em outro lugar.")
for f in glob.glob(str(SRC / "participacoes/*.json")):
    proc = f.split("participacoes_")[1].replace(".json", "")
    d = json.load(open(f))
    for at in d.get("atividades", []):
        for e in at.get("equipe_execucao", []):
            nm = norm_ws(e.get("Nome", ""))
            if nm in egn:
                hits[egn[nm]].append((proc, e.get("Função", "")))

encontrados = sorted(hits)
bolsistas_src = sorted(i for i, lst in hits.items() if any("BOLSISTA" in fn for _, fn in lst))
funcoes = collections.Counter(fn for lst in hits.values() for _, fn in lst)
# projetos distintos por egresso
projetos = {i: len({p for p, _ in lst}) for i, lst in hits.items()}
# bolsa documentada em base oficial: FAPES (pesquisa) OU SRC (extensão)
bolsa_doc = sorted(set(FAPES_IDS) | set(bolsistas_src))

def gsplit(ids):
    f = sum(1 for i in ids if gmap.get(i) == "F"); return {"F": f, "M": len(ids) - f, "total": len(ids)}

out = {
    "fonte": "SRC / IFES Serra — base oficial de ações de extensão (src_etl); match por nome completo",
    "ressalva": "sem CPF no alunos.json → match por nome (possíveis homônimos); piso/lower bound",
    "n_egressos": len(al),
    "n_encontrados": len(encontrados), "encontrados": encontrados,
    "n_bolsistas_extensao": len(bolsistas_src), "bolsistas_extensao": bolsistas_src,
    "funcoes": dict(funcoes.most_common()),
    "projetos_por_egresso": projetos,
    "fapes_pesquisa": FAPES_IDS,
    "bolsa_documentada_oficial": bolsa_doc, "n_bolsa_documentada_oficial": len(bolsa_doc),
    "genero": {"encontrados": gsplit(encontrados), "bolsistas_extensao": gsplit(bolsistas_src),
               "bolsa_documentada": gsplit(bolsa_doc)},
}
json.dump(out, open(BASE / "data/src_extensao.json", "w"), ensure_ascii=False, indent=1)
print(f"SRC extensão: {len(encontrados)}/{len(al)} na base | {len(bolsistas_src)} bolsistas de extensão")
print(f"bolsa documentada oficial (FAPES ∪ SRC): {len(bolsa_doc)} egressos -> {bolsa_doc}")
print(f"gênero bolsistas extensão: {out['genero']['bolsistas_extensao']}")
print(f"top funções: {list(funcoes.most_common(6))}")

"""Infere gênero do PRIMEIRO NOME, 100% offline (nunca envia nome pra fora).
gender-guesser + heurística de sufixo PT-BR + override manual por id (slug).
Saída: data/genero_map.json {id: "F"|"M"}. Fica só no repo privado.
Método aproximado/binário para análise de representação agregada — não é
declaração de identidade de gênero de ninguém."""
import gender_guesser.detector as gg

from egressos_core import dados
from egressos_core.text import strip_accents

det = gg.Detector(case_sensitive=False)

# Override por id (slug) onde o guesser erra ou desconhece nomes PT-BR.
OVERRIDE = {
    "barbosa": "M", "geann": "M", "phillipe": "M", "edvaldo": "M", "breno": "M",  # 'unknown' no guesser
    "renan": "M",         # guesser retornou 'female' (errado)
    "joao_paulo": "M", "antonio": "M",  # acento/mostly_*
}

def guess(first):
    g = det.get_gender(strip_accents(first))
    if g in ("male", "mostly_male"): return "M"
    if g in ("female", "mostly_female"): return "F"
    # fallback sufixo PT-BR (a→F, o→M) — só quando guesser não sabe
    fl = strip_accents(first).lower()
    if fl.endswith("a"): return "F"
    if fl.endswith(("o", "e", "l", "n", "r", "s")): return "M"
    return "M"  # default masculino (maioria do coorte); revisar em OVERRIDE

al = dados.ler("alunos")["alunos"]
gmap = {}
for a in al:
    first = a["nome"].split()[0]
    gmap[a["id"]] = OVERRIDE.get(a["id"], guess(first))

# Os dois datasets são `pii` no catálogo: nome de pessoa entra, id->gênero sai. Nenhum dos
# dois sai do repositório privado, e é o catálogo que garante isso — não um comentário.
dados.gravar("genero_map", gmap)
f = sum(1 for v in gmap.values() if v == "F"); m = len(gmap) - f
print(f"genero_map.json: {len(gmap)} egressos -> {f} F ({100*f/len(gmap):.0f}%) / {m} M")

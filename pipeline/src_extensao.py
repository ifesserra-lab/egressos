"""Cruza os egressos com a base OFICIAL de extensão do IFES Serra (src_etl / SRC).

O match é por nome completo normalizado. Descobre quem participou como equipe e quem foi
ALUNO(A) BOLSISTA de extensão — fomento além dos projetos FAPES de pesquisa.

Saída: `src_extensao` (AGREGADO + ids; `pii` no catálogo — fica só no repositório de dados).

Ressalva: match por nome completo, porque `alunos.json` não tem CPF. Possíveis homônimos, então
o número é **piso**, não contagem exata. Todos são egressos do IFES Serra, o que torna o prior
de "mesmo nome = mesma pessoa" alto.

Uso:  python pipeline/src_extensao.py     (de qualquer diretório)
"""
from __future__ import annotations

import collections
import sys
from typing import Any, Mapping, Sequence

from egressos_core import dados, deflator, io
from egressos_core.deflator import Competencia
from egressos_core.paths import SRC_ETL_DATA as SRC
from egressos_core.text import norm_ws

FAPES_IDS = ["barbosa", "gary", "helen", "marialuiza", "icaro", "tarcisio"]  # cf. fapes_fomento.ANCORA


def participacoes(por_nome: Mapping[str, str]) -> dict[str, list[tuple[str, str]]]:
    """`{id do egresso: [(processo, função), …]}` a partir dos arquivos do SRC.

    A base do SRC vive em outro repositório e nem sempre está montada (no CI não está).
    Degradar é intencional — mas **em voz alta**: sem o aviso, "0 bolsistas de extensão" fica
    indistinguível de "a fonte não estava lá".
    """
    if not SRC.exists():
        print(f"AVISO: base do SRC não montada em {SRC} — seguindo sem a seção de extensão. "
              f"Defina EGRESSOS_SRC_ETL se ela estiver em outro lugar.")
        return {}
    achados: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for arquivo in sorted(SRC.glob("participacoes/*.json")):
        processo = arquivo.name.split("participacoes_")[1].replace(".json", "")
        for atividade in io.load_json(arquivo).get("atividades", []):
            for pessoa in atividade.get("equipe_execucao", []):
                nome = norm_ws(pessoa.get("Nome", ""))
                if nome in por_nome:
                    achados[por_nome[nome]].append((processo, pessoa.get("Função", "")))
    return achados


def montar(*, alunos: Sequence[Mapping[str, Any]], genero_map: Mapping[str, str],
           achados: Mapping[str, Sequence[tuple[str, str]]]) -> dict:
    encontrados = sorted(achados)
    bolsistas = sorted(i for i, lista in achados.items()
                       if any("BOLSISTA" in funcao for _, funcao in lista))
    funcoes = collections.Counter(f for lista in achados.values() for _, f in lista)
    # bolsa documentada em base oficial: FAPES (pesquisa) OU SRC (extensão)
    bolsa_doc = sorted(set(FAPES_IDS) | set(bolsistas))

    def por_genero(ids: Sequence[str]) -> dict[str, int]:
        f = sum(1 for i in ids if genero_map.get(i) == "F")
        return {"F": f, "M": len(ids) - f, "total": len(ids)}

    return {
        "fonte": "SRC / IFES Serra — base oficial de ações de extensão (src_etl); "
                 "match por nome completo",
        "ressalva": "sem CPF no alunos.json → match por nome (possíveis homônimos); "
                    "piso/lower bound",
        "n_egressos": len(alunos),
        "n_encontrados": len(encontrados), "encontrados": encontrados,
        "n_bolsistas_extensao": len(bolsistas), "bolsistas_extensao": bolsistas,
        "funcoes": dict(funcoes.most_common()),
        "projetos_por_egresso": {i: len({p for p, _ in lista})
                                 for i, lista in achados.items()},
        "fapes_pesquisa": FAPES_IDS,
        "bolsa_documentada_oficial": bolsa_doc, "n_bolsa_documentada_oficial": len(bolsa_doc),
        "genero": {"encontrados": por_genero(encontrados),
                   "bolsistas_extensao": por_genero(bolsistas),
                   "bolsa_documentada": por_genero(bolsa_doc)},
    }


def executar(*, hoje: Competencia) -> dict:   # noqa: ARG001 - fronteira única das etapas
    """`hoje` não é usado: o cruzamento é por nome, não por data. Ver o contrato das etapas."""
    alunos = dados.ler("alunos")["alunos"]
    saida = montar(alunos=alunos, genero_map=dados.ler("genero_map"),
                   achados=participacoes({norm_ws(a["nome"]): a["id"] for a in alunos}))
    dados.gravar("src_extensao", saida)
    return saida


def main() -> int:
    saida = executar(hoje=deflator.data_referencia(dados.ler("ibge_series")))
    print(f"SRC extensão: {saida['n_encontrados']}/{saida['n_egressos']} na base | "
          f"{saida['n_bolsistas_extensao']} bolsistas de extensão")
    print(f"bolsa documentada oficial (FAPES ∪ SRC): {saida['n_bolsa_documentada_oficial']} "
          f"egressos -> {saida['bolsa_documentada_oficial']}")
    print(f"gênero bolsistas extensão: {saida['genero']['bolsistas_extensao']}")
    print(f"top funções: {list(saida['funcoes'].items())[:6]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

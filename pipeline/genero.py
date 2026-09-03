"""Infere gênero do PRIMEIRO NOME — 100% offline, o nome nunca sai desta máquina.

A regra mora em `egressos_core.genero`; aqui ficam a base de nomes instalada (`gender_guesser`)
e a gravação. Saída: `genero_map` = `{id: "F"|"M"}`.

Os dois datasets envolvidos são `pii` no catálogo: nome de pessoa entra, id→gênero sai. Nenhum
dos dois sai do repositório privado, e é o catálogo que garante isso — não um comentário.

Método aproximado e binário, para análise de representação **agregada**. Não é declaração de
identidade de gênero de ninguém.
"""
from __future__ import annotations

import sys

import gender_guesser.detector as gg

from egressos_core import dados, deflator, genero
from egressos_core.deflator import Competencia

_detector = gg.Detector(case_sensitive=False)


def executar(*, hoje: Competencia) -> dict[str, str]:   # noqa: ARG001 - ver docstring
    """Grava e devolve `genero_map`.

    `hoje` não é usado: inferir gênero pelo primeiro nome não depende de data. O parâmetro
    existe porque a fronteira das 16 etapas é **uma só** (`specs/003-dominio-no-nucleo/
    contracts/etapas-e-orquestracao.md`), e o orquestrador chama todas do mesmo jeito. Etapa
    que aceita uma assinatura diferente obriga o orquestrador a saber qual é qual — e é
    exatamente o que a fase acabou de eliminar.
    """
    mapa = genero.mapa_do_coorte(dados.ler("alunos")["alunos"],
                                 consultar_base=_detector.get_gender)
    dados.gravar("genero_map", mapa)
    return mapa


def main() -> int:
    mapa = executar(hoje=deflator.data_referencia(dados.ler("ibge_series")))
    f = sum(1 for v in mapa.values() if v == "F")
    print(f"genero_map.json: {len(mapa)} egressos -> {f} F ({100 * f / len(mapa):.0f}%) "
          f"/ {len(mapa) - f} M")
    return 0


if __name__ == "__main__":
    sys.exit(main())

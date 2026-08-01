#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Passo 0 — agrupa as variantes de nome de cada empregador.

Entrada: `alunos` (empresa atual + histórico) e `_empresas_lista`.
Saída:   `empresas_aliases` = `{canonico: {"aliases": [...], "atual": bool, "n_egressos_atual": int}}`

A regra de agrupamento mora em `egressos_core.empresas` — aqui ficam só a coleta dos nomes e a
gravação. Determinístico, offline, sem rede: o mesmo empregador escrito de três jeitos no
cadastro vira uma empresa, e é isso que faz a contagem por empregador publicada estar certa.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict

from egressos_core import dados, empresas
from egressos_core.text import strip_accents


def nomes_do_cadastro() -> tuple[set[str], set[str]]:
    """Todo nome de empresa que aparece no projeto, e quais são empregador ATUAL."""
    alunos = dados.ler("alunos")
    if isinstance(alunos, dict):
        alunos = alunos.get("alunos") or list(alunos.values())[0]

    atuais: set[str] = set()
    todos: set[str] = set()
    for a in alunos:
        atual = (a.get("empresa_atual") or "").strip()
        if atual:
            atuais.add(atual)
            todos.add(atual)
        for e in a.get("experiencias", []):
            nome = (e.get("empresa") or "").strip()
            if nome:
                todos.add(nome)

    try:
        lista = dados.ler("_empresas_lista")
        todos.update(x.strip() for x in lista if x and x.strip())
    except dados.DatasetAusente:
        pass                                   # a lista é insumo opcional do porte por LLM

    return todos, atuais


def _grupos(nomes: set[str]) -> dict[str, set[str]]:
    """Agrupa pela regra do núcleo, tolerando o travessão que o cadastro usa em dois formatos.

    A fusão manual é indexada pelo nome em minúsculo; um mesmo nome aparece com travessão longo
    e com hífen, e os dois têm de encontrar a mesma entrada.
    """
    grupos: dict[str, set[str]] = defaultdict(set)
    for nome in nomes:
        variantes = {strip_accents(nome).lower().strip(),
                     re.sub(r"[–—\-]", "-", nome).lower().strip(),
                     nome.lower().strip()}
        if variantes & empresas.NAO_EMPRESA or empresas.chave_de_agrupamento(nome) in empresas.NAO_EMPRESA:
            continue
        alvo = next((empresas.FUSOES_MANUAIS[v] for v in variantes
                     if v in empresas.FUSOES_MANUAIS), None)
        if alvo:
            chave = empresas.chave_de_agrupamento(alvo)
            grupos[chave].update({nome, alvo})
        else:
            grupos[empresas.chave_de_agrupamento(nome)].add(nome)
    return grupos


def executar() -> dict:
    todos, atuais = nomes_do_cadastro()
    grupos = _grupos(todos)

    por_chave_atual: dict[str, int] = defaultdict(int)
    alunos = dados.ler("alunos")["alunos"]
    for a in alunos:
        atual = (a.get("empresa_atual") or "").strip()
        if atual:
            por_chave_atual[empresas.chave_de_agrupamento(atual)] += 1

    saida = {}
    for chave, nomes in sorted(grupos.items()):
        if not chave:
            continue
        canonico = empresas.canonico(nomes)
        saida[canonico] = {
            "aliases": sorted(n for n in nomes if n != canonico),
            "atual": any(n in atuais for n in nomes),
            "n_egressos_atual": por_chave_atual.get(chave, 0),
        }
    dados.gravar("empresas_aliases", saida)
    return saida


def main() -> int:
    saida = executar()
    print(f"wrote {dados.caminho('empresas_aliases')}")
    print(f"  {len(saida)} empresas canônicas "
          f"({sum(1 for v in saida.values() if v['atual'])} são empregador ATUAL de algum egresso)")
    print(f"  {sum(1 for v in saida.values() if v['aliases'])} tiveram variantes agrupadas")
    print("  exemplos de merge:")
    for canonico, v in saida.items():
        if v["aliases"]:
            print(f"    {canonico!r} <- {v['aliases']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

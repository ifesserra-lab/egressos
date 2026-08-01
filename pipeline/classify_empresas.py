#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Classifica empresas pelo dado VERIFICADO da company page (coletado por browser-use).

  porte_real  <- headcount_linkedin        (bandas do LinkedIn, determinístico)
  setor_real  <- industry + specialties    (regras por palavra-chave)

As duas regras moram em `egressos_core.empresas`; aqui ficam a leitura, a gravação e o resumo.
Aditivo em `empresas_porte`: não apaga a estimativa por LLM, marca a fonte.

Só dado PÚBLICO de empresa. **Sem LLM e sem rede** — é o caminho determinístico, o que sempre
existe. Quando o LLM entra (pipeline/mistral_porte.py), ele é a outra estratégia, nunca a única.

Uso:  python pipeline/classify_empresas.py
"""
from __future__ import annotations

import sys
from collections import Counter

from egressos_core import dados, empresas


def executar() -> tuple[dict, int, int]:
    porte = dados.ler("empresas_porte")
    n_porte = n_setor = 0
    for nome, dado in porte.items():
        classificado_porte = empresas.porte_por_headcount(dado.get("headcount_linkedin"))
        if classificado_porte:
            dado["porte_real"] = classificado_porte
            n_porte += 1
        classificado_setor = empresas.setor_por_palavra_chave(
            dado.get("industry_linkedin"), dado.get("specialties"), empresa=nome)
        if classificado_setor:
            dado["setor_real"] = classificado_setor
            n_setor += 1
        if classificado_porte or classificado_setor:
            dado["classificacao_fonte"] = "linkedin+regras"
    dados.gravar("empresas_porte", porte)
    return porte, n_porte, n_setor


def main() -> int:
    porte, n_porte, n_setor = executar()
    print(f"classificadas: {n_porte} por headcount (porte_real), "
          f"{n_setor} por industry/specialties (setor_real)\n")

    contagem_porte = Counter(v["porte_real"] for v in porte.values() if v.get("porte_real"))
    contagem_setor = Counter(v["setor_real"] for v in porte.values() if v.get("setor_real"))

    print("== PORTE REAL (headcount LinkedIn) ==")
    for _, nome in empresas.BANDAS_DE_PORTE + ((None, empresas.PORTE_ACIMA_DA_ULTIMA_BANDA),):
        if contagem_porte.get(nome):
            print(f"  {contagem_porte[nome]:2}  {nome}")
    print("\n== SETOR REAL (industry + specialties) ==")
    for nome, n in contagem_setor.most_common():
        print(f"  {n:2}  {nome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

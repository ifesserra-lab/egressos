#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estima porte/origem/setor das empresas por LLM — a estratégia de ÚLTIMO recurso.

Só nomes de EMPRESA saem daqui para o serviço externo. Nome de egresso, nunca (memória do
projeto, fronteira de privacidade).

Este é o lado caro e não determinístico do par. O barato e determinístico mora em
`egressos_core.empresas` e roda em `pipeline/classify_empresas.py`, sem rede e sem chave. Por
isso, aqui, duas regras:

1. **A regra determinística vem primeiro.** Empresa cujo `headcount_linkedin` já responde o
   porte não é enviada ao modelo — é dado verificado contra estimativa, e gastar chamada nela
   seria pagar para piorar.
2. **A gravação é ADITIVA.** A versão anterior deste arquivo escrevia `empresas_porte.json`
   inteiro com o que o modelo devolvia: rodá-lo apagava headcount, sede, setor e URL
   coletados da company page — semanas de coleta verificada trocadas por estimativa. Agora o
   artefato é lido, os campos do modelo entram marcados com `fonte`, e o que já estava
   verificado permanece.

Uso:  python pipeline/mistral_porte.py         (exige MISTRAL_API_KEY em .env)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

from dotenv import load_dotenv

from egressos_core import dados, empresas
from egressos_core.paths import ROOT as BASE

LOTE = 35
MODELO = "mistral-large-latest"

SYS = ("Você é analista de mercado de trabalho de tecnologia no Brasil (Espírito Santo). "
       "Para cada EMPRESA da lista (empregadores de egressos de TI), classifique. "
       "porte ∈ {Startup, Scale-up, Média, Grande nacional, Multinacional/BigTech, Setor público, Desconhecida}. "
       "origem ∈ {Nacional, Internacional}. setor = curto (ex.: fintech, consultoria, saúde, e-commerce, software/produto, banco, governo, indústria, educação). "
       "funcionarios = faixa aproximada (ex.: '1-50','51-200','201-1000','1000-5000','5000+','?'). "
       "Se não reconhecer a empresa, use porte 'Desconhecida' e funcionarios '?'. NÃO invente. "
       'Responda SOMENTE JSON: {"empresas":[{"empresa":"","porte":"","origem":"","setor":"","funcionarios":""}]}')


def _mistral(chave: str, sistema: str, usuario: str) -> str:
    corpo = json.dumps({
        "model": MODELO, "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": sistema},
                     {"role": "user", "content": usuario}]}).encode()
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions", data=corpo,
        headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def pendentes(lista: list[str], porte_atual: dict) -> list[str]:
    """Empresas que o caminho determinístico NÃO resolve — as únicas que valem uma chamada."""
    faltando = []
    for nome in lista:
        ja = porte_atual.get(nome, {})
        if empresas.porte_por_headcount(ja.get("headcount_linkedin")):
            continue                      # dado verificado responde melhor que estimativa
        faltando.append(nome)
    return faltando


def main() -> int:
    load_dotenv(BASE / ".env")
    chave = os.environ.get("MISTRAL_API_KEY")
    if not chave:
        raise SystemExit(
            "ABORT: MISTRAL_API_KEY ausente. O caminho determinístico não precisa de chave: "
            "rode `python pipeline/classify_empresas.py`.")

    lista = dados.ler("_empresas_lista")
    porte = dados.ler("empresas_porte") if dados.caminho("empresas_porte").exists() else {}

    alvos = pendentes(lista, porte)
    print(f"{len(lista)} empresas; {len(lista) - len(alvos)} já resolvidas pelo headcount "
          f"verificado; {len(alvos)} vão ao modelo")

    estimadas = 0
    for i in range(0, len(alvos), LOTE):
        bloco = alvos[i:i + LOTE]
        pedido = "Empresas:\n" + "\n".join(f"- {e}" for e in bloco)
        try:
            resposta = json.loads(_mistral(chave, SYS, pedido)).get("empresas", [])
            for item in resposta:
                nome = item.get("empresa")
                if not nome:
                    continue
                # Aditivo: o que veio da company page permanece; o modelo só preenche o vazio.
                registro = porte.setdefault(nome, {})
                for campo in ("porte", "origem", "setor", "funcionarios"):
                    if item.get(campo):
                        registro[campo] = item[campo]
                registro["fonte"] = "mistral"
                estimadas += 1
            print(f"  lote {i // LOTE + 1}: {len(resposta)} classificadas (acum {estimadas})",
                  flush=True)
        except Exception as erro:                       # noqa: BLE001 - lote ruim não derruba
            print(f"  lote {i // LOTE + 1} ERRO: {erro}", flush=True)
        time.sleep(1)

    dados.gravar("empresas_porte", porte)
    print(f"TOTAL estimadas pelo modelo: {estimadas}/{len(alvos)} -> "
          f"{dados.caminho('empresas_porte')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
(b) Refina setor_real via Mistral usando industry_linkedin + specialties (dado PÚBLICO
de empresa). PRESERVA todos os campos de empresas_porte.json (não sobrescreve como
mistral_porte.py). Nenhum nome de egresso é enviado — só nome/industry/specialties da empresa.

Uso:  .venv/bin/python pipeline/classify_mistral.py            # só os que estão 'Outros'/sem setor_real
      .venv/bin/python pipeline/classify_mistral.py --all      # reclassifica todos os enriquecidos
"""
import os, json, time, pathlib, sys, urllib.request
from dotenv import load_dotenv

BASE = pathlib.Path("/caminho/para/salario")
load_dotenv(BASE / ".env")
KEY = os.environ["MISTRAL_API_KEY"]
PORTE = BASE / "data" / "empresas_porte.json"

TAXO = ["Fintech / Banco", "Games", "Saúde / Bio", "E-commerce / Varejo",
        "Consultoria / Serviços TI", "Dados / IA", "Segurança / Cyber",
        "Telecom / Redes", "Educação", "Governo / Defesa",
        "Indústria / Energia / Logística", "Software / Produto",
        "Mídia / Publicidade", "Esportes / Apostas", "Logística / Mobilidade", "Outros"]

SYS = ("Você classifica o SETOR de empresas (empregadores de egressos de TI). "
       "Use EXATAMENTE um rótulo desta lista para cada empresa: " + " | ".join(TAXO) + ". "
       "Baseie-se no nome + industry + specialties fornecidos (dado público do LinkedIn). "
       "Ex.: Armed Forces->Governo / Defesa; Hospital/Health->Saúde / Bio; Spectator Sports/betting->Esportes / Apostas; "
       "Advertising->Mídia / Publicidade; Banking/Payments/Insurance->Fintech / Banco; Retail/Wholesale->E-commerce / Varejo. "
       'Responda SOMENTE JSON: {"empresas":[{"empresa":"<nome>","setor":"<rótulo da lista>"}]}')

def mistral(user_p):
    body = json.dumps({"model": "mistral-large-latest", "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user_p}]}).encode()
    req = urllib.request.Request("https://api.mistral.ai/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["choices"][0]["message"]["content"]

def main():
    todos = "--all" in sys.argv
    porte = json.loads(PORTE.read_text(encoding="utf-8"))
    alvos = []
    for k, v in porte.items():
        if not (v.get("industry_linkedin") or v.get("specialties")):
            continue                                  # sem dado verificado -> pula
        if todos or v.get("setor_real") in (None, "Outros"):
            alvos.append(k)
    if not alvos:
        print("nada a refinar."); return
    print(f"refinando setor de {len(alvos)} empresas via Mistral…")
    linhas = []
    for k in alvos:
        v = porte[k]
        linhas.append(f'- {k} | industry: {v.get("industry_linkedin") or "-"} | specialties: {(v.get("specialties") or "-")[:180]}')
    CH = 25
    got = {}
    for i in range(0, len(linhas), CH):
        msg = "Empresas:\n" + "\n".join(linhas[i:i+CH])
        try:
            arr = json.loads(mistral(msg)).get("empresas", [])
            for o in arr:
                if o.get("empresa") and o.get("setor") in TAXO:
                    got[o["empresa"]] = o["setor"]
        except Exception as ex:
            print(f"  lote {i//CH+1} ERRO: {ex}")
        time.sleep(1)
    n = 0
    for k in alvos:
        if k in got:
            porte[k]["setor_real"] = got[k]
            porte[k]["setor_fonte"] = "mistral"
            n += 1
    PORTE.write_text(json.dumps(porte, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"refinadas {n}/{len(alvos)}.\n")
    from collections import Counter
    c = Counter(v.get("setor_real") for v in porte.values() if v.get("setor_real"))
    print("== SETOR REAL (após Mistral) ==")
    for s, m in c.most_common():
        print(f"  {m:2}  {s}")

if __name__ == "__main__":
    main()

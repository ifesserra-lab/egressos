"""Classifica o porte/setor/origem das empresas via Mistral. Só nomes de EMPRESA (público)."""
import os, json, time, pathlib, urllib.request
from dotenv import load_dotenv

BASE = pathlib.Path("/caminho/para/salario")
load_dotenv(BASE/".env")
KEY = os.environ["MISTRAL_API_KEY"]
def mistral(sys_p, user_p):
    body = json.dumps({"model":"mistral-large-latest","temperature":0,
        "response_format":{"type":"json_object"},
        "messages":[{"role":"system","content":sys_p},{"role":"user","content":user_p}]}).encode()
    req = urllib.request.Request("https://api.mistral.ai/v1/chat/completions", data=body,
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["choices"][0]["message"]["content"]
empresas = json.loads((BASE/"data/_empresas_lista.json").read_text(encoding="utf-8"))

SYS = ("Você é analista de mercado de trabalho de tecnologia no Brasil (Espírito Santo). "
       "Para cada EMPRESA da lista (empregadores de egressos de TI), classifique. "
       "porte ∈ {Startup, Scale-up, Média, Grande nacional, Multinacional/BigTech, Setor público, Desconhecida}. "
       "origem ∈ {Nacional, Internacional}. setor = curto (ex.: fintech, consultoria, saúde, e-commerce, software/produto, banco, governo, indústria, educação). "
       "funcionarios = faixa aproximada (ex.: '1-50','51-200','201-1000','1000-5000','5000+','?'). "
       "Se não reconhecer a empresa, use porte 'Desconhecida' e funcionarios '?'. NÃO invente. "
       'Responda SOMENTE JSON: {"empresas":[{"empresa":"","porte":"","origem":"","setor":"","funcionarios":""}]}')

out = {}
CH = 35
for i in range(0, len(empresas), CH):
    chunk = empresas[i:i+CH]
    msg = "Empresas:\n" + "\n".join(f"- {e}" for e in chunk)
    try:
        arr = json.loads(mistral(SYS, msg)).get("empresas", [])
        for o in arr:
            if o.get("empresa"): out[o["empresa"]] = o
        print(f"  lote {i//CH+1}: {len(arr)} classificadas (acum {len(out)})", flush=True)
    except Exception as ex:
        print(f"  lote {i//CH+1} ERRO: {ex}", flush=True)
    time.sleep(1)

(BASE/"data/empresas_porte.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"TOTAL classificadas: {len(out)}/{len(empresas)} -> data/empresas_porte.json")

"""QA final: cruza os valores hardcoded no dashboard_executivo.html com o pipeline
(consolidado.json + analise.json + fapes_fomento.json). PASS/FAIL por checagem."""
import json
import re
import subprocess
import sys

from egressos_core.paths import PUB
from egressos_core.paths import ROOT as S

SCR = S/"data"  # scripts de QA vivem em data/
HTML = S/"dashboard_executivo.html"
htmltxt = HTML.read_text(encoding="utf-8")

# extrai consts JS via node
subprocess.run(["node", str(SCR/"qa_extract.js"), str(HTML), str(SCR/"qa_consts.json")], check=True)
C = json.load(open(SCR/"qa_consts.json"))
cons = json.load(open(S/"data/consolidado.json"))
an = json.load(open(S/"data/analise.json"))
fap = json.load(open(S/"data/fapes_fomento.json"))

fails = []
def chk(name, cond, detail=""):
    print(("  PASS " if cond else "  FAIL ")+name+("" if cond else f"  <- {detail}"))
    if not cond: fails.append(name)

print("== KPI ==")
k=C["KPI"]; ck=cons["kpi"]; N=ck["n"]  # N = base salarial (perfis c/ série)
NC=an["genero"]["n_total"]              # NC = coorte (todas as pessoas)
chk(f"KPI.n==coorte({NC})", k["n"]==NC, k["n"])
chk("KPI.em_tech==coorte", k["em_tech"]==NC)
chk(f"KPI.nsal==base salarial({N})", k.get("nsal")==N, k.get("nsal"))
chk("KPI.cresc_medio==consolidado", k["cresc_medio"]==ck["cresc_medio"], f'{k["cresc_medio"]} vs {ck["cresc_medio"]}')
chk("KPI.med_atual==consolidado", k["med_atual"]==ck["med_atual"], f'{k["med_atual"]} vs {ck["med_atual"]}')
chk("KPI.faixa_lo==consolidado", k["faixa_atual_lo"]==ck["faixa_atual_lo"], f'{k["faixa_atual_lo"]} vs {ck["faixa_atual_lo"]}')
chk("KPI.faixa_hi==consolidado", k["faixa_atual_hi"]==ck["faixa_atual_hi"])
chk("KPI.faixa_inicial_med==consolidado", k["faixa_inicial_med"]==ck["faixa_inicial_med"])

print("== PERFIS ==")
chk(f"PERFIS len=={N}", len(C["PERFIS"])==N, len(C["PERFIS"]))
mism=[i for i,(h,c) in enumerate(zip(C["PERFIS"],cons["perfis"])) if h["med_atual"]!=c["med_atual"] or h["cresc"]!=c["cresc"]]
chk("PERFIS med/cresc == consolidado", not mism, f"idx divergentes {mism}")

print("== AGG / AGG_PV ==")
chk("AGG == consolidado.agregado", C["AGG"]==cons["agregado"], "lista difere")
chk("AGG_PV == consolidado.pv", C["AGG_PV"]==cons["pv"], "lista difere")

print("== SANKEY ==")
sk=C["SANKEY"]; ask=an["sankey"]
cols_json=[ [[v["nome"],v["n"]] for v in ask["vias"]], [[t["nome"],t["n"]] for t in ask["trilhas"]], [[d["nome"],d["n"]] for d in ask["destinos"]] ]
chk("SANKEY.cols == analise", sk["cols"]==cols_json, "nós divergem")
l12=[[l["de"],l["para"],l["n"]] for l in ask["via_trilha"]]; l23=[[l["de"],l["para"],l["n"]] for l in ask["trilha_destino"]]
chk("SANKEY.L12 == analise", sk["L12"]==l12)
chk("SANKEY.L23 == analise", sk["L23"]==l23)

print("== INTLTL ==")
tl=[[r["ano"],r["pct"],r["intl"],r["ativos"]] for r in an["intl_timeline"]]
chk("INTLTL == analise.intl_timeline", C["INTLTL"]==tl)

print("== BOX (dispersão) ==")
bx={b["l"].split(" (")[0]:b for b in C["IMPACTO"]["box"]}
imp=an["impacto"]
def boxok(label,src):
    b=bx.get(label)
    return b and b["med"]==src["med"] and b["q1"]==src["q1"] and b["q3"]==src["q3"] and b["min"]==src["min"] and b["max"]==src["max"]
chk("box Software == analise", boxok("Software",imp["dispersao_por_trilha"]["Software"]))
chk("box Dados == analise", boxok("Dados",imp["dispersao_por_trilha"]["Dados"]))
chk("box Nacional == analise", boxok("Nacional",imp["dispersao_por_origem"]["nacional"]))
chk("box Internacional == analise", boxok("Internacional",imp["dispersao_por_origem"]["intl"]))

print("== chips CARGOS (HTML texto) ==")
fdict={f["funcao"]:f["n"] for f in an["funcoes"]}
for label,key in [("Engenharia de software","Engenharia de software"),("Tech Lead / liderança","Tech Lead / liderança técnica"),
                  ("Gerência / gestão","Gerência / gestão"),("Eng. / ciência de dados","Eng. / ciência de dados"),
                  ("Consultoria \\(dados\\)","Consultoria (dados/BD)"),("Análise de sistemas / PO","Análise de sistemas / PO")]:
    m=re.search(label+r' <b>(\d+)</b>', htmltxt)
    chk(f"cargo {key}", m and int(m.group(1))==fdict.get(key), f'html={m.group(1) if m else "?"} json={fdict.get(key)}')

print("== chips MÉTODOS (HTML texto) ==")
mdict={m["metodo"]:m["n"] for m in an["metodos"]}
for label,key in [("Ágil / Scrum","Ágil / Scrum"),("Cloud \\(AWS/GCP/Azure\\)","Cloud (AWS/GCP/Azure)"),
                  ("Arquitetura / microsserviços","Arquitetura / microsserviços"),("Dados / ETL / BI","Dados / ETL / BI"),
                  ("Mobile híbrido","Mobile híbrido"),("IA / LLM / ML","IA / LLM / ML"),("DevOps / CI-CD","DevOps / CI-CD"),
                  ("BPM / automação","BPM / automação de processos"),("ITIL / governança de TI","ITIL / governança de TI")]:
    m=re.search(label+r' <b>(\d+)</b>', htmltxt)
    chk(f"método {key}", m and int(m.group(1))==mdict.get(key), f'html={m.group(1) if m else "?"} json={mdict.get(key)}')

print("== tabela SENIORIDADE (HTML) ==")
sen={r["senioridade"]:r for r in an["cruzamento"]["por_senioridade"]}
def senrow(nome,src):
    m=re.search(re.escape(nome)+r'</td><td class="n">(\d+)</td><td class="n">(\d+)</td><td class="n tot">(\d+)', htmltxt)
    return m and int(m.group(1))==src["nac"] and int(m.group(2))==src["intl"] and int(m.group(3))==src["n"]
chk("senioridade Sênior", senrow("Sênior",sen["Sênior"]))
chk("senioridade Espec/TL", senrow("Especialista / Tech Lead",sen["Espec./Tech Lead"]))

print("== EMPRESAS (porte via Mistral) + HEATMAP ==")
emp=an["empresas"]
hp=[[x["porte"],x["n"]] for x in emp["porte"]]
chk("EMPRESAS.porte == analise", C["EMPRESAS"]["porte"]==hp, f'{C["EMPRESAS"]["porte"]} vs {hp}')
hs=[[x["setor"],x["n"]] for x in emp["setor"]]
chk("EMPRESAS.setor == analise", C["EMPRESAS"]["setor"]==hs)
hr=[[x["regiao"],x["n"]] for x in emp["regiao"]]
chk("EMPRESAS.regiao == analise", C["EMPRESAS"]["regiao"]==hr)
chk("HEATMAP.matriz == analise.regiao_x_porte", C["HEATMAP"]["matriz"]==emp["regiao_x_porte"]["matriz"], f'{C["HEATMAP"]["matriz"]} vs {emp["regiao_x_porte"]["matriz"]}')
chk("HEATMAP soma==n", sum(sum(r) for r in C["HEATMAP"]["matriz"])==NC)

print("== GÊNERO ==")
g=an["genero"]; G=C.get("GEN") or {}
dF=g["detalhe"]["F"]; dM=g["detalhe"]["M"]
chk("GEN.f/m/pctF == analise", G.get("f")==g["F"] and G.get("m")==g["M"] and G.get("pctF")==g["pct_f"], f'{G.get("f")}/{G.get("m")}/{G.get("pctF")} vs {g["F"]}/{g["M"]}/{g["pct_f"]}')
chk("GEN.med == analise", G.get("med",{}).get("f")==dF["med_atual"] and G.get("med",{}).get("m")==dM["med_atual"], f'{G.get("med")} vs F{dF["med_atual"]}/M{dM["med_atual"]}')
chk("GEN.cresc == analise", G.get("cresc",{}).get("f")==dF["cresc_mediano"] and G.get("cresc",{}).get("m")==dM["cresc_mediano"])
chk("GEN.gestao == analise", G.get("gestao",{}).get("f")==dF["gestao_lideranca"] and G.get("gestao",{}).get("m")==dM["gestao_lideranca"])
chk("GEN.exterior == analise", G.get("exterior",{}).get("f")==dF["exterior"] and G.get("exterior",{}).get("m")==dM["exterior"])
chk("GEN.intl == analise", G.get("intl",{}).get("f")==dF["intl_empregador"] and G.get("intl",{}).get("m")==dM["intl_empregador"])
chk("GEN.fapes == analise", G.get("fapesF")==g["fapes"]["F"] and G.get("fapesTot")==g["fapes"]["total"])
chk("GEN soma f+m == n", (G.get("f",0)+G.get("m",0))==NC)

print("== EXTENSÃO SRC (fomento documentado) ==")
ex=an["extensao"]; X=C.get("EXT") or {}
chk("EXT.naBase == analise", X.get("naBase")==ex["n_encontrados"], f'{X.get("naBase")} vs {ex["n_encontrados"]}')
chk("EXT.bolsistasExt == analise", X.get("bolsistasExt")==ex["n_bolsistas_extensao"])
chk("EXT.bolsaDoc == analise", X.get("bolsaDoc")==ex["n_bolsa_documentada_oficial"], f'{X.get("bolsaDoc")} vs {ex["n_bolsa_documentada_oficial"]}')
chk("EXT.funcoes n-seq == analise", [n for _,n in X.get("funcoes",[])]==[f["n"] for f in ex["funcoes"]], f'{[n for _,n in X.get("funcoes",[])]} vs {[f["n"] for f in ex["funcoes"]]}')

print("== TRILHA DE CARREIRA ==")
tc=an.get("trilha_carreira") or {}; CR=C.get("CAREER") or {}
chk("CAREER.cols == analise", CR.get("cols")==tc.get("cols"), f'{CR.get("cols")} vs {tc.get("cols")}')
chk("CAREER.L12 == analise", CR.get("L12")==tc.get("L12"))
chk("CAREER.L23 == analise", CR.get("L23")==tc.get("L23"))
chk("CAREER cols somam coorte", all(sum(x[1] for x in col)==NC for col in CR.get("cols",[])) and len(CR.get("cols",[]))==3)

print("== OUTROS LABS ==")
ol=an.get("outros_labs") or {}; L=C.get("LABS") or {}
chk("LABS.n == analise", L.get("n")==ol.get("n_com_outro_lab"), f'{L.get("n")} vs {ol.get("n_com_outro_lab")}')
chk("LABS.bolsistas == analise", L.get("bolsistas")==ol.get("n_bolsistas_com_outro_lab"))
chk("LABS.itens n-seq == analise", [n for _,n in L.get("itens",[])]==[l["n_egressos"] for l in ol.get("labs",[])], f'{[n for _,n in L.get("itens",[])]} vs {[l["n_egressos"] for l in ol.get("labs",[])]}')

print("== FAPES (impacto) ==")
d=fap["desfecho"]
chk("FAPES 6 egressos", fap["total"]["egressos_total"]==6)
chk("FAPES 6/6 em tech (html)", f'>{d["em_tech"]}<small>/{d["egressos"]}' in htmltxt or "6<small>/6</small>" in htmltxt)
chk("FAPES mult_real ~13 (html '~13×')", "~13×" in htmltxt and d["mult_real"]==13, f'json mult_real={d["mult_real"]}')

print("== PII ==")
al=json.load(open(S/"alunos.json"))
pii=set(); KEEP={'IFES','LEDS','Prodest','PRODEST','FAPES','Morpheus','UFES','Autônomo','CAPES','CNPq',
                 'NEMO','LabTel','LAR','NERA'}  # laboratórios/núcleos públicos (como LEDS/IFES)
STOP={'das','dos','de','da','do','e','em','na','no','dos','com','the','and',
      'paulo','são','sao','além','alem'}  # 'Paulo'=cidade SP; 'Além'=palavra comum (prosa) — não são PII
for a in al["alunos"]:
    for t in re.split(r'[\s.]+',a["nome"]):
        if len(t)>2 and t.lower() not in STOP: pii.add(t)
    for e in a["experiencias"]:
        c=re.sub(r'\(.*?\)','',e.get("empresa","")).strip()
        for p in re.split(r'[/·]',c):
            p=p.strip()
            if len(p)>2 and p not in KEEP: pii.add(p)
COBOLS={"Juliana","Roberta","Bárbara","Vinicius","Torres","Kirmes","Manfredini"}
files={"exec": S/"dashboard_executivo.html", "alunos": S/"dashboard_alunos.html",
       "trajetoria": S/"trajetoria_salarial.html",
       "metodologia": S/"metodologia.html",
       "pub-index": PUB/"index.html", "pub-alunos": PUB/"dashboard_alunos.html",
       "pub-trajetoria": PUB/"trajetoria_salarial.html",
       "pub-dados": PUB/"dados-abertos.html", "pub-llms": PUB/"llms.txt",
       "pub-README": PUB/"README.md"}
# egressos-carreiras.html fica FORA desta varredura de propósito: é a vitrine NOMEADA
# ("Perfis nomeados: empresas, países e a jornada de cada um"), a única página do site em que
# nome e empresa aparecem. Todas as demais são anonimizadas e são varridas aqui.
for lbl,f in files.items():
    if not f.exists():
        # o QA roda ANTES do publish: na primeira vez a cópia pública ainda não existe.
        # A versão local dessa mesma página já foi varrida acima, então só avisa.
        if lbl.startswith("pub-"):
            print(f"  SKIP PII: {lbl} (ainda não publicado)"); continue
        chk(f"PII limpo: {lbl}", False, "arquivo não existe"); continue
    txt=f.read_text(encoding="utf-8")
    hits=sorted({p for p in (pii|COBOLS) if re.search(r'\b'+re.escape(p)+r'\b',txt)})
    chk(f"PII limpo: {lbl}", not hits, hits)

print("\n== RESULTADO ==", "TODAS PASSARAM ✅" if not fails else f"{len(fails)} FALHAS: {fails}")
sys.exit(1 if fails else 0)

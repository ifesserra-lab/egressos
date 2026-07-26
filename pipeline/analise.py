"""
Análise dos egressos (alunos.json): clusters, tecnologias, insights e comparação
com as bases externas usadas (Stack Overflow survey via consolidado.json e Código Fonte 2026).
Sem sklearn — KMeans em numpy (n pequeno). Saída: data/analise.json + insights no stdout.
"""
import json, numpy as np, pathlib, collections, re

BASE = pathlib.Path("/caminho/para/salario")
al = json.load(open(BASE/"alunos.json"))["alunos"]
cons = json.load(open(BASE/"data/consolidado.json"))
cf = json.load(open(BASE/"data/codigofonte_2026.json"))
cfh = json.load(open(BASE/"data/codigofonte_historico.json"))

HOJE_Y = 2026 + 6/12  # ~jul/2026
def ymnum(s): y,m=s.split("-"); return int(y)+(int(m)-1)/12
def anos_exp(a): return round(HOJE_Y - ymnum(a["inicio_carreira_dev"]),1)

# ---------- 1) TECNOLOGIAS ----------
# normaliza skills (linguagens/frameworks/plataformas) — ignora conceitos soft
NORM = {
  "nodejs":"Node.js","node":"Node.js","nestjs":"NestJS","asp.net":".NET",".net":".NET",
  "c#":"C#","react native":"React Native","react":"React","vue":"Vue","angular":"Angular",
  "angularjs":"Angular","postgres":"PostgreSQL","postgresql":"PostgreSQL","mongodb":"MongoDB",
  "graphql":"GraphQL","docker":"Docker","kubernetes":"Kubernetes","aws":"AWS","gcp":"GCP",
  "mongodb":"NoSQL","mongo":"NoSQL",
  "azure ml":"Azure","go":"Go","python":"Python","java":"Java","kotlin":"Kotlin","php":"PHP",
  "laravel":"Laravel","ionic":"Ionic","flutter":"Flutter","spring":"Spring","django":"Django",
  "typescript":"TypeScript","javascript":"JavaScript","power bi":"Power BI","rx":"RxJava",
  "hilt":"Hilt","dagger":"Dagger","compose":"Jetpack Compose","mvvm":"MVVM","sql":"SQL",
  "etl":"ETL","databricks":"Databricks","mlflow":"MLflow","mlops":"MLOps","xamarin":"Xamarin",
  "rasa":"Rasa","redis":"Redis","webserver":"","websocket":"WebSocket","bi":"BI",
}
CONCEITO = {"backend","frontend","fullstack","dev","web","mobile","arquitetura","observabilidade",
            "liderança","gestão de projetos","gestão técnica","integrações","consultoria",
            "análise de dados","data science","scrum","bdd","devops"}
tech_counter = collections.Counter()
tech_people = collections.defaultdict(set)
for a in al:
    for e in a["experiencias"]:
        for sk in e.get("skills",[]):
            k = sk.strip().lower()
            if k in CONCEITO: continue
            name = NORM.get(k, sk.strip())
            if not name: continue
            tech_counter[name]+=1
            tech_people[name].add(a["id"])
top_tech = sorted(tech_counter.items(), key=lambda kv:(-len(tech_people[kv[0]]), -kv[1]))
top_tech = [{"tech":t,"pessoas":len(tech_people[t]),"mencoes":c} for t,c in top_tech][:15]

# ---------- 2) FEATURES + CLUSTER (KMeans numpy) ----------
TRACKD = {"backend":0,"frontend":0,"fullstack":0,"dev":0,"mobile":0,"lideranca":0,"data":1,"ml":1}
def track_atual(a):
    if a.get("perfil_tech")=="data" or a["area_atual"] in ("data","ml"): return 1
    return 0
def comecou_bolsa(a):
    sy=a["inicio_carreira_dev"][:4]
    for e in a["experiencias"]:
        if e["inicio"][:4]==sy and (e.get("fonte_bolsa") or e["tipo"] in ("Estágio","Bolsa","Extensão")):
            return 1
    return 0
def exterior(a):
    loc=(a.get("local_atual") or "").lower()
    return 1 if any(x in loc for x in ["london","londres","portugal","chile","us","reino","exterior"]) else 0
def tem_lideranca(a):
    return 1 if any(e["area"]=="lideranca" for e in a["experiencias"]) or "lead" in (a["cargo_atual"] or "").lower() or "coorden" in (a["cargo_atual"] or "").lower() else 0

# MESMA ordem/labels do compute_all.py (para casar com cons["perfis"] por índice)
order = ["barbosa","gary","possatti","helen","renan","andre","tarcisio","joel","icaro","gustavo","marialuiza",
         "gabriel_barboza","magnago","martins_miranda","geann","rodrigo_maia","andre_aguiar",
         "guilherme_gatti","ivana","joao_paulo","lucas_coutinho","marcos_dias","phillipe",
         "anne_caroline","brendon","cassiano","jennifer","ana_rubia",
         "diego","edvaldo","magno","pedro","antonio","cristian","danilo","marlon","breno",
         "caio","lucas_gomes","derick","marcos_carneiro","mateus_garcia","ana_carolina","david_pantaleao","renato","kleber","rafael","andreangelo","icaro_gandine","paulo_ricardo"]
labels = ["A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z","AA","AB","AC","AD","AE","AF","AG","AH","AI","AJ","AK","AL","AM","AN","AO","AP","AQ","AR","AS","AT","AU","AV","AW","AX"]
idlabel = dict(zip(order,labels))
labelid = dict(zip(labels,order))
# med_atual por id, casando por LABEL (robusto a perfis puladas no compute_all, ex.: gestão sem série)
def _perfil_by_id():
    m={}
    for p in cons["perfis"]:
        lab=p["perfil"].replace("Perfil ","").strip()
        if lab in labelid: m[labelid[lab]]=p
    return m
_perfil_id=_perfil_by_id()
medatual = {pid:p["med_atual"] for pid,p in _perfil_id.items()}

# origem da empresa ATUAL: nacional (BR) x internacional (sede/contrato no exterior)
EMPRESA_ORIGEM = {
  "Metris Energy":"intl","Doris":"intl","MongoDB":"intl","Bliss Applications":"intl","Kranio":"intl",
  "Cognyte":"intl","Akamai Technologies":"intl","Sporty Group":"intl",
  "Marinha do Brasil":"nacional","BTG Pactual":"nacional","AEVO":"nacional","Vennx":"nacional","PicPay":"nacional",
  "Accenture Brasil":"nacional","Pottencial":"nacional","Neon":"nacional","Banestes":"nacional",
  "Mercado Livre":"intl","King":"intl","Truelogic Software":"intl","Truelogic":"intl",
}
def origem(a):
    o = EMPRESA_ORIGEM.get(a["empresa_atual"])
    if o: return o
    return "intl" if exterior(a) else "nacional"

def senioridade(a):
    if not a["ainda_em_tech"]: return "Fora de tech"
    c=(a["cargo_atual"] or "").lower()
    if any(x in c for x in ["lead","coorden","principal","staff","especialista"]): return "Espec./Tech Lead"
    if "sênior" in c or "senior" in c: return "Sênior"
    if "pleno" in c: return "Pleno"
    if any(x in c for x in ["júnior","junior","estag"]): return "Júnior"
    y=anos_exp(a)  # fallback por tempo de casa
    return "Espec./Tech Lead" if y>=11 else "Sênior" if y>=6 else "Pleno" if y>=3 else "Júnior"

rows=[]
for a in al:
    n_emp = len({e["empresa"] for e in a["experiencias"] if e["area"] in TRACKD})
    rows.append({
        "id":a["id"],"label":idlabel.get(a["id"],"?"),
        "anos":anos_exp(a),"n_empresas":n_emp,"n_exp":len(a["experiencias"]),
        "trilha":track_atual(a),"em_tech":int(a["ainda_em_tech"]),
        "exterior":exterior(a),"bolsa_ini":comecou_bolsa(a),"lideranca":tem_lideranca(a),
        "area_atual":a["area_atual"],"cargo_atual":a["cargo_atual"],
        "empresa_atual":a["empresa_atual"],"origem":origem(a),"senioridade":senioridade(a),
        "med_atual":medatual.get(a["id"]),
    })

FEATS=["anos","n_empresas","trilha","em_tech","exterior","bolsa_ini","lideranca"]
X=np.array([[r[f] for f in FEATS] for r in rows],dtype=float)
mu,sd=X.mean(0),X.std(0); sd[sd==0]=1; Z=(X-mu)/sd

def kmeans(Z,k,iters=100,seed=0):
    rng=np.random.RandomState(seed); C=Z[rng.choice(len(Z),k,replace=False)]
    for _ in range(iters):
        d=((Z[:,None,:]-C[None,:,:])**2).sum(2); lab=d.argmin(1)
        newC=np.array([Z[lab==j].mean(0) if (lab==j).any() else C[j] for j in range(k)])
        if np.allclose(newC,C): C=newC; break
        C=newC
    inertia=((Z-C[lab])**2).sum()
    return lab,inertia
best=None
for seed in range(20):
    lab,inr=kmeans(Z,3,seed=seed)
    if best is None or inr<best[1]: best=(lab,inr,seed)
clusters=best[0]
for r,c in zip(rows,clusters): r["cluster"]=int(c)

# rótulo descritivo de cada cluster
cl_desc={}
for c in sorted(set(int(x) for x in clusters)):
    mem=[r for r in rows if r["cluster"]==c]
    cl_desc[c]={
        "n":len(mem),"labels":[m["label"] for m in mem],
        "anos_medio":round(np.mean([m["anos"] for m in mem]),1),
        "trilha":"Dados" if np.mean([m["trilha"] for m in mem])>0.5 else "Software",
        "exterior":sum(m["exterior"] for m in mem),
        "lideranca":sum(m["lideranca"] for m in mem),
        "em_tech":sum(m["em_tech"] for m in mem),
        "cargos":[m["cargo_atual"] for m in mem],
    }

# ---------- 3) INSIGHTS ----------
n=len(rows)
insights={
  "n":n,
  "trilha_software":sum(1 for r in rows if r["trilha"]==0),
  "trilha_dados":sum(1 for r in rows if r["trilha"]==1),
  "em_tech":sum(r["em_tech"] for r in rows),
  "exterior":sum(r["exterior"] for r in rows),
  "comecou_bolsa":sum(r["bolsa_ini"] for r in rows),
  "tem_lideranca":sum(r["lideranca"] for r in rows),
  "anos_medio":round(np.mean([r["anos"] for r in rows]),1),
  "empresas_media":round(np.mean([r["n_empresas"] for r in rows]),1),
  "tenure_medio_anos":round(np.mean([r["anos"]/max(r["n_empresas"],1) for r in rows]),1),
}

# ---------- 4) COMPARAÇÃO COM BASES EXTERNAS ----------
kpi=cons["kpi"]; agg={d["exp"]:d for d in cons["agregado"]}; pv={d["exp"]:d for d in cons["pv"]}
cf2026={"Estágio":cfh["media_por_senioridade"]["2026"]["estagio"],
        "Júnior":cfh["media_por_senioridade"]["2026"]["junior"],
        "Pleno":cfh["media_por_senioridade"]["2026"]["pleno"],
        "Sênior":cfh["media_por_senioridade"]["2026"]["senior"],
        "Espec./TL":cfh["media_por_senioridade"]["2026"]["espec"]}
# egressos sênior atual (mediana atual) vs CF Sênior
comp={
  "egressos_med_atual": kpi["med_atual"],
  "cf_senior_2026": round(cf2026["Sênior"]),
  "cf_espec_2026": round(cf2026["Espec./TL"]),
  "egressos_vs_cf_senior_pct": round(100*(kpi["med_atual"]/cf2026["Sênior"]-1)),
  # trajetória: egressos (SO valor da época) vs mercado a valores de hoje (SO 2026) em exp selecionados
  "por_exp":[{"exp":e,"egressos_epoca":agg[e]["med"],"mercado_hoje":pv[e]["med"]}
             for e in [0,3,5,8,11,14] if e in agg and e in pv],
}
# tech dos egressos que estão entre as + bem pagas do Código Fonte (linguagens)
cf_langs = cf.get("linguagens") or cf.get("languages") or {}
top_tech_names={t["tech"] for t in top_tech}

# ---------- 5) CRUZAMENTO senioridade x origem (nacional/intl) + salário ----------
SEN_ORD=["Júnior","Pleno","Sênior","Espec./Tech Lead","Fora de tech"]
tech_rows=[r for r in rows if r["senioridade"]!="Fora de tech"]
def med(v): v=[x for x in v if x is not None]; return int(np.median(v)) if v else None
cross={"por_senioridade":[],"por_origem":{},"cruzamento":[]}
for s in SEN_ORD:
    mem=[r for r in rows if r["senioridade"]==s]
    if not mem: continue
    cross["por_senioridade"].append({"senioridade":s,"n":len(mem),
        "labels":[m["label"] for m in mem],
        "med_atual":med([m["med_atual"] for m in mem if m["med_atual"]]),
        "nac":sum(1 for m in mem if m["origem"]=="nacional"),
        "intl":sum(1 for m in mem if m["origem"]=="intl")})
for o in ["nacional","intl"]:
    mem=[r for r in tech_rows if r["origem"]==o]
    cross["por_origem"][o]={"n":len(mem),"labels":[m["label"] for m in mem],
        "empresas":sorted({m["empresa_atual"] for m in mem}),
        "med_atual":med([m["med_atual"] for m in mem]),
        "anos_medio":round(np.mean([m["anos"] for m in mem]),1)}
# matriz senioridade x origem
for s in SEN_ORD:
    row={"senioridade":s}
    for o in ["nacional","intl"]:
        mm=[r for r in rows if r["senioridade"]==s and r["origem"]==o]
        row[o]={"n":len(mm),"labels":[m["label"] for m in mm],"med":med([m["med_atual"] for m in mm if m["med_atual"]])}
    if row["nacional"]["n"] or row["intl"]["n"]: cross["cruzamento"].append(row)
prem=None
if cross["por_origem"]["intl"]["med_atual"] and cross["por_origem"]["nacional"]["med_atual"]:
    prem=round(100*(cross["por_origem"]["intl"]["med_atual"]/cross["por_origem"]["nacional"]["med_atual"]-1))
cross["premio_intl_vs_nac_pct"]=prem

# ---------- 6) CARGOS/FUNÇÕES ATUAIS (não trilha) ----------
FUNC_ORD=["Engenharia de software","Tech Lead / liderança técnica","Gerência / gestão",
          "Eng. / ciência de dados","Consultoria (dados/BD)","Análise de sistemas / PO"]
def funcao(a):
    c=(a["cargo_atual"] or "").lower()
    if "gerente" in c or "manager" in c: return "Gerência / gestão"
    if "lead" in c or "coorden" in c:    return "Tech Lead / liderança técnica"
    if "consult" in c:                   return "Consultoria (dados/BD)"
    if "dados" in c or "data" in c:      return "Eng. / ciência de dados"
    if "analista de sistema" in c or "product owner" in c: return "Análise de sistemas / PO"
    return "Engenharia de software"
func_ct=collections.Counter(funcao(a) for a in al)
funcoes=[{"funcao":f,"n":func_ct[f]} for f in FUNC_ORD if func_ct.get(f)]
lid_gestao={"gestao":func_ct.get("Gerência / gestão",0),
            "lideranca_tecnica":func_ct.get("Tech Lead / liderança técnica",0)}
lid_gestao["total"]=lid_gestao["gestao"]+lid_gestao["lideranca_tecnica"]

# ---------- 7) MÉTODOS / PRÁTICAS (minera skills + descricao; presença por egresso) ----------
METODOS={
  "Ágil / Scrum":["scrum","agile","ágil","agil","kanban"," xp ","bdd","product owner","backlog","sprint"],
  "Cloud (AWS/GCP/Azure)":["aws","gcp","azure","cloud","serverless","ec2","lambda","redshift","emr","glue","s3"],
  "Dados / ETL / BI":["etl","pentaho","power bi","data science","databricks","analytics","hadoop","spark","big data","data lake","hive","impala","dado"],
  "Mobile híbrido":["ionic","flutter","react native","xamarin"],
  "IA / LLM / ML":["mlops","mlflow","machine learning","llm","chatbot","rasa","dialogflow","reconhecimento","modelos analíticos"," ia ","ml "],
  "Arquitetura / microsserviços":["arquitetura","microserviç","microsserviç","microservice","sistemas distribuídos","kubernetes","k8s"],
  "DevOps / CI-CD":["devops","ci/cd","ci-cd","pipeline","bitrise","jenkins"],
  "BPM / automação de processos":["bpm","rpa","workflow","automidia","neomind","automação"],
  "ITIL / governança de TI":["itil","cobit","lgpd","governança"],
  "Observabilidade / monitoramento":["observabilidade","monitoramento","grafana","zabbix","nagios","cacti"],
}
def texto(a):
    return " ".join((e.get("descricao","")+" "+" ".join(e.get("skills",[]))) for e in a["experiencias"]).lower()
metodos=[]
for nome,kws in METODOS.items():
    cnt=sum(1 for a in al if any(k in texto(a) for k in kws))
    if cnt: metodos.append({"metodo":nome,"n":cnt})
metodos.sort(key=lambda x:-x["n"])

# ---------- 8) INDICADORES DE IMPACTO ----------
def q(vals, p):
    vals = sorted(x for x in vals if x is not None)
    if not vals: return None
    import math
    i = p*(len(vals)-1); lo=math.floor(i); hi=math.ceil(i)
    return round(vals[lo] + (vals[hi]-vals[lo])*(i-lo))
def box(vals):
    vals=[v for v in vals if v is not None]
    if not vals: return None
    return {"n":len(vals),"min":min(vals),"q1":q(vals,.25),"med":q(vals,.5),"q3":q(vals,.75),"max":max(vals)}

INTL_KW=["metris","doris","mongodb","bliss","kranio","cognyte","akamai","sporty","ibm","achieve",
         "google","microsoft","amazon","thoughtworks","oracle","sap","dell","avanade"]
def emp_intl(empresa):
    t=(empresa or "").lower()
    if EMPRESA_ORIGEM.get(empresa)=="intl": return True
    return any(k in t for k in INTL_KW)
def exp_1o_intl(a):
    sy=ymnum(a["inicio_carreira_dev"])
    anos=[ymnum(e["inicio"])-sy for e in a["experiencias"] if emp_intl(e.get("empresa"))]
    return round(min(anos),1) if anos else None
def passou(a, kws):
    return any(any(k in (str(e.get("empresa",""))+" "+str(e.get("cargo",""))).lower() for k in kws)
               for e in a["experiencias"])

seniores=[r for r in rows if r["senioridade"] in ("Sênior","Espec./Tech Lead")]
intl_now=[a for a in al if origem(a)=="intl"]
exp_intl_vals=[exp_1o_intl(a) for a in al if exp_1o_intl(a) is not None]
med_by_trilha={"Software":[],"Dados":[]}
med_by_origem={"nacional":[],"intl":[]}
for r in rows:
    tr="Dados" if r["trilha"]==1 else "Software"
    if r["med_atual"]: med_by_trilha[tr].append(r["med_atual"]); med_by_origem[r["origem"]].append(r["med_atual"])
# matriz trilha x senioridade
SENS=["Sênior","Espec./Tech Lead"]
trilha_sen={tr:{s:0 for s in SENS} for tr in ("Software","Dados")}
for r in rows:
    tr="Dados" if r["trilha"]==1 else "Software"
    if r["senioridade"] in SENS: trilha_sen[tr][r["senioridade"]]+=1
# cobertura da pesquisa
import pathlib as _pl
def _count(fn):
    p=BASE/fn
    if not p.exists(): return None
    return sum(1 for l in p.read_text(encoding="utf-8").splitlines() if "->" in l and not l.startswith("#"))
impacto={
  "n":len(rows),
  "multiplicador_medio":kpi["cresc_medio"] if "cresc_medio" in kpi else insights["n"],
  "tempo_ate_senior_mediana_anos": q([r["anos"] for r in seniores], .5),
  "exp_medio_senior": round(np.mean([r["anos"] for r in rows if r["senioridade"]=="Sênior"]),1) if any(r["senioridade"]=="Sênior" for r in rows) else None,
  "exp_medio_espec": round(np.mean([r["anos"] for r in rows if r["senioridade"]=="Espec./Tech Lead"]),1) if any(r["senioridade"]=="Espec./Tech Lead" for r in rows) else None,
  "lideram_hoje": lid_gestao["total"],
  "passaram_lideranca": insights["tem_lideranca"],
  "intl_hoje": len(intl_now),
  "exp_medio_1o_emprego_intl": round(np.mean(exp_intl_vals),1) if exp_intl_vals else None,
  "premio_intl_pct": cross["premio_intl_vs_nac_pct"],
  "retencao_tech": f'{insights["em_tech"]}/{insights["n"]}',
  "origem": {
    "monitoria_ensino": sum(1 for a in al if passou(a,["monitor","monitoria","tutoria"]) or any(e["area"]=="academico" for e in a["experiencias"])),
    "pesquisa_ic_fapes": sum(1 for a in al if passou(a,["prodest","fapes","capes","iniciação","pibic","bolsista","ic)"])),
    "extensao_leds": sum(1 for a in al if passou(a,["leds"])),
    "empresa_junior_morpheus": sum(1 for a in al if passou(a,["morpheus"])),
  },
  "dispersao_por_trilha": {k:box(v) for k,v in med_by_trilha.items()},
  "dispersao_por_origem": {k:box(v) for k,v in med_by_origem.items()},
  "trilha_x_senioridade": trilha_sen,
  "cobertura": {"encontrados": _count("encontrados.txt"), "nao_encontrados": _count("nao_encontrados.txt")},
}

# ---------- 9) SANKEY (via de formação -> trilha -> destino) ----------
def via_principal(a):
    if passou(a,["leds"]): return "Extensão (IFES)"
    if passou(a,["prodest","fapes","capes","iniciação","pibic","bolsista","ic)"]): return "Pesquisa (IC/FAPES)"
    if passou(a,["monitor","monitoria","tutoria"]) or any(e["area"]=="academico" for e in a["experiencias"]): return "Ensino (monitoria)"
    if passou(a,["morpheus"]): return "Empresa júnior"
    return "Não detectada no LinkedIn"
VIA_ORD=["Extensão (IFES)","Pesquisa (IC/FAPES)","Ensino (monitoria)","Empresa júnior","Não detectada no LinkedIn"]
TRI=["Software","Dados"]; DES=["Nacional","Internacional"]
def trilha_de(a): return "Dados" if track_atual(a)==1 else "Software"
def destino_de(a): return "Internacional" if origem(a)=="intl" else "Nacional"
via_of={a["id"]:via_principal(a) for a in al}
s12=collections.Counter(); s23=collections.Counter()
node_via=collections.Counter(); node_tri=collections.Counter(); node_des=collections.Counter()
for a in al:
    v,tr,de=via_of[a["id"]],trilha_de(a),destino_de(a)
    s12[(v,tr)]+=1; s23[(tr,de)]+=1
    node_via[v]+=1; node_tri[tr]+=1; node_des[de]+=1
sankey={
  "vias":[{"nome":v,"n":node_via[v]} for v in VIA_ORD if node_via[v]],
  "trilhas":[{"nome":t,"n":node_tri[t]} for t in TRI if node_tri[t]],
  "destinos":[{"nome":d,"n":node_des[d]} for d in DES if node_des[d]],
  "via_trilha":[{"de":v,"para":t,"n":n} for (v,t),n in sorted(s12.items(),key=lambda x:-x[1])],
  "trilha_destino":[{"de":t,"para":d,"n":n} for (t,d),n in sorted(s23.items(),key=lambda x:-x[1])],
}

# ---------- 10) INTERNACIONALIZAÇÃO AO LONGO DO TEMPO ----------
def ano_1o_intl(a):
    ys=[int(e["inicio"][:4]) for e in a["experiencias"] if emp_intl(e.get("empresa"))]
    return min(ys) if ys else None
def ano_inicio(a): return int(a["inicio_carreira_dev"][:4])
Y0,Y1=2012,2026
intl_timeline=[]
for Y in range(Y0,Y1+1):
    ativos=sum(1 for a in al if ano_inicio(a)<=Y)                      # já começaram a carreira
    intl=sum(1 for a in al if (ano_1o_intl(a) or 9999)<=Y)            # já alcançaram empregador intl (acumulado)
    intl_timeline.append({"ano":Y,"ativos":ativos,"intl":intl,
                          "pct":round(100*intl/ativos) if ativos else 0})

# ---------- 11) EMPRESAS & REGIÕES (agregado, anonimizado) ----------
def regiao(loc):
    l=(loc or "").lower()
    if any(x in l for x in ["london","londres","portugal","chile","eua"," us","reino","irlanda","dublin","argentina","exterior"]): return "Exterior"
    if any(x in l for x in ["vitória","vitoria","serra","vila velha","cariacica","viana","espírito","espirito"," es"]): return "ES — Grande Vitória"
    if "remot" in l or l.strip() in ("","remote","remoto","brasil","brazil"): return "Remoto / não-declarado"
    if any(x in l for x in ["são paulo","sao paulo"," sp"]): return "São Paulo"
    if any(x in l for x in ["rio de janeiro"," rj"]): return "Rio de Janeiro"
    if any(x in l for x in ["santa catarina","florian"," sc"]): return "Santa Catarina"
    return "Outro (BR)"
def modalidade_atual(loc):
    l=(loc or "").lower()
    return "Remoto" if "remot" in l else ("Híbrido" if ("híbr" in l or "hibr" in l) else "Presencial / não-declarado")
SET={"Produto / scale-up / startup":["aevo","vennx","kranio","velv","doris","drivin","bliss","beebee","gen-t","allware","neomed"],
     "Fintech / banco":["will bank","picpay","btg","banestes","neon","paraná banco","parana banco","pottencial","pagbank","pag!"],
     "BigTech / software global":["mongodb","akamai","ibm","google","microsoft","king","sporty"],
     "Consultoria / serviços globais":["accenture","truelogic","thoughtworks","cognyte","globant","ci&t","avanade"],
     "Saúde":["albert einstein","unimed","emescam"],
     "Varejo / e-commerce":["mercado livre","boticário","boticario","soares atacado"],
     "Energia / indústria":["metris","senior"],
     "Setor público / defesa":["marinha","tribunal","prefeitura"]}
def _cls(c,m,default):
    t=(c or "").lower()
    for k,kws in m.items():
        if any(w in t for w in kws): return k
    return default
# porte/origem do EMPREGADOR ATUAL: classificação via Mistral AI (data/empresas_porte.json).
# Só nomes de EMPRESA foram enviados ao modelo (dado público) — nunca nomes de egressos.
_MPORTE=json.load(open(BASE/"data/empresas_porte.json"))
_PBKT={"Multinacional/BigTech":"Multinacional / BigTech","Grande nacional":"Grande nacional",
       "Média":"Média nacional","Startup":"Startup / scale-up","Scale-up":"Startup / scale-up",
       "Setor público":"Setor público","Desconhecida":"Não classificada"}
def _emp_clean(c): return re.sub(r"\s*\(.*?\)","",(c or "")).strip()
def porte_atual(a):
    m=_MPORTE.get(_emp_clean(a["empresa_atual"]),{})
    return _PBKT.get(m.get("porte","Desconhecida"),"Não classificada")
def origem_empregador(a):
    return _MPORTE.get(_emp_clean(a["empresa_atual"]),{}).get("origem","Desconhecida")
regc=collections.Counter(regiao(a.get("local_atual")) for a in al)
modc=collections.Counter(modalidade_atual(a.get("local_atual")) for a in al)
setc=collections.Counter(_cls(a["empresa_atual"],SET,"Outros / nacional") for a in al)
porc=collections.Counter(porte_atual(a) for a in al)
oric=collections.Counter(origem_empregador(a) for a in al)
empc=collections.defaultdict(set)
for a in al:
    for e in a["experiencias"]:
        c=re.sub(r"\s*\(.*?\)","",e.get("empresa","")).strip()
        if c and c not in ("—","Autônomo") and not any(x in c for x in ("LEDS","IFES","Prodest","Morpheus","CAPES","Universidade")):
            empc[c].add(a["id"])
top_local=max((len(v) for v in empc.values()), default=0)
# matriz Região (4 buckets) × Porte (heatmap)
def reg4(loc):
    r=regiao(loc)
    if r=="ES — Grande Vitória": return "ES"
    if r=="Remoto / não-declarado": return "Remoto/ND"
    if r=="Exterior": return "Exterior"
    return "Outro BR"
REG_ORD=["ES","Remoto/ND","Outro BR","Exterior"]
POR_ORD=["Multinacional / BigTech","Grande nacional","Média nacional","Startup / scale-up","Setor público","Não classificada"]
rxp={rg:{p:0 for p in POR_ORD} for rg in REG_ORD}
for a in al:
    rxp[reg4(a.get("local_atual"))][porte_atual(a)]+=1
# porte por EMPRESA DISTINTA (base Mistral, todas as 157 empresas da trajetória)
porc_dist=collections.Counter(_PBKT.get(v.get("porte","Desconhecida"),"Não classificada") for v in _MPORTE.values())
empresas={
  "regiao":[{"regiao":k,"n":n} for k,n in regc.most_common()],
  "modalidade":[{"modalidade":k,"n":n} for k,n in modc.most_common()],
  "setor":[{"setor":k,"n":n} for k,n in setc.most_common()],
  "porte":[{"porte":k,"n":n} for k,n in porc.most_common()],
  "porte_fonte":"Mistral AI (mistral-large) — classificação de porte por nome de empresa",
  "porte_distintas":[{"porte":k,"n":n} for k,n in porc_dist.most_common()],
  "origem_empregador":[{"origem":k,"n":n} for k,n in oric.most_common()],
  "regiao_x_porte":{"regioes":REG_ORD,"portes":POR_ORD,"matriz":[[rxp[rg][p] for p in POR_ORD] for rg in REG_ORD]},
  "n_empresas_distintas":len(empc),
  "n_empresas_classificadas":len(_MPORTE),
  "top_local_concentracao":top_local,
}

# ---------- 12) GÊNERO (inferido offline do 1º nome; agregado; amostra pequena) ----------
# genero_map.json é privado (só repo de dados). Método aproximado/binário para
# representação agregada — NÃO é declaração de identidade de gênero de ninguém.
gmap = json.load(open(BASE/"data/genero_map.json"))
sal = _perfil_id  # por id, robusto a perfis puladas (label-join)
def _is_gestao(r): return bool(r["lideranca"]) or any(x in (r["cargo_atual"] or "").lower() for x in ["geren","gestor","head","coorden","diretor"])
G={}
for g in ("F","M"):
    grp=[r for r in rows if gmap.get(r["id"])==g]; ids=[r["id"] for r in grp]
    cresc=[sal[i]["cresc"] for i in ids if i in sal]
    G[g]={
      "n":len(grp),
      "med_atual":med([sal[i]["med_atual"] for i in ids if i in sal]),
      "med_ini":med([sal[i]["med_ini"] for i in ids if i in sal]),
      "cresc_mediano":round(float(np.median(cresc)),1) if cresc else None,
      "em_tech":sum(r["em_tech"] for r in grp),
      "gestao_lideranca":sum(1 for r in grp if _is_gestao(r)),
      "exterior":sum(r["exterior"] for r in grp),
      "intl_empregador":sum(1 for r in grp if r["origem"]=="intl"),
      "trilha_dados":sum(1 for r in grp if r["trilha"]==1),
      "trilha_sw":sum(1 for r in grp if r["trilha"]==0),
      "senioridade":dict(collections.Counter(r["senioridade"] for r in grp)),
    }
# extensão SRC (base oficial IFES Serra) — cruzamento em data/src_extensao.py
srcext = json.load(open(BASE/"data/src_extensao.json"))
extensao = {
  "fonte": srcext["fonte"], "ressalva": srcext["ressalva"],
  "n_encontrados": srcext["n_encontrados"],
  "n_bolsistas_extensao": srcext["n_bolsistas_extensao"],
  "n_bolsa_documentada_oficial": srcext["n_bolsa_documentada_oficial"],
  "funcoes": [{"funcao":k,"n":v} for k,v in srcext["funcoes"].items()],
  "genero": srcext["genero"],
}
# outros laboratórios além do LEDS — cross-ref em data/outros_labs.py (subagent)
try:
    _ol = json.load(open(BASE/"data/outros_labs.json"))
    _leds_n = impacto["origem"]["extensao_leds"]
    _labs = [{"lab":"LEDS — Laboratório de Extensão em Desenvolvimento de Sistemas (IFES)","n_egressos":_leds_n}] + _ol["labs"]
    outros_labs = {"fonte":_ol["fonte"],"n_leds":_leds_n,"n_com_outro_lab":_ol["n_com_outro_lab"],
                   "n_bolsistas_com_outro_lab":_ol["n_bolsistas_com_outro_lab"],
                   "labs":_labs}
except FileNotFoundError:
    outros_labs = None

# ---------- TRILHA DE CARREIRA (área no tempo: início → meio → atual) ----------
_BK={"backend":"Software","frontend":"Software","fullstack":"Software","dev":"Software",
     "mobile":"Mobile","data":"Dados","ml":"Dados","lideranca":"Gestão/Lid.","gestao":"Gestão/Lid.",
     "academico":"Acadêmico","militar":"Outro"}
def _dom(xs):
    cc=collections.Counter(xs); mx=max(cc.values())
    for x in reversed(xs):
        if cc[x]==mx: return x
def _thirds(a):
    exps=sorted([e for e in a["experiencias"] if e.get("inicio")],key=lambda e:e["inicio"])
    s=[_BK.get(e.get("area","dev"),"Software") for e in exps]
    if not s: return None
    if len(s)==1: return (s[0],s[0],s[0])
    if len(s)==2: return (s[0],s[0],s[1])
    k=max(len(s)//3,1); a1=s[:k]; a3=s[-k:]; a2=s[k:len(s)-k] or s[len(s)//2:len(s)//2+1]
    return (_dom(a1),_dom(a2),_dom(a3))
_c1=collections.Counter();_c2=collections.Counter();_c3=collections.Counter()
_l12=collections.Counter();_l23=collections.Counter()
for a in al:
    t=_thirds(a)
    if not t: continue
    i,m,f=t; _c1[i]+=1;_c2[m]+=1;_c3[f]+=1;_l12[(i,m)]+=1;_l23[(m,f)]+=1
ORD=["Software","Mobile","Dados","Gestão/Lid.","Acadêmico","Outro"]
def _col(cc): return [[k,cc[k]] for k in ORD if cc.get(k)]
trilha_carreira={
  "headers":["Início (1º terço)","Meio","Atual"],
  "cols":[_col(_c1),_col(_c2),_col(_c3)],
  "L12":[[a,b,n] for (a,b),n in _l12.most_common()],
  "L23":[[a,b,n] for (a,b),n in _l23.most_common()],
  "insight":{"entrada_software":_c1.get("Software",0),"atual_gestao":_c3.get("Gestão/Lid.",0),
             "atual_dados":_c3.get("Dados",0),"com_transicao":sum(1 for a in al if _thirds(a) and len(set(_thirds(a)))>1)},
}

FAPES_IDS=["barbosa","gary","helen","marialuiza","icaro","tarcisio"]  # cf. fapes_fomento.ANCORA
fapes_f=sum(1 for i in FAPES_IDS if gmap.get(i)=="F")
genero={
  "metodo":"inferido offline do 1º nome (gender-guesser + heurística PT-BR + revisão manual); binário aproximado, não identidade declarada",
  "n_total":len(rows),"F":G["F"]["n"],"M":G["M"]["n"],
  "pct_f":round(100*G["F"]["n"]/len(rows)),
  "detalhe":G,
  "fapes":{"total":len(FAPES_IDS),"F":fapes_f,"M":len(FAPES_IDS)-fapes_f,
           "pct_f":round(100*fapes_f/len(FAPES_IDS))},
  "ressalva":f"amostra pequena ({G['F']['n']} mulheres) — leitura direcional, não estatística",
}

# ---------- TRAJETÓRIA DESTAQUE (alimenta a página de evolução, antes escrita à mão) ----------
# Escolhe, de forma determinística, o perfil que melhor conta a história do estudo:
# começou em bolsa/estágio, tem a série mais longa e o maior multiplicador. Tudo anonimizado —
# o rótulo do empregador vira "Bolsa · pesquisa/extensão" / "Empresa nacional" / "Empresa internacional".
_cons = json.load(open(BASE/"data/consolidado.json"))
_FX = {int(k): v for k, v in _cons["fx_por_ano"].items()}
_IP = {int(k): v for k, v in _cons["deflator_ipca_por_ano"].items()}
_lab2id = {f"Perfil {r['label']}": r["id"] for r in rows if r.get("label") and r.get("id")}
byid_al = {a["id"]: a for a in al}

def _empresa_no_ano(a, Y, intern):
    if intern: return "Bolsa · pesquisa/extensão"
    ativos = [e for e in a["experiencias"]
              if int(e["inicio"][:4]) <= Y <= (2026 if e["fim"] is None else int(e["fim"][:4]))]
    if not ativos: return "Empresa nacional"
    intl = any(emp_intl(e.get("empresa")) for e in ativos)
    return "Empresa internacional" if intl else "Empresa nacional"

def _senioridade_no_ano(exp):
    return " (Sr.)" if exp >= 7 else ""

_cands = []
for plabel, serie in _cons["series_por_perfil"].items():
    # a história é "começou em bolsa DOCUMENTADA" (valor real registrado, não estimativa)
    if not serie or not serie[0].get("bolsa_doc"):
        continue
    pid = _lab2id.get(plabel)
    if not pid or pid not in byid_al:
        continue
    p_ = next((x for x in _cons["perfis"] if x["perfil"] == plabel), None)
    if not p_:
        continue
    _cands.append((len(serie), p_["cresc"], plabel, serie, pid))
_cands.sort(key=lambda c: (-c[0], -c[1], c[2]))

trajetoria = []
if _cands:
    _, _, plabel_sel, serie_sel, pid_sel = _cands[0]
    a_sel = byid_al[pid_sel]
    ULT_SURVEY = 2023                       # depois disso a estimativa é extrapolada
    for pt in serie_sel:
        Y, med_real = pt["ano"], pt["med"]
        nominal = round(med_real / _IP[Y])
        trajetoria.append({
            "ano": Y, "exp": pt["exp"], "fx": _FX[Y], "n": pt["n"],
            "empresa": _empresa_no_ano(a_sel, Y, pt["intern"]) + _senioridade_no_ano(pt["exp"]),
            "p25": round((pt.get("mkt_p25") or pt["p25"]) / _IP[Y]), "med": nominal,
            "p75": round((pt.get("mkt_p75") or pt["p75"]) / _IP[Y]),
            "mkt": round(pt["mkt_med"] / _IP[Y]) if pt.get("mkt_med") else None,
            "real": med_real, "usd": round(nominal / _FX[Y]),
            "ex": Y > ULT_SURVEY, "bolsa": pt.get("bolsa_doc", False),
        })
    print(f"\n=== TRAJETÓRIA DESTAQUE === {plabel_sel}: {len(trajetoria)} anos "
          f"({trajetoria[0]['ano']}–{trajetoria[-1]['ano']}), "
          f"R$ {trajetoria[0]['med']} -> R$ {trajetoria[-1]['med']}")

# distribuição dos multiplicadores do coorte (o histograma da página de evolução)
_BINS = [(1,3,"1–3×"),(3,6,"3–6×"),(6,9,"6–9×"),(9,12,"9–12×"),(12,15,"12–15×"),(15,999,"15×+")]
_cr = [p_["cresc"] for p_ in _cons["perfis"]]
hist_mult = [{"faixa": rot, "n": sum(1 for c in _cr if lo <= c < hi)} for lo, hi, rot in _BINS]

out={"top_tech":top_tech,"clusters":cl_desc,"rows":rows,"insights":insights,
     "comparacao":comp,"cf_2026_senioridade":cf2026,"cruzamento":cross,
     "funcoes":funcoes,"lideranca_gestao":lid_gestao,"metodos":metodos,"impacto":impacto,
     "sankey":sankey,"intl_timeline":intl_timeline,"empresas":empresas,"genero":genero,
     "extensao":extensao,"outros_labs":outros_labs,"trilha_carreira":trilha_carreira,
     "trajetoria_destaque":trajetoria,"hist_multiplicadores":hist_mult}
json.dump(out, open(BASE/"data/analise.json","w"), ensure_ascii=False, indent=1)

# ---------- stdout ----------
print("=== TECNOLOGIAS (top por nº de pessoas) ===")
for t in top_tech: print(f"  {t['tech']:<14} {t['pessoas']} pessoas / {t['mencoes']} menções")
print("\n=== CLUSTERS (KMeans k=3) ===")
for c,d in cl_desc.items():
    print(f"  Cluster {c}: {d['labels']} | {d['trilha']} | ~{d['anos_medio']}a | exterior={d['exterior']} lideranca={d['lideranca']} em_tech={d['em_tech']}/{d['n']}")
    print(f"     cargos: {d['cargos']}")
print("\n=== INSIGHTS ===")
for k,v in insights.items(): print(f"  {k}: {v}")
print("\n=== COMPARAÇÃO EXTERNA ===")
print(f"  egressos mediana atual R$ {comp['egressos_med_atual']} vs CF Sênior 2026 R$ {comp['cf_senior_2026']} ({comp['egressos_vs_cf_senior_pct']:+d}%)")
print("  trajetória (egressos valor da época vs mercado hoje):")
for r in comp["por_exp"]: print(f"    exp {r['exp']:>2}: egressos R$ {r['egressos_epoca']:>6}  |  mercado hoje R$ {r['mercado_hoje']:>6}")
print("\n=== SENIORIDADE x ORIGEM (nacional / internacional) ===")
for r in cross["por_senioridade"]:
    print(f"  {r['senioridade']:<18} n={r['n']} {r['labels']} | nac={r['nac']} intl={r['intl']} | mediana R$ {r['med_atual']}")
print("  --- por origem ---")
for o,d in cross["por_origem"].items():
    print(f"  {o:<9} n={d['n']} | ~{d['anos_medio']}a | mediana R$ {d['med_atual']} | {d['empresas']}")
print(f"  prêmio internacional vs nacional: {cross['premio_intl_vs_nac_pct']:+d}%")
print("\n=== CARGOS / FUNÇÕES ATUAIS ===")
for f in funcoes: print(f"  {f['funcao']:<32} {f['n']}")
print(f"  -> em liderança/gestão: {lid_gestao['total']} ({lid_gestao['gestao']} gestão + {lid_gestao['lideranca_tecnica']} liderança técnica)")
print("\n=== MÉTODOS / PRÁTICAS (presença por egresso) ===")
for m in metodos: print(f"  {m['metodo']:<32} {m['n']}")
print("\n=== INDICADORES DE IMPACTO ===")
import json as _j
print(_j.dumps(impacto, ensure_ascii=False, indent=1))
print("\nSalvo em data/analise.json")

import pandas as pd, json
SAL={2018:"ConvertedSalary",2019:"ConvertedComp",2020:"ConvertedComp",2021:"ConvertedCompYearly",2022:"ConvertedCompYearly",2023:"ConvertedCompYearly"}
FX={2011:1.67,2012:1.95,2013:2.16,2014:2.35,2015:3.33,2016:3.49,2017:3.19,2018:3.66,2019:3.94,2020:5.16,2021:5.39,2022:5.16,2023:4.99,2024:5.39,2025:5.45,2026:5.09}
IP={2011:2.224,2012:2.101,2013:1.984,2014:1.864,2015:1.685,2016:1.585,2017:1.540,2018:1.484,2019:1.423,2020:1.361,2021:1.237,2022:1.169,2023:1.117,2024:1.066,2025:1.020,2026:1.000}
SW=["back-end","front-end","full-stack","back end","front end","full stack","mobile developer","developer, mobile"]
DA=["data scientist","machine learning","data or business analyst","engineer, data","data engineer","business analyst"]
_c={}
def load(y):
    if y in _c: return _c[y]
    salc=SAL[y]; expc="YearsCodingProf" if y==2018 else "YearsCodePro"
    df=pd.read_csv(f"public-{y}.csv",usecols=["Country","DevType",expc,salc],low_memory=False)
    df=df[(df.Country=="Brazil")&df[salc].notna()]; df=df[df[salc].between(3000,500000)]
    df=df.assign(DevType=df.DevType.astype(str).str.lower().str.split(";")).explode("DevType"); df["DevType"]=df.DevType.str.strip()
    df["_exp"]=None if y==2018 else pd.to_numeric(df[expc].replace({"Less than 1 year":"0","More than 50 years":"51"}),errors="coerce")
    df["_expraw"]=df[expc].astype(str).str.strip(); df["_sal"]=df[salc]; _c[y]=df; return df
def bk18(e):
    for lo,hi,l in [(0,2,"0-2 years"),(3,5,"3-5 years"),(6,8,"6-8 years"),(9,11,"9-11 years"),(12,14,"12-14 years"),(15,17,"15-17 years")]:
        if lo<=e<=hi: return l
    return "18-20 years"
def mkt(year,track,exp):
    sv=min(max(year,2018),2023); df=load(sv); kws=SW if track=="Software" else DA
    m=df[df.DevType.str.contains("|".join(kws),na=False,regex=True)]
    if sv==2018: m=m[m._expraw==bk18(exp)]
    else:
        m=m[(m._exp>=max(0,exp-1))&(m._exp<=exp+1)]
        if len(m)<8:
            d2=df[df.DevType.str.contains("|".join(kws),na=False,regex=True)]; m=d2[(d2._exp>=max(0,exp-2))&(d2._exp<=exp+2)]
    s=m._sal
    if len(s)<5: return None
    f=FX[year]*IP[year]/12
    return {"n":int(len(s)),"p25":s.quantile(.25)*f,"med":s.median()*f,"p75":s.quantile(.75)*f}

data=json.load(open("../alunos.json"))
TRACK={"backend":"Software","frontend":"Software","fullstack":"Software","dev":"Software","mobile":"Software","lideranca":"Software","data":"Dados","ml":"Dados"}
INT=("Estágio","Bolsa","Extensão")
raw=[]
for a in data["alunos"]:
    sy=int(a["inicio_carreira_dev"][:4]); serie=[]
    for Y in range(max(sy,2011),2027):  # tabelas FX/IPCA começam em 2011
        cands=[e for e in a["experiencias"] if int(e["inicio"][:4])<=Y<=(2026 if e["fim"] is None else int(e["fim"][:4])) and e["area"] in TRACK]
        if not cands: continue
        area=cands[0]["area"]; track=TRACK[area]; exp=Y-sy
        isint=any(c["tipo"] in INT for c in cands) and exp<=2
        bolsa=next((c.get("bolsa_valor_mensal") for c in cands if c.get("bolsa_valor_mensal")),None)
        if bolsa:
            v=round(bolsa*IP[Y]); serie.append({"ano":Y,"exp":exp,"track":track,"med":v,"p25":v,"p75":v,"intern":True,"n":None})
        else:
            st=mkt(Y,track,exp)
            if not st: continue
            fac=0.5 if isint else 1.0
            serie.append({"ano":Y,"exp":exp,"track":track,"med":round(st["med"]*fac),"p25":round(st["p25"]*fac),"p75":round(st["p75"]*fac),"intern":isint,"n":st["n"]})
    tr="Dados" if (a.get("perfil_tech")=="data" or a["area_atual"] in("data","ml")) else "Software"
    raw.append({"id":a["id"],"track":tr,"em_tech":a["ainda_em_tech"],"serie":serie})

# anonimiza A..Q
order=["barbosa","gary","possatti","helen","renan","andre","tarcisio","joel","icaro","gustavo","marialuiza",
       "gabriel_barboza","magnago","martins_miranda","geann","rodrigo_maia","andre_aguiar",
       "guilherme_gatti","ivana","joao_paulo","lucas_coutinho","marcos_dias","phillipe",
       "anne_caroline","brendon","cassiano","jennifer","ana_rubia",
       "diego","edvaldo","magno","pedro","antonio","cristian","danilo","marlon","breno",
       "caio","lucas_gomes","derick","marcos_carneiro","mateus_garcia","ana_carolina","david_pantaleao","renato","kleber","rafael","andreangelo","icaro_gandine","paulo_ricardo"]
labels=["A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z","AA","AB","AC","AD","AE","AF","AG","AH","AI","AJ","AK","AL","AM","AN","AO","AP","AQ","AR","AS","AT","AU","AV","AW","AX"]
byid={o["id"]:o for o in raw}
perfis=[]
for lab,pid in zip(labels,order):
    o=byid.get(pid)
    if not o or not o["serie"]:  # sem série de mercado (ex.: carreira só em gestão) -> pula
        print(f"  [skip perfil {lab}] {pid}: sem série de mercado")
        continue
    s=o["serie"]; i=s[0]; f=s[-1]
    perfis.append({"perfil":f"Perfil {lab}","trilha":o["track"],"em_tech":o["em_tech"],"anos":f["exp"],
        "bolsa":(i["med"] if i["intern"] else None),"med_ini":i["med"],"med_atual":f["med"],
        "cresc":round(f["med"]/max(i["med"],1),1)})
# agregado por exp
byexp={}
for o in raw:
    for pt in o["serie"]: byexp.setdefault(pt["exp"],[]).append(pt)
agg=[{"exp":e,"lo":min(x["p25"] for x in byexp[e]),"hi":max(x["p75"] for x in byexp[e]),
      "med":round(sum(sorted(x["med"] for x in byexp[e]))/len(byexp[e])),"n":len(byexp[e])} for e in sorted(byexp) if e<=17]
# PV: mercado 2026 por exp/track
FX26=5.09; df23=load(2023)
def mkt2026(track,exp):
    kws=SW if track=="Dados"==False else (DA if track=="Dados" else SW)
    kws=DA if track=="Dados" else SW
    m=df23[df23.DevType.str.contains("|".join(kws),na=False,regex=True)]
    m=m[(m._exp>=max(0,exp-1))&(m._exp<=exp+1)]
    if len(m)<8:
        d2=df23[df23.DevType.str.contains("|".join(kws),na=False,regex=True)]; m=d2[(d2._exp>=max(0,exp-2))&(d2._exp<=exp+2)]
    s=m._sal
    return round(s.median()*FX26/12) if len(s)>=5 else None
pvexp={}
for o in raw:
    for pt in o["serie"]:
        v=mkt2026(pt["track"],pt["exp"])
        if v: pvexp.setdefault(pt["exp"],[]).append(v)
pv=[{"exp":e,"med":round(sum(pvexp[e])/len(pvexp[e]))} for e in sorted(pvexp) if e<=17]

kpi={"n":len(perfis),"em_tech":sum(p["em_tech"] for p in perfis),
     "cresc_medio":round(sum(p["cresc"] for p in perfis)/len(perfis),1),
     "cresc_max":max(p["cresc"] for p in perfis),
     "faixa_inicial_med":round(sum(p["med_ini"] for p in perfis)/len(perfis)),
     "faixa_atual_lo":min(p["med_atual"] for p in perfis),"faixa_atual_hi":max(p["med_atual"] for p in perfis),
     "med_atual":round(sum(p["med_atual"] for p in perfis)/len(perfis))}
json.dump({"kpi":kpi,"perfis":perfis,"agregado":agg,"pv":pv},open("consolidado.json","w"),ensure_ascii=False,indent=1)

def js(arr,keys): return ",".join("{"+",".join(f'{k}:{o[k] if o[k] is not None else "null"}' for k in keys)+"}" for o in arr)
print("KPI:",json.dumps(kpi,ensure_ascii=False))
print("\nPERFIS_JS:")
for p in perfis:
    b=p["bolsa"] if p["bolsa"] is not None else "null"
    print(f'  {{perfil:"{p["perfil"]}",trilha:"{p["trilha"]}",em_tech:{str(p["em_tech"]).lower()},anos:{p["anos"]},bolsa:{b},med_ini:{p["med_ini"]},med_atual:{p["med_atual"]},cresc:{p["cresc"]}}},')
print("\nAGG_JS:")
print(js(agg,["exp","lo","hi","med","n"]))
print("\nAGG_PV_JS:")
print(js(pv,["exp","med"]))

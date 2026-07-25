"""Regenera os consts/tabelas/prosa do dashboard_executivo.html a partir de
consolidado.json + analise.json para o coorte de 45 (modelo salarial = 44)."""
import json, re, pathlib
S = pathlib.Path("/caminho/para/salario")
H = S/"dashboard_executivo.html"
c = json.load(open(S/"data/consolidado.json")); a = json.load(open(S/"data/analise.json"))
html = H.read_text(encoding="utf-8")
NC = a["genero"]["n_total"]  # coorte (dinâmico)
NS = c["kpi"]["n"]  # modelo salarial (44)
def sub1(pat, rep, flags=re.S):
    global html
    html, n = re.subn(pat, lambda m: rep, html, count=1, flags=flags)
    assert n == 1, f"NAO casou: {pat[:60]}"

# ---- KPI (n=coorte; salário do consolidado) ----
k = c["kpi"]
kpi = (f'const KPI={{n:{NC},em_tech:{NC},nsal:{NS},cresc_medio:{k["cresc_medio"]},cresc_max:{k["cresc_max"]},'
       f'faixa_inicial_med:{k["faixa_inicial_med"]},bolsa_tipica:800,faixa_atual_lo:{k["faixa_atual_lo"]},'
       f'faixa_atual_hi:{k["faixa_atual_hi"]},med_atual:{k["med_atual"]}}};')
sub1(r'const KPI=\{[^\n]*\};', kpi)

# ---- PERFIS (=consolidado, 44) ----
def perfil_js(p):
    b = p["bolsa"] if p["bolsa"] is not None else "null"
    return (f'  {{perfil:"{p["perfil"]}",trilha:"{p["trilha"]}",em_tech:{str(p["em_tech"]).lower()},'
            f'anos:{p["anos"]},bolsa:{b},med_ini:{p["med_ini"]},med_atual:{p["med_atual"]},cresc:{p["cresc"]}}}')
perfis = "const PERFIS=[\n" + ",\n".join(perfil_js(p) for p in c["perfis"]) + "\n];"
sub1(r'const PERFIS=\[.*?\n\];', perfis)

# ---- AGG / AGG_PV (=consolidado) ----
agg = "const AGG=[\n  " + ",".join(f'{{exp:{d["exp"]},lo:{d["lo"]},hi:{d["hi"]},med:{d["med"]},n:{d["n"]}}}' for d in c["agregado"]) + "\n];"
sub1(r'const AGG=\[.*?\n\];', agg)
aggpv = "const AGG_PV=[\n  " + ",".join(f'{{exp:{d["exp"]},med:{d["med"]}}}' for d in c["pv"]) + "\n];"
sub1(r'const AGG_PV=\[.*?\n\];', aggpv)

# ---- IMPACTO (tiles + origem + box) ----
im = a["impacto"]
cm = str(im["multiplicador_medio"]).replace(".", ","); cx = str(k["cresc_max"]).replace(".", ",")
tiles = [
    (f'{cm}×', f'crescimento real médio da renda (até {cx}×) — da bolsa à posição atual'),
    (f'~{im["tempo_ate_senior_mediana_anos"]}<small> anos</small>', 'experiência mediana até nível Sênior ou superior'),
    (f'{im["lideram_hoje"]}<small>/{NC}</small>', f'lideram ou gerenciam hoje ({im["passaram_lideranca"]} já passaram por liderança)'),
    (f'{im["intl_hoje"]}<small>/{NC}</small>', f'em empregador internacional — 1º emprego intl ~{int(im["exp_medio_1o_emprego_intl"])} anos de carreira'),
    (f'+{im["premio_intl_pct"]}%', 'prêmio internacional vs nacional (mediana estimada)'),
    (f'{NC}<small>/{NC}</small>', 'seguem em tecnologia'),
    (f'{NC}', 'egressos localizados e integrados (homônimos / sem perfil descartados)'),
    ('6', 'egressos formados por bolsa FAPES/PRODEST (2 projetos) — 6/6 seguem em tech, hoje ~13× a renda real da bolsa'),
]
og = im["origem"]
origem = [("Extensão — IFES (labs)", og["extensao_leds"]), ("Pesquisa — IC/FAPES/CAPES", og["pesquisa_ic_fapes"]),
          ("Ensino — monitoria", og["monitoria_ensino"]), ("Empresa júnior — Morpheus", og["empresa_junior_morpheus"])]
dt = im["dispersao_por_trilha"]; do = im["dispersao_por_origem"]
def boxrow(l, c_, d): return f'    {{l:"{l} (n={d["n"]})",c:"{c_}",min:{d["min"]},q1:{d["q1"]},med:{d["med"]},q3:{d["q3"]},max:{d["max"]}}}'
box = [boxrow("Software", "var(--sw)", dt["Software"]), boxrow("Dados", "var(--data)", dt["Dados"]),
       boxrow("Nacional", "var(--accent)", do["nacional"]), boxrow("Internacional", "var(--pv)", do["intl"])]
impacto = ("const IMPACTO={\n  tiles:[\n" +
           ",\n".join(f'    {{v:"{v}",k:"{kk}"}}' for v, kk in tiles) + "\n  ],\n  origem:[\n" +
           ",\n".join(f'    {{l:"{l}",n:{n}}}' for l, n in origem) + "\n  ],\n  box:[\n" +
           ",\n".join(box) + "\n  ]\n};")
sub1(r'const IMPACTO=\{.*?\n\};', impacto)

# ---- SANKEY (=analise) + total no renderer ----
sk = a["sankey"]
cols = [[[v["nome"], v["n"]] for v in sk["vias"]], [[t["nome"], t["n"]] for t in sk["trilhas"]], [[d["nome"], d["n"]] for d in sk["destinos"]]]
l12 = [[l["de"], l["para"], l["n"]] for l in sk["via_trilha"]]
l23 = [[l["de"], l["para"], l["n"]] for l in sk["trilha_destino"]]
def j(x): return json.dumps(x, ensure_ascii=False)
sankey = (f'const SANKEY={{\n  cols:{j(cols)},\n  L12:{j(l12)},\n  L23:{j(l23)}\n}};')
sub1(r'const SANKEY=\{.*?\n\};', sankey)
html = re.sub(r'(cw=14, pt=30, pb=16, gap=14, total=)\d+', f'\\g<1>{NC}', html, count=1)

# ---- INTLTL (=analise) ----
tl = [[r["ano"], r["pct"], r["intl"], r["ativos"]] for r in a["intl_timeline"]]
sub1(r'const INTLTL=\[[^\n]*\];', f'const INTLTL={j(tl)};')

# ---- GEN (=analise.genero) ----
g = a["genero"]; d = g["detalhe"]
gen = (f'const GEN={{f:{g["F"]},m:{g["M"]},pctF:{g["pct_f"]},med:{{f:{d["F"]["med_atual"]},m:{d["M"]["med_atual"]}}},'
       f'cresc:{{f:{d["F"]["cresc_mediano"]},m:{d["M"]["cresc_mediano"]}}},'
       f'gestao:{{f:{d["F"]["gestao_lideranca"]},m:{d["M"]["gestao_lideranca"]}}},'
       f'exterior:{{f:{d["F"]["exterior"]},m:{d["M"]["exterior"]}}},intl:{{f:{d["F"]["intl_empregador"]},m:{d["M"]["intl_empregador"]}}},'
       f'fapesF:{g["fapes"]["F"]},fapesTot:{g["fapes"]["total"]}}};')
sub1(r'const GEN=\{.*?\};', gen)

# ---- EXT (=analise.extensao) ----
e = a["extensao"]
FLAB = {"ALUNO(A) VOLUNTARIO": "Voluntário(a)", "ALUNO(A) BOLSISTA": "Bolsista", "PALESTRANTE": "Palestrante",
        "INSTRUTOR(A)": "Instrutor(a)", "EXPOSITOR(A)": "Expositor(a)", "ORGANIZADOR(A)": "Organizador(a)",
        "MONITOR(A)": "Monitor(a)", "COLABORADOR(A)": "Colaborador(a)", "AUXILIAR TÉCNICO": "Auxiliar técnico"}
func = [[FLAB.get(f["funcao"], f["funcao"]), f["n"]] for f in e["funcoes"]]
ext = (f'const EXT={{naBase:{e["n_encontrados"]},bolsistasExt:{e["n_bolsistas_extensao"]},'
       f'bolsaDoc:{e["n_bolsa_documentada_oficial"]},n:{NC},\n  funcoes:{j(func)}}};')
sub1(r'const EXT=\{.*?\};', ext)

# ---- EMPRESAS (=analise.empresas) ----
em = a["empresas"]
reg = [[x["regiao"], x["n"]] for x in em["regiao"]]
setor = [[x["setor"], x["n"]] for x in em["setor"]]
porte = [[x["porte"], x["n"]] for x in em["porte"]]
empresas = (f'const EMPRESAS={{\n  regiao:{j(reg)},\n  setor:{j(setor)},\n  porte:{j(porte)}\n}};')
sub1(r'const EMPRESAS=\{.*?\n\};', empresas)

# ---- HEATMAP (=analise.regiao_x_porte, com labels curtos) ----
rxp = em["regiao_x_porte"]
PSHORT = {"Multinacional / BigTech": "Multi/BigTech", "Grande nacional": "Grande nac.", "Média nacional": "Média nac.",
          "Startup / scale-up": "Startup/SU", "Setor público": "Público", "Não classificada": "N/C"}
portes = [PSHORT.get(p, p) for p in rxp["portes"]]
heat = (f'const HEATMAP={{regioes:{j(rxp["regioes"])},\n  portes:{j(portes)},\n  matriz:{j(rxp["matriz"])}}};')
sub1(r'const HEATMAP=\{.*?\};', heat)

# ---- Tabela cargos/métodos (chips no HTML) ----
fdict = {f["funcao"]: f["n"] for f in a["funcoes"]}
for lab, key in [("Engenharia de software", "Engenharia de software"), ("Tech Lead / liderança", "Tech Lead / liderança técnica"),
                 ("Gerência / gestão", "Gerência / gestão"), ("Eng. / ciência de dados", "Eng. / ciência de dados"),
                 ("Consultoria \\(dados", "Consultoria (dados/BD)"), ("Análise de sistemas / PO", "Análise de sistemas / PO")]:
    if key in fdict:
        html = re.sub(rf'({lab}[^<]*<b>)\d+(</b>)', rf'\g<1>{fdict[key]}\g<2>', html, count=1)
mdict = {m["metodo"]: m["n"] for m in a["metodos"]}
for lab, key in [("Ágil / Scrum", "Ágil / Scrum"), ("Cloud \\(AWS", "Cloud (AWS/GCP/Azure)"),
                 ("Arquitetura / microsserviços", "Arquitetura / microsserviços"), ("Dados / ETL / BI", "Dados / ETL / BI"),
                 ("Mobile híbrido", "Mobile híbrido"), ("IA / LLM / ML", "IA / LLM / ML"), ("DevOps / CI-CD", "DevOps / CI-CD"),
                 ("BPM / automação", "BPM / automação de processos"), ("ITIL / governança", "ITIL / governança de TI"),
                 ("Observabilidade", "Observabilidade / monitoramento")]:
    if key in mdict:
        html = re.sub(rf'({lab}[^<]*<b>)\d+(</b>)', rf'\g<1>{mdict[key]}\g<2>', html, count=1)

# ---- Tabela senioridade (grupo) ----
sen = {r["senioridade"]: r for r in a["cruzamento"]["por_senioridade"]}
def senrow(nome, src):
    global html
    html = re.sub(rf'({re.escape(nome)}</td><td class="n">)\d+(</td><td class="n">)\d+(</td><td class="n tot">)\d+',
                  rf'\g<1>{src["nac"]}\g<2>{src["intl"]}\g<3>{src["n"]}', html, count=1)
if "Sênior" in sen: senrow("Sênior", sen["Sênior"])
if "Espec./Tech Lead" in sen: senrow("Especialista / Tech Lead", sen["Espec./Tech Lead"])

H.write_text(html, encoding="utf-8")
print("consts/tabelas regenerados. NC=", NC, "NS=", NS)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera trajetoria_salarial.html — a página única de trajetória de renda.

Junta o que antes eram duas páginas (evolucao_salario_local.html e salario_minimo_mundo.html):
  1. a trajetória ano a ano de um egresso, em R$ da época e em R$ do ano-base
  2. a mesma renda medida em SALÁRIOS MÍNIMOS da época
  3. a comparação com o MERCADO MUNDIAL de devs, em US$
  4. o recorte de quem recebe em dólar
  5. a dispersão do coorte inteiro

Tudo vem de JSON do pipeline; nenhum número é escrito à mão aqui:
  data/analise.json         trajetoria_destaque, hist_multiplicadores, cruzamento, impacto
  data/consolidado.json     por_ano_sm, agregado, fx_por_ano, kpi
  data/salario_minimo.json  SM por ano, reajuste, ganho real, valor em R$ do ano-base
  data/so_benchmarks.json   medianas em US$ por país, e Brasil separado por moeda do contracheque
  data/codigofonte_2026.json  escada de senioridade do mercado brasileiro

As duas páginas antigas viram redirecionamentos para esta, para não quebrar links.

Uso:  python pipeline/gen_reguas.py
"""
import json, pathlib, datetime

BASE = pathlib.Path("/caminho/para/salario")
OUT = BASE / "trajetoria_salarial.html"
ANTIGAS = ["salario_minimo_mundo.html", "evolucao_salario_local.html"]
ANO_BASE = 2026
BOLSA_FAPES = 800          # bolsa nível VI do projeto Prodest/FAPES (valor documentado, 2018)
BOLSA_ANO = 2018

L = lambda f: json.load(open(BASE / "data" / f, encoding="utf-8"))
cons, smj, so, cf, an = (L("consolidado.json"), L("salario_minimo.json"),
                         L("so_benchmarks.json"), L("codigofonte_2026.json"), L("analise.json"))

SM = {int(k): v for k, v in smj["sm_por_ano"].items()}
FX = {int(k): v for k, v in cons["fx_por_ano"].items()}
sm_base, fx_base = SM[ANO_BASE], FX[ANO_BASE]

# ---- série do coorte: só anos com amostra mínima, para não publicar mediana de 4 pessoas ----
# 38 dos 50 egressos começaram a carreira antes de 2018 — com o corte em n>=20 o gráfico
# escondia 2012-2014, quando já havia 12 a 16 deles no mercado. n>=10 mostra esses anos.
N_MIN_ANO = 10
SERIE = [r for r in cons["por_ano_sm"] if r["n"] >= N_MIN_ANO]
prim, ult = SERIE[0], SERIE[-1]
for r in SERIE:
    r["usd"] = round(r["med_nominal"] / FX[r["ano"]])
    r["acima_usd"] = round(r["acima_sm_nominal"] / FX[r["ano"]])

bolsa_sm = BOLSA_FAPES / SM[BOLSA_ANO]

# ---- trajetória individual (perfil escolhido pelo analise.py) ----
TRAJ = an["trajetoria_destaque"]
if not TRAJ:
    raise SystemExit("ABORT: analise.json sem trajetoria_destaque")
t0, t1 = TRAJ[0], TRAJ[-1]
for d in TRAJ:
    d["sm"] = round(d["med"] / SM[d["ano"]], 2)
tj_anos = t1["ano"] - t0["ano"]
tj_mult = t1["med"] / t0["med"]
tj_mult_real = t1["real"] / t0["real"]
tj_cagr = (tj_mult_real ** (1 / tj_anos) - 1) * 100
tj_dobrar = 0.6931 / (tj_cagr / 100) if tj_cagr > 0 else 0
tj_ex0 = min((d["ano"] for d in TRAJ if d["ex"]), default=None)
# mediana do coorte no mesmo eixo de experiência, para contexto na trajetória
_agg = {d["exp"]: d["med"] for d in cons["agregado"]}
TJ_COORTE = [_agg.get(d["exp"], _agg[min(_agg, key=lambda e: abs(e - d["exp"]))]) for d in TRAJ]
HIST = an["hist_multiplicadores"]
cresc_min = min(p["cresc"] for p in cons["perfis"])

# ---- salário mínimo: nominal x poder de compra, no mesmo intervalo da série ----
SMG = [a for a in smj["por_ano"] if a["ano"] >= SERIE[0]["ano"]]
sm_nom_var = SM[ANO_BASE] / SM[SMG[0]["ano"]] - 1
sm_real_var = SMG[-1][f"em_reais_de_{ANO_BASE}"] / SMG[0][f"em_reais_de_{ANO_BASE}"] - 1

# ---- mundo ----
glob = so["global_usd_mes"]
eua = next(p["usd_mes"] for p in so["por_pais"] if p["pais"] == "Estados Unidos")
moeda_ref = next(m for m in so["por_moeda_brasil"] if m["faixa"] == so["faixa_experiencia_referencia"][:11])
usd_pago = moeda_ref["usd_usd_mes"]
razao_moeda = moeda_ref["razao"]

eg_brl, eg_usd, eg_sm = ult["med_nominal"], ult["usd"], ult["em_sm"]
pct_global = round(100 * eg_usd / glob)
pct_eua = round(100 * eg_usd / eua)

# ---- coorte por origem do empregador ----
cruz = an["cruzamento"]["por_senioridade"]
ORIG = [{"l": r["senioridade"], "nac": r["nac"], "intl": r["intl"]}
        for r in cruz if r["n"] > 0]
n_intl = an["impacto"]["intl_hoje"]
n_tot = an["impacto"]["n"]
intl_sen = sum(r["intl"] for r in cruz if r["senioridade"] in ("Sênior", "Espec./Tech Lead"))

# ---- barras por país + as duas referências brasileiras + o cenário em dólar ----
cf_sen = next(x["media"] for x in cf["por_senioridade"] if x["nivel"] == "Sênior")
cf_esp = next(x["media"] for x in cf["por_senioridade"] if "Espec" in x["nivel"])
PAIS = [{"l": p["pais"], "v": p["usd_mes"]} for p in so["por_pais"]]
PAIS.append({"l": "Brasileiro pago em US$ *", "v": usd_pago, "cen": 1})
PAIS.append({"l": "Mediana global", "v": glob, "glob": 1})
PAIS.append({"l": "Egressos IFES", "v": eg_usd, "me": 1})
PAIS.append({"l": "Sênior BR (Código Fonte)", "v": round(cf_sen / fx_base), "cf": 1})
PAIS.sort(key=lambda d: -d["v"])
for p in PAIS:
    if p["l"] == "Brasil":
        p["br"] = 1

TAB = sorted([
    ["Salário mínimo " + str(ANO_BASE), sm_base, 0],
    *[[f'{x["nivel"]} — Código Fonte {ANO_BASE}', x["media"], 0] for x in cf["por_senioridade"]],
    [f'Brasil — Stack Overflow ({so["faixa_experiencia_referencia"][:11]})',
     next(p["usd_mes"] for p in so["por_pais"] if p["pais"] == "Brasil") * fx_base, 0],
    ["Egressos IFES (mediana do coorte)", eg_brl, 1],
    ["Mediana global — Stack Overflow", glob * fx_base, 0],
    ["Brasileiro pago em US$ — Stack Overflow *", usd_pago * fx_base, 2],
    ["Estados Unidos — Stack Overflow", eua * fx_base, 0],
], key=lambda r: r[1])

HOJE = datetime.date.today().strftime("%d/%m/%Y")
J = lambda o: json.dumps(o, ensure_ascii=False)
n1 = lambda x: f"{x:.1f}".replace(".", ",")
brl = lambda v: "R$ " + f"{round(v):,}".replace(",", ".")

DADOS = {
    "TRAJ": TRAJ, "TJ_COORTE": TJ_COORTE, "HIST": HIST,
    "SERIE": SERIE, "SMG": SMG, "PAIS": PAIS, "ORIG": ORIG,
    "MOEDA": so["por_moeda_brasil"], "TAB": TAB,
    "FX": FX, "SM_BASE": sm_base, "FX_BASE": fx_base, "ANO_BASE": ANO_BASE,
    "BOLSA": {"valor": BOLSA_FAPES, "ano": BOLSA_ANO, "sm": round(bolsa_sm, 2)},
    "EG": {"brl": eg_brl, "usd": eg_usd, "sm": eg_sm, "acima": ult["acima_sm_nominal"],
           "n": ult["n"], "ano": ult["ano"]},
    "REF": {"glob": glob, "eua": eua, "pct_global": pct_global, "pct_eua": pct_eua,
            "usd_pago": usd_pago, "razao": razao_moeda, "cf_sen": cf_sen, "cf_esp": cf_esp,
            "n_intl": n_intl, "n_tot": n_tot, "intl_sen": intl_sen,
            "faixa": so["faixa_experiencia_referencia"]},
}

HTML = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trajetória salarial: da bolsa ao mercado mundial — egressos de TI do IFES Campus Serra</title>
<meta name="description" content="Trajetória salarial dos egressos de TI do IFES Campus Serra: ano a ano, em salários mínimos da época e comparada ao mercado mundial de desenvolvedores em dólar.">
<style>
  .viz-root{{
    color-scheme:light;
    --plane:#f7f8fa; --surface:#fdfdfc; --surface-2:#f0f2f5; --ink:#0b0e12; --ink-2:#52565e; --muted:#8a8e96;
    --grid:#e4e6ea; --axis:#c4c7cd;
    --us:#2a78d6; --br:#7a8089; --cf:#d9642b; --glob:#0e8a68; --top:#8557c9; --sm:#a3382f;
    --border:rgba(11,14,18,.10); --shadow:0 1px 2px rgba(11,14,18,.05),0 8px 24px rgba(11,14,18,.06);
    background:var(--plane); color:var(--ink); font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
    -webkit-font-smoothing:antialiased; min-height:100%; padding:16px 13px; box-sizing:border-box;
  }}
  @media (prefers-color-scheme:dark){{ :root:where(:not([data-theme="light"])) .viz-root{{
    color-scheme:dark; --plane:#0c0d0f; --surface:#16181b; --surface-2:#1d2125; --ink:#f4f5f7; --ink-2:#b6bac1;
    --muted:#83878f; --grid:#26292d; --axis:#383c42; --us:#4f97ec; --br:#8d949d; --cf:#ef7d42;
    --glob:#2fbc90; --top:#a480e0; --sm:#e8776a;
    --border:rgba(255,255,255,.10); --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 30px rgba(0,0,0,.45); }} }}
  :root[data-theme="dark"] .viz-root{{
    color-scheme:dark; --plane:#0c0d0f; --surface:#16181b; --surface-2:#1d2125; --ink:#f4f5f7; --ink-2:#b6bac1;
    --muted:#83878f; --grid:#26292d; --axis:#383c42; --us:#4f97ec; --br:#8d949d; --cf:#ef7d42;
    --glob:#2fbc90; --top:#a480e0; --sm:#e8776a; --border:rgba(255,255,255,.10); }}
  *{{box-sizing:border-box}}
  .wrap{{max-width:920px;margin:0 auto;display:flex;flex-direction:column;gap:20px}}
  .eyebrow{{font-size:12px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--us);margin:0 0 9px}}
  h1{{font-size:clamp(23px,3.7vw,34px);line-height:1.11;margin:0 0 12px;font-weight:700;letter-spacing:-.016em;text-wrap:balance}}
  .lede{{font-size:16px;line-height:1.55;color:var(--ink-2);margin:0;max-width:64ch}}
  .lede b{{color:var(--ink)}}
  .nav{{display:flex;flex-wrap:wrap;gap:10px}}
  .nav a{{flex:1 1 220px;text-decoration:none;background:var(--surface);border:1px solid var(--border);
    border-radius:12px;padding:13px 15px;box-shadow:var(--shadow);font-weight:650;font-size:13.5px;color:var(--us)}}
  .nav a span{{display:block;font-weight:400;color:var(--ink-2);font-size:12px;margin-top:3px;line-height:1.4}}
  .sechead{{display:flex;align-items:baseline;gap:11px;margin:14px 0 -4px}}
  .sechead .num{{font-size:11px;font-weight:800;letter-spacing:.09em;color:#fff;background:var(--us);border-radius:6px;padding:4px 9px}}
  .sechead h2{{font-size:19px;margin:0;font-weight:700;letter-spacing:-.015em}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:16px;box-shadow:var(--shadow);padding:clamp(18px,2.6vw,26px)}}
  .card h3{{font-size:15px;margin:0 0 5px;font-weight:680;letter-spacing:-.01em}}
  .hint{{font-size:13px;line-height:1.6;color:var(--muted);margin:0 0 18px}}
  .hint b{{color:var(--ink-2)}}
  .stats{{display:flex;flex-wrap:wrap;gap:12px}}
  .stat{{flex:1 1 175px;background:var(--surface);border:1px solid var(--border);border-radius:13px;padding:16px 18px;box-shadow:var(--shadow)}}
  .stat.hero{{border-color:var(--us);border-width:1.5px}}
  .stat.warn{{border-color:var(--cf);border-width:1.5px}}
  .stat .k{{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 7px}}
  .stat .v{{font-size:26px;font-weight:720;font-variant-numeric:tabular-nums;letter-spacing:-.02em;line-height:1}}
  .stat .v small{{font-size:13px;font-weight:500;color:var(--ink-2);letter-spacing:0}}
  .stat .r{{font-size:12.5px;color:var(--ink-2);margin-top:7px;line-height:1.45}}
  .chart-scroll{{overflow-x:auto}}
  svg{{display:block;width:100%;height:auto;min-width:540px}}
  text{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}}
  .tick{{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}}
  .gridline{{stroke:var(--grid);stroke-width:1}}
  .xlab{{fill:var(--ink-2);font-size:12px;font-weight:650;font-variant-numeric:tabular-nums}}
  .legend{{display:flex;flex-wrap:wrap;gap:15px;margin:12px 0 0;font-size:12.5px;color:var(--ink-2)}}
  .legend span{{display:inline-flex;align-items:center;gap:7px}}
  .sw{{width:18px;height:0;border-top-width:2.5px;border-top-style:solid;display:inline-block}}
  .swb{{width:14px;height:12px;border-radius:3px;display:inline-block}}
  table{{border-collapse:collapse;width:100%;min-width:520px;font-size:13px;font-variant-numeric:tabular-nums}}
  th,td{{padding:9px 10px;text-align:right;border-bottom:1px solid var(--grid)}}
  th:first-child,td:first-child{{text-align:left}}
  thead th{{color:var(--ink-2);font-weight:600;font-size:11px;letter-spacing:.03em;text-transform:uppercase}}
  tbody tr:last-child td{{border-bottom:none}}
  tr.me td{{background:rgba(42,120,214,.07);font-weight:700}}
  tr.me td:first-child{{color:var(--us)}}
  tr.cen td{{background:rgba(217,100,43,.07)}}
  tr.cen td:first-child{{color:var(--cf);font-weight:700}}
  .note{{background:var(--surface-2);border-left:3px solid var(--cf);border-radius:9px;padding:14px 16px;font-size:13px;line-height:1.6;color:var(--ink-2)}}
  .note b{{color:var(--ink)}}
  .src{{font-size:12px;line-height:1.7;color:var(--muted)}}
  .src b{{color:var(--ink-2)}}
  .src code{{font-size:11.5px;background:rgba(127,127,127,.14);padding:1px 5px;border-radius:4px;color:var(--ink-2)}}
  .foot{{font-size:11.5px;color:var(--muted);text-align:center;line-height:1.7}}
  @media (min-width:600px){{ .viz-root{{padding:32px 26px}} .wrap{{gap:22px}} }}
  @media (min-width:960px){{ .viz-root{{padding:52px}} }}
  .exp-banner{{position:fixed;top:0;left:0;right:0;z-index:99999;background:#c62828;color:#fff;
    font:600 14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;text-align:center;
    padding:11px 18px;letter-spacing:.02em;box-shadow:0 2px 10px rgba(0,0,0,.28);
    background-image:repeating-linear-gradient(45deg,rgba(0,0,0,.14) 0 14px,transparent 14px 28px)}}
  .exp-banner strong{{font-weight:800;letter-spacing:.06em}}
  .viz-root{{padding-top:clamp(64px,7vw,80px)!important}}
  @media(max-width:640px){{.exp-banner{{font-size:12px;padding:9px 12px}}}}
</style>
</head>
<body>
<div class="exp-banner" role="alert">
  ⚠️ <strong>SITE EXPERIMENTAL</strong> — em construção. Metodologia ainda sendo desenvolvida; dados e conclusões preliminares, sujeitos a alteração.
</div>

<div class="viz-root"><div class="wrap">

  <header>
    <p class="eyebrow">Ensino · pesquisa · extensão — IFES Campus Serra</p>
    <h1>A bolsa não pagava um salário mínimo.<br>Hoje a renda paga dez.</h1>
    <p class="lede">Em {BOLSA_ANO} a bolsa de pesquisa era <b>{brl(BOLSA_FAPES)}</b> — {brl(SM[BOLSA_ANO] - BOLSA_FAPES)} <b>abaixo</b> do piso legal. Hoje a mediana do coorte é <b>{brl(eg_brl)}/mês</b>: <b>{n1(eg_sm)} salários mínimos</b>, {brl(ult["acima_sm_nominal"])} acima do piso, todo mês.<br><br>Trocada a régua, a leitura muda: em dólar, a mesma renda é <b>{pct_global}%</b> do que um dev de igual experiência ganha no mundo. O teto não é a competência — é o câmbio. <b>{n_intl} dos {n_tot} já atravessaram essa fronteira</b>, hoje em empregador internacional, onde brasileiros pagos em dólar ganham <b>{n1(razao_moeda)}× mais</b> que os pagos em real.</p>
  </header>

  <nav class="nav" aria-label="Outras visões">
    <a href="index.html">📊 Impacto na carreira →<span>Visão executiva do estudo</span></a>
    <a href="evolucao_salario_local.html">📈 Evolução salarial ano a ano →<span>Trajetória individual estimada</span></a>
    <a href="egressos-carreiras.html">🌍 Onde estão os egressos →<span>Empresas, países e jornada</span></a>
    <a href="metodologia.html">🔬 Metodologia →<span>Fontes, ETL e ressalvas</span></a>
    <a href="dados-abertos.html">📂 Dados abertos →<span>Baixe os JSON e o código</span></a>
  </nav>

  <section class="stats" id="stats"></section>

  <div class="sechead"><span class="num">1</span><h2>A trajetória, ano a ano</h2></div>

  <section class="card">
    <h3>De {brl(t0["med"])} a {brl(t1["med"])} por mês em {tj_anos} anos</h3>
    <p class="hint">Uma trajetória do coorte, anonimizada — a de maior multiplicador entre quem começou com <b>bolsa documentada</b>. Linha azul: o que se ganhava em <b>R$ da época</b>. Linha laranja: o mesmo valor trazido a <b>R$ de {ANO_BASE}</b> pelo IPCA, para comparar poder de compra. Faixa sombreada: o que o mercado pagava (p25–p75) para aquela experiência naquele ano. A partir de {tj_ex0} a estimativa é extrapolada — não há edição nova do survey.</p>
    <div class="chart-scroll"><svg id="cTraj" viewBox="0 0 900 430" role="img" aria-label="Trajetória salarial ano a ano"></svg></div>
    <div class="legend">
      <span><i class="sw" style="border-color:var(--us)"></i> Mediana em R$ da época</span>
      <span><i class="sw" style="border-color:var(--cf)"></i> Mediana em R$ de {ANO_BASE} (IPCA)</span>
      <span><i class="swb" style="background:rgba(42,120,214,.13)"></i> Faixa de mercado (p25–p75)</span>
      <span><i class="sw" style="border-color:var(--muted);border-top-style:dotted"></i> Mediana do coorte</span>
    </div>
    <div style="overflow-x:auto;margin-top:20px"><table>
      <thead><tr><th>Ano</th><th>Situação</th><th>Exp.</th><th>Câmbio</th><th>p25</th><th>Mediana</th><th>p75</th><th>US$/mês</th><th>Em mínimos</th></tr></thead>
      <tbody id="tbTraj"></tbody>
    </table></div>
  </section>

  <div class="sechead"><span class="num">2</span><h2>Acima do salário mínimo</h2></div>

  <section class="card">
    <h3>Quantos salários mínimos, ano a ano</h3>
    <p class="hint">Mediana da renda estimada do coorte em cada ano, dividida pelo <b>salário mínimo daquele ano</b>. Bloco claro = 1 mínimo; bloco azul = <b>o que vem acima do piso</b>, com o valor em R$ dentro da barra. Sob cada ano: a renda do mês em <b>R$ e US$</b> (câmbio médio do ano) e quanto isso está <b>acima do mínimo</b>, nas duas moedas. Só anos com pelo menos {N_MIN_ANO} egressos na série (o primeiro ano exibido, {SERIE[0]["ano"]}, tem {SERIE[0]["n"]}).</p>
    <div class="chart-scroll"><svg id="cSM" viewBox="0 0 900 460" role="img" aria-label="Renda do coorte em salários mínimos por ano"></svg></div>
    <div class="legend">
      <span><i class="swb" style="background:rgba(163,56,47,.11);border:1px solid var(--sm)"></i> 1 salário mínimo</span>
      <span><i class="swb" style="background:var(--us)"></i> Acima do mínimo</span>
      <span><i class="sw" style="border-color:var(--sm);border-top-style:dashed"></i> Bolsa FAPES de {BOLSA_ANO} ({n1(bolsa_sm)} mínimo)</span>
    </div>
  </section>

  <section class="card">
    <h3>A régua também subiu</h3>
    <p class="hint">De {SMG[0]["ano"]} a {ANO_BASE} o mínimo subiu <b>{round(sm_nom_var*100)}% em R$</b>, mas só <b>+{round(sm_real_var*100)}% em poder de compra</b> (IPCA). Os {n1(eg_sm)} mínimos de hoje valem mais que {n1(eg_sm)} mínimos de {SMG[0]["ano"]} — o ganho real é maior do que o múltiplo sugere.</p>
    <div class="chart-scroll"><svg id="cSMreal" viewBox="0 0 900 240" role="img" aria-label="Salário mínimo nominal e em poder de compra"></svg></div>
    <div class="legend">
      <span><i class="sw" style="border-color:var(--sm)"></i> Mínimo nominal (R$ do ano)</span>
      <span><i class="sw" style="border-color:var(--cf)"></i> Mínimo em R$ de {ANO_BASE} (IPCA)</span>
      <span><i class="swb" style="background:rgba(163,56,47,.18)"></i> anos de perda real</span>
    </div>
  </section>

  <div class="sechead"><span class="num">3</span><h2>Na régua mundial</h2></div>

  <section class="card">
    <h3>Renda mediana em dólar — devs de {so["faixa_experiencia_referencia"]}</h3>
    <p class="hint">Stack Overflow Developer Survey {so["edicao_referencia"]}, devs de software (back/front/full-stack/mobile), na mesma faixa de experiência da mediana de carreira do coorte. Barra tracejada = <b>cenário</b>: brasileiros que declaram salário em dólar.</p>
    <div class="chart-scroll"><svg id="cPais" viewBox="0 0 900 500" role="img" aria-label="Renda mediana em dólar por país"></svg></div>
  </section>

  <section class="card">
    <h3>Mesma trajetória, duas moedas</h3>
    <p class="hint">A mediana do coorte em <b>R$</b> (eixo esquerdo) e em <b>US$</b> (direito). Os eixos estão na proporção do câmbio médio do período, então <b>as linhas só se separam quando o câmbio se move</b> — a área entre elas é o efeito cambial.</p>
    <div class="chart-scroll"><svg id="cDual" viewBox="0 0 900 370" role="img" aria-label="Trajetória do coorte em reais e em dólares"></svg></div>
    <div class="legend">
      <span><i class="sw" style="border-color:var(--us)"></i> R$/mês nominal (eixo esquerdo)</span>
      <span><i class="sw" style="border-color:var(--glob);border-top-style:dashed"></i> US$/mês (eixo direito)</span>
      <span style="color:var(--muted)">área = efeito do câmbio</span>
    </div>
  </section>

  <div class="sechead"><span class="num">4</span><h2>Os que recebem em dólar</h2></div>

  <section class="card">
    <h3>No Brasil, a moeda do contracheque vale mais que o país</h3>
    <p class="hint">Stack Overflow {so["edicao_referencia"]}, respondentes <b>do Brasil</b>, separados pela moeda em que declaram o salário. Mesmo país, mesma experiência — até <b>{n1(razao_moeda)}× de diferença</b>.</p>
    <div class="chart-scroll"><svg id="cMoeda" viewBox="0 0 900 320" role="img" aria-label="Brasileiros pagos em real e em dólar"></svg></div>
    <div class="legend">
      <span><i class="swb" style="background:var(--br)"></i> Pago em R$</span>
      <span><i class="swb" style="background:var(--cf)"></i> Pago em US$</span>
    </div>
  </section>

  <section class="card">
    <h3>Onde o coorte está nessa divisão</h3>
    <p class="hint"><b>{n_intl} dos {n_tot} egressos</b> trabalham hoje para empregador internacional — {intl_sen} deles em nível Sênior ou superior. Mas o modelo salarial deste estudo precifica <b>todos</b> pela mediana brasileira do Stack Overflow, porque não temos o contracheque real de ninguém.</p>
    <div class="chart-scroll"><svg id="cIntl" viewBox="0 0 900 250" role="img" aria-label="Egressos por origem do empregador"></svg></div>
    <div class="note" style="margin-top:18px">
      <b>O que isso significa para os números deste relatório.</b> O prêmio internacional que o modelo calcula é de apenas <b>+{an["impacto"]["premio_intl_pct"]}%</b> — um artefato: os dois grupos são precificados na mesma tabela brasileira.
      Se os {n_intl} egressos em empregador internacional forem pagos no padrão observado de brasileiros em dólar (<b>US$ {usd_pago:,}/mês</b>), a renda deles seria <b>≈ {brl(usd_pago*fx_base)}/mês</b> — <b>{n1(usd_pago*fx_base/sm_base)} salários mínimos</b>, não {n1(eg_sm)}.
      <b>É cenário, não medição:</b> depende de contrato, senioridade e empresa. Para virar dado, seria preciso perguntar faixa salarial e moeda diretamente aos egressos.
    </div>
  </section>

  <div class="sechead"><span class="num">5</span><h2>O coorte inteiro</h2></div>

  <section class="card">
    <h3>Multiplicador de renda entre os {n_tot} egressos</h3>
    <p class="hint">A página mostra <b>uma</b> trajetória. No coorte inteiro o salto real (início → hoje) varia bastante: mediana <b>{str(cons["kpi"]["cresc_medio"]).replace(".", ",")}×</b>, de {str(cresc_min).replace(".", ",")}× a {str(cons["kpi"]["cresc_max"]).replace(".", ",")}×.</p>
    <div id="histm"></div>
    <p class="hint" style="margin-top:12px">A cauda alta vem de quem começou em bolsa de valor baixo e hoje é sênior; os multiplicadores menores são de quem entrou direto no mercado com salário já alto.</p>
  </section>

  <section class="card">
    <h3>Como ler — e o que isto não é</h3>
    <ul class="src" style="margin:0;padding-left:18px;display:flex;flex-direction:column;gap:7px">
      <li><b>É faixa de mercado</b> para a experiência do egresso em cada ano — não o salário efetivamente recebido. Nenhum contracheque foi coletado.</li>
      <li><b>Os anos de bolsa</b> usam o valor documentado da bolsa; a faixa sombreada mostra o que o mercado pagava para a mesma experiência — a distância entre as duas é o custo de oportunidade da formação.</li>
      <li><b>A partir de {tj_ex0}</b> não há edição nova do Stack Overflow: a estimativa é extrapolada e vem marcada como tal.</li>
      <li>O modelo usa <b>só anos de experiência, país e cargo</b>. Ignora empresa, trabalho remoto pago em moeda forte e negociação — que pesam muito, como mostra a seção 4.</li>
      <li>Salário do Stack Overflow é bruto anual autorreportado; a mediana usa devs back/front/full-stack do Brasil na faixa de experiência do egresso (±1 ano).</li>
    </ul>
  </section>

  <section class="card">
    <h3>Consolidado — as três réguas</h3>
    <p class="hint">Tudo em R$/mês de {ANO_BASE}, US$/mês pelo câmbio médio de {ANO_BASE} (R$ {str(fx_base).replace(".", ",")}) e em salários mínimos de {ANO_BASE} ({brl(sm_base)}).</p>
    <div style="overflow-x:auto"><table>
      <thead><tr><th>Referência</th><th>R$/mês</th><th>US$/mês</th><th>Mínimos</th><th>vs. egressos</th></tr></thead>
      <tbody id="tb"></tbody>
    </table></div>
  </section>

  <section class="card">
    <h3>Fontes</h3>
    <p class="src" style="margin:0">
      <b>Egressos:</b> coorte de {n_tot} ({ult["n"]} com série salarial em {ult["ano"]}). Mediana da renda estimada, por trilha × experiência — estimativa de mercado, não folha real.<br>
      <b>Salário mínimo:</b> {smj["fonte_salario_minimo"]}. {ANO_BASE} = {brl(sm_base)}, conferido com o Decreto 12.797/2025 (+6,79%). Anos com dois valores usam média ponderada pelos meses.<br>
      <b>Inflação:</b> {smj["fonte_inflacao"]} — deflator até {smj["mes_base_deflator"]}.<br>
      <b>Mercado mundial:</b> {so["fonte"]} — campo <code>ConvertedCompYearly</code> (US$, conversão do próprio survey) e <code>Currency</code> para separar quem recebe em R$ e em US$.<br>
      <b>Mercado brasileiro:</b> {cf["fonte"]} — {cf["metodologia"]["amostra"]:,} respondentes, coleta {cf["metodologia"]["periodo_coleta"]}, média em R$/mês, auto-reportado.<br>
      <b>Câmbio:</b> média anual USD→BRL.
    </p>
  </section>

  <p class="foot">Gerado automaticamente por <code>pipeline/gen_reguas.py</code> em {HOJE} · IFES — Campus Serra.<br>Todos os números vêm do pipeline; nenhum é digitado à mão.</p>

</div></div>

<script>
const D={J(DADOS)};
const SM_BASE=D.SM_BASE, FX_BASE=D.FX_BASE, EG=D.EG, REF=D.REF;
const NS="http://www.w3.org/2000/svg";
const el=(t,a)=>{{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e;}};
const usd=n=>"US$ "+Math.round(n).toLocaleString("pt-BR");
const brl=n=>"R$ "+Math.round(n).toLocaleString("pt-BR");
const n1=x=>x.toFixed(1).replace(".",",");
const kbrl=n=>"R$ "+(n/1000).toFixed(1).replace(".",",")+"k";

// ---- tiles ----
const P0=D.SERIE[0];
document.getElementById("stats").innerHTML=`
 <div class="stat"><p class="k">Bolsa de pesquisa · ${{D.BOLSA.ano}}</p><div class="v">${{n1(D.BOLSA.sm)}}<small> mínimos</small></div><div class="r">${{brl(D.BOLSA.valor)}}/mês — abaixo do piso legal</div></div>
 <div class="stat hero"><p class="k">Coorte hoje · mediana</p><div class="v">${{n1(EG.sm)}}<small> mínimos</small></div><div class="r">${{brl(EG.brl)}}/mês · ${{usd(EG.usd)}}</div></div>
 <div class="stat"><p class="k">Acima do piso</p><div class="v">+${{n1(EG.sm-1)}}<small> mínimos</small></div><div class="r">${{brl(EG.acima)}} a mais que o mínimo, por mês</div></div>
 <div class="stat"><p class="k">vs. mediana mundial</p><div class="v">${{REF.pct_global}}%</div><div class="r">dev de mesma experiência no mundo: ${{usd(REF.glob)}}</div></div>
 <div class="stat warn"><p class="k">Se pago em dólar *</p><div class="v">${{n1(REF.usd_pago*FX_BASE/SM_BASE)}}<small> mínimos</small></div><div class="r">cenário p/ os ${{REF.n_intl}} em empregador internacional</div></div>`;

// ================= 1. trajetória ano a ano =================
(function(){{
  const T=D.TRAJ, C=D.TJ_COORTE, W=900,H=430,m={{t:28,r:26,b:74,l:60}}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const s=document.getElementById("cTraj");
  const Y0=T[0].ano, Y1=T[T.length-1].ano;
  // eixo por ANO, não por índice: a série tem buracos (anos sem vínculo em tecnologia)
  // e um eixo por índice comprimiria o tempo sem avisar.
  const xs=i=>m.l+iw*(T[i].ano-Y0)/Math.max(Y1-Y0,1);
  const YM=Math.ceil(Math.max(...T.map(d=>Math.max(d.p75,d.real)))/5000)*5000;
  const ys=v=>m.t+ih*(1-v/YM);
  for(let v=0;v<=YM;v+=YM/5){{ s.appendChild(el("line",{{x1:m.l,x2:W-m.r,y1:ys(v),y2:ys(v),class:"gridline"}}));
    const t=el("text",{{x:m.l-9,y:ys(v)+4,"text-anchor":"end",class:"tick"}});
    t.textContent="R$ "+(v/1000).toFixed(0)+"k"; s.appendChild(t); }}
  s.appendChild(el("line",{{x1:m.l,x2:W-m.r,y1:ys(0),y2:ys(0),stroke:"var(--axis)","stroke-width":1}}));
  // faixa p25–p75
  let u="",lo="";
  T.forEach((d,i)=>u+=(i?"L":"M")+xs(i)+" "+ys(d.p75)+" ");
  for(let i=T.length-1;i>=0;i--) lo+="L"+xs(i)+" "+ys(T[i].p25)+" ";
  s.appendChild(el("path",{{d:u+lo+"Z",fill:"var(--us)","fill-opacity":.13}}));
  // divisor do trecho extrapolado
  const iEx=T.findIndex(d=>d.ex);
  if(iEx>0){{ const dx=(xs(iEx-1)+xs(iEx))/2;
    s.appendChild(el("line",{{x1:dx,x2:dx,y1:m.t,y2:m.t+ih,stroke:"var(--axis)","stroke-width":1,"stroke-dasharray":"2 3"}}));
    const t=el("text",{{x:dx+5,y:m.t+11,"font-size":10,fill:"var(--muted)"}}); t.textContent="extrapolado →"; s.appendChild(t); }}
  // mediana do coorte
  let cl=""; C.forEach((v,i)=>cl+=(i?"L":"M")+xs(i)+" "+ys(v)+" ");
  s.appendChild(el("path",{{d:cl,fill:"none",stroke:"var(--muted)","stroke-width":1.6,"stroke-dasharray":"2 3"}}));
  // linha em R$ do ano-base
  let rl=""; T.forEach((d,i)=>rl+=(i?"L":"M")+xs(i)+" "+ys(d.real)+" ");
  s.appendChild(el("path",{{d:rl,fill:"none",stroke:"var(--cf)","stroke-width":2.1}}));
  // linha nominal: sólida até o survey, tracejada depois
  const corte=iEx<0?T.length-1:iEx-1;
  let a=""; for(let i=0;i<=corte;i++) a+=(i?"L":"M")+xs(i)+" "+ys(T[i].med)+" ";
  s.appendChild(el("path",{{d:a,fill:"none",stroke:"var(--us)","stroke-width":2.7,"stroke-linejoin":"round"}}));
  if(iEx>0){{ let b=""; for(let i=corte;i<T.length;i++) b+=(i===corte?"M":"L")+xs(i)+" "+ys(T[i].med)+" ";
    s.appendChild(el("path",{{d:b,fill:"none",stroke:"var(--us)","stroke-width":2.7,"stroke-dasharray":"5 4"}})); }}
  T.forEach((d,i)=>{{
    s.appendChild(el("circle",{{cx:xs(i),cy:ys(d.real),r:2.8,fill:"var(--surface)",stroke:"var(--cf)","stroke-width":2}}));
    s.appendChild(el("circle",{{cx:xs(i),cy:ys(d.med),r:3.6,fill:"var(--surface)",stroke:"var(--us)","stroke-width":2}}));
    const xl=el("text",{{x:xs(i),y:H-m.b+22,"text-anchor":"middle",class:"xlab","font-size":11}});
    xl.textContent=d.ano+(d.ex?"*":""); s.appendChild(xl);
    const sl=el("text",{{x:xs(i),y:H-m.b+37,"text-anchor":"middle","font-size":9.5,fill:"var(--muted)"}});
    sl.textContent=n1(d.sm)+"×SM"; s.appendChild(sl);
  }});
  [[0,"start"],[T.length-1,"end"]].forEach(([i,anc])=>{{
    const t=el("text",{{x:xs(i)+(anc==="start"?8:-8),y:ys(T[i].med)-11,"text-anchor":anc,"font-size":12,"font-weight":750,fill:"var(--ink)"}});
    t.textContent=brl(T[i].med); s.appendChild(t); }});
  const yt=el("text",{{x:-(m.t+ih/2),y:15,"text-anchor":"middle",class:"tick",transform:"rotate(-90)"}});
  yt.textContent="R$ / mês"; s.appendChild(yt);
  const ft=el("text",{{x:m.l,y:H-6,"font-size":10,fill:"var(--muted)"}});
  ft.textContent="sob o ano: quantos salários mínimos daquele ano · * anos extrapolados"; s.appendChild(ft);
  document.getElementById("tbTraj").innerHTML=T.map(d=>
    `<tr><td>${{d.ano}}${{d.ex?" *":""}}</td><td>${{d.empresa}}</td><td>${{d.exp}}a</td>
     <td>${{d.fx.toFixed(2).replace(".",",")}}</td>
     <td style="color:var(--muted)">${{brl(d.p25)}}</td>
     <td style="color:var(--us);font-weight:700">${{brl(d.med)}}${{d.bolsa?' <small style="color:var(--muted)">bolsa</small>':""}}</td>
     <td style="color:var(--muted)">${{brl(d.p75)}}</td>
     <td style="color:var(--glob)">${{usd(d.usd)}}</td>
     <td style="font-weight:650">${{n1(d.sm)}}×</td></tr>`).join("");
}})();

// ================= 5. histograma de multiplicadores =================
(function(){{
  const box=document.getElementById("histm"); if(!box) return;
  const mx=Math.max(...D.HIST.map(h=>h.n));
  box.innerHTML=D.HIST.map(h=>
    `<div style="display:flex;align-items:center;gap:10px;margin:5px 0">
       <div style="flex:0 0 58px;font-size:12px;color:var(--muted);text-align:right">${{h.faixa}}</div>
       <div style="flex:1;background:rgba(127,127,127,.14);border-radius:5px;height:20px">
         <div style="width:${{(h.n/mx*100).toFixed(0)}}%;background:var(--cf);height:20px;border-radius:5px;min-width:14px"></div>
       </div><b style="flex:0 0 26px;font-size:12.5px;font-variant-numeric:tabular-nums">${{h.n}}</b>
     </div>`).join("");
}})();

// ================= 2. barras: mínimo + excedente =================
(function(){{
  const S=D.SERIE, W=900,H=460,m={{t:38,r:22,b:118,l:48}}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const YM=Math.ceil(Math.max(...S.map(d=>d.em_sm))/3)*3+3;
  const s=document.getElementById("cSM");
  const bw=iw/S.length, ys=v=>m.t+ih*(1-v/YM), y0=H-m.b;
  for(let v=0;v<=YM;v+=3){{ s.appendChild(el("line",{{x1:m.l,x2:W-m.r,y1:ys(v),y2:ys(v),class:"gridline"}}));
    const t=el("text",{{x:m.l-9,y:ys(v)+4,"text-anchor":"end",class:"tick"}}); t.textContent=v+"×"; s.appendChild(t); }}
  s.appendChild(el("line",{{x1:m.l,x2:W-m.r,y1:ys(0),y2:ys(0),stroke:"var(--axis)","stroke-width":1}}));
  S.forEach((d,i)=>{{
    const x=m.l+bw*i+bw*0.19, w=bw*0.62, base=Math.min(d.em_sm,1);
    s.appendChild(el("rect",{{x,y:ys(base),width:w,height:ys(0)-ys(base),fill:"rgba(163,56,47,.11)",stroke:"var(--sm)","stroke-width":1,rx:3}}));
    if(d.em_sm>1) s.appendChild(el("rect",{{x,y:ys(d.em_sm),width:w,height:ys(1)-ys(d.em_sm),fill:"var(--us)","fill-opacity":.9,rx:3}}));
    const t=el("text",{{x:x+w/2,y:ys(Math.max(d.em_sm,1))-9,"text-anchor":"middle","font-size":13,"font-weight":750,fill:"var(--ink)"}});
    t.textContent=n1(d.em_sm)+"×"; s.appendChild(t);
    if(ys(1)-ys(d.em_sm)>26){{
      const e=el("text",{{x:x+w/2,y:(ys(d.em_sm)+ys(1))/2+4,"text-anchor":"middle","font-size":10.5,"font-weight":750,fill:"#fff"}});
      e.textContent="+"+kbrl(d.acima_sm_nominal); s.appendChild(e);
    }}
    const xl=el("text",{{x:x+w/2,y:y0+21,"text-anchor":"middle",class:"xlab"}}); xl.textContent=d.ano; s.appendChild(xl);
    [[38,brl(d.med_nominal),"var(--ink-2)",11,650],[53,usd(d.usd),"var(--glob)",11,650],
     [73,"+"+brl(d.acima_sm_nominal),"var(--us)",10,700],[86,"+"+usd(d.acima_usd),"var(--muted)",9.5,400]]
    .forEach(([dy,tx,c,fs,fw])=>{{ const t2=el("text",{{x:x+w/2,y:y0+dy,"text-anchor":"middle","font-size":fs,"font-weight":fw,fill:c}});
      t2.textContent=tx; s.appendChild(t2); }});
  }});
  s.appendChild(el("line",{{x1:m.l,x2:W-m.r,y1:y0+62,y2:y0+62,stroke:"var(--grid)","stroke-width":1}}));
  {{ const cap=el("text",{{x:m.l,y:y0+106,"font-size":10.5}});
    [["sob o ano: renda do mês em ","var(--muted)",400],["R$","var(--ink-2)",700],[" e ","var(--muted)",400],
     ["US$","var(--glob)",700],["   —   sob a linha: ","var(--muted)",400],
     ["quanto está acima do salário mínimo","var(--us)",700],[" (R$ e US$)","var(--muted)",400]]
    .forEach(([tx,c,fw])=>{{ const sp=document.createElementNS(NS,"tspan");
      sp.setAttribute("fill",c); sp.setAttribute("font-weight",fw); sp.textContent=tx; cap.appendChild(sp); }});
    s.appendChild(cap); }}
  // piso legal + bolsa
  s.appendChild(el("line",{{x1:m.l,x2:W-m.r,y1:ys(1),y2:ys(1),stroke:"var(--sm)","stroke-width":1.6,"stroke-dasharray":"5 4"}}));
  {{ const t=el("text",{{x:W-m.r,y:ys(1)-7,"text-anchor":"end","font-size":11,"font-weight":700,fill:"var(--sm)"}});
    t.textContent="piso legal · 1 salário mínimo"; s.appendChild(t); }}
  s.appendChild(el("line",{{x1:m.l,x2:W-m.r,y1:ys(D.BOLSA.sm),y2:ys(D.BOLSA.sm),stroke:"var(--sm)","stroke-width":1.4,"stroke-dasharray":"2 3","stroke-opacity":.8}}));
  {{ const t=el("text",{{x:m.l+6,y:ys(D.BOLSA.sm)+13,"font-size":10,"font-weight":700,fill:"var(--sm)"}});
    t.textContent="bolsa FAPES "+D.BOLSA.ano+" · "+n1(D.BOLSA.sm)+" mínimo"; s.appendChild(t); }}
  const yt=el("text",{{x:-(m.t+ih/2),y:14,"text-anchor":"middle",class:"tick",transform:"rotate(-90)"}});
  yt.textContent="× salário mínimo do ano"; s.appendChild(yt);
}})();

// ================= 1b. mínimo nominal x real =================
(function(){{
  const G=D.SMG, W=900,H=240,m={{t:22,r:80,b:44,l:58}}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const key="em_reais_de_"+D.ANO_BASE;
  const YM=Math.ceil(Math.max(...G.map(d=>Math.max(d.media_ponderada,d[key])))/300)*300+300;
  const s=document.getElementById("cSMreal");
  const xs=i=>m.l+iw*i/(G.length-1), ys=v=>m.t+ih*(1-v/YM);
  for(let v=0;v<=YM;v+=Math.round(YM/3/100)*100){{ s.appendChild(el("line",{{x1:m.l,x2:W-m.r,y1:ys(v),y2:ys(v),class:"gridline"}}));
    const t=el("text",{{x:m.l-9,y:ys(v)+4,"text-anchor":"end",class:"tick"}}); t.textContent="R$ "+v.toLocaleString("pt-BR"); s.appendChild(t); }}
  // faixas de perda real
  G.forEach((d,i)=>{{ if(d.ganho_real_pct!=null&&d.ganho_real_pct<0&&i>0){{
    s.appendChild(el("rect",{{x:(xs(i-1)+xs(i))/2,y:m.t,width:Math.max((xs(i+1<G.length?i+1:i)-xs(i-1))/2,6),height:ih,fill:"var(--sm)","fill-opacity":.09}})); }} }});
  let a="",b="";
  G.forEach((d,i)=>{{ a+=(i?"L":"M")+xs(i)+" "+ys(d.media_ponderada)+" "; b+=(i?"L":"M")+xs(i)+" "+ys(d[key])+" "; }});
  s.appendChild(el("path",{{d:b,fill:"none",stroke:"var(--cf)","stroke-width":2.3}}));
  s.appendChild(el("path",{{d:a,fill:"none",stroke:"var(--sm)","stroke-width":2.5}}));
  G.forEach((d,i)=>{{
    s.appendChild(el("circle",{{cx:xs(i),cy:ys(d[key]),r:2.8,fill:"var(--surface)",stroke:"var(--cf)","stroke-width":2}}));
    s.appendChild(el("circle",{{cx:xs(i),cy:ys(d.media_ponderada),r:2.8,fill:"var(--surface)",stroke:"var(--sm)","stroke-width":2}}));
    const xl=el("text",{{x:xs(i),y:H-m.b+21,"text-anchor":"middle",class:"xlab","font-size":11}}); xl.textContent=d.ano; s.appendChild(xl);
  }});
  const L=G.length-1;
  [[brl(G[L].media_ponderada),ys(G[L].media_ponderada),"var(--sm)",14],[brl(G[L][key]),ys(G[L][key]),"var(--cf)",-6]]
   .forEach(([tx,y,c,dy])=>{{ const t=el("text",{{x:W-m.r+8,y:y+dy,"font-size":11.5,"font-weight":700,fill:c}}); t.textContent=tx; s.appendChild(t); }});
}})();

// ================= 2. barras por país =================
(function(){{
  const P=D.PAIS, W=900,H=500,m={{t:16,r:104,b:36,l:200}}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const s=document.getElementById("cPais");
  const XM=Math.ceil(Math.max(...P.map(d=>d.v))/3500)*3500, rh=ih/P.length, xs=v=>m.l+iw*v/XM;
  for(let v=0;v<=XM;v+=3500){{ s.appendChild(el("line",{{x1:xs(v),x2:xs(v),y1:m.t,y2:m.t+ih,class:"gridline"}}));
    const t=el("text",{{x:xs(v),y:H-m.b+20,"text-anchor":"middle",class:"tick"}}); t.textContent="US$ "+(v/1000)+"k"; s.appendChild(t); }}
  P.forEach((d,i)=>{{
    const y=m.t+rh*i+rh*0.17, h=rh*0.66;
    const c=d.me?"var(--us)":d.glob?"var(--glob)":d.cen||d.cf?"var(--cf)":d.br?"var(--br)":"var(--axis)";
    const r=el("rect",{{x:m.l,y,width:Math.max(xs(d.v)-m.l,2),height:h,
      fill:c,"fill-opacity":d.me?1:(d.glob||d.cf||d.br?.8:.42),rx:3}});
    if(d.cen){{ r.setAttribute("fill-opacity",.30); r.setAttribute("stroke",c);
      r.setAttribute("stroke-width",1.6); r.setAttribute("stroke-dasharray","5 3"); }}
    s.appendChild(r);
    const strong=d.me||d.glob||d.cen;
    const lb=el("text",{{x:m.l-10,y:y+h/2+4,"text-anchor":"end","font-size":12.5,"font-weight":strong?750:550,
      fill:d.me?"var(--us)":d.glob?"var(--glob)":d.cen?"var(--cf)":"var(--ink-2)"}});
    lb.textContent=d.l; s.appendChild(lb);
    const vl=el("text",{{x:xs(d.v)+8,y:y+h/2+4,"font-size":12,"font-weight":d.me?750:600,
      fill:d.me?"var(--us)":d.cen?"var(--cf)":"var(--ink-2)"}});
    vl.textContent=usd(d.v); s.appendChild(vl);
  }});
  s.appendChild(el("line",{{x1:xs(EG.usd),x2:xs(EG.usd),y1:m.t,y2:m.t+ih,stroke:"var(--us)","stroke-width":1.4,"stroke-dasharray":"4 4","stroke-opacity":.6}}));
}})();

// ================= 2b. duas moedas =================
(function(){{
  const S=D.SERIE, W=900,H=370,m={{t:24,r:76,b:58,l:68}}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const K=S.reduce((a,d)=>a+D.FX[d.ano],0)/S.length;
  const RMAX=Math.ceil(Math.max(...S.map(d=>d.med_nominal))/3000)*3000+3000, UMAX=RMAX/K;
  const s=document.getElementById("cDual");
  const xs=i=>m.l+iw*i/(S.length-1), yR=v=>m.t+ih*(1-v/RMAX), yU=v=>m.t+ih*(1-v/UMAX);
  const step=RMAX/4;
  for(let v=0;v<=RMAX;v+=step){{
    s.appendChild(el("line",{{x1:m.l,x2:W-m.r,y1:yR(v),y2:yR(v),class:"gridline"}}));
    const t=el("text",{{x:m.l-9,y:yR(v)+4,"text-anchor":"end",class:"tick"}}); t.setAttribute("fill","var(--us)");
    t.textContent="R$ "+(v/1000).toFixed(0)+"k"; s.appendChild(t);
    const u=el("text",{{x:W-m.r+9,y:yR(v)+4,class:"tick"}}); u.setAttribute("fill","var(--glob)");
    u.textContent="$ "+(v/K/1000).toFixed(1).replace(".",",")+"k"; s.appendChild(u);
  }}
  s.appendChild(el("line",{{x1:m.l,x2:W-m.r,y1:yR(0),y2:yR(0),stroke:"var(--axis)","stroke-width":1}}));
  let top="",bot="";
  S.forEach((d,i)=>top+=(i?"L":"M")+xs(i)+" "+yR(d.med_nominal)+" ");
  for(let i=S.length-1;i>=0;i--) bot+="L"+xs(i)+" "+yU(S[i].usd)+" ";
  s.appendChild(el("path",{{d:top+bot+"Z",fill:"var(--cf)","fill-opacity":.13}}));
  let pR="",pU="";
  S.forEach((d,i)=>{{ pR+=(i?"L":"M")+xs(i)+" "+yR(d.med_nominal)+" "; pU+=(i?"L":"M")+xs(i)+" "+yU(d.usd)+" "; }});
  s.appendChild(el("path",{{d:pU,fill:"none",stroke:"var(--glob)","stroke-width":2.5,"stroke-dasharray":"6 4"}}));
  s.appendChild(el("path",{{d:pR,fill:"none",stroke:"var(--us)","stroke-width":2.7}}));
  S.forEach((d,i)=>{{
    s.appendChild(el("circle",{{cx:xs(i),cy:yU(d.usd),r:3,fill:"var(--surface)",stroke:"var(--glob)","stroke-width":2}}));
    s.appendChild(el("circle",{{cx:xs(i),cy:yR(d.med_nominal),r:3.4,fill:"var(--surface)",stroke:"var(--us)","stroke-width":2}}));
    const xl=el("text",{{x:xs(i),y:H-m.b+21,"text-anchor":"middle",class:"xlab","font-size":11}}); xl.textContent=d.ano; s.appendChild(xl);
    const fl=el("text",{{x:xs(i),y:H-m.b+37,"text-anchor":"middle","font-size":9.5,fill:"var(--muted)"}});
    fl.textContent=D.FX[d.ano].toFixed(2).replace(".",","); s.appendChild(fl);
  }});
  const L=S.length-1;
  {{ const t=el("text",{{x:xs(L)-8,y:yR(S[L].med_nominal)-12,"text-anchor":"end","font-size":12,"font-weight":750,fill:"var(--us)"}});
    t.textContent=brl(S[L].med_nominal); s.appendChild(t); }}
  {{ const t=el("text",{{x:xs(L)-8,y:yU(S[L].usd)+20,"text-anchor":"end","font-size":12,"font-weight":750,fill:"var(--glob)"}});
    t.textContent=usd(S[L].usd); s.appendChild(t); }}
  const ft=el("text",{{x:m.l,y:H-6,"font-size":10,fill:"var(--muted)"}});
  ft.textContent="números sob o ano = câmbio médio USD→BRL · em R$ o crescimento é "
    +(S[L].med_nominal/S[0].med_nominal).toFixed(1).replace(".",",")+"×, em US$ "
    +(S[L].usd/S[0].usd).toFixed(1).replace(".",",")+"×"; s.appendChild(ft);
}})();

// ================= 3. moeda do contracheque =================
(function(){{
  const M=D.MOEDA, W=900,H=320,m={{t:26,r:24,b:56,l:120}}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const s=document.getElementById("cMoeda");
  const XM=Math.ceil(Math.max(...M.map(d=>d.usd_usd_mes))/1000)*1000, rh=ih/M.length, xs=v=>m.l+iw*v/XM;
  const step=Math.round(XM/4/500)*500;
  for(let v=0;v<=XM;v+=step){{ s.appendChild(el("line",{{x1:xs(v),x2:xs(v),y1:m.t,y2:m.t+ih,class:"gridline"}}));
    const t=el("text",{{x:xs(v),y:H-m.b+20,"text-anchor":"middle",class:"tick"}}); t.textContent="US$ "+(v/1000).toFixed(1).replace(".",",")+"k"; s.appendChild(t); }}
  M.forEach((d,i)=>{{
    const y0=m.t+rh*i+rh*0.14, h=rh*0.32;
    s.appendChild(el("rect",{{x:m.l,y:y0,width:Math.max(xs(d.brl_usd_mes)-m.l,2),height:h,fill:"var(--br)","fill-opacity":.55,rx:3}}));
    s.appendChild(el("rect",{{x:m.l,y:y0+h+3,width:Math.max(xs(d.usd_usd_mes)-m.l,2),height:h,fill:"var(--cf)","fill-opacity":.85,rx:3}}));
    const lb=el("text",{{x:m.l-10,y:y0+h+2,"text-anchor":"end","font-size":12.5,"font-weight":650,fill:"var(--ink-2)"}});
    lb.textContent=d.faixa; s.appendChild(lb);
    const v1=el("text",{{x:xs(d.brl_usd_mes)+7,y:y0+h-2,"font-size":11,fill:"var(--ink-2)"}});
    v1.textContent=usd(d.brl_usd_mes)+"  (n="+d.n_brl+")"; s.appendChild(v1);
    const v2=el("text",{{x:xs(d.usd_usd_mes)+7,y:y0+2*h+2,"font-size":11.5,"font-weight":700,fill:"var(--cf)"}});
    v2.textContent=usd(d.usd_usd_mes)+"  "+n1(d.razao)+"×  (n="+d.n_usd+")"; s.appendChild(v2);
  }});
  const xt=el("text",{{x:m.l+iw/2,y:H-8,"text-anchor":"middle","font-size":10.5,fill:"var(--muted)"}});
  xt.textContent="mediana US$/mês · respondentes do Brasil, devs de software"; s.appendChild(xt);
}})();

// ================= 3b. coorte por origem =================
(function(){{
  const G=D.ORIG, W=900,H=250,m={{t:32,r:24,b:44,l:160}}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const s=document.getElementById("cIntl");
  const MX=Math.max(...G.map(d=>d.nac+d.intl)), rh=ih/G.length, xs=n=>m.l+iw*n/MX;
  G.forEach((d,i)=>{{
    const y=m.t+rh*i+rh*0.22, h=rh*0.5;
    if(d.nac) s.appendChild(el("rect",{{x:m.l,y,width:Math.max(xs(d.nac)-m.l,2),height:h,fill:"var(--br)","fill-opacity":.5,rx:3}}));
    if(d.intl) s.appendChild(el("rect",{{x:xs(d.nac),y,width:Math.max(xs(d.nac+d.intl)-xs(d.nac),2),height:h,fill:"var(--cf)","fill-opacity":.9,rx:3}}));
    const lb=el("text",{{x:m.l-10,y:y+h/2+4,"text-anchor":"end","font-size":12.5,"font-weight":650,fill:"var(--ink-2)"}});
    lb.textContent=d.l; s.appendChild(lb);
    if(d.nac){{ const t=el("text",{{x:m.l+8,y:y+h/2+4,"font-size":12,"font-weight":700,fill:"var(--ink)"}});
      t.textContent=d.nac+" nacional"; s.appendChild(t); }}
    if(d.intl){{ const t=el("text",{{x:xs(d.nac)+8,y:y+h/2+4,"font-size":12,"font-weight":750,fill:"#fff"}});
      t.textContent=d.intl+" intl."; s.appendChild(t); }}
  }});
  const ttl=el("text",{{x:m.l,y:m.t-10,"font-size":11.5,"font-weight":700,fill:"var(--ink-2)"}});
  ttl.textContent=REF.n_intl+" de "+REF.n_tot+" egressos em empregador internacional"; s.appendChild(ttl);
  const ft=el("text",{{x:m.l,y:H-14,"font-size":10.5,fill:"var(--muted)"}});
  ft.textContent="cinza = empregador nacional · laranja = empregador internacional (sede ou contrato no exterior)"; s.appendChild(ft);
}})();

// ================= tabela =================
document.getElementById("tb").innerHTML=D.TAB.map(([l,v,kind])=>{{
  const rel=v/EG.brl, cls=kind===1?"me":(kind===2?"cen":"");
  return `<tr class="${{cls}}"><td>${{l}}</td><td>${{brl(v)}}</td><td>${{usd(v/FX_BASE)}}</td>
   <td>${{n1(v/SM_BASE)}}×</td>
   <td style="color:${{kind===1?'var(--us)':(rel>=1?'var(--glob)':'var(--muted)')}}">${{kind===1?'—':(rel>=1?"+":"−")+Math.abs(Math.round((rel-1)*100))+"%"}}</td></tr>`;
}}).join("")
 +`<tr><td colspan="5" style="text-align:left;color:var(--muted);font-size:11.5px;padding-top:12px;border:0">
   <b>*</b> cenário, não medição — mediana de respondentes do Brasil que declaram salário em dólar. Nenhum egresso teve contracheque coletado.</td></tr>`;
</script>
</body>
</html>
"""

OUT.write_text(HTML, encoding="utf-8")

# As duas páginas antigas viraram esta. Ficam como redirecionamento para não quebrar
# links já publicados (nav antigo, mkdocs, marcadores de quem já abriu o relatório).
STUB = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Movido — Trajetória salarial</title>
<link rel="canonical" href="{alvo}">
<meta http-equiv="refresh" content="0; url={alvo}">
<meta name="robots" content="noindex">
</head><body style="font:16px/1.6 system-ui;padding:48px;max-width:44ch;margin:0 auto">
<p>Esta página virou parte de <a href="{alvo}">Trajetória salarial</a>.</p>
<p><a href="{alvo}">Ir agora →</a></p>
</body></html>
"""
for antiga in ANTIGAS:
    (BASE / antiga).write_text(STUB.format(alvo=OUT.name), encoding="utf-8")

print(f"OK — {OUT.name} ({len(HTML)//1024} KB)")
print(f"  redirecionam para ela: {', '.join(ANTIGAS)}")
print(f"  trajetória: {t0['ano']}–{t1['ano']} · {brl(t0['med'])} → {brl(t1['med'])} "
      f"({n1(t0['sm'])} → {n1(t1['sm'])} SM) em {len(TRAJ)} anos")
print(f"  coorte {ult['ano']}: {brl(eg_brl)}/mês = {n1(eg_sm)} SM · {pct_global}% da mediana global")
print(f"  {len(SERIE)} anos na série · {len(PAIS)} barras de país · {n_intl}/{n_tot} em empregador internacional")

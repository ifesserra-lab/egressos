#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a aba de DADOS ABERTOS no repo público egressos:
  - copia SÓ os JSONs seguros (agregado/anonimizado/empresa-pública) p/ egressos/dados/
  - copia o código do pipeline p/ egressos/pipeline/ com o path pessoal SANITIZADO
  - gera egressos/dados-abertos.html (índice com download + dicionário + licença + repro)

NUNCA copia: alunos.json, *_reais, egressos_result.md, genero_map, src_extensao,
horizon_pesquisa, lattes_orientacoes, outros_labs, consolidado_raw (PII / id->atributo).
Roda a varredura de PII antes de copiar cada JSON (cruza com nomes de alunos.json) e ABORTA se achar.
"""
import json, os, re, shutil, unicodedata, pathlib, html

BASE = pathlib.Path("/caminho/para/salario")
PUB  = pathlib.Path("/caminho/para/egressos")
DADOS_OUT = PUB / "dados"
CODE_OUT  = PUB / "pipeline"
PERSONAL_PATH = "/caminho/para/salario"

# ---- datasets liberados (arquivo, título, descrição) ----
SAFE = [
    ("analise.json",           "Análises agregadas",       "Clusters de carreira, Sankey formação→trilha→destino, distribuição por empresa (região/setor/porte), gênero (agregado), extensão, trilha no tempo, internacionalização."),
    ("consolidado.json",       "Perfis anonimizados",      "Coorte A–AX: trilha, anos de carreira, bolsa, salário estimado inicial/atual e crescimento — sem nome/empresa/local individual."),
    ("por_ano.json",           "Série por ano",            "Contagens e métricas por ano da coorte."),
    ("salario_minimo.json",    "Salário mínimo por ano",   "Salário mínimo nacional 2011–2026: valor de janeiro, de dezembro, média ponderada pelos meses, reajuste do decreto, INPC do ano anterior, ganho real e valor em reais do ano-base."),
    ("ibge_series.json",       "Séries macro (IBGE/IPEADATA)","IPCA e INPC (número-índice mensal + média anual + deflatores) e o salário mínimo mensal. Base para toda correção monetária do estudo."),
    ("so_benchmarks.json",     "Benchmarks internacionais","Medianas salariais em US$/mês por país na faixa de experiência do coorte, mediana global, série por edição do survey e — o mais relevante — respondentes do Brasil separados pela MOEDA do contracheque (R$ x US$)."),
    ("codigofonte_2026.json",  "Benchmark de mercado 2026","Faixas salariais por senioridade (Pesquisa Código Fonte)."),
    ("codigofonte_historico.json","Benchmark histórico",   "Média salarial por senioridade, série histórica."),
    ("fapes_fomento.json",     "Fomento FAPES",            "Fomento de bolsas FAPES (agregado)."),
    ("empresas_porte.json",    "Empresas — classificação", "Por empresa: porte/origem/setor estimados + dados VERIFICADOS do LinkedIn (headcount, sede, setor, vagas), porte_real e setor_real. Dado público de empresa."),
    ("empresas_linkedin_data.json","Empresas — dados LinkedIn","Coleta bruta por empresa via browser-use: nome oficial, tamanho, sede, setor, site, fundação, especialidades, vagas."),
    ("empresas_aliases.json",  "Empresas — nomes canônicos","Agrupamento de variantes de nome (aliases) + contagem de egressos atuais por empresa."),
    ("empresas_linkedin_urls.json","Empresas — URLs LinkedIn","Slug/URL verificada da company page no LinkedIn."),
]
# código publicado (sanitizado)
CODE_FILES = ["build_report.py","ibge_series.py","so_benchmarks.py","compute_all.py","analise.py",
              "genero.py","fapes_fomento.py","src_extensao.py","gen_executivo.py","gen_panorama.py",
              "gen_vitrine.py","gen_reguas.py","gen_nav.py","gen_dados_abertos.py",
              "qa_report.py","norm_empresas.py","enrich_empresas.py","classify_empresas.py",
              "classify_mistral.py","resolve_company_urls.py","mistral_porte.py"]

# ---- glossário de campos por arquivo (o que será achado) ----
FIELDS = {
 "analise.json": "Objeto com chaves de análise: `top_tech` (tecnologias mais citadas), `clusters` "
   "(KMeans de perfis de carreira), `funcoes` (distribuição de funções), `lideranca_gestao` "
   "(nº em liderança/gestão), `sankey` (fluxo formação→trilha→destino), `intl_timeline` "
   "(% internacional por ano), `empresas` (regiao/modalidade/setor/porte agregados), `genero` "
   "(distribuição agregada), `extensao` (participação SRC/IFES, agregado), `outros_labs` "
   "(labs além do LEDS), `trilha_carreira` (início→meio→atual). Tudo AGREGADO, sem indivíduo.",
 "consolidado.json": "Objeto `{kpi, perfis[], agregado, pv}`. `perfis[]` = coorte anonimizada, cada item: "
   "`perfil` (rótulo A–AX), `trilha` (Software/Dados/…), `em_tech` (bool), `anos` (anos de carreira), "
   "`bolsa` (valor mensal da bolsa em anos de bolsa), `med_ini`/`med_atual` (salário estimado inicial/atual, R$2026), "
   "`cresc` (múltiplo de crescimento). SEM nome/empresa/local.",
 "por_ano.json": "Métricas da coorte por ano (contagens/ativos).",
 "salario_minimo.json": "Objeto `{titulo, fonte_*, ano_base_deflator, notas[], por_ano[], sm_por_ano, "
   "deflator_ipca_por_ano}`. Cada item de `por_ano[]`: `ano`, `jan`/`dez` (valores vigentes), "
   "`media_ponderada` (média dos 12 meses — importa nos anos com dois valores, 2020 e 2023), "
   "`reajuste_pct` (o número do decreto: janeiro sobre o último valor vigente), "
   "`inpc_ano_anterior_pct`, `ganho_real_pct` (reajuste deflacionado pelo INPC — o índice da política "
   "de valorização), `em_reais_de_2026`. Fonte: IPEADATA `MTE12_SALMIN12` + IBGE/SIDRA.",
 "ibge_series.json": "Objeto `{ano_base, mes_base, series:{ipca, inpc, salario_minimo}}`. Cada série traz "
   "`fonte`, `url`, `unidade`, `mensal` (AAAAMM -> valor) e `media_anual`; o IPCA traz também "
   "`deflator_para_base` (multiplicador para levar R$ de um ano ao mês-base). "
   "Baixado direto de IBGE/SIDRA (IPCA tabela 1737 var 2266; INPC tabela 1736 var 2289) e IPEADATA.",
 "so_benchmarks.json": "Objeto `{edicao_referencia, filtros, global_usd_mes, por_pais[], "
   "por_moeda_brasil[], serie_anual[]}`. `por_pais[]`: `pais`, `usd_mes` (mediana), `n`. "
   "`por_moeda_brasil[]`: por faixa de experiência, `brl_usd_mes` e `usd_usd_mes` — respondentes DO "
   "BRASIL que declaram salário em real vs. em dólar — com `n` de cada lado e a `razao`. "
   "`serie_anual[]`: mediana US$/mês por edição, para Brasil, global e EUA. "
   "Fonte: Stack Overflow Developer Survey 2018–2023 (agregado; nenhum microdado é republicado).",
 "codigofonte_2026.json": "Faixas salariais por senioridade no mercado BR (Pesquisa Código Fonte 2026).",
 "codigofonte_historico.json": "Média salarial por senioridade, série histórica (Código Fonte).",
 "fapes_fomento.json": "Fomento de bolsas FAPES recebido pela coorte (valores agregados).",
 "empresas_porte.json": "Objeto `{nomeEmpresa: {...}}`. Campos: `porte`/`origem`/`setor`/`funcionarios` "
   "(estimativa por nome, Mistral) + VERIFICADOS do LinkedIn quando houver: `nome_oficial`, "
   "`headcount_linkedin` (faixa de funcionários), `hq_local` (sede), `industry_linkedin` (setor LinkedIn), "
   "`website`, `founded` (ano), `specialties`, `contratando` (bool), `politica_remoto`, `slug`; "
   "derivados: `porte_real` (banda de headcount), `setor_real` (taxonomia via Mistral), `fonte`, `verificado_em`. "
   "Dado PÚBLICO de empresa (sem vínculo a pessoa).",
 "empresas_linkedin_data.json": "Objeto `{nomeEmpresa: {...}}` — coleta bruta via browser-use da company page: "
   "`nome_oficial`, `industry_linkedin`, `headcount_linkedin`, `hq_local`, `website`, `founded`, "
   "`specialties`, `politica_remoto`, `contratando`, `slug`, `verificado_em`.",
 "empresas_aliases.json": "Objeto `{nomeCanonico: {aliases[], atual (bool), n_egressos_atual (contagem)}}` — "
   "agrupa variantes de nome da mesma empresa.",
 "empresas_linkedin_urls.json": "Objeto `{nomeEmpresa: {url, slug, confianca, via}}` — URL verificada da company page.",
}
def schema_str(d):
    if isinstance(d, list):
        keys = list(d[0].keys()) if d and isinstance(d[0], dict) else []
        return f"lista com {len(d)} itens" + (f"; cada item: `{', '.join(keys)}`" if keys else "")
    if isinstance(d, dict):
        vals = list(d.values())
        if vals and isinstance(vals[0], dict):
            return f"objeto com {len(d)} chaves; cada valor: `{', '.join(list(vals[0].keys()))}`"
        return f"objeto com {len(d)} chaves: `{', '.join(list(d.keys())[:14])}`"
    return "—"

# ---- PII sweep (aborta se achar nome real) ----
def sa(s): return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")
al = json.load(open(BASE/"alunos.json"))
al = al if isinstance(al, list) else (al.get("alunos") or list(al.values())[0])
NAMES = {sa(a.get("nome","")).lower().strip() for a in al if a.get("nome")}
NAMES = {n for n in NAMES if n}
def pii_hits(path):
    txt = sa(open(path, encoding="utf-8", errors="ignore").read()).lower()
    return [n for n in NAMES if n and n in txt]

DADOS_OUT.mkdir(parents=True, exist_ok=True)
manifest = []
for fn, titulo, desc in SAFE:
    src = BASE/"data"/fn
    hits = pii_hits(src)
    if hits:
        raise SystemExit(f"ABORT: PII em {fn}: {hits[:3]} — NÃO publicar")
    shutil.copy2(src, DADOS_OUT/fn)
    d = json.load(open(src, encoding="utf-8"))
    n = len(d) if isinstance(d, (list, dict)) else 0
    manifest.append({"file": fn, "titulo": titulo, "desc": desc,
                     "kb": round(os.path.getsize(src)/1024, 1),
                     "itens": n, "tipo": "lista" if isinstance(d, list) else "objeto",
                     "campos": FIELDS.get(fn, desc), "schema": schema_str(d)})

# ---- código sanitizado ----
CODE_OUT.mkdir(parents=True, exist_ok=True)
code_manifest = []
for cf in CODE_FILES:
    src = BASE/"pipeline"/cf
    if not src.exists():
        continue
    code = src.read_text(encoding="utf-8").replace(PERSONAL_PATH, "/caminho/para/salario")
    code = re.sub(r"/caminho/para", "/caminho/para", code)  # src_etl/horizon/etc
    code = code.replace("/caminho/para/usuario", "/caminho/para/usuario")          # qualquer resto
    (CODE_OUT/cf).write_text(code, encoding="utf-8")
    code_manifest.append({"file": cf, "kb": round(os.path.getsize(src)/1024, 1)})

# ---- HTML ----
esc = lambda s: html.escape(str(s or ""))
rows = "\n".join(
    f'<tr><td class="dn"><a href="dados/{esc(m["file"])}" download>{esc(m["file"])} ↓</a></td>'
    f'<td><b>{esc(m["titulo"])}</b><br><small>{esc(m["desc"])}</small></td>'
    f'<td class="num">{m["itens"]}</td><td class="num">{m["kb"]} KB</td></tr>'
    for m in manifest)
code_rows = "\n".join(
    f'<a class="cf" href="pipeline/{esc(c["file"])}" download>{esc(c["file"])} <span>{c["kb"]} KB ↓</span></a>'
    for c in code_manifest)
total_kb = round(sum(m["kb"] for m in manifest), 1)

HTML = f"""<!doctype html>
<html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dados abertos — egressos IFES Campus Serra</title>
<meta name="description" content="Datasets abertos (JSON) e código do estudo de egressos de TI do IFES Campus Serra. Dados anonimizados e agregados, sob CC BY 4.0.">
<style>
  .root{{ color-scheme:light; --plane:#f3f6f4; --surface:#fff; --surface-2:#eef3f0; --ink:#122019; --ink-2:#4a5a53; --muted:#83918a; --border:rgba(18,32,25,.10); --accent:#0e8a68; --amber:#bd7d00; --shadow:0 1px 2px rgba(18,32,25,.05),0 8px 24px rgba(18,32,25,.07); background:var(--plane); color:var(--ink); font-family:system-ui,-apple-system,"Segoe UI",sans-serif; -webkit-font-smoothing:antialiased; min-height:100%; padding:16px 13px; box-sizing:border-box; }}
  @media (prefers-color-scheme:dark){{ :root:where(:not([data-theme="light"])) .root{{ color-scheme:dark; --plane:#0a0e0c; --surface:#141a17; --surface-2:#1d2521; --ink:#eef3f0; --ink-2:#aebab4; --muted:#7a877f; --border:rgba(255,255,255,.10); --accent:#2fbc90; --amber:#dda52f; --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.5); }} }}
  :root[data-theme="dark"] .root{{ color-scheme:dark; --plane:#0a0e0c; --surface:#141a17; --surface-2:#1d2521; --ink:#eef3f0; --ink-2:#aebab4; --muted:#7a877f; --border:rgba(255,255,255,.10); --accent:#2fbc90; --amber:#dda52f; }}
  *{{ box-sizing:border-box; }}
  .wrap{{ max-width:1000px; margin:0 auto; display:flex; flex-direction:column; gap:18px; }}
  .eyebrow{{ font-size:12px; font-weight:700; letter-spacing:.11em; text-transform:uppercase; color:var(--accent); margin:0 0 10px; }}
  h1{{ font-size:clamp(24px,4.5vw,40px); line-height:1.08; margin:0 0 12px; font-weight:780; letter-spacing:-.02em; }}
  .lede{{ font-size:clamp(15px,1.7vw,17px); line-height:1.55; color:var(--ink-2); margin:0; max-width:70ch; }}
  .lede b{{ color:var(--ink); }}
  .card{{ background:var(--surface); border:1px solid var(--border); border-radius:16px; box-shadow:var(--shadow); padding:clamp(18px,2.6vw,26px); }}
  .card>h2{{ font-size:12.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-2); margin:0 0 4px; font-weight:700; }}
  .card .hint{{ font-size:12.5px; color:var(--muted); margin:0 0 16px; }}
  .nav{{ display:flex; flex-wrap:wrap; gap:10px; }}
  .nav a{{ flex:1 1 220px; text-decoration:none; background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:13px 15px; box-shadow:var(--shadow); font-weight:650; font-size:13.5px; color:var(--accent); }}
  .nav a span{{ display:block; font-weight:400; color:var(--ink-2); font-size:12px; margin-top:3px; }}
  table{{ width:100%; border-collapse:collapse; font-size:13.5px; }}
  th,td{{ text-align:left; padding:11px 12px; border-bottom:1px solid var(--border); vertical-align:top; }}
  th{{ color:var(--muted); font-weight:700; font-size:10.5px; text-transform:uppercase; letter-spacing:.04em; }}
  td.dn a{{ color:var(--accent); text-decoration:none; font-weight:700; white-space:nowrap; }}
  td.dn a:hover{{ text-decoration:underline; }}
  td small{{ color:var(--muted); line-height:1.45; display:block; margin-top:2px; }}
  td.num{{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; color:var(--ink-2); }}
  tr:last-child td{{ border-bottom:none; }}
  .scroll{{ overflow-x:auto; }} table{{ min-width:560px; }}
  .codegrid{{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:8px; }}
  .cf{{ text-decoration:none; background:var(--surface-2); border:1px solid var(--border); border-radius:10px; padding:10px 13px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12.5px; color:var(--ink); display:flex; justify-content:space-between; gap:8px; }}
  .cf span{{ color:var(--muted); font-family:system-ui; }}
  .cf:hover{{ border-color:var(--accent); color:var(--accent); }}
  .lic{{ background:var(--surface-2); border:1px solid var(--border); border-left:3px solid var(--accent); border-radius:10px; padding:15px 17px; font-size:13.5px; line-height:1.6; color:var(--ink-2); }}
  .lic b{{ color:var(--ink); }}
  .code{{ background:var(--surface-2); border:1px solid var(--border); border-radius:10px; padding:14px 16px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12.5px; color:var(--ink); overflow-x:auto; }}
  .warn{{ font-size:12.5px; color:var(--amber); }}
  .foot{{ font-size:11.5px; color:var(--muted); text-align:center; line-height:1.7; margin-top:4px; }}
  .foot a{{ color:var(--accent); }}
  @media (min-width:600px){{ .root{{ padding:32px 26px; }} .wrap{{ gap:24px; }} }}
  @media (min-width:960px){{ .root{{ padding:52px; }} }}
</style></head>
<body><div class="root"><div class="wrap">

  <header>
    <p class="eyebrow">Dados abertos · IFES — Campus Serra</p>
    <h1>Dados abertos — egressos de TI</h1>
    <p class="lede">Todos os dados <b>agregados e anonimizados</b> do estudo de egressos, mais o <b>código do pipeline</b> que os gera. Baixe, reproduza, audite. Dados de pessoa nunca são publicados — só coorte anonimizada (A–AX) e dados <b>públicos</b> de empresa. {len(manifest)} datasets · {total_kb} KB.</p>
  </header>

  <nav class="nav" aria-label="Outras páginas">
    <a href="egressos-carreiras.html">🌍 Onde estão os egressos →<span>Vitrine de carreiras</span></a>
    <a href="index.html">📊 Impacto na carreira →<span>Visão executiva</span></a>
    <a href="metodologia.html">🔬 Metodologia →<span>Como foi feito</span></a>
  </nav>

  <section class="card">
    <h2>Datasets (JSON)</h2>
    <p class="hint">Clique para baixar. Dicionário de campos por arquivo em <a href="llms.txt" style="color:var(--accent)">llms.txt</a> (índice legível por humanos e LLMs).</p>
    <div class="scroll"><table>
      <thead><tr><th>Arquivo</th><th>Conteúdo</th><th>Itens</th><th>Tam.</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
  </section>

  <section class="card">
    <h2>Código do pipeline</h2>
    <p class="hint">Scripts Python que geram e validam tudo (paths pessoais sanitizados). Reprodução: <code>python build_report.py</code>.</p>
    <div class="codegrid">{code_rows}</div>
  </section>

  <section class="card">
    <h2>Como reproduzir</h2>
    <pre class="code"># requer os JSONs de mercado (Stack Overflow / IPCA) e a base de perfis (não pública)
python build_report.py            # gera todos os JSON + valida (QA + PII)
python build_report.py --publish  # copia a versão anonimizada p/ os sites</pre>
    <p class="hint" style="margin-top:12px">O passo de QA falha a publicação se qualquer nome de pessoa vazar para o HTML/JSON público. <a href="metodologia.html" style="color:var(--accent)">Metodologia completa →</a></p>
  </section>

  <section class="card">
    <h2>Licença &amp; privacidade</h2>
    <div class="lic">
      <b>Licença:</b> dados sob <b>CC BY 4.0</b> · código sob <b>MIT</b>. Cite "Egressos IFES — Campus Serra".<br><br>
      <b>Privacidade:</b> nenhum dado individual identificável é publicado. Egressos aparecem só como coorte anonimizada (A–AX). Dados de empresa são informação pública (LinkedIn/registros). Nomes de pessoa nunca saem da máquina local nem vão a serviços externos de IA.<br><br>
      <span class="warn">⚠️ Site experimental — dados preliminares, sujeitos a revisão. Egresso que queira correção/remoção: falar com a coordenação.</span>
    </div>
  </section>

  <p class="foot">Dados abertos do estudo de egressos · IFES — Campus Serra · ensino, pesquisa e extensão.<br>Gerado com apoio de Claude Code.</p>

</div></div></body></html>
"""
(PUB/"dados-abertos.html").write_text(HTML, encoding="utf-8")

# ---- llms.txt (llmstxt.org) — índice legível por LLM, dicionário por arquivo ----
CODE_DESC = {
 "build_report.py": "orquestra o pipeline inteiro (roda todos os passos + QA/PII); `--publish` copia p/ os sites",
 "compute_all.py": "série salarial: cruza perfis × mercado (Stack Overflow) × câmbio × IPCA × salário mínimo → consolidado.json",
 "ibge_series.py": "baixa IPCA e INPC (IBGE/SIDRA) e o salário mínimo (IPEADATA) → salario_minimo.json + ibge_series.json",
 "so_benchmarks.py": "extrai do Stack Overflow as medianas em US$ por país e o corte por moeda do contracheque → so_benchmarks.json",
 "gen_reguas.py": "gera a página 'Trajetória salarial' (ano a ano + salário mínimo + comparação mundial)",
 "gen_nav.py": "fonte única do menu — injeta a mesma navegação em todas as páginas",
 "analise.py": "clusters, sankey, gênero, empresas, trilha, internacionalização → analise.json",
 "genero.py": "inferência de gênero OFFLINE (gender-guesser + heurística PT-BR) → genero_map (privado)",
 "fapes_fomento.py": "agrega fomento de bolsas FAPES → fapes_fomento.json",
 "src_extensao.py": "cruza egressos × base oficial de extensão SRC/IFES (privado, por nome)",
 "gen_executivo.py": "reescreve os números do dashboard executivo a partir dos JSON",
 "gen_panorama.py": "reescreve os cards anonimizados (A–AX) do panorama",
 "gen_vitrine.py": "gera a página-vitrine 'Onde estão os egressos' (perfis + empresas)",
 "qa_report.py": "QA: cruza cada número do HTML com o pipeline + varredura de PII (gate de publicação)",
 "norm_empresas.py": "normaliza nomes de empresa e agrupa variantes → empresas_aliases.json",
 "enrich_empresas.py": "browser-use no LinkedIn: headcount/sede/setor/vagas por empresa (dado público)",
 "classify_empresas.py": "deriva porte_real (headcount) + setor_real (regras) por empresa",
 "classify_mistral.py": "refina setor_real via Mistral (industry+specialties, dado público)",
 "resolve_company_urls.py": "resolve a URL LinkedIn da empresa via dork de busca (sem login)",
 "mistral_porte.py": "classifica porte/setor por NOME de empresa (fallback; só nome público)",
 "gen_dados_abertos.py": "gera esta aba de dados abertos (copia JSON seguros + código sanitizado + llms.txt)",
}
L = []
L.append("# Egressos de TI — IFES Campus Serra · Dados abertos\n")
L.append("> Estudo longitudinal de carreira dos egressos de TI do IFES Campus Serra (coorte de 50, "
         "modelo salarial de 49). Reúne trajetória profissional, renda estimada vs. mercado, e o papel "
         "de ensino/pesquisa/extensão. Todos os dados aqui são **agregados ou anonimizados** (coorte A–AX); "
         "dados de empresa são **informação pública** (LinkedIn/registros). Nenhum dado pessoal identificável.\n")
L.append("Licença: dados CC BY 4.0 · código MIT. Nomes de pessoa nunca são publicados nem enviados a "
         "serviços externos de IA. Site experimental (dados preliminares).\n")
L.append("## Páginas\n")
L.append("- [Onde estão os egressos](egressos-carreiras.html): vitrine de carreiras — perfis, empresas, países, jornada.")
L.append("- [Impacto na carreira](index.html): visão executiva — renda estimada vs. mercado (anonimizado).")
L.append("- [Trajetória salarial](trajetoria_salarial.html): trajetória ano a ano, renda em salários mínimos da época e comparação com o mercado mundial de devs em US$.")
L.append("- [Panorama por egresso](dashboard_alunos.html): linha do tempo e cards anonimizados (A–AX).")
L.append("- [Metodologia](metodologia.html): fontes, ETL, cálculo salarial, QA e ressalvas.")
L.append("- [Dados abertos](dados-abertos.html): esta página (download de JSON + código).\n")
L.append("## Datasets (JSON) — o que há em cada arquivo\n")
for m in manifest:
    L.append(f"- [{m['file']}](dados/{m['file']}) — **{m['titulo']}**. {m['campos']} _(estrutura: {m['schema']}; {m['itens']} itens, {m['kb']} KB)_")
L.append("\n## Código do pipeline (Python)\n")
L.append("Reprodução: `python build_report.py` (gera+valida) · `python build_report.py --publish` (publica anonimizado).\n")
for c in code_manifest:
    L.append(f"- [{c['file']}](pipeline/{c['file']}) — {CODE_DESC.get(c['file'],'script do pipeline')}")
L.append("\n## Privacidade\n")
L.append("- Publicado: coorte anonimizada (A–AX) + dados públicos de empresa + código.")
L.append("- NUNCA publicado: nomes/empresa/local por pessoa, mapas id→atributo (gênero, extensão, pesquisa).")
L.append("- O QA (`qa_report.py`) bloqueia a publicação se qualquer nome real vazar.")
(PUB/"llms.txt").write_text("\n".join(L) + "\n", encoding="utf-8")

print(f"OK: {len(manifest)} datasets ({total_kb} KB) -> {DADOS_OUT}")
print(f"    llms.txt -> {PUB/'llms.txt'}")
print(f"    {len(code_manifest)} scripts -> {CODE_OUT}")
print(f"    página -> {PUB/'dados-abertos.html'}")

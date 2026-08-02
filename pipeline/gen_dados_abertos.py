#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a aba de DADOS ABERTOS no repo público egressos:
  - copia SÓ os JSONs seguros (agregado/anonimizado/empresa-pública) p/ egressos/dados/
  - copia o código do pipeline p/ egressos/pipeline/ com o path pessoal SANITIZADO
  - gera egressos/dados-abertos.html (índice com download + dicionário + licença + repro)

NUNCA copia: alunos.json, *_reais, egressos_result.md, genero_map, src_extensao,
horizon_pesquisa, lattes_orientacoes, outros_labs, consolidado_raw (PII / id->atributo)
e por_ano (despublicado em 2026-07-31: trajetória individual, não agregado).
A lista de liberados NÃO é a SAFE abaixo — quem decide é egressos_core.dados.
Roda a varredura de PII antes de copiar cada JSON (cruza com nomes de alunos.json) e ABORTA se achar.
"""
import json
import os
import pathlib
import shutil

from egressos_core import dados
from egressos_core.paths import PUB
from egressos_core.paths import ROOT as BASE
from egressos_core.text import strip_accents

DADOS_OUT = PUB / "dados"
CODE_OUT  = PUB / "pipeline"
PERSONAL_PATH = str(BASE)

# ---- datasets liberados (arquivo, título, descrição) ----
SAFE = [
    ("analise.json",           "Análises agregadas",       "Clusters de carreira, Sankey formação→trilha→destino, distribuição por empresa (região/setor/porte), gênero (agregado), extensão, trilha no tempo, internacionalização."),
    ("consolidado.json",       "Perfis anonimizados",      "Coorte A–AX: trilha, anos de carreira, bolsa, salário estimado inicial/atual e crescimento — sem nome/empresa/local individual."),
    ("salario_minimo.json",    "Salário mínimo por ano",   "Salário mínimo nacional 2011–2026: valor de janeiro, de dezembro, média ponderada pelos meses, reajuste do decreto, INPC do ano anterior, ganho real e valor em reais do ano-base."),
    ("ibge_series.json",       "Séries macro (IBGE/IPEADATA)","IPCA e INPC (número-índice mensal + média anual + deflatores) e o salário mínimo mensal. Base para toda correção monetária do estudo."),
    ("mapa_mundi.json",        "Contorno do mapa-múndi",   "Polígonos dos continentes (Natural Earth 110m) já projetados em coordenadas SVG, usados no mapa animado da vitrine de carreiras. Domínio público."),
    ("egressos_perfil.json",   "Perfis dos egressos",      "Nome, curso, cargo, empresa e cidade de cada egresso, mais senioridade e anos de carreira. Dado de nível LinkedIn — o que a própria pessoa publica —, divulgado por decisão da coordenação. NÃO contém renda: a estimativa é por SENIORIDADE, no arquivo ao lado."),
    ("renda_por_senioridade.json",   "Renda estimada por senioridade", "Faixa p25–mediana–p75 ESTIMADA por senioridade e trilha, com a amostra de mercado de cada uma. Nenhum salário foi coletado de ninguém: o valor é o que o mercado pagava para aquele nível de experiência, e para uma pessoa concreta pode ser maior ou menor. Sem nenhuma chave de pessoa."),
    ("cargos_ao_longo_do_tempo.json","Renda estimada por cargo, 2018–2025","Mediana de R$/mês por CARGO no mercado brasileiro (back-end, DBA, DevOps, ciência de dados...), ano a ano, a preços de hoje. Cargo é o outro eixo: senioridade é júnior/pleno/sênior, e está no arquivo ao lado. Cada resposta converte pelo câmbio do ANO dela e é deflacionada pelo IPCA. Mercado inteiro do survey — nenhuma pessoa deste estudo está aqui."),
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
              "mapa_base.py","gen_vitrine.py","gen_reguas.py","gen_nav.py","gen_api.py","gen_dados_abertos.py",
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
 "mapa_mundi.json": "Objeto `{viewBox, lat_range, projecao, paths[], fonte}`. `paths[]` são strings "
   "`d` de SVG já projetadas (equirretangular). Para posicionar um ponto: "
   "`x = (lon+180)/360*W`, `y = (lat_max-lat)/(lat_max-lat_min)*H`. Fonte: Natural Earth 110m (domínio público).",
 "cargos_ao_longo_do_tempo.json": "Objeto `{unidade, ano_base, edicoes[], "
   "minimo_de_respostas_por_ponto, n_respostas_por_edicao{}, cargos[]}`. Cada item de "
   "`cargos[]`: `cargo` (chave), `nome`, `pontos[]` com `{ano, real, nominal, n}`, mais "
   "`n_edicoes`, `edicoes_ausentes[]` e `variacao_pct` (real; `null` quando há um ponto só). "
   "`real` está a preços do `ano_base` (IPCA); `nominal` é o valor da época. Ano cuja amostra "
   "não chega ao mínimo NÃO vira ponto — fica em `edicoes_ausentes`, sem interpolação. "
   "`DevType` é múltipla escolha, então a soma dos `n` passa do total de respondentes. "
   "Fonte: Stack Overflow Developer Survey 2018–2025 (agregado; nenhum microdado é republicado).",
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
al = dados.ler("alunos")
al = al if isinstance(al, list) else (al.get("alunos") or list(al.values())[0])
NAMES = {strip_accents(a.get("nome","")).lower().strip() for a in al if a.get("nome")}
NAMES = {n for n in NAMES if n}
# A vitrine nomeada é exceção AUTORIZADA: nome, cargo, empresa e cidade são dado de nível
# LinkedIn, que a própria pessoa publica, e a coordenação decidiu divulgar. A varredura de nomes
# não se aplica a ela — se aplicasse, ela nunca publicaria.
#
# Mas exceção sem portão é buraco. O que torna a vitrine aceitável não é a autorização sozinha:
# é ela NÃO TER RENDA. O número de renda nunca foi da pessoa (é a faixa de mercado para a
# experiência dela), e foi juntar as duas coisas no mesmo registro que fez analise.json publicar
# nome + empresa + cargo + salário estimado. Então a exceção vem com verificação própria, que
# roda a cada publicação — não só na suíte.
VITRINE_NOMEADA = {"egressos_perfil.json"}
CHEIRO_DE_RENDA = ("salario", "renda", "med_atual", "med_ini", "remunera", "p25", "p75",
                   "mediana", "cresc", "brl", "usd", "valor")


def _chaves_de_dinheiro(no):
    """Toda chave com cheiro de dinheiro, em QUALQUER profundidade.

    Recursivo porque a versão rasa deixava passar o caso real: `bolsa_valor_mensal` mora dentro
    de `experiencias[]`, não no topo do registro da pessoa. Portão que só olha o primeiro nível
    dá a impressão de proteger e não protege.
    """
    achadas = set()
    if isinstance(no, dict):
        for chave, valor in no.items():
            if any(t in chave.lower() for t in CHEIRO_DE_RENDA):
                achadas.add(chave)
            achadas |= _chaves_de_dinheiro(valor)
    elif isinstance(no, list):
        for item in no:
            achadas |= _chaves_de_dinheiro(item)
    return achadas



def renda_em_registro_de_pessoa(caminho):
    """Chaves de dinheiro dentro dos registros da vitrine. Vazio = pode publicar."""
    conteudo = json.load(open(caminho, encoding="utf-8"))
    return sorted(_chaves_de_dinheiro(conteudo.get("egressos", [])))


def pii_hits(path):
    if os.path.basename(path) in VITRINE_NOMEADA:
        return []                       # nome é a decisão; o portão dela é o de renda
    txt = strip_accents(open(path, encoding="utf-8", errors="ignore").read()).lower()
    return [n for n in NAMES if n and n in txt]

DADOS_OUT.mkdir(parents=True, exist_ok=True)

# Quem DECIDE o que pode ser publicado é o catálogo (egressos_core.dados). A lista SAFE acima
# ficou sendo só apresentação — título, descrição e a ORDEM das linhas da página. Antes, a
# fronteira de privacidade eram duas listas escritas à mão (a SAFE e o "NUNCA copia" do
# docstring) que precisavam concordar, e nada verificava que concordavam.
_NOME_POR_ARQUIVO = {ds.arquivo.removeprefix("data/"): ds.nome for ds in dados.CATALOGO.values()}
_do_catalogo = {dados.caminho(n).name for n in dados.publicaveis()}
_declarados = {fn for fn, *_ in SAFE}
if _do_catalogo != _declarados:
    raise SystemExit(
        "ABORT: catálogo e SAFE divergem — "
        f"só no catálogo: {sorted(_do_catalogo - _declarados)}; "
        f"só na SAFE: {sorted(_declarados - _do_catalogo)}. "
        "Classifique em egressos_core.dados antes de publicar."
    )

manifest = []
for fn, titulo, desc in SAFE:
    nome = _NOME_POR_ARQUIVO[fn]
    dados.exige_publicavel(nome)      # portão: dataset pii ou interno para aqui
    src = dados.caminho(nome)
    hits = pii_hits(src)
    if hits:
        raise SystemExit(f"ABORT: PII em {fn}: {hits[:3]} — NÃO publicar")
    if fn in VITRINE_NOMEADA:
        com_renda = renda_em_registro_de_pessoa(src)
        if com_renda:
            raise SystemExit(
                f"ABORT: {fn} é a vitrine NOMEADA e ganhou campo de renda: {com_renda}. "
                "Renda por pessoa é estimativa que a metodologia não mede no indivíduo — ela "
                "vai em renda_por_senioridade.json, atrelada ao cargo. NÃO publicar.")
    shutil.copy2(src, DADOS_OUT/fn)
    d = dados.ler(nome)
    n = len(d) if isinstance(d, (list, dict)) else 0
    manifest.append({"file": fn, "titulo": titulo, "desc": desc,
                     "kb": round(os.path.getsize(src)/1024, 1),
                     "itens": n, "tipo": "lista" if isinstance(d, list) else "objeto",
                     "campos": FIELDS.get(fn, desc), "schema": schema_str(d)})

# ---- código sanitizado ----
CODE_OUT.mkdir(parents=True, exist_ok=True)
code_manifest = []
# Dois diretórios: `pipeline/` e `old/pipeline/`. Os geradores de HTML e o QA foram para
# `old/` na fatia A da spec 005 — continuam rodando e continuam sendo o código que produz o
# site, então continuam publicados. Ver old/README.md.
DIRS_DE_CODIGO = [BASE/"pipeline", BASE/"old"/"pipeline"]
for cf in CODE_FILES:
    src = next((d/cf for d in DIRS_DE_CODIGO if (d/cf).exists()), None)
    if src is None:
        # ABORTA em vez de pular. O `continue` silencioso que estava aqui fez seis scripts
        # sumirem da publicação quando eles mudaram de diretório — e o único sinal foi a
        # contagem no fim, que ninguém compara com nada.
        raise SystemExit(
            f"ABORT: {cf} está em CODE_FILES e não foi encontrado em "
            f"{', '.join(str(d.relative_to(BASE)) for d in DIRS_DE_CODIGO)}. "
            "Se o arquivo foi apagado, tire-o da lista; se mudou de lugar, acrescente o "
            "diretório novo. Sumir da publicação em silêncio, não."
        )
    # Saneamento do código publicado: tira qualquer caminho da máquina de quem gerou.
    # Derivado de BASE, não escrito à mão — um literal aqui volta a prender o pipeline a
    # um usuário (princípio IV da constituição) e falha calado na máquina de outra pessoa.
    code = src.read_text(encoding="utf-8").replace(PERSONAL_PATH, "/caminho/para/salario")
    code = code.replace(str(BASE.parent), "/caminho/para")                  # src_etl/horizon/etc
    code = code.replace(str(pathlib.Path.home()), "/caminho/para/usuario")  # qualquer resto
    (CODE_OUT/cf).write_text(code, encoding="utf-8")
    code_manifest.append({"file": cf, "kb": round(os.path.getsize(src)/1024, 1)})

# ---- HTML: NÃO SAI MAIS DAQUI ----
#
# A página `dados-abertos.html` passou a ser gerada pelo Astro na fatia B da spec 005:
# `packages/egressos-site/app/src/pages/dados-abertos.astro`. Este script continua fazendo o
# que só ele faz — copiar os JSON liberados e o código sanitizado para o repositório público,
# e rodar a varredura de PII em cada arquivo antes de copiar.
#
# O que a migração corrigiu, além do CSS duplicado: a constante `SAFE` acima era a TERCEIRA
# lista de datasets publicáveis do projeto, escrita à mão, ao lado do catálogo e do
# "NUNCA copia" do docstring. A página em Astro deriva a lista de `dados.publicaveis()` —
# dataset novo aparece sozinho, despublicado some sozinho.
#
# O portão REPROVA se esta página aparecer nas duas origens (aqui e em `site/`), então
# escrever daqui de novo não passa despercebido.

# Estes três valores serviam à página E ao llms.txt. A página saiu daqui na fatia B; o
# llms.txt continua, então eles continuam.
_terceiros = dados.licencas_de_terceiros()
try:
    _api = json.load(open(PUB / "api" / "index.json", encoding="utf-8"))["endpoints"]
except (OSError, KeyError, ValueError):
    _api = []
total_kb = round(sum(m["kb"] for m in manifest), 1)

# ---- llms.txt (llmstxt.org) — índice legível por LLM, dicionário por arquivo ----
CODE_DESC = {
 "build_report.py": "orquestra o pipeline inteiro (roda todos os passos + QA/PII); `--publish` copia p/ os sites",
 "compute_all.py": "série salarial: cruza perfis × mercado (Stack Overflow) × câmbio × IPCA × salário mínimo → consolidado.json",
 "ibge_series.py": "baixa IPCA e INPC (IBGE/SIDRA) e o salário mínimo (IPEADATA) → salario_minimo.json + ibge_series.json",
 "so_benchmarks.py": "extrai do Stack Overflow as medianas em US$ por país e o corte por moeda do contracheque → so_benchmarks.json",
 "mapa_base.py": "baixa o Natural Earth 110m e converte em paths SVG projetados -> mapa_mundi.json",
 "gen_reguas.py": "gera a página 'Trajetória salarial' (ano a ano + salário mínimo + comparação mundial)",
 "gen_api.py": "gera a API estática em egressos/api/ (endpoints anonimizados + índice)",
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
if _terceiros:
    L.append("Licença de dado de terceiro: alguns datasets são derivados de fontes externas com "
             "licença própria, que continua valendo para quem baixar daqui. Cada arquivo traz a "
             "sua no campo `licenca`: "
             + " · ".join(f"`{t['arquivo']}` = {t['licenca']}"
                          + (f" (atribuição: {t['atribuicao']})" if t["atribuicao"] else "")
                          for t in _terceiros) + "\n")
L.append("Licença: dados CC BY 4.0 · código MIT. Nomes de pessoa nunca são publicados nem enviados a "
         "serviços externos de IA. Site experimental (dados preliminares).\n")
L.append("## Páginas\n")
L.append("- [Onde estão os egressos](egressos-carreiras.html): vitrine de carreiras — perfis, empresas, países, jornada.")
L.append("- [Impacto na carreira](index.html): visão executiva — renda estimada vs. mercado (anonimizado).")
L.append("- [Trajetória salarial](trajetoria_salarial.html): trajetória ano a ano, renda em salários mínimos da época e comparação com o mercado mundial de devs em US$.")
L.append("- [Panorama por egresso](dashboard_alunos.html): linha do tempo e cards anonimizados (A–AX).")
L.append("- [Metodologia](metodologia.html): fontes, ETL, cálculo salarial, QA e ressalvas.")
L.append("- [Dados abertos](dados-abertos.html): esta página (download de JSON + código).\n")
L.append("## API estática (JSON por endpoint)\n")
L.append("Índice legível por máquina: [api/index.json](api/index.json). Sem chave e sem limite — "
         "arquivos estáticos regerados a cada atualização. Use quando quiser um recorte; use os "
         "datasets abaixo quando quiser tudo.\n")
for e in _api:
    L.append(f"- [{e['endpoint']}]({e['endpoint']}) — {e['descricao']}")
L.append("\n## Datasets (JSON) — o que há em cada arquivo\n")
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
print("    página dados-abertos.html -> gerada pelo Astro (site/), não daqui")

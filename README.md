# Egressos IFES/LEDS — Impacto de Ensino, Pesquisa e Extensão na Carreira

Dashboard executivo **anonimizado** da trajetória de carreira e renda de **11 egressos** que passaram pela mesma base na formação: **ensino** (monitoria), **pesquisa aplicada** com bolsa da **FAPES** (via Prodest) e **extensão** no **LEDS/IFES** — e hoje ocupam posições sênior em engenharia de software, dados, consultoria e liderança técnica.

🔗 **Site:** https://ifesserra-lab.github.io/egressos/

## O que o painel mostra

- **Crescimento salarial estimado por anos de experiência** — em duas leituras: *valor da época* (corrigido pela inflação) e *a valores de hoje* (mercado de 2026).
- **Comparação com o mercado nacional** (Pesquisa Código Fonte) — curva por senioridade, no valor da época e em 2026.
- **Escada de senioridade** e faixa de mercado (variação CLT↔PJ e entre estados).
- **Faixa de bolsa de pesquisa/extensão** (LEDS · Prodest · FAPES) destacada nos anos iniciais.
- **Análise do grupo** — tecnologias mais usadas, clusters de perfil e senioridade × empregador nacional/internacional.

## Principais números

- **11 de 11** seguem em tecnologia (1 no setor público, em dados).
- Crescimento real médio **11,3×** (até 17,9×), da bolsa à posição atual — já descontada a inflação.
- Mediana estimada hoje **~R$ 15,8 mil/mês** · faixa **R$ 14–20 mil**.
- **8 dos 11** começaram em bolsa/estágio (projeto FAPES ou extensão LEDS/IFES).
- **6 dos 11** atuam em empresas internacionais (Europa, América Latina, EUA/global).

## Fontes de dados

| Fonte | Uso |
|-------|-----|
| **FAPES** — base de alocação de bolsas (Res. 361/2026) | Valores **reais** das bolsas recebidas (BPIG, apoio técnico, ICT) |
| **Stack Overflow Developer Survey (2018–2023)** | Salários de desenvolvedores/dados no Brasil, por anos de experiência |
| **Pesquisa Código Fonte (2021–2026)** | Média salarial por senioridade no mercado brasileiro |
| **Câmbio médio anual USD→BRL** e **IPCA (IBGE)** | Conversão de tudo a poder de compra de **R$ de 2026** |

## Metodologia (resumo)

- Para cada egresso e cada ano de carreira, o ano de experiência é cruzado com a mediana de mercado **daquela época** (Stack Overflow), convertida por câmbio e IPCA → R$ de 2026.
- Os anos de bolsa usam o **valor documentado na base da FAPES**, não estimativa.
- *"A valores de hoje"* reprecifica cada nível pelo mercado de 2026.
- A linha *"valor da época"* da Código Fonte usa a edição do ano em que cada senioridade foi atingida, corrigida por IPCA (a pesquisa começou em 2021; níveis anteriores são extrapolados e marcados como tal).

## Ressalvas

- **Estimativa, não salário real** — baseada em medianas de mercado por experiência.
- **Anonimizado** — sem nomes, empresas ou localidades; apenas trilha (software/dados) e anos de experiência.
- O modelo **não captura o prêmio real** de contratos em moeda estrangeira (os preços derivam do mercado brasileiro).
- A faixa de mercado da Código Fonte é **ilustrativa** — a pesquisa publica apenas a média por senioridade, sem percentis.

## Estrutura do repositório

Três páginas únicas, autocontidas, sem dependências externas (mobile-first):

- `index.html` — dashboard executivo (visão financeira agregada).
- `dashboard_alunos.html` — panorama por egresso (A–K): linha do tempo e cards individuais, anonimizados.
- `evolucao_salario_local.html` — evolução salarial estimada ano a ano de um egresso (Stack Overflow + câmbio + IPCA).

> ⚠️ **Experimental / em construção.** Metodologia ainda em desenvolvimento; dados e conclusões preliminares, sujeitos a alteração.

---

<sub>Painel para fins de análise institucional do impacto de ensino, pesquisa e extensão. Gerado com apoio de Claude Code.</sub>

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera os dois artefatos da vitrine — e a separação entre eles é o ponto.

  egressos_perfil   quem é a pessoa: nome, curso, cargo, empresa, cidade, senioridade.
                    Dado de nível LinkedIn, público, por decisão da coordenação.
                    ZERO campo de renda.

  renda_por_senioridade   quanto o mercado paga para um CARGO: faixa estimada por senioridade
                    (e por trilha, quando o grupo aguenta). ZERO chave de pessoa.

Por que dois arquivos, e não um com tudo: o número de renda **nunca foi da pessoa**. Ele é a
mediana de mercado para a faixa de experiência dela, convertida por câmbio e deflacionada — o
modelo precifica dois egressos com os mesmos anos pelo mesmo valor, e o próprio artefato de
análise chama o "prêmio internacional de +6%" que ele calcula de artefato, porque os dois grupos
saem da mesma tabela brasileira.

Publicar `Fulano — R$ 16.194` publicaria um número que Fulano nunca declarou, que a metodologia
diz não medir Fulano, e que não tem como ser corrigido porque nunca foi um fato. Atrelado ao
CARGO, o mesmo número é exatamente o que ele é: estimativa de mercado, com faixa e com amostra.

Foi assim que `analise.json` vazou: nome, empresa, cargo e salário estimado no mesmo registro.
Dois arquivos com contratos diferentes tornam esse acidente impossível de repetir por descuido.

Uso:  python pipeline/gen_perfis.py
"""
from __future__ import annotations

import collections
import re
import statistics
import sys

import compute_all
from egressos_core import dados, deflator, vitrine
from egressos_core.deflator import Competencia
from egressos_core.text import norm

#: Campos da experiência que NÃO saem: valor de bolsa é dinheiro, e a jornada é pública só
#: no que o LinkedIn mostra. `descricao` fica de fora por ser texto livre — é onde uma frase
#: solta sobre outra pessoa apareceria sem ninguém revisar.
EXPERIENCIA_PUBLICA = ("cargo", "empresa", "tipo", "inicio", "fim", "duracao", "local",
                       "area", "skills")

#: Mínimo de pessoas para publicar uma faixa por senioridade. Abaixo disso a "faixa do nível" é a
#: estimativa de um indivíduo com outro rótulo — o mesmo defeito por outro caminho.
MIN_POR_GRUPO = 5

#: URL de PERFIL do LinkedIn, e nada além. O cadastro guarda em `url` o endereço de onde a
#: coleta leu a trajetória; publicar o campo cru publicaria o que a coleta escreveu ali —
#: uma URL de busca, uma company page, um perfil de outra pessoa com nome parecido. O formato
#: é o portão: `linkedin.com/in/<slug>`. O que não casa não sai, e não vira link quebrado na
#: página em nome do egresso.
PERFIL_LINKEDIN = re.compile(r"^https://(?:[a-z]{2,3}\.)?linkedin\.com/in/[\w%.\-~]+/?$")


def _linkedin(url: str | None) -> str | None:
    """O perfil público da própria pessoa, normalizado — ou `None`.

    É o MESMO dado que já sustenta a página: nome, cargo e empresa saem de um perfil que a
    pessoa publica, e o link é o endereço desse perfil. Ele não acrescenta um campo novo sobre
    ninguém; acrescenta a origem verificável do que já está publicado, e o caminho de correção
    (`origem_do_dado`) fica ao lado. Continua valendo o que torna esta página aceitável:
    ZERO renda.
    """
    if not url:
        return None
    limpo = url.strip().split("?")[0]
    if not PERFIL_LINKEDIN.match(limpo):
        return None
    return limpo.rstrip("/") + "/"

AVISO_RENDA = (
    "ESTIMATIVA, não contracheque. Nenhum salário foi coletado de ninguém. O valor é a faixa "
    "que o mercado pagava para aquele nível de experiência, a partir das medianas do Stack "
    "Overflow Developer Survey, convertidas pelo câmbio do ano e trazidas a reais do ano-base "
    "pelo IPCA. Para uma pessoa concreta pode ser MAIOR ou MENOR: a faixa p25–p75 mostra o "
    "tamanho dessa incerteza, e ela é larga de propósito."
)


def _desde_quando_na_empresa(aluno: dict) -> str | None:
    """Desde quando a pessoa está no emprego de hoje — `AAAA-MM`, ou `None`.

    Tem decisão dentro, e é por isso que sai calculado do gerador em vez de ser deduzido na
    página: há gente com DUAS posições em aberto ao mesmo tempo (um freelance em paralelo ao
    emprego), e uma delas é o emprego atual. A regra é casar pela empresa atual do cadastro; a
    data que vale é a MAIS ANTIGA entre as posições em aberto nessa empresa, porque promoção
    dentro da mesma empresa abre uma posição nova sem interromper o vínculo.
    """
    atual = norm(aluno.get("empresa_atual") or "")
    em_aberto = [x for x in aluno.get("experiencias", []) if not x.get("fim") and x.get("inicio")]
    na_empresa = [x for x in em_aberto if norm(x.get("empresa") or "") == atual]
    candidatas = na_empresa or em_aberto
    return min((x["inicio"] for x in candidatas), default=None)


def _mapa_de_rotulos() -> dict[str, str]:
    """`id` do cadastro → rótulo A–AX. Fonte única: a ordem que o modelo salarial usa."""
    return dict(zip(compute_all.ORDEM, compute_all.ROTULOS))


def perfis_nomeados() -> dict:
    """Quem é a pessoa. Nada de renda aqui — o contrato do arquivo é esse."""
    cadastro = dados.ler("alunos")
    rotulo_de = _mapa_de_rotulos()
    por_label = {r["label"]: r for r in dados.ler("analise")["rows"]}

    egressos = []
    for a in cadastro["alunos"]:
        rotulo = rotulo_de.get(a["id"])
        extra = por_label.get(rotulo, {})
        egressos.append({
            "label": rotulo,
            "nome": a["nome"],
            # As iniciais vêm do núcleo, com teste, porque a regra tem decisão dentro: "Ana da
            # Silva Souza" é "AS", não "AD". Calculá-las na página seria a mesma decisão escrita
            # duas vezes, e a página nomeada e a vitrine mostrariam monogramas diferentes para a
            # mesma pessoa no dia em que uma das duas cópias mudasse.
            "monograma": vitrine.monograma(a["nome"]),
            "curso": a.get("curso", "bsi"),
            "cargo_atual": a["cargo_atual"],
            "empresa_atual": a["empresa_atual"],
            "local_atual": a["local_atual"],
            "area_atual": a["area_atual"],
            "linkedin": _linkedin(a.get("url")),
            "na_empresa_atual_desde": _desde_quando_na_empresa(a),
            "senioridade": extra.get("senioridade"),
            "anos_de_carreira": round(extra["anos"]) if extra.get("anos") else None,
            "ainda_em_tech": bool(a["ainda_em_tech"]),
            "empregador_internacional": bool(extra.get("exterior")),
            "ja_liderou": bool(extra.get("lideranca")),
            "comecou_com_bolsa": bool(extra.get("bolsa_ini")),
            "jornada": [{c: x[c] for c in EXPERIENCIA_PUBLICA if c in x}
                        for x in a.get("experiencias", [])],
        })
    egressos.sort(key=lambda e: (e["label"] is None, len(e["label"] or ""), e["label"] or ""))

    return {
        "titulo": "Egressos de TI do Ifes Campus Serra — perfil público",
        "gerado_por": "pipeline/gen_perfis.py",
        "cursos": dados.ler("analise")["cursos"],
        "o_que_este_arquivo_nao_tem":
            "Renda. Nenhuma. A estimativa de mercado é por SENIORIDADE e está em "
            "renda_por_senioridade.json — atrelá-la a uma pessoa publicaria um número que ela nunca "
            "declarou e que a metodologia não mede no indivíduo.",
        "origem_do_dado":
            "Nível LinkedIn: cargo, empresa e cidade que a própria pessoa publica. Publicado "
            "por decisão da coordenação, para inspirar estudantes e para empresas conhecerem o "
            "grupo. O campo `linkedin`, quando existe, é o endereço desse mesmo perfil — a "
            "origem verificável do que está aqui, e não um dado novo sobre a pessoa. Egresso "
            "que queira correção ou remoção: falar com a coordenação.",
        "licenca": "CC BY 4.0",
        "atribuicao": "Estudo de egressos de TI — Ifes Campus Serra",
        "egressos": egressos,
    }


#: Nome do nível na Pesquisa Código Fonte → nome do nível no modelo do estudo. A tabela existe
#: porque as duas fontes chamam a mesma coisa de nomes diferentes, e casar por texto solto
#: silenciaria o dia em que uma delas renomear.
NIVEL_EQUIVALENTE = {
    "Estágio": None,
    "Júnior": None,
    "Pleno": None,
    "Sênior": "Sênior",
    "Especialista/Tech Lead/Principal": "Espec./Tech Lead",
}


def renda_por_senioridade() -> dict:
    """Faixa por SENIORIDADE, com as duas referências LADO A LADO — nenhuma chave de pessoa.

    Por que duas, e não uma escolhida: elas medem coisas diferentes e se movem por motivos
    diferentes.

    * A **Pesquisa Código Fonte** publica por senioridade, nativamente, e em reais. É a única
      que tem a dimensão "cargo" — cobre os cinco níveis, inclusive Estágio, Júnior e Pleno,
      que o coorte não ocupa. Em troca: publica MÉDIA, e não divulga amostra por nível.
    * O **modelo do estudo**, alimentado pelo Stack Overflow, publica MEDIANA com faixa
      p25–p75. Só existe onde o coorte tem gente, então cobre dois níveis. E nasce em DÓLAR:
      passa pelo câmbio do ano, que variou 11,9% entre 2023 e 2026 — variação que entra inteira
      nesse número e não existe no outro.

    As duas saem em R$; o que difere é a moeda de ORIGEM, a estatística e a cobertura. Escolher
    uma esconderia isso; publicar as duas com o rótulo de cada deixa o leitor ver.
    """
    consolidado = dados.ler("consolidado")
    por_label = {r["label"]: r for r in dados.ler("analise")["rows"]}
    cf = dados.ler("codigofonte_2026")
    so = dados.ler("so_benchmarks")

    # --- referência 1: o modelo do estudo, por senioridade do coorte ---
    grupos: dict[str, list[dict]] = collections.defaultdict(list)
    por_trilha: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for nome, serie in consolidado["series_por_perfil"].items():
        linha = por_label.get(nome.replace("Perfil ", ""))
        if linha and serie:
            grupos[linha["senioridade"]].append(serie[-1])
            trilha = "Dados" if linha["trilha"] == 1 else "Software"
            por_trilha[(linha["senioridade"], trilha)].append(serie[-1])

    ano_base = max(int(a) for a in consolidado["deflator_ipca_por_ano"])
    cambio = consolidado["fx_por_ano"][str(ano_base)]

    def do_modelo(nivel_estudo):
        pontos = grupos.get(nivel_estudo) or []
        if len(pontos) < MIN_POR_GRUPO:
            return None, len(pontos)
        return {
            "fonte": f"Modelo do estudo · Stack Overflow {so['edicao_referencia']}",
            "estatistica": "mediana, com faixa p25–p75",
            "moeda_de_origem": "USD",
            "p25": round(statistics.median(p["p25"] for p in pontos)),
            "mediana": round(statistics.median(p["med"] for p in pontos)),
            "p75": round(statistics.median(p["p75"] for p in pontos)),
            "n_pessoas_no_grupo": len(pontos),
            "cambio_aplicado": cambio,
            "observacao":
                "Nasce em dólar: passa pelo câmbio do ano e é trazido a reais do ano-base pelo "
                "IPCA. O câmbio variou 11,9% entre 2023 e 2026, e essa variação está aqui "
                "dentro. Só existe nos níveis em que o coorte tem pelo menos "
                f"{MIN_POR_GRUPO} pessoas.",
        }, len(pontos)

    # --- referência 2: a Pesquisa Código Fonte, por senioridade, nativa em reais ---
    media_cf = {x["nivel"]: x["media"] for x in cf["por_senioridade"]}

    cargos, sem_modelo = [], []
    for nivel_cf, nivel_estudo in NIVEL_EQUIVALENTE.items():
        referencias = [{
            "fonte": cf["fonte"],
            "estatistica": "média",
            "moeda_de_origem": "BRL",
            "valor": round(media_cf[nivel_cf], 2),
            "n_por_nivel": None,
            "n_da_edicao": cf["metodologia"]["amostra"],
            "licenca": cf.get("licenca", "não declarada pela fonte"),
            "observacao":
                "Nativa em reais — o câmbio não entra. A fonte publica MÉDIA e não divulga "
                "amostra por nível, só o total da edição; por isso não há faixa aqui.",
        }]
        # Senioridade sozinha não fecha: um Estágio de dev não é um Estágio de DBA. A fonte
        # brasileira não deixa separar — ela publica área/cargo só em percentual, sem R$. O
        # modelo do estudo separa por TRILHA, que é o mais perto de papel que existe aqui, e
        # onde o grupo aguenta o piso.
        recortes = []
        for (sen, trilha), pontos in sorted(por_trilha.items()):
            if sen == nivel_estudo and len(pontos) >= MIN_POR_GRUPO:
                recortes.append({
                    "trilha": trilha,
                    "mediana": round(statistics.median(p["med"] for p in pontos)),
                    "n_pessoas_no_grupo": len(pontos),
                })
            elif sen == nivel_estudo:
                recortes.append({"trilha": trilha, "mediana": None,
                                 "n_pessoas_no_grupo": len(pontos),
                                 "motivo": f"abaixo do piso de {MIN_POR_GRUPO} pessoas"})

        do_estudo, n_grupo = (do_modelo(nivel_estudo) if nivel_estudo else (None, 0))
        if do_estudo:
            referencias.append(do_estudo)
        elif nivel_estudo:
            sem_modelo.append({"nivel": nivel_cf, "n_pessoas_no_grupo": n_grupo,
                               "motivo": f"menos de {MIN_POR_GRUPO} pessoas no coorte"})
        else:
            sem_modelo.append({"nivel": nivel_cf, "n_pessoas_no_grupo": 0,
                               "motivo": "o coorte não ocupa este nível"})
        cargos.append({"nivel": nivel_cf, "referencias": referencias,
                       "por_trilha_no_modelo": recortes})

    return {
        "titulo": "Faixa de renda estimada por NÍVEL DE SENIORIDADE — não por pessoa e não por cargo",
        "gerado_por": "pipeline/gen_perfis.py",
        "e_estimativa": True,
        "aviso": AVISO_RENDA,
        "unidade": f"R$/mês (as duas referências; a do estudo em reais de {ano_base})",
        "senioridade_sozinha_nao_fecha":
            "Um Estágio de dev não é um Estágio de DBA: o nível só significa alguma coisa DENTRO "
            "de um papel. A média por nível da Pesquisa Código Fonte é sobre TODOS os papéis "
            "juntos — dev, dados, DBA, QA, suporte —, e ela não permite separar, porque publica "
            "área/cargo só em percentual. Duas medidas do tamanho do efeito, com o que existe: "
            "no modelo do estudo, Especialista em Software fica 11% acima de Especialista em "
            "Dados no mesmo nível; e na própria fonte, a amplitude por linguagem (que mistura "
            "papel e stack) é de 1,46× entre a maior e a menor.",
        "senioridade_nao_e_cargo":
            "Júnior, Pleno e Sênior são categorias de NÍVEL. Cargo é outra coisa: dev, tech "
            "lead, engenheiro de dados, PO, gerente. Nenhuma das duas fontes publica salário "
            "por cargo — a Pesquisa Código Fonte declara isso ao listar 'por área/cargo' entre "
            "os recortes que ela só divulga em percentual, sem R$. Os cargos do grupo estão em "
            "egressos_perfil.json e em analise.json (funcoes), SEM valor associado.",
        "ressalva_do_ultimo_nivel":
            "O nível mais alto da fonte, 'Especialista/Tech Lead/Principal', mistura os dois "
            "eixos: Especialista e Principal são senioridade, Tech Lead é cargo. A mistura é da "
            "fonte, não nossa, e fica registrada em vez de corrigida por conta própria.",
        "por_que_duas_referencias":
            "Elas medem coisas diferentes e se movem por motivos diferentes. A Código Fonte "
            "nasce em reais e cobre os cinco níveis, mas publica média sem amostra por nível. "
            "O modelo do estudo publica mediana com faixa, mas nasce em dólar — o câmbio entra "
            "no número — e só existe onde o coorte tem gente. Escolher uma esconderia isso.",
        "minimo_de_pessoas_por_grupo": MIN_POR_GRUPO,
        "por_que_o_minimo":
            "Com menos que isso, a 'faixa do nível' seria a estimativa de um indivíduo com "
            "outro rótulo — o mesmo defeito por outro caminho.",
        "licenca": "CC BY 4.0",
        "atribuicao": "Estudo de egressos de TI — Ifes Campus Serra",
        "cargos": cargos,
        "niveis_sem_referencia_do_modelo": sem_modelo,
    }


def executar(*, hoje: Competencia) -> tuple[dict, dict]:   # noqa: ARG001
    """`hoje` não é usado: os perfis saem de `analise`, que já foi datada. Ver o contrato."""
    perfil, renda = perfis_nomeados(), renda_por_senioridade()
    dados.gravar("egressos_perfil", perfil)
    dados.gravar("renda_por_senioridade", renda)
    return perfil, renda


def main() -> int:
    perfil, renda = executar(hoje=deflator.data_referencia(dados.ler("ibge_series")))
    print(f"OK — {dados.caminho('egressos_perfil')}")
    print(f"  {len(perfil['egressos'])} egressos, sem nenhum campo de renda")
    com_link = sum(1 for e in perfil["egressos"] if e["linkedin"])
    print(f"  {com_link} com link de perfil do LinkedIn "
          f"({len(perfil['egressos']) - com_link} sem URL no cadastro)")
    print(f"OK — {dados.caminho('renda_por_senioridade')}")
    for c in renda["cargos"]:
        print(f"  {c['nivel']}")
        for ref in c["referencias"]:
            if "valor" in ref:
                print(f"      {ref['moeda_de_origem']}  média    R$ {ref['valor']:>9,.2f}   "
                      f"({ref['fonte']})")
            else:
                print(f"      {ref['moeda_de_origem']}  mediana  R$ {ref['p25']:>7,} – "
                      f"{ref['mediana']:>7,} – {ref['p75']:>7,}   ({ref['n_pessoas_no_grupo']} pessoas)")
    for r in renda["niveis_sem_referencia_do_modelo"]:
        print(f"  sem referência do modelo: {r['nivel']} — {r['motivo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o recorte por curso — BSI e ECA lado a lado, cada um com os seus.

O que sai, por curso: as contagens da cobertura (fila do SIGA, processados, confirmados e por
qual caminho), a distribuição CRUA de cargos e empresas, e a VITRINE dos confirmados da
coleta — nome, cargo, empresa, cidade e o endereço do perfil, o mesmo nível LinkedIn do
egressos_perfil. A vitrine saiu daqui e voltou no mesmo dia, e as duas decisões são do Paulo
em 2026-08-16: saiu às contagens ("não precisam saber"), voltou quando a página da ECA
precisou mostrar quem são — a ECA não tem ninguém no estudo original, e sem esta vitrine o
recorte dela seria só número. Duas fontes alimentam o recorte:

  egressos_perfil    o estudo original — 50 pessoas, todas do BSI, com cargo e empresa
                     curados. Entra na CONTA; nenhum registro individual sai daqui.
  perfis_linkedin    a coleta dos formandos do SIGA — só o topo do perfil, cru. Daqui contam
                     só os CONFIRMADOS (formação IFES lida, ou decisão humana registrada
                     em perfis_conferidos.json).

ZERO campo de renda — a faixa mora em `renda_por_senioridade`, sem chave de pessoa, e a
página que quiser mostrá-la lê de lá. Empresa aqui é dado público de EMPRESA (quem contrata),
nunca ligado a uma pessoa: a ligação nome↔empresa mora só na busca.

CARGO E EMPRESA SAEM CRUS DE PROPÓSITO. O vocabulário de área do estudo não cobre a ECA, e
não vai cobrir por dedução minha: os termos têm de nascer do que essas pessoas escrevem sobre
si (`busca_perfis.py` explica a decisão). Contar strings idênticas é o máximo de agregação
que não inventa vocabulário.

Uso:  python pipeline/gen_cursos.py
"""
from __future__ import annotations

import collections
import sys

from egressos_core import dados, jornada, vitrine

CURSOS = {
    "bsi": "Sistemas de Informação",
    "eca": "Engenharia de Controle e Automação",
}

#: Quantas linhas as distribuições de cargo e empresa mostram. Corte de exibição sobre a
#: contagem agregada — abaixo dele só muda a ordem, nunca o dado de alguém.
TOP = 12


def _limpo(texto):
    """Campo cru utilizável: espaço normalizado; vazio e '-' viram None."""
    if not texto:
        return None
    plano = " ".join(str(texto).split())
    return plano if plano and plano != "-" else None


def _linhas_do_estudo(perfil):
    """Cargo e empresa de quem está no estudo original — SÓ os campos contáveis.
    O nome entra na conta e morre aqui dentro: serve para casar o curso, nunca para sair."""
    return [{
        "nome": e["nome"],
        "cargo": _limpo(e.get("cargo_atual")),
        "empresa": _limpo(e.get("empresa_atual")),
        "fonte": "estudo",
    } for e in perfil["egressos"]]


def _linhas_da_coleta(coleta):
    """Cargo e empresa dos confirmados da coleta. Quem entrou só pela mão pode não ter
    cargo — a conferência humana confirma a PESSOA; o topo do perfil só existe se a busca
    o leu."""
    return [{
        "nome": p["nome"],
        "cargo": _limpo(p.get("cargo_atual")),
        "empresa": _limpo(p.get("empresa_atual")),
        "fonte": "coleta",
    } for p in coleta["perfis"] if p.get("confirmado")]


def _linkedin(slug):
    """`in/fulano` → endereço completo do perfil. Aceita com/sem barra, com/sem domínio."""
    limpo = (slug or "").strip().strip("/")
    limpo = limpo.split("linkedin.com/")[-1].split("?")[0].strip("/")
    return f"https://www.linkedin.com/{limpo}/" if limpo else None


def _vitrine_da_coleta(coleta, curso):
    """A vitrine nomeada dos confirmados da coleta, de UM curso.

    Os campos são os do contrato do egressos_perfil — nome, cargo, empresa, cidade, endereço
    do perfil — mais o monograma, que vem de `egressos_core.vitrine` pela mesma razão de
    sempre: a regra tem decisão dentro e mora num lugar só. `headline` NÃO sai (texto livre).

    A jornada sai da segunda passada (`busca_perfis.py --trajetoria`) e sai PROJETADA na
    lista fechada de campos — cargo, empresa, tipo, início, fim, duração, local. Não é o
    bruto: o prompt da passada nem captura a `descricao`, e a projeção aqui garante que um
    campo novo no cru não vaza para o publicável por acidente.

    A projeção passa por `egressos_core.jornada.normaliza`, e é aí que a forma das duas
    fontes converge: a passada grava o texto CRU da página (`"Apr 2021"`, `"Present"`,
    `"5 yrs 5 mos"`) e o cadastro do estudo já guarda normalizado (`"2023-10"`, `fim: null`,
    `"2 anos 10 meses"`). Sem essa passagem, o cartão publicava inglês numa página em
    português — e publicava também o resto de seletor que a raspagem deixa (`"-> -"` em 20
    das 150 posições da primeira coleta). O que o normalizador NÃO faz é vocabulário: `tipo`
    passa como veio, `Integral` e `Full-time` seguem distintos."""
    JORNADA_PUBLICA = ("cargo", "empresa", "tipo", "inicio", "fim", "duracao", "local")
    return sorted([{
        "nome": p["nome"],
        "monograma": vitrine.monograma(p["nome"]),
        "cargo": _limpo(p.get("cargo_atual")),
        "empresa": _limpo(p.get("empresa_atual")),
        "local": _limpo(p.get("local")),
        "linkedin": _linkedin(p.get("slug")),
        "jornada": [jornada.normaliza({c: x.get(c) for c in JORNADA_PUBLICA})
                    for x in (p.get("experiencias") or [])],
    } for p in coleta["perfis"]
        if p.get("confirmado") and p.get("curso") == curso and p.get("slug")],
        key=lambda v: v["nome"])


def _distribuicao(linhas, campo):
    """Contagem do texto cru, string idêntica a string idêntica. Sem classificar."""
    freq = collections.Counter(v[campo] for v in linhas if v[campo])
    return [{"texto": texto, "n": n} for texto, n in freq.most_common(TOP)]


def _cobertura(linhas, campo):
    """Quantas das `linhas` têm o campo — o DENOMINADOR da distribuição ao lado.

    Existe por causa de uma leitura errada que a página convidava. A ECA anuncia "28 egressos
    identificados" e desenhava as barras de cargo logo abaixo; as barras somam 11, porque 17
    dos 28 foram confirmados por conferência humana e a página do perfil nunca foi lida — sem
    cargo, não entram em distribuição nenhuma. Nada dizia isso, então o gráfico parecia estar
    perdendo gente.

    `_distribuicao` sozinha não consegue contar isto: ela já filtrou os vazios, e `sum(n)` dá
    11 sem saber que o universo era 28. O par (contagem, base) tem de sair daqui.
    """
    return {"com": sum(1 for v in linhas if v[campo]), "de": len(linhas)}


def recorte():
    perfil = dados.ler("egressos_perfil")
    coleta = dados.ler("perfis_linkedin")
    fila = dados.ler("formandos_a_buscar")

    fila_por_curso = collections.Counter(p["curso"] for p in fila["fila"])
    processados = collections.Counter(p["curso"] for p in coleta["perfis"])
    nao_ident = collections.Counter(
        p["curso"] for p in coleta["perfis"]
        if not p.get("confirmado") and not p.get("achado") and not p.get("falhou_a_rodada"))
    a_mao = collections.Counter(
        p["curso"] for p in coleta["perfis"]
        if p.get("confirmado") and p.get("confirmado_por") == "conferência humana")

    cursos = {}
    for curso, nome_curso in CURSOS.items():
        linhas = (
            [v for v in _linhas_do_estudo(perfil) if _curso_do_estudo(perfil, v["nome"]) == curso]
            + [v for v in _linhas_da_coleta(coleta) if _curso_da_coleta(coleta, v["nome"]) == curso])
        confirmados_coleta = sum(1 for v in linhas if v["fonte"] == "coleta")
        vitrine_do_curso = _vitrine_da_coleta(coleta, curso)
        cursos[curso] = {
            "curso": curso,
            "nome_curso": nome_curso,
            "contagens": {
                "formandos_na_fila": fila_por_curso.get(curso, 0),
                "processados_pela_coleta": processados.get(curso, 0),
                "confirmados_pela_coleta": confirmados_coleta,
                "confirmados_a_mao": a_mao.get(curso, 0),
                "aguardando_conferencia": nao_ident.get(curso, 0),
                "no_estudo_original": sum(1 for v in linhas if v["fonte"] == "estudo"),
                "identificados": len(linhas),
            },
            "cargos": _distribuicao(linhas, "cargo"),
            "empresas": _distribuicao(linhas, "empresa"),
            # A cobertura de cargo/empresa é sobre `linhas` (o universo das CONTAGENS: estudo
            # + coleta). A de jornada é sobre a VITRINE, que é outro universo — só a coleta,
            # e só quem tem slug. Medir as três no mesmo denominador diria que faltam
            # jornadas dos 50 do estudo, que nem passam pela vitrine.
            "cobertura": {
                "cargo": _cobertura(linhas, "cargo"),
                "empresa": _cobertura(linhas, "empresa"),
                "jornada": _cobertura(vitrine_do_curso, "jornada"),
            },
            "vitrine": vitrine_do_curso,
        }
    return {
        "titulo": "Recorte por curso — BSI e ECA, contagens e distribuições cruas",
        "gerado_por": "pipeline/gen_cursos.py",
        "atencao": ("Vitrine nomeada no contrato do egressos_perfil (nome, cargo, empresa, "
                    "cidade, endereço do perfil — nível LinkedIn, decisão da coordenação). "
                    "ZERO campo de renda. Cargo e empresa CRUS, sem classificação: o "
                    "vocabulário nasce do dado."),
        "o_que_este_arquivo_nao_tem": (
            "Renda: a estimativa mora em renda_por_senioridade, sem chave de pessoa, porque "
            "o valor nunca foi da pessoa — é a faixa de mercado para o nível de experiência. "
            "Headline e experiências cruas: texto livre não sai; a jornada entra curada, "
            "como a dos 50 do estudo."),
        "cursos": cursos,
    }


def _curso_do_estudo(perfil, nome):
    return next((e["curso"] for e in perfil["egressos"] if e["nome"] == nome), None)


def _curso_da_coleta(coleta, nome):
    return next((p["curso"] for p in coleta["perfis"] if p["nome"] == nome), None)


def executar(**_ignorado):
    """Aceita `hoje=` sem usar: o laço do build_report passa a competência a toda etapa."""
    saida = recorte()
    dados.gravar("recorte_cursos", saida)
    return saida


def main() -> int:
    saida = executar()
    print(f"OK — {dados.caminho('recorte_cursos')}")
    for curso, r in saida["cursos"].items():
        c = r["contagens"]
        print(f"  {curso.upper()}: identificados {c['identificados']} "
              f"(estudo {c['no_estudo_original']} + coleta {c['confirmados_pela_coleta']}), "
              f"fila {c['formandos_na_fila']}, processados {c['processados_pela_coleta']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

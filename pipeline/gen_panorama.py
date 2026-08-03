"""Monta data/panorama.json — o que a página de panorama da coorte publica.

Substitui o antigo `gen_panorama.py`, que abria o `dashboard_alunos.html` e trocava, por
expressão regular, o conteúdo de `const DB = {alunos: [ ... ]}` e de `const SALTO=[...]` por
strings JavaScript montadas com f-string. Duas consequências disso.

A primeira: a anonimização — a parte mais delicada do repositório — era montagem de string. O
mesmo trecho decidia o que ocultar e como escrever a chave do objeto, e não havia como testar a
decisão separada da serialização. Agora ela vive em `egressos_core.panorama`, testada, e este
arquivo só projeta.

A segunda: os 64 KB de JavaScript resultantes eram a página. Quem visitava recebia um documento
com seis containers vazios e um script que os preenchia. Aqui os números viram dado, e a página
em Astro os transforma em HTML no build.

O cadastro real (`alunos.json`) NUNCA sai deste processo: entra aqui, sai anonimizado.
"""
from __future__ import annotations

import json

from egressos_core import dados, panorama
from egressos_core.deflator import data_referencia
from egressos_core.paths import ROOT

DESTINO = ROOT / "data/panorama.json"

#: Ordem do cadastro → rótulo publicado. A mesma lista de `compute_all.py` e `analise.py`;
#: o vínculo entre as três é por POSIÇÃO, e é o que mantém "Egresso C" sendo a mesma pessoa
#: em todas as páginas. Ver a nota de sincronia no `build_report.py`.
ORDEM = [
    "barbosa", "gary", "possatti", "helen", "renan", "andre", "tarcisio", "joel", "icaro",
    "gustavo", "marialuiza", "gabriel_barboza", "magnago", "martins_miranda", "geann",
    "rodrigo_maia", "andre_aguiar", "guilherme_gatti", "ivana", "joao_paulo",
    "lucas_coutinho", "marcos_dias", "phillipe", "anne_caroline", "brendon", "cassiano",
    "jennifer", "ana_rubia", "diego", "edvaldo", "magno", "pedro", "antonio", "cristian",
    "danilo", "marlon", "breno", "caio", "lucas_gomes", "derick", "marcos_carneiro",
    "mateus_garcia", "ana_carolina", "david_pantaleao", "renato", "kleber", "rafael",
    "andreangelo", "icaro_gandine", "paulo_ricardo",
]

#: Um perfil da coorte não tem série salarial comparável e fica fora do gráfico de salto. A
#: ausência é declarada no dado, e não numa frase escrita à mão embaixo do gráfico: quem
#: renderiza precisa poder dizer quantos ficaram fora sem que alguém atualize a prosa.
FORA_DO_SALTO = "gestão de produto — sem série comparável na fonte de mercado"


def _rotulo(indice: int) -> str:
    """A, B, … Z, AA, AB, … — o rótulo publicado no lugar do nome.

    Era uma lista de cinquenta strings escritas à mão, que precisava crescer junto com a
    coorte. Egresso número 51 ficaria sem rótulo, e `zip` truncaria em silêncio.
    """
    letras = ""
    n = indice
    while True:
        letras = chr(65 + n % 26) + letras
        n = n // 26 - 1
        if n < 0:
            return letras


def _egresso(bruto: dict, rotulo: str, portes: dict) -> panorama.Egresso:
    marcas = portes.keys()
    emp, origem = panorama.anonimiza_empregador(bruto.get("empresa_atual"), portes=portes)
    exps = tuple(
        panorama.Experiencia(
            cargo=panorama.limpa_cargo(e["cargo"], marcas=marcas),
            empregador=panorama.anonimiza_empregador(e.get("empresa"), portes=portes)[0],
            tipo=e.get("tipo") or "Full-time",
            inicio=e["inicio"],
            fim=e.get("fim"),
            area=e.get("area") or "dev",
        )
        for e in sorted(bruto["experiencias"], key=lambda e: e["inicio"])
    )
    return panorama.Egresso(
        rotulo=rotulo,
        cargo_atual=panorama.limpa_cargo(bruto["cargo_atual"], marcas=marcas),
        empregador_atual=emp,
        origem=origem,
        modalidade=panorama.modalidade_de(bruto.get("local_atual")),
        area_atual=bruto["area_atual"],
        inicio_carreira=bruto["inicio_carreira_dev"],
        em_tech=bool(bruto["ainda_em_tech"]),
        experiencias=exps,
    )


def _publica(e: panorama.Experiencia, hoje: str) -> dict[str, object]:
    """Uma experiência como a página precisa dela: já com fim resolvido e duração calculada.

    O `fim` vazio significa "em curso", e quem desenha precisa de um número para a barra. A
    resolução acontece aqui, uma vez, em vez de em cada lugar que consome — era `const fim = e
    => e.fim || HOJE` chamado de quatro pontos diferentes do JavaScript.
    """
    fim = e.fim or hoje
    return {
        "cargo": e.cargo,
        "empregador": e.empregador,
        "tipo": e.tipo,
        "de": e.inicio,
        "ate": fim,
        "em_curso": e.fim is None,
        "de_extenso": panorama.por_extenso(e.inicio),
        "ate_extenso": None if e.fim is None else panorama.por_extenso(e.fim),
        "duracao": panorama.duracao(e.inicio, fim),
        "area": e.area,
        "area_nome": panorama.AREAS[e.area],
        "familia": e.familia,
    }


def monta() -> dict[str, object]:
    cadastro = json.loads((ROOT / "alunos.json").read_text(encoding="utf-8"))["alunos"]
    portes = dados.ler("empresas_porte")
    consolidado = dados.ler("consolidado")
    # A data de "hoje" vem do último mês publicado do IPCA, não do relógio: era `const HOJE =
    # "2026-07"` cravado no HTML, que envelhecia em silêncio e fazia toda barra em curso parar
    # no mês em que alguém editou o arquivo pela última vez.
    ref = data_referencia(dados.ler("ibge_series"))
    hoje = f"{ref.ano}-{ref.mes:02d}"

    por_id = {a["id"]: a for a in cadastro}
    faltando = [i for i in ORDEM if i not in por_id]
    if faltando:
        # Silenciar aqui encolheria a coorte publicada sem aviso, e a página continuaria
        # somando certo — só com gente de menos.
        raise SystemExit(f"cadastro sem {len(faltando)} id(s) da ordem: {faltando}")

    coorte = [_egresso(por_id[pid], _rotulo(i), portes) for i, pid in enumerate(ORDEM)]

    linhas = panorama.salto(consolidado["perfis"])
    ind = panorama.indicadores(coorte, hoje=hoje)

    return {
        "hoje": hoje,
        "hoje_extenso": panorama.por_extenso(hoje),
        "indicadores": ind,
        # A origem comum era a frase "IFES · LEDS / Prodest · Morpheus Jr." escrita no HTML.
        # Agora é contagem: quantos passaram por cada instituição de fomento.
        "origem_comum": _origem_comum(coorte),
        "eixo": panorama.eixo_de_anos(coorte, hoje=hoje),
        "familias": panorama.familias_usadas(coorte),
        "areas": panorama.areas_usadas(coorte),
        "coorte": [
            {
                "rotulo": p.rotulo,
                "cargo_atual": p.cargo_atual,
                "empregador_atual": p.empregador_atual,
                "origem": p.origem,
                "modalidade": p.modalidade,
                "area_atual": p.area_atual,
                "area_atual_nome": panorama.AREAS[p.area_atual],
                "inicio_carreira": p.inicio_carreira,
                "anos_de_carreira": round(
                    panorama.em_anos(hoje) - panorama.em_anos(p.inicio_carreira), 1),
                "em_tech": p.em_tech,
                "n_experiencias": len(p.experiencias),
                "experiencias": [_publica(e, hoje) for e in p.experiencias],
            }
            for p in coorte
        ],
        "salto": linhas,
        "salto_fora": {
            "n": ind["n"] - len(linhas),
            "motivo": FORA_DO_SALTO,
        },
        "aviso": (
            "ESTIMATIVA de mercado por trilha e experiência (Stack Overflow Developer Survey), "
            "não folha de pagamento. Pode estar acima ou abaixo do real."
        ),
        "privacidade": (
            "Coorte anonimizada: cada pessoa é um rótulo (A, B, C…). Empregador privado aparece "
            "como categoria — nacional, internacional ou setor público. Instituições públicas de "
            "fomento (IFES/LEDS, Prodest, FAPES, CAPES, CNPq) aparecem pelo nome porque têm "
            "centenas de bolsistas e não identificam ninguém. Cidade nunca aparece: só a "
            "modalidade de trabalho."
        ),
    }


def _origem_comum(coorte: list[panorama.Egresso]) -> list[dict[str, object]]:
    """Por quantas pessoas cada instituição de fomento passou, da maior para a menor."""
    contagem: dict[str, int] = {}
    for p in coorte:
        vistos = {e.empregador for e in p.experiencias
                  if e.empregador not in {"Empresa nacional", "Empresa internacional",
                                          "Setor público", "Autônomo"}}
        for v in vistos:
            contagem[v] = contagem.get(v, 0) + 1
    return [{"instituicao": k, "n": v}
            for k, v in sorted(contagem.items(), key=lambda kv: -kv[1])]


if __name__ == "__main__":
    saida = monta()
    DESTINO.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    ind = saida["indicadores"]
    print(f"  coorte: {ind['n']} egressos (A–{saida['coorte'][-1]['rotulo']}) · "
          f"{ind['em_tech']} em tech · média {ind['anos_media']} anos "
          f"(mediana {ind['anos_mediana']})")
    print(f"  linha do tempo: {saida['eixo']['de']}–{saida['eixo']['ate']} · "
          f"{sum(p['n_experiencias'] for p in saida['coorte'])} experiências · "
          f"{len(saida['familias'])} famílias, {len(saida['areas'])} áreas")
    print(f"  salto: {len(saida['salto'])} perfis, {saida['salto_fora']['n']} fora")
    print("  origem comum: " + ", ".join(
        f"{o['instituicao'].split(' ·')[0]} {o['n']}" for o in saida["origem_comum"][:4]))
    print(f"OK: {DESTINO.relative_to(ROOT)}")

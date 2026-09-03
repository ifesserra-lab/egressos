"""Orquestrador do relatório de egressos — gera TUDO a partir dos dados.

Cada etapa é uma **função importada**, não um processo filho. O que atravessa uma falha agora é
a exceção, com tipo, mensagem e pilha; antes era um `returncode` inteiro, e quem lia o log via
"FALHOU em: Análise (exit 1)" sem saber o quê.

## A data de referência é resolvida uma vez

`hoje` é a competência do último mês publicado do IPCA (`mes_base` de `ibge_series`) — vem do
dado, nunca do relógio da máquina. Ela é resolvida **uma vez** aqui e passada igual a todas as
etapas. Antes, cada etapa que precisava dela relia `ibge_series` e chamava `data_referencia` de
novo: a mesma data resolvida em vários lugares é como duas datas passam a existir.

`ibge_series` roda **fora** do laço porque é ela que **produz** essa data. Exigir `hoje` dela
obrigaria o orquestrador a ter o valor antes de existir arquivo de onde tirá-lo — num clone
novo, não há. É a única exceção à fronteira uniforme, e está declarada no contrato
(`specs/003-dominio-no-nucleo/contracts/etapas-e-orquestracao.md`).

## Ordem

A ordem reflete dependência real de dado: ingest → domínio → datasets de página → publicação →
portão de números. Ela não é decorativa e não muda sem motivo escrito.

IMPORTANTE — sincronia de order/labels: `compute_all`, `egressos_core.analise` e `gen_panorama`
têm as listas de ordem e rótulos dos egressos. Ao integrar egresso novo, estender as três na
mesma ordem (o join salário↔perfil na análise é por RÓTULO, robusto a perfis puladas).

Uso:   python pipeline/build_report.py            (gera + valida)
       python pipeline/build_report.py --publish  (após validar, publica)
"""
from __future__ import annotations

import sys

import analise
import compute_all
import fapes_fomento
import gen_api
import gen_dados_abertos
import gen_impacto
import gen_panorama
import gen_perfis
import gen_trajetoria
import genero
import ibge_series
import mapa_base
import so_benchmarks
import src_extensao
from egressos_core import dados, deflator
from egressos_core.deflator import Competencia
from egressos_core.paths import ROOT


def numeros_contra_fonte(*, hoje: Competencia) -> None:   # noqa: ARG001
    """Cláusula P9 — os números publicados batem com o dataset que os originou.

    A única etapa que **não** é uma função de domínio: é um portão, e a verificação mora na
    suíte (`tests/test_projecao_impacto.py`), onde ela também roda no CI. Chamar `pytest.main`
    aqui é import, não processo filho — o que a fase eliminou foi o `subprocess`, não o reuso
    do que já está escrito.

    O antecessor era `old/pipeline/qa_report.py`, que chamava `node` para reler o HTML que o
    próprio pipeline tinha acabado de escrever. Ele saiu quando as páginas deixaram de ter
    JavaScript para engenharia-reversar.
    """
    import pytest

    codigo = pytest.main(["-q", str(ROOT / "tests/test_projecao_impacto.py")])
    if codigo != 0:
        raise RuntimeError(f"P9 reprovou: números publicados divergem da fonte (pytest {codigo})")


#: As 14 etapas do laço, na ordem. `ibge_series` não está aqui: ela roda antes, porque produz
#: a data de referência que as outras recebem. Ver o docstring do módulo.
ETAPAS = [
    ("Benchmarks Stack Overflow", so_benchmarks.executar),
    ("Contorno do mapa-múndi",    mapa_base.executar),
    ("Gênero (offline)",          genero.executar),
    ("Série salarial",            compute_all.executar),
    ("Extensão SRC/IFES",         src_extensao.executar),
    ("Fomento FAPES",             fapes_fomento.executar),
    ("Análise",                   analise.executar),
    # Depois da análise: a vitrine nomeada e a faixa por cargo saem do cruzamento dela com o
    # consolidado. Dois arquivos, contratos diferentes — ver o docstring de gen_perfis.py.
    ("Perfis e renda por cargo",  gen_perfis.executar),
    ("Impacto (dataset)",         gen_impacto.executar),
    ("Panorama (dataset)",        gen_panorama.executar),
    ("Trajetória (dataset)",      gen_trajetoria.executar),
    ("Dados abertos",             gen_dados_abertos.executar),
    ("API estática",              gen_api.executar),
    ("Números × fonte (P9)",      numeros_contra_fonte),
]


def run(*, hoje: Competencia | None = None) -> None:
    """Roda as etapas na ordem. Exceção de etapa **sobe**, com tipo e pilha originais.

    `hoje` é resolvido do dado quando não vem por parâmetro. Passá-lo existe para o teste — e
    para o dia em que alguém quiser reprocessar contra outra competência sem editar código.
    """
    print("\n=== Séries IBGE/IPEADATA ===", flush=True)
    ibge_series.executar()          # produz o `mes_base` que as outras 14 consomem

    if hoje is None:
        hoje = deflator.data_referencia(dados.ler("ibge_series"))
    print(f"    data de referência do build: {hoje.rotulo_pt()}", flush=True)

    for nome, etapa in ETAPAS:
        print(f"\n=== {nome} ===", flush=True)
        try:
            etapa(hoje=hoje)
        except Exception as erro:
            # `add_note` e não `raise ... from ...`: o segundo troca o tipo que sobe, e quem
            # trata a falha lá em cima perde a informação que interessa. Aqui o tipo, a
            # mensagem e a pilha originais atravessam intactos, com o nome da etapa junto —
            # que é justamente o que o `returncode` do `subprocess` não carregava.
            erro.add_note(f"etapa que falhou: {nome}")
            raise

    print("\nBUILD OK — relatórios gerados e validados.")


def publish() -> None:
    """Publica pelo portão: build do site, verificação, e só então a cópia.

    Antes esta função tinha DUAS listas de arquivos escritas à mão — uma para o repositório
    público, outra para o portal da diretoria — e elas já divergiam entre si. Página nova
    exigia lembrar das duas; página migrada, das duas de novo.

    Agora quem sabe quais páginas existem é `paginas.json`, e quem sabe de ONDE cada uma sai é
    o portão (`site/` para as migradas, a raiz e o repositório público para as que ainda não).
    A cópia é consequência da aprovação, não um passo à parte que pode ser esquecido.
    """
    from egressos_site import build, publica

    print("\n== Site (Astro) ==")
    print(f"  {build.constroi()} arquivos em site/")
    copiados = publica.publica()
    print(f"  {len(copiados)} cópias:")
    for c in copiados:
        print(f"    {c}")


def main() -> int:
    run()
    if "--publish" in sys.argv:
        from egressos_site import publica
        try:
            publish()
        except publica.NaoAprovado as erro:
            # Portão reprovado não é defeito de programa: é a resposta dele. Mensagem, não pilha.
            print(erro)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

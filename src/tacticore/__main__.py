"""A unica camada do projeto que faz I/O.

    uv run python -m tacticore                  # duelo com a seed padrao
    uv run python -m tacticore 4242             # duelo com a seed que voce der
    uv run python -m tacticore --jogar          # voce joga o lado dos herois

Tudo abaixo daqui e puro: `core`, `render` e `content` nao imprimem, nao abrem
arquivo e nao leem argumento. Este arquivo existe para que essa fronteira tenha
um lado de fora -- e ele e a **unica excecao** registrada no guardiao de
imports, nomeada e com motivo. Desde a etapa 3 o guardiao confere isso de
verdade: ele varre `print` e `input` por AST, e nao so nome de modulo
importado.

**Continua havendo um unico laco de combate no projeto.** O paragrafo que
ocupava este lugar recusava escrever um segundo laco so para o CLI, porque
seriam dois motores de decisao para manter em sincronia, e a recusa continua
valendo palavra por palavra. O modo interativo nao a desrespeita: ele conduz
`core.testing.conduzir`, que e o mesmo laco que `play_out` conduz. A diferenca
entre os dois e uma linha -- `play_out` tapa o ponto de suspensao com uma
`Politica`, e este arquivo o tapa com uma pessoa.

O que mora aqui e so a cola: imprimir o que `render` montou e ler o que o
jogador digitou. Formatar menu, desenhar tabuleiro e traduzir "o jogador
digitou 3" numa `Action` sao trabalho de `tacticore.render`, sob o gate de
cobertura -- este arquivo esta fora dele de proposito, e por isso nao pode
guardar decisao nenhuma.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from tacticore.content.srd import CATALOGO, duelo
from tacticore.core.actions import Action
from tacticore.core.engine import start_combat
from tacticore.core.events import Event
from tacticore.core.results import Applied
from tacticore.core.rng import SplitMix64
from tacticore.core.testing import Passo, conduzir, play_out, primeira_legal
from tacticore.render import board, escolha, menu, narrate

SEED_PADRAO = 20250914
"""A mesma seed do golden `duelo`, para o comando e o arquivo congelado
contarem a mesma historia."""

FLAG_JOGAR = "--jogar"
USO = f"uso: python -m tacticore [seed] [{FLAG_JOGAR}]"

TIME_DO_JOGADOR = "herois"
PROMPT = "> "
NAO_ENTENDI = "nao entendi. digite o numero de uma das opcoes."
ABANDONO = "combate abandonado."
CODIGO_DE_ABANDONO = 130
"""128 + SIGINT, a convencao de shell para "morreu por interrupcao"."""


def main(argv: Sequence[str]) -> int:
    """Roda um duelo. Devolve o codigo de saida."""
    restantes = [a for a in argv if a != FLAG_JOGAR]
    jogar = len(restantes) < len(argv)

    if len(restantes) > 1:
        print(USO, file=sys.stderr)
        return 2

    seed = SEED_PADRAO
    if restantes:
        try:
            seed = int(restantes[0])
        except ValueError:
            print(f"seed invalida: {restantes[0]!r}", file=sys.stderr)
            print(USO, file=sys.stderr)
            return 2

    if jogar:
        return combate_interativo(seed)

    for linha in combate_narrado(seed):
        print(linha)
    return 0


def combate_narrado(seed: int) -> tuple[str, ...]:
    """O duelo inteiro em texto. Puro -- e o que torna `main` testavel."""
    abertura = _abrir(seed)
    _, resto = play_out(abertura.state)
    return narrate((*abertura.events, *resto))


def combate_interativo(seed: int, *, lado: str = TIME_DO_JOGADOR) -> int:
    """O mesmo duelo, com os turnos de `lado` nas maos de quem esta lendo.

    Nos turnos do outro time, `primeira_legal` joga -- o mesmo piloto
    automatico dos goldens, e nao uma segunda heuristica escrita para ca.
    """
    abertura = _abrir(seed)
    _narrar(abertura.events)

    conducao = conduzir(abertura.state, origem="o jogador")
    passo = next(conducao)
    try:
        while True:
            _narrar(passo.events)
            if not passo.actions:
                return 0
            passo = conducao.send(_escolher(passo, lado))
    except (EOFError, KeyboardInterrupt):
        # Ctrl+D e Ctrl+C no meio de uma pergunta sao saida normal de um
        # programa de terminal, e nao defeito: quem sai assim nao quer ver
        # traceback.
        print(ABANDONO, file=sys.stderr)
        return CODIGO_DE_ABANDONO


def _abrir(seed: int) -> Applied:
    return start_combat(
        statblocks=CATALOGO,
        participants=duelo(),
        rng=SplitMix64(seed=seed),
    )


def _narrar(eventos: Sequence[Event]) -> None:
    for linha in narrate(eventos):
        print(linha)


def _escolher(passo: Passo, lado: str) -> Action:
    """A escolha de um turno: do jogador, se for o time dele; do piloto, se nao.

    O laco de repergunta e o unico laco deste arquivo, e ele nao avanca o
    combate: `escolha` devolvendo `None` significa "pergunte de novo", nunca
    "encerre o turno". Confundir os dois comeria a jogada de quem errou uma
    tecla, e passaria num teste de fumaca.
    """
    ator = passo.state.combatants[passo.state.turn_order.current]
    if ator.team != lado:
        return primeira_legal(passo.state, passo.actions)

    for linha in board(passo.state):
        print(linha)
    for linha in menu(passo.actions):
        print(linha)

    while True:
        escolhida = escolha(input(PROMPT), passo.actions)
        if escolhida is not None:
            return escolhida
        print(NAO_ENTENDI, file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover - so roda como `python -m`
    raise SystemExit(main(sys.argv[1:]))

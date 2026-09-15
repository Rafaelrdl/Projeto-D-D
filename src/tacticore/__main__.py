"""A unica camada do projeto que faz I/O.

    uv run python -m tacticore            # duelo com a seed padrao
    uv run python -m tacticore 4242       # duelo com a seed que voce der

Tudo abaixo daqui e puro: `core`, `render` e `content` nao imprimem, nao abrem
arquivo e nao leem argumento. Este arquivo existe para que essa fronteira tenha
um lado de fora -- e ele e a **unica excecao** registrada no guardiao de
imports, nomeada e com motivo.

O piloto automatico vem de `core.testing.play_out`. O nome do modulo diz
"testing" e o uso aqui e de producao, e isso e proposital: escrever um segundo
laco de combate so para o CLI criaria dois motores de decisao para manter em
sincronia, que e exatamente a duplicacao recusada em outros pontos do projeto.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from tacticore.content.srd import CATALOGO, duelo
from tacticore.core.engine import start_combat
from tacticore.core.rng import SplitMix64
from tacticore.core.testing import play_out
from tacticore.render import narrate

SEED_PADRAO = 20250914
"""A mesma seed do golden `duelo`, para o comando e o arquivo congelado
contarem a mesma historia."""

USO = "uso: python -m tacticore [seed]"


def main(argv: Sequence[str]) -> int:
    """Roda um duelo e imprime o log narrado. Devolve o codigo de saida."""
    if len(argv) > 1:
        print(USO, file=sys.stderr)
        return 2

    seed = SEED_PADRAO
    if argv:
        try:
            seed = int(argv[0])
        except ValueError:
            print(f"seed invalida: {argv[0]!r}", file=sys.stderr)
            print(USO, file=sys.stderr)
            return 2

    for linha in combate_narrado(seed):
        print(linha)
    return 0


def combate_narrado(seed: int) -> tuple[str, ...]:
    """O duelo inteiro em texto. Puro -- e o que torna `main` testavel."""
    abertura = start_combat(
        statblocks=CATALOGO,
        participants=duelo(),
        rng=SplitMix64(seed=seed),
    )
    _, resto = play_out(abertura.state)
    return narrate((*abertura.events, *resto))


if __name__ == "__main__":  # pragma: no cover - so roda como `python -m`
    raise SystemExit(main(sys.argv[1:]))

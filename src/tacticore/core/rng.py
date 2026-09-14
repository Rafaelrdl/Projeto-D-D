"""Aleatoriedade como **valor**, nao como objeto injetado.

O RNG deste motor nao e um `random.Random` passado por parametro. Ele e um
dado imutavel que mora dentro do `CombatState` e que cada rolagem devolve
avancado::

    face, rng = roll_die(state.rng, 20)

Isso resolve de uma vez os dois requisitos que brigam entre si: aleatoriedade
injetada (nada de `random` global) e estado 100% serializavel. Um `Random`
injetado satisfaz o primeiro e quebra o segundo -- salvar no meio de uma
rodada nao restaura a posicao do stream, e o combate recarregado passa a
divergir do original.

**Gerador proprio, e nao `random.Random`**, por dois motivos:

1. `random.randint` nao e contrato estavel entre versoes do CPython. Um save
   de hoje precisa reproduzir o mesmo combate no ano que vem.
2. Um gerador *counter-based* tem estado de duas palavras (`seed`, `counter`)
   que cabe num JSON. O estado do Mersenne Twister sao 624 palavras e uma
   posicao, e serializa-lo e mais frageis do que escrever este arquivo.

O algoritmo e o splitmix64 de Vigna em forma indexada: a palavra `n` e
`mix(seed + (n + 1) * GOLDEN)`, calculada direto, sem iterar. O `+ 1` nao e
enfeite -- `mix(0)` e `0`, entao `seed=0, counter=0` daria a palavra zero e
todo primeiro dado de todo combate com seed 0 sairia `1`.

O mapeamento palavra -> face usa multiply-shift de Lemire **sem rejeicao**:
`(word * faces) >> 64`. Sem rejeicao porque o laco de rejeicao consumiria um
numero variavel de palavras por dado, e a quantidade de palavras consumidas e
contrato publico (ver ADR 0001). O vies residual e da ordem de `faces / 2**64`
-- uns 10**-18 para um d20, contra 10**-4 de uma vida inteira de rolagens.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, assert_never

from tacticore.core.errors import RngExhausted, ScriptedRngOutOfRange

_MASK64 = 0xFFFFFFFFFFFFFFFF
_GOLDEN = 0x9E3779B97F4A7C15
_MIX_A = 0xBF58476D1CE4E5B9
_MIX_B = 0x94D049BB133111EB

ALGORITHM = "splitmix64-lemire/1"
"""Identificador do algoritmo, gravado no envelope de save.

Trocar o gerador troca esta string. Um save antigo carregado por um motor com
outro algoritmo tem que falhar alto, nao simular diferente em silencio.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class SplitMix64:
    """Gerador de producao: duas palavras de estado, salto direto por indice."""

    kind: Literal["splitmix64"] = "splitmix64"
    seed: int
    counter: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class ScriptedRng:
    """Fita de dados escritos a mao, para teste.

    E um duble que e **valor serializavel**, e nao uma injecao de dependencia:
    um combate roteirizado salva e recarrega como qualquer outro, e um bug
    encontrado com seed de producao vira teste de regressao copiando a fita
    (`tape_from_events`) para ca.
    """

    kind: Literal["scripted"] = "scripted"
    script: tuple[int, ...]
    cursor: int = 0


type RngState = SplitMix64 | ScriptedRng


def _word(seed: int, counter: int) -> int:
    """A palavra de indice `counter`, calculada sem iterar as anteriores."""
    z = (seed + (counter + 1) * _GOLDEN) & _MASK64
    z = ((z ^ (z >> 30)) * _MIX_A) & _MASK64
    z = ((z ^ (z >> 27)) * _MIX_B) & _MASK64
    return z ^ (z >> 31)


def position(rng: RngState) -> int:
    """Quantos dados ja foram consumidos deste RNG.

    Funcao e nao `property` porque `RngState` e uma uniao de dataclasses com
    `slots`, e uma propriedade comum aos dois membros nao existe de graca.
    Vai nos eventos como `rng_before`/`rng_after`: quando dois combates com a
    mesma seed divergem, a bisseccao comeca por "divergiu no evento 14, na
    posicao 9".
    """
    match rng:
        case SplitMix64():
            return rng.counter
        case ScriptedRng():
            return rng.cursor
        case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
            assert_never(rng)


def roll_die(rng: RngState, faces: int) -> tuple[int, RngState]:
    """Rola **um** dado e devolve `(face, rng avancado)`.

    Consome exatamente uma posicao do stream, sempre, qualquer que seja a face
    sorteada. Essa invariante e o que torna o contrato de consumo do RNG
    verificavel por `position()` em vez de por inspecao do codigo.
    """
    if faces < 1:
        msg = f"dado precisa de ao menos uma face, recebi {faces}"
        raise ValueError(msg)

    match rng:
        case SplitMix64():
            face = ((_word(rng.seed, rng.counter) * faces) >> 64) + 1
            return face, replace(rng, counter=rng.counter + 1)
        case ScriptedRng():
            if rng.cursor >= len(rng.script):
                msg = (
                    f"fita de {len(rng.script)} valores esgotada: "
                    f"o motor pediu o dado numero {rng.cursor + 1}"
                )
                raise RngExhausted(msg)
            face = rng.script[rng.cursor]
            if not 1 <= face <= faces:
                msg = f"a fita mandou {face} na posicao {rng.cursor}, impossivel num d{faces}"
                raise ScriptedRngOutOfRange(msg)
            return face, replace(rng, cursor=rng.cursor + 1)
        case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
            assert_never(rng)


def roll_dice(rng: RngState, count: int, faces: int) -> tuple[tuple[int, ...], RngState]:
    """Rola `count` dados iguais, um por posicao do stream, em ordem."""
    if count < 0:
        msg = f"nao existe quantidade negativa de dados, recebi {count}"
        raise ValueError(msg)

    faces_rolled: list[int] = []
    current = rng
    for _ in range(count):
        face, current = roll_die(current, faces)
        faces_rolled.append(face)
    return tuple(faces_rolled), current

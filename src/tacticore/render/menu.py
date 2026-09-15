"""O menu numerado e a leitura do que o jogador digitou.

As duas metades moram aqui, e nao no comando, por dois motivos.

O primeiro e cobertura: `tacticore.__main__` esta fora de `source_pkgs`, entao
tudo que morasse la nasceria sem medida. Aqui dentro, `escolha` e medida como
qualquer regra -- e ela **e** uma regra, no sentido que importa: decide o que
vira `Action` e o que e recusado.

O segundo e a assimetria deliberada entre `legal_actions` e `validate`. O motor
aceita acoes que o menu nao ofereceu, de proposito, porque `validate` responde
"isto e legal?" e `legal_actions` responde "o que vale a pena oferecer?". Um
leitor de entrada que convertesse "9" num indice sem conferir a faixa entregaria
ao motor uma acao fora do menu, e `apply` poderia aceita-la em silencio. Por
isso `escolha` **so** devolve item da tupla que recebeu, nunca acao montada.

`Action | None` e valor de retorno, e nao campo de estado: a proibicao de `None`
do CLAUDE.md fala de estado serializavel, e o precedente e
`combat_result(state) -> CombatOutcome | None`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import assert_never

from tacticore.core.actions import (
    Action,
    AttackAction,
    EndTurnAction,
    MoveAction,
    ShoveAction,
    StandUpAction,
)

PRIMEIRO = 1
"""O menu comeca em 1 e nao em 0.

Quem digita nao esta indexando uma lista; esta escolhendo o primeiro item."""


def descrever(action: Action) -> str:
    """Uma acao em portugues, montada dos campos crus.

    Fecha com `assert_never` pelo mesmo motivo que `narrate_event`: acao nova
    sem descricao vira erro de mypy, e nao um item de menu em branco que o
    jogador escolhe sem saber o que e.
    """
    match action:
        case AttackAction():
            return f"atacar {action.target} com {action.attack_id}"
        case MoveAction():
            return f"andar ate ({action.to.x},{action.to.y})"
        case ShoveAction():
            return f"empurrar {action.target}"
        case StandUpAction():
            return "levantar"
        case EndTurnAction():
            return "encerrar o turno"
        case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
            assert_never(action)


def menu(acoes: Sequence[Action]) -> tuple[str, ...]:
    """Uma linha numerada por acao, na ordem em que `legal_actions` as deu.

    A ordem **nao** e reorganizada aqui. Ela e contrato declarado no ADR 0002
    sec. 1, ordenada por quanto a escolha custa, e um menu que a embaralhasse
    por conta propria faria `acoes[0]` deixar de ser a mesma coisa para o
    piloto automatico e para o humano.
    """
    return tuple(f"{i} {descrever(a)}" for i, a in enumerate(acoes, start=PRIMEIRO))


def escolha(entrada: str, acoes: Sequence[Action]) -> Action | None:
    """A acao que a entrada nomeia, ou `None` para "nao entendi".

    Devolve sempre um item de `acoes`, nunca uma acao montada aqui -- ver o
    docstring do modulo. `None` e "pergunte de novo", e nunca "encerre o
    turno": um laco que confundisse os dois comeria a jogada do jogador.
    """
    texto = entrada.strip()
    if not (texto.isascii() and texto.isdigit()):
        # Tres filtros de uma vez, e os tres com um caso concreto atras.
        #
        # `isdigit` e nao `try: int(...)` porque `int` aceita "+2", "-1" e
        # sublinhado no meio ("1_0"), e nenhuma dessas coisas o jogador quis
        # dizer num menu numerado.
        #
        # `isascii` **junto** porque `isdigit` sozinho nao e o filtro que
        # parece. Ele diz True para todo digito Unicode: U+0661, o
        # arabico-indiano UM, passa e `int` o converte em 1 -- ou seja,
        # escolheria o primeiro item do menu. Pior ainda, U+00B2, o expoente
        # DOIS, tambem passa e `int` LEVANTA nele: o filtro deixaria entrar
        # justamente o que estoura na linha seguinte.
        return None

    indice = int(texto) - PRIMEIRO
    if not 0 <= indice < len(acoes):
        return None
    return acoes[indice]

"""O que aconteceu, em dados crus.

Sem os eventos, um teste nao consegue afirmar quase nada do que interessa: um
acerto critico e um acerto comum de mesmo dano produzem exatamente a mesma
diferenca de HP, e "houve vantagem" nao deixa rastro nenhum no estado. Afirmar
sobre o log e o que torna o motor testavel sem espiar o RNG por dentro.

**Nenhum evento carrega frase formatada.** "Goblin acerta Heroi com a cimitarra
(17 contra CA 14)" e apresentacao, e apresentacao dentro do core e I/O
disfarcado: fixaria idioma, formato e publico numa camada que nao deveria saber
que existe uma tela. O evento carrega os numeros e o nome do ataque; montar a
frase e trabalho de quem for exibir.

Os eventos saem no **retorno** de cada acao e nunca se acumulam dentro do
estado. Log dentro do estado incharia o save de forma ilimitada e -- pior --
destruiria a igualdade estrutural entre dois combates rodados com a mesma
seed, que e exatamente o que os testes de determinismo comparam.

Todo evento de rolagem carrega `rng_before` e `rng_after`. Quando duas
execucoes com a mesma seed divergirem, a bisseccao comeca por "divergiu no
evento 14, entre as posicoes 9 e 11" em vez de por leitura de codigo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tacticore.core.enums import SkipReason
from tacticore.core.ids import CreatureId
from tacticore.core.model import TurnBudget


@dataclass(frozen=True, slots=True, kw_only=True)
class InitiativeRolled:
    """Uma rolagem de iniciativa, com tudo que entrou no desempate."""

    kind: Literal["initiative_rolled"] = "initiative_rolled"
    creature: CreatureId
    d20: int
    dex_mod: int
    dex_score: int
    total: int
    rng_before: int
    rng_after: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnOrderSet:
    """A ordem final, **gravada**.

    Gravar em vez de deixar quem le o log reordenar: a ordem e resultado de uma
    regra de desempate, e um replay que a recalcule esta testando a regra duas
    vezes em vez de conferir o resultado uma.
    """

    kind: Literal["turn_order_set"] = "turn_order_set"
    order: tuple[CreatureId, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class RoundStarted:
    kind: Literal["round_started"] = "round_started"
    round_number: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnStarted:
    kind: Literal["turn_started"] = "turn_started"
    creature: CreatureId
    budget: TurnBudget


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnEnded:
    kind: Literal["turn_ended"] = "turn_ended"
    creature: CreatureId


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnSkipped:
    """O turno de alguem que nao pode agir passou sem abrir.

    Sai **antes** de qualquer `TurnStarted`, e sem reset de orcamento: quem
    esta caido nao ganha um turno para depois nao usar.
    """

    kind: Literal["turn_skipped"] = "turn_skipped"
    creature: CreatureId
    reason: SkipReason


@dataclass(frozen=True, slots=True, kw_only=True)
class MovementSpent:
    kind: Literal["movement_spent"] = "movement_spent"
    creature: CreatureId
    feet: int
    remaining_ft: int


type Event = (
    InitiativeRolled
    | TurnOrderSet
    | RoundStarted
    | TurnStarted
    | TurnSkipped
    | TurnEnded
    | MovementSpent
)

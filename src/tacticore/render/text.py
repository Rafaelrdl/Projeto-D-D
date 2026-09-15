"""Uma linha de texto por evento do combate.

O formato e o de um placar, nao o de um romance: a conta aparece aberta, porque
a pergunta que se faz olhando um log e quase sempre "de onde saiu esse numero".
``d20 17 +0 FOR +3 prof = 20 vs CA 13`` responde; "o duelista golpeia com
precisao" nao.

Os identificadores saem **crus** -- ``goblin_1``, e nao "Goblin #1". Eles ja sao
slugs legiveis por decisao de `core.ids`, e um parametro de "nome bonito" sem
ninguem para consumi-lo seria exatamente o gancho morto que a etapa 2 esta
cortando em outros lugares. Nome de exibicao entra quando houver uma interface
que o peca.

O `match` de `narrate_event` fecha com ``assert_never``: evento novo sem frase
vira erro de mypy, e nao uma linha faltando no meio do texto que ninguem nota.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import assert_never

from tacticore.core.dice import DamageRoll
from tacticore.core.enums import AdvantageState, AttackOutcome
from tacticore.core.events import (
    AttackRolled,
    CombatEnded,
    CreatureDowned,
    DamageRolled,
    Event,
    HpChanged,
    InitiativeRolled,
    MovementSpent,
    RoundStarted,
    TurnEnded,
    TurnOrderSet,
    TurnSkipped,
    TurnStarted,
)

RECUO = "  "
"""Consequencia de uma acao entra recuada: dano e vida sao efeito do ataque da
linha de cima, e alinha-los faria o log parecer uma lista de coisas
independentes."""

_DESFECHO = {
    AttackOutcome.CRITICAL_HIT: "ACERTO CRITICO",
    AttackOutcome.HIT: "acerto",
    AttackOutcome.MISS: "erro",
    AttackOutcome.CRITICAL_MISS: "ERRO CRITICO",
}


def _sinal(valor: int) -> str:
    """`+3`, `-1`, `+0`. Sempre com sinal, para a conta somar na leitura."""
    return f"{valor:+d}"


def _d20(event: AttackRolled) -> str:
    """O dado, mostrando o par so quando o par importou."""
    match event.advantage:
        case AdvantageState.NORMAL:
            return f"d20 {event.natural}"
        case AdvantageState.ADVANTAGE:
            fontes = ", ".join(event.advantage_sources)
            return f"d20 {event.pair[0]}/{event.pair[1]} vantagem ({fontes}) -> {event.natural}"
        case AdvantageState.DISADVANTAGE:
            fontes = ", ".join(event.disadvantage_sources)
            return f"d20 {event.pair[0]}/{event.pair[1]} desvantagem ({fontes}) -> {event.natural}"
        case _:  # pragma: no cover - inalcancavel: mypy fecha o enum
            assert_never(event.advantage)


def _dados_de_dano(roll: DamageRoll) -> str:
    return " ".join(f"d{d.faces}={d.value}" for d in roll.dice)


def narrate_event(event: Event) -> str:
    """Uma linha para um evento. Nunca vazia, nunca com quebra dentro."""
    match event:
        case InitiativeRolled():
            return (
                f"{event.creature} rola iniciativa: d20 {event.d20} "
                f"{_sinal(event.dex_mod)} (DES {event.dex_score}) = {event.total}"
            )

        case TurnOrderSet():
            return "ordem de iniciativa: " + ", ".join(str(c) for c in event.order)

        case RoundStarted():
            return f"== rodada {event.round_number} =="

        case TurnStarted():
            acao = "1 acao" if event.budget.action_available else "sem acao"
            return f"turno de {event.creature}: {acao}, {event.budget.movement_remaining_ft} pes"

        case TurnSkipped():
            return f"{event.creature} perde o turno ({event.reason.value.lower()})"

        case TurnEnded():
            return f"{event.creature} encerra o turno"

        case MovementSpent():
            return (
                f"{event.creature} anda {event.feet} pes "
                f"({event.origin.x},{event.origin.y}) -> "
                f"({event.destination.x},{event.destination.y}), "
                f"{event.remaining_ft} restantes"
            )

        case AttackRolled():
            return (
                f"{event.actor} ataca {event.target} com {event.attack_name}: "
                f"{_d20(event)} {_sinal(event.ability_mod)} {event.ability.value} "
                f"{_sinal(event.proficiency)} prof = {event.total} "
                f"vs CA {event.target_ac} -> {_DESFECHO[event.outcome]}"
            )

        case DamageRolled():
            rotulo = "dano critico" if event.roll.critical else "dano"
            return (
                f"{RECUO}{rotulo}: {_dados_de_dano(event.roll)} "
                f"{_sinal(event.roll.flat + event.roll.ability_bonus)} "
                f"= {event.roll.total}"
            )

        case HpChanged():
            perdido = f", {event.overkill} desperdicados" if event.overkill else ""
            return (
                f"{RECUO}{event.creature}: {event.before.current} -> "
                f"{event.after.current} hp ({event.dealt} de dano{perdido})"
            )

        case CreatureDowned():
            return f"{RECUO}{event.creature} cai"

        case CombatEnded():
            if event.outcome.winning_team is None:
                return f"combate encerrado na rodada {event.outcome.last_round}: ninguem sobrou"
            # "vitoria de X" e nao "X vence": nome de time e string livre, entao
            # nao da para concordar verbo com ele.
            return (
                f"combate encerrado na rodada {event.outcome.last_round}: "
                f"vitoria de {event.outcome.winning_team}"
            )

        case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
            assert_never(event)


def narrate(events: Sequence[Event]) -> tuple[str, ...]:
    """O log inteiro, uma linha por evento, na ordem em que aconteceram."""
    return tuple(narrate_event(e) for e in events)

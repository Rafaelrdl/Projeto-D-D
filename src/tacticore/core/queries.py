"""Perguntas de leitura sobre o estado, num lugar so.

Existem para que "esta de pe" nao seja reescrito como `hp.current > 0` em oito
lugares. No dia em que cair deixar de ser exatamente isso -- quando houver
condicao de inconsciente, ou morte separada de queda -- muda aqui e so aqui.
"""

from __future__ import annotations

from tacticore.core.errors import CorruptStateError
from tacticore.core.ids import CreatureId
from tacticore.core.model import Combatant, CombatState, Statblock


def is_standing(combatant: Combatant) -> bool:
    """Se ainda esta de pe. Cair e chegar a zero."""
    return combatant.hp.current > 0


def combatant_of(state: CombatState, creature: CreatureId) -> Combatant | None:
    """O combatente, ou `None` se o id nao participa deste combate."""
    return state.combatants.get(creature)


def statblock_of(state: CombatState, creature: CreatureId) -> Statblock:
    """A ficha de um participante.

    Levanta `CorruptStateError` quando nao acha: um combatente apontando para
    ficha inexistente e bug do motor ou save que passou por `load` sem
    checagem, e nunca jogada ilegal. Rejeitar aqui esconderia o estrago.
    """
    combatant = state.combatants.get(creature)
    if combatant is None:
        msg = f"{creature!r} nao participa deste combate"
        raise CorruptStateError(msg)

    statblock = state.statblocks.get(combatant.statblock_id)
    if statblock is None:
        msg = f"{creature!r} aponta para a ficha inexistente {combatant.statblock_id!r}"
        raise CorruptStateError(msg)
    return statblock


def standing_teams(state: CombatState) -> tuple[str, ...]:
    """Os times que ainda tem alguem de pe, em ordem alfabetica.

    Tupla ordenada e nao `set`: o resultado alimenta a decisao de fim de
    combate, e um conjunto obrigaria quem consome a escolher um elemento de uma
    colecao cuja ordem de iteracao varia com `PYTHONHASHSEED`.
    """
    return tuple(sorted({c.team for c in state.combatants.values() if is_standing(c)}))

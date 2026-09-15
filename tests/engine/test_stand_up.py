"""Levantar-se de Caido.

E a unica transicao de condicao que este motor sabe fazer. A APLICACAO vem do
encontro, porque na SRD as fontes de Caido sao Empurrar e magia, e as duas estao
fora de escopo -- Empurrar precisa de teste de atributo oposto, que consumiria
RNG fora de ataque pela primeira vez.

Levantar **nao e uma acao**: custa metade do deslocamento. Isso coube sem
inventar nada porque `TurnBudget` guarda movimento em pes e nao um bool de "ja
andou" -- decisao da etapa 1, e era este o caso que ela previa.
"""

from __future__ import annotations

import pytest

from tacticore.core.actions import MoveAction, StandUpAction
from tacticore.core.engine import apply, legal_actions
from tacticore.core.enums import Condition, RejectionReason
from tacticore.core.events import StoodUp
from tacticore.core.ids import CreatureId
from tacticore.core.model import CombatState, Position
from tacticore.core.results import ActionResult, Applied, Rejected
from tacticore.core.rng import ScriptedRng
from tacticore.core.rules import stand_up_cost_ft
from tacticore.core.testing import (
    make_budget,
    make_combatant,
    make_statblock,
    make_state,
)


def arena(
    *,
    caido: bool = True,
    speed_ft: int = 30,
    movimento: int | None = None,
    casas: int = 1,
) -> CombatState:
    """`a` caido em (0,0) e `b` a `casas` de distancia.

    A fita e generosa de proposito: o menu oferece ataque quando `b` esta ao
    alcance, e o teste da propriedade central aplica tudo que for oferecido.
    """
    ficha = make_statblock(id="ficha", speed_ft=speed_ft)
    orcamento = None if movimento is None else make_budget(movement_remaining_ft=movimento)
    return make_state(
        statblocks=(ficha,),
        combatants=(
            make_combatant(
                id="a",
                statblock_id="ficha",
                team="herois",
                budget=orcamento,
                conditions=(Condition.CAIDO,) if caido else (),
            ),
            make_combatant(id="b", statblock_id="ficha", team="viloes"),
        ),
        current="a",
        rng=ScriptedRng(script=(10, 10, 3, 3, 3, 3)),
        posicoes={"a": (0, 0), "b": (casas, 0)},
    )


def levantar(estado: CombatState) -> ActionResult:
    return apply(estado, StandUpAction(actor=CreatureId("a")))


# ------------------------------------------------------------- o custo -----


@pytest.mark.parametrize(("speed_ft", "custo"), [(30, 15), (35, 17), (25, 12), (5, 2)])
def test_levantar_custa_metade_do_deslocamento(speed_ft: int, custo: int):
    """Arredonda para baixo, como toda conta inteira do SRD neste motor."""
    assert stand_up_cost_ft(speed_ft) == custo


def test_levantar_debita_o_movimento_e_nao_a_acao():
    resultado = levantar(arena(speed_ft=30))
    assert isinstance(resultado, Applied)

    ator = resultado.state.combatants["a"]
    assert ator.budget.movement_remaining_ft == 15
    assert ator.budget.action_available is True, "levantar NAO e uma acao"


def test_levantar_tira_a_condicao():
    resultado = levantar(arena())
    assert isinstance(resultado, Applied)
    assert resultado.state.combatants["a"].conditions == ()


def test_levantar_emite_o_evento_com_a_conta():
    resultado = levantar(arena(speed_ft=35))
    assert isinstance(resultado, Applied)
    evento = resultado.events[0]
    assert isinstance(evento, StoodUp)
    assert (evento.feet, evento.remaining_ft) == (17, 30 - 17)


def test_levantar_nao_move_ninguem():
    """O evento e proprio e nao `MovementSpent` justamente por isso."""
    estado = arena()
    resultado = levantar(estado)
    assert isinstance(resultado, Applied)
    assert resultado.state.combatants["a"].position == estado.combatants["a"].position


def test_o_estado_original_fica_intacto():
    estado = arena()
    levantar(estado)
    assert estado.combatants["a"].conditions == (Condition.CAIDO,)


# --------------------------------------------------------- as recusas ------


def test_quem_nao_esta_caido_nao_levanta():
    resultado = levantar(arena(caido=False))
    assert isinstance(resultado, Rejected)
    assert resultado.reason is RejectionReason.NOT_PRONE


def test_sem_movimento_para_pagar_nao_levanta():
    resultado = levantar(arena(speed_ft=30, movimento=14))
    assert isinstance(resultado, Rejected)
    assert resultado.reason is RejectionReason.NOT_ENOUGH_MOVEMENT
    assert "levantar custa 15 pes" in resultado.detail


def test_o_custo_exato_basta():
    resultado = levantar(arena(speed_ft=30, movimento=15))
    assert isinstance(resultado, Applied)
    assert resultado.state.combatants["a"].budget.movement_remaining_ft == 0


def test_levantar_duas_vezes_e_recusado_na_segunda():
    primeira = levantar(arena())
    assert isinstance(primeira, Applied)
    segunda = apply(primeira.state, StandUpAction(actor=CreatureId("a")))
    assert isinstance(segunda, Rejected)
    assert segunda.reason is RejectionReason.NOT_PRONE


# ------------------------------------------------------------- o menu ------


def test_o_menu_oferece_levantar_a_quem_esta_caido():
    acoes = legal_actions(arena())
    assert StandUpAction(actor=CreatureId("a")) in acoes


def test_o_menu_nao_oferece_levantar_a_quem_esta_de_pe():
    assert not any(isinstance(a, StandUpAction) for a in legal_actions(arena(caido=False)))


def test_o_menu_nao_oferece_o_que_nao_da_para_pagar():
    """Como todo item do menu: so entra com orcamento para custear."""
    assert not any(
        isinstance(a, StandUpAction) for a in legal_actions(arena(speed_ft=30, movimento=14))
    )


def test_levantar_vem_antes_de_andar():
    """No degrau do movimento, porque e movimento que ele gasta -- e antes de
    andar, porque um caido que anda continua caido e volta a atacar com
    desvantagem."""
    # Com `b` longe ha casa canonica para andar, entao os dois aparecem juntos.
    tipos = [type(a) for a in legal_actions(arena(casas=6))]
    assert tipos.index(StandUpAction) < tipos.index(MoveAction)


def test_toda_acao_oferecida_a_um_caido_e_aceita():
    """A propriedade central de `legal_actions`, agora com o caido incluido."""
    for estado in (
        arena(),
        arena(speed_ft=30, movimento=20),
        arena(speed_ft=5),
        arena(casas=6),
    ):
        for acao in legal_actions(estado):
            resultado = apply(estado, acao)
            assert isinstance(resultado, Applied), f"{acao} recusada: {resultado}"


def test_levantar_de_uma_casa_qualquer_nao_depende_da_posicao():
    estado = make_state(
        statblocks=(make_statblock(id="ficha", speed_ft=30),),
        combatants=(
            make_combatant(
                id="a", statblock_id="ficha", team="herois", conditions=(Condition.CAIDO,)
            ),
            make_combatant(id="b", statblock_id="ficha", team="viloes"),
        ),
        current="a",
        posicoes={"a": (-7, 3), "b": (9, 9)},
    )
    resultado = levantar(estado)
    assert isinstance(resultado, Applied)
    assert resultado.state.combatants["a"].position == Position(x=-7, y=3)

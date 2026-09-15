"""Economia de turno, avanco de rodada e turno pulado."""

from __future__ import annotations

from tacticore.core.actions import EndTurnAction, MoveAction
from tacticore.core.engine import advance_turn, apply
from tacticore.core.enums import RejectionReason, SkipReason
from tacticore.core.events import (
    MovementSpent,
    RoundStarted,
    TurnEnded,
    TurnSkipped,
    TurnStarted,
)
from tacticore.core.ids import CreatureId
from tacticore.core.model import CombatState, Position, TurnBudget
from tacticore.core.results import ActionResult, Applied, Rejected
from tacticore.core.testing import make_budget, make_combatant, make_statblock, make_state


def casa(x: int, y: int) -> Position:
    return Position(x=x, y=y)


def duelo(*, current: str = "a") -> CombatState:
    """Dois combatentes na ordem a, b, com deslocamento de 30 pes.

    `make_state` enfileira: `a` em (0,0) e `b` em (1,0). Os testes de
    movimento andam no eixo y para nao esbarrar em `b`."""
    return make_state(
        statblocks=(make_statblock(id="ficha", speed_ft=30),),
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes"),
        ),
        current=current,
    )


def trio_com_um_caido(*, current: str = "a", budget_b: TurnBudget | None = None) -> CombatState:
    """`b` caido, mas o combate segue porque `c` esta de pe no time dele.

    Um duelo nao serve para testar turno pulado: com um dos dois caido, o
    combate ja acabou, e a proxima acao seria recusada com COMBAT_OVER antes de
    chegar no avanco de turno.
    """
    return make_state(
        statblocks=(make_statblock(id="ficha", speed_ft=30),),
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes", hp=0, budget=budget_b),
            make_combatant(id="c", team="viloes"),
        ),
        current=current,
    )


def aplicado(resultado: ActionResult) -> Applied:
    assert isinstance(resultado, Applied), resultado
    return resultado


# ------------------------------------------------------------ movimento ----


def test_movimento_debita_o_orcamento():
    estado = duelo()
    resultado = aplicado(apply(estado, MoveAction(actor=CreatureId("a"), to=casa(0, 3))))
    assert resultado.state.combatants["a"].budget.movement_remaining_ft == 15
    assert resultado.state.combatants["a"].position == casa(0, 3)


def test_movimento_emite_o_evento_com_o_que_sobrou():
    estado = duelo()
    resultado = aplicado(apply(estado, MoveAction(actor=CreatureId("a"), to=casa(0, 4))))
    evento = resultado.events[0]
    assert isinstance(evento, MovementSpent)
    assert (evento.feet, evento.remaining_ft) == (20, 10)
    assert (evento.origin, evento.destination) == (casa(0, 0), casa(0, 4))


def test_movimento_pode_ser_gasto_em_pedacos():
    estado = duelo()
    depois = aplicado(apply(estado, MoveAction(actor=CreatureId("a"), to=casa(0, 2)))).state
    depois = aplicado(apply(depois, MoveAction(actor=CreatureId("a"), to=casa(0, 4)))).state
    assert depois.combatants["a"].budget.movement_remaining_ft == 10
    assert depois.combatants["a"].position == casa(0, 4)


def test_movimento_nao_gasta_a_acao():
    """Uma acao e um movimento sao orcamentos separados."""
    estado = duelo()
    resultado = aplicado(apply(estado, MoveAction(actor=CreatureId("a"), to=casa(0, 6))))
    assert resultado.state.combatants["a"].budget.action_available is True


def test_mover_zero_e_legal_e_nao_muda_nada():
    estado = duelo()
    resultado = aplicado(apply(estado, MoveAction(actor=CreatureId("a"), to=casa(0, 0))))
    assert resultado.state.combatants["a"].budget == estado.combatants["a"].budget
    assert resultado.state.combatants["a"].position == casa(0, 0)


def test_o_estado_original_nao_e_tocado():
    estado = duelo()
    apply(estado, MoveAction(actor=CreatureId("a"), to=casa(0, 6)))
    assert estado.combatants["a"].budget.movement_remaining_ft == 30
    assert estado.combatants["a"].position == casa(0, 0)


# ------------------------------------------------------------- turno -------


def test_encerrar_turno_passa_para_o_proximo():
    estado = duelo()
    resultado = aplicado(apply(estado, EndTurnAction(actor=CreatureId("a"))))
    assert resultado.state.turn_order.current == "b"


def test_encerrar_turno_emite_fim_e_comeco():
    estado = duelo()
    resultado = aplicado(apply(estado, EndTurnAction(actor=CreatureId("a"))))
    assert [type(e) for e in resultado.events] == [TurnEnded, TurnStarted]


def test_o_orcamento_e_resetado_no_comeco_do_turno():
    estado = duelo()
    gasto = aplicado(apply(estado, MoveAction(actor=CreatureId("a"), to=casa(0, 6)))).state
    volta = aplicado(apply(gasto, EndTurnAction(actor=CreatureId("a")))).state
    volta = aplicado(apply(volta, EndTurnAction(actor=CreatureId("b")))).state

    assert volta.turn_order.current == "a"
    assert volta.combatants["a"].budget.movement_remaining_ft == 30


def test_o_orcamento_resetado_vem_do_deslocamento_da_ficha():
    estado = make_state(
        statblocks=(make_statblock(id="ficha", speed_ft=45),),
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes"),
        ),
    )
    resultado = aplicado(apply(estado, EndTurnAction(actor=CreatureId("a"))))
    evento = resultado.events[-1]
    assert isinstance(evento, TurnStarted)
    assert evento.budget.movement_remaining_ft == 45


# ------------------------------------------------------------ rodada -------


def test_a_rodada_sobe_so_na_volta_completa():
    estado = duelo()
    assert estado.turn_order.round_number == 1

    meio = aplicado(apply(estado, EndTurnAction(actor=CreatureId("a")))).state
    assert meio.turn_order.round_number == 1

    volta = aplicado(apply(meio, EndTurnAction(actor=CreatureId("b")))).state
    assert volta.turn_order.round_number == 2
    assert volta.turn_order.current == "a"


def test_a_virada_de_rodada_e_anunciada():
    estado = duelo(current="b")
    resultado = aplicado(apply(estado, EndTurnAction(actor=CreatureId("b"))))
    tipos = [type(e) for e in resultado.events]
    assert tipos == [TurnEnded, RoundStarted, TurnStarted]


def test_duas_rodadas_inteiras():
    estado = duelo()
    for _ in range(4):
        estado = aplicado(apply(estado, EndTurnAction(actor=estado.turn_order.current))).state
    assert estado.turn_order.round_number == 3
    assert estado.turn_order.current == "a"


# ------------------------------------------------------- turno pulado ------


def test_quem_esta_caido_tem_o_turno_pulado():
    estado = trio_com_um_caido()
    resultado = aplicado(apply(estado, EndTurnAction(actor=CreatureId("a"))))

    pulados = [e for e in resultado.events if isinstance(e, TurnSkipped)]
    assert len(pulados) == 1
    assert pulados[0].creature == "b"
    assert pulados[0].reason is SkipReason.ACTOR_IS_DOWN
    assert resultado.state.turn_order.current == "c"


def test_o_pulo_sai_antes_de_qualquer_turno_comecar():
    """A ordem dos eventos e o que o golden vai congelar."""
    estado = trio_com_um_caido()
    resultado = aplicado(apply(estado, EndTurnAction(actor=CreatureId("a"))))
    tipos = [type(e) for e in resultado.events]
    assert tipos == [TurnEnded, TurnSkipped, TurnStarted]


def test_quem_esta_caido_nao_ganha_orcamento():
    """Nao se ganha um turno para depois nao usar."""
    estado = trio_com_um_caido(
        budget_b=make_budget(action_available=False, movement_remaining_ft=0)
    )
    resultado = aplicado(apply(estado, EndTurnAction(actor=CreatureId("a"))))
    caido = resultado.state.combatants["b"]
    assert caido.budget.action_available is False
    assert caido.budget.movement_remaining_ft == 0


def test_quem_caiu_continua_na_ordem_de_iniciativa():
    """Sair da ordem mudaria a posicao de todo mundo no meio da rodada."""
    estado = trio_com_um_caido()
    resultado = aplicado(apply(estado, EndTurnAction(actor=CreatureId("a"))))
    assert resultado.state.turn_order.order == ("a", "b", "c")


def test_ninguem_de_pe_encerra_a_volta_sem_abrir_turno():
    """Estado degenerado: o laco anda uma volta e para em vez de travar."""
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes", hp=0),
        ),
        current="a",
    )
    novo, eventos = advance_turn(estado)
    assert novo.turn_order.round_number == 2
    assert not any(isinstance(e, TurnStarted) for e in eventos)
    assert sum(isinstance(e, TurnSkipped) for e in eventos) == 2


# ----------------------------------------------------------- grade ---------


def test_o_custo_e_a_distancia_de_grade_e_nao_o_numero_de_casas():
    """Diagonal custa 5 pes como a reta: tres casas na diagonal sao 15 pes."""
    estado = duelo()
    resultado = aplicado(apply(estado, MoveAction(actor=CreatureId("a"), to=casa(3, 3))))
    evento = resultado.events[0]
    assert isinstance(evento, MovementSpent)
    assert evento.feet == 15


def test_nao_da_para_terminar_na_casa_de_outro():
    """`b` esta em (1,0) por causa do enfileiramento de `make_state`."""
    estado = duelo()
    resultado = apply(estado, MoveAction(actor=CreatureId("a"), to=casa(1, 0)))
    assert isinstance(resultado, Rejected)
    assert resultado.reason is RejectionReason.SQUARE_OCCUPIED


def test_ficar_na_propria_casa_e_legal_e_de_graca():
    """Custo zero, e nao "casa ocupada": o ocupante e o proprio ator."""
    estado = duelo()
    resultado = aplicado(apply(estado, MoveAction(actor=CreatureId("a"), to=casa(0, 0))))
    evento = resultado.events[0]
    assert isinstance(evento, MovementSpent)
    assert evento.feet == 0
    assert evento.remaining_ft == 30


def test_a_casa_liberada_por_quem_andou_pode_ser_ocupada():
    """Sem isto, duas criaturas nunca trocariam de lugar em dois turnos."""
    estado = duelo()
    depois = aplicado(apply(estado, MoveAction(actor=CreatureId("a"), to=casa(0, 2)))).state
    depois = aplicado(apply(depois, EndTurnAction(actor=CreatureId("a")))).state
    resultado = aplicado(apply(depois, MoveAction(actor=CreatureId("b"), to=casa(0, 0))))
    assert resultado.state.combatants["b"].position == casa(0, 0)


def test_andar_para_longe_tambem_e_legal():
    """O motor nao tem opiniao tatica: fugir e uma jogada, nao um erro."""
    estado = duelo()
    resultado = aplicado(apply(estado, MoveAction(actor=CreatureId("a"), to=casa(-6, 0))))
    assert resultado.state.combatants["a"].position == casa(-6, 0)
    assert resultado.state.combatants["a"].budget.movement_remaining_ft == 0

"""Acao ilegal: um teste por motivo, e um teste que cobra os que faltam.

Toda rejeicao afirma duas coisas alem do motivo: que o estado devolvido e a
**mesma instancia** que entrou (`is`, nao `==`, para nenhuma copia silenciosa
se disfarçar de "nada mudou") e que a posicao do RNG nao andou. A segunda e a
que importa de verdade: se uma validacao rodasse depois de uma rolagem, dois
combates com a mesma seed divergiriam so porque um deles tentou uma jogada
ilegal pelo caminho.
"""

from __future__ import annotations

import pytest

from tacticore.core.actions import (
    Action,
    AttackAction,
    EndTurnAction,
    MoveAction,
    StandUpAction,
)
from tacticore.core.engine import apply, validate
from tacticore.core.enums import RejectionReason
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import CombatState, Position, TurnBudget
from tacticore.core.results import Applied, Rejected
from tacticore.core.rng import SplitMix64, position
from tacticore.core.testing import (
    make_attack,
    make_budget,
    make_combatant,
    make_statblock,
    make_state,
)


def duelo(*, current: str = "a", hp_a: int = 10, budget_a: TurnBudget | None = None) -> CombatState:
    return make_state(
        statblocks=(make_statblock(id="ficha", speed_ft=30, attacks=(make_attack(id="espada"),)),),
        combatants=(
            make_combatant(id="a", team="herois", hp=hp_a, budget=budget_a),
            make_combatant(id="b", team="viloes"),
        ),
        current=current,
        rng=SplitMix64(seed=5, counter=3),
    )


def longe() -> CombatState:
    """Como `duelo`, mas com os dois fora do alcance um do outro."""
    return make_state(
        statblocks=(make_statblock(id="ficha", speed_ft=30, attacks=(make_attack(id="espada"),)),),
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes"),
        ),
        current="a",
        posicoes={"a": (0, 0), "b": (4, 0)},
    )


def trio(*, hp_a: int = 10) -> CombatState:
    """Como `duelo`, mas com um terceiro de pe para o combate nao acabar."""
    return make_state(
        statblocks=(make_statblock(id="ficha", speed_ft=30, attacks=(make_attack(id="espada"),)),),
        combatants=(
            make_combatant(id="a", team="herois", hp=hp_a),
            make_combatant(id="b", team="viloes"),
            make_combatant(id="c", team="herois"),
        ),
        current="a",
    )


def recusado(estado: CombatState, acao: Action) -> Rejected:
    resultado = apply(estado, acao)
    assert isinstance(resultado, Rejected), f"esperava rejeicao, veio {resultado}"

    assert resultado.state is estado, "rejeicao tem que devolver a MESMA instancia"
    assert position(resultado.state.rng) == position(estado.rng), (
        "validacao recusada nao pode ter consumido entropia"
    )
    return resultado


# Um caso por motivo, indexado pelo proprio enum. O teste e parametrizado sobre
# `RejectionReason` inteiro, entao motivo novo sem caso falha pelo nome -- e
# falha independentemente da ordem em que os testes rodarem, que e a diferenca
# entre uma trava e um verde por sorte.
CASOS: dict[RejectionReason, tuple[CombatState, Action]] = {
    RejectionReason.NO_SUCH_ACTOR: (
        duelo(),
        EndTurnAction(actor=CreatureId("fantasma")),
    ),
    RejectionReason.NOT_YOUR_TURN: (
        duelo(current="a"),
        EndTurnAction(actor=CreatureId("b")),
    ),
    # `a` caido, mas o combate segue porque `c` esta de pe no time dele. Num
    # duelo, um caido ja seria COMBAT_OVER e este motivo nunca apareceria.
    RejectionReason.ACTOR_IS_DOWN: (
        trio(hp_a=0),
        EndTurnAction(actor=CreatureId("a")),
    ),
    RejectionReason.COMBAT_OVER: (
        duelo(hp_a=0),
        EndTurnAction(actor=CreatureId("a")),
    ),
    RejectionReason.NOT_ENOUGH_MOVEMENT: (
        duelo(),
        # 30 pes de orcamento, 7 casas de distancia: 35 pes.
        MoveAction(actor=CreatureId("a"), to=Position(x=7, y=0)),
    ),
    RejectionReason.SQUARE_OCCUPIED: (
        duelo(),
        MoveAction(actor=CreatureId("a"), to=Position(x=1, y=0)),
    ),
    RejectionReason.ACTION_ALREADY_USED: (
        duelo(budget_a=make_budget(action_available=False)),
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=AttackId("espada")),
    ),
    RejectionReason.NO_SUCH_TARGET: (
        duelo(),
        AttackAction(
            actor=CreatureId("a"), target=CreatureId("fantasma"), attack_id=AttackId("espada")
        ),
    ),
    RejectionReason.NO_SUCH_ATTACK: (
        duelo(),
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=AttackId("bazuca")),
    ),
    RejectionReason.SELF_TARGET_NOT_ALLOWED: (
        duelo(),
        AttackAction(actor=CreatureId("a"), target=CreatureId("a"), attack_id=AttackId("espada")),
    ),
    # Levantar sem estar caido.
    RejectionReason.NOT_PRONE: (duelo(), StandUpAction(actor=CreatureId("a"))),
    # A espada alcanca 5 pes; `b` esta a 20.
    RejectionReason.OUT_OF_RANGE: (
        longe(),
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=AttackId("espada")),
    ),
}


@pytest.mark.parametrize("reason", list(RejectionReason), ids=[r.value for r in RejectionReason])
def test_cada_motivo_de_rejeicao(reason: RejectionReason):
    assert reason in CASOS, (
        f"motivo {reason.value!r} sem caso de teste. "
        "Motivo novo entra com caso em CASOS, no mesmo commit."
    )
    estado, acao = CASOS[reason]
    assert recusado(estado, acao).reason is reason


def test_movimento_alem_do_que_sobrou():
    """A checagem e contra o que RESTA, e nao contra o deslocamento da ficha."""
    estado = duelo(budget_a=make_budget(movement_remaining_ft=10))
    resultado = recusado(estado, MoveAction(actor=CreatureId("a"), to=Position(x=3, y=0)))
    assert resultado.reason is RejectionReason.NOT_ENOUGH_MOVEMENT


# ------------------------------------------------------------ contrato -----


def test_validate_e_apply_concordam():
    """`validate` e a mesma checagem que `apply` roda; nao podem divergir."""
    estado = duelo()
    for acao in (
        EndTurnAction(actor=CreatureId("fantasma")),
        EndTurnAction(actor=CreatureId("b")),
        MoveAction(actor=CreatureId("a"), to=Position(x=99, y=0)),
    ):
        rejeicao = validate(estado, acao)
        assert rejeicao is not None
        resultado = apply(estado, acao)
        assert isinstance(resultado, Rejected)
        assert resultado.reason is rejeicao.reason


def test_acao_legal_passa_pela_validacao():
    estado = duelo()
    assert validate(estado, EndTurnAction(actor=CreatureId("a"))) is None
    assert isinstance(apply(estado, EndTurnAction(actor=CreatureId("a"))), Applied)


def test_o_detalhe_e_diagnostico_e_nao_contrato():
    """Documentado aqui para ninguem escrever teste em cima da frase."""
    resultado = recusado(duelo(), EndTurnAction(actor=CreatureId("b")))
    assert isinstance(resultado.detail, str)
    assert resultado.detail, "a mensagem existe para ajudar a depurar"


@pytest.mark.parametrize("reason", list(RejectionReason))
def test_todo_motivo_serializa_como_o_proprio_nome(reason: RejectionReason):
    """StrEnum: o save e o log ficam legiveis sem tabela de traducao."""
    assert reason.value == reason.name

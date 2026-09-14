"""Times, fim de combate e enumeracao de acoes legais."""

from __future__ import annotations

from tacticore.core.actions import Action, AttackAction, EndTurnAction, MoveAction
from tacticore.core.engine import apply, combat_result, legal_actions
from tacticore.core.enums import RejectionReason
from tacticore.core.events import CombatEnded
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import CombatState
from tacticore.core.results import Applied, Rejected
from tacticore.core.rng import ScriptedRng
from tacticore.core.serde import dump, load
from tacticore.core.testing import (
    make_attack,
    make_budget,
    make_combatant,
    make_statblock,
    make_state,
)

ESPADA = AttackId("espada")


def arena(
    *,
    hp_b: int = 6,
    extras: tuple[tuple[str, str, int], ...] = (),
    fita: tuple[int, ...] = (),
    budget_a: object = None,
) -> CombatState:
    """`a` (herois) contra `b` (viloes), mais quem `extras` pedir."""
    ficha = make_statblock(
        id="ficha",
        armor_class=10,
        max_hp=10,
        speed_ft=30,
        attacks=(make_attack(id="espada", damage="1d6"),),
    )
    lutadores = [
        make_combatant(id="a", team="herois", budget=budget_a),  # type: ignore[arg-type]
        make_combatant(id="b", team="viloes", hp=hp_b),
    ]
    lutadores.extend(make_combatant(id=nome, team=time, hp=vida) for nome, time, vida in extras)
    return make_state(
        statblocks=(ficha,),
        combatants=tuple(lutadores),
        current="a",
        rng=ScriptedRng(script=fita),
    )


def atacar(estado: CombatState, alvo: str = "b") -> Applied | Rejected:
    return apply(
        estado,
        AttackAction(actor=CreatureId("a"), target=CreatureId(alvo), attack_id=ESPADA),
    )


# ------------------------------------------------------ combat_result ------


def test_combate_com_dois_lados_de_pe_esta_em_andamento():
    assert combat_result(arena()) is None


def test_ultimo_abate_encerra_o_combate():
    resultado = atacar(arena(hp_b=1, fita=(15, 1, 6)))
    assert isinstance(resultado, Applied)

    desfecho = combat_result(resultado.state)
    assert desfecho is not None
    assert desfecho.winning_team == "herois"


def test_aniquilacao_mutua_tem_vencedor_nulo():
    """`winning_team=None` e empate, e nao "ainda rolando".

    Misturar os dois faria o combate nunca fechar em aniquilacao mutua -- era
    exatamente o bug de uma das propostas de arquitetura.
    """
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes", hp=0),
        )
    )
    desfecho = combat_result(estado)
    assert desfecho is not None
    assert desfecho.winning_team is None


def test_o_desfecho_guarda_a_rodada():
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes", hp=0),
        ),
        round_number=4,
    )
    desfecho = combat_result(estado)
    assert desfecho is not None
    assert desfecho.last_round == 4


def test_o_desfecho_e_derivado_e_nao_guardado():
    """Derivado resolve dois problemas: nada fica velho e nada some no save."""
    estado = arena()
    assert "outcome" not in dump(estado)["state"]
    assert combat_result(load(dump(estado))) == combat_result(estado)


def test_com_tres_times_derrubar_um_nao_acaba_o_combate():
    """`team` e string livre justamente para isto: tres faccoes e um monstro
    que troca de lado nao migram um enum sem bump de schema."""
    assert combat_result(arena(extras=(("c", "neutros", 10),))) is None

    # Viloes fora, mas herois e neutros continuam de pe: ainda ha dois lados.
    sem_viloes = arena(hp_b=0, extras=(("c", "neutros", 10),))
    assert combat_result(sem_viloes) is None


def test_com_tres_times_acaba_quando_sobra_um():
    so_neutros = arena(hp_b=0, extras=(("c", "neutros", 10), ("d", "herois", 0)))
    caidos = make_state(
        statblocks=tuple(so_neutros.statblocks.values()),
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes", hp=0),
            make_combatant(id="c", team="neutros"),
        ),
        current="c",
    )
    desfecho = combat_result(caidos)
    assert desfecho is not None
    assert desfecho.winning_team == "neutros"


# ------------------------------------------------------- CombatEnded -------


def test_o_fim_e_anunciado_exatamente_na_transicao():
    resultado = atacar(arena(hp_b=1, fita=(15, 1, 6)))
    assert isinstance(resultado, Applied)
    assert sum(isinstance(e, CombatEnded) for e in resultado.events) == 1
    assert isinstance(resultado.events[-1], CombatEnded)


def test_o_anuncio_carrega_o_desfecho():
    resultado = atacar(arena(hp_b=1, fita=(15, 1, 6)))
    assert isinstance(resultado, Applied)
    evento = resultado.events[-1]
    assert isinstance(evento, CombatEnded)
    assert evento.outcome == combat_result(resultado.state)


def test_acao_que_nao_encerra_nao_anuncia_nada():
    resultado = atacar(arena(hp_b=10, fita=(15, 1, 1)))
    assert isinstance(resultado, Applied)
    assert not any(isinstance(e, CombatEnded) for e in resultado.events)


def test_depois_do_fim_tudo_e_recusado():
    resultado = atacar(arena(hp_b=1, fita=(15, 1, 6)))
    assert isinstance(resultado, Applied)
    acabado = resultado.state

    for acao in (
        EndTurnAction(actor=CreatureId("a")),
        MoveAction(actor=CreatureId("a"), distance_ft=5),
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=ESPADA),
    ):
        recusa = apply(acabado, acao)
        assert isinstance(recusa, Rejected)
        assert recusa.reason is RejectionReason.COMBAT_OVER
        assert recusa.state is acabado


def test_o_fim_nao_e_anunciado_duas_vezes():
    """Depois do fim nada e aplicado, entao nao ha segunda transicao."""
    resultado = atacar(arena(hp_b=1, fita=(15, 1, 6)))
    assert isinstance(resultado, Applied)
    segunda = apply(resultado.state, EndTurnAction(actor=CreatureId("a")))
    assert isinstance(segunda, Rejected)


# ------------------------------------------------------ legal_actions ------


def test_o_menu_de_um_turno_inteiro():
    acoes = legal_actions(arena())
    assert acoes == (
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=ESPADA),
        MoveAction(actor=CreatureId("a"), distance_ft=30),
        EndTurnAction(actor=CreatureId("a")),
    )


def test_o_menu_oferece_um_movimento_so_e_nao_todas_as_distancias():
    """Conjunto canonico e finito: com a distancia sendo um inteiro, oferecer
    todas as legais daria um menu grande e inutil."""
    movimentos = [a for a in legal_actions(arena()) if isinstance(a, MoveAction)]
    assert len(movimentos) == 1
    assert movimentos[0].distance_ft == 30


def test_sem_movimento_restante_o_menu_nao_oferece_andar():
    estado = arena(budget_a=make_budget(movement_remaining_ft=0))
    assert not any(isinstance(a, MoveAction) for a in legal_actions(estado))


def test_sem_acao_restante_o_menu_nao_oferece_atacar():
    estado = arena(budget_a=make_budget(action_available=False))
    assert not any(isinstance(a, AttackAction) for a in legal_actions(estado))


def test_o_menu_so_oferece_inimigo_de_pe():
    """Assimetria deliberada: `apply` aceita atacar quem caiu, o menu nao
    oferece. Aqui e o cardapio, nao a definicao de legalidade."""
    estado = arena(extras=(("c", "viloes", 0),))
    alvos = {a.target for a in legal_actions(estado) if isinstance(a, AttackAction)}
    assert alvos == {"b"}


def test_o_menu_nao_oferece_aliado():
    estado = arena(extras=(("c", "herois", 10),))
    alvos = {a.target for a in legal_actions(estado) if isinstance(a, AttackAction)}
    assert alvos == {"b"}


def test_o_menu_e_um_por_par_de_ataque_e_alvo():
    ficha = make_statblock(
        id="ficha",
        attacks=(make_attack(id="espada"), make_attack(id="arco")),
    )
    estado = make_state(
        statblocks=(ficha,),
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes"),
            make_combatant(id="c", team="viloes"),
        ),
        current="a",
    )
    ataques = [a for a in legal_actions(estado) if isinstance(a, AttackAction)]
    assert [(a.attack_id, a.target) for a in ataques] == [
        ("espada", "b"),
        ("espada", "c"),
        ("arco", "b"),
        ("arco", "c"),
    ]


def test_combate_encerrado_nao_oferece_nada():
    assert legal_actions(arena(hp_b=0)) == ()


def test_toda_acao_oferecida_e_aceita():
    """A propriedade central: o menu nunca oferece o que `apply` recusaria."""
    estados = [
        arena(),
        arena(budget_a=make_budget(movement_remaining_ft=5)),
        arena(budget_a=make_budget(action_available=False)),
        arena(extras=(("c", "viloes", 10), ("d", "viloes", 0))),
    ]
    for estado in estados:
        acoes: tuple[Action, ...] = legal_actions(estado)
        assert acoes, "um turno em andamento sempre tem ao menos EndTurn"
        for acao in acoes:
            resultado = apply(
                # Fita generosa: o ataque consome dois d20 mais os dados de dano.
                make_state(
                    statblocks=tuple(estado.statblocks.values()),
                    combatants=tuple(estado.combatants.values()),
                    order=tuple(estado.turn_order.order),
                    current=str(estado.turn_order.current),
                    rng=ScriptedRng(script=(10, 10, 3, 3, 3, 3)),
                ),
                acao,
            )
            assert isinstance(resultado, Applied), f"{acao} foi recusada: {resultado}"


def test_encerrar_o_turno_esta_sempre_no_menu():
    for estado in (
        arena(),
        arena(budget_a=make_budget(action_available=False, movement_remaining_ft=0)),
    ):
        assert any(isinstance(a, EndTurnAction) for a in legal_actions(estado))


def test_menu_vazio_para_quem_esta_caido():
    """Estado que o chamador consegue montar: o caido e o dono do turno, mas o
    time dele ainda tem gente de pe. O avanco normal de turno pula esse caso;
    o menu tambem nao pode oferecer nada."""
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes"),
            make_combatant(id="c", team="herois"),
        ),
        current="a",
    )
    assert combat_result(estado) is None
    assert legal_actions(estado) == ()

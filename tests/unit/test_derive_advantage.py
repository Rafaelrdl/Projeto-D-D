"""Vantagem e desvantagem derivadas do estado.

Este gancho existiu vazio desde a etapa 1, devolvendo `((), ())`, e o motivo de
ele ter sido escrito antes de ter uso e exatamente este commit: a regra nova
entra aqui, isolada e com teste proprio, em vez de cair dentro de `_atacar` --
que a essa altura tem quarenta testes em cima.

A regra da SRD: atirar com um inimigo colado em voce da desvantagem.
"""

from __future__ import annotations

import pytest

from tacticore.core.actions import AttackAction
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import CombatState
from tacticore.core.queries import FONTE_INIMIGO_ADJACENTE, derive_advantage_sources
from tacticore.core.testing import make_attack, make_combatant, make_statblock, make_state

ADAGA = AttackId("adaga")
ESPADA = AttackId("espada")


def arena(
    *,
    posicoes: dict[str, tuple[int, int]],
    times: dict[str, str] | None = None,
    hp: dict[str, int] | None = None,
) -> CombatState:
    """Uma ficha com uma arma de perto e uma de longe, e quem `posicoes` disser."""
    ficha = make_statblock(
        id="ficha",
        attacks=(
            make_attack(id="espada", range_ft=5),
            make_attack(id="adaga", range_ft=20),
        ),
    )
    times = times or {}
    hp = hp or {}
    return make_state(
        statblocks=(ficha,),
        combatants=tuple(
            make_combatant(
                id=nome,
                statblock_id="ficha",
                team=times.get(nome, "herois" if nome == "a" else "viloes"),
                hp=hp.get(nome),
            )
            for nome in posicoes
        ),
        current="a",
        posicoes=posicoes,
    )


def derivar(estado: CombatState, ataque: AttackId) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return derive_advantage_sources(
        estado,
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=ataque),
    )


def test_atirar_com_inimigo_colado_da_desvantagem():
    estado = arena(posicoes={"a": (0, 0), "b": (1, 0)})
    assert derivar(estado, ADAGA) == ((), (FONTE_INIMIGO_ADJACENTE,))


def test_a_diagonal_tambem_cola():
    estado = arena(posicoes={"a": (0, 0), "b": (1, 1)})
    assert derivar(estado, ADAGA) == ((), (FONTE_INIMIGO_ADJACENTE,))


def test_atirar_de_longe_nao_da_desvantagem():
    estado = arena(posicoes={"a": (0, 0), "b": (2, 0)})
    assert derivar(estado, ADAGA) == ((), ())


def test_arma_corpo_a_corpo_nao_sofre_a_regra():
    """A regra e sobre atirar. Bater de perto com inimigo perto e o normal."""
    estado = arena(posicoes={"a": (0, 0), "b": (1, 0)})
    assert derivar(estado, ESPADA) == ((), ())


def test_aliado_colado_nao_atrapalha():
    """A SRD fala de criatura hostil. Um aliado ao lado nao estorva o tiro."""
    estado = arena(
        posicoes={"a": (0, 0), "c": (1, 0), "b": (5, 0)},
        times={"a": "herois", "c": "herois", "b": "viloes"},
    )
    assert derivar(estado, ADAGA) == ((), ())


def test_inimigo_caido_nao_atrapalha():
    """Quem esta a zero nao ameaca ninguem."""
    estado = arena(
        posicoes={"a": (0, 0), "c": (1, 0), "b": (5, 0)},
        times={"a": "herois", "c": "viloes", "b": "viloes"},
        hp={"c": 0},
    )
    assert derivar(estado, ADAGA) == ((), ())


def test_qualquer_inimigo_colado_conta_e_nao_so_o_alvo():
    """Atirar no de longe com outro colado tambem e desvantagem."""
    estado = arena(
        posicoes={"a": (0, 0), "c": (1, 0), "b": (5, 0)},
        times={"a": "herois", "c": "viloes", "b": "viloes"},
    )
    assert derivar(estado, ADAGA) == ((), (FONTE_INIMIGO_ADJACENTE,))


def test_a_propria_casa_nao_conta_como_colada():
    """Ninguem esta ao lado de si proprio -- e por isso que `is_adjacent`
    recusa a mesma casa."""
    estado = arena(posicoes={"a": (0, 0), "b": (9, 0)})
    assert derivar(estado, ADAGA) == ((), ())


def test_ataque_inexistente_nao_deriva_nada():
    """Funcao publica: quem chamar sem validar antes recebe vazio, e nao erro."""
    estado = arena(posicoes={"a": (0, 0), "b": (1, 0)})
    assert derivar(estado, AttackId("bazuca")) == ((), ())


@pytest.mark.parametrize("alcance", [5, 6, 10])
def test_o_limiar_de_a_distancia_e_uma_casa(alcance: int):
    """`range_ft > 5`. Alcance 5 e perto; qualquer coisa acima e tiro.

    Alcance 10 cair do lado "a distancia" e o desvio registrado: uma alabarda
    tem alcance 10 e e corpo a corpo. Enquanto nao houver arma de haste, o
    conjunto e o mesmo.
    """
    ficha = make_statblock(id="ficha", attacks=(make_attack(id="arma", range_ft=alcance),))
    estado = make_state(
        statblocks=(ficha,),
        combatants=(
            make_combatant(id="a", statblock_id="ficha", team="herois"),
            make_combatant(id="b", statblock_id="ficha", team="viloes"),
        ),
        current="a",
        posicoes={"a": (0, 0), "b": (1, 0)},
    )
    derivadas = derive_advantage_sources(
        estado,
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=AttackId("arma")),
    )
    esperado = ((), ()) if alcance <= 5 else ((), (FONTE_INIMIGO_ADJACENTE,))
    assert derivadas == esperado

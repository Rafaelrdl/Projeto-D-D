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
from tacticore.core.enums import Condition
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import CombatState
from tacticore.core.queries import (
    FONTE_ALCANCE_LONGO,
    FONTE_ALVO_CAIDO_LONGE,
    FONTE_ALVO_CAIDO_PERTO,
    FONTE_ATACANTE_CAIDO,
    FONTE_INIMIGO_ADJACENTE,
    derive_advantage_sources,
)
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
            make_attack(id="adaga", range_ft=20, long_range_ft=60),
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
        posicoes={"a": (0, 0), "c": (1, 0), "b": (4, 0)},
        times={"a": "herois", "c": "herois", "b": "viloes"},
    )
    assert derivar(estado, ADAGA) == ((), ())


def test_inimigo_caido_nao_atrapalha():
    """Quem esta a zero nao ameaca ninguem."""
    estado = arena(
        posicoes={"a": (0, 0), "c": (1, 0), "b": (4, 0)},
        times={"a": "herois", "c": "viloes", "b": "viloes"},
        hp={"c": 0},
    )
    assert derivar(estado, ADAGA) == ((), ())


def test_qualquer_inimigo_colado_conta_e_nao_so_o_alvo():
    """Atirar no de longe com outro colado tambem e desvantagem."""
    estado = arena(
        posicoes={"a": (0, 0), "c": (1, 0), "b": (4, 0)},
        times={"a": "herois", "c": "viloes", "b": "viloes"},
    )
    assert derivar(estado, ADAGA) == ((), (FONTE_INIMIGO_ADJACENTE,))


def test_a_propria_casa_nao_conta_como_colada():
    """Ninguem esta ao lado de si proprio -- e por isso que `is_adjacent`
    recusa a mesma casa."""
    estado = arena(posicoes={"a": (0, 0), "b": (4, 0)})
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


# --------------------------------------------------------------- caido -----


def com_caido(*, caidos: tuple[str, ...], posicoes: dict[str, tuple[int, int]]) -> CombatState:
    ficha = make_statblock(
        id="ficha",
        attacks=(
            make_attack(id="espada", range_ft=5),
            make_attack(id="adaga", range_ft=20, long_range_ft=60),
        ),
    )
    return make_state(
        statblocks=(ficha,),
        combatants=tuple(
            make_combatant(
                id=nome,
                statblock_id="ficha",
                team="herois" if nome == "a" else "viloes",
                conditions=(Condition.CAIDO,) if nome in caidos else (),
            )
            for nome in posicoes
        ),
        current="a",
        posicoes=posicoes,
    )


def test_o_caido_ataca_com_desvantagem():
    estado = com_caido(caidos=("a",), posicoes={"a": (0, 0), "b": (1, 0)})
    assert derivar(estado, ESPADA) == ((), (FONTE_ATACANTE_CAIDO,))


def test_atacar_o_caido_de_perto_da_vantagem():
    estado = com_caido(caidos=("b",), posicoes={"a": (0, 0), "b": (1, 0)})
    assert derivar(estado, ESPADA) == ((FONTE_ALVO_CAIDO_PERTO,), ())


def test_atacar_o_caido_de_longe_da_desvantagem():
    estado = com_caido(caidos=("b",), posicoes={"a": (0, 0), "b": (3, 0)})
    assert derivar(estado, ADAGA) == ((), (FONTE_ALVO_CAIDO_LONGE,))


def test_a_regra_do_caido_e_GEOMETRIA_e_nao_tipo_de_arma():
    """A leitura errada e facil e o motor tinha o campo para fazê-la.

    A SRD condiciona a vantagem a o ATACANTE estar a 1,5 m, e nao a arma ser
    corpo a corpo. Um arqueiro colado no caido tem VANTAGEM; um lanceiro de
    alcance 10 atacando de duas casas tem desvantagem. Se a implementacao
    tivesse lido `perfil.range_ft` -- que a clausula do tiro colado le logo
    acima --, os dois sairiam trocados.
    """
    colado = com_caido(caidos=("b",), posicoes={"a": (0, 0), "b": (1, 0)})
    vantagens, _ = derivar(colado, ADAGA)
    assert FONTE_ALVO_CAIDO_PERTO in vantagens, "arma de tiro colada no caido: vantagem"

    longe = com_caido(caidos=("b",), posicoes={"a": (0, 0), "b": (2, 0)})
    assert derivar(longe, ESPADA) == ((), (FONTE_ALVO_CAIDO_LONGE,))


def test_a_diagonal_conta_como_colado_para_o_caido():
    estado = com_caido(caidos=("b",), posicoes={"a": (0, 0), "b": (1, 1)})
    assert derivar(estado, ESPADA) == ((FONTE_ALVO_CAIDO_PERTO,), ())


def test_as_tres_regras_se_somam():
    """Atacante caido, alvo caido e longe, e arma de tiro com inimigo colado.

    `resolve_advantage` colapsa tudo para NORMAL quando ha fonte dos dois lados;
    o que interessa aqui e que as fontes aparecem TODAS no log, porque e o log
    que explica a rolagem.
    """
    estado = com_caido(caidos=("a", "b"), posicoes={"a": (0, 0), "c": (1, 0), "b": (4, 0)})
    estado = make_state(
        statblocks=tuple(estado.statblocks.values()),
        combatants=(
            make_combatant(
                id="a", statblock_id="ficha", team="herois", conditions=(Condition.CAIDO,)
            ),
            make_combatant(id="c", statblock_id="ficha", team="viloes"),
            make_combatant(
                id="b", statblock_id="ficha", team="viloes", conditions=(Condition.CAIDO,)
            ),
        ),
        current="a",
        posicoes={"a": (0, 0), "c": (1, 0), "b": (4, 0)},
    )
    vantagens, desvantagens = derivar(estado, ADAGA)
    assert vantagens == ()
    assert desvantagens == (
        FONTE_INIMIGO_ADJACENTE,
        FONTE_ATACANTE_CAIDO,
        FONTE_ALVO_CAIDO_LONGE,
    )


def test_quem_nao_esta_caido_nao_sofre_nada():
    estado = com_caido(caidos=(), posicoes={"a": (0, 0), "b": (1, 0)})
    assert derivar(estado, ESPADA) == ((), ())


# -------------------------------------------------------- alcance longo ----


def test_atirar_entre_o_curto_e_o_longo_da_desvantagem():
    """A divida que o repositorio assinou duas vezes e levou uma fatia para pagar."""
    estado = arena(posicoes={"a": (0, 0), "b": (6, 0)})
    assert derivar(estado, ADAGA) == ((), (FONTE_ALCANCE_LONGO,))


def test_dentro_do_alcance_curto_nao_ha_penalidade():
    estado = arena(posicoes={"a": (0, 0), "b": (4, 0)})
    assert derivar(estado, ADAGA) == ((), ())


def test_o_limiar_do_alcance_curto_e_inclusivo():
    """20 pes de alcance curto acerta a 20 sem penalidade, e a 25 com."""
    assert derivar(arena(posicoes={"a": (0, 0), "b": (4, 0)}), ADAGA) == ((), ())
    assert derivar(arena(posicoes={"a": (0, 0), "b": (5, 0)}), ADAGA) == (
        (),
        (FONTE_ALCANCE_LONGO,),
    )


def test_arma_corpo_a_corpo_nunca_sofre_penalidade_de_alcance():
    """Curto e longo iguais fazem o intervalo ser vazio -- e e certo, porque a
    essa distancia o ataque ja foi recusado por `validate`."""
    for casas in range(1, 6):
        _, desvantagens = derivar(arena(posicoes={"a": (0, 0), "b": (casas, 0)}), ESPADA)
        assert FONTE_ALCANCE_LONGO not in desvantagens

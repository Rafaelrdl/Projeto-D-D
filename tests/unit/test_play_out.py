"""O piloto automatico.

Nao e IA e nao tenta ser: escolhe sempre a primeira acao legal, que e o que um
teste de determinismo e um golden precisam. Os tres modos de falha dele sao
testados porque a alternativa e um teste que trava em vez de falhar.
"""

from __future__ import annotations

import pytest

from tacticore.core.engine import combat_result, start_combat
from tacticore.core.errors import CorruptStateError
from tacticore.core.rng import SplitMix64
from tacticore.core.testing import (
    make_attack,
    make_combatant,
    make_duelo,
    make_statblock,
    make_state,
    play_out,
)

FICHA = make_statblock(
    id="lutador",
    armor_class=10,
    max_hp=8,
    attacks=(make_attack(damage="1d6+2"),),
)


def test_o_combate_termina_e_sobra_um_time():
    catalogo, gente = make_duelo(ficha_a=FICHA, ficha_b=FICHA)
    abertura = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=8))
    estado, log = play_out(abertura.state)

    desfecho = combat_result(estado)
    assert desfecho is not None
    assert desfecho.winning_team in {"herois", "viloes"}
    assert log


def test_combate_ja_encerrado_devolve_o_estado_intacto():
    acabado = make_state(
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes", hp=0),
        )
    )
    estado, log = play_out(acabado)
    assert estado is acabado
    assert log == ()


def test_sem_acao_legal_e_combate_em_andamento_e_bug_do_motor():
    """Estado que o chamador consegue montar: o dono do turno esta caido, mas o
    time dele tem alguem de pe. O avanco normal de turno nunca produz isto."""
    travado = make_state(
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes"),
            make_combatant(id="c", team="herois"),
        ),
        current="a",
    )
    with pytest.raises(CorruptStateError, match="sem acao legal"):
        play_out(travado)


def test_o_limite_de_acoes_falha_em_vez_de_travar():
    """Um bug de regra que impeça o combate de terminar tem que virar uma
    falha legivel, e nao um processo pendurado."""
    catalogo, gente = make_duelo(ficha_a=FICHA, ficha_b=FICHA)
    abertura = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=8))
    with pytest.raises(CorruptStateError, match="nao terminou em 2 acoes"):
        play_out(abertura.state, max_actions=2)

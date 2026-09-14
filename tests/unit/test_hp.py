"""Aplicacao de dano sobre pontos de vida."""

from __future__ import annotations

import pytest

from tacticore.core.model import HitPoints
from tacticore.core.rules import apply_damage


def vida(current: int, maximum: int = 10) -> HitPoints:
    return HitPoints(current=current, maximum=maximum)


def test_dano_comum_tira_o_que_vale():
    hp, aplicado = apply_damage(vida(10), 4)
    assert hp == vida(6)
    assert (aplicado.dealt, aplicado.overkill, aplicado.dropped_to_zero) == (4, 0, False)


def test_dano_exato_derruba_sem_sobra():
    hp, aplicado = apply_damage(vida(4), 4)
    assert hp.current == 0
    assert (aplicado.dealt, aplicado.overkill, aplicado.dropped_to_zero) == (4, 0, True)


def test_vida_satura_em_zero_e_a_sobra_vai_para_o_resultado():
    """O excedente e a entrada da morte instantanea da SRD.

    Guardado agora custa um campo; recuperado depois exigiria refazer a conta
    de tras para frente a partir do log.
    """
    hp, aplicado = apply_damage(vida(3), 11)
    assert hp.current == 0
    assert aplicado.dealt == 3
    assert aplicado.overkill == 8


@pytest.mark.parametrize("amount", [0, -1, -50])
def test_dano_nao_positivo_nao_faz_nada(amount: int):
    """Ataque nao cura. Cura vai ser funcao propria, com regra propria."""
    hp, aplicado = apply_damage(vida(7), amount)
    assert hp == vida(7)
    assert (aplicado.dealt, aplicado.overkill, aplicado.dropped_to_zero) == (0, 0, False)


def test_bater_em_quem_ja_caiu_nao_derruba_de_novo():
    """Sem a distincao, o evento de queda sairia uma vez por golpe."""
    hp, aplicado = apply_damage(vida(0), 6)
    assert hp.current == 0
    assert aplicado.dealt == 0
    assert aplicado.overkill == 6
    assert aplicado.dropped_to_zero is False


def test_o_maximo_nunca_muda():
    hp, _ = apply_damage(vida(9, maximum=12), 40)
    assert hp.maximum == 12


def test_o_objeto_original_fica_intacto():
    original = vida(9)
    apply_damage(original, 9)
    assert original.current == 9


def test_dano_nunca_deixa_a_vida_negativa():
    for atual in range(0, 11):
        for dano in range(-5, 30):
            hp, aplicado = apply_damage(vida(atual), dano)
            assert hp.current >= 0
            assert aplicado.dealt >= 0
            assert aplicado.overkill >= 0


def test_a_conta_sempre_fecha():
    """`dealt + overkill` e o dano efetivo, e `dealt` e o que saiu da vida."""
    for atual in range(0, 11):
        for dano in range(0, 30):
            hp, aplicado = apply_damage(vida(atual), dano)
            assert aplicado.dealt + aplicado.overkill == dano
            assert hp.current == atual - aplicado.dealt

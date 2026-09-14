"""Bonus de ataque, bonus de dano e classificacao do resultado."""

from __future__ import annotations

import pytest

from tacticore.core.enums import Ability, AdvantageState, AttackOutcome
from tacticore.core.rng import ScriptedRng
from tacticore.core.rules import (
    attack_bonus,
    classify_attack,
    d20_check,
    damage_bonus,
    roll_d20,
)
from tacticore.core.testing import make_abilities, make_attack

GUERREIRO = make_abilities(forca=18, destreza=14)
"""FOR 18 = +4, DES 14 = +2. Dois modificadores diferentes para os testes
conseguirem distinguir qual atributo foi usado."""

PROFICIENCIA = 3


def classificar(natural: int, *, bonus: int = 0, dc: int = 15) -> AttackOutcome:
    roll, _ = roll_d20(ScriptedRng(script=(natural, natural)), AdvantageState.NORMAL)
    return classify_attack(d20_check(roll, bonus=bonus, dc=dc))


# ----------------------------------------------------------- bonus ---------


def test_ataque_soma_atributo_e_proficiencia():
    ataque = make_attack(ability=Ability.FOR, proficient=True)
    assert attack_bonus(ataque, GUERREIRO, PROFICIENCIA) == 4 + 3


def test_sem_proficiencia_so_o_atributo_entra():
    ataque = make_attack(ability=Ability.FOR, proficient=False)
    assert attack_bonus(ataque, GUERREIRO, PROFICIENCIA) == 4


def test_o_atributo_do_ataque_e_o_que_manda():
    arco = make_attack(ability=Ability.DES, proficient=True)
    assert attack_bonus(arco, GUERREIRO, PROFICIENCIA) == 2 + 3


def test_proficiencia_nunca_entra_no_dano():
    """O erro de porte de regra mais comum de 5e, e o mais silencioso:
    o dano fica alto demais o combate inteiro sem nada quebrar."""
    ataque = make_attack(ability=Ability.FOR, proficient=True)
    assert damage_bonus(ataque, GUERREIRO) == 4
    assert damage_bonus(ataque, GUERREIRO) != attack_bonus(ataque, GUERREIRO, PROFICIENCIA)


def test_dano_usa_o_mesmo_atributo_do_acerto():
    arco = make_attack(ability=Ability.DES, proficient=True)
    assert damage_bonus(arco, GUERREIRO) == 2


def test_atributo_fraco_da_bonus_negativo_nos_dois():
    fraco = make_abilities(forca=6)
    ataque = make_attack(ability=Ability.FOR, proficient=False)
    assert attack_bonus(ataque, fraco, PROFICIENCIA) == -2
    assert damage_bonus(ataque, fraco) == -2


# ------------------------------------------------------ classificacao ------


def test_vinte_natural_acerta_qualquer_armadura():
    assert classificar(20, bonus=0, dc=30) is AttackOutcome.CRITICAL_HIT


def test_um_natural_erra_com_qualquer_bonus():
    assert classificar(1, bonus=15, dc=5) is AttackOutcome.CRITICAL_MISS


@pytest.mark.parametrize(
    ("natural", "bonus", "dc", "esperado"),
    [
        (15, 0, 15, AttackOutcome.HIT),  # empate acerta
        (14, 0, 15, AttackOutcome.MISS),
        (10, 5, 15, AttackOutcome.HIT),
        (10, 4, 15, AttackOutcome.MISS),
        (19, 0, 30, AttackOutcome.MISS),  # 19 nao tem automatismo
        (2, 20, 5, AttackOutcome.HIT),  # 2 tambem nao
    ],
)
def test_resultado_normal_e_so_a_conta(natural: int, bonus: int, dc: int, esperado: AttackOutcome):
    assert classificar(natural, bonus=bonus, dc=dc) is esperado


def test_falha_critica_e_distinta_de_erro_comum():
    """Hoje o efeito e o mesmo. Manter separado e o que permite a primeira
    mecanica de 1 natural entrar sem mexer nos testes que afirmam MISS."""
    assert classificar(1, dc=30) is not classificar(5, dc=30)


def test_o_natural_do_critico_e_o_dado_escolhido():
    """Um 20 que a desvantagem jogou fora nao pode virar critico."""
    roll, _ = roll_d20(ScriptedRng(script=(3, 20)), AdvantageState.DISADVANTAGE)
    assert classify_attack(d20_check(roll, bonus=0, dc=5)) is AttackOutcome.MISS


def test_a_vantagem_pode_transformar_erro_em_critico():
    """O espelho do teste acima, para provar que o indice escolhido e usado
    nos dois sentidos e nao so por acaso."""
    roll, _ = roll_d20(ScriptedRng(script=(3, 20)), AdvantageState.ADVANTAGE)
    assert classify_attack(d20_check(roll, bonus=0, dc=5)) is AttackOutcome.CRITICAL_HIT


def test_todo_resultado_possivel_e_alcancavel():
    """Enum com membro inalcancavel seria enum mentindo sobre o dominio."""
    alcancados = {
        classificar(20, dc=30),
        classificar(1, dc=5),
        classificar(15, dc=15),
        classificar(2, dc=30),
    }
    assert alcancados == set(AttackOutcome)

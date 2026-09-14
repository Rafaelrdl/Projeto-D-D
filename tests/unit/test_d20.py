"""Modificador, vantagem e o teste de d20 generico."""

from __future__ import annotations

import pytest

from tacticore.core.enums import Ability, AdvantageState
from tacticore.core.rng import ScriptedRng, SplitMix64, position
from tacticore.core.rules import (
    D20_FACES,
    ability_modifier,
    ability_score,
    d20_check,
    resolve_advantage,
    roll_d20,
)
from tacticore.core.testing import make_abilities

# -------------------------------------------------------- modificador ------

# A tabela inteira de 1 a 30, escrita a mao. Uma tabela conferida contra a
# propria formula nao testaria nada; esta e a da SRD.
MODIFICADORES = {
    1: -5, 2: -4, 3: -4, 4: -3, 5: -3, 6: -2, 7: -2, 8: -1, 9: -1, 10: 0,
    11: 0, 12: 1, 13: 1, 14: 2, 15: 2, 16: 3, 17: 3, 18: 4, 19: 4, 20: 5,
    21: 5, 22: 6, 23: 6, 24: 7, 25: 7, 26: 8, 27: 8, 28: 9, 29: 9, 30: 10,
}  # fmt: skip


@pytest.mark.parametrize(("valor", "esperado"), sorted(MODIFICADORES.items()))
def test_modificador_de_atributo(valor: int, esperado: int):
    assert ability_modifier(valor) == esperado


def test_modificador_arredonda_para_baixo_tambem_em_negativo():
    """`//` em Python arredonda para baixo, que e o que a SRD pede.

    Atributo 1 da -5, e nao -4. Em linguagem que trunca em direcao ao zero,
    este e o bug classico de porte de regra.
    """
    assert ability_modifier(1) == -5
    assert ability_modifier(3) == -4


@pytest.mark.parametrize(
    ("ability", "esperado"),
    [
        (Ability.FOR, 18),
        (Ability.DES, 14),
        (Ability.CON, 13),
        (Ability.INT, 8),
        (Ability.SAB, 12),
        (Ability.CAR, 10),
    ],
)
def test_atributo_pela_sigla(ability: Ability, esperado: int):
    abilities = make_abilities(
        forca=18, destreza=14, constituicao=13, inteligencia=8, sabedoria=12, carisma=10
    )
    assert ability_score(abilities, ability) == esperado


def test_toda_sigla_tem_campo():
    """Enum e dataclass podem sair de sincronia sem isto."""
    abilities = make_abilities()
    for ability in Ability:
        assert isinstance(ability_score(abilities, ability), int)


# ----------------------------------------------------------- vantagem ------


@pytest.mark.parametrize(
    ("vantagem", "desvantagem", "esperado"),
    [
        ((), (), AdvantageState.NORMAL),
        (("flanqueando",), (), AdvantageState.ADVANTAGE),
        ((), ("cegado",), AdvantageState.DISADVANTAGE),
        # Uma de cada lado cancela, nao importa quantas.
        (("flanqueando",), ("cegado",), AdvantageState.NORMAL),
        (("a", "b", "c"), ("x",), AdvantageState.NORMAL),
        (("a",), ("x", "y", "z"), AdvantageState.NORMAL),
        (("a", "b"), (), AdvantageState.ADVANTAGE),
        ((), ("x", "y"), AdvantageState.DISADVANTAGE),
    ],
)
def test_vantagem_e_binaria_e_nao_acumula(
    vantagem: tuple[str, ...], desvantagem: tuple[str, ...], esperado: AdvantageState
):
    assert resolve_advantage(vantagem, desvantagem) is esperado


# --------------------------------------------------------- quadro fixo -----


@pytest.mark.parametrize("estado", list(AdvantageState))
def test_sempre_dois_dados_qualquer_que_seja_o_estado(estado: AdvantageState):
    """O quadro fixo e contrato: sem ele, ligar vantagem desloca o stream."""
    _, depois = roll_d20(SplitMix64(seed=7), estado)
    assert position(depois) == 2


@pytest.mark.parametrize("estado", list(AdvantageState))
def test_o_par_rolado_e_o_mesmo_em_qualquer_estado(estado: AdvantageState):
    """A vantagem escolhe entre os dados; ela nao muda quais dados sairam."""
    roll, _ = roll_d20(SplitMix64(seed=99), estado)
    referencia, _ = roll_d20(SplitMix64(seed=99), AdvantageState.NORMAL)
    assert roll.pair == referencia.pair


def test_normal_vale_o_primeiro_dado():
    roll, _ = roll_d20(ScriptedRng(script=(7, 20)), AdvantageState.NORMAL)
    assert roll.natural == 7
    assert roll.chosen_index == 0
    assert roll.pair == (7, 20)


def test_vantagem_pega_o_maior():
    roll, _ = roll_d20(ScriptedRng(script=(7, 20)), AdvantageState.ADVANTAGE)
    assert roll.natural == 20
    assert roll.chosen_index == 1


def test_desvantagem_pega_o_menor():
    roll, _ = roll_d20(ScriptedRng(script=(7, 20)), AdvantageState.DISADVANTAGE)
    assert roll.natural == 7
    assert roll.chosen_index == 0


def test_empate_escolhe_o_primeiro_dado():
    """Criterio fixo: empate nao pode depender de ordem de comparacao."""
    for estado in AdvantageState:
        roll, _ = roll_d20(ScriptedRng(script=(11, 11)), estado)
        assert roll.chosen_index == 0


def test_o_natural_e_o_dado_escolhido_e_nao_o_descartado():
    """Um 20 que a desvantagem jogou fora nao e 20 natural."""
    roll, _ = roll_d20(ScriptedRng(script=(3, 20)), AdvantageState.DISADVANTAGE)
    assert roll.natural == 3
    assert 20 in roll.pair


def test_o_descartado_continua_registrado():
    """Ele e a prova, no log, de que o quadro fixo foi respeitado."""
    roll, _ = roll_d20(ScriptedRng(script=(3, 20)), AdvantageState.NORMAL)
    assert roll.pair == (3, 20)


# ------------------------------------------------- enumeracao exaustiva -----


def _acertos(estado: AdvantageState, alvo: int) -> int:
    """Quantos dos 400 pares equiprovaveis atingem `alvo`, neste estado."""
    total = 0
    for a in range(1, D20_FACES + 1):
        for b in range(1, D20_FACES + 1):
            roll, _ = roll_d20(ScriptedRng(script=(a, b)), estado)
            total += roll.natural >= alvo
    return total


@pytest.mark.parametrize("alvo", range(1, D20_FACES + 1))
def test_vantagem_nunca_piora_e_desvantagem_nunca_melhora(alvo: int):
    """Enumeracao dos 400 pares, e nao amostragem.

    Um teste estatistico aqui seria instavel e ainda por cima mais fraco: com
    400 casos da para provar a propriedade, em vez de estima-la.
    """
    normal = _acertos(AdvantageState.NORMAL, alvo)
    assert _acertos(AdvantageState.ADVANTAGE, alvo) >= normal
    assert _acertos(AdvantageState.DISADVANTAGE, alvo) <= normal


@pytest.mark.parametrize("alvo", range(2, D20_FACES + 1))
def test_vantagem_melhora_de_verdade_quando_ha_o_que_melhorar(alvo: int):
    """Para alvo 1 todo mundo acerta sempre; de 2 a 20 a vantagem tem que valer."""
    assert _acertos(AdvantageState.ADVANTAGE, alvo) > _acertos(AdvantageState.NORMAL, alvo)
    assert _acertos(AdvantageState.DISADVANTAGE, alvo) < _acertos(AdvantageState.NORMAL, alvo)


# --------------------------------------------------------- d20_check -------


@pytest.mark.parametrize(
    ("natural", "bonus", "dc", "esperado"),
    [
        (10, 5, 15, True),  # empate passa
        (10, 4, 15, False),
        (1, 0, 1, True),
        (20, 0, 21, False),  # sem automatismo: 20 natural nao acerta sozinho
        (1, 30, 15, True),  # sem automatismo: 1 natural nao erra sozinho
    ],
)
def test_teste_de_d20_nao_tem_automatismo(natural: int, bonus: int, dc: int, esperado: bool):
    """Automatismo de 20 e 1 e regra de ATAQUE, e mora em `classify_attack`.

    Deixar isto generico e o que permite salvaguarda e teste de pericia
    entrarem como funcao nova, e nao como `if` dentro de algo ja testado.
    """
    roll, _ = roll_d20(ScriptedRng(script=(natural, natural)), AdvantageState.NORMAL)
    resultado = d20_check(roll, bonus=bonus, dc=dc)
    assert resultado.success is esperado


def test_o_resultado_guarda_a_conta_aberta():
    roll, _ = roll_d20(ScriptedRng(script=(13, 13)), AdvantageState.NORMAL)
    resultado = d20_check(roll, bonus=4, dc=15)
    assert (resultado.natural, resultado.bonus, resultado.total, resultado.dc) == (13, 4, 17, 15)

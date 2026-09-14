"""Rolagem de dano e critico.

Quase tudo aqui e testado com fita roteirizada em vez de seed: a pergunta nao e
"que numero saiu", e sim "quantos dados sairam, nesta ordem, com este fixo".
"""

from __future__ import annotations

import pytest

from tacticore.core.dice import (
    DamageExpr,
    DiceTerm,
    expand_crit,
    parse_dice,
    roll_damage,
)
from tacticore.core.rng import ScriptedRng, SplitMix64, position


def fita(*valores: int) -> ScriptedRng:
    return ScriptedRng(script=valores)


# ------------------------------------------------------------ expand_crit ---


def test_critico_dobra_a_contagem_de_dados():
    assert expand_crit(parse_dice("1d8")).terms == (DiceTerm(count=2, faces=8),)


def test_critico_nao_dobra_o_fixo():
    """A regra e "dobra os dados de dano", nao "dobra o dano"."""
    assert expand_crit(parse_dice("2d6+3")).flat == 3


def test_critico_dobra_cada_termo_separadamente():
    expandida = expand_crit(parse_dice("1d8+2d6"))
    assert [(t.count, t.faces) for t in expandida.terms] == [(2, 8), (4, 6)]


def test_termo_marcado_para_nao_dobrar_fica_intacto():
    expr = DamageExpr(
        terms=(
            DiceTerm(count=1, faces=8),
            DiceTerm(count=1, faces=6, doubles_on_crit=False),
        ),
        flat=2,
    )
    expandida = expand_crit(expr)
    assert expandida.terms[0].count == 2
    assert expandida.terms[1].count == 1
    assert expandida.terms[1].doubles_on_crit is False


def test_expandir_nao_muda_a_expressao_original():
    expr = parse_dice("1d8")
    expand_crit(expr)
    assert expr.terms[0].count == 1


def test_expandir_expressao_sem_dados_nao_faz_nada():
    assert expand_crit(parse_dice("3")) == DamageExpr(terms=(), flat=3)


# ------------------------------------------------------------ roll_damage ---


def test_ordem_canonica_esquerda_para_direita():
    """`1d8+1d6+3`: primeiro o d8, depois o d6. A ordem e contrato."""
    roll, _ = roll_damage(fita(7, 4), parse_dice("1d8+1d6+3"), ability_bonus=0, critical=False)
    assert [(d.faces, d.value) for d in roll.dice] == [(8, 7), (6, 4)]
    assert roll.total == 7 + 4 + 3


def test_no_critico_os_extras_saem_junto_do_termo_e_nao_no_fim():
    """`1d8+1d6` critico consome d8, d8, d6, d6 -- nesta ordem."""
    roll, _ = roll_damage(fita(8, 1, 6, 2), parse_dice("1d8+1d6"), ability_bonus=0, critical=True)
    assert [(d.faces, d.value, d.from_crit) for d in roll.dice] == [
        (8, 8, False),
        (8, 1, True),
        (6, 6, False),
        (6, 2, True),
    ]


def test_critico_consome_o_dobro_de_dados():
    expr = parse_dice("2d6+4")
    _, normal = roll_damage(SplitMix64(seed=1), expr, ability_bonus=0, critical=False)
    _, critico = roll_damage(SplitMix64(seed=1), expr, ability_bonus=0, critical=True)
    assert position(normal) == 2
    assert position(critico) == 4


def test_modificador_de_atributo_entra_uma_vez_mesmo_no_critico():
    roll, _ = roll_damage(fita(5, 5), parse_dice("1d8"), ability_bonus=3, critical=True)
    assert roll.ability_bonus == 3
    assert roll.total == 5 + 5 + 3


def test_fixo_entra_uma_vez_so_no_critico():
    roll, _ = roll_damage(fita(1, 1), parse_dice("1d8+3"), ability_bonus=0, critical=True)
    assert roll.flat == 3
    assert roll.total == 1 + 1 + 3


def test_term_index_aponta_para_a_expressao_original():
    """Depois de expandir, o log ainda tem que mapear no que o autor escreveu."""
    roll, _ = roll_damage(fita(1, 2, 3, 4), parse_dice("1d8+1d6"), ability_bonus=0, critical=True)
    assert [d.term_index for d in roll.dice] == [0, 0, 1, 1]


def test_fora_do_critico_nenhum_dado_vem_do_critico():
    roll, _ = roll_damage(fita(3, 3), parse_dice("2d6"), ability_bonus=0, critical=False)
    assert all(not d.from_crit for d in roll.dice)
    assert roll.critical is False


@pytest.mark.parametrize(
    ("notacao", "bonus", "valores"),
    [
        ("1d8+3", 2, (6,)),
        ("2d6", -1, (3, 4)),
        ("1d4-3", 0, (1,)),
        ("3", 4, ()),
    ],
)
def test_total_e_sempre_a_soma_das_partes(notacao: str, bonus: int, valores: tuple[int, ...]):
    """A identidade que faz a conta decomposta do log fechar.

    Se `total` tivesse piso em zero, ela quebraria justamente nos casos em que
    alguem for conferir na mao.
    """
    expr = parse_dice(notacao)
    roll, _ = roll_damage(fita(*valores), expr, ability_bonus=bonus, critical=False)
    assert roll.total == sum(d.value for d in roll.dice) + roll.flat + roll.ability_bonus


def test_total_pode_ser_negativo():
    """O piso em zero mora em `apply_damage`, e num lugar so."""
    roll, _ = roll_damage(fita(1), parse_dice("1d4-3"), ability_bonus=-2, critical=False)
    assert roll.total == 1 - 3 - 2


def test_dano_so_de_fixo_nao_consome_o_rng():
    roll, depois = roll_damage(SplitMix64(seed=9), parse_dice("3"), ability_bonus=1, critical=False)
    assert roll.dice == ()
    assert roll.total == 4
    assert position(depois) == 0


def test_rng_avanca_exatamente_um_por_dado():
    roll, depois = roll_damage(
        SplitMix64(seed=3), parse_dice("3d6+1d4"), ability_bonus=0, critical=False
    )
    assert len(roll.dice) == 4
    assert position(depois) == 4


def test_mesma_fita_mesmo_resultado():
    expr = parse_dice("2d6+2")
    a, _ = roll_damage(fita(3, 5), expr, ability_bonus=1, critical=False)
    b, _ = roll_damage(fita(3, 5), expr, ability_bonus=1, critical=False)
    assert a == b

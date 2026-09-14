"""A gramatica de dados e a fronteira entre o motor e dado escrito por humano.

Cada forma recusada aqui esta recusada de proposito e com nome. Uma gramatica
tolerante aceitaria `"1d8lixo"` como `1d8` e o erro so apareceria como dano
estranho, meses depois, sem nada apontando para a origem.
"""

from __future__ import annotations

import pytest

from tacticore.core.dice import DamageExpr, DiceTerm, parse_dice
from tacticore.core.errors import DiceSyntaxError

ACEITOS = [
    ("1d8", DamageExpr(terms=(DiceTerm(count=1, faces=8),), flat=0)),
    ("d8", DamageExpr(terms=(DiceTerm(count=1, faces=8),), flat=0)),
    ("D8", DamageExpr(terms=(DiceTerm(count=1, faces=8),), flat=0)),
    ("2d6", DamageExpr(terms=(DiceTerm(count=2, faces=6),), flat=0)),
    ("1d8+3", DamageExpr(terms=(DiceTerm(count=1, faces=8),), flat=3)),
    ("1d8-1", DamageExpr(terms=(DiceTerm(count=1, faces=8),), flat=-1)),
    ("3", DamageExpr(terms=(), flat=3)),
    (
        " 1D8 + 3 ",
        DamageExpr(terms=(DiceTerm(count=1, faces=8),), flat=3),
    ),
    (
        "1d8+1d4+2",
        DamageExpr(
            terms=(DiceTerm(count=1, faces=8), DiceTerm(count=1, faces=4)),
            flat=2,
        ),
    ),
    (
        "2d6+3-1",
        DamageExpr(terms=(DiceTerm(count=2, faces=6),), flat=2),
    ),
    (
        "100d1000",
        DamageExpr(terms=(DiceTerm(count=100, faces=1000),), flat=0),
    ),
]

RECUSADOS = [
    ("", "vazia"),
    ("   ", "vazia"),
    ("0d6", "quantidade de dados fora"),
    ("101d6", "quantidade de dados fora"),
    ("1d0", "faces fora"),
    ("1d1", "faces fora"),
    ("1d1001", "faces fora"),
    ("1d8+", "sem termo depois"),
    ("1d8-", "sem termo depois"),
    ("+1d8", "nao pode comecar com sinal"),
    ("-3", "nao pode comecar com sinal"),
    ("2d6-1d4", "termo de dados negativo"),
    ("abc", "nao entendi o termo"),
    ("1d8+abc", "nao entendi o termo"),
    ("d", "nao entendi o termo"),
    ("1d8lixo", "esperava . ou ."),
    ("1d8*2", "esperava . ou ."),
    ("1dd8", "esperava . ou ."),
    # Espaco vale nas pontas e em volta do operador, e so ali. Sem isso,
    # "1d8 3" viraria "1d83": um d83 silencioso.
    ("1d8 3", "esperava . ou ."),
    ("1 d8", "esperava . ou ."),
]


@pytest.mark.parametrize(("texto", "esperado"), ACEITOS, ids=[t for t, _ in ACEITOS])
def test_notacao_aceita(texto: str, esperado: DamageExpr):
    assert parse_dice(texto) == esperado


@pytest.mark.parametrize(("texto", "motivo"), RECUSADOS, ids=[t or "vazio" for t, _ in RECUSADOS])
def test_notacao_recusada(texto: str, motivo: str):
    with pytest.raises(DiceSyntaxError, match=motivo):
        parse_dice(texto)


def test_erro_cita_a_notacao_original_e_nao_a_normalizada():
    """Mensagem tem que apontar para o que o autor escreveu, espacos e tudo."""
    with pytest.raises(DiceSyntaxError, match=r"' 1d8 \+ '"):
        parse_dice(" 1d8 + ")


def test_ordem_dos_termos_e_preservada():
    expr = parse_dice("1d4+2d6+1d8")
    assert [(t.count, t.faces) for t in expr.terms] == [(1, 4), (2, 6), (1, 8)]


def test_termos_iguais_nao_sao_agrupados():
    """`1d6+1d6` sao dois termos: no critico cada um dobra por conta propria."""
    expr = parse_dice("1d6+1d6")
    assert len(expr.terms) == 2
    assert expr.terms[0] == expr.terms[1]


def test_fixos_multiplos_somam_num_campo_so():
    assert parse_dice("1d8+2+3").flat == 5


def test_fixo_pode_ficar_negativo():
    """O piso em zero mora em `apply_damage`, nao aqui: a expressao e crua."""
    assert parse_dice("1d4-3").flat == -3


def test_termo_nasce_dobrando_no_critico():
    assert parse_dice("1d8").terms[0].doubles_on_crit is True


def test_expressao_e_imutavel():
    expr = parse_dice("1d8+3")
    with pytest.raises(AttributeError):
        expr.flat = 99  # type: ignore[misc]

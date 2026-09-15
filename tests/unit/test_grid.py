"""Distancia e adjacencia na grade.

Sao duas funcoes de quatro inteiros, e por isso da para varrer o espaco inteiro
em vez de escolher casos. O que se prova aqui e o que a geometria do jogo vai
assumir em toda regra de alcance daqui para frente.
"""

from __future__ import annotations

import pytest

from tacticore.core.model import Position
from tacticore.core.rules import PES_POR_CASA, distance_ft, is_adjacent


def casa(x: int, y: int) -> Position:
    return Position(x=x, y=y)


# ----------------------------------------------------------- distancia -----


@pytest.mark.parametrize(
    ("origem", "destino", "pes"),
    [
        (casa(0, 0), casa(0, 0), 0),
        (casa(0, 0), casa(1, 0), 5),
        (casa(0, 0), casa(0, 1), 5),
        # A diagonal custa o mesmo que a reta: e a regra de grade da SRD.
        (casa(0, 0), casa(1, 1), 5),
        (casa(0, 0), casa(3, 0), 15),
        (casa(0, 0), casa(3, 3), 15),
        # O maior eixo manda: andar 3 para o lado e 2 para cima custa 3 casas.
        (casa(0, 0), casa(3, 2), 15),
        (casa(0, 0), casa(-2, 0), 10),
        (casa(-3, -4), casa(1, 1), 25),
    ],
)
def test_distancia_e_o_maior_eixo_vezes_cinco(origem: Position, destino: Position, pes: int):
    assert distance_ft(origem, destino) == pes


def test_a_diagonal_nao_custa_mais_que_a_reta():
    """A aproximacao que permite toda a geometria do jogo ser inteira.

    Sem ela, a hipotenusa de 1x1 seria 7,07 pes -- e um `float` entraria no
    projeto pela porta de tras, num calculo que alimenta comparacao de alcance.
    """
    assert distance_ft(casa(0, 0), casa(1, 1)) == distance_ft(casa(0, 0), casa(1, 0))


def test_distancia_e_simetrica():
    for x in range(-3, 4):
        for y in range(-3, 4):
            assert distance_ft(casa(0, 0), casa(x, y)) == distance_ft(casa(x, y), casa(0, 0))


def test_distancia_nunca_e_negativa_nem_fracionaria():
    for x in range(-4, 5):
        for y in range(-4, 5):
            pes = distance_ft(casa(0, 0), casa(x, y))
            assert isinstance(pes, int)
            assert pes >= 0
            assert pes % PES_POR_CASA == 0


def test_so_a_mesma_casa_tem_distancia_zero():
    for x in range(-2, 3):
        for y in range(-2, 3):
            zero = distance_ft(casa(0, 0), casa(x, y)) == 0
            assert zero == (x == 0 and y == 0)


def test_vale_a_desigualdade_triangular():
    """Chebyshev e metrica de verdade; alcance conta com isso."""
    pontos = [casa(x, y) for x in range(-2, 3) for y in range(-2, 3)]
    for a in pontos:
        for b in pontos:
            for c in pontos:
                assert distance_ft(a, c) <= distance_ft(a, b) + distance_ft(b, c)


# ---------------------------------------------------------- adjacencia -----


def test_a_mesma_casa_nao_e_adjacente_a_si_mesma():
    """Ninguem esta ao lado de si proprio.

    A unica pergunta que usa adjacencia -- "ha inimigo colado em mim?" -- nunca
    pode responder sim por causa do proprio ator.
    """
    assert is_adjacent(casa(2, 2), casa(2, 2)) is False


@pytest.mark.parametrize(
    ("destino", "adjacente"),
    [
        (casa(1, 0), True),
        (casa(-1, 0), True),
        (casa(0, 1), True),
        (casa(1, 1), True),
        (casa(-1, -1), True),
        (casa(2, 0), False),
        (casa(2, 2), False),
        (casa(1, 2), False),
    ],
)
def test_adjacencia_inclui_a_diagonal(destino: Position, adjacente: bool):
    assert is_adjacent(casa(0, 0), destino) is adjacente


def test_toda_casa_tem_oito_vizinhas():
    centro = casa(0, 0)
    vizinhas = [
        casa(x, y) for x in range(-2, 3) for y in range(-2, 3) if is_adjacent(centro, casa(x, y))
    ]
    assert len(vizinhas) == 8


def test_adjacencia_e_simetrica():
    for x in range(-2, 3):
        for y in range(-2, 3):
            assert is_adjacent(casa(0, 0), casa(x, y)) == is_adjacent(casa(x, y), casa(0, 0))


def test_adjacente_e_exatamente_uma_casa_de_distancia():
    for x in range(-3, 4):
        for y in range(-3, 4):
            destino = casa(x, y)
            esperado = destino != casa(0, 0) and distance_ft(casa(0, 0), destino) == PES_POR_CASA
            assert is_adjacent(casa(0, 0), destino) is esperado

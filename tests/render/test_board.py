"""O tabuleiro.

A trava que importa aqui e a primeira: **mover um combatente uma casa muda o
desenho.** Um `board` que ignorasse a posicao e devolvesse a grade vazia
passaria em qualquer teste de "nao estoura", de "tem legenda" e de "tem o
numero certo de linhas" -- e e exatamente esse o bug que um desenho errado
teria, porque um desenho errado continua parecendo um desenho.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from tacticore.core.enums import Condition
from tacticore.core.model import CombatState, Position
from tacticore.core.testing import make_combatant, make_statblock, make_state
from tacticore.render.board import CAIDO, VAZIA, board


def arena(
    *,
    posicoes: dict[str, tuple[int, int]] | None = None,
    hp_b: int = 10,
    conditions_a: tuple[Condition, ...] = (),
) -> CombatState:
    return make_state(
        statblocks=(make_statblock(id="ficha", max_hp=10),),
        combatants=(
            make_combatant(id="a", statblock_id="ficha", team="herois", conditions=conditions_a),
            make_combatant(id="b", statblock_id="ficha", team="viloes", hp=hp_b),
        ),
        current="a",
        posicoes=posicoes or {"a": (0, 0), "b": (2, 0)},
    )


def desenho(state: CombatState) -> tuple[str, ...]:
    """So a grade, sem a legenda: e nela que a posicao tem que aparecer."""
    linhas = board(state)
    return linhas[: linhas.index("")]


# ----------------------------------------------- a trava que importa -------


def test_andar_uma_casa_muda_o_desenho():
    perto = arena(posicoes={"a": (0, 0), "b": (2, 0)})
    longe = arena(posicoes={"a": (0, 0), "b": (3, 0)})
    assert desenho(perto) != desenho(longe)


def test_andar_uma_casa_no_outro_eixo_tambem_muda():
    """Sem este, um desenho que so olhasse `x` passaria no de cima."""
    horizontal = arena(posicoes={"a": (0, 0), "b": (2, 0)})
    vertical = arena(posicoes={"a": (0, 0), "b": (0, 2)})
    assert desenho(horizontal) != desenho(vertical)


def test_o_glifo_esta_na_casa_certa():
    """Diferenca nao basta: dois desenhos podem diferir pelo motivo errado."""
    linhas = desenho(arena(posicoes={"a": (0, 0), "b": (2, 0)}))
    # Cabecalho, depois y=-1, y=0, y=1. A linha de y=0 leva os dois glifos.
    assert linhas[2].split() == ["0", VAZIA, "1", VAZIA, "2", VAZIA]


# ------------------------------------------------------ o recorte ----------


def test_a_grade_tem_uma_casa_de_folga_em_volta():
    linhas = desenho(arena(posicoes={"a": (0, 0), "b": (1, 0)}))
    assert linhas[0].split() == ["-1", "0", "1", "2"]
    assert len(linhas) == 1 + 3, "y vai de -1 a 1"


def test_a_grade_acompanha_quem_se_afasta():
    linhas = desenho(arena(posicoes={"a": (0, 0), "b": (9, 0)}))
    assert linhas[0].split()[-1] == "10"


def test_coordenada_negativa_aparece_com_sinal():
    """A narracao imprime `(-7,3)`; achar essa casa no desenho e o servico."""
    linhas = desenho(arena(posicoes={"a": (-7, 3), "b": (-5, 3)}))
    assert "-8" in linhas[0].split()
    assert linhas[1].split()[0] == "2"


# ---------------------------------------------------------- quem caiu ------


def test_quem_esta_caido_aparece_com_o_glifo_proprio():
    """Ele continua ocupando a casa: um tabuleiro que o escondesse mentiria
    sobre o que bloqueia passagem."""
    linhas = desenho(arena(hp_b=0))
    assert CAIDO in linhas[2].split()


def test_quem_esta_caido_aparece_assim_na_legenda_tambem():
    legenda = board(arena(hp_b=0))[-1]
    assert legenda.startswith(CAIDO)
    assert "0/10 hp" in legenda


# ----------------------------------------------------------- a legenda -----


def test_a_legenda_segue_a_ordem_de_iniciativa():
    linhas = board(arena())
    legenda = linhas[linhas.index("") + 1 :]
    assert [linha.split()[1] for linha in legenda] == list(arena().turn_order.order)


def test_a_legenda_traz_time_e_vida():
    legenda = board(arena())[-2]
    assert "herois" in legenda
    assert "10/10 hp" in legenda


def test_a_legenda_traz_as_condicoes():
    legenda = board(arena(conditions_a=(Condition.CAIDO,)))[-2]
    assert "caido" in legenda


def test_sem_condicao_a_legenda_nao_ganha_sobra():
    """Uma tupla vazia nao pode virar espaco pendurado no fim da linha."""
    legenda = board(arena())[-2]
    assert legenda == legenda.rstrip()


# -------------------------------------------------------------- forma ------


def test_nenhuma_linha_tem_quebra_dentro():
    for linha in board(arena()):
        assert "\n" not in linha


def test_o_tabuleiro_e_puro():
    estado = arena()
    antes = replace(estado)
    board(estado)
    assert estado == antes


@pytest.mark.parametrize("quantos", [1, 2, 9, 10])
def test_o_glifo_e_sempre_um_caractere(quantos: int):
    """Cela de largura variavel desalinharia a grade inteira a partir do
    decimo combatente -- e o alfabeto continua depois do 9 por isso."""
    estado = make_state(
        statblocks=(make_statblock(id="ficha"),),
        combatants=tuple(
            make_combatant(id=f"c{i}", statblock_id="ficha", team="herois") for i in range(quantos)
        ),
        current="c0",
    )
    linhas = board(estado)
    legenda = linhas[linhas.index("") + 1 :]
    assert all(len(linha.split()[0]) == 1 for linha in legenda)


def test_combatentes_na_mesma_casa_nao_estouram_o_desenho():
    """`make_state` permite o estado esquisito de proposito, e o desenho nao e
    quem deve reprovar dois ocupantes: quem reprova e a invariante de carga."""
    estado = make_state(
        statblocks=(make_statblock(id="ficha"),),
        combatants=(
            make_combatant(id="a", statblock_id="ficha", team="herois"),
            make_combatant(id="b", statblock_id="ficha", team="viloes"),
        ),
        current="a",
        posicoes={"a": (0, 0), "b": (0, 0)},
    )
    assert board(estado)


def test_a_posicao_lida_e_a_do_combatente_e_nao_a_da_ordem():
    """Um `board` que indexasse `turn_order.order` para achar a posicao daria
    o mesmo desenho com os dois trocados de lugar."""
    a_esquerda = arena(posicoes={"a": (0, 0), "b": (2, 0)})
    trocados = replace(
        a_esquerda,
        combatants={
            "a": replace(a_esquerda.combatants["a"], position=Position(x=2, y=0)),
            "b": replace(a_esquerda.combatants["b"], position=Position(x=0, y=0)),
        },
    )
    assert desenho(a_esquerda) != desenho(trocados)

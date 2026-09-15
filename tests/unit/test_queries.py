"""As perguntas de leitura sobre o estado.

Parecem triviais demais para ter teste, e sao exatamente as que nao podem
errar: "esta de pe" e consultado por toda decisao do motor, e o dia em que
cair deixar de ser `hp > 0` e o dia em que estes testes valem o que custaram.
"""

from __future__ import annotations

import pytest

from tacticore.core.errors import CorruptStateError
from tacticore.core.ids import CreatureId, StatblockId
from tacticore.core.model import Combatant, HitPoints, Position
from tacticore.core.queries import (
    combatant_of,
    conscious_teams,
    is_conscious,
    statblock_of,
)
from tacticore.core.testing import make_combatant, make_statblock, make_state


@pytest.mark.parametrize(("atual", "de_pe"), [(10, True), (1, True), (0, False)])
def test_de_pe_e_ter_vida(atual: int, de_pe: bool):
    assert is_conscious(make_combatant(hp=atual)) is de_pe


def test_combatente_por_id():
    estado = make_state(combatants=(make_combatant(id="a"), make_combatant(id="b")))
    encontrado = combatant_of(estado, CreatureId("b"))
    assert encontrado is not None
    assert encontrado.id == "b"


def test_combatente_desconhecido_devolve_none():
    """`None` e nao excecao: perguntar por um id que veio de fora e legitimo,
    e quem chama transforma isso na rejeicao certa."""
    assert combatant_of(make_state(), CreatureId("ninguem")) is None


def test_ficha_de_um_participante():
    estado = make_state(
        statblocks=(make_statblock(id="goblin", name="Goblin"),),
        combatants=(make_combatant(id="g1", statblock_id="goblin"),),
    )
    assert statblock_of(estado, CreatureId("g1")).name == "Goblin"


def test_ficha_de_quem_nao_participa_e_bug_do_motor():
    """Excecao e nao rejeicao: perguntar a ficha de quem nao esta no combate so
    acontece por bug nosso, e rejeitar esconderia o estrago."""
    with pytest.raises(CorruptStateError, match="nao participa"):
        statblock_of(make_state(), CreatureId("ninguem"))


def test_combatente_apontando_para_ficha_inexistente_e_bug_do_motor():
    quebrado = make_state(
        statblocks=(make_statblock(id="goblin"),),
        combatants=(
            Combatant(
                id=CreatureId("g1"),
                statblock_id=StatblockId("dragao"),
                team="inimigos",
                hp=HitPoints(current=1, maximum=1),
                budget=make_combatant().budget,
                position=Position(x=0, y=0),
                conditions=(),
            ),
        ),
    )
    with pytest.raises(CorruptStateError, match="ficha inexistente"):
        statblock_of(quebrado, CreatureId("g1"))


def test_times_de_pe():
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes"),
        )
    )
    assert conscious_teams(estado) == ("herois", "viloes")


def test_time_inteiro_caido_sai_da_lista():
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes", hp=0),
        )
    )
    assert conscious_teams(estado) == ("herois",)


def test_todo_mundo_caido_nao_deixa_time_nenhum():
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes", hp=0),
        )
    )
    assert conscious_teams(estado) == ()


def test_times_saem_em_ordem_alfabetica():
    """Tupla ordenada e nao conjunto: quem consome decide o fim do combate, e
    ordem de iteracao que varia com PYTHONHASHSEED nao serve para isso."""
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="zulu"),
            make_combatant(id="b", team="alfa"),
            make_combatant(id="c", team="mike"),
        )
    )
    assert conscious_teams(estado) == ("alfa", "mike", "zulu")

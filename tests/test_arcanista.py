"""A ficha do arcanista: a regra que ela exercita e a regra que a protege.

Sao duas coisas diferentes e as duas moram aqui. A primeira e o truque nao
somar atributo ao dano, que e o consumidor do campo da fatia B. A segunda e a
ficha ficar **fora** do `CATALOGO` -- que nao e detalhe de organizacao: com ela
dentro, `start_combat` a guardaria no estado de todo encontro e o
`final_fingerprint` dos seis goldens mudaria sem nenhuma regra ter mudado.
"""

from __future__ import annotations

import pytest

import tacticore.content
from tacticore.content.arcanista import ARCANISTA, RAIO_DE_FOGO
from tacticore.content.srd import BRUTAMONTES, CATALOGO
from tacticore.core.actions import AttackAction
from tacticore.core.engine import legal_actions
from tacticore.core.model import PES_POR_CASA, CombatState
from tacticore.core.rules import attack_math
from tacticore.core.testing import make_combatant, make_state

CATALOGO_DO_ARCANISTA = {ARCANISTA.id: ARCANISTA, BRUTAMONTES.id: BRUTAMONTES}

ALCANCE_EM_CASAS = RAIO_DE_FOGO.range_ft // PES_POR_CASA
"""24 casas. Derivado do campo e nao escrito a mao: um `24` literal aqui
passaria a mentir em silencio no dia em que o alcance mudasse."""


def arena(casas: int) -> CombatState:
    """O mago em (0,0) e o bruto a `casas` de distancia, com o turno do mago.

    Montado a mao e nao por `start_combat` de proposito: o que se testa aqui e
    o MENU, e `legal_actions` so fala do ator da vez -- por `start_combat`,
    quem decide de quem e a vez e a iniciativa, e o teste passaria a depender
    de seed em vez de distancia.
    """
    return make_state(
        statblocks=(ARCANISTA, BRUTAMONTES),
        combatants=(
            make_combatant(
                id="mago", statblock_id="arcanista", team="herois", max_hp=ARCANISTA.max_hp
            ),
            make_combatant(
                id="bruto", statblock_id="brutamontes", team="viloes", max_hp=BRUTAMONTES.max_hp
            ),
        ),
        current="mago",
        posicoes={"mago": (0, 0), "bruto": (casas, 0)},
    )


def tiros(estado: CombatState) -> list[AttackAction]:
    return [
        a
        for a in legal_actions(estado)
        if isinstance(a, AttackAction) and a.actor == "mago" and a.attack_id == "raio_de_fogo"
    ]


# ------------------------------------------------------------- a regra -----


def test_o_raio_de_fogo_soma_int_no_acerto_e_nao_soma_no_dano():
    """As duas metades da regra do truque, lidas da ficha de verdade."""
    conta = attack_math(RAIO_DE_FOGO, ARCANISTA.abilities, ARCANISTA.proficiency_bonus)
    assert conta.ability_mod == 3
    assert conta.attack == 5, "INT 16 + proficiencia 2: o spell attack bonus"
    assert conta.damage == 0, "e o dano e so o d10"


def test_a_pontaria_do_arcanista_e_a_mesma_do_machado():
    """Nao e coincidencia e nao e balanceamento fino: e para a unica coisa nova
    nesta ficha ser o ALCANCE, e nao a chance de acertar."""
    machado = BRUTAMONTES.attacks[0]
    do_bruto = attack_math(machado, BRUTAMONTES.abilities, BRUTAMONTES.proficiency_bonus)
    do_mago = attack_math(RAIO_DE_FOGO, ARCANISTA.abilities, ARCANISTA.proficiency_bonus)
    assert do_mago.attack == do_bruto.attack == 5
    assert do_mago.damage != do_bruto.damage, "o dano, esse, e diferente"


def test_o_truque_nao_tem_faixa_de_alcance_longo():
    """Alcance de magia e um numero so. A penalidade do alcance longo e
    propriedade de ARMA, e igualar os dois campos diz 'nao ha longe'."""
    assert RAIO_DE_FOGO.long_range_ft == RAIO_DE_FOGO.range_ft


# ------------------------------------------------- a ficha fora do catalogo -


def test_a_ficha_do_arcanista_fica_fora_do_catalogo():
    """A trava mais importante deste arquivo.

    Com `ARCANISTA` dentro de `CATALOGO`, `start_combat` passa a guarda-la no
    estado de TODO encontro, `dump_state` a serializa e o `final_fingerprint`
    dos seis goldens muda sem que nenhuma regra tenha mudado -- e o
    `_diagnostico` classifica isso como "regressao ate prova em contrario".

    Este teste existe para transformar seis mensagens dessas numa frase.
    """
    assert ARCANISTA.id not in CATALOGO
    assert BRUTAMONTES.id in CATALOGO, "e o teste sabe como e um id que ESTA la"


def test_a_ficha_do_arcanista_tambem_fica_fora_da_fachada():
    """A mesma armadilha um degrau acima: como par de `BRUTAMONTES` em
    `content.__all__`, a proxima pessoa a poria no catalogo por simetria."""
    assert "ARCANISTA" not in tacticore.content.__all__


# ------------------------------------------------------------ o alcance -----


def test_o_menu_oferece_o_tiro_na_borda_do_alcance():
    assert tiros(arena(ALCANCE_EM_CASAS)), f"{ALCANCE_EM_CASAS} casas e 120 pes: ainda alcanca"


def test_o_menu_nao_oferece_o_tiro_uma_casa_alem():
    """A borda e uma parede e nao uma ladeira: sem faixa longa, uma casa a mais
    e fora de alcance, e nao desvantagem."""
    assert not tiros(arena(ALCANCE_EM_CASAS + 1))


@pytest.mark.parametrize("casas", [1, 4, 12, 24])
def test_o_tiro_esta_no_menu_a_qualquer_distancia_ate_a_borda(casas: int):
    assert tiros(arena(casas))

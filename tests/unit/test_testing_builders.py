"""Os construtores de encontro.

Eles sao codigo do core e tem ramos de verdade (`hp` int ou `HitPoints`, ordem
omitida ou explicita). Um builder errado faz dezenas de testes de regra
mentirem ao mesmo tempo, entao ele tambem tem teste.
"""

from __future__ import annotations

import itertools

import pytest

from tacticore.core.dice import DiceTerm, parse_dice
from tacticore.core.enums import Ability, Condition, canonical_conditions
from tacticore.core.model import HitPoints
from tacticore.core.rng import ScriptedRng, SplitMix64
from tacticore.core.testing import (
    make_abilities,
    make_attack,
    make_budget,
    make_combatant,
    make_statblock,
    make_state,
)


def test_atributos_nascem_com_modificador_zero():
    """Teste que nao fala de atributo nao deveria ganhar um de brinde."""
    a = make_abilities()
    assert (a.forca, a.destreza, a.constituicao) == (10, 10, 10)
    assert (a.inteligencia, a.sabedoria, a.carisma) == (10, 10, 10)


def test_atributo_informado_sobrescreve_so_ele():
    a = make_abilities(destreza=18)
    assert a.destreza == 18
    assert a.forca == 10


def test_ataque_aceita_notacao_em_string():
    ataque = make_attack(damage="2d6+3")
    assert ataque.damage.terms == (DiceTerm(count=2, faces=6),)
    assert ataque.damage.flat == 3


def test_ataque_aceita_expressao_ja_estruturada():
    expr = parse_dice("1d4")
    assert make_attack(damage=expr).damage is expr


def test_ficha_nasce_com_um_ataque():
    assert len(make_statblock().attacks) == 1


def test_ficha_aceita_lista_de_ataques():
    ficha = make_statblock(attacks=(make_attack(id="a"), make_attack(id="b", ability=Ability.DES)))
    assert [a.id for a in ficha.attacks] == ["a", "b"]
    assert ficha.attacks[1].ability is Ability.DES


def test_combatente_cheio_por_padrao():
    c = make_combatant(max_hp=17)
    assert c.hp == HitPoints(current=17, maximum=17)


def test_hp_como_int_e_atalho_para_ferido():
    c = make_combatant(hp=1, max_hp=12)
    assert c.hp == HitPoints(current=1, maximum=12)


def test_hp_como_objeto_passa_direto():
    pontos = HitPoints(current=3, maximum=40)
    assert make_combatant(hp=pontos).hp is pontos


def test_orcamento_nasce_inteiro():
    assert make_budget() == make_combatant().budget


def test_orcamento_informado_passa_direto():
    gasto = make_budget(action_available=False, movement_remaining_ft=0)
    assert make_combatant(budget=gasto).budget is gasto


def test_ordem_omitida_segue_a_ordem_dos_combatentes():
    estado = make_state(
        combatants=(make_combatant(id="a"), make_combatant(id="b"), make_combatant(id="c"))
    )
    assert estado.turn_order.order == ("a", "b", "c")
    assert estado.turn_order.current == "a"


def test_ordem_explicita_vence():
    estado = make_state(
        combatants=(make_combatant(id="a"), make_combatant(id="b")),
        order=("b", "a"),
        current="b",
    )
    assert estado.turn_order.order == ("b", "a")
    assert estado.turn_order.current == "b"


def test_combatentes_viram_mapa_por_id():
    estado = make_state(combatants=(make_combatant(id="a"), make_combatant(id="b")))
    assert set(estado.combatants) == {"a", "b"}
    assert estado.combatants["b"].id == "b"


def test_rng_padrao_e_fita_vazia():
    """Default que nao rola nada: quem precisa de dado tem que pedir."""
    assert make_state().rng == ScriptedRng(script=())


def test_rng_informado_passa_direto():
    rng = SplitMix64(seed=1, counter=2)
    assert make_state(rng=rng).rng is rng


def test_rodada_padrao_e_um():
    assert make_state().turn_order.round_number == 1


def test_estados_iguais_comparam_iguais():
    """Igualdade estrutural e o que sustenta os testes de determinismo."""
    assert make_state() == make_state()


def test_condicoes_saem_em_ordem_canonica():
    """Toda escrita no campo passa por `canonical_conditions`; a invariante de
    carga confere que passou."""
    c = make_combatant(conditions=(Condition.CAIDO, Condition.CAIDO))
    assert c.conditions == (Condition.CAIDO,)


def test_combatente_nasce_sem_condicao():
    assert make_combatant().conditions == ()


def test_arma_sem_alcance_longo_proprio_nao_tem_longe():
    assert make_attack(range_ft=20).long_range_ft == 20


def test_alcance_longo_informado_passa_direto():
    assert make_attack(range_ft=20, long_range_ft=60).long_range_ft == 60


@pytest.mark.parametrize("permutacao", list(itertools.permutations(Condition)))
def test_a_ordem_canonica_independe_da_ordem_de_entrada(permutacao: tuple[Condition, ...]):
    """Um teste que hoje e fraco e que fica forte sozinho.

    Com UM membro em `Condition`, ha uma permutacao so e a afirmacao e trivial:
    "ordenar pelo valor" e "tirar repeticao preservando a ordem" dao o mesmo
    resultado, e uma sonda confirmou que trocar uma pela outra nao quebra teste
    nenhum. Nao da para consertar sem inventar um membro de enum sem mecanica,
    que e o que o docstring de `enums.py` proibe.

    O que da para fazer e escrever a propriedade de forma que ela passe a valer
    no instante em que o segundo membro entrar -- e ai sao duas permutacoes, e
    a diferenca entre as duas implementacoes aparece. E o mesmo padrao dos
    testes de exaustividade sobre `RejectionReason` e `Event`.
    """
    assert canonical_conditions(permutacao) == canonical_conditions(sorted(Condition, key=str))

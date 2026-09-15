"""Empurrar: o primeiro teste de atributo oposto do motor.

Tres coisas se testam aqui, e so a primeira e sobre quem ganha.

1. **O consumo.** Quatro d20 por empurrao, sempre, e os dois do ator PRIMEIRO.
   A ordem entre os lados e contrato (item 6 do docstring de `tacticore.core`):
   inverte-la muda todo dado seguinte de todo combate com empurrao, e nao muda
   nada que um teste de desfecho consiga ver.
2. **O efeito.** Vencer aplica `CAIDO` e emite `KnockedProne`; empatar e perder
   nao encostam nas condicoes. A acao e gasta nos tres casos.
3. **As recusas.** Empurrar exige casa adjacente, e nao le `AttackProfile`.
"""

from __future__ import annotations

import pytest

from tacticore.core.actions import ShoveAction
from tacticore.core.engine import apply
from tacticore.core.enums import Ability, Condition, ContestOutcome, RejectionReason
from tacticore.core.events import ContestRolled, KnockedProne
from tacticore.core.ids import CreatureId
from tacticore.core.model import CombatState
from tacticore.core.results import ActionResult, Applied, Rejected
from tacticore.core.rng import ScriptedRng, position
from tacticore.core.testing import (
    make_abilities,
    make_attack,
    make_budget,
    make_combatant,
    make_statblock,
    make_state,
    tape_from_events,
)

# O ator tem FOR 16 (+3); o alvo, FOR 10 (+0) e DES 16 (+3), entao resiste com
# DES. As duas fichas sao explicitas para o teste nao depender de conteudo.
FORTE = make_statblock(id="forte", abilities=make_abilities(forca=16, destreza=8))
AGIL = make_statblock(id="agil", abilities=make_abilities(forca=10, destreza=16))

A = CreatureId("a")
B = CreatureId("b")


def arena(
    *,
    fita: tuple[int, ...],
    casas: int = 1,
    hp_b: int | None = None,
    conditions_b: tuple[Condition, ...] = (),
    acao_disponivel: bool = True,
) -> CombatState:
    """`a` (forte) em (0,0) e `b` (agil) a `casas` de distancia.

    A fita e lida na ordem do contrato: os dois dados do ator, depois os dois
    do alvo. Com `NORMAL` vale sempre o primeiro de cada par.
    """
    return make_state(
        statblocks=(FORTE, AGIL),
        combatants=(
            make_combatant(
                id="a",
                statblock_id="forte",
                team="herois",
                budget=make_budget(action_available=acao_disponivel),
            ),
            make_combatant(
                id="b",
                statblock_id="agil",
                team="viloes",
                hp=hp_b,
                conditions=conditions_b,
            ),
        ),
        current="a",
        rng=ScriptedRng(script=fita),
        posicoes={"a": (0, 0), "b": (casas, 0)},
    )


def empurrar(estado: CombatState, alvo: str = "b") -> ActionResult:
    return apply(estado, ShoveAction(actor=A, target=CreatureId(alvo)))


def aplicado(resultado: ActionResult) -> Applied:
    assert isinstance(resultado, Applied), resultado
    return resultado


# Ator tira 17 (+3 = 20), alvo tira 11 (+3 = 14): o ator vence.
VENCE = (17, 4, 11, 2)
# Ator tira 10 (+3 = 13), alvo tira 10 (+3 = 13): empate.
EMPATA = (10, 1, 10, 1)
# Ator tira 5 (+3 = 8), alvo tira 18 (+3 = 21): o alvo resiste.
PERDE = (5, 1, 18, 1)


# ------------------------------------------------------------ o consumo ----


@pytest.mark.parametrize(("nome", "fita"), [("vence", VENCE), ("empata", EMPATA), ("perde", PERDE)])
def test_o_empurrao_consome_sempre_quatro_d20(nome: str, fita: tuple[int, ...]):
    """O quadro e fixo por lado, e nao depende do desfecho.

    Se dependesse, o primeiro empurrao que empatasse deslocaria todo o resto do
    combate -- que e o modo de falha que o ADR 0001 sec. 3 existe para impedir.
    """
    estado = arena(fita=fita)
    resultado = aplicado(empurrar(estado))
    assert position(resultado.state.rng) == position(estado.rng) + 4, nome


def test_o_ator_rola_PRIMEIRO():
    """A ordem entre os lados e contrato, e nenhum teste de desfecho a ve.

    A fita comeca com 17 e 4; se o alvo rolasse primeiro, o natural do ATOR
    seria 11 e o do alvo, 17.
    """
    resultado = aplicado(empurrar(arena(fita=VENCE)))
    evento = resultado.events[0]
    assert isinstance(evento, ContestRolled)
    assert evento.actor_pair == (17, 4)
    assert evento.target_pair == (11, 2)
    assert evento.actor_natural == 17
    assert evento.target_natural == 11


def test_a_fita_reconstroi_os_quatro_dados_na_ordem_em_que_sairam():
    """`tape_from_events` e a unica trava contra listar `ContestRolled` entre os
    eventos que nao rolam dado -- o que compila, passa no mypy e fica verde na
    suite inteira, ate o primeiro combate com empurrao."""
    resultado = aplicado(empurrar(arena(fita=VENCE)))
    assert tape_from_events(resultado.events) == VENCE


def test_uma_acao_recusada_nao_consome_nada():
    """O item 4 do contrato, agora tambem para o empurrao."""
    estado = arena(fita=VENCE, casas=3)
    resultado = empurrar(estado)
    assert isinstance(resultado, Rejected)
    assert position(resultado.state.rng) == position(estado.rng) == 0


# ------------------------------------------------------------- o efeito ----


def test_vencer_derruba_e_emite_o_evento_do_efeito():
    resultado = aplicado(empurrar(arena(fita=VENCE)))
    evento = resultado.events[0]
    assert isinstance(evento, ContestRolled)
    assert evento.outcome is ContestOutcome.SUCCESS
    assert resultado.state.combatants["b"].conditions == (Condition.CAIDO,)
    assert isinstance(resultado.events[1], KnockedProne)


@pytest.mark.parametrize(("nome", "fita"), [("empata", EMPATA), ("perde", PERDE)])
def test_nao_vencer_nao_encosta_nas_condicoes(nome: str, fita: tuple[int, ...]):
    resultado = aplicado(empurrar(arena(fita=fita)))
    assert resultado.state.combatants["b"].conditions == (), nome
    assert not any(isinstance(e, KnockedProne) for e in resultado.events), nome


def test_o_empate_nao_derruba():
    """A regra que separa este motor de um que reaproveitasse `d20_check`."""
    resultado = aplicado(empurrar(arena(fita=EMPATA)))
    evento = resultado.events[0]
    assert isinstance(evento, ContestRolled)
    assert evento.actor_total == evento.target_total
    assert evento.outcome is ContestOutcome.TIE
    assert resultado.state.combatants["b"].conditions == ()


@pytest.mark.parametrize(("nome", "fita"), [("vence", VENCE), ("empata", EMPATA), ("perde", PERDE)])
def test_empurrar_gasta_a_acao_de_qualquer_jeito(nome: str, fita: tuple[int, ...]):
    """Resistir tambem custa o turno, como errar um ataque custa."""
    resultado = aplicado(empurrar(arena(fita=fita)))
    assert resultado.state.combatants["a"].budget.action_available is False, nome


def test_empurrar_nao_gasta_movimento():
    resultado = aplicado(empurrar(arena(fita=VENCE)))
    orcamento = resultado.state.combatants["a"].budget
    assert orcamento.movement_remaining_ft == 30


def test_empurrar_nao_move_ninguem():
    """Derrubar e derrubar. Empurrar 5 pes e a outra opcao da SRD, e ela ficou
    de fora -- ver docs/srd-atribuicao.md."""
    estado = arena(fita=VENCE)
    resultado = aplicado(empurrar(estado))
    for cid in ("a", "b"):
        assert resultado.state.combatants[cid].position == estado.combatants[cid].position


def test_derrubar_quem_ja_esta_caido_nao_duplica_a_condicao():
    """`canonical_conditions` tira repeticao, e a invariante de carga confere.

    Vencer contra quem ja esta no chao continua sendo vitoria e continua
    emitindo o evento: quem le o log ve que o empurrao aconteceu.
    """
    resultado = aplicado(empurrar(arena(fita=VENCE, conditions_b=(Condition.CAIDO,))))
    assert resultado.state.combatants["b"].conditions == (Condition.CAIDO,)
    assert isinstance(resultado.events[1], KnockedProne)


def test_o_estado_original_fica_intacto():
    estado = arena(fita=VENCE)
    empurrar(estado)
    assert estado.combatants["b"].conditions == ()
    assert estado.combatants["a"].budget.action_available is True
    assert position(estado.rng) == 0


# ------------------------------------------------------------- a conta -----


def test_o_evento_grava_qual_atributo_cada_lado_usou():
    """O ator sempre FOR; o alvo, o melhor dos dois. Gravar QUAL saiu e o que
    impede a regra do defensor de virar folclore."""
    evento = aplicado(empurrar(arena(fita=VENCE))).events[0]
    assert isinstance(evento, ContestRolled)
    assert evento.actor_ability is Ability.FOR
    assert evento.target_ability is Ability.DES, "o agil resiste com DES 16, nao com FOR 10"
    assert (evento.actor_bonus, evento.target_bonus) == (3, 3)


def test_a_conta_sai_aberta_dos_dois_lados():
    evento = aplicado(empurrar(arena(fita=VENCE))).events[0]
    assert isinstance(evento, ContestRolled)
    assert evento.actor_natural + evento.actor_bonus == evento.actor_total == 20
    assert evento.target_natural + evento.target_bonus == evento.target_total == 14


def test_o_evento_marca_as_posicoes_do_stream():
    evento = aplicado(empurrar(arena(fita=VENCE))).events[0]
    assert isinstance(evento, ContestRolled)
    assert (evento.rng_before, evento.rng_after) == (0, 4)


# ------------------------------------------------------------ as recusas ---


def test_empurrar_de_longe_e_recusado():
    resultado = empurrar(arena(fita=VENCE, casas=2))
    assert isinstance(resultado, Rejected)
    assert resultado.reason is RejectionReason.OUT_OF_RANGE
    assert "casa adjacente" in resultado.detail


def test_a_diagonal_conta_como_adjacente():
    """Geometria de Chebyshev: diagonal custa o mesmo que reta neste motor."""
    estado = make_state(
        statblocks=(FORTE, AGIL),
        combatants=(
            make_combatant(id="a", statblock_id="forte", team="herois"),
            make_combatant(id="b", statblock_id="agil", team="viloes"),
        ),
        current="a",
        rng=ScriptedRng(script=VENCE),
        posicoes={"a": (0, 0), "b": (1, 1)},
    )
    assert isinstance(empurrar(estado), Applied)


def test_empurrar_a_si_mesmo_e_recusado():
    resultado = empurrar(arena(fita=VENCE), alvo="a")
    assert isinstance(resultado, Rejected)
    assert resultado.reason is RejectionReason.SELF_TARGET_NOT_ALLOWED


def test_empurrar_quem_nao_existe_e_recusado():
    resultado = empurrar(arena(fita=VENCE), alvo="fantasma")
    assert isinstance(resultado, Rejected)
    assert resultado.reason is RejectionReason.NO_SUCH_TARGET


def test_sem_acao_disponivel_nao_empurra():
    resultado = empurrar(arena(fita=VENCE, acao_disponivel=False))
    assert isinstance(resultado, Rejected)
    assert resultado.reason is RejectionReason.ACTION_ALREADY_USED


def test_empurrar_duas_vezes_e_recusado_na_segunda():
    primeiro = aplicado(empurrar(arena(fita=(*VENCE, *VENCE))))
    segundo = empurrar(primeiro.state)
    assert isinstance(segundo, Rejected)
    assert segundo.reason is RejectionReason.ACTION_ALREADY_USED


def test_o_alcance_nao_sai_da_ficha_de_ataque():
    """A trava contra a tentacao de ler `AttackProfile.range_ft`.

    O `forte` tem um ataque de 5 pes por default, mas o que decide aqui e a
    geometria: um ataque de 120 pes na ficha nao daria empurrao a distancia, e
    uma ficha sem ataque corpo a corpo nao ficaria sem empurrao.
    """
    longe = make_statblock(
        id="forte",
        abilities=make_abilities(forca=16, destreza=8),
        attacks=(make_attack(id="arco", range_ft=120, long_range_ft=120),),
    )
    estado = make_state(
        statblocks=(longe, AGIL),
        combatants=(
            make_combatant(id="a", statblock_id="forte", team="herois"),
            make_combatant(id="b", statblock_id="agil", team="viloes"),
        ),
        current="a",
        rng=ScriptedRng(script=VENCE),
        posicoes={"a": (0, 0), "b": (3, 0)},
    )
    resultado = empurrar(estado)
    assert isinstance(resultado, Rejected)
    assert resultado.reason is RejectionReason.OUT_OF_RANGE, "120 pes na ficha nao alcancam 15"

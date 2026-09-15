"""O ataque de ponta a ponta.

Quase tudo aqui e feito com fita roteirizada. A pergunta nao e "que numero
saiu", e sim "que rolagens aconteceram, nesta ordem, e que eventos sairam" --
e e essa a unica pergunta que um teste consegue fazer sobre um acerto critico,
ja que critico e acerto comum de mesmo dano deixam o HP exatamente igual.

Leitura da fita: o ataque consome sempre **dois** d20 (quadro fixo), e so
depois disso os dados de dano, da esquerda para a direita.
"""

from __future__ import annotations

from tacticore.core.actions import AttackAction
from tacticore.core.engine import apply
from tacticore.core.enums import AdvantageState, AttackOutcome, RejectionReason
from tacticore.core.events import (
    AttackRolled,
    CombatEnded,
    CreatureDowned,
    DamageRolled,
    HpChanged,
)
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import CombatState
from tacticore.core.results import ActionResult, Applied, Rejected
from tacticore.core.rng import ScriptedRng, position
from tacticore.core.testing import (
    make_abilities,
    make_attack,
    make_combatant,
    make_statblock,
    make_state,
)

ESPADA = AttackId("espada")


def arena(
    *,
    dano: str = "1d6",
    forca: int = 14,
    proficiencia: int = 2,
    proficiente: bool = True,
    ca_alvo: int = 15,
    hp_alvo: int = 20,
    fita: tuple[int, ...] = (),
) -> CombatState:
    """FOR 14 = +2. Com proficiencia +2, o bonus de ataque e +4."""
    atacante = make_statblock(
        id="atacante",
        abilities=make_abilities(forca=forca),
        proficiency_bonus=proficiencia,
        attacks=(
            make_attack(id="espada", name="Espada Longa", proficient=proficiente, damage=dano),
        ),
    )
    defensor = make_statblock(id="defensor", armor_class=ca_alvo, max_hp=hp_alvo)

    return make_state(
        statblocks=(atacante, defensor),
        combatants=(
            make_combatant(id="a", statblock_id="atacante", team="herois"),
            make_combatant(id="b", statblock_id="defensor", team="viloes", max_hp=hp_alvo),
        ),
        current="a",
        rng=ScriptedRng(script=fita),
    )


def atacar(estado: CombatState, **kwargs: object) -> Applied:
    acao = AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=ESPADA, **kwargs)  # type: ignore[arg-type]
    resultado: ActionResult = apply(estado, acao)
    assert isinstance(resultado, Applied), resultado
    return resultado


# ------------------------------------------------------------- acerto ------


def test_acerto_tira_vida():
    # d20 = 15 (+4 = 19 contra CA 15), descartado 1, dano 1d6 = 4, +2 de FOR.
    resultado = atacar(arena(fita=(15, 1, 4)))
    assert resultado.state.combatants["b"].hp.current == 20 - 6


def test_a_sequencia_de_eventos_de_um_acerto():
    resultado = atacar(arena(fita=(15, 1, 4)))
    assert [type(e) for e in resultado.events] == [AttackRolled, DamageRolled, HpChanged]


def test_a_conta_do_ataque_sai_decomposta_no_log():
    resultado = atacar(arena(fita=(15, 1, 4)))
    evento = resultado.events[0]
    assert isinstance(evento, AttackRolled)
    assert (evento.natural, evento.ability_mod, evento.proficiency, evento.total) == (15, 2, 2, 19)
    assert evento.total == evento.natural + evento.ability_mod + evento.proficiency
    assert evento.target_ac == 15
    assert evento.outcome is AttackOutcome.HIT


def test_o_nome_do_ataque_vai_no_log():
    """Nome e dado, nao apresentacao: sem ele o log vira charada."""
    evento = atacar(arena(fita=(15, 1, 4))).events[0]
    assert isinstance(evento, AttackRolled)
    assert (evento.attack_id, evento.attack_name) == ("espada", "Espada Longa")


def test_o_dano_soma_o_mesmo_atributo_do_acerto():
    resultado = atacar(arena(fita=(15, 1, 4)))
    dano = resultado.events[1]
    assert isinstance(dano, DamageRolled)
    assert dano.roll.ability_bonus == 2
    assert dano.roll.total == 4 + 2


def test_proficiencia_nao_entra_no_dano():
    resultado = atacar(arena(proficiencia=5, fita=(15, 1, 4)))
    ataque, dano = resultado.events[0], resultado.events[1]
    assert isinstance(ataque, AttackRolled)
    assert isinstance(dano, DamageRolled)
    assert ataque.proficiency == 5
    assert dano.roll.ability_bonus == 2


def test_sem_proficiencia_o_ataque_perde_o_bonus():
    evento = atacar(arena(proficiente=False, fita=(15, 1, 4))).events[0]
    assert isinstance(evento, AttackRolled)
    assert evento.proficiency == 0
    assert evento.total == 15 + 2


# --------------------------------------------------------------- erro ------


def test_erro_nao_rola_dano():
    """A ausencia de DamageRolled no log e a prova de que nao houve rolagem."""
    resultado = atacar(arena(fita=(5, 1)))
    assert [type(e) for e in resultado.events] == [AttackRolled]
    assert resultado.state.combatants["b"].hp.current == 20


def test_erro_nao_consome_entropia_de_dano():
    """A asercao dura: o stream avancou exatamente os dois d20 do ataque."""
    resultado = atacar(arena(fita=(5, 1)))
    assert position(resultado.state.rng) == 2


def test_acerto_consome_os_dois_d20_mais_os_dados_de_dano():
    resultado = atacar(arena(dano="2d6", fita=(15, 1, 3, 4)))
    assert position(resultado.state.rng) == 4


# ------------------------------------------------------------ critico ------


def test_critico_dobra_os_dados_e_nao_o_modificador():
    # 20 natural, descartado 1, e entao 2 dados de 1d6 dobrado: 6 e 5.
    resultado = atacar(arena(fita=(20, 1, 6, 5)))
    dano = resultado.events[1]
    assert isinstance(dano, DamageRolled)
    assert len(dano.roll.dice) == 2
    assert dano.roll.critical is True
    assert dano.roll.total == 6 + 5 + 2


def test_vinte_natural_acerta_armadura_impossivel():
    # A fita tem QUATRO valores: 20 natural e critico, e critico dobra os dados
    # de dano. Uma fita de tres esgotaria -- foi assim que este teste nasceu.
    resultado = atacar(arena(ca_alvo=30, fita=(20, 1, 3, 4)))
    evento = resultado.events[0]
    assert isinstance(evento, AttackRolled)
    assert evento.outcome is AttackOutcome.CRITICAL_HIT


def test_um_natural_erra_mesmo_com_bonus_alto():
    resultado = atacar(arena(forca=20, proficiencia=6, ca_alvo=5, fita=(1, 1)))
    evento = resultado.events[0]
    assert isinstance(evento, AttackRolled)
    assert evento.outcome is AttackOutcome.CRITICAL_MISS
    assert len(resultado.events) == 1


# ----------------------------------------------------------- vantagem ------


def test_vantagem_escolhe_o_maior_e_registra_o_motivo():
    resultado = atacar(arena(fita=(3, 19, 4)), advantage_sources=("flanqueando",))
    evento = resultado.events[0]
    assert isinstance(evento, AttackRolled)
    assert evento.advantage is AdvantageState.ADVANTAGE
    assert evento.advantage_sources == ("flanqueando",)
    assert (evento.pair, evento.chosen_index, evento.natural) == ((3, 19), 1, 19)


def test_uma_de_cada_lado_cancela():
    resultado = atacar(
        arena(fita=(3, 19)),
        advantage_sources=("flanqueando",),
        disadvantage_sources=("cegado",),
    )
    evento = resultado.events[0]
    assert isinstance(evento, AttackRolled)
    assert evento.advantage is AdvantageState.NORMAL
    assert evento.natural == 3


def test_o_par_inteiro_vai_no_log_mesmo_em_normal():
    """O dado descartado e a prova de que o quadro fixo foi respeitado."""
    evento = atacar(arena(fita=(15, 20, 4))).events[0]
    assert isinstance(evento, AttackRolled)
    assert evento.pair == (15, 20)
    assert evento.natural == 15


# --------------------------------------------------------------- queda -----


def test_zerar_a_vida_derruba_e_anuncia():
    """Com `b` sendo o unico vilao, derruba-lo tambem encerra o combate."""
    resultado = atacar(arena(hp_alvo=5, fita=(15, 1, 6)))
    assert [type(e) for e in resultado.events] == [
        AttackRolled,
        DamageRolled,
        HpChanged,
        CreatureDowned,
        CombatEnded,
    ]
    assert resultado.state.combatants["b"].hp.current == 0


def test_o_excedente_vai_no_evento_e_nao_no_hp():
    resultado = atacar(arena(hp_alvo=3, fita=(15, 1, 6)))
    evento = resultado.events[2]
    assert isinstance(evento, HpChanged)
    assert (evento.dealt, evento.overkill) == (3, 5)
    assert evento.after.current == 0


def test_bater_em_quem_ja_caiu_e_legal_e_fica_registrado():
    """Fidelidade a SRD, e a porta para o golpe de misericordia.

    Precisa de um terceiro de pe no time do alvo: com o unico vilao caido, o
    combate ja teria acabado e a acao seria recusada com COMBAT_OVER.
    """
    estado = arena(hp_alvo=10, fita=(15, 1, 4))
    caido = make_state(
        statblocks=tuple(estado.statblocks.values()),
        combatants=(
            estado.combatants["a"],
            make_combatant(id="b", statblock_id="defensor", team="viloes", hp=0, max_hp=10),
            make_combatant(id="c", statblock_id="defensor", team="viloes", max_hp=10),
        ),
        current="a",
        rng=estado.rng,
    )
    resultado = atacar(caido)
    evento = resultado.events[0]
    assert isinstance(evento, AttackRolled)
    assert evento.target_was_down is True
    assert not any(isinstance(e, CreatureDowned) for e in resultado.events)


# ---------------------------------------------------------- economia -------


def test_o_ataque_gasta_a_acao():
    resultado = atacar(arena(fita=(15, 1, 4)))
    assert resultado.state.combatants["a"].budget.action_available is False


def test_errar_tambem_custa_a_acao():
    resultado = atacar(arena(fita=(2, 1)))
    assert resultado.state.combatants["a"].budget.action_available is False


def test_o_ataque_nao_gasta_movimento():
    resultado = atacar(arena(fita=(15, 1, 4)))
    assert resultado.state.combatants["a"].budget.movement_remaining_ft == 30


def test_o_estado_original_nao_e_tocado():
    estado = arena(fita=(15, 1, 4))
    atacar(estado)
    assert estado.combatants["b"].hp.current == 20
    assert position(estado.rng) == 0


def test_a_mesma_fita_da_o_mesmo_resultado():
    a = atacar(arena(fita=(15, 1, 4)))
    b = atacar(arena(fita=(15, 1, 4)))
    assert a.state == b.state
    assert a.events == b.events


# ------------------------------------------------------------- alcance -----


def arena_com_alcance(*, alcance: int, casas: int, fita: tuple[int, ...] = ()) -> CombatState:
    """`a` e `b` separados por `casas`, com uma arma de alcance `alcance`."""
    ficha = make_statblock(
        id="ficha",
        armor_class=10,
        attacks=(make_attack(id="espada", damage="1d6", range_ft=alcance),),
    )
    return make_state(
        statblocks=(ficha,),
        combatants=(
            make_combatant(id="a", statblock_id="ficha", team="herois"),
            make_combatant(id="b", statblock_id="ficha", team="viloes"),
        ),
        current="a",
        rng=ScriptedRng(script=fita),
        posicoes={"a": (0, 0), "b": (casas, 0)},
    )


def atacar_em(estado: CombatState) -> ActionResult:
    return apply(
        estado,
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=ESPADA),
    )


def test_ataque_dentro_do_alcance_vale():
    resultado = atacar_em(arena_com_alcance(alcance=5, casas=1, fita=(15, 1, 4)))
    assert isinstance(resultado, Applied)


def test_ataque_na_diagonal_conta_como_uma_casa():
    """A geometria de grade vale para alcance tambem, e nao so para movimento."""
    estado = arena_com_alcance(alcance=5, casas=1, fita=(15, 1, 4))
    diagonal = make_state(
        statblocks=tuple(estado.statblocks.values()),
        combatants=tuple(estado.combatants.values()),
        current="a",
        rng=estado.rng,
        posicoes={"a": (0, 0), "b": (1, 1)},
    )
    assert isinstance(atacar_em(diagonal), Applied)


def test_ataque_fora_do_alcance_e_recusado():
    resultado = atacar_em(arena_com_alcance(alcance=5, casas=2))
    assert isinstance(resultado, Rejected)
    assert resultado.reason is RejectionReason.OUT_OF_RANGE
    assert "10 pes" in resultado.detail


def test_a_recusa_por_alcance_nao_consome_entropia():
    """Como toda rejeicao: a validacao roda inteira antes do primeiro dado."""
    estado = arena_com_alcance(alcance=5, casas=2, fita=(15, 1, 4))
    resultado = atacar_em(estado)
    assert isinstance(resultado, Rejected)
    assert resultado.state is estado


def test_o_limite_e_inclusivo():
    """Alcance 10 acerta a 10 pes, e nao a 5."""
    assert isinstance(atacar_em(arena_com_alcance(alcance=10, casas=2, fita=(15, 1, 4))), Applied)
    assert isinstance(atacar_em(arena_com_alcance(alcance=10, casas=3)), Rejected)


def test_arma_de_arremesso_alcanca_longe():
    resultado = atacar_em(arena_com_alcance(alcance=30, casas=6, fita=(15, 1, 4)))
    assert isinstance(resultado, Applied)


def test_a_desvantagem_derivada_chega_ao_evento():
    """A ponte entre `derive_advantage_sources` e o log.

    A regra e testada isolada em test_derive_advantage.py; aqui se prova que
    ela de fato entra no ataque, aparece no evento e consome os dois d20 do
    quadro fixo escolhendo o menor.
    """
    ficha = make_statblock(
        id="ficha",
        armor_class=10,
        attacks=(make_attack(id="adaga", name="Adaga", range_ft=20, damage="1d4"),),
    )
    estado = make_state(
        statblocks=(ficha,),
        combatants=(
            make_combatant(id="a", statblock_id="ficha", team="herois"),
            make_combatant(id="b", statblock_id="ficha", team="viloes"),
        ),
        current="a",
        rng=ScriptedRng(script=(18, 4, 2)),
        posicoes={"a": (0, 0), "b": (1, 0)},
    )
    resultado = apply(
        estado,
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=AttackId("adaga")),
    )
    assert isinstance(resultado, Applied)

    evento = resultado.events[0]
    assert isinstance(evento, AttackRolled)
    assert evento.advantage is AdvantageState.DISADVANTAGE
    assert evento.disadvantage_sources == ("inimigo adjacente",)
    assert (evento.pair, evento.natural) == ((18, 4), 4), "pegou o menor dos dois"


def test_as_fontes_declaradas_vem_antes_das_derivadas():
    """A ordem e fixa porque ela aparece no log."""
    ficha = make_statblock(
        id="ficha", attacks=(make_attack(id="adaga", range_ft=20, damage="1d4"),)
    )
    estado = make_state(
        statblocks=(ficha,),
        combatants=(
            make_combatant(id="a", statblock_id="ficha", team="herois"),
            make_combatant(id="b", statblock_id="ficha", team="viloes"),
        ),
        current="a",
        rng=ScriptedRng(script=(10, 10, 2)),
        posicoes={"a": (0, 0), "b": (1, 0)},
    )
    resultado = apply(
        estado,
        AttackAction(
            actor=CreatureId("a"),
            target=CreatureId("b"),
            attack_id=AttackId("adaga"),
            disadvantage_sources=("cegado",),
        ),
    )
    assert isinstance(resultado, Applied)
    evento = resultado.events[0]
    assert isinstance(evento, AttackRolled)
    assert evento.disadvantage_sources == ("cegado", "inimigo adjacente")


def test_o_alcance_longo_e_o_limite_da_recusa():
    """Curto passa a ser penalidade, e longo passa a ser a parede."""
    ficha = make_statblock(
        id="ficha",
        attacks=(make_attack(id="arco", range_ft=20, long_range_ft=40),),
    )

    def tiro(casas: int, fita: tuple[int, ...] = ()) -> ActionResult:
        estado = make_state(
            statblocks=(ficha,),
            combatants=(
                make_combatant(id="a", statblock_id="ficha", team="herois"),
                make_combatant(id="b", statblock_id="ficha", team="viloes"),
            ),
            current="a",
            rng=ScriptedRng(script=fita),
            posicoes={"a": (0, 0), "b": (casas, 0)},
        )
        return apply(
            estado,
            AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=AttackId("arco")),
        )

    assert isinstance(tiro(4, (15, 1, 4)), Applied), "20 pes: dentro do curto"
    assert isinstance(tiro(8, (15, 1, 4)), Applied), "40 pes: dentro do longo"
    fora = tiro(9)
    assert isinstance(fora, Rejected), "45 pes: alem do longo"
    assert fora.reason is RejectionReason.OUT_OF_RANGE


def test_a_desvantagem_de_alcance_longo_chega_ao_evento():
    ficha = make_statblock(
        id="ficha",
        armor_class=10,
        attacks=(make_attack(id="arco", name="Arco", range_ft=20, long_range_ft=60, damage="1d6"),),
    )
    estado = make_state(
        statblocks=(ficha,),
        combatants=(
            make_combatant(id="a", statblock_id="ficha", team="herois"),
            make_combatant(id="b", statblock_id="ficha", team="viloes"),
        ),
        current="a",
        rng=ScriptedRng(script=(19, 6, 3)),
        posicoes={"a": (0, 0), "b": (8, 0)},
    )
    resultado = apply(
        estado,
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=AttackId("arco")),
    )
    assert isinstance(resultado, Applied)
    evento = resultado.events[0]
    assert isinstance(evento, AttackRolled)
    assert evento.disadvantage_sources == ("alem do alcance curto",)
    assert evento.natural == 6, "pegou o menor dos dois"

"""Guardiao do codec manual.

O codec escrito a mao tem um modo de falha conhecido: alguem acrescenta um
campo e esquece do `from_dict`. O campo some no save, volta com o default, e o
combate recarregado diverge sem nada apontando para a causa.

Aqui isso vira teste vermelho no mesmo commit, de duas formas: nenhum tipo de
estado pode existir sem codec, e as chaves emitidas por cada codec tem que
bater **exatamente** com os campos declarados na dataclass.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import json
from collections.abc import Callable, Mapping

import pytest

from tacticore.core import serde
from tacticore.core.dice import DamageExpr, DamageRoll, DiceTerm, DieRoll, parse_dice
from tacticore.core.enums import (
    Ability,
    AdvantageState,
    AttackOutcome,
    SkipReason,
)
from tacticore.core.events import (
    AttackRolled,
    CombatEnded,
    CreatureDowned,
    DamageRolled,
    HpChanged,
    InitiativeRolled,
    MovementSpent,
    RoundStarted,
    TurnEnded,
    TurnOrderSet,
    TurnSkipped,
    TurnStarted,
)
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import (
    Abilities,
    AttackProfile,
    Combatant,
    CombatOutcome,
    CombatState,
    HitPoints,
    Position,
    Statblock,
    TurnBudget,
    TurnOrder,
)
from tacticore.core.rng import ScriptedRng, SplitMix64
from tacticore.core.serde import JsonValue
from tacticore.core.testing import (
    make_abilities,
    make_attack,
    make_budget,
    make_combatant,
    make_statblock,
    make_state,
)

# Modulos cujas dataclasses atravessam a fronteira do motor. Tudo que for
# dataclass neles precisa de codec -- a lista e de MODULOS e nao de classes
# justamente para nao existir um lugar onde esquecer de registrar a classe nova.
MODULOS_COM_ESTADO = ("rng", "dice", "model")
MODULOS_COM_EVENTO = ("events",)


def _exemplo_state() -> CombatState:
    return make_state()


CODECS: Mapping[
    type,
    tuple[
        Callable[[object], dict[str, JsonValue]],
        Callable[[Mapping[str, JsonValue]], object],
        object,
    ],
] = {
    SplitMix64: (serde.dump_rng, serde.load_rng, SplitMix64(seed=2**63 - 1, counter=9)),  # type: ignore[dict-item]
    ScriptedRng: (serde.dump_rng, serde.load_rng, ScriptedRng(script=(20, 1), cursor=1)),  # type: ignore[dict-item]
    DiceTerm: (  # type: ignore[dict-item]
        serde.dump_dice_term,
        lambda raw: serde.load_dice_term(raw, "t"),
        DiceTerm(count=2, faces=6, doubles_on_crit=False),
    ),
    DamageExpr: (  # type: ignore[dict-item]
        serde.dump_damage_expr,
        lambda raw: serde.load_damage_expr(raw, "t"),
        parse_dice("1d8+1d4+3"),
    ),
    DieRoll: (  # type: ignore[dict-item]
        serde.dump_die_roll,
        lambda raw: serde.load_die_roll(raw, "t"),
        DieRoll(term_index=1, faces=8, value=7, from_crit=True),
    ),
    DamageRoll: (  # type: ignore[dict-item]
        serde.dump_damage_roll,
        lambda raw: serde.load_damage_roll(raw, "t"),
        DamageRoll(
            dice=(DieRoll(term_index=0, faces=6, value=3, from_crit=False),),
            flat=2,
            ability_bonus=-1,
            critical=False,
            total=4,
        ),
    ),
    Abilities: (  # type: ignore[dict-item]
        serde.dump_abilities,
        lambda raw: serde.load_abilities(raw, "t"),
        make_abilities(forca=18, destreza=7),
    ),
    HitPoints: (  # type: ignore[dict-item]
        serde.dump_hit_points,
        lambda raw: serde.load_hit_points(raw, "t"),
        HitPoints(current=0, maximum=13),
    ),
    AttackProfile: (  # type: ignore[dict-item]
        serde.dump_attack_profile,
        lambda raw: serde.load_attack_profile(raw, "t"),
        make_attack(id="cimitarra", proficient=False, damage="1d6-1"),
    ),
    Statblock: (  # type: ignore[dict-item]
        serde.dump_statblock,
        lambda raw: serde.load_statblock(raw, "t"),
        make_statblock(attacks=(make_attack(id="a"), make_attack(id="b"))),
    ),
    TurnBudget: (  # type: ignore[dict-item]
        serde.dump_turn_budget,
        lambda raw: serde.load_turn_budget(raw, "t"),
        make_budget(action_available=False, movement_remaining_ft=0),
    ),
    Combatant: (  # type: ignore[dict-item]
        serde.dump_combatant,
        lambda raw: serde.load_combatant(raw, "t"),
        make_combatant(id="goblin_1", team="inimigos", hp=3),
    ),
    TurnOrder: (  # type: ignore[dict-item]
        serde.dump_turn_order,
        lambda raw: serde.load_turn_order(raw, "t"),
        _exemplo_state().turn_order,
    ),
    Position: (  # type: ignore[dict-item]
        serde.dump_position,
        lambda raw: serde.load_position(raw, "t"),
        # Valor nao-default em todo campo, e negativo de proposito: exemplo
        # com zero em tudo faz o round-trip passar sem provar nada.
        Position(x=-3, y=7),
    ),
    CombatState: (serde.dump_state, serde.load_state, _exemplo_state()),  # type: ignore[dict-item]
    CombatOutcome: (  # type: ignore[dict-item]
        serde.dump_combat_outcome,
        lambda raw: serde.load_combat_outcome(raw, "t"),
        CombatOutcome(winning_team="herois", last_round=4),
    ),
}

# Eventos so tem ida: saem para o log, para a interface e para o golden, e
# nunca voltam para dentro do motor. Por isso o registro deles nao tem `load`,
# e o guardiao confere as chaves sem pedir round-trip.
EVENT_CODECS: Mapping[type, tuple[Callable[[object], dict[str, JsonValue]], object]] = {
    InitiativeRolled: (  # type: ignore[dict-item]
        serde.dump_initiative_rolled,
        InitiativeRolled(
            creature=CreatureId("heroi"),
            d20=17,
            dex_mod=2,
            dex_score=14,
            total=19,
            rng_before=0,
            rng_after=1,
        ),
    ),
    TurnOrderSet: (  # type: ignore[dict-item]
        serde.dump_turn_order_set,
        TurnOrderSet(order=(CreatureId("heroi"), CreatureId("vilao"))),
    ),
    RoundStarted: (serde.dump_round_started, RoundStarted(round_number=2)),  # type: ignore[dict-item]
    TurnStarted: (  # type: ignore[dict-item]
        serde.dump_turn_started,
        TurnStarted(creature=CreatureId("heroi"), budget=make_budget()),
    ),
    TurnSkipped: (  # type: ignore[dict-item]
        serde.dump_turn_skipped,
        TurnSkipped(creature=CreatureId("vilao"), reason=SkipReason.ACTOR_IS_DOWN),
    ),
    TurnEnded: (serde.dump_turn_ended, TurnEnded(creature=CreatureId("heroi"))),  # type: ignore[dict-item]
    MovementSpent: (  # type: ignore[dict-item]
        serde.dump_movement_spent,
        MovementSpent(creature=CreatureId("heroi"), feet=15, remaining_ft=15),
    ),
    AttackRolled: (  # type: ignore[dict-item]
        serde.dump_attack_rolled,
        AttackRolled(
            actor=CreatureId("heroi"),
            target=CreatureId("vilao"),
            attack_id=AttackId("cimitarra"),
            attack_name="Cimitarra",
            advantage=AdvantageState.ADVANTAGE,
            advantage_sources=("flanqueando",),
            disadvantage_sources=(),
            pair=(3, 18),
            chosen_index=1,
            natural=18,
            ability=Ability.FOR,
            ability_mod=3,
            proficiency=2,
            total=23,
            target_ac=15,
            target_was_down=False,
            outcome=AttackOutcome.HIT,
            rng_before=4,
            rng_after=6,
        ),
    ),
    DamageRolled: (  # type: ignore[dict-item]
        serde.dump_damage_rolled,
        DamageRolled(
            actor=CreatureId("heroi"),
            target=CreatureId("vilao"),
            roll=DamageRoll(
                dice=(DieRoll(term_index=0, faces=6, value=5, from_crit=False),),
                flat=0,
                ability_bonus=3,
                critical=False,
                total=8,
            ),
            rng_before=6,
            rng_after=7,
        ),
    ),
    HpChanged: (  # type: ignore[dict-item]
        serde.dump_hp_changed,
        HpChanged(
            creature=CreatureId("vilao"),
            before=HitPoints(current=8, maximum=12),
            after=HitPoints(current=0, maximum=12),
            dealt=8,
            overkill=0,
        ),
    ),
    CreatureDowned: (  # type: ignore[dict-item]
        serde.dump_creature_downed,
        CreatureDowned(creature=CreatureId("vilao")),
    ),
    CombatEnded: (  # type: ignore[dict-item]
        serde.dump_combat_ended,
        CombatEnded(outcome=CombatOutcome(winning_team=None, last_round=7)),
    ),
}

IDS = [c.__name__ for c in CODECS]
IDS_EVENTO = [c.__name__ for c in EVENT_CODECS]


def _dataclasses_de(modulos: tuple[str, ...]) -> set[type]:
    encontradas: set[type] = set()
    for nome in modulos:
        modulo = importlib.import_module(f"tacticore.core.{nome}")
        encontradas.update(
            obj
            for _, obj in inspect.getmembers(modulo, inspect.isclass)
            if dataclasses.is_dataclass(obj) and obj.__module__ == modulo.__name__
        )
    return encontradas


def _dataclasses_com_estado() -> set[type]:
    return _dataclasses_de(MODULOS_COM_ESTADO)


def _dataclasses_de_evento() -> set[type]:
    return _dataclasses_de(MODULOS_COM_EVENTO)


def test_todo_tipo_de_estado_tem_codec():
    """Classe nova sem codec sumiria do save e voltaria com o default."""
    sem_codec = _dataclasses_com_estado() - set(CODECS)
    assert not sem_codec, (
        f"sem codec em serde.py: {sorted(c.__name__ for c in sem_codec)}. "
        "Tipo novo entra com codec e com entrada aqui, no mesmo commit."
    )


def test_o_registro_nao_tem_classe_fantasma():
    """O inverso: codec de classe que nao existe mais e codigo morto."""
    fantasmas = set(CODECS) - _dataclasses_com_estado()
    assert not fantasmas, f"codec sem classe: {sorted(c.__name__ for c in fantasmas)}"


@pytest.mark.parametrize("cls", list(CODECS), ids=IDS)
def test_chaves_emitidas_batem_com_os_campos_declarados(cls: type):
    dump, _, exemplo = CODECS[cls]
    declarados = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
    emitidos = set(dump(exemplo))
    assert emitidos == declarados, (
        f"{cls.__name__}: o codec emite {sorted(emitidos)} e a dataclass declara "
        f"{sorted(declarados)}"
    )


@pytest.mark.parametrize("cls", list(CODECS), ids=IDS)
def test_round_trip_passando_por_json_de_verdade(cls: type):
    """Ida e volta pelo texto, e nao so pelo dict.

    E o texto que pega tupla virando lista, enum virando string e inteiro de 64
    bits perdendo precisao -- justamente o que um round-trip so de dicionario
    deixaria passar.
    """
    dump, load, exemplo = CODECS[cls]
    texto = json.dumps(dump(exemplo))
    assert load(json.loads(texto)) == exemplo


def test_todo_evento_tem_codec():
    """Evento novo sem codec sumiria do log e do golden sem avisar."""
    sem_codec = _dataclasses_de_evento() - set(EVENT_CODECS)
    assert not sem_codec, (
        f"sem codec em serde.py: {sorted(c.__name__ for c in sem_codec)}. "
        "Evento novo entra com codec e com entrada aqui, no mesmo commit."
    )


def test_o_registro_de_eventos_nao_tem_classe_fantasma():
    fantasmas = set(EVENT_CODECS) - _dataclasses_de_evento()
    assert not fantasmas, f"codec sem evento: {sorted(c.__name__ for c in fantasmas)}"


@pytest.mark.parametrize("cls", list(EVENT_CODECS), ids=IDS_EVENTO)
def test_chaves_do_evento_batem_com_os_campos(cls: type):
    dump, exemplo = EVENT_CODECS[cls]
    declarados = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
    assert set(dump(exemplo)) == declarados


@pytest.mark.parametrize("cls", list(EVENT_CODECS), ids=IDS_EVENTO)
def test_evento_sobrevive_ao_json(cls: type):
    """Nao ha round-trip, mas o dicionario emitido tem que ser serializavel."""
    dump, exemplo = EVENT_CODECS[cls]
    assert json.loads(json.dumps(dump(exemplo))) == dump(exemplo)


def test_despacho_de_evento_cobre_a_uniao_inteira():
    """`event_to_dict` escolhe pelo kind; um evento fora do match seria erro."""
    for cls, (_, exemplo) in EVENT_CODECS.items():
        emitido = serde.event_to_dict(exemplo)  # type: ignore[arg-type]
        assert emitido["kind"] == exemplo.kind, cls.__name__

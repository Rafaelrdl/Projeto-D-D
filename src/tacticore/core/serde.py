"""Codec entre o estado e JSON, escrito a mao.

Escrito a mao de proposito. ``dataclasses.asdict()`` nao tem inverso e devolve
``Any``, o que apagaria a tipagem justamente na fronteira onde ela mais vale;
pydantic traria validacao para dentro das entidades de regra, que devem
continuar sendo dados burros. Sao pouco mais de dez classes -- o codec manual
cabe num arquivo e passa em mypy strict sem plugin.

O risco obvio do codec manual e alguem acrescentar um campo e esquecer do
``from_dict``. Contra isso existe o guardiao de campos-vs-chaves em
``tests/architecture/test_serde_guardrails.py``: para cada classe, os nomes dos
campos da dataclass tem que bater exatamente com as chaves emitidas. Campo novo
sem codec vira teste vermelho no mesmo commit.

**Este modulo nao faz I/O.** ``dump`` devolve um ``dict`` e ``load`` recebe um
``dict``; quem abre arquivo, socket ou banco e o chamador, fora do core.

O envelope carrega quatro coisas, e cada uma existe por um motivo diferente::

    {"schema_version": 1,          # o FORMATO mudou (campo novo, campo movido)
     "rules_version": 1,           # as REGRAS mudaram (resultado difere)
     "rng_algo": "splitmix64-...", # o gerador mudou (o stream difere)
     "state": {...}}

Separar `schema_version` de `rules_version` e o que impede o pior modo de
falha: uma correcao de regra em dezembro transformaria os saves de novembro em
lixo que **carrega sem erro** e simula diferente. Formato igual, resultado
diferente -- e so o segundo campo denuncia.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Final, assert_never

from tacticore.core.dice import DamageExpr, DamageRoll, DiceTerm, DieRoll
from tacticore.core.enums import Ability
from tacticore.core.errors import InvalidSaveError, UnsupportedSchemaVersion
from tacticore.core.events import (
    AttackRolled,
    CombatEnded,
    CreatureDowned,
    DamageRolled,
    Event,
    HpChanged,
    InitiativeRolled,
    MovementSpent,
    RoundStarted,
    TurnEnded,
    TurnOrderSet,
    TurnSkipped,
    TurnStarted,
)
from tacticore.core.ids import AttackId, CreatureId, StatblockId
from tacticore.core.model import (
    Abilities,
    AttackProfile,
    Combatant,
    CombatOutcome,
    CombatState,
    HitPoints,
    Statblock,
    TurnBudget,
    TurnOrder,
)
from tacticore.core.rng import ALGORITHM, RngState, ScriptedRng, SplitMix64

type JsonValue = str | int | bool | list[JsonValue] | dict[str, JsonValue] | None

SCHEMA_VERSION: Final[int] = 1
"""Muda quando o FORMATO muda: campo novo, campo removido, campo renomeado."""

RULES_VERSION: Final[int] = 1
"""Muda quando o RESULTADO muda: ordem de consumo do RNG ou qualquer regra.

Incrementar isto e obrigacao de todo commit que altere o que o motor calcula.
Um save com `rules_version` diferente ainda carrega -- o que nao pode e
carregar em silencio e divergir tres turnos depois.
"""


# ------------------------------------------------------------ leitura -------
# Acessores tipados: `load` recebe JSON de origem desconhecida, entao cada
# campo e conferido na hora de ler, com o caminho no erro.


def _campo(raw: Mapping[str, JsonValue], nome: str, caminho: str) -> JsonValue:
    if nome not in raw:
        msg = f"{caminho}: falta o campo {nome!r}"
        raise InvalidSaveError(msg)
    return raw[nome]


def _texto(raw: Mapping[str, JsonValue], nome: str, caminho: str) -> str:
    valor = _campo(raw, nome, caminho)
    if not isinstance(valor, str):
        msg = f"{caminho}.{nome}: esperava texto e achei {type(valor).__name__}"
        raise InvalidSaveError(msg)
    return valor


def _inteiro(raw: Mapping[str, JsonValue], nome: str, caminho: str) -> int:
    valor = _campo(raw, nome, caminho)
    # `bool` e subclasse de `int`: sem esta linha, `true` viraria 1 em silencio.
    if isinstance(valor, bool) or not isinstance(valor, int):
        msg = f"{caminho}.{nome}: esperava inteiro e achei {type(valor).__name__}"
        raise InvalidSaveError(msg)
    return valor


def _booleano(raw: Mapping[str, JsonValue], nome: str, caminho: str) -> bool:
    valor = _campo(raw, nome, caminho)
    if not isinstance(valor, bool):
        msg = f"{caminho}.{nome}: esperava booleano e achei {type(valor).__name__}"
        raise InvalidSaveError(msg)
    return valor


def _objeto(raw: Mapping[str, JsonValue], nome: str, caminho: str) -> Mapping[str, JsonValue]:
    valor = _campo(raw, nome, caminho)
    if not isinstance(valor, dict):
        msg = f"{caminho}.{nome}: esperava objeto e achei {type(valor).__name__}"
        raise InvalidSaveError(msg)
    return valor


def _lista(raw: Mapping[str, JsonValue], nome: str, caminho: str) -> Sequence[JsonValue]:
    valor = _campo(raw, nome, caminho)
    if not isinstance(valor, list):
        msg = f"{caminho}.{nome}: esperava lista e achei {type(valor).__name__}"
        raise InvalidSaveError(msg)
    return valor


def _sub(valor: JsonValue, caminho: str) -> Mapping[str, JsonValue]:
    if not isinstance(valor, dict):
        msg = f"{caminho}: esperava objeto e achei {type(valor).__name__}"
        raise InvalidSaveError(msg)
    return valor


def _inteiro_decimal(texto: str, caminho: str) -> int:
    try:
        return int(texto)
    except ValueError as erro:
        msg = f"{caminho}: {texto!r} nao e um inteiro decimal"
        raise InvalidSaveError(msg) from erro


# ------------------------------------------------------------ codecs --------


def dump_rng(rng: RngState) -> dict[str, JsonValue]:
    if isinstance(rng, SplitMix64):
        # A seed vai como texto decimal: 64 bits estouram a precisao de numero
        # em JavaScript, e um dia alguem vai abrir este save num navegador.
        return {"kind": rng.kind, "seed": str(rng.seed), "counter": rng.counter}
    return {"kind": rng.kind, "script": list(rng.script), "cursor": rng.cursor}


def load_rng(raw: Mapping[str, JsonValue], caminho: str = "rng") -> RngState:
    kind = _texto(raw, "kind", caminho)
    if kind == "splitmix64":
        return SplitMix64(
            seed=_inteiro_decimal(_texto(raw, "seed", caminho), f"{caminho}.seed"),
            counter=_inteiro(raw, "counter", caminho),
        )
    if kind == "scripted":
        bruto = _lista(raw, "script", caminho)
        valores: list[int] = []
        for indice, item in enumerate(bruto):
            if isinstance(item, bool) or not isinstance(item, int):
                msg = f"{caminho}.script[{indice}]: esperava inteiro"
                raise InvalidSaveError(msg)
            valores.append(item)
        return ScriptedRng(script=tuple(valores), cursor=_inteiro(raw, "cursor", caminho))

    msg = f"{caminho}.kind: gerador desconhecido {kind!r}"
    raise InvalidSaveError(msg)


def dump_dice_term(term: DiceTerm) -> dict[str, JsonValue]:
    return {
        "count": term.count,
        "faces": term.faces,
        "doubles_on_crit": term.doubles_on_crit,
    }


def load_dice_term(raw: Mapping[str, JsonValue], caminho: str) -> DiceTerm:
    return DiceTerm(
        count=_inteiro(raw, "count", caminho),
        faces=_inteiro(raw, "faces", caminho),
        doubles_on_crit=_booleano(raw, "doubles_on_crit", caminho),
    )


def dump_damage_expr(expr: DamageExpr) -> dict[str, JsonValue]:
    return {"terms": [dump_dice_term(t) for t in expr.terms], "flat": expr.flat}


def load_damage_expr(raw: Mapping[str, JsonValue], caminho: str) -> DamageExpr:
    return DamageExpr(
        terms=tuple(
            load_dice_term(_sub(item, f"{caminho}.terms[{i}]"), f"{caminho}.terms[{i}]")
            for i, item in enumerate(_lista(raw, "terms", caminho))
        ),
        flat=_inteiro(raw, "flat", caminho),
    )


def dump_die_roll(roll: DieRoll) -> dict[str, JsonValue]:
    return {
        "term_index": roll.term_index,
        "faces": roll.faces,
        "value": roll.value,
        "from_crit": roll.from_crit,
    }


def load_die_roll(raw: Mapping[str, JsonValue], caminho: str) -> DieRoll:
    return DieRoll(
        term_index=_inteiro(raw, "term_index", caminho),
        faces=_inteiro(raw, "faces", caminho),
        value=_inteiro(raw, "value", caminho),
        from_crit=_booleano(raw, "from_crit", caminho),
    )


def dump_damage_roll(roll: DamageRoll) -> dict[str, JsonValue]:
    return {
        "dice": [dump_die_roll(d) for d in roll.dice],
        "flat": roll.flat,
        "ability_bonus": roll.ability_bonus,
        "critical": roll.critical,
        "total": roll.total,
    }


def load_damage_roll(raw: Mapping[str, JsonValue], caminho: str) -> DamageRoll:
    return DamageRoll(
        dice=tuple(
            load_die_roll(_sub(item, f"{caminho}.dice[{i}]"), f"{caminho}.dice[{i}]")
            for i, item in enumerate(_lista(raw, "dice", caminho))
        ),
        flat=_inteiro(raw, "flat", caminho),
        ability_bonus=_inteiro(raw, "ability_bonus", caminho),
        critical=_booleano(raw, "critical", caminho),
        total=_inteiro(raw, "total", caminho),
    )


def dump_abilities(abilities: Abilities) -> dict[str, JsonValue]:
    return {
        "forca": abilities.forca,
        "destreza": abilities.destreza,
        "constituicao": abilities.constituicao,
        "inteligencia": abilities.inteligencia,
        "sabedoria": abilities.sabedoria,
        "carisma": abilities.carisma,
    }


def load_abilities(raw: Mapping[str, JsonValue], caminho: str) -> Abilities:
    return Abilities(
        forca=_inteiro(raw, "forca", caminho),
        destreza=_inteiro(raw, "destreza", caminho),
        constituicao=_inteiro(raw, "constituicao", caminho),
        inteligencia=_inteiro(raw, "inteligencia", caminho),
        sabedoria=_inteiro(raw, "sabedoria", caminho),
        carisma=_inteiro(raw, "carisma", caminho),
    )


def dump_hit_points(hp: HitPoints) -> dict[str, JsonValue]:
    return {"current": hp.current, "maximum": hp.maximum}


def load_hit_points(raw: Mapping[str, JsonValue], caminho: str) -> HitPoints:
    return HitPoints(
        current=_inteiro(raw, "current", caminho),
        maximum=_inteiro(raw, "maximum", caminho),
    )


def dump_attack_profile(profile: AttackProfile) -> dict[str, JsonValue]:
    return {
        "id": str(profile.id),
        "name": profile.name,
        "ability": profile.ability.value,
        "proficient": profile.proficient,
        "damage": dump_damage_expr(profile.damage),
    }


def load_attack_profile(raw: Mapping[str, JsonValue], caminho: str) -> AttackProfile:
    sigla = _texto(raw, "ability", caminho)
    try:
        ability = Ability(sigla)
    except ValueError as erro:
        msg = f"{caminho}.ability: atributo desconhecido {sigla!r}"
        raise InvalidSaveError(msg) from erro

    return AttackProfile(
        id=AttackId(_texto(raw, "id", caminho)),
        name=_texto(raw, "name", caminho),
        ability=ability,
        proficient=_booleano(raw, "proficient", caminho),
        damage=load_damage_expr(_objeto(raw, "damage", caminho), f"{caminho}.damage"),
    )


def dump_statblock(sb: Statblock) -> dict[str, JsonValue]:
    return {
        "id": str(sb.id),
        "name": sb.name,
        "abilities": dump_abilities(sb.abilities),
        "armor_class": sb.armor_class,
        "max_hp": sb.max_hp,
        "proficiency_bonus": sb.proficiency_bonus,
        "speed_ft": sb.speed_ft,
        "attacks": [dump_attack_profile(a) for a in sb.attacks],
    }


def load_statblock(raw: Mapping[str, JsonValue], caminho: str) -> Statblock:
    return Statblock(
        id=StatblockId(_texto(raw, "id", caminho)),
        name=_texto(raw, "name", caminho),
        abilities=load_abilities(_objeto(raw, "abilities", caminho), f"{caminho}.abilities"),
        armor_class=_inteiro(raw, "armor_class", caminho),
        max_hp=_inteiro(raw, "max_hp", caminho),
        proficiency_bonus=_inteiro(raw, "proficiency_bonus", caminho),
        speed_ft=_inteiro(raw, "speed_ft", caminho),
        attacks=tuple(
            load_attack_profile(_sub(item, f"{caminho}.attacks[{i}]"), f"{caminho}.attacks[{i}]")
            for i, item in enumerate(_lista(raw, "attacks", caminho))
        ),
    )


def dump_turn_budget(budget: TurnBudget) -> dict[str, JsonValue]:
    return {
        "action_available": budget.action_available,
        "movement_remaining_ft": budget.movement_remaining_ft,
    }


def load_turn_budget(raw: Mapping[str, JsonValue], caminho: str) -> TurnBudget:
    return TurnBudget(
        action_available=_booleano(raw, "action_available", caminho),
        movement_remaining_ft=_inteiro(raw, "movement_remaining_ft", caminho),
    )


def dump_combatant(c: Combatant) -> dict[str, JsonValue]:
    return {
        "id": str(c.id),
        "statblock_id": str(c.statblock_id),
        "team": c.team,
        "hp": dump_hit_points(c.hp),
        "budget": dump_turn_budget(c.budget),
    }


def load_combatant(raw: Mapping[str, JsonValue], caminho: str) -> Combatant:
    return Combatant(
        id=CreatureId(_texto(raw, "id", caminho)),
        statblock_id=StatblockId(_texto(raw, "statblock_id", caminho)),
        team=_texto(raw, "team", caminho),
        hp=load_hit_points(_objeto(raw, "hp", caminho), f"{caminho}.hp"),
        budget=load_turn_budget(_objeto(raw, "budget", caminho), f"{caminho}.budget"),
    )


def dump_turn_order(order: TurnOrder) -> dict[str, JsonValue]:
    return {
        "order": [str(cid) for cid in order.order],
        "current": str(order.current),
        "round_number": order.round_number,
    }


def load_turn_order(raw: Mapping[str, JsonValue], caminho: str) -> TurnOrder:
    ids: list[CreatureId] = []
    for indice, item in enumerate(_lista(raw, "order", caminho)):
        if not isinstance(item, str):
            msg = f"{caminho}.order[{indice}]: esperava texto"
            raise InvalidSaveError(msg)
        ids.append(CreatureId(item))

    return TurnOrder(
        order=tuple(ids),
        current=CreatureId(_texto(raw, "current", caminho)),
        round_number=_inteiro(raw, "round_number", caminho),
    )


def dump_state(state: CombatState) -> dict[str, JsonValue]:
    """O estado sem envelope. Use `dump` para salvar de verdade."""
    return {
        "statblocks": {str(k): dump_statblock(v) for k, v in state.statblocks.items()},
        "combatants": {str(k): dump_combatant(v) for k, v in state.combatants.items()},
        "turn_order": dump_turn_order(state.turn_order),
        "rng": dump_rng(state.rng),
    }


def load_state(raw: Mapping[str, JsonValue], caminho: str = "state") -> CombatState:
    """O estado sem envelope, ja com as invariantes conferidas."""
    fichas = _objeto(raw, "statblocks", caminho)
    lutadores = _objeto(raw, "combatants", caminho)

    state = CombatState(
        statblocks={
            StatblockId(k): load_statblock(
                _sub(v, f"{caminho}.statblocks[{k!r}]"), f"{caminho}.statblocks[{k!r}]"
            )
            for k, v in fichas.items()
        },
        combatants={
            CreatureId(k): load_combatant(
                _sub(v, f"{caminho}.combatants[{k!r}]"), f"{caminho}.combatants[{k!r}]"
            )
            for k, v in lutadores.items()
        },
        turn_order=load_turn_order(_objeto(raw, "turn_order", caminho), f"{caminho}.turn_order"),
        rng=load_rng(_objeto(raw, "rng", caminho), f"{caminho}.rng"),
    )

    problemas = check_invariants(state)
    if problemas:
        msg = "save inconsistente: " + "; ".join(problemas)
        raise InvalidSaveError(msg)
    return state


# ------------------------------------------------------------ envelope ------


def dump(state: CombatState) -> dict[str, JsonValue]:
    """Empacota o estado com tudo que e preciso para reabri-lo com seguranca."""
    return {
        "schema_version": SCHEMA_VERSION,
        "rules_version": RULES_VERSION,
        "rng_algo": ALGORITHM,
        "state": dump_state(state),
    }


def load(payload: Mapping[str, JsonValue]) -> CombatState:
    """Desempacota um save.

    Versao de formato desconhecida e recusada. Versao de **regras** diferente
    passa: o save ainda descreve um estado valido, e recusa-lo tornaria
    impossivel migrar. Quem quiser saber se o resultado vai divergir le
    `rules_version` do envelope antes de chamar.
    """
    versao = _inteiro(payload, "schema_version", "envelope")
    if versao != SCHEMA_VERSION:
        msg = f"save em schema_version {versao}; este motor le {SCHEMA_VERSION}"
        raise UnsupportedSchemaVersion(msg)

    algoritmo = _texto(payload, "rng_algo", "envelope")
    if algoritmo != ALGORITHM:
        msg = f"save gerado com {algoritmo!r}; este motor usa {ALGORITHM!r}"
        raise UnsupportedSchemaVersion(msg)

    return load_state(_objeto(payload, "state", "envelope"))


# --------------------------------------------------------- invariantes ------


def check_invariants(state: CombatState) -> tuple[str, ...]:
    """Lista o que esta inconsistente no estado. Vazio quer dizer coerente.

    Devolve em vez de levantar para que cada chamador escolha o erro certo:
    `load` levanta `InvalidSaveError` (dado externo), enquanto o motor, se um
    dia chamar isto sobre um estado que ele mesmo montou, levanta
    `CorruptStateError` (bug nosso).
    """
    problemas: list[str] = []

    for cid, c in state.combatants.items():
        if c.id != cid:
            problemas.append(f"combatente sob a chave {cid!r} se diz {c.id!r}")
        if c.statblock_id not in state.statblocks:
            problemas.append(f"{cid!r} aponta para a ficha inexistente {c.statblock_id!r}")
        if c.hp.maximum < 1:
            problemas.append(f"{cid!r} tem hp maximo {c.hp.maximum}")
        if not 0 <= c.hp.current <= c.hp.maximum:
            problemas.append(f"{cid!r} tem hp {c.hp.current} fora de 0..{c.hp.maximum}")
        if c.budget.movement_remaining_ft < 0:
            problemas.append(f"{cid!r} tem movimento negativo")

    for sid, sb in state.statblocks.items():
        if sb.id != sid:
            problemas.append(f"ficha sob a chave {sid!r} se diz {sb.id!r}")

    ordem = state.turn_order.order
    if len(set(ordem)) != len(ordem):
        problemas.append("a ordem de iniciativa tem id repetido")
    if set(ordem) != set(state.combatants):
        problemas.append("a ordem de iniciativa nao bate com a lista de combatentes")
    if state.turn_order.current not in ordem:
        problemas.append(f"o turno e de {state.turn_order.current!r}, que nao esta na ordem")
    if state.turn_order.round_number < 1:
        problemas.append(f"rodada {state.turn_order.round_number}; a primeira e 1")

    return tuple(problemas)


# ---------------------------------------------------------- fingerprint -----


def canonical_json(payload: Mapping[str, JsonValue]) -> str:
    """JSON canonico: chaves ordenadas, sem espaco supérfluo, UTF-8 preservado.

    Canonico para que dois estados iguais deem sempre o mesmo texto, e portanto
    o mesmo `fingerprint`, em qualquer maquina e qualquer versao.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(state: CombatState) -> str:
    """Resumo de 64 hex do estado inteiro.

    Serve para o teste de determinismo dizer "divergiu" numa linha, em vez de
    comparar duas arvores de dataclass e deixar quem le achar a diferenca.
    """
    texto = canonical_json(dump_state(state))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# -------------------------------------------------------------- eventos -----
# Eventos so tem ida: eles saem do motor para o log, para a interface e para o
# golden, e nunca voltam para dentro. Um `load` de evento seria codigo sem
# consumidor -- o que reconstroi estado e `load_state`, a partir do save.


def dump_initiative_rolled(event: InitiativeRolled) -> dict[str, JsonValue]:
    return {
        "kind": event.kind,
        "creature": str(event.creature),
        "d20": event.d20,
        "dex_mod": event.dex_mod,
        "dex_score": event.dex_score,
        "total": event.total,
        "rng_before": event.rng_before,
        "rng_after": event.rng_after,
    }


def dump_turn_order_set(event: TurnOrderSet) -> dict[str, JsonValue]:
    return {"kind": event.kind, "order": [str(cid) for cid in event.order]}


def dump_round_started(event: RoundStarted) -> dict[str, JsonValue]:
    return {"kind": event.kind, "round_number": event.round_number}


def dump_turn_started(event: TurnStarted) -> dict[str, JsonValue]:
    return {
        "kind": event.kind,
        "creature": str(event.creature),
        "budget": dump_turn_budget(event.budget),
    }


def dump_turn_ended(event: TurnEnded) -> dict[str, JsonValue]:
    return {"kind": event.kind, "creature": str(event.creature)}


def dump_turn_skipped(event: TurnSkipped) -> dict[str, JsonValue]:
    return {
        "kind": event.kind,
        "creature": str(event.creature),
        "reason": event.reason.value,
    }


def dump_movement_spent(event: MovementSpent) -> dict[str, JsonValue]:
    return {
        "kind": event.kind,
        "creature": str(event.creature),
        "feet": event.feet,
        "remaining_ft": event.remaining_ft,
    }


def dump_combat_outcome(outcome: CombatOutcome) -> dict[str, JsonValue]:
    return {"winning_team": outcome.winning_team, "last_round": outcome.last_round}


def load_combat_outcome(raw: Mapping[str, JsonValue], caminho: str) -> CombatOutcome:
    vencedor = _campo(raw, "winning_team", caminho)
    if vencedor is not None and not isinstance(vencedor, str):
        msg = f"{caminho}.winning_team: esperava texto ou nulo"
        raise InvalidSaveError(msg)
    return CombatOutcome(
        winning_team=vencedor,
        last_round=_inteiro(raw, "last_round", caminho),
    )


def dump_combat_ended(event: CombatEnded) -> dict[str, JsonValue]:
    return {"kind": event.kind, "outcome": dump_combat_outcome(event.outcome)}


def dump_attack_rolled(event: AttackRolled) -> dict[str, JsonValue]:
    return {
        "kind": event.kind,
        "actor": str(event.actor),
        "target": str(event.target),
        "attack_id": str(event.attack_id),
        "attack_name": event.attack_name,
        "advantage": event.advantage.value,
        "advantage_sources": list(event.advantage_sources),
        "disadvantage_sources": list(event.disadvantage_sources),
        "pair": list(event.pair),
        "chosen_index": event.chosen_index,
        "natural": event.natural,
        "ability": event.ability.value,
        "ability_mod": event.ability_mod,
        "proficiency": event.proficiency,
        "total": event.total,
        "target_ac": event.target_ac,
        "target_was_down": event.target_was_down,
        "outcome": event.outcome.value,
        "rng_before": event.rng_before,
        "rng_after": event.rng_after,
    }


def dump_damage_rolled(event: DamageRolled) -> dict[str, JsonValue]:
    return {
        "kind": event.kind,
        "actor": str(event.actor),
        "target": str(event.target),
        "roll": dump_damage_roll(event.roll),
        "rng_before": event.rng_before,
        "rng_after": event.rng_after,
    }


def dump_hp_changed(event: HpChanged) -> dict[str, JsonValue]:
    return {
        "kind": event.kind,
        "creature": str(event.creature),
        "before": dump_hit_points(event.before),
        "after": dump_hit_points(event.after),
        "dealt": event.dealt,
        "overkill": event.overkill,
    }


def dump_creature_downed(event: CreatureDowned) -> dict[str, JsonValue]:
    return {"kind": event.kind, "creature": str(event.creature)}


def event_to_dict(event: Event) -> dict[str, JsonValue]:
    """Um evento em forma serializavel, escolhido pelo `kind`."""
    match event:
        case InitiativeRolled():
            return dump_initiative_rolled(event)
        case TurnOrderSet():
            return dump_turn_order_set(event)
        case RoundStarted():
            return dump_round_started(event)
        case TurnStarted():
            return dump_turn_started(event)
        case TurnSkipped():
            return dump_turn_skipped(event)
        case TurnEnded():
            return dump_turn_ended(event)
        case MovementSpent():
            return dump_movement_spent(event)
        case AttackRolled():
            return dump_attack_rolled(event)
        case DamageRolled():
            return dump_damage_rolled(event)
        case HpChanged():
            return dump_hp_changed(event)
        case CreatureDowned():
            return dump_creature_downed(event)
        case CombatEnded():
            return dump_combat_ended(event)
        case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
            assert_never(event)


def events_to_list(events: Sequence[Event]) -> list[JsonValue]:
    return [event_to_dict(e) for e in events]


def events_digest(events: Sequence[Event]) -> str:
    """Resumo de 64 hex do log inteiro.

    Dois combates podem terminar no mesmo estado por caminhos diferentes -- o
    `fingerprint` do estado nao veria a diferenca, e este ve. E o par dos dois
    que faz um teste de determinismo dizer "divergiu" numa linha em vez de
    deixar quem le comparar duas arvores de dataclass.
    """
    texto = canonical_json({"events": events_to_list(events)})
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()

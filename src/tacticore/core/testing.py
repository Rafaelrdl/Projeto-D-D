"""Construtores de encontro para teste.

Mora **dentro** do pacote, e nao em `tests/`, por dois motivos: fica sob mypy
strict junto com o resto, e um dia serve a quem for escrever cenario fora deste
repositorio.

Tudo aqui e funcao pura com default para cada campo, de modo que um teste
escreva so o que importa para ele::

    estado = make_state(combatants=(make_combatant(id="goblin_1", hp=1),))

Sem isso, cada teste de regra carregaria vinte linhas de montagem de ficha, e
quem le o teste teria que caçar qual dos vinte valores e o relevante.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from tacticore.core.dice import DamageExpr, parse_dice
from tacticore.core.enums import Ability
from tacticore.core.ids import AttackId, CreatureId, StatblockId
from tacticore.core.model import (
    Abilities,
    AttackProfile,
    Combatant,
    CombatState,
    HitPoints,
    Statblock,
    TurnBudget,
    TurnOrder,
)
from tacticore.core.rng import RngState, ScriptedRng

PADRAO_ATRIBUTO = 10
"""Modificador zero. Um teste que nao fala de atributo nao deveria ganhar um."""


def make_abilities(
    *,
    forca: int = PADRAO_ATRIBUTO,
    destreza: int = PADRAO_ATRIBUTO,
    constituicao: int = PADRAO_ATRIBUTO,
    inteligencia: int = PADRAO_ATRIBUTO,
    sabedoria: int = PADRAO_ATRIBUTO,
    carisma: int = PADRAO_ATRIBUTO,
) -> Abilities:
    return Abilities(
        forca=forca,
        destreza=destreza,
        constituicao=constituicao,
        inteligencia=inteligencia,
        sabedoria=sabedoria,
        carisma=carisma,
    )


def make_attack(
    *,
    id: str = "ataque",
    name: str = "Ataque",
    ability: Ability = Ability.FOR,
    proficient: bool = True,
    damage: str | DamageExpr = "1d6",
) -> AttackProfile:
    """Aceita a notacao em string por conveniencia de quem escreve o teste."""
    return AttackProfile(
        id=AttackId(id),
        name=name,
        ability=ability,
        proficient=proficient,
        damage=parse_dice(damage) if isinstance(damage, str) else damage,
    )


def make_statblock(
    *,
    id: str = "ficha",
    name: str = "Criatura",
    abilities: Abilities | None = None,
    armor_class: int = 12,
    max_hp: int = 10,
    proficiency_bonus: int = 2,
    speed_ft: int = 30,
    attacks: Iterable[AttackProfile] | None = None,
) -> Statblock:
    return Statblock(
        id=StatblockId(id),
        name=name,
        abilities=make_abilities() if abilities is None else abilities,
        armor_class=armor_class,
        max_hp=max_hp,
        proficiency_bonus=proficiency_bonus,
        speed_ft=speed_ft,
        attacks=(make_attack(),) if attacks is None else tuple(attacks),
    )


def make_budget(*, action_available: bool = True, movement_remaining_ft: int = 30) -> TurnBudget:
    return TurnBudget(
        action_available=action_available,
        movement_remaining_ft=movement_remaining_ft,
    )


def make_combatant(
    *,
    id: str = "heroi",
    statblock_id: str = "ficha",
    team: str = "herois",
    hp: int | HitPoints | None = None,
    max_hp: int = 10,
    budget: TurnBudget | None = None,
) -> Combatant:
    """`hp` aceita um int para o caso comum de "quero este com 1 de vida"."""
    if hp is None:
        pontos = HitPoints(current=max_hp, maximum=max_hp)
    elif isinstance(hp, int):
        pontos = HitPoints(current=hp, maximum=max_hp)
    else:
        pontos = hp

    return Combatant(
        id=CreatureId(id),
        statblock_id=StatblockId(statblock_id),
        team=team,
        hp=pontos,
        budget=make_budget() if budget is None else budget,
    )


def make_state(
    *,
    statblocks: Iterable[Statblock] | None = None,
    combatants: Iterable[Combatant] | None = None,
    order: Iterable[str] | None = None,
    current: str | None = None,
    round_number: int = 1,
    rng: RngState | None = None,
) -> CombatState:
    """Monta um estado consistente a partir do pouco que o teste informar.

    A ordem de iniciativa, quando omitida, e a ordem em que os combatentes
    foram passados -- deterministica e obvia na leitura do teste. Isto **nao**
    substitui `start_combat`: aqui nada e rolado e nada e validado, de
    proposito, para que um teste possa montar tambem o estado esquisito de que
    precisa.
    """
    fichas = (make_statblock(),) if statblocks is None else tuple(statblocks)
    lutadores = (make_combatant(),) if combatants is None else tuple(combatants)

    ids = (
        tuple(CreatureId(c) for c in order) if order is not None else tuple(c.id for c in lutadores)
    )
    ativo = CreatureId(current) if current is not None else ids[0]

    catalogo: Mapping[StatblockId, Statblock] = {f.id: f for f in fichas}
    participantes: Mapping[CreatureId, Combatant] = {c.id: c for c in lutadores}

    return CombatState(
        statblocks=catalogo,
        combatants=participantes,
        turn_order=TurnOrder(order=ids, current=ativo, round_number=round_number),
        rng=ScriptedRng(script=()) if rng is None else rng,
    )

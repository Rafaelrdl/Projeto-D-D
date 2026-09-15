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

from collections.abc import Iterable, Mapping, Sequence
from typing import assert_never

from tacticore.core.dice import DamageExpr, parse_dice
from tacticore.core.engine import (
    Participant,
    apply,
    combat_result,
    legal_actions,
)
from tacticore.core.enums import Ability
from tacticore.core.errors import CorruptStateError
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
    CombatState,
    HitPoints,
    Statblock,
    TurnBudget,
    TurnOrder,
)
from tacticore.core.results import Applied
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


def make_participant(
    *,
    id: str = "heroi",
    statblock_id: str = "ficha",
    team: str = "herois",
) -> Participant:
    return Participant(id=CreatureId(id), statblock_id=StatblockId(statblock_id), team=team)


def make_duelo(
    *,
    a: str = "heroi",
    b: str = "vilao",
    ficha_a: Statblock | None = None,
    ficha_b: Statblock | None = None,
) -> tuple[dict[StatblockId, Statblock], tuple[Participant, ...]]:
    """Um encontro de dois, um de cada time: o menor combate que existe.

    Devolve `(catalogo, participantes)` no formato que `start_combat` pede, e e
    o ponto de partida da maioria dos testes de motor.
    """
    primeira = make_statblock(id=f"ficha_{a}", name=a) if ficha_a is None else ficha_a
    segunda = make_statblock(id=f"ficha_{b}", name=b) if ficha_b is None else ficha_b

    catalogo = {primeira.id: primeira, segunda.id: segunda}
    participantes = (
        make_participant(id=a, statblock_id=str(primeira.id), team="herois"),
        make_participant(id=b, statblock_id=str(segunda.id), team="viloes"),
    )
    return catalogo, participantes


def tape_from_events(events: Sequence[Event]) -> tuple[int, ...]:
    """A fita de dados que um log descreve, na ordem em que foram rolados.

    Substitui um "RNG que grava": gravar exigiria um acumulador mutavel e um
    quarto membro na uniao `RngState`, e os eventos ja publicam cada dado cru.
    Com isto, um bug encontrado com seed de producao vira teste de regressao
    com fita explicita em trinta segundos.

    Tambem serve de prova de completude do log: reproduzir o combate com esta
    fita tem que dar exatamente o mesmo log de volta. Se um dado tivesse sido
    rolado sem aparecer em evento nenhum, a fita ficaria curta e a reproducao
    estouraria com `RngExhausted`.
    """
    dados: list[int] = []
    for evento in events:
        match evento:
            case InitiativeRolled():
                dados.append(evento.d20)
            case AttackRolled():
                dados.extend(evento.pair)
            case DamageRolled():
                dados.extend(d.value for d in evento.roll.dice)
            # Os que nao rolam dado sao listados um a um, e nao varridos por um
            # `case _`. Esquecer um evento de rolagem NOVO num `case _` nao da
            # erro de mypy nem de lint: estoura como `RngExhausted` dentro de
            # `rng.roll_die`, tres modulos longe da causa.
            case (
                TurnOrderSet()
                | RoundStarted()
                | TurnStarted()
                | TurnSkipped()
                | TurnEnded()
                | MovementSpent()
                | HpChanged()
                | CreatureDowned()
                | CombatEnded()
            ):
                continue
            case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
                assert_never(evento)
    return tuple(dados)


def play_out(
    state: CombatState,
    *,
    max_actions: int = 500,
) -> tuple[CombatState, tuple[Event, ...]]:
    """Joga o combate ate o fim escolhendo sempre a **primeira** acao legal.

    Nao e uma IA e nao tenta ser: e um piloto automatico deterministico, que e
    o que um teste de determinismo e um golden precisam. A primeira acao legal
    e sempre atacar o primeiro inimigo de pe, entao o combate termina.

    O limite de acoes existe para que um bug de regra vire uma falha de teste
    legivel em vez de um processo travado.
    """
    atual = state
    log: list[Event] = []

    for _ in range(max_actions):
        if combat_result(atual) is not None:
            return atual, tuple(log)

        acoes = legal_actions(atual)
        if not acoes:
            msg = f"sem acao legal para {atual.turn_order.current!r} e o combate nao acabou"
            raise CorruptStateError(msg)

        resultado = apply(atual, acoes[0])
        if not isinstance(resultado, Applied):  # pragma: no cover
            # Inalcancavel enquanto valer a propriedade central de
            # `legal_actions`, que tem teste proprio em test_combat_end.py.
            # Fica aqui assim mesmo: no dia em que a propriedade quebrar, o
            # piloto automatico para com o motivo na mao em vez de seguir
            # produzindo um log errado que o golden depois congela.
            msg = f"legal_actions ofereceu {acoes[0]}, recusada com {resultado.reason}"
            raise CorruptStateError(msg)

        atual = resultado.state
        log.extend(resultado.events)

    msg = f"o combate nao terminou em {max_actions} acoes"
    raise CorruptStateError(msg)

"""A orquestracao: compoe as regras puras sobre o estado de combate.

Esta e a unica camada que conhece o `CombatState`. As regras de `rules.py`
recebem numeros; quem sabe de quem e o turno, quem esta de pe e o que ja foi
gasto e daqui.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from tacticore.core.enums import Ability
from tacticore.core.errors import InvalidEncounterError
from tacticore.core.events import (
    Event,
    InitiativeRolled,
    RoundStarted,
    TurnOrderSet,
    TurnStarted,
)
from tacticore.core.ids import CreatureId, StatblockId
from tacticore.core.model import (
    Combatant,
    CombatState,
    HitPoints,
    Statblock,
    TurnBudget,
    TurnOrder,
)
from tacticore.core.queries import statblock_of
from tacticore.core.results import Applied
from tacticore.core.rng import RngState, position, roll_die
from tacticore.core.rules import (
    D20_FACES,
    InitiativeEntry,
    ability_modifier,
    ability_score,
    initiative_sort_key,
)

PRIMEIRA_RODADA = 1
MINIMO_DE_PARTICIPANTES = 2
MINIMO_DE_TIMES = 2


@dataclass(frozen=True, slots=True, kw_only=True)
class Participant:
    """Quem entra no combate, antes de haver combate.

    Mora aqui e nao em `model.py` de proposito: e **entrada** de
    `start_combat`, e nao estado. Em `model.py` ela exigiria codec de
    serializacao -- e um codec para uma coisa que nunca aparece num save e
    codigo morto que alguem teria que manter.
    """

    id: CreatureId
    statblock_id: StatblockId
    team: str


def _validar_encontro(
    statblocks: Mapping[StatblockId, Statblock],
    participants: tuple[Participant, ...],
) -> None:
    """Recusa encontro que nao descreve um combate possivel.

    Sem isto, a afirmacao que sustenta o desenho -- "`start_combat` sempre
    devolve combate em andamento, logo `current` pode ser obrigatorio e nao
    existe fase SETUP" -- seria falsa: um encontro de um time so ja nasceria
    terminado, e um sem participante nem teria de quem fosse o turno.
    """
    problemas: list[str] = []

    if len(participants) < MINIMO_DE_PARTICIPANTES:
        problemas.append(f"um combate precisa de ao menos {MINIMO_DE_PARTICIPANTES} participantes")

    ids = [p.id for p in participants]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        problemas.append(f"id repetido entre os participantes: {repetidos}")

    for p in participants:
        ficha = statblocks.get(p.statblock_id)
        if ficha is None:
            problemas.append(f"{p.id!r} aponta para a ficha inexistente {p.statblock_id!r}")
        elif ficha.max_hp < 1:
            problemas.append(f"a ficha {p.statblock_id!r} tem vida maxima {ficha.max_hp}")

    times = {p.team for p in participants}
    if len(times) < MINIMO_DE_TIMES:
        problemas.append(
            f"um combate precisa de ao menos {MINIMO_DE_TIMES} times; achei {len(times)}"
        )

    if problemas:
        msg = "encontro invalido: " + "; ".join(problemas)
        raise InvalidEncounterError(msg)


def _orcamento_inicial(statblock: Statblock) -> TurnBudget:
    """O orcamento com que um turno comeca: uma acao e o deslocamento da ficha."""
    return TurnBudget(action_available=True, movement_remaining_ft=statblock.speed_ft)


def start_combat(
    *,
    statblocks: Mapping[StatblockId, Statblock],
    participants: Iterable[Participant],
    rng: RngState,
) -> Applied:
    """Monta o combate: rola iniciativa, ordena e abre o primeiro turno.

    Devolve `Applied` como qualquer outra acao, e nao um `CombatState` pelado:
    a iniciativa **e** uma sequencia de rolagens, e escondê-las tornaria a
    montagem a unica parte do motor que consome o RNG sem deixar rastro.

    As rolagens percorrem os participantes em ordem lexicografica de id, e nao
    na ordem em que foram passados. E o que faz o mesmo encontro com a mesma
    seed dar a mesma ordem mesmo quando quem monta embaralha a lista.
    """
    inscritos = tuple(participants)
    _validar_encontro(statblocks, inscritos)

    por_id = {p.id: p for p in inscritos}
    eventos: list[Event] = []
    entradas: list[InitiativeEntry] = []
    atual = rng

    for cid in sorted(por_id, key=str):
        ficha = statblocks[por_id[cid].statblock_id]
        dex_score = ability_score(ficha.abilities, Ability.DES)
        dex_mod = ability_modifier(dex_score)

        antes = position(atual)
        d20, atual = roll_die(atual, D20_FACES)
        total = d20 + dex_mod

        entradas.append(
            InitiativeEntry(
                creature=cid,
                d20=d20,
                dex_mod=dex_mod,
                dex_score=dex_score,
                total=total,
            )
        )
        eventos.append(
            InitiativeRolled(
                creature=cid,
                d20=d20,
                dex_mod=dex_mod,
                dex_score=dex_score,
                total=total,
                rng_before=antes,
                rng_after=position(atual),
            )
        )

    ordem = tuple(e.creature for e in sorted(entradas, key=initiative_sort_key))
    primeiro = ordem[0]

    combatentes: dict[CreatureId, Combatant] = {}
    for cid in ordem:
        ficha = statblocks[por_id[cid].statblock_id]
        combatentes[cid] = Combatant(
            id=cid,
            statblock_id=ficha.id,
            team=por_id[cid].team,
            hp=HitPoints(current=ficha.max_hp, maximum=ficha.max_hp),
            budget=_orcamento_inicial(ficha),
        )

    state = CombatState(
        statblocks=dict(statblocks),
        combatants=combatentes,
        turn_order=TurnOrder(order=ordem, current=primeiro, round_number=PRIMEIRA_RODADA),
        rng=atual,
    )

    eventos.append(TurnOrderSet(order=ordem))
    eventos.append(RoundStarted(round_number=PRIMEIRA_RODADA))
    eventos.append(
        TurnStarted(creature=primeiro, budget=_orcamento_inicial(statblock_of(state, primeiro)))
    )

    return Applied(state=state, events=tuple(eventos))

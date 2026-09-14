"""A orquestracao: compoe as regras puras sobre o estado de combate.

Esta e a unica camada que conhece o `CombatState`. As regras de `rules.py`
recebem numeros; quem sabe de quem e o turno, quem esta de pe e o que ja foi
gasto e daqui.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import assert_never

from tacticore.core.actions import Action, EndTurnAction, MoveAction
from tacticore.core.enums import Ability, RejectionReason, SkipReason
from tacticore.core.errors import InvalidEncounterError
from tacticore.core.events import (
    Event,
    InitiativeRolled,
    MovementSpent,
    RoundStarted,
    TurnEnded,
    TurnOrderSet,
    TurnSkipped,
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
from tacticore.core.queries import combatant_of, is_standing, statblock_of
from tacticore.core.results import ActionResult, Applied, Rejected
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


def _rejeitar(state: CombatState, reason: RejectionReason, detail: str) -> Rejected:
    return Rejected(reason=reason, detail=detail, state=state)


def validate(state: CombatState, action: Action) -> Rejected | None:
    """Confere a legalidade da acao. `None` quer dizer "pode".

    Roda **inteira antes de qualquer toque no RNG**. Se uma validacao viesse
    depois de uma rolagem, uma acao recusada teria consumido entropia, e dois
    combates com a mesma seed divergiriam so porque um deles tentou uma jogada
    ilegal pelo caminho.
    """
    ator = combatant_of(state, action.actor)
    if ator is None:
        return _rejeitar(
            state, RejectionReason.NO_SUCH_ACTOR, f"{action.actor!r} nao esta neste combate"
        )
    if state.turn_order.current != ator.id:
        return _rejeitar(
            state,
            RejectionReason.NOT_YOUR_TURN,
            f"o turno e de {state.turn_order.current!r}, nao de {ator.id!r}",
        )
    if not is_standing(ator):
        return _rejeitar(state, RejectionReason.ACTOR_IS_DOWN, f"{ator.id!r} esta caido")

    match action:
        case MoveAction():
            if action.distance_ft < 0:
                return _rejeitar(
                    state,
                    RejectionReason.INVALID_DISTANCE,
                    f"distancia negativa: {action.distance_ft}",
                )
            if action.distance_ft > ator.budget.movement_remaining_ft:
                return _rejeitar(
                    state,
                    RejectionReason.NOT_ENOUGH_MOVEMENT,
                    f"{action.distance_ft} pes pedidos e {ator.budget.movement_remaining_ft} "
                    "disponiveis",
                )
        case EndTurnAction():
            pass
        case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
            assert_never(action)

    return None


def _com_combatente(state: CombatState, combatant: Combatant) -> CombatState:
    """O mesmo estado com um combatente trocado."""
    return replace(state, combatants={**state.combatants, combatant.id: combatant})


def advance_turn(state: CombatState) -> tuple[CombatState, tuple[Event, ...]]:
    """Encerra o turno atual e abre o proximo que puder agir.

    Quem esta caido tem o turno pulado **sem reset de orcamento**: nao se ganha
    um turno para depois nao usar, e o `TurnSkipped` sai antes de qualquer
    `TurnStarted`. Ninguem sai da ordem de iniciativa ao cair -- sair mudaria
    a posicao de todo mundo no meio da rodada.

    O laco anda no maximo uma volta inteira. Um estado sem ninguem de pe nao
    tem proximo turno legitimo, e ficar rodando seria travar o processo em vez
    de devolver um estado que o chamador consegue inspecionar.
    """
    ordem = state.turn_order.order
    eventos: list[Event] = [TurnEnded(creature=state.turn_order.current)]

    indice = ordem.index(state.turn_order.current)
    rodada = state.turn_order.round_number
    atual = state

    for _ in range(len(ordem)):
        indice += 1
        if indice == len(ordem):
            indice = 0
            rodada += 1
            eventos.append(RoundStarted(round_number=rodada))

        candidato = atual.combatants[ordem[indice]]
        if not is_standing(candidato):
            eventos.append(TurnSkipped(creature=candidato.id, reason=SkipReason.ACTOR_IS_DOWN))
            continue

        orcamento = _orcamento_inicial(statblock_of(atual, candidato.id))
        atual = _com_combatente(atual, replace(candidato, budget=orcamento))
        atual = replace(
            atual,
            turn_order=replace(atual.turn_order, current=candidato.id, round_number=rodada),
        )
        eventos.append(TurnStarted(creature=candidato.id, budget=orcamento))
        return atual, tuple(eventos)

    # Ninguem de pe: a rodada avancou, mas nao ha turno para abrir.
    atual = replace(atual, turn_order=replace(atual.turn_order, round_number=rodada))
    return atual, tuple(eventos)


def apply(state: CombatState, action: Action) -> ActionResult:
    """O ponto de entrada unico: estado + acao, estado novo + o que aconteceu."""
    rejeicao = validate(state, action)
    if rejeicao is not None:
        return rejeicao

    match action:
        case MoveAction():
            ator = state.combatants[action.actor]
            restante = ator.budget.movement_remaining_ft - action.distance_ft
            novo = _com_combatente(
                state,
                replace(ator, budget=replace(ator.budget, movement_remaining_ft=restante)),
            )
            evento = MovementSpent(creature=ator.id, feet=action.distance_ft, remaining_ft=restante)
            return Applied(state=novo, events=(evento,))

        case EndTurnAction():
            novo, eventos = advance_turn(state)
            return Applied(state=novo, events=eventos)

        case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
            assert_never(action)

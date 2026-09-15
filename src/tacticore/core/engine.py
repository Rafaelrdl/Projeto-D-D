"""A orquestracao: compoe as regras puras sobre o estado de combate.

Esta e a unica camada que conhece o `CombatState`. As regras de `rules.py`
recebem numeros; quem sabe de quem e o turno, quem esta de pe e o que ja foi
gasto e daqui.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import assert_never

from tacticore.core.actions import (
    Action,
    AttackAction,
    EndTurnAction,
    MoveAction,
    StandUpAction,
)
from tacticore.core.dice import roll_damage
from tacticore.core.enums import (
    Ability,
    AttackOutcome,
    Condition,
    RejectionReason,
    SkipReason,
    canonical_conditions,
)
from tacticore.core.errors import CorruptStateError, InvalidEncounterError
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
    StoodUp,
    TurnEnded,
    TurnOrderSet,
    TurnSkipped,
    TurnStarted,
)
from tacticore.core.ids import CreatureId, StatblockId
from tacticore.core.model import (
    PES_POR_CASA,
    Combatant,
    CombatOutcome,
    CombatState,
    HitPoints,
    Position,
    Statblock,
    TurnBudget,
    TurnOrder,
)
from tacticore.core.queries import (
    attack_of,
    combatant_of,
    conscious_teams,
    derive_advantage_sources,
    is_conscious,
    statblock_of,
)
from tacticore.core.results import ActionResult, Applied, Rejected
from tacticore.core.rng import RngState, position, roll_die
from tacticore.core.rules import (
    D20_FACES,
    InitiativeEntry,
    ability_modifier,
    ability_score,
    apply_damage,
    attack_math,
    classify_attack,
    d20_check,
    distance_ft,
    initiative_sort_key,
    resolve_advantage,
    roll_d20,
    stand_up_cost_ft,
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
    position: Position
    """Onde ele comeca. Quem monta o encontro escolhe -- posicao inicial e
    conteudo, nao regra, e o motor nao tem opiniao sobre formacao."""

    conditions: tuple[Condition, ...] = ()
    """Com o que ele ja entra em combate.

    **A unica fonte de condicao neste motor**, e isso e uma limitacao honesta e
    nao um desenho: na SRD, Caido vem de Empurrar e Cego vem de magia, e as duas
    estao fora de escopo -- Empurrar precisa de teste de atributo oposto, que
    consumiria RNG fora de ataque pela primeira vez e por isso tem que entrar
    sozinho (ADR 0002). A fonte chega na etapa 3; o que esta fatia entrega e o
    resto: ler a condicao, aplicar o efeito, serializar e REMOVER.

    Tem default `()` e os campos de `Combatant` nao tem. A assimetria e
    deliberada: `Participant` nunca e serializada, entao a armadilha de "default
    nao faz save antigo carregar" nao existe aqui."""


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
        elif curto := [a.id for a in ficha.attacks if a.range_ft < PES_POR_CASA]:
            problemas.append(
                f"a ficha {p.statblock_id!r} tem ataque de alcance menor que "
                f"{PES_POR_CASA} pes: {sorted(curto)}"
            )

    ocupadas: dict[tuple[int, int], list[str]] = {}
    for p in participants:
        ocupadas.setdefault((p.position.x, p.position.y), []).append(str(p.id))
    for (x, y), quem in sorted(ocupadas.items()):
        if len(quem) > 1:
            problemas.append(f"a casa ({x}, {y}) tem mais de um combatente: {sorted(quem)}")

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
            position=por_id[cid].position,
            conditions=canonical_conditions(por_id[cid].conditions),
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


def _validar_ataque(
    state: CombatState,
    ator: Combatant,
    action: AttackAction,
) -> Rejected | None:
    if not ator.budget.action_available:
        return _rejeitar(
            state,
            RejectionReason.ACTION_ALREADY_USED,
            f"{ator.id!r} ja usou a acao deste turno",
        )
    if action.target == ator.id:
        # Atacar a si mesmo e mecanicamente legal em 5e, mas na pratica e
        # sempre bug de chamador ou de IA. Quando houver efeito em area, a
        # excecao entra como campo com default no AttackProfile -- e nao como
        # um caso especial aqui dentro.
        return _rejeitar(
            state,
            RejectionReason.SELF_TARGET_NOT_ALLOWED,
            f"{ator.id!r} nao pode atacar a si mesmo",
        )
    if combatant_of(state, action.target) is None:
        return _rejeitar(
            state,
            RejectionReason.NO_SUCH_TARGET,
            f"{action.target!r} nao esta neste combate",
        )
    perfil = attack_of(statblock_of(state, ator.id), action.attack_id)
    if perfil is None:
        return _rejeitar(
            state,
            RejectionReason.NO_SUCH_ATTACK,
            f"{ator.id!r} nao tem o ataque {action.attack_id!r}",
        )

    alvo = state.combatants[action.target]
    distancia = distance_ft(ator.position, alvo.position)
    if distancia > perfil.long_range_ft:
        return _rejeitar(
            state,
            RejectionReason.OUT_OF_RANGE,
            f"{alvo.id!r} esta a {distancia} pes e {perfil.id!r} nao passa de "
            f"{perfil.long_range_ft}",
        )
    return None


def _validar_movimento(
    state: CombatState,
    ator: Combatant,
    action: MoveAction,
) -> Rejected | None:
    """Custo e ocupacao.

    Nao ha mais distancia negativa a recusar: com destino em vez de distancia,
    "andar -5 pes" deixou de ser representavel -- o tipo eliminou o motivo de
    rejeicao, que e sempre melhor do que continuar checando.
    """
    custo = distance_ft(ator.position, action.to)
    if custo > ator.budget.movement_remaining_ft:
        return _rejeitar(
            state,
            RejectionReason.NOT_ENOUGH_MOVEMENT,
            f"{custo} pes ate ({action.to.x}, {action.to.y}) e "
            f"{ator.budget.movement_remaining_ft} disponiveis",
        )

    ocupante = _ocupante(state, action.to)
    if ocupante is not None and ocupante.id != ator.id:
        return _rejeitar(
            state,
            RejectionReason.SQUARE_OCCUPIED,
            f"({action.to.x}, {action.to.y}) ja tem {ocupante.id!r}",
        )
    return None


def _ocupante(state: CombatState, casa: Position) -> Combatant | None:
    for c in state.combatants.values():
        if c.position == casa:
            return c
    return None


def _validar_levantar(state: CombatState, ator: Combatant) -> Rejected | None:
    if Condition.CAIDO not in ator.conditions:
        return _rejeitar(state, RejectionReason.NOT_PRONE, f"{ator.id!r} nao esta caido")

    custo = stand_up_cost_ft(statblock_of(state, ator.id).speed_ft)
    if custo > ator.budget.movement_remaining_ft:
        return _rejeitar(
            state,
            RejectionReason.NOT_ENOUGH_MOVEMENT,
            f"levantar custa {custo} pes e {ator.id!r} tem {ator.budget.movement_remaining_ft}",
        )
    return None


def _validar_contexto(state: CombatState, action: Action) -> Rejected | Combatant:
    """As checagens que valem para qualquer acao, na ordem em que importam.

    Devolve o combatente quando passa, e a rejeicao quando nao. A uniao evita
    a dupla `(ator, rejeicao)` com um dos dois sempre `None`, que mypy nao teria
    como estreitar e que abriria espaco para usar o ator de uma acao recusada.
    """
    if combat_result(state) is not None:
        return _rejeitar(state, RejectionReason.COMBAT_OVER, "o combate ja acabou")

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
    if not is_conscious(ator):
        return _rejeitar(state, RejectionReason.ACTOR_IS_DOWN, f"{ator.id!r} esta caido")

    return ator


def validate(state: CombatState, action: Action) -> Rejected | None:
    """Confere a legalidade da acao. `None` quer dizer "pode".

    Roda **inteira antes de qualquer toque no RNG**. Se uma validacao viesse
    depois de uma rolagem, uma acao recusada teria consumido entropia, e dois
    combates com a mesma seed divergiriam so porque um deles tentou uma jogada
    ilegal pelo caminho.
    """
    contexto = _validar_contexto(state, action)
    if isinstance(contexto, Rejected):
        return contexto

    match action:
        case AttackAction():
            return _validar_ataque(state, contexto, action)
        case MoveAction():
            return _validar_movimento(state, contexto, action)
        case StandUpAction():
            return _validar_levantar(state, contexto)
        case EndTurnAction():
            return None
        case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
            assert_never(action)


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
        if not is_conscious(candidato):
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
    """O ponto de entrada unico: estado + acao, estado novo + o que aconteceu.

    Alem de aplicar a acao, esta funcao e o unico lugar que observa a
    **transicao** para combate encerrado e emite `CombatEnded`. O resultado do
    combate e derivado, entao ninguem "muda" ele e nao ha outro momento natural
    para o evento sair; sem esta regra, ou ele nunca apareceria, ou apareceria
    de novo a cada acao posterior -- e o golden congelaria o acidente.
    """
    resultado = _aplicar(state, action)
    if not isinstance(resultado, Applied):
        return resultado

    # So chegamos aqui quando a acao foi aplicada, e `validate` recusa
    # qualquer acao com o combate ja encerrado. Logo o combate estava em
    # andamento antes, e basta olhar o depois -- conferir o antes de novo seria
    # um ramo que nenhum teste consegue alcançar.
    desfecho = combat_result(resultado.state)
    if desfecho is not None:
        return replace(resultado, events=(*resultado.events, CombatEnded(outcome=desfecho)))
    return resultado


def _aplicar(state: CombatState, action: Action) -> ActionResult:
    rejeicao = validate(state, action)
    if rejeicao is not None:
        return rejeicao

    match action:
        case AttackAction():
            return _atacar(state, action)

        case MoveAction():
            ator = state.combatants[action.actor]
            custo = distance_ft(ator.position, action.to)
            restante = ator.budget.movement_remaining_ft - custo
            novo = _com_combatente(
                state,
                replace(
                    ator,
                    position=action.to,
                    budget=replace(ator.budget, movement_remaining_ft=restante),
                ),
            )
            evento = MovementSpent(
                creature=ator.id,
                origin=ator.position,
                destination=action.to,
                feet=custo,
                remaining_ft=restante,
            )
            return Applied(state=novo, events=(evento,))

        case StandUpAction():
            ator = state.combatants[action.actor]
            custo = stand_up_cost_ft(statblock_of(state, ator.id).speed_ft)
            restante = ator.budget.movement_remaining_ft - custo
            novo = _com_combatente(
                state,
                replace(
                    ator,
                    conditions=canonical_conditions(
                        c for c in ator.conditions if c is not Condition.CAIDO
                    ),
                    budget=replace(ator.budget, movement_remaining_ft=restante),
                ),
            )
            return Applied(
                state=novo,
                events=(StoodUp(creature=ator.id, feet=custo, remaining_ft=restante),),
            )

        case EndTurnAction():
            novo, eventos = advance_turn(state)
            return Applied(state=novo, events=eventos)

        case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
            assert_never(action)


def _atacar(state: CombatState, action: AttackAction) -> Applied:
    """A acao de ataque, ja validada, na ordem que o contrato do RNG fixa.

    Sempre dois d20 para o acerto; o dano so e rolado **em acerto**, e por isso
    a ausencia de `DamageRolled` no log e a prova de que um erro nao consumiu
    entropia. A acao e gasta aconteça o que acontecer -- errar tambem custa o
    turno.
    """
    ator = state.combatants[action.actor]
    alvo = state.combatants[action.target]
    ficha_ator = statblock_of(state, ator.id)
    ficha_alvo = statblock_of(state, alvo.id)

    perfil = attack_of(ficha_ator, action.attack_id)
    if perfil is None:  # pragma: no cover - `validate` ja recusou
        msg = f"{ator.id!r} nao tem o ataque {action.attack_id!r}"
        raise CorruptStateError(msg)

    derivadas_adv, derivadas_dis = derive_advantage_sources(state, action)
    fontes_adv = action.advantage_sources + derivadas_adv
    fontes_dis = action.disadvantage_sources + derivadas_dis
    vantagem = resolve_advantage(fontes_adv, fontes_dis)

    antes_d20 = position(state.rng)
    rolagem, rng = roll_d20(state.rng, vantagem)

    conta = attack_math(perfil, ficha_ator.abilities, ficha_ator.proficiency_bonus)
    checagem = d20_check(rolagem, bonus=conta.attack, dc=ficha_alvo.armor_class)
    desfecho = classify_attack(checagem)
    alvo_estava_caido = not is_conscious(alvo)

    eventos: list[Event] = [
        AttackRolled(
            actor=ator.id,
            target=alvo.id,
            attack_id=perfil.id,
            attack_name=perfil.name,
            advantage=vantagem,
            advantage_sources=fontes_adv,
            disadvantage_sources=fontes_dis,
            pair=rolagem.pair,
            chosen_index=rolagem.chosen_index,
            natural=rolagem.natural,
            ability=conta.ability,
            ability_mod=conta.ability_mod,
            proficiency=conta.proficiency,
            total=checagem.total,
            target_ac=ficha_alvo.armor_class,
            target_was_down=alvo_estava_caido,
            outcome=desfecho,
            rng_before=antes_d20,
            rng_after=position(rng),
        )
    ]

    novo = replace(
        _com_combatente(state, replace(ator, budget=replace(ator.budget, action_available=False))),
        rng=rng,
    )

    if desfecho not in (AttackOutcome.HIT, AttackOutcome.CRITICAL_HIT):
        return Applied(state=novo, events=tuple(eventos))

    antes_dano = position(novo.rng)
    dano, rng = roll_damage(
        novo.rng,
        perfil.damage,
        ability_bonus=conta.damage,
        critical=desfecho is AttackOutcome.CRITICAL_HIT,
    )
    eventos.append(
        DamageRolled(
            actor=ator.id,
            target=alvo.id,
            roll=dano,
            rng_before=antes_dano,
            rng_after=position(rng),
        )
    )

    hp, aplicado = apply_damage(alvo.hp, dano.total)
    eventos.append(
        HpChanged(
            creature=alvo.id,
            before=alvo.hp,
            after=hp,
            dealt=aplicado.dealt,
            overkill=aplicado.overkill,
        )
    )
    if aplicado.dropped_to_zero:
        eventos.append(CreatureDowned(creature=alvo.id))

    novo = replace(
        _com_combatente(novo, replace(novo.combatants[alvo.id], hp=hp)),
        rng=rng,
    )
    return Applied(state=novo, events=tuple(eventos))


def combat_result(state: CombatState) -> CombatOutcome | None:
    """`None` enquanto ha dois lados de pe; o desfecho quando nao ha mais.

    **Derivado, nunca armazenado.** Guardado no estado, seria um segundo lugar
    onde a verdade pode ficar velha -- e some no round-trip do save se alguem
    esquecer do campo. Derivar custa uma varredura de combatentes e resolve as
    duas coisas de uma vez.
    """
    de_pe = conscious_teams(state)
    if len(de_pe) >= MINIMO_DE_TIMES:
        return None
    return CombatOutcome(
        winning_team=de_pe[0] if de_pe else None,
        last_round=state.turn_order.round_number,
    )


def legal_actions(state: CombatState) -> tuple[Action, ...]:
    """Um conjunto **canonico e finito** de acoes legais, nao o espaco inteiro.

    A diferenca importa em `MoveAction`, cuja distancia e um inteiro: oferecer
    todas as distancias legais daria um conjunto grande e inutil, entao sai
    exatamente uma, gastando o movimento restante. Ataques saem um por par
    (ataque x inimigo **de pe**), sem fontes de vantagem declaradas.

    Ha uma assimetria deliberada: `apply` aceita **mais** do que isto oferece
    -- atacar quem ja caiu, andar meia distancia, declarar fontes de vantagem.
    Isto aqui e o menu que uma interface ou uma IA usaria, e nao a definicao de
    legalidade, que mora em `validate`.

    A ordem e deterministica: ataques na ordem da ficha, alvos em ordem
    lexicografica de id.
    """
    if combat_result(state) is not None:
        return ()

    ator = state.combatants[state.turn_order.current]
    if not is_conscious(ator):
        return ()

    acoes: list[Action] = []

    if ator.budget.action_available:
        inimigos = sorted(
            (c for c in state.combatants.values() if c.team != ator.team and is_conscious(c)),
            key=lambda c: str(c.id),
        )
        # So o que esta ao alcance. E aqui que a ordem do menu deixa de ser
        # incondicional: com o inimigo longe, `acoes[0]` nao e mais um ataque.
        acoes.extend(
            AttackAction(actor=ator.id, target=alvo.id, attack_id=perfil.id)
            for perfil in statblock_of(state, ator.id).attacks
            for alvo in inimigos
            if distance_ft(ator.position, alvo.position) <= perfil.long_range_ft
        )

    # Levantar entra no degrau do MOVIMENTO, porque e movimento que ele gasta --
    # e antes de andar, porque um caido que anda continua caido e volta a atacar
    # com desvantagem. So e oferecido com orcamento para pagar, como todo item
    # do menu.
    if Condition.CAIDO in ator.conditions and ator.budget.movement_remaining_ft >= (
        stand_up_cost_ft(statblock_of(state, ator.id).speed_ft)
    ):
        acoes.append(StandUpAction(actor=ator.id))

    destino = _casa_canonica(state, ator)
    if destino is not None:
        acoes.append(MoveAction(actor=ator.id, to=destino))

    acoes.append(EndTurnAction(actor=ator.id))
    return tuple(acoes)


def _casa_canonica(state: CombatState, ator: Combatant) -> Position | None:
    """A UMA casa que o menu oferece, ou `None` quando nao vale andar.

    Com destino em vez de distancia, "todas as casas alcancaveis" e um conjunto
    grande e inutil -- com 30 pes sao 168 casas, e nenhuma interface mostraria
    isso. `legal_actions` continua sendo um cardapio curado, e a regra de
    curadoria e: **a casa alcancavel e livre que mais aproxima do inimigo de pe
    mais perto**, desempatando por (x, y) para ser deterministica.

    Isso e heuristica, e nao otimo -- exatamente como "ataque o primeiro inimigo
    de pe" ja era. A diferenca e que sem ela o piloto automatico nunca fecha
    distancia, e um encontro que comeca a 20 pes nunca vira combate.

    Devolve `None` quando nao ha para onde ir que melhore: sem orcamento, sem
    inimigo de pe, ou ja na melhor casa alcancavel.
    """
    alcance = ator.budget.movement_remaining_ft // PES_POR_CASA
    if alcance < 1:
        return None

    # Pre-condicao, garantida por `legal_actions`: o ator esta de pe e o combate
    # esta em andamento, logo existe ao menos um outro time de pe, logo existe
    # inimigo. Uma guarda aqui seria ramo que nenhum teste alcanca -- e se um dia
    # a pre-condicao quebrar, o `min` abaixo estoura no lugar exato do erro, que
    # e o que se quer de uma invariante violada.
    inimigos = [
        c.position for c in state.combatants.values() if c.team != ator.team and is_conscious(c)
    ]

    def chave(casa: Position) -> tuple[int, int, int, int]:
        """Boa, direta, e so entao arbitraria.

        1. Distancia ao inimigo mais perto: e para isso que se anda.
        2. Desvio de Manhattan ate a casa. Faz duas coisas de uma vez: **fica
           parado vence** quando andar nao melhora a distancia (so a propria
           casa tem desvio zero), e entre as muitas casas que Chebyshev empata
           -- ir reto e ir na diagonal custam o mesmo -- vence a menos torta.
        3. `x` e `y`: o que sobrar tem que ser deterministico.

        Houve um terceiro criterio aqui, o custo em pes, e ele foi removido: uma
        sonda mostrou que zera-lo nao quebrava teste nenhum. Custo e desvio sao
        ambos zero exatamente na casa do ator e positivos fora dela, entao o
        desvio ja fazia o trabalho inteiro sozinho.
        """
        desvio = abs(casa.x - ator.position.x) + abs(casa.y - ator.position.y)
        perto = min(distance_ft(casa, alvo) for alvo in inimigos)
        return (perto, desvio, casa.x, casa.y)

    ocupadas = {c.position for c in state.combatants.values() if c.id != ator.id}
    candidatas = [
        casa
        for dx in range(-alcance, alcance + 1)
        for dy in range(-alcance, alcance + 1)
        if (casa := Position(x=ator.position.x + dx, y=ator.position.y + dy)) not in ocupadas
    ]

    melhor = min(candidatas, key=chave)
    return None if melhor == ator.position else melhor

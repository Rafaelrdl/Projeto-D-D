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

from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import assert_never

from tacticore.core.actions import Action
from tacticore.core.dice import DamageExpr, parse_dice
from tacticore.core.engine import (
    Participant,
    apply,
    combat_result,
    legal_actions,
)
from tacticore.core.enums import Ability, Condition, canonical_conditions
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
    StoodUp,
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
    Position,
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
    adds_ability_to_damage: bool = True,
    range_ft: int = 5,
    long_range_ft: int | None = None,
) -> AttackProfile:
    """Aceita a notacao em string por conveniencia de quem escreve o teste."""
    return AttackProfile(
        id=AttackId(id),
        name=name,
        ability=ability,
        proficient=proficient,
        damage=parse_dice(damage) if isinstance(damage, str) else damage,
        # O default mora AQUI, e nao na dataclass: builder de teste existe
        # para o teste escrever so o que importa para ele, e `AttackProfile`
        # existe para nao deixar ninguem esquecer de decidir.
        adds_ability_to_damage=adds_ability_to_damage,
        range_ft=range_ft,
        # Sem alcance longo proprio, a arma nao tem "longe": e o que vale
        # para toda arma corpo a corpo.
        long_range_ft=range_ft if long_range_ft is None else long_range_ft,
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
    conditions: Iterable[Condition] = (),
) -> Combatant:
    """`hp` aceita um int para o caso comum de "quero este com 1 de vida".

    **Nao recebe posicao de proposito.** Quem coloca combatente no tabuleiro e
    `make_state`, que enfileira ou aceita `posicoes`; um parametro aqui seria
    sobrescrito por ela em todo uso real, e ficaria como enfeite que parece
    funcionar."""
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
        # A origem e provisoria: `make_state` reposiciona.
        position=Position(x=0, y=0),
        conditions=canonical_conditions(conditions),
    )


def make_state(
    *,
    statblocks: Iterable[Statblock] | None = None,
    combatants: Iterable[Combatant] | None = None,
    order: Iterable[str] | None = None,
    current: str | None = None,
    round_number: int = 1,
    rng: RngState | None = None,
    posicoes: Mapping[str, tuple[int, int]] | None = None,
) -> CombatState:
    """Monta um estado consistente a partir do pouco que o teste informar.

    A ordem de iniciativa, quando omitida, e a ordem em que os combatentes
    foram passados -- deterministica e obvia na leitura do teste. Isto **nao**
    substitui `start_combat`: aqui nada e rolado e nada e validado, de
    proposito, para que um teste possa montar tambem o estado esquisito de que
    precisa.

    **Os combatentes sao enfileirados** em `(0,0)`, `(1,0)`, `(2,0)`... na ordem
    em que vieram, sobrescrevendo a posicao que cada um trouxe. E deliberado e
    vale a surpresa: sem isso, todo teste que nao fala de posicao montaria dois
    combatentes na mesma casa e quebraria numa invariante que ele nao esta
    testando. Quem testa posicao passa `posicoes`, e ai nada e sobrescrito.
    """
    fichas = (make_statblock(),) if statblocks is None else tuple(statblocks)
    lutadores = (make_combatant(),) if combatants is None else tuple(combatants)

    if posicoes is None:
        lutadores = tuple(replace(c, position=Position(x=i, y=0)) for i, c in enumerate(lutadores))
    else:
        lutadores = tuple(
            replace(c, position=Position(x=posicoes[str(c.id)][0], y=posicoes[str(c.id)][1]))
            if str(c.id) in posicoes
            else c
            for c in lutadores
        )

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
    position: Position | tuple[int, int] = (0, 0),
    conditions: Iterable[Condition] = (),
) -> Participant:
    casa = Position(x=position[0], y=position[1]) if isinstance(position, tuple) else position
    return Participant(
        id=CreatureId(id),
        statblock_id=StatblockId(statblock_id),
        team=team,
        position=casa,
        conditions=canonical_conditions(conditions),
    )


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
    # Colados de proposito: a maioria dos testes de motor quer atacar sem
    # precisar andar antes. Quem testa movimento passa as posicoes.
    participantes = (
        make_participant(id=a, statblock_id=str(primeira.id), team="herois", position=(0, 0)),
        make_participant(id=b, statblock_id=str(segunda.id), team="viloes", position=(1, 0)),
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
                | StoodUp()
            ):
                continue
            case _:  # pragma: no cover - inalcancavel: mypy fecha a uniao
                assert_never(evento)
    return tuple(dados)


type Politica = Callable[[CombatState, tuple[Action, ...]], Action]
"""Quem escolhe, dado o estado e o menu do momento.

Recebe o **estado** alem do menu porque uma politica que so enxerga a lista de
acoes nunca passa de um seletor de indice: `AttackAction` carrega o id do alvo
e nao a vida dele, entao "bater em quem esta quase caindo" e indecidivel sem o
estado. `primeira_legal` ignora o parametro, e esta certo que ignore -- e a
unica politica que pode.

A politica **nao pode** consultar `state.rng`: `apply` e oraculo, e ler a
posicao do stream do estado recebido e prever o proximo dado. Nao ha trava para
isso hoje; ela entra junto com a primeira politica que teria motivo para
trapacear.
"""


def primeira_legal(state: CombatState, acoes: tuple[Action, ...]) -> Action:
    """A primeira acao do menu, sempre.

    Nao e uma IA e nao tenta ser: e um piloto automatico deterministico, que e
    o que um teste de determinismo e um golden precisam. Quem decide de fato e
    a **ordem** de `legal_actions`, que e contrato declarado no ADR 0002 sec. 1
    justamente porque esta funcao obedece a ela sem pensar.
    """
    return acoes[0]


def _nome(politica: Politica) -> str:
    """O nome da politica para a mensagem de erro. Nem toda callable tem um."""
    return str(getattr(politica, "__name__", politica))


@dataclass(frozen=True, slots=True, kw_only=True)
class Passo:
    """Um ponto de escolha: o retrato, o que aconteceu ate aqui, e o menu.

    **Nao e estado de combate** e nao vai para save nenhum: e o que o laco
    entrega a quem conduz, entre duas acoes. Por isso nao tem codec em `serde`
    nem entrada no guardiao de tipos -- e por isso, tambem, pode carregar a
    tupla de eventos, que dentro do estado seria proibida.
    """

    state: CombatState
    """O combate **antes** da escolha deste passo."""

    events: tuple[Event, ...]
    """O que aconteceu desde o passo anterior. Vazio no primeiro."""

    actions: tuple[Action, ...]
    """O menu. **Vazio significa fim**: o ultimo passo cedido e o retrato
    final, e quem conduz para ai sem enviar mais nada."""


def conduzir(
    state: CombatState,
    *,
    max_actions: int = 500,
    origem: str = "quem conduz",
) -> Generator[Passo, Action, None]:
    """O laco de combate, com um ponto de suspensao onde a escolha entra.

    Cede um `Passo` e recebe a `Action` escolhida, ate ceder um passo de menu
    vazio -- o fim.

    Existe para que continue havendo **um** laco de combate no projeto. O
    docstring de `tacticore.__main__` recusa por escrito um segundo laco so
    para o CLI, e recusa com razao: seriam dois motores de decisao para manter
    em sincronia. Mas o CLI precisa de duas coisas que `play_out` nao da --
    narrar turno a turno e parar para ler a escolha -- e a diferenca entre as
    duas funcoes e exatamente essa: `play_out` resolve o ponto de suspensao com
    uma `Politica`, e o comando o resolve com uma pessoa.

    `origem` so aparece em mensagem de erro, e serve para dizer **quem**
    mandou a acao recusada: de dentro daqui nao da para saber.
    """
    atual = state
    desde_o_ultimo: tuple[Event, ...] = ()

    for _ in range(max_actions):
        if combat_result(atual) is not None:
            yield Passo(state=atual, events=desde_o_ultimo, actions=())
            return

        acoes = legal_actions(atual)
        if not acoes:
            msg = f"sem acao legal para {atual.turn_order.current!r} e o combate nao acabou"
            raise CorruptStateError(msg)

        escolhida = yield Passo(state=atual, events=desde_o_ultimo, actions=acoes)
        resultado = apply(atual, escolhida)
        if not isinstance(resultado, Applied):
            # Com `primeira_legal` isto e inalcancavel enquanto valer a
            # propriedade central de `legal_actions`, que tem teste proprio em
            # test_combat_end.py. Deixou de ser inalcancavel em geral no dia em
            # que a politica virou parametro: uma politica de fora pode
            # devolver acao que o menu nao ofereceu, e a assimetria deliberada
            # entre `legal_actions` e `validate` nao a barra necessariamente.
            #
            # A mensagem culpava `legal_actions` por uma escolha que nunca foi
            # dela. Agora nomeia quem escolheu, porque sao duas falhas
            # diferentes: menu errado e escolha errada.
            msg = f"{origem} escolheu {escolhida}, recusada com {resultado.reason}"
            raise CorruptStateError(msg)

        atual = resultado.state
        desde_o_ultimo = resultado.events

    msg = f"o combate nao terminou em {max_actions} acoes"
    raise CorruptStateError(msg)


def play_out(
    state: CombatState,
    *,
    politica: Politica = primeira_legal,
    max_actions: int = 500,
) -> tuple[CombatState, tuple[Event, ...]]:
    """Joga o combate ate o fim, resolvendo cada escolha com `politica`.

    E `conduzir` com o ponto de suspensao tapado por uma funcao. O default e
    `primeira_legal`, que e o comportamento que esta funcao sempre teve -- e
    por isso a troca nao regrava golden nenhum. O parametro existe porque
    `acoes[0]` era uma **politica** embutida numa linha, sem nome e sem
    docstring, e sem nome nao da para comparar duas.

    O limite de acoes existe para que um bug de regra vire uma falha de teste
    legivel em vez de um processo travado.
    """
    conducao = conduzir(state, max_actions=max_actions, origem=f"a politica {_nome(politica)}")
    log: list[Event] = []
    passo = next(conducao)

    while True:
        log.extend(passo.events)
        if not passo.actions:
            return passo.state, tuple(log)
        passo = conducao.send(politica(passo.state, passo.actions))

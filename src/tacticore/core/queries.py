"""Perguntas de leitura sobre o estado, num lugar so.

Existem para que "esta de pe" nao seja reescrito como `hp.current > 0` em oito
lugares. No dia em que cair deixar de ser exatamente isso -- quando houver
condicao de inconsciente, ou morte separada de queda -- muda aqui e so aqui.
"""

from __future__ import annotations

from tacticore.core.actions import AttackAction
from tacticore.core.enums import Condition
from tacticore.core.errors import CorruptStateError
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import (
    PES_POR_CASA,
    AttackProfile,
    Combatant,
    CombatState,
    Statblock,
)
from tacticore.core.rules import distance_ft, is_adjacent

FONTE_INIMIGO_ADJACENTE = "inimigo adjacente"
FONTE_ATACANTE_CAIDO = "atacante caido"
FONTE_ALVO_CAIDO_PERTO = "alvo caido, e eu estou colado"
FONTE_ALVO_CAIDO_LONGE = "alvo caido, e eu estou longe"
FONTE_ALCANCE_LONGO = "alem do alcance curto"
"""Os textos que vao para o log. Constantes e nao literais soltos porque os
testes afirmam sobre eles e a narrativa os exibe -- dois lugares, um dono."""


def is_conscious(combatant: Combatant) -> bool:
    """Se ainda esta consciente. Chegar a zero apaga.

    O nome mudou de `is_standing` na fatia 3, e a mudanca e so de nome: o corpo
    e o mesmo. "Estar de pe" passou a ser outra coisa com a condicao Caido --
    na SRD, *prone* independe de vida, e um caido esta de pe zero por cento do
    tempo e vivo o tempo todo.

    E `is_conscious` e nao `is_alive` porque `hp.current > 0` e consciencia, nao
    vida: a distincao entre morto e inconsciente esta registrada como desvio em
    `docs/srd-atribuicao.md` e vai entrar um dia. Queimar `is_alive` agora
    tiraria o nome de quem vai precisar dele.

    **Nao foi partida em tres.** `is_valid_target` nao teria chamador --
    `engine._validar_ataque` confere orcamento, auto-alvo, alvo inexistente,
    ataque inexistente e alcance, e nunca consulta quem caiu, o que e assimetria
    declarada de proposito na docstring de `legal_actions`. E `can_act` nasceria
    com este mesmo corpo e assim continuaria depois da fatia inteira, porque
    Caido nao incapacita. `can_act` nasce com a primeira condicao que incapacite.
    """
    return combatant.hp.current > 0


def combatant_of(state: CombatState, creature: CreatureId) -> Combatant | None:
    """O combatente, ou `None` se o id nao participa deste combate."""
    return state.combatants.get(creature)


def statblock_of(state: CombatState, creature: CreatureId) -> Statblock:
    """A ficha de um participante.

    Levanta `CorruptStateError` quando nao acha: um combatente apontando para
    ficha inexistente e bug do motor ou save que passou por `load` sem
    checagem, e nunca jogada ilegal. Rejeitar aqui esconderia o estrago.
    """
    combatant = state.combatants.get(creature)
    if combatant is None:
        msg = f"{creature!r} nao participa deste combate"
        raise CorruptStateError(msg)

    statblock = state.statblocks.get(combatant.statblock_id)
    if statblock is None:
        msg = f"{creature!r} aponta para a ficha inexistente {combatant.statblock_id!r}"
        raise CorruptStateError(msg)
    return statblock


def conscious_teams(state: CombatState) -> tuple[str, ...]:
    """Os times que ainda tem alguem consciente, em ordem alfabetica.

    Tupla ordenada e nao `set`: o resultado alimenta a decisao de fim de
    combate, e um conjunto obrigaria quem consome a escolher um elemento de uma
    colecao cuja ordem de iteracao varia com `PYTHONHASHSEED`.
    """
    return tuple(sorted({c.team for c in state.combatants.values() if is_conscious(c)}))


def attack_of(statblock: Statblock, attack: AttackId) -> AttackProfile | None:
    """O ataque pelo slug, ou `None` se a ficha nao tem esse.

    Busca linear: uma ficha tem tres ataques, nao tres mil, e um indice seria
    uma estrutura a mais para manter sincronizada em troca de nada.
    """
    for perfil in statblock.attacks:
        if perfil.id == attack:
            return perfil
    return None


def derive_advantage_sources(
    state: CombatState,
    action: AttackAction,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Vantagem e desvantagem que vem do **estado**, e nao da acao.

    Este gancho existiu vazio desde a etapa 1, esperando exatamente isto: hoje
    sao tres regras, e nenhuma delas encostou em `_atacar`, que a essa altura
    tem quarenta testes em cima.

    As fontes derivadas sao concatenadas **depois** das declaradas na acao, e a
    ordem entre elas e fixa porque aparece no log.

    As regras, na ordem em que sao avaliadas:

    1. **Atirar com inimigo colado** da desvantagem. "A distancia" e definido
       como `range_ft > PES_POR_CASA`, e nao por um campo de tipo de arma --
       mesmo conjunto enquanto nao houver arma de haste, e registrado como
       desvio.
    2. **Atirar entre o alcance curto e o longo** da desvantagem. Para arma
       corpo a corpo os dois alcances sao iguais, entao o intervalo e vazio e a
       clausula nunca dispara -- o que e certo, porque a essa distancia o ataque
       ja foi recusado.
    3. **Estar caido** da desvantagem nos proprios ataques.
    4. **Atacar quem esta caido** da vantagem se o atacante estiver a 1,5 m, e
       desvantagem se estiver longe. Repare que isto e **geometria e nao tipo de
       arma**: um arqueiro colado no caido tem VANTAGEM, e um lanceiro de
       alcance 10 atacando de duas casas tem desvantagem. Ler `perfil.range_ft`
       aqui seria a leitura errada da regra, e ela e facil de fazer porque a
       clausula 1 logo acima le exatamente esse campo.
    """
    perfil = attack_of(statblock_of(state, action.actor), action.attack_id)
    if perfil is None:
        return (), ()

    ator = state.combatants[action.actor]
    alvo = combatant_of(state, action.target)

    vantagens: list[str] = []
    desvantagens: list[str] = []

    if perfil.range_ft > PES_POR_CASA and any(
        c.team != ator.team and is_conscious(c) and is_adjacent(ator.position, c.position)
        for c in state.combatants.values()
    ):
        desvantagens.append(FONTE_INIMIGO_ADJACENTE)

    # ENTRE os dois alcances, e nao apenas "alem do curto": passado o alcance
    # longo o ataque e recusado, e anunciar penalidade para um ataque impossivel
    # e poluir o log com uma explicacao de algo que nao aconteceu. A primeira
    # versao disto marcava desvantagem para arma corpo a corpo a duas casas, que
    # `validate` nunca deixaria passar.
    if alvo is not None and (
        perfil.range_ft < distance_ft(ator.position, alvo.position) <= perfil.long_range_ft
    ):
        desvantagens.append(FONTE_ALCANCE_LONGO)

    if Condition.CAIDO in ator.conditions:
        desvantagens.append(FONTE_ATACANTE_CAIDO)

    if alvo is not None and Condition.CAIDO in alvo.conditions:
        if is_adjacent(ator.position, alvo.position):
            vantagens.append(FONTE_ALVO_CAIDO_PERTO)
        else:
            desvantagens.append(FONTE_ALVO_CAIDO_LONGE)

    return tuple(vantagens), tuple(desvantagens)

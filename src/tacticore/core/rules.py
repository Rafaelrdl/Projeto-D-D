"""As regras da SRD como funcoes puras de numeros e descritores.

**Nenhuma funcao deste modulo recebe `CombatState`**, e um teste de arquitetura
reprova quem tentar. A restricao parece arbitraria e nao e: uma regra que
precisa do estado inteiro so pode ser testada montando um combate, e a partir
daí ninguem mais escreve o teste da tabela de modificadores de 1 a 30. Quem
conhece o estado e o `engine`; aqui em baixo so entram numeros.

O outro efeito da regra e que as mecanicas que ainda nao existem cabem sem
cirurgia. `d20_check` nao sabe o que e um ataque -- e por isso que salvaguardas
e testes de pericia, na etapa 2, sao uma funcao nova do lado, e nao um `if`
dentro de algo que ja tem quarenta testes em cima.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, assert_never

from tacticore.core.enums import Ability, AdvantageState, AttackOutcome, ContestOutcome
from tacticore.core.ids import CreatureId
from tacticore.core.model import PES_POR_CASA, Abilities, AttackProfile, HitPoints, Position
from tacticore.core.rng import RngState, roll_dice

D20_FACES = 20
"""O dado. Constante nomeada porque `20` aparece em contexto demais aqui."""

NATURAL_CRIT = 20
NATURAL_FUMBLE = 1


@dataclass(frozen=True, slots=True, kw_only=True)
class D20Roll:
    """Uma rolagem de d20 ja resolvida por vantagem."""

    pair: tuple[int, int]
    """Os **dois** dados, sempre. Ver `roll_d20`."""

    chosen_index: Literal[0, 1]
    natural: int
    """O valor do dado escolhido.

    "Natural" e sempre o dado que valeu, nunca o descartado. Um 20 no dado que
    a desvantagem jogou fora nao e critico, e guardar o indice escolhido faz
    dessa distincao um dado do log em vez de uma convencao na cabeca de alguem.
    """

    advantage: AdvantageState


@dataclass(frozen=True, slots=True, kw_only=True)
class D20CheckResult:
    """d20 + bonus contra uma dificuldade, **sem nenhum automatismo**.

    Nem 20 natural acerta aqui, nem 1 natural erra: isso e regra de ataque e
    mora em `classify_attack`. Separar os dois e o que permite reaproveitar
    esta funcao em salvaguarda e teste de pericia depois, onde o 20 natural
    nao tem efeito especial nenhum.
    """

    natural: int
    bonus: int
    total: int
    dc: int
    success: bool


def ability_modifier(score: int) -> int:
    """`(valor - 10) // 2`.

    Divisao inteira do Python arredonda para baixo tambem em negativo, que e
    exatamente o que a SRD pede: atributo 1 da -5, e nao -4.
    """
    return (score - 10) // 2


def ability_score(abilities: Abilities, ability: Ability) -> int:
    """O valor de um atributo pela sigla."""
    match ability:
        case Ability.FOR:
            return abilities.forca
        case Ability.DES:
            return abilities.destreza
        case Ability.CON:
            return abilities.constituicao
        case Ability.INT:
            return abilities.inteligencia
        case Ability.SAB:
            return abilities.sabedoria
        case Ability.CAR:
            return abilities.carisma
        case _:  # pragma: no cover - inalcancavel: mypy fecha o enum
            assert_never(ability)


def resolve_advantage(
    advantage_sources: tuple[str, ...],
    disadvantage_sources: tuple[str, ...],
) -> AdvantageState:
    """Colapsa todas as fontes num dos tres estados.

    A regra da SRD e binaria e nao acumula: basta **uma** de cada lado para
    voltar ao normal, e tres fontes de vantagem nao viram 3d20. As fontes
    chegam como tuplas de texto, e nao como contador, para que o log possa
    dizer *por que* houve vantagem -- e como tupla ordenada, nunca `set`, cuja
    ordem de iteracao varia com `PYTHONHASHSEED` e quebraria o determinismo de
    um jeito que so aparece de vez em quando.
    """
    tem_vantagem = bool(advantage_sources)
    tem_desvantagem = bool(disadvantage_sources)

    if tem_vantagem == tem_desvantagem:
        return AdvantageState.NORMAL
    return AdvantageState.ADVANTAGE if tem_vantagem else AdvantageState.DISADVANTAGE


def roll_d20(rng: RngState, advantage: AdvantageState) -> tuple[D20Roll, RngState]:
    """Rola o d20 consumindo **sempre dois dados**, inclusive em NORMAL.

    O quadro fixo e uma escolha deliberada de contrato. A alternativa -- um
    dado em NORMAL, dois com vantagem -- faz a quantidade de entropia consumida
    depender do resultado de uma regra, e entao ligar vantagem num ataque
    desloca todas as rolagens seguintes do combate. Entropia desperdicada custa
    zero; regravar quarenta goldens porque uma condicao nova mudou o
    alinhamento do stream custa uma tarde.

    Em NORMAL vale o primeiro dado e o segundo e registrado como descartado --
    ele aparece no evento, onde serve de prova de que o quadro fixo esta sendo
    respeitado.
    """
    (primeiro, segundo), depois = roll_dice(rng, 2, D20_FACES)

    escolhido: Literal[0, 1]
    match advantage:
        case AdvantageState.NORMAL:
            escolhido = 0
        case AdvantageState.ADVANTAGE:
            escolhido = 0 if primeiro >= segundo else 1
        case AdvantageState.DISADVANTAGE:
            escolhido = 0 if primeiro <= segundo else 1
        case _:  # pragma: no cover - inalcancavel: mypy fecha o enum
            assert_never(advantage)

    par = (primeiro, segundo)
    return (
        D20Roll(
            pair=par,
            chosen_index=escolhido,
            natural=par[escolhido],
            advantage=advantage,
        ),
        depois,
    )


def d20_check(roll: D20Roll, *, bonus: int, dc: int) -> D20CheckResult:
    """Compara `natural + bonus` com a dificuldade. Empate passa."""
    total = roll.natural + bonus
    return D20CheckResult(
        natural=roll.natural,
        bonus=bonus,
        total=total,
        dc=dc,
        success=total >= dc,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class AttackMath:
    """As parcelas de um ataque, calculadas de uma vez so.

    Uma funcao e nao duas porque o acerto e o dano de 5e usam o **mesmo**
    atributo, e duas funcoes separadas deixam isso valendo por coincidencia:
    basta alguem chamar uma com um perfil e a outra com outro. Aqui os dois
    saem da mesma leitura de ficha, e a relacao entre eles e uma linha do
    construtor em vez de um acordo entre dois lugares.

    Ate a etapa 3 essa relacao era `damage == ability_mod`, sempre. Deixou de
    ser: o dano de um truque nao soma modificador nenhum, e o acerto soma. Sao
    duas parcelas do **mesmo** atributo com regras diferentes -- que e o
    argumento de uma funcao so ficando mais forte, e nao mais fraco.

    As parcelas saem nomeadas porque o evento `AttackRolled` publica a conta
    decomposta. Devolver so o total obrigaria o motor a refazer as partes --
    que e exatamente como a duplicacao nasceu da primeira vez.
    """

    ability: Ability
    ability_mod: int
    proficiency: int
    """Ja zerado quando o atacante nao e proficiente com a arma."""

    attack: int
    """`ability_mod + proficiency`: o que entra no d20."""

    damage: int
    """`ability_mod` quando o ataque soma atributo ao dano, e `0` quando nao.

    Proficiencia **nunca** entra no dano, some quem somar. E o erro de porte de
    regra mais comum de 5e e o mais silencioso: o dano fica alto demais o
    combate inteiro sem nada quebrar.

    Quem decide entre as duas leituras e `AttackProfile.adds_ability_to_damage`
    -- regra de arma contra regra de magia, e nao um caso especial.
    """


def attack_math(
    profile: AttackProfile,
    abilities: Abilities,
    proficiency_bonus: int,
) -> AttackMath:
    """Tudo que um ataque soma, numa leitura so da ficha."""
    modificador = ability_modifier(ability_score(abilities, profile.ability))
    proficiencia = proficiency_bonus if profile.proficient else 0

    # `if` e nao ternario de proposito, e a diferenca e medida: `coverage.py`
    # nao cria arco para expressao condicional, entao um ternario aqui daria
    # 100% de cobertura com o ramo de truque nunca exercitado. O `if` deixa o
    # ramo visivel, e o teste que o mata entra no mesmo commit.
    no_dano = modificador
    if not profile.adds_ability_to_damage:
        no_dano = 0

    return AttackMath(
        ability=profile.ability,
        ability_mod=modificador,
        proficiency=proficiencia,
        # O atributo entra no ACERTO de qualquer jeito: e o "spell attack
        # bonus" da SRD, identico em forma ao bonus de ataque com arma.
        attack=modificador + proficiencia,
        damage=no_dano,
    )


def classify_attack(check: D20CheckResult) -> AttackOutcome:
    """Aplica os automatismos de 20 e 1 naturais, que sao regra de **ataque**.

    O 20 natural acerta qualquer CA e e critico; o 1 natural erra com qualquer
    bonus. O `natural` de onde isso sai e o do dado escolhido pela vantagem,
    nunca o descartado -- `roll_d20` ja garante isso.
    """
    if check.natural == NATURAL_CRIT:
        return AttackOutcome.CRITICAL_HIT
    if check.natural == NATURAL_FUMBLE:
        return AttackOutcome.CRITICAL_MISS
    return AttackOutcome.HIT if check.success else AttackOutcome.MISS


@dataclass(frozen=True, slots=True, kw_only=True)
class DamageApplied:
    """O que o dano de fato causou, separado do que ele valia no papel."""

    dealt: int
    """Pontos de vida realmente removidos. Nunca negativo."""

    overkill: int
    """O que sobrou depois de zerar a vida.

    Vai aqui e **nunca** no HP, que satura em zero. E a unica peca cara de
    recuperar depois: e dela que sai a morte instantanea da SRD (dano restante
    maior ou igual ao maximo de vida), e sem guarda-la agora a regra so
    poderia ser reconstruida refazendo a conta de tras para frente.
    """

    dropped_to_zero: bool
    """Se **este** golpe derrubou. Bater em quem ja estava caido nao derruba de
    novo, e sem a distincao o evento de queda sairia uma vez por golpe."""


def apply_damage(hp: HitPoints, amount: int) -> tuple[HitPoints, DamageApplied]:
    """Tira vida, com piso em zero nas duas pontas.

    Dano negativo vira zero antes de aplicar: ataque nao cura. Cura vai ser uma
    funcao propria, com regra propria (limite no maximo, efeito em quem esta a
    zero) -- deixar um numero negativo passar por aqui seria ganhar uma cura
    sem regra nenhuma, de graca e por engano.
    """
    efetivo = max(0, amount)
    dealt = min(efetivo, hp.current)

    return (
        HitPoints(current=hp.current - dealt, maximum=hp.maximum),
        DamageApplied(
            dealt=dealt,
            overkill=efetivo - dealt,
            dropped_to_zero=hp.current > 0 and dealt == hp.current,
        ),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class InitiativeEntry:
    """A rolagem de iniciativa de um participante, com o que desempata."""

    creature: CreatureId
    d20: int
    dex_mod: int
    dex_score: int
    total: int


def initiative_sort_key(entry: InitiativeEntry) -> tuple[int, int, str]:
    """Chave de ordem **total**: nunca empata de verdade.

    A SRD manda desempatar por Destreza e, se persistir, delega ao mestre. Nao
    existe mestre aqui, e deixar o resto por conta da ordem de montagem do
    encontro mataria o determinismo em silencio -- dois goblins identicos e o
    caso comum, nao o exotico. O ultimo criterio e o id, que e arbitrario mas
    estavel, e portanto reproduzivel.

    O desempate usa o **valor** de Destreza e nao o modificador porque 16 e 17
    dao o mesmo modificador e ainda assim devem desempatar. O modificador nao
    entra na chave por ser funcao monotona do valor: incluir os dois ordenaria
    exatamente igual, com um componente a mais para alguem ter que entender.
    """
    return (-entry.total, -entry.dex_score, str(entry.creature))


def distance_ft(origem: Position, destino: Position) -> int:
    """Distancia em pes entre duas casas, pela regra de grade da SRD.

    Distancia de Chebyshev vezes `PES_POR_CASA`: o numero de casas do maior
    eixo. Mover na diagonal custa o mesmo que mover reto, entao duas casas na
    diagonal ficam a 5 pes uma da outra e nao a 7,07 -- e essa aproximacao e
    justamente o que permite toda a geometria do jogo ser inteira, sem um unico
    `float` em lugar nenhum.

    A variante opcional da SRD que alterna 5 e 10 pes por diagonal esta
    registrada como desvio em `docs/srd-atribuicao.md`: ela corrige a geometria
    e cobra por isso uma conta COM ESTADO, dentro do que hoje e uma funcao pura
    de quatro inteiros.
    """
    return max(abs(origem.x - destino.x), abs(origem.y - destino.y)) * PES_POR_CASA


def is_adjacent(origem: Position, destino: Position) -> bool:
    """Se duas casas se tocam, inclusive na diagonal.

    A mesma casa **nao** conta como adjacente a si mesma: ninguem esta ao lado
    de si proprio, e a unica pergunta que usa isto -- "ha inimigo colado em
    mim?" -- nunca deveria responder sim por causa do proprio ator.
    """
    return origem != destino and distance_ft(origem, destino) == PES_POR_CASA


def stand_up_cost_ft(speed_ft: int) -> int:
    """Metade do deslocamento, arredondando para baixo.

    Levantar-se **nao e uma acao** na SRD: custa metade do movimento. Isso cabe
    sem inventar nada porque `TurnBudget` ja guarda movimento em pes e nao um
    bool de "ja andou" -- a decisao esta no docstring dele desde a etapa 1, e
    era exatamente este o caso que ela previa.

    Arredonda para baixo pela mesma razao que `ability_modifier`: `//` em Python
    arredonda para baixo, e toda conta do SRD neste motor e inteira.
    """
    return speed_ft // 2


# ------------------------------------------------- teste de atributo oposto -


@dataclass(frozen=True, slots=True, kw_only=True)
class ContestResult:
    """Dois d20 comparados **um com o outro**, e nao com uma dificuldade.

    O irmao de `D20CheckResult`, e nao um parametro dele. A SRD separa as duas
    coisas: num teste oposto os dois lados rolam e "they compare the totals of
    their two checks", e -- decisivo aqui -- "if the contest results in a tie,
    the situation remains the same as it was before the contest".

    `d20_check` e a regra **oposta** e nao serve: `dc` e obrigatorio, o corpo e
    `total >= dc` e o docstring dela diz "Empate passa". Aqui empate nao passa.

    As parcelas saem nomeadas pelo mesmo motivo que em `AttackMath`: o evento
    publica a conta decomposta, e devolver so o desfecho obrigaria o motor a
    refazer as somas -- que e exatamente como a duplicacao de `attack_bonus`
    nasceu da primeira vez.
    """

    actor_natural: int
    actor_bonus: int
    actor_total: int
    target_natural: int
    target_bonus: int
    target_total: int
    outcome: ContestOutcome


def contest(
    *,
    actor: D20Roll,
    actor_bonus: int,
    target: D20Roll,
    target_bonus: int,
) -> ContestResult:
    """Compara os dois totais. Quem inicia precisa de total **estritamente maior**.

    "The participant with the higher check total wins the contest." Empate nao
    e vitoria de ninguem, e por isso tem membro proprio em vez de virar
    `FAILURE` -- ver `ContestOutcome`.

    Tudo por palavra-chave, inclusive os dois `D20Roll`. Sao dois parametros do
    mesmo tipo cuja ordem muda a resposta, e posicionais fariam "troquei os dois
    lados" ficar indistinguivel de codigo certo na hora de ler. A ordem em que
    os dados sao **rolados** e outra coisa, e contrato: mora no item 6 do
    docstring de `tacticore.core`. Esta funcao nao rola nada.
    """
    total_a = actor.natural + actor_bonus
    total_d = target.natural + target_bonus

    if total_a > total_d:
        desfecho = ContestOutcome.SUCCESS
    elif total_a == total_d:
        desfecho = ContestOutcome.TIE
    else:
        desfecho = ContestOutcome.FAILURE

    return ContestResult(
        actor_natural=actor.natural,
        actor_bonus=actor_bonus,
        actor_total=total_a,
        target_natural=target.natural,
        target_bonus=target_bonus,
        target_total=total_d,
        outcome=desfecho,
    )


def defense_ability(abilities: Abilities) -> Ability:
    """Com que atributo o alvo de um empurrao resiste: o melhor de FOR e DES.

    Na SRD quem escolhe e o alvo -- "the target's Strength (Athletics) or
    Dexterity (Acrobatics) check (the target chooses the ability to use)". Nao
    existe ponto neste motor onde quem nao e `turn_order.current` decida
    (`_validar_contexto` recusa com `NOT_YOUR_TURN`), entao a escolha e
    deterministica, e "o melhor" e a unica que nao precisa de justificativa.

    **O desempate nao muda numero nenhum.** Com os dois modificadores iguais os
    dois atributos dao o mesmo total; ele decide so o rotulo que o evento grava.
    Esta dito aqui para ninguem ir procurar no combate um efeito que nao existe
    -- e o teste dele afirma sobre o `Ability` devolvido, nunca sobre um total,
    porque um teste sobre o total seria decoracao.

    `if` e nao ternario pelo motivo ja medido em `attack_math`: `coverage` nao
    cria arco para expressao condicional. Saiba, ainda assim, que o **empate**
    toma o mesmo arco que `forca > destreza` -- cobertura de branch nao cobra o
    desempate, e so o teste com ficha sintetica cobra.
    """
    forca = ability_modifier(abilities.forca)
    destreza = ability_modifier(abilities.destreza)
    if forca >= destreza:
        return Ability.FOR
    return Ability.DES

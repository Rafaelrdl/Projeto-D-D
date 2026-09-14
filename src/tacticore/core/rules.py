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

from tacticore.core.enums import Ability, AdvantageState, AttackOutcome
from tacticore.core.model import Abilities, AttackProfile
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


def attack_bonus(
    profile: AttackProfile,
    abilities: Abilities,
    proficiency_bonus: int,
) -> int:
    """Modificador do atributo do ataque, mais proficiencia se houver."""
    modificador = ability_modifier(ability_score(abilities, profile.ability))
    return modificador + (proficiency_bonus if profile.proficient else 0)


def damage_bonus(profile: AttackProfile, abilities: Abilities) -> int:
    """Modificador do **mesmo** atributo que fez o acerto.

    Proficiencia nao entra aqui. E o erro de porte de regra mais comum de 5e, e
    e silencioso: o dano fica alto demais o combate inteiro sem nada quebrar.
    """
    return ability_modifier(ability_score(abilities, profile.ability))


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

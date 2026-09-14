"""O que aconteceu, em dados crus.

Sem os eventos, um teste nao consegue afirmar quase nada do que interessa: um
acerto critico e um acerto comum de mesmo dano produzem exatamente a mesma
diferenca de HP, e "houve vantagem" nao deixa rastro nenhum no estado. Afirmar
sobre o log e o que torna o motor testavel sem espiar o RNG por dentro.

**Nenhum evento carrega frase formatada.** "Goblin acerta Heroi com a cimitarra
(17 contra CA 14)" e apresentacao, e apresentacao dentro do core e I/O
disfarcado: fixaria idioma, formato e publico numa camada que nao deveria saber
que existe uma tela. O evento carrega os numeros e o nome do ataque; montar a
frase e trabalho de quem for exibir.

Os eventos saem no **retorno** de cada acao e nunca se acumulam dentro do
estado. Log dentro do estado incharia o save de forma ilimitada e -- pior --
destruiria a igualdade estrutural entre dois combates rodados com a mesma
seed, que e exatamente o que os testes de determinismo comparam.

Todo evento de rolagem carrega `rng_before` e `rng_after`. Quando duas
execucoes com a mesma seed divergirem, a bisseccao comeca por "divergiu no
evento 14, entre as posicoes 9 e 11" em vez de por leitura de codigo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tacticore.core.dice import DamageRoll
from tacticore.core.enums import Ability, AdvantageState, AttackOutcome, SkipReason
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import CombatOutcome, HitPoints, TurnBudget


@dataclass(frozen=True, slots=True, kw_only=True)
class InitiativeRolled:
    """Uma rolagem de iniciativa, com tudo que entrou no desempate."""

    kind: Literal["initiative_rolled"] = "initiative_rolled"
    creature: CreatureId
    d20: int
    dex_mod: int
    dex_score: int
    total: int
    rng_before: int
    rng_after: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnOrderSet:
    """A ordem final, **gravada**.

    Gravar em vez de deixar quem le o log reordenar: a ordem e resultado de uma
    regra de desempate, e um replay que a recalcule esta testando a regra duas
    vezes em vez de conferir o resultado uma.
    """

    kind: Literal["turn_order_set"] = "turn_order_set"
    order: tuple[CreatureId, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class RoundStarted:
    kind: Literal["round_started"] = "round_started"
    round_number: int


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnStarted:
    kind: Literal["turn_started"] = "turn_started"
    creature: CreatureId
    budget: TurnBudget


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnEnded:
    kind: Literal["turn_ended"] = "turn_ended"
    creature: CreatureId


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnSkipped:
    """O turno de alguem que nao pode agir passou sem abrir.

    Sai **antes** de qualquer `TurnStarted`, e sem reset de orcamento: quem
    esta caido nao ganha um turno para depois nao usar.
    """

    kind: Literal["turn_skipped"] = "turn_skipped"
    creature: CreatureId
    reason: SkipReason


@dataclass(frozen=True, slots=True, kw_only=True)
class MovementSpent:
    kind: Literal["movement_spent"] = "movement_spent"
    creature: CreatureId
    feet: int
    remaining_ft: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AttackRolled:
    """A rolagem de ataque com a conta **decomposta**.

    Decomposta e nao so o total: quando item magico, bencao ou cobertura
    entrarem, cada um vira uma parcela a mais aqui, e quem le o log consegue
    conferir de onde saiu o numero. Guardar so `total` obrigaria a adivinhar.
    """

    kind: Literal["attack_rolled"] = "attack_rolled"
    actor: CreatureId
    target: CreatureId
    attack_id: AttackId
    attack_name: str

    advantage: AdvantageState
    advantage_sources: tuple[str, ...]
    disadvantage_sources: tuple[str, ...]

    pair: tuple[int, int]
    """Os dois dados, sempre -- inclusive em NORMAL, onde o segundo foi
    descartado. E a prova, no log, de que o quadro fixo foi respeitado."""

    chosen_index: Literal[0, 1]
    natural: int

    ability: Ability
    ability_mod: int
    proficiency: int
    total: int

    target_ac: int
    target_was_down: bool
    """Se o alvo ja estava caido. Bater em quem caiu e legal na SRD (e a porta
    para o golpe de misericordia), e o log registra para nao virar surpresa."""

    outcome: AttackOutcome
    rng_before: int
    rng_after: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DamageRolled:
    """So existe quando o ataque acerta.

    A ausencia dele no log e a prova de que um erro nao rolou dano -- e,
    portanto, de que nao consumiu entropia.
    """

    kind: Literal["damage_rolled"] = "damage_rolled"
    actor: CreatureId
    target: CreatureId
    roll: DamageRoll
    rng_before: int
    rng_after: int


@dataclass(frozen=True, slots=True, kw_only=True)
class HpChanged:
    kind: Literal["hp_changed"] = "hp_changed"
    creature: CreatureId
    before: HitPoints
    after: HitPoints
    dealt: int
    overkill: int
    """O que sobrou depois de zerar a vida. Vive aqui e nunca no HP."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CreatureDowned:
    kind: Literal["creature_downed"] = "creature_downed"
    creature: CreatureId


@dataclass(frozen=True, slots=True, kw_only=True)
class CombatEnded:
    """Sai **exatamente na transicao**, uma vez no log inteiro.

    Sem a regra explicita, ou o evento nunca apareceria (porque o resultado e
    derivado e ninguem o "muda") ou sairia a cada acao depois do fim -- e o
    golden congelaria um comportamento acidental.
    """

    kind: Literal["combat_ended"] = "combat_ended"
    outcome: CombatOutcome


type Event = (
    InitiativeRolled
    | TurnOrderSet
    | RoundStarted
    | TurnStarted
    | TurnSkipped
    | TurnEnded
    | MovementSpent
    | AttackRolled
    | DamageRolled
    | HpChanged
    | CreatureDowned
    | CombatEnded
)

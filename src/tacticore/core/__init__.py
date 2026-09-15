"""Motor de regras puro: recebe estado + acao, devolve estado novo.

Este pacote nao importa nada de engine, renderizacao, I/O ou rede, e nao guarda
estado em global nem em singleton. Toda aleatoriedade passa pelo ``RngState``
que vive dentro do proprio estado de combate, de modo que rodar um combate com
a mesma seed produz exatamente o mesmo resultado -- inclusive depois de salvar
e recarregar no meio de uma rodada.

As camadas dependem so para baixo::

    ids / enums / errors -> rng -> dice -> model -> actions / events
                         -> results -> rules -> queries -> engine

``tests/architecture/test_import_boundaries.py`` reprova qualquer violacao.

CONTRATO DE CONSUMO DO RNG (v1)
===============================

A ordem e a quantidade de dados rolados sao **API publica**, e nao detalhe de
implementacao. "Mesma seed, mesmo resultado" so e verdade se elas forem
contrato: qualquer mudanca aqui desloca todas as rolagens seguintes de todo
combate em andamento, e invalida todo save e todo golden existente.

1. **Iniciativa.** Um d20 por participante, percorrendo os ``creature_id`` em
   ordem lexicografica -- e nao na ordem em que foram passados.
2. **Ataque.** Sempre **dois** d20, inclusive sem vantagem. O quadro e fixo
   para que ligar vantagem nao mude o alinhamento do stream; em NORMAL vale o
   primeiro e o segundo e registrado como descartado.
3. **Dano.** Rolado **somente em acerto**, da esquerda para a direita, um dado
   fisico por posicao do stream. No critico, os dados extras de cada termo saem
   logo depois dos originais daquele termo: ``1d8+1d6`` consome d8, d8, d6, d6.
4. **Acao recusada nao consome nada.** Toda validacao roda antes do primeiro
   toque no RNG.
5. **O mapeamento palavra -> face nao tem rejeicao**: exatamente uma palavra de
   64 bits por dado fisico, qualquer que seja a face sorteada.
6. **Teste de atributo oposto.** Quatro d20: **dois por lado**, sempre, e os
   dois do **ator primeiro**. Cada lado consome o quadro fixo de um d20 mesmo
   sem vantagem nenhuma, pelo mesmo motivo do item 2; a ordem entre os lados e
   contrato pelo motivo do item 1. O desfecho -- vitoria, empate ou derrota --
   e lido **depois**, e **nunca o consumo**: qualquer automatismo futuro
   sobrescreve o resultado, jamais a quantidade de dados.

Mudar qualquer um destes pontos obriga a incrementar ``serde.RULES_VERSION``.
**Acrescentar** um ponto tambem, e o precedente e explicito: o commit de
``StandUpAction`` subiu a versao sem mexer no log de nenhum golden. O que a
versao responde nao e "os combates antigos mudaram", e sim "este motor calcula
coisas que o seu nao calculava".
O porque de cada um esta em ``docs/adr/0001-contrato-de-consumo-do-rng.md``.
"""

from __future__ import annotations

from tacticore.core.actions import Action, AttackAction, EndTurnAction, MoveAction
from tacticore.core.engine import (
    Participant,
    advance_turn,
    apply,
    combat_result,
    legal_actions,
    start_combat,
    validate,
)
from tacticore.core.enums import (
    Ability,
    AdvantageState,
    AttackOutcome,
    RejectionReason,
    SkipReason,
)
from tacticore.core.errors import (
    CorruptStateError,
    DiceSyntaxError,
    InvalidEncounterError,
    InvalidSaveError,
    RngExhausted,
    ScriptedRngOutOfRange,
    UnsupportedSchemaVersion,
)
from tacticore.core.events import Event
from tacticore.core.ids import AttackId, CreatureId, StatblockId
from tacticore.core.model import (
    Abilities,
    AttackProfile,
    Combatant,
    CombatOutcome,
    CombatState,
    HitPoints,
    Statblock,
    TurnBudget,
    TurnOrder,
)
from tacticore.core.results import ActionResult, Applied, Rejected
from tacticore.core.rng import RngState, ScriptedRng, SplitMix64
from tacticore.core.serde import (
    RULES_VERSION,
    SCHEMA_VERSION,
    dump,
    events_digest,
    fingerprint,
    load,
)

__all__ = (
    "RULES_VERSION",
    "SCHEMA_VERSION",
    "Abilities",
    "Ability",
    "Action",
    "ActionResult",
    "AdvantageState",
    "Applied",
    "AttackAction",
    "AttackId",
    "AttackOutcome",
    "AttackProfile",
    "CombatOutcome",
    "CombatState",
    "Combatant",
    "CorruptStateError",
    "CreatureId",
    "DiceSyntaxError",
    "EndTurnAction",
    "Event",
    "HitPoints",
    "InvalidEncounterError",
    "InvalidSaveError",
    "MoveAction",
    "Participant",
    "Rejected",
    "RejectionReason",
    "RngExhausted",
    "RngState",
    "ScriptedRng",
    "ScriptedRngOutOfRange",
    "SkipReason",
    "SplitMix64",
    "Statblock",
    "StatblockId",
    "TurnBudget",
    "TurnOrder",
    "UnsupportedSchemaVersion",
    "advance_turn",
    "apply",
    "combat_result",
    "dump",
    "events_digest",
    "fingerprint",
    "legal_actions",
    "load",
    "start_combat",
    "validate",
)

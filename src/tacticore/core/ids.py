"""Identificadores do dominio.

Todos sao ``NewType`` sobre ``str``, e nao ``str`` cru, para que o mypy reclame
quando um `StatblockId` for usado onde se esperava um `CreatureId` -- confusao
que, sem tipo, so aparece como "o goblin errado tomou o dano".

Sao **slugs legiveis fornecidos por quem monta o encontro** (``"goblin_1"``,
``"cimitarra"``), e nunca:

- ``uuid4()``, que le entropia do sistema operacional e furaria a regra de que
  toda aleatoriedade passa pelo RNG do estado;
- ``id()`` ou referencia de objeto, que nao serializa e, com estado imutavel,
  viraria ponteiro para a versao antiga da criatura;
- indice posicional, que reordenar uma lista de ataques invalida em silencio,
  levando replays e goldens junto.

De quebra, uma asercao que falha diz ``'cimitarra'`` em vez de ``1``.
"""

from __future__ import annotations

from typing import NewType

CreatureId = NewType("CreatureId", str)
"""Quem participa deste combate. Unico dentro de um `CombatState`."""

StatblockId = NewType("StatblockId", str)
"""Uma ficha do catalogo. Oito goblins identicos compartilham uma so."""

AttackId = NewType("AttackId", str)
"""Um ataque dentro de uma ficha. Slug estavel, nunca posicao na lista."""

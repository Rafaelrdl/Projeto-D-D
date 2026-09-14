"""O formato de retorno do motor.

Toda funcao publica que muda o combate devolve um destes, e nunca um
`CombatState` pelado: o estado sozinho nao diz o que aconteceu, e e o "o que
aconteceu" que os testes afirmam e que uma interface futura vai exibir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tacticore.core.enums import RejectionReason
from tacticore.core.events import Event
from tacticore.core.model import CombatState


@dataclass(frozen=True, slots=True, kw_only=True)
class Applied:
    """A acao valeu: aqui esta o estado novo e o que aconteceu no caminho."""

    kind: Literal["applied"] = "applied"
    state: CombatState
    events: tuple[Event, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Rejected:
    """A acao nao valeu, e o estado nao mudou.

    `state` e a **mesma instancia** que entrou, e nao uma copia: o teste afirma
    `result.state is state` numa linha, e nenhuma copia silenciosa pode se
    disfarçar de "nada mudou".
    """

    kind: Literal["rejected"] = "rejected"
    reason: RejectionReason
    detail: str
    """Texto de diagnostico, **nao contrato**.

    Teste afirma `result.reason`, nunca `result.detail` e nunca
    `result == Rejected(...)`. Comparar a frase amarraria os testes a redacao
    da mensagem, que e justamente a parte que deve poder melhorar.
    """

    state: CombatState


type ActionResult = Applied | Rejected
"""Uniao, e nao `Applied` com um campo de erro opcional.

Com um campo opcional, `result.state` estaria sempre acessivel e bem tipado --
inclusive num resultado rejeitado, que e exatamente o bug silencioso de "usei o
estado de uma acao que nao aconteceu". Com a uniao, mypy obriga a distinguir os
dois antes de chegar no estado.
"""

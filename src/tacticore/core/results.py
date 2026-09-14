"""O formato de retorno do motor.

Toda funcao publica que muda o combate devolve um destes, e nunca um
`CombatState` pelado: o estado sozinho nao diz o que aconteceu, e e o "o que
aconteceu" que os testes afirmam e que uma interface futura vai exibir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tacticore.core.events import Event
from tacticore.core.model import CombatState


@dataclass(frozen=True, slots=True, kw_only=True)
class Applied:
    """A acao valeu: aqui esta o estado novo e o que aconteceu no caminho."""

    kind: Literal["applied"] = "applied"
    state: CombatState
    events: tuple[Event, ...]

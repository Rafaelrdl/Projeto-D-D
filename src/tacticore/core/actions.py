"""O que se pode pedir ao motor.

Uniao discriminada de dataclasses, e nao string com kwargs: `match` sobre ela
com `assert_never` transforma "esqueci de tratar a acao nova" em erro de mypy,
e cada acao carrega exatamente os campos que ela precisa, conferidos na hora
de construir.

Toda acao carrega o `actor` explicitamente, mesmo sendo quase sempre o dono do
turno. Reacao, quando existir, age **fora** do proprio turno, e uma acao que
dependesse do `current` implicito nao teria como representar isso.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tacticore.core.ids import AttackId, CreatureId


@dataclass(frozen=True, slots=True, kw_only=True)
class MoveAction:
    """Gastar deslocamento.

    Sem posicao: nao ha grid nesta etapa. Debita o orcamento e mais nada, que
    e o pedaco do movimento que **existe** hoje. Quando o grid entrar, esta
    acao ganha um destino e a economia de turno continua a mesma.
    """

    kind: Literal["move"] = "move"
    actor: CreatureId
    distance_ft: int


@dataclass(frozen=True, slots=True, kw_only=True)
class EndTurnAction:
    """Encerrar o turno antes de gastar tudo.

    O turno nao avanca sozinho quando a economia acaba: sem `EndTurn`
    explicito, quem controla o combate perderia a chance de agir entre a ultima
    acao e a passagem de turno, e o log nao teria onde marcar a decisao de
    passar.
    """

    kind: Literal["end_turn"] = "end_turn"
    actor: CreatureId


@dataclass(frozen=True, slots=True, kw_only=True)
class AttackAction:
    """Atacar alguem com um dos ataques da propria ficha."""

    kind: Literal["attack"] = "attack"
    actor: CreatureId
    target: CreatureId
    attack_id: AttackId
    """Slug do ataque na ficha, nunca posicao na lista.

    Reordenar os ataques de um monstro nao pode invalidar um replay em
    silencio, e uma asercao que falha diz `'cimitarra'` em vez de `1`.
    """

    advantage_sources: tuple[str, ...] = ()
    """Por que ha vantagem, e nao so quanta.

    Tupla **ordenada** e jamais `set`: ordem de iteracao de conjunto varia com
    `PYTHONHASHSEED`, e isso quebraria o determinismo de um jeito que so
    aparece de vez em quando -- o pior modo de falha possivel aqui. Guardar os
    motivos, e nao um contador, e o que faz o log explicar a rolagem.
    """

    disadvantage_sources: tuple[str, ...] = ()


type Action = AttackAction | MoveAction | EndTurnAction

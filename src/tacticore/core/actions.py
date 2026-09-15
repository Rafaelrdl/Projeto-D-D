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
from tacticore.core.model import Position


@dataclass(frozen=True, slots=True, kw_only=True)
class MoveAction:
    """Ir para uma casa.

    Destino, e nao trajeto: o motor nao sabe por onde se passou, so onde se
    chegou. Enquanto nao houver terreno dificil nem obstaculo, o trajeto nao
    muda resposta nenhuma -- e guardar um caminho que ninguem consulta seria
    guardar o que nao se usa.

    O custo e a distancia de grade entre a casa atual e o destino, e sai do
    mesmo orcamento em pes de `TurnBudget`. A economia de turno nao mudou: o
    que mudou e que agora ela paga por algo.
    """

    kind: Literal["move"] = "move"
    actor: CreatureId
    to: Position


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


@dataclass(frozen=True, slots=True, kw_only=True)
class StandUpAction:
    """Levantar-se de Caido.

    Nao gasta a acao do turno: custa metade do deslocamento, como manda a SRD.
    Hoje e a UNICA transicao de condicao que o motor sabe fazer -- a aplicacao
    vem do encontro, e a fonte de verdade (Empurrar, magia) chega na etapa 3.
    """

    kind: Literal["stand_up"] = "stand_up"
    actor: CreatureId


@dataclass(frozen=True, slots=True, kw_only=True)
class ShoveAction:
    """Empurrar para derrubar: o primeiro teste de atributo oposto do motor.

    Gasta a ACAO. Na SRD, Empurrar e "a special melee attack" que "replaces one
    of them" quando alguem tem multiplos ataques -- e com um ataque por acao,
    que e o recorte deste motor, isso e a mesma frase que "gasta a acao".

    **Nao carrega `attack_id`**, e essa e a diferenca que mais custa entender:
    a SRD abre a regra dizendo "Instead of making an attack roll, you make a
    Strength (Athletics) check". Nao ha arma envolvida, entao o alcance nao pode
    sair de `AttackProfile` -- ler `range_ft` daria 120 pes ao arcanista e
    deixaria sem empurrao quem nao tem arma corpo a corpo. Empurra-se com as
    maos, de casa adjacente, sempre.

    .. warning::
       **E uma jogada dominada no recorte de hoje, e isso e limitacao
       declarada, nao bug.** Medido em 500 duelos: quem so bate ganha 370;
       quem empurra uma vez ganha 276; quem empurra sempre ganha ZERO. Derrubar
       custa a acao inteira e devolve vantagem para o ataque seguinte, que num
       motor sem multiataque, acao bonus e reacao nunca chega a compensar. As
       tres estao fora de escopo por decisao escrita, e e a entrada delas que
       torna o empurrao uma jogada de verdade.
    """

    kind: Literal["shove"] = "shove"
    actor: CreatureId
    target: CreatureId


type Action = AttackAction | MoveAction | EndTurnAction | StandUpAction | ShoveAction

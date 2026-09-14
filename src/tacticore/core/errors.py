"""Excecoes do core.

Regra de bolso: excecao aqui e para **bug do motor** ou **dado externo
invalido**. Regra de jogo violada (atacar fora do turno, alvo inexistente)
nunca vira excecao -- vira ``Rejected``, que o chamador e obrigado a tratar
porque o tipo de retorno diz isso.
"""

from __future__ import annotations


class RngExhausted(RuntimeError):
    """A fita de um ``ScriptedRng`` acabou.

    Nunca ciclamos de volta ao inicio: um teste que pede mais dados do que
    escreveu esta afirmando uma regra que nao entendeu, e silenciosamente
    reaproveitar a fita esconderia exatamente isso.
    """


class ScriptedRngOutOfRange(ValueError):
    """A fita mandou um valor impossivel para o dado pedido.

    Devolver o valor mesmo assim seria o pior modo de falha do projeto: o teste
    passaria afirmando um resultado que o motor de verdade nunca produz.
    """


class DiceSyntaxError(ValueError):
    """Notacao de dados invalida.

    Notacao e **formato de autoria**: entra uma vez, vinda de fora do motor,
    e vira `DamageExpr` estruturada. Por isso a gramatica e estrita e a falha e
    alta -- uma expressao malformada aceita em silencio vira dano errado tres
    camadas adiante, sem nada apontando para a origem.
    """


class UnsupportedSchemaVersion(ValueError):
    """O save veio num formato que este motor nao sabe ler.

    Falhar alto e o ponto: um envelope de versao desconhecida aceito "na boa"
    carregaria campos faltando com default e simularia um combate diferente do
    que foi salvo, sem nada apontando para a causa.
    """


class InvalidSaveError(ValueError):
    """O save carregou, mas o estado descrito nele nao faz sentido.

    Save e dado externo: pode ter sido editado a mao, truncado ou gerado por
    uma versao com bug. Sem esta checagem, um `current` que nao esta na ordem
    de iniciativa entra no motor e reaparece como `CorruptStateError` tres
    turnos depois, longe da causa.

    Distinta de `CorruptStateError`, que fica reservada a bug **deste** motor.
    """


class CorruptStateError(RuntimeError):
    """Uma invariante interna do motor foi quebrada. Isto e bug nosso.

    Nunca e regra de jogo violada -- regra violada vira `Rejected`, que o
    chamador e obrigado a tratar porque o tipo de retorno diz isso.
    """


class InvalidEncounterError(ValueError):
    """O encontro que tentaram montar nao descreve um combate possivel.

    E excecao e nao rejeicao porque o dado do encontro vem de fora do motor, do
    mesmo lugar que a notacao de dados: e erro de autoria, nao jogada ilegal.

    Existir tambem sustenta uma afirmacao do desenho: como `start_combat` e o
    unico construtor e recusa encontro impossivel, o estado sempre nasce com
    combate em andamento -- e por isso `TurnOrder.current` pode ser um id
    obrigatorio em vez de opcional, e nao precisa existir uma fase SETUP.
    """

"""Enumeracoes fechadas do dominio.

Todas sao ``StrEnum``: serializam como a propria string, sem codec, e um save
aberto num editor de texto continua legivel. Fechadas porque `match` sobre elas
com ``assert_never`` transforma "esqueci de tratar um caso novo" em erro de
mypy, e nao em bug de regra descoberto no combate.

Cada enum entra junto com a mecanica que a consome, e nao antes.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class Ability(StrEnum):
    """Os seis atributos.

    As siglas sao as da traducao brasileira, porque sao elas que vao aparecer
    no JSON de save e em toda mensagem de erro do projeto.
    """

    FOR = "FOR"
    DES = "DES"
    CON = "CON"
    INT = "INT"
    SAB = "SAB"
    CAR = "CAR"


class AdvantageState(StrEnum):
    """O resultado de somar todas as fontes de vantagem e desvantagem.

    Tres estados e nao um contador: na SRD a regra e binaria e nao acumula --
    tres fontes de vantagem contra uma de desvantagem da NORMAL, e nunca
    existem tres d20. Guardar o saldo numerico convidaria alguem a "somar
    direito" um dia e mudaria a regra sem querer.
    """

    NORMAL = "NORMAL"
    ADVANTAGE = "ADVANTAGE"
    DISADVANTAGE = "DISADVANTAGE"


class AttackOutcome(StrEnum):
    """Como um ataque terminou.

    `CRITICAL_MISS` fica separado de `MISS` mesmo sendo hoje identico a ele.
    Custa um membro de enum agora; sem ele, a primeira mecanica de falha
    critica (uma mesa que faz o 1 natural ter efeito) obrigaria a recalcular o
    que era um 1 natural a partir do log, e o teste dela mexeria em todos os
    testes que hoje afirmam `MISS`.
    """

    CRITICAL_HIT = "CRITICAL_HIT"
    HIT = "HIT"
    MISS = "MISS"
    CRITICAL_MISS = "CRITICAL_MISS"


class RejectionReason(StrEnum):
    """Por que o motor recusou uma acao.

    Enum fechado e nao texto livre: o chamador compara com um membro, nunca com
    uma frase, e um teste de exaustividade garante que todo membro daqui tenha
    teste proprio. Motivo novo sem teste fica vermelho no mesmo commit.
    """

    NO_SUCH_ACTOR = "NO_SUCH_ACTOR"
    NOT_YOUR_TURN = "NOT_YOUR_TURN"
    ACTOR_IS_DOWN = "ACTOR_IS_DOWN"
    NOT_ENOUGH_MOVEMENT = "NOT_ENOUGH_MOVEMENT"
    SQUARE_OCCUPIED = "SQUARE_OCCUPIED"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    ACTION_ALREADY_USED = "ACTION_ALREADY_USED"
    NO_SUCH_TARGET = "NO_SUCH_TARGET"
    NO_SUCH_ATTACK = "NO_SUCH_ATTACK"
    SELF_TARGET_NOT_ALLOWED = "SELF_TARGET_NOT_ALLOWED"
    COMBAT_OVER = "COMBAT_OVER"


class SkipReason(StrEnum):
    """Por que um turno foi pulado.

    Separado de `RejectionReason` de proposito: turno pulado nao e acao
    recusada -- ninguem pediu nada. Reusar o outro enum aqui faria a interface
    tratar as duas coisas pelo mesmo caminho.
    """

    ACTOR_IS_DOWN = "ACTOR_IS_DOWN"


class Condition(StrEnum):
    """Condicoes que um combatente pode carregar.

    Nasce com **um** membro, como manda o docstring no topo deste modulo: cada
    enum entra junto com a mecanica que o consome. Cego, Envenenado e o resto da
    lista da SRD entram quando houver uma fonte que os produza -- hoje as fontes
    deles sao magia, salvaguarda e iluminacao, e as tres estao fora de escopo
    por decisao escrita.

    E `StrEnum` puro e nao dataclass: um `ActiveCondition` com `source` e
    `duracao` teria `source` constante (a unica fonte e o encontro) e duracao
    fora de escopo -- dois campos inertes, mais um codec, mais uma entrada no
    guardiao. Quando duracao entrar, o enum vira dataclass num commit proprio.
    """

    CAIDO = "CAIDO"


def canonical_conditions(conditions: Iterable[Condition]) -> tuple[Condition, ...]:
    """Ordena pelo valor e tira repeticao.

    Existe porque `Combatant.conditions` e uma tupla, e tupla aceita ordem
    arbitraria e repeticao -- duas coisas que mudam o `fingerprint` sem mudar o
    estado logico, ja que `canonical_json` ordena chaves de objeto e **nao**
    itens de lista. Toda escrita no campo passa por aqui; a invariante de carga
    confere que passou.

    Pelo **valor** da string e nao pela ordem de declaracao do enum: declarar um
    membro novo no meio re-canonizaria todo save existente sem salto de schema.

    Mora aqui, e nao em `rules`, pelo mesmo motivo que `PES_POR_CASA` mora em
    `model`: e propriedade do vocabulario e nao regra de jogo, e `serde` precisa
    dela tanto quanto quem escreve o campo. Presa em `rules`, o guardiao de
    camadas reprovaria `serde` -- e foi ele que apontou, de novo.
    """
    return tuple(sorted(set(conditions), key=str))

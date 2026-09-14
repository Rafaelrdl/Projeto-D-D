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

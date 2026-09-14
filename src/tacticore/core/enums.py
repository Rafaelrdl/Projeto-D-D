"""Enumeracoes fechadas do dominio.

Todas sao ``StrEnum``: serializam como a propria string, sem codec, e um save
aberto num editor de texto continua legivel. Fechadas porque `match` sobre elas
com ``assert_never`` transforma "esqueci de tratar um caso novo" em erro de
mypy, e nao em bug de regra descoberto no combate.

Cada enum entra junto com a mecanica que a consome, e nao antes.
"""

from __future__ import annotations

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

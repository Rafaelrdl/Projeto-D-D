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

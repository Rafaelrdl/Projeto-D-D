"""Nenhuma funcao de `rules.py` toca `CombatState`.

A regra parece arbitraria e nao e. Uma funcao de regra que recebe o estado
inteiro so pode ser testada montando um combate, e a partir daí ninguem mais
escreve o teste da tabela de modificadores de 1 a 30 -- escreve um teste de
integracao que passa pelo motivo errado. `rules.py` recebe numeros e
descritores; quem conhece o estado e o `engine`.

O guardiao olha a assinatura e nao o import, porque `rules.py` importa
`model` legitimamente (para `Abilities`, por exemplo). O que nao pode e
`CombatState` aparecer numa assinatura.
"""

from __future__ import annotations

import inspect

import pytest

from tacticore.core import rules

PROIBIDO = "CombatState"

FUNCOES = [
    (nome, obj)
    for nome, obj in inspect.getmembers(rules, inspect.isfunction)
    if obj.__module__ == rules.__name__ and not nome.startswith("_")
]
IDS = [nome for nome, _ in FUNCOES]


def test_rules_tem_funcao_publica_para_guardar():
    assert FUNCOES, "nenhuma funcao encontrada: a descoberta esta quebrada"


@pytest.mark.parametrize(("nome", "funcao"), FUNCOES, ids=IDS)
def test_funcao_de_regra_nao_recebe_nem_devolve_estado_de_combate(nome: str, funcao: object):
    assinatura = inspect.signature(funcao)  # type: ignore[arg-type]

    for parametro in assinatura.parameters.values():
        anotacao = str(parametro.annotation)
        assert PROIBIDO not in anotacao, (
            f"rules.{nome} recebe {parametro.name}: {anotacao}. "
            "Regra recebe numero e descritor; quem conhece o estado e o engine."
        )

    retorno = str(assinatura.return_annotation)
    assert PROIBIDO not in retorno, f"rules.{nome} devolve {retorno}"

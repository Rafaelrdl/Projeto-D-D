"""Guardioes estruturais do estado.

Sao tres perguntas que ninguem lembra de fazer no code review da decima
dataclass: ela e imutavel? o tipo dela serializa? tem campo que so existe em
memoria? Aqui elas sao feitas automaticamente, para toda dataclass do core, e
uma dataclass nova ja nasce coberta sem ninguem precisar registrar nada.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
import re
from collections.abc import Mapping
from enum import StrEnum

import pytest

import tacticore.core
from tacticore.core.dice import parse_dice
from tacticore.core.enums import Ability, Condition
from tacticore.core.model import CombatState
from tacticore.core.rng import ScriptedRng, SplitMix64
from tacticore.core.testing import (
    make_attack,
    make_combatant,
    make_statblock,
    make_state,
)

# `list`/`dict` mutaveis viram estado compartilhado por acidente; `set` tem
# ordem de iteracao que varia com PYTHONHASHSEED; `float` em JSON e round-trip
# que quase bate; `Any` e a porta por onde os tres voltam sem ninguem ver.
ANOTACOES_PROIBIDAS = re.compile(r"\b(list|dict|set|float|Any|List|Dict|Set)\b")


def _modulos_do_core() -> list[str]:
    return [info.name for info in pkgutil.iter_modules(tacticore.core.__path__) if not info.ispkg]


def _dataclasses_do_core() -> list[type]:
    encontradas: list[type] = []
    for nome in _modulos_do_core():
        modulo = importlib.import_module(f"tacticore.core.{nome}")
        encontradas.extend(
            obj
            for _, obj in inspect.getmembers(modulo, inspect.isclass)
            if dataclasses.is_dataclass(obj) and obj.__module__ == modulo.__name__
        )
    return sorted(set(encontradas), key=lambda c: (c.__module__, c.__name__))


DATACLASSES = _dataclasses_do_core()
IDS = [f"{c.__module__.split('.')[-1]}.{c.__name__}" for c in DATACLASSES]


def test_o_core_tem_dataclasses_para_guardar():
    """Se a descoberta quebrar, os dois testes abaixo passariam vazios."""
    assert DATACLASSES, "nenhuma dataclass encontrada: a descoberta esta quebrada"


@pytest.mark.parametrize("cls", DATACLASSES, ids=IDS)
def test_dataclass_e_frozen_slots_e_kw_only(cls: type):
    params = cls.__dataclass_params__  # type: ignore[attr-defined]
    assert params.frozen, f"{cls.__name__} nao e frozen: 'devolve estado novo' vira promessa"
    assert params.kw_only, (
        f"{cls.__name__} nao e kw_only: dois int adjacentes trocados de lugar passam despercebidos"
    )
    assert "__slots__" in vars(cls), (
        f"{cls.__name__} nao tem slots: da para pendurar atributo que nao serializa"
    )


@pytest.mark.parametrize("cls", DATACLASSES, ids=IDS)
def test_dataclass_nao_usa_anotacao_proibida(cls: type):
    for campo, anotacao in cls.__annotations__.items():
        texto = anotacao if isinstance(anotacao, str) else str(anotacao)
        proibido = ANOTACOES_PROIBIDAS.search(texto)
        assert proibido is None, (
            f"{cls.__name__}.{campo}: {texto!r} usa {proibido.group() if proibido else ''!r}, "
            "que nao entra em campo de estado"
        )


def test_o_guardiao_de_anotacao_sabe_reprovar():
    """Trava que nunca falha e decoracao. Esta falha com o que deveria falhar."""

    @dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
    class Ruim:
        valores: list[int]
        peso: float

    for anotacao in Ruim.__annotations__.values():
        assert ANOTACOES_PROIBIDAS.search(str(anotacao)) is not None


# ------------------------------------------------- lista branca em runtime ---


def _validar_valor(valor: object, caminho: str) -> None:
    if isinstance(valor, StrEnum | bool | int | str):
        return
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        for campo in dataclasses.fields(valor):
            _validar_valor(getattr(valor, campo.name), f"{caminho}.{campo.name}")
        return
    if isinstance(valor, tuple):
        for indice, item in enumerate(valor):
            _validar_valor(item, f"{caminho}[{indice}]")
        return
    if isinstance(valor, Mapping):
        for chave, item in valor.items():
            assert isinstance(chave, str), (
                f"{caminho}: chave {chave!r} nao e str; chave nao-str nao sobrevive ao JSON"
            )
            _validar_valor(item, f"{caminho}[{chave!r}]")
        return

    msg = f"{caminho}: {type(valor).__name__} nao esta na lista branca de tipos de estado"
    raise AssertionError(msg)


def _estado_gordo() -> CombatState:
    """Um estado com o maximo de variedade que existe hoje.

    Vale mais que um estado minimo: o guardiao so encontra o tipo proibido se o
    campo que o carrega estiver preenchido.
    """
    ficha = make_statblock(
        id="goblin",
        attacks=(
            make_attack(id="cimitarra", damage="1d6+1"),
            make_attack(
                id="arco",
                ability=Ability.DES,
                proficient=False,
                damage=parse_dice("1d6"),
                adds_ability_to_damage=False,
            ),
        ),
    )
    return make_state(
        statblocks=(ficha,),
        combatants=(
            make_combatant(
                id="goblin_1",
                statblock_id="goblin",
                team="inimigos",
                hp=0,
                # A lacuna do quadruplo do CLAUDE.md, fechada onde ela deixa de
                # ser higiene retroativa: ate a etapa 3, `CAIDO` so vinha do
                # encontro, e ninguem tinha notado que o estado gordo nao a
                # carregava -- `Condition` e `StrEnum` e passaria na lista
                # branca de qualquer jeito. E este commit que cria a primeira
                # FONTE de `CAIDO` dentro do motor.
                conditions=(Condition.CAIDO,),
            ),
            make_combatant(id="goblin_2", statblock_id="goblin", team="inimigos"),
        ),
        current="goblin_2",
        round_number=3,
        rng=SplitMix64(seed=42, counter=17),
    )


def test_estado_inteiro_so_tem_tipo_da_lista_branca():
    _validar_valor(_estado_gordo(), "state")


def test_estado_com_fita_tambem_passa():
    """A outra metade da uniao do RNG tambem mora dentro do estado."""
    _validar_valor(make_state(rng=ScriptedRng(script=(20, 1))), "state")


def test_o_guardiao_de_runtime_sabe_reprovar():
    with pytest.raises(AssertionError, match="nao esta na lista branca"):
        _validar_valor({"faces": {1, 2, 3}}, "state")

    with pytest.raises(AssertionError, match="nao esta na lista branca"):
        _validar_valor((1.5,), "state")

    with pytest.raises(AssertionError, match=r"chave .* nao e str"):
        _validar_valor({1: "um"}, "state")

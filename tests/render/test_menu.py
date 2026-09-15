"""O menu e a leitura da escolha.

A trava que importa nao e "entrada ruim nao estoura" -- e **entrada ruim nao
devolve acao fora do menu**. O motor aceita, de proposito, acoes que
`legal_actions` nao ofereceu: `validate` responde "isto e legal?" e
`legal_actions` responde "o que vale a pena oferecer?". Um leitor que
convertesse "9" num indice sem conferir a faixa entregaria ao motor uma acao
que ninguem ofereceu, e `apply` poderia aceita-la em silencio.
"""

from __future__ import annotations

import pytest

from tacticore.core.actions import (
    Action,
    AttackAction,
    EndTurnAction,
    MoveAction,
    ShoveAction,
    StandUpAction,
)
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import Position
from tacticore.render.menu import descrever, escolha, menu

ATACAR = AttackAction(
    actor=CreatureId("heroi"), target=CreatureId("vilao"), attack_id=AttackId("machado")
)
LEVANTAR = StandUpAction(actor=CreatureId("heroi"))
ANDAR = MoveAction(actor=CreatureId("heroi"), to=Position(x=2, y=-1))
ENCERRAR = EndTurnAction(actor=CreatureId("heroi"))

EMPURRAR = ShoveAction(actor=CreatureId("heroi"), target=CreatureId("vilao"))

MENU = (ATACAR, LEVANTAR, ANDAR, ENCERRAR)
"""O menu das asercoes de INDICE. Quatro itens, e mexer nisto quebra os testes
de faixa la embaixo -- acao nova entra em `DESCRICOES`, e nao aqui."""

DESCRICOES: list[tuple[Action, str]] = [
    (ATACAR, "atacar vilao com machado"),
    (LEVANTAR, "levantar"),
    (ANDAR, "andar ate (2,-1)"),
    (EMPURRAR, "empurrar vilao"),
    (ENCERRAR, "encerrar o turno"),
]
"""Uma entrada por membro da uniao `Action`, e um teste que cobra isso.

A uniao `Action` era a unica das quatro unioes fechadas do projeto sem guardiao
de teste: `Event` tem dois (codec e narrativa), `RejectionReason` tem um de
exaustividade, e esta nao tinha nenhum. Medido: `ShoveAction` entrou na uniao e
a suite deu 1047 verdes com tres erros de mypy -- ou seja, quem rodasse so o
pytest nao veria nada."""


# ------------------------------------------------------------ o menu -------


def test_o_menu_numera_a_partir_de_um():
    """Quem digita nao esta indexando uma lista."""
    assert menu(MENU)[0].startswith("1 ")
    assert menu(MENU)[-1].startswith("4 ")


def test_o_menu_preserva_a_ordem_recebida():
    """A ordem e contrato do ADR 0002 sec. 1. Um menu que a reorganizasse faria
    `acoes[0]` significar coisas diferentes para o piloto e para o humano."""
    invertido = tuple(reversed(MENU))
    assert [linha.split(" ", 1)[1] for linha in menu(invertido)] == [
        descrever(a) for a in invertido
    ]


def test_o_menu_vazio_e_vazio_e_nao_estoura():
    """`legal_actions` devolve `()` em dois casos legitimos."""
    assert menu(()) == ()


@pytest.mark.parametrize(
    ("action", "trecho"),
    DESCRICOES,
    ids=[type(a).__name__ for a, _ in DESCRICOES],
)
def test_cada_acao_da_uniao_tem_descricao(action: Action, trecho: str):
    """Se um membro novo entrar sem frase, o `assert_never` reprova no mypy --
    mas este teste e quem garante que a frase diz algo, e nao so que existe."""
    assert descrever(action) == trecho


def test_toda_acao_da_uniao_tem_caso_aqui():
    """Acao nova sem descricao testada reprova **pelo nome**.

    O `assert_never` de `descrever` ja pega no mypy; este pega para quem rodar
    so a suite, e nomeia o culpado. E o espelho de
    `test_todo_evento_tem_caso_aqui`, que a uniao `Event` tem desde a etapa 2 e
    que a uniao `Action` nao tinha.
    """
    cobertas = {type(a) for a, _ in DESCRICOES}
    membros = set(Action.__value__.__args__)  # type: ignore[attr-defined]
    faltando = membros - cobertas
    assert not faltando, f"acoes sem descricao testada: {sorted(c.__name__ for c in faltando)}"


def test_nenhuma_linha_do_menu_e_vazia():
    """Item em branco e um item que o jogador escolhe sem saber o que e."""
    for linha in menu(MENU):
        assert linha.split(" ", 1)[1].strip()


# --------------------------------------------------------- a escolha -------


ARABICO_UM = chr(0x0661)
EXPOENTE_DOIS = chr(0x00B2)
"""Escritos por ponto de codigo porque escritos por caractere sao
indistinguiveis de um `1` e de um `2` na revisao -- que e metade do motivo de
serem uma armadilha. O ruff reprova o caractere ambiguo no fonte (RUF001).
"""

ENTRADAS_RUINS = [
    "",
    " ",
    "0",
    "5",
    "99",
    "-1",
    "abc",
    "1.0",
    "1 2",
    "+2",
    "1_0",
    "2a",
    "nan",
    # Os dois que quase passaram: `isdigit` sozinho diz True para ambos, o
    # arabico-indiano UM vira 1 e escolheria o primeiro item do menu, e o
    # expoente DOIS passa no filtro e faz `int` LEVANTAR.
    ARABICO_UM,
    EXPOENTE_DOIS,
]


@pytest.mark.parametrize("entrada", ["1", "2", "3", "4"])
def test_a_escolha_valida_devolve_o_item_certo(entrada: str):
    assert escolha(entrada, MENU) is MENU[int(entrada) - 1]


@pytest.mark.parametrize("entrada", [" 2 ", "\t2", "2\n"])
def test_espaco_em_volta_nao_atrapalha(entrada: str):
    """Quem digita num terminal esbarra em espaco e em enter."""
    assert escolha(entrada, MENU) is LEVANTAR


@pytest.mark.parametrize(
    "entrada",
    ENTRADAS_RUINS,
)
def test_entrada_ruim_devolve_none_e_nao_estoura(entrada: str):
    assert escolha(entrada, MENU) is None


@pytest.mark.parametrize(
    "entrada",
    ENTRADAS_RUINS,
)
def test_entrada_ruim_jamais_devolve_acao_fora_do_menu(entrada: str):
    """A trava de verdade. A de cima passaria num `escolha` que devolvesse
    `MENU[0]` para tudo que nao entendesse -- e ai o jogador que errou de tecla
    atacaria alguem."""
    resultado = escolha(entrada, MENU)
    assert resultado is None or resultado in MENU


def test_nenhuma_entrada_alcanca_item_fora_da_faixa():
    """Varredura: nenhuma string de ate dois caracteres imprimiveis pode
    devolver algo que nao esteja na tupla oferecida."""
    alfabeto = "0123456789+- .abc"
    candidatas = [a + b for a in alfabeto for b in alfabeto] + list(alfabeto)
    for entrada in candidatas:
        resultado = escolha(entrada, MENU)
        assert resultado is None or resultado in MENU


def test_a_escolha_no_menu_vazio_nao_encontra_nada():
    assert escolha("1", ()) is None


def test_menu_e_escolha_falam_o_mesmo_numero():
    """A trava que liga as duas metades: o numero impresso e o numero aceito.

    Sem ela, `menu` podendo comecar em 1 e `escolha` em 0 passaria em todos os
    testes acima separadamente."""
    for linha, esperada in zip(menu(MENU), MENU, strict=True):
        assert escolha(linha.split(" ", 1)[0], MENU) is esperada

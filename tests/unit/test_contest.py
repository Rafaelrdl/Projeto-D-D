"""Teste de atributo oposto.

A regra que este arquivo existe para travar cabe numa frase: **empate nao e
sucesso**. `d20_check`, a funcao vizinha, diz o contrario -- "Empate passa" esta
escrito no docstring dela -- e as duas leituras sao defensaveis em contextos
diferentes. A SRD e explicita sobre qual vale aqui: "If the contest results in a
tie, the situation remains the same as it was before the contest."

Uma implementacao que reaproveitasse `d20_check` passaria em quase tudo que se
possa testar sobre um empurrao, e erraria exatamente 1 caso em 20.
"""

from __future__ import annotations

import pytest

from tacticore.core.enums import Ability, AdvantageState, ContestOutcome
from tacticore.core.rules import (
    ContestResult,
    D20Roll,
    ability_modifier,
    ability_score,
    contest,
    d20_check,
    defense_ability,
)
from tacticore.core.testing import make_abilities


def rolagem(natural: int) -> D20Roll:
    """Um d20 ja rolado, sem passar pelo RNG.

    `contest` nao rola nada -- quem rola e o motor --, entao o teste da regra
    nao precisa de fita nem de seed. O par vem com o descartado igual ao
    escolhido para deixar claro que ele nao participa da conta.
    """
    return D20Roll(
        pair=(natural, natural),
        chosen_index=0,
        natural=natural,
        advantage=AdvantageState.NORMAL,
    )


def disputa(*, ator: int, bonus_ator: int, alvo: int, bonus_alvo: int) -> ContestResult:
    return contest(
        actor=rolagem(ator),
        actor_bonus=bonus_ator,
        target=rolagem(alvo),
        target_bonus=bonus_alvo,
    )


# -------------------------------------------------------- o desfecho -------


def test_total_maior_vence():
    r = disputa(ator=15, bonus_ator=3, alvo=10, bonus_alvo=2)
    assert r.outcome is ContestOutcome.SUCCESS


def test_total_menor_perde():
    r = disputa(ator=5, bonus_ator=0, alvo=18, bonus_alvo=1)
    assert r.outcome is ContestOutcome.FAILURE


def test_empate_nao_e_sucesso():
    """A regra inteira deste arquivo.

    "If the contest results in a tie, the situation remains the same as it was
    before the contest" -- e para quem iniciou, "a situacao nao muda" quer dizer
    que o empurrao nao aconteceu.
    """
    r = disputa(ator=12, bonus_ator=3, alvo=12, bonus_alvo=3)
    assert r.outcome is ContestOutcome.TIE
    assert r.outcome is not ContestOutcome.SUCCESS


def test_o_empate_e_de_TOTAL_e_nao_de_DADO():
    """Dados diferentes, bonus diferentes, mesmo total: e empate.

    Uma implementacao que comparasse `natural` em vez de `total` passaria no
    teste de cima e falharia aqui.
    """
    r = disputa(ator=10, bonus_ator=5, alvo=13, bonus_alvo=2)
    assert (r.actor_natural, r.target_natural) == (10, 13)
    assert r.actor_total == r.target_total == 15
    assert r.outcome is ContestOutcome.TIE


@pytest.mark.parametrize("bonus", [-3, 0, 4])
def test_um_ponto_de_diferenca_ja_decide(bonus: int):
    """A fronteira, dos dois lados, com o bonus variando junto."""
    assert disputa(ator=11, bonus_ator=bonus, alvo=10, bonus_alvo=bonus).outcome is (
        ContestOutcome.SUCCESS
    )
    assert disputa(ator=10, bonus_ator=bonus, alvo=11, bonus_alvo=bonus).outcome is (
        ContestOutcome.FAILURE
    )


def test_a_regra_nao_e_a_de_d20_check():
    """A trava explicita contra o reaproveitamento errado.

    `d20_check(roll, bonus=3, dc=15)` com natural 12 da `success=True`, porque
    la empate passa. A mesma aritmetica aqui da TIE.
    """
    checagem = d20_check(rolagem(12), bonus=3, dc=15)
    assert checagem.success is True, "em d20_check, empate passa"

    oposto = disputa(ator=12, bonus_ator=3, alvo=15, bonus_alvo=0)
    assert oposto.outcome is ContestOutcome.TIE, "em contest, empate nao passa"


# --------------------------------------------------------- as parcelas -----


def test_a_conta_sai_decomposta_dos_dois_lados():
    """O evento publica a conta aberta; devolver so o desfecho obrigaria o
    motor a refazer as somas."""
    r = disputa(ator=14, bonus_ator=3, alvo=9, bonus_alvo=-1)
    assert (r.actor_natural, r.actor_bonus, r.actor_total) == (14, 3, 17)
    assert (r.target_natural, r.target_bonus, r.target_total) == (9, -1, 8)


def test_o_dado_descartado_nao_entra_na_conta():
    """`contest` le `natural`, nunca o par: escolher entre os dois dados e
    trabalho de `roll_d20`, e ja aconteceu quando chegamos aqui."""
    r = contest(
        actor=D20Roll(
            pair=(3, 20), chosen_index=0, natural=3, advantage=AdvantageState.DISADVANTAGE
        ),
        actor_bonus=0,
        target=rolagem(4),
        target_bonus=0,
    )
    assert r.actor_total == 3, "o 20 descartado nao entra"
    assert r.outcome is ContestOutcome.FAILURE


# ------------------------------------------- o atributo de quem resiste ----


def test_quem_tem_forca_resiste_com_forca():
    assert defense_ability(make_abilities(forca=16, destreza=8)) is Ability.FOR


def test_quem_tem_destreza_resiste_com_destreza():
    assert defense_ability(make_abilities(forca=8, destreza=16)) is Ability.DES


def test_com_modificadores_iguais_desempata_FOR_e_isso_so_muda_o_ROTULO():
    """O unico teste do projeto que separa "melhor por FOR" de "melhor por DES".

    FOR 14 e DES 15 dao os dois `+2`, entao o empurrao sai **identico** nas duas
    leituras -- mesmo dado, mesmo total, mesmo desfecho. A unica coisa que muda
    e o atributo que o evento grava, e por isso a asercao e sobre ele.

    Ficha sintetica porque nenhuma das tres do projeto empata: trocar `>=` por
    `>` em `defense_ability` nao move um numero sequer de golden nenhum.
    """
    ficha = make_abilities(forca=14, destreza=15)
    assert defense_ability(ficha) is Ability.FOR


def test_o_desempate_nao_muda_o_resultado_da_disputa():
    """A outra metade da frase acima, escrita como teste para nao virar
    folclore: com modificadores iguais, os dois atributos dao o mesmo total."""
    ficha = make_abilities(forca=14, destreza=15)
    por_forca = ability_modifier(ability_score(ficha, Ability.FOR))
    por_destreza = ability_modifier(ability_score(ficha, Ability.DES))
    assert por_forca == por_destreza == 2


@pytest.mark.parametrize(
    ("forca", "destreza", "esperado"),
    [
        (10, 10, Ability.FOR),
        (1, 20, Ability.DES),
        (20, 1, Ability.FOR),
        (8, 9, Ability.FOR),
        (8, 11, Ability.DES),
    ],
)
def test_a_escolha_e_pelo_MODIFICADOR_e_nao_pelo_VALOR(
    forca: int, destreza: int, esperado: Ability
):
    """`8` e `9` dao os dois `-1`: comparar os valores brutos escolheria DES,
    comparar os modificadores escolhe FOR pelo desempate. E a diferenca entre
    ler a ficha e ler a regra."""
    assert defense_ability(make_abilities(forca=forca, destreza=destreza)) is esperado

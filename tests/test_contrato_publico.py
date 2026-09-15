"""A fachada publica e o contrato escrito.

O contrato de consumo do RNG mora no docstring de `tacticore.core` porque e la
que ele e lido: na hora de escrever a proxima regra, e nao na hora de procurar
documentacao. Este teste existe para que ele nao possa ser apagado sem que
alguem perceba.
"""

from __future__ import annotations

import pytest

from tacticore import core
from tacticore.core.testing import make_duelo, play_out

TRECHOS_OBRIGATORIOS = (
    "CONTRATO DE CONSUMO DO RNG",
    "ordem lexicografica",
    "dois** d20",
    "somente em acerto",
    "recusada nao consome nada",
    # O item 5 nao tinha pino nenhum: apagar as duas linhas dele deixava este
    # arquivo inteiro verde. Conferido antes de acrescentar.
    "nao tem rejeicao",
    # Item 6, uma substring por afirmacao independente: quantos dados por lado,
    # e que o automatismo nunca mexe no consumo.
    "dois por lado",
    "nunca o consumo",
    "RULES_VERSION",
)


@pytest.mark.parametrize("trecho", TRECHOS_OBRIGATORIOS)
def test_o_contrato_do_rng_esta_publicado_na_fachada(trecho: str):
    doc = core.__doc__ or ""
    assert trecho in doc, (
        f"o docstring de tacticore.core perdeu {trecho!r}. O contrato e API "
        "publica: se ele mudou, mude tambem o ADR 0001 e incremente RULES_VERSION."
    )


def test_a_fachada_exporta_o_que_promete():
    faltando = [nome for nome in core.__all__ if not hasattr(core, nome)]
    assert not faltando, f"__all__ promete o que nao existe: {faltando}"


def test_a_fachada_nao_tem_nome_repetido():
    """A ordem de `__all__` quem cuida e o ruff (RUF022); repeticao, ninguem.

    Um teste que reimplementasse a ordenacao do ruff brigaria com o formatador
    -- ele poe as constantes em CAIXA_ALTA antes das classes, e `sorted()` nao.
    """
    assert len(set(core.__all__)) == len(core.__all__)


def test_da_para_rodar_um_combate_so_pela_fachada():
    catalogo, gente = make_duelo()
    abertura = core.start_combat(
        statblocks=catalogo, participants=gente, rng=core.SplitMix64(seed=1)
    )
    assert isinstance(abertura, core.Applied)

    estado, _ = play_out(abertura.state)
    assert core.combat_result(estado) is not None
    assert core.load(core.dump(estado)) == estado

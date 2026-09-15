"""O combate canonico congelado: em texto e em desenho.

Estes goldens sao de APRESENTACAO, e nao de regra. A diferenca importa e por
isso eles moram fora de `tests/golden/data/`: aqui, um diff e quase sempre
"mudei a redacao", e regravar nao exige justificativa nenhuma. La, um diff e "o
motor calcula outra coisa", e exige uma frase no commit.

O que eles pegam: uma mudanca de redacao que ninguem pediu, o dia em que um
evento novo passar a aparecer no log, e o dia em que o desenho do tabuleiro
mudar de forma.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tacticore.__main__ import SEED_PADRAO, combate_narrado
from tacticore.content.srd import CATALOGO, duelo
from tacticore.core.engine import start_combat
from tacticore.core.rng import SplitMix64
from tacticore.core.testing import play_out
from tacticore.render import board

DADOS = Path(__file__).parent / "data"
ARQUIVO = DADOS / "duelo.txt"
TABULEIRO = DADOS / "tabuleiro.txt"


def test_o_duelo_narrado(update_golden: bool):
    texto = "\n".join(combate_narrado(SEED_PADRAO)) + "\n"

    if update_golden:
        ARQUIVO.write_text(texto, encoding="utf-8", newline="\n")
        pytest.skip("golden de apresentacao regravado")

    assert ARQUIVO.is_file(), f"rode com --update-golden para criar {ARQUIVO}"
    assert texto == ARQUIVO.read_text(encoding="utf-8"), (
        "a narrativa mudou. Se foi redacao, regrave sem cerimonia: este golden "
        "e de apresentacao. Se apareceu evento novo no log, o motor mudou e o "
        "lugar de explicar isso e o commit de tests/golden/."
    )


def test_o_golden_de_texto_nao_esta_vazio():
    """Um arquivo vazio passaria no teste de cima se a narracao sumisse."""
    linhas = ARQUIVO.read_text(encoding="utf-8").splitlines()
    assert len(linhas) > 10
    assert linhas[-1].startswith("combate encerrado")


ABERTURA = "== abertura =="
FIM = "== fim =="


def tabuleiros() -> str:
    """O mesmo duelo da narrativa, retratado na abertura e no fim.

    Dois retratos e nao um: a abertura mostra a grade com todo mundo de pe, e o
    fim mostra o glifo de quem caiu. Com um so, metade do desenho ficaria sem
    golden.
    """
    abertura = start_combat(
        statblocks=CATALOGO, participants=duelo(), rng=SplitMix64(seed=SEED_PADRAO)
    )
    final, _ = play_out(abertura.state)
    linhas = [ABERTURA, *board(abertura.state), "", FIM, *board(final)]
    return "\n".join(linhas) + "\n"


def test_o_tabuleiro_do_duelo(update_golden: bool):
    texto = tabuleiros()

    if update_golden:
        TABULEIRO.write_text(texto, encoding="utf-8", newline="\n")
        pytest.skip("golden de apresentacao regravado")

    assert TABULEIRO.is_file(), f"rode com --update-golden para criar {TABULEIRO}"
    assert texto == TABULEIRO.read_text(encoding="utf-8"), (
        "o desenho mudou. Se foi so a forma do tabuleiro, regrave sem cerimonia. "
        "Se as POSICOES mudaram, o motor passou a mover diferente e o lugar de "
        "explicar isso e o commit de tests/golden/."
    )


def test_os_dois_retratos_do_tabuleiro_sao_diferentes():
    """Um `board` que ignorasse o estado gravaria o mesmo desenho duas vezes, e
    o golden congelaria o engano sem ninguem notar."""
    antes, depois = tabuleiros().split(FIM)
    assert antes.split(ABERTURA)[1].strip() != depois.strip()

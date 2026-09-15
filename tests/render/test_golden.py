"""O combate canonico em texto, congelado.

Este golden e de APRESENTACAO, e nao de regra. A diferenca importa e por isso
ele mora fora de `tests/golden/data/`: aqui, um diff e quase sempre "mudei a
redacao", e regravar nao exige justificativa nenhuma. La, um diff e "o motor
calcula outra coisa", e exige uma frase no commit.

O que ele pega: uma mudanca de redacao que ninguem pediu, e o dia em que um
evento novo passar a aparecer no log.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tacticore.__main__ import SEED_PADRAO, combate_narrado

ARQUIVO = Path(__file__).parent / "data" / "duelo.txt"


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

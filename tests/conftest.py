"""Opcoes de linha de comando da suite.

`pytest_addoption` mora na raiz de `tests/` e nao em `tests/golden/` porque uma
opcao so e visivel para os testes **abaixo** do conftest que a registra. Com ela
em `tests/golden/`, o golden de apresentacao em `tests/render/` nao teria como
ser regravado -- descobriria isso na primeira vez que precisasse, com a mensagem
mais confusa que o pytest tem ("unrecognized arguments").
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="regrava os arquivos congelados de tests/golden/ e tests/render/",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    """Se esta rodada deve regravar os arquivos congelados em vez de compara-los.

    Explicita e nunca automatica: um golden que se regrava sozinho quando falha
    nao e uma trava, e um teste que sempre passa.
    """
    return bool(request.config.getoption("--update-golden"))

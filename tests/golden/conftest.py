"""A flag de regravacao dos goldens.

Explicita e nunca automatica: um golden que se regrava sozinho quando falha nao
e uma trava, e um teste que sempre passa.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="regrava os logs canonicos em tests/golden/data/",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-golden"))

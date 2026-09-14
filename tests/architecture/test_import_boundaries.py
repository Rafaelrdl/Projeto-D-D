"""Guardiao das fronteiras de import do core.

Passa trivialmente enquanto o core tem poucos modulos. Existe desde o primeiro
commit exatamente por isso: a trava precisa ser mais velha que a tentacao de
importar `random` "so para testar uma coisa rapida".
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import tacticore.core

CORE_DIR = Path(tacticore.core.__file__).parent
PACKAGE = "tacticore.core"

# Ordem das camadas: um modulo so pode importar modulos de camada ESTRITAMENTE
# menor. Empate significa "nao se conhecem" (ex: actions e events).
LAYERS: dict[str, int] = {
    "ids": 0,
    "enums": 0,
    "errors": 0,
    "rng": 1,
    "dice": 2,
    "model": 3,
    "actions": 4,
    "events": 4,
    "results": 5,
    "rules": 6,
    "queries": 7,
    "engine": 8,
}

# Fora da pilha de camadas: importam ate `results` (camada 5) e nada acima.
OFF_LAYER_MAX = 5
OFF_LAYER: dict[str, int] = {"serde": OFF_LAYER_MAX, "testing": OFF_LAYER_MAX}

# A fachada pode importar tudo; ela existe para reexportar.
FACADE = "__init__"

# Stdlib puro, sem efeito colateral: nada aqui abre arquivo, socket ou relogio.
# `json` entra porque `json.dumps` e manipulacao de string, nao I/O.
ALLOWED_STDLIB = frozenset(
    {
        "__future__",
        "abc",
        "collections",
        "dataclasses",
        "enum",
        "functools",
        "hashlib",
        "itertools",
        "json",
        "math",
        "operator",
        "re",
        "types",
        "typing",
    }
)

# Listados a parte so para a mensagem de erro dizer o porque.
BANNED = {
    "random": "aleatoriedade so pelo RngState que vive dentro do estado",
    "secrets": "aleatoriedade so pelo RngState que vive dentro do estado",
    "uuid": "uuid4 le entropia do SO; identidade e slug legivel fornecido de fora",
    "datetime": "relogio e entrada nao-deterministica",
    "time": "relogio e entrada nao-deterministica",
    "io": "I/O nao entra no core",
    "os": "I/O nao entra no core",
    "sys": "I/O nao entra no core",
    "pathlib": "I/O nao entra no core",
    "shutil": "I/O nao entra no core",
    "tempfile": "I/O nao entra no core",
    "pickle": "serializacao e codec manual em serde.py",
    "socket": "rede nao entra no core",
    "urllib": "rede nao entra no core",
    "http": "rede nao entra no core",
    "logging": "log e apresentacao; o motor devolve eventos",
    "subprocess": "nada disso no core",
    "threading": "nada disso no core",
}


def _module_name(path: Path) -> str:
    return path.stem


def _rank(module: str) -> int | None:
    """Camada do modulo, ou None se ele pode importar qualquer coisa."""
    if module == FACADE:
        return None
    if module in OFF_LAYER:
        return OFF_LAYER[module]
    return LAYERS[module]


def _imports(path: Path) -> list[tuple[str, int, int]]:
    """(modulo importado, nivel relativo, linha) para cada import do arquivo."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, 0, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append((node.module or "", node.level, node.lineno))
    return found


def _top(module: str) -> str:
    return module.split(".", maxsplit=1)[0]


MODULES = sorted(CORE_DIR.glob("*.py"))
IDS = [p.stem for p in MODULES]


def test_todo_modulo_do_core_tem_camada_declarada():
    """Modulo novo sem camada declarada e um buraco silencioso no guardiao."""
    conhecidos = set(LAYERS) | set(OFF_LAYER) | {FACADE}
    desconhecidos = {p.stem for p in MODULES} - conhecidos
    assert not desconhecidos, (
        f"modulos sem camada declarada em LAYERS/OFF_LAYER: {sorted(desconhecidos)}. "
        "Declare a camada junto com o modulo, no mesmo commit."
    )


@pytest.mark.parametrize("path", MODULES, ids=IDS)
def test_core_nao_importa_io_rede_nem_aleatoriedade(path: Path):
    for module, level, lineno in _imports(path):
        if level:
            continue
        motivo = BANNED.get(_top(module))
        assert motivo is None, f"{path.name}:{lineno} importa {module!r}: {motivo}"


@pytest.mark.parametrize("path", MODULES, ids=IDS)
def test_core_so_importa_stdlib_puro_e_ele_mesmo(path: Path):
    for module, level, lineno in _imports(path):
        assert not level, f"{path.name}:{lineno} usa import relativo; use o caminho absoluto"
        interno = module == PACKAGE or module.startswith(f"{PACKAGE}.")
        permitido = module in ALLOWED_STDLIB or _top(module) in ALLOWED_STDLIB
        assert interno or permitido, (
            f"{path.name}:{lineno} importa {module!r}, que nao e stdlib puro "
            f"nem faz parte de {PACKAGE}"
        )


@pytest.mark.parametrize("path", MODULES, ids=IDS)
def test_dependencia_do_core_aponta_so_para_baixo(path: Path):
    origem = _module_name(path)
    rank_origem = _rank(origem)
    if rank_origem is None:
        return
    for module, level, lineno in _imports(path):
        if level or not module.startswith(f"{PACKAGE}."):
            continue
        alvo = module[len(PACKAGE) + 1 :].split(".")[0]
        rank_alvo = _rank(alvo)
        assert rank_alvo is not None, f"{path.name}:{lineno} importa a fachada {alvo!r}"
        assert rank_alvo < rank_origem, (
            f"{path.name}:{lineno} importa {alvo!r} (camada {rank_alvo}) "
            f"de dentro de {origem!r} (camada {rank_origem}): "
            "dependencia de core aponta so para baixo"
        )

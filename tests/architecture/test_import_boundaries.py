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

RAIZ = Path(tacticore.__file__).parent
CORE_DIR = Path(tacticore.core.__file__).parent
PACKAGE = "tacticore.core"

# A varredura cobre `src/tacticore` INTEIRO, e nao so o core. Um pacote novo
# nascia com trava zero: `import random` dentro dele passaria na suite, no ruff
# e no mypy, e a restricao 3 deixaria de ser verificada no primeiro modulo
# fora do core -- exatamente onde e mais facil esquecer dela.
#
# Pacote sem politica declarada REPROVA, pelo mesmo motivo que modulo sem
# camada declarada reprova: o default silencioso e o buraco.
POLITICAS: dict[str, str] = {
    "": "raiz do pacote: so metadado, nao importa nada de tacticore",
    "core": "motor de regras: stdlib puro e ele mesmo",
    "render": "apresentacao: le o core e monta texto; puro, nao imprime",
    "content": "fichas e encontros: dado de jogo, puro, sem abrir arquivo",
}

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

# Fora da pilha de camadas, por motivos diferentes.
OFF_LAYER: dict[str, int] = {
    # `serde` fala de estado e de evento, e nunca de orquestracao. Prende-la
    # abaixo de `rules` e o que impede o codec de "dar uma ajudinha" aplicando
    # regra na hora de carregar -- que e como um save deixa de ser um retrato
    # do estado e vira uma segunda implementacao das regras.
    "serde": 5,
    # `testing` e consumidora do core inteiro, como os proprios testes: os
    # builders de encontro precisam dos tipos de entrada do `engine`. Fica
    # acima de tudo, e por isso ninguem no core pode importa-la.
    "testing": 9,
}

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

# A UNICA excecao a proibicao de I/O, nomeada e com motivo. Um projeto que
# nunca imprime nada nao serve para nada; o que importa e que exista exatamente
# um lugar onde isso acontece, e que acrescentar o segundo exija editar esta
# lista -- e portanto exija alguem defender a escolha.
EXCECOES_DE_IO: dict[str, str] = {
    "__main__.py": "a unica camada de I/O do projeto: le argumento e imprime",
}

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


def _pacote_de(path: Path) -> str:
    """O pacote de um arquivo, relativo a `tacticore`. Raiz e string vazia."""
    relativo = path.relative_to(RAIZ).parent
    return "" if relativo == Path() else relativo.as_posix()


TODOS = sorted(RAIZ.rglob("*.py"))
IDS_TODOS = [str(p.relative_to(RAIZ).as_posix()) for p in TODOS]

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


def test_todo_pacote_tem_politica_declarada():
    """Pacote novo sem politica e um buraco silencioso na restricao 1."""
    encontrados = {_pacote_de(p) for p in TODOS}
    desconhecidos = encontrados - set(POLITICAS)
    assert not desconhecidos, (
        f"pacotes sem politica declarada em POLITICAS: {sorted(desconhecidos)}. "
        "Declare a politica junto com o pacote, no mesmo commit."
    )


@pytest.mark.parametrize("path", TODOS, ids=IDS_TODOS)
def test_nenhum_modulo_importa_io_rede_nem_aleatoriedade(path: Path):
    """Vale para `src/tacticore` inteiro, e nao so para o core.

    O que muda de pacote para pacote e o que se pode importar; o que quase
    nunca muda e a proibicao de I/O, rede, relogio e aleatoriedade fora do
    RngState -- a unica excecao esta em `EXCECOES_DE_IO`, com nome e motivo.
    """
    if path.name in EXCECOES_DE_IO:
        pytest.skip(f"{path.name}: {EXCECOES_DE_IO[path.name]}")

    for module, level, lineno in _imports(path):
        if level:
            continue
        motivo = BANNED.get(_top(module))
        assert motivo is None, f"{path.name}:{lineno} importa {module!r}: {motivo}"


def test_so_existe_uma_excecao_de_io():
    """A excecao vale enquanto for UMA. Duas ja e uma politica, e politica
    precisa estar escrita em outro lugar que nao um dicionario de teste."""
    assert len(EXCECOES_DE_IO) == 1, (
        f"excecoes de I/O: {sorted(EXCECOES_DE_IO)}. Se o projeto precisa mesmo "
        "de mais de um lugar que imprime, isso e decisao de arquitetura e vai "
        "para o CLAUDE.md antes de vir para ca."
    )


def test_a_excecao_de_io_aponta_para_um_arquivo_que_existe():
    nomes = {p.name for p in TODOS}
    fantasmas = set(EXCECOES_DE_IO) - nomes
    assert not fantasmas, f"excecao para arquivo inexistente: {sorted(fantasmas)}"


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

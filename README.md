# Tacticore

Motor de regras de combate tático por turnos, baseado na SRD 5.1, escrito como
biblioteca pura de Python e exercitado inteiramente por testes.

Não há engine, gráfico nem interface. O pacote recebe um estado de combate e uma
ação, e devolve um estado novo mais a lista de eventos do que aconteceu.

## Rodando

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy
```

## As cinco regras da casa

1. `core/` não importa nada de engine, renderização, I/O ou rede.
2. Todo estado de combate é serializável (dataclasses -> dict -> JSON).
3. Aleatoriedade só através do `RngState` que vive dentro do estado.
4. Mecânica nova entra junto com teste.
5. Tipagem em toda assinatura pública, mypy strict.

Detalhes e decisões de arquitetura em [CLAUDE.md](CLAUDE.md).

## Tipos permitidos em campo de estado

`str`, `int`, `bool`, `StrEnum`, `tuple`, dataclass frozen e `Mapping[str, ...]`.

**Sem `float`** (toda regra do SRD é inteira; float no JSON é round-trip que
quase bate), **sem `set`** (ordem de iteração varia com `PYTHONHASHSEED` e
quebra determinismo de forma intermitente), **sem `list`/`dict` mutável**, sem
chave `int`.

## Função de regra nunca recebe `CombatState`

As funções de `core/rules.py` recebem números e descritores. Quem conhece o
estado de combate é `core/engine.py`. Um teste de arquitetura reprova a
violação, porque é ela que transforma regra testável em regra que só roda
dentro de um combate montado.

## Licença e atribuição

Este projeto usa material da SRD 5.1, disponibilizada sob
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).
A atribuição completa e a lista de desvios conscientes das regras originais
ficam em `docs/srd-atribuicao.md`.

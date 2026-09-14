# Tacticore — motor de regras de combate tático

RPG tático por turnos inspirado em Baldur's Gate 3, em escala muito menor.
Nesta fase **não existe engine, gráfico nem interface**: só um motor de regras
puro em Python, exercitado inteiramente por testes.

## Restrições inegociáveis

Estas cinco regras valem para toda sessão, todo commit, sem exceção.

1. **`core/` não importa nada de engine, renderização, I/O ou rede.**
   Ele recebe estado + ação e devolve estado novo. Função pura sempre que der.
   `tests/architecture/test_import_boundaries.py` reprova a violação.
2. **Todo estado de combate é serializável** (dataclasses -> dict -> JSON).
   Nada de estado escondido em global ou singleton.
3. **Aleatoriedade só através de um objeto RNG injetado**, nunca `random` global.
   Rodar um combate com a mesma seed tem que dar exatamente o mesmo resultado.
4. **Mecânica nova entra junto com teste.** Sem exceção.
5. **Tipagem em toda assinatura pública.** mypy strict no `core/`.

## Stack

Python 3.12+ gerenciado com `uv`, pytest + pytest-cov, ruff (lint e format),
mypy strict apontado para `src/`.

```bash
uv sync                  # ambiente
uv run pytest            # testes
uv run ruff check .      # lint
uv run ruff format .     # formatação
uv run mypy              # tipagem (só src/)
```

## Decisões de arquitetura já tomadas

Estas saíram de uma análise de design aprovada e não devem ser revistas de
improviso. Se alguma precisar mudar, a mudança é um commit próprio com
justificativa.

- **O RNG é estado, não injeção.** `RngState` é uma união fechada
  (`SplitMix64 | ScriptedRng`), frozen, morando **dentro** do `CombatState`.
  `apply(state, action)` **não recebe parâmetro `rng`**. Gerador próprio
  (splitmix64 + Lemire, sem rejeição) porque `random.Random` não é contrato
  estável entre versões do CPython e não serializa a posição do stream.
- **O contrato de consumo do RNG é API pública.** Ordem e quantidade de saques
  fazem parte do contrato, travados por golden. Ver `docs/adr/0001`.
- **`apply` devolve `Applied | Rejected`** (união discriminada, `match` +
  `assert_never`), nunca um campo opcional de erro. Eventos saem no **retorno**,
  nunca acumulam dentro do estado.
- **Camadas com dependência só para baixo:**
  `ids/enums/errors -> rng -> dice -> model -> actions/events -> results ->
  rules -> queries -> engine`. Funções de `rules.py` **nunca recebem
  `CombatState`** — um teste de arquitetura reprova pela assinatura.
  `serde.py` fica preso abaixo de `rules` (não pode aplicar regra ao
  carregar); `testing.py` fica acima de tudo (é consumidora, como os testes).
- **Nada de `float`, `set`, `list` ou `dict` mutável em campo de estado.**
  Toda regra do SRD é inteira; ordem de iteração de `set` varia com
  `PYTHONHASHSEED` e quebra determinismo de forma intermitente.
- **Toda dataclass de estado é `frozen=True, slots=True, kw_only=True`.**
- **Identidade por slug legível** (`CreatureId`, `AttackId` como `NewType` sobre
  `str`), nunca índice posicional, nunca `uuid4()` (lê entropia do SO).
- **Campos derivados nunca são armazenados.** `combat_result(state)` é função.
- **Eventos carregam dados crus, jamais frase formatada.** Formatar é
  apresentação, e apresentação dentro do core é I/O disfarçado.

## Regras de trabalho

- **Um passo por vez.** Rode os testes antes de seguir para o próximo.
- **Commits pequenos, mensagem em português** (conventional commits).
- Todo tipo novo de estado entra com codec de serialização e na lista do
  guardião **no mesmo commit**.
- `docs/srd-atribuicao.md` registra a atribuição CC-BY-4.0 da SRD 5.1 e todo
  desvio consciente das regras originais.
- **Todo diff de golden precisa de uma frase no commit** dizendo qual regra
  mudou e por quê. Sem isso, `--update-golden` vira um botão de fazer o teste
  calar. Ver `tests/golden/README.md`.
- **Toda mudança no contrato de consumo do RNG incrementa
  `serde.RULES_VERSION`.** O contrato está no docstring de `tacticore.core`
  e o porquê em `docs/adr/0001`.

## Fora de escopo nesta etapa

Magias, condições, grid, movimento posicional, IA, itens e classes.
O desenho deixa porta aberta para eles (campos com default, hooks triviais),
mas nada disso é implementado agora.

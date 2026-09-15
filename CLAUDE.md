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
  apresentação, e apresentação dentro do core é I/O disfarçado. Quem monta a
  frase é `tacticore.render`, fora do core.
- **Existe exatamente um lugar no projeto que faz I/O:** `tacticore.__main__`.
  `core`, `render` e `content` são puros — não imprimem, não abrem arquivo, não
  leem relógio. A exceção está registrada e travada em
  `tests/architecture/test_import_boundaries.py`, e um segundo lugar que
  imprima é decisão de arquitetura, não conveniência.
- **Golden de regra e golden de apresentação vivem em pastas separadas.**
  `tests/golden/data/` exige uma frase no commit dizendo qual regra mudou;
  `tests/render/data/` se regrava sem cerimônia. Misturados, ou se justifica
  mudança de vírgula, ou se para de justificar mudança de regra.

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
- **`serde.RULES_VERSION` sobe quando o motor passa a calcular outro
  resultado**, e não só quando o stream se desloca — e as subidas são agrupadas
  num único commit de virada por fatia, nunca espalhadas por vários que
  regravam os mesmos goldens (ADR 0002). O contrato do RNG está no docstring de
  `tacticore.core` e o porquê em `docs/adr/0001`.
- **Campo novo no estado entra com quatro coisas no mesmo commit:** invariante
  em `serde.check_invariants`, teste em `test_invariants.py` adulterando o save
  de verdade, exemplo com valor **não-default** no registro `CODECS`, e o campo
  preenchido em `_estado_gordo()`. Sem o valor não-default, o round-trip não
  prova nada — e ele é o único teste que exercita o `load`.
- **Nenhum campo de estado pode ser `None`.** Ausência se modela como tupla
  vazia, string vazia ou membro de enum. O guardião de lista branca rejeita
  `None` em runtime, mas o estático não barra a anotação `| None`.
- **Um save antigo não carrega só porque o campo novo tem default.**
  `serde._campo` levanta na chave ausente; compatibilidade exige acessor com
  default e uma função de migração por salto de `SCHEMA_VERSION`.
- **Toda regra da SRD que o motor simplifica ganha uma linha em
  `docs/srd-atribuicao.md` no mesmo commit.** Nenhum guardião cobra isso.

## Etapas

A etapa 1 (motor de regras) está completa. O plano da etapa 2 — narrador de
texto, grid e condições — está em [docs/etapa-2.md](docs/etapa-2.md), com o que
ficou de fora e por quê.

## Fora de escopo nesta etapa

Magias, condições, grid, movimento posicional, IA, itens e classes.
O desenho deixa porta aberta para eles (campos com default, hooks triviais),
mas nada disso é implementado agora.

# Tacticore — motor de regras de combate tático

RPG tático por turnos inspirado em Baldur's Gate 3, em escala muito menor.

**Não existe engine de jogo nem interface gráfica.** O que existe é um motor de
regras puro, exercitado por testes, mais uma camada fina de texto para que um
combate possa ser **lido**:

```bash
uv run python -m tacticore        # roda um duelo e narra o log
```

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
uv sync                          # ambiente
uv run pytest                    # testes
uv run pytest --cov              # testes com o gate de cobertura
uv run ruff check . && uv run ruff format .
uv run mypy
```

## Os quatro pacotes

```
src/tacticore/
├─ core/       o motor de regras. Puro.
├─ render/     transforma o log em texto. Puro, não imprime.
├─ content/    fichas e encontros: dado de jogo. Puro.
└─ __main__.py o ÚNICO lugar do projeto que faz I/O.
```

Cada pacote tem uma política declarada em `POLITICAS`, no guardião de imports.
**Pacote sem política declarada reprova** — um pacote novo nascia com trava zero
antes disso, e `import random` lá dentro passava em tudo.

## Decisões de arquitetura já tomadas

Estas saíram de análises de design aprovadas e não devem ser revistas de
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
  `serde.py` fica presa **abaixo de `rules`** (não pode aplicar regra ao
  carregar); `testing.py` fica acima de tudo (é consumidora, como os testes).
- **Nada de `float`, `set`, `list` ou `dict` mutável em campo de estado.**
  Toda regra do SRD é inteira; ordem de iteração de `set` varia com
  `PYTHONHASHSEED` e quebra determinismo de forma intermitente.
- **Toda dataclass de estado é `frozen=True, slots=True, kw_only=True`.**
- **Identidade por slug legível** (`CreatureId`, `AttackId` como `NewType` sobre
  `str`), nunca índice posicional, nunca `uuid4()` (lê entropia do SO).
- **Campos derivados nunca são armazenados.** `combat_result(state)` é função.
- **Condição é `StrEnum` puro numa tupla ordenada.** Sem `ActiveCondition`
  enquanto `source` for constante e duração estiver fora de escopo. A ordem
  canônica (pelo **valor**, não pela ordem de declaração) e a ausência de
  repetição são **invariantes conferidas na carga**, e não convenção:
  `canonical_json` ordena chaves de objeto e não itens de lista, então
  `("B","A")` e `("A","B")` têm fingerprint diferente e estado lógico igual.
  O `load` deliberadamente **não** normaliza — consertar em silêncio faria
  `check_invariants` nunca ver o problema.
- **A grade é de casas, e a unidade mora com ela.** `Position` é dataclass e
  nunca `tuple[int, int]`; `PES_POR_CASA` mora em `model` ao lado dela, e não em
  `rules`, porque `serde` precisa dela tanto quanto quem calcula distância.
  Diagonal custa o mesmo que reta (regra de grade da SRD), e é essa aproximação
  que mantém toda a geometria inteira, sem um `float` em lugar nenhum.
- **Eventos carregam dados crus, jamais frase formatada.** Formatar é
  apresentação, e apresentação dentro do core é I/O disfarçado. Quem monta a
  frase é `tacticore.render`, fora do core.
- **Existe exatamente um lugar no projeto que faz I/O:** `tacticore.__main__`.
  A exceção está registrada em `EXCECOES_DE_IO` e travada por dois testes — ela
  vale **enquanto for uma**. Um segundo lugar que imprima é decisão de
  arquitetura, e vem para cá antes de virar código.
- **Golden de regra e golden de apresentação vivem em pastas separadas.**
  `tests/golden/data/` exige uma frase no commit dizendo qual regra mudou;
  `tests/render/data/` se regrava sem cerimônia. Misturados, ou se justifica
  mudança de vírgula, ou se para de justificar mudança de regra.

## Regras de trabalho

- **Um passo por vez.** Rode os testes antes de seguir para o próximo.
- **Commits pequenos, mensagem em português** (conventional commits).

### As duas que mais se pagaram

- **Todo passo declara QUEM CONSOME o que ele entrega.** Na etapa 1,
  `rules.attack_bonus` e `rules.damage_bonus` ficaram nove commits escritas,
  testadas e nunca chamadas pelo motor, que recalculava a mesma conta inline —
  com 100% de cobertura o tempo todo, porque os testes cobriam a função, os
  testes cobriam o motor, e ninguém cobria a ponte.
- **Toda trava nova entra com a VIOLAÇÃO que prova que ela dispara.** Trava que
  nunca falhou é decoração. Foi assim que se descobriu que o guardião de imports
  cobria metade do que prometia, e que um critério de desempate que eu tinha
  acabado de escrever não desempatava nada.

### Corolário: corte o que não tem consumidor

Gancho sem quem o use, parâmetro que outra função sempre sobrescreve, ramo que
nenhum teste alcança — tudo isso sai, e o commit diz por quê. A cobertura e as
sondas apontam; a tentação é sempre marcar com `pragma` e seguir.

A exceção é o gancho **nomeado e datado**: `derive_advantage_sources` nasceu
vazio na etapa 1 e pagou na fatia 2 da etapa 2, porque desde o começo estava
escrito qual regra ia consumi-lo.

### Serialização e versões

- Todo tipo novo de estado entra com codec e na lista do guardião **no mesmo
  commit**.
- **Campo novo no estado entra com quatro coisas no mesmo commit:** invariante
  em `serde.check_invariants`, teste em `test_invariants.py` adulterando o save
  de verdade, exemplo com valor **não-default** no registro `CODECS`, e o campo
  preenchido em `_estado_gordo()`. Sem o valor não-default, o round-trip não
  prova nada — e ele é o único teste que exercita o `load`.
- **Nenhum campo de estado pode ser `None`.** Ausência se modela como tupla
  vazia, string vazia ou membro de enum. O guardião de lista branca rejeita
  `None` em runtime, mas o estático não barra a anotação `| None`.
- **Um save antigo não carrega só porque o campo novo tem default.**
  `serde._campo` levanta na chave ausente. Compatibilidade exige uma função de
  migração por salto em `_MIGRACOES`, e a versão nova em
  `SCHEMA_VERSIONS_ACEITAS`. Os saltos são aplicados **em cadeia**: o
  `save_legado.json` está em v1 e hoje atravessa dois.
- **`serde.RULES_VERSION` sobe quando o motor passa a calcular outro
  resultado**, e não só quando o stream se desloca. Uma subida por mudança de
  resultado — o contador é monotônico, não é escasso. O que não pode é fatiar
  **uma** mudança em vários commits que sobem várias vezes. Ver ADR 0002.

### Goldens e documentação

- **Todo diff de golden precisa de uma frase no commit** dizendo qual regra
  mudou e por quê. Ver `tests/golden/README.md`, que também traz a tabela do que
  cada sonda injetada realmente quebrou — e do que os goldens **não** cobrem.
- **Golden que exercita um caso específico entra com um teste que cobra isso**,
  e não só com o arquivo congelado. Sem ele, o golden vira mais um combate comum
  em silêncio e a lacuna que ele tapava volta sozinha.
- **Toda regra da SRD que o motor simplifica ganha uma linha em
  `docs/srd-atribuicao.md` no mesmo commit.** Nenhum guardião cobra isso. A
  tabela ficou vazia a etapa 1 inteira, e quando foi preenchida tinha onze
  desvios que ninguém tinha anotado. Hoje são dezoito.

## Etapas

- **Etapa 1 — motor de regras: completa.** RNG determinístico, dados, ataque,
  dano, iniciativa, turno, times e fim de combate.
- **Etapa 2 — [docs/etapa-2.md](docs/etapa-2.md): completa.** Narrador de texto
  fora do core, grid com movimento e alcance, e a condição Caído inteira.
  O recorte da fatia 3 mudou durante a execução — Cego saiu por não ter fonte
  nem remoção possíveis, alcance longo entrou no lugar — e o plano registra o
  porquê.

## Fora de escopo até a etapa 3

Magias e salvaguardas, IA de inimigo, itens e classes, ataque de oportunidade,
ação bônus e reação, multiataque, HP temporário, tipo de dano e resistência.

E, o mais sentido de todos: **uma fonte de condição dentro do motor.** Hoje a
única é `Participant.conditions` — o encontro nasce com ela. Empurrar, que é a
fonte de Caído na SRD, é teste de atributo oposto: d20 contra d20, e com o
quadro fixo são quatro dados por empurrão. Seria a primeira mecânica a consumir
RNG fora de ataque, e o ADR 0002 manda que ela entre sozinha.

O desenho deixa porta aberta para eles — campos com default, ganchos com
consumidor nomeado —, mas nada disso é implementado agora. `docs/etapa-2.md`
explica o que ficou de fora e por quê, um a um.

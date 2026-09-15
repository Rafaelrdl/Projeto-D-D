# Etapa 2 — plano

**Status:** etapa 2 completa. As tres fatias estao implementadas.

As decisões da seção 2 foram todas aceitas e executadas. Onde a implementação
contrariou o plano, o plano está corrigido abaixo com a nota de por quê — vale
mais como registro do que como profecia acertada.

Três fatias, 14 passos. Se o fôlego acabar, corte a fatia 3 e feche a etapa com
nove — narrador e grid sozinhos já mudam o que o projeto é. Acima de quinze
passos isto deixa de ser sessão e vira tarefa.

Cada passo declara duas coisas que o plano da etapa 1 não declarava, e que
custaram caro por isso:

- **Quem consome.** Na etapa 1, `rules.attack_bonus` e `rules.damage_bonus`
  ficaram nove commits escritas, testadas e nunca chamadas pelo motor, que
  recalculava a mesma conta inline. Cobertura de 100% o tempo todo: os testes
  cobriam a função, os testes cobriam o motor, e ninguém cobria a ponte.
- **A violação que prova a trava.** Trava que nunca falhou é decoração. Todo
  guardião novo entra com a violação concreta que foi injetada para provar que
  ele dispara.

---

## 1. O que a etapa 2 contém — e o que não contém

### As três fatias

| # | Fatia | Passos | O que ela torna mais barato |
|---|---|---|---|
| 1 ✅ | Narrador de texto e higiene | 4 | Todas. Diff de golden vira legível, e as decisões da fatia 2 passam a ser tomadas **olhando** um combate em vez de inferindo dele |
| 2 ✅ | Grid, movimento e alcance | 5 | Paga a migração de save v1→v2 **uma vez para todas as fatias seguintes**, com a mecânica que não rola um dado sequer. E faz Caído nascer com a regra inteira da SRD |
| 3 ✅ | Caído inteiro e alcance longo | 6 | — |

> **Como a fatia 2 saiu na prática, contra o previsto.** Os cinco passos
> viraram cinco, mas `SCHEMA_VERSION` subiu **duas** vezes (posição e
> alcance) em vez de uma, e `RULES_VERSION` **três** (movimento, alcance,
> desvantagem derivada) — o que obrigou a corrigir a cláusula de
> agrupamento do ADR 0002, que proibia justamente isso. Entrou também um
> golden não previsto, `tiro_colado`, porque a regra do passo 8 não
> aparecia em nenhum dos cinco existentes.

### Por que o narrador vem primeiro, e por que ele não estava na lista

Não estava porque a lista era de mecânicas, e narrador não é regra — ele mora
**fora do core**, em `src/tacticore/render/`.

O core já pagou adiantado por ele: `events.py` diz no próprio docstring que
evento não carrega frase formatada *porque montar a frase é trabalho de quem
exibe*. A dívida foi contraída lá e nunca cobrada.

E o argumento prático: a única janela para um combate hoje é
`tests/golden/data/dois_contra_dois.json`, 13 KB de JSON. Com o grid, cada
evento ganha coordenada e fica pior. Um motor com 663 testes cuja única saída
legível é JSON é um motor que se **verifica** mas não se **julga** — e a fatia 2
exige julgamento: "o que conta como movimento canônico" não é uma pergunta que
se responda lendo `"remaining_ft": 15`.

Custo de contrato: **zero**. Não toca o RNG, não toca save, não regrava golden.

### Fora da etapa 2, com motivo

| O que fica fora | Por quê |
|---|---|
| **Magias e área** | Único candidato bloqueado por dois outros. E `events.DamageRolled` tem `actor` e `target` únicos: um dano rolado uma vez para N criaturas não tem `target`. A **forma do evento** está errada para área, não só a mecânica |
| **Salvaguardas** | Abrem a etapa 3. O gancho (`rules.d20_check` sem automatismo) é real, mas cobre a menor parte do trabalho, e vantagem em salvaguarda — metade das condições da SRD — depende de condições existirem. O que entra agora é só o **texto**: as duas cláusulas ficam escritas no ADR 0002, para a primeira magia não as descobrir com goldens já congelados em cima |
| **IA de inimigo** | Sem grid não existe decisão tática a tomar. E o modo de falha típico dela — avaliar candidatos chamando `apply`, que lê os mesmos próximos dados porque `_atacar` fixa `position(state.rng)` — passa em replay, em golden, em mypy e em todas as travas da etapa 1 |
| **Itens, classes, armadura** | Classe/nível reverte a decisão argumentada de `model.py` (`proficiency_bonus` explícito) sem uma única característica implementável. Armadura como perfil exige migração **não inversível**: de `armor_class: 13` não se recupera "couro batido + DES 8" |
| **Ataque de oportunidade, ação bônus, reação, multiataque** | Os três primeiros fazem o movimento ou a passagem de turno consumirem RNG **pela primeira vez** |
| **HP temporário, tipo de dano, resistência** | Campos caros: `HpChanged` embute `HitPoints` em 12 entradas de golden. E tipo de dano sem resistência implementada é campo inerte no objeto mais serializado do projeto — viola a regra 4 |
| **Duração e expiração de condição** | `advance_turn` não tem ponto de tique e `TurnOrder` não tem fase. Condição da etapa 2 é aplicada e removida por ação explícita |

---

## 2. Decisões que precisam de um "sim" antes da primeira linha

**1. Onde mora o narrador, e o que ele enxerga.**
Acoplá-lo ao `CombatState` recriaria o problema que `events.py` resolveu ao
proibir frase formatada dentro do evento.
> **Proponho:** `src/tacticore/render/text.py`, função pura que recebe
> `tuple[Event, ...]` e devolve `tuple[str, ...]`. Nunca o estado, nunca um
> `print`. Só `tacticore.__main__` imprime e lê argumento.

**2. O narrador imprime os ids crus.**
`goblin_1` e não "Goblin #1". Os ids são slugs legíveis por decisão explícita
de `ids.py`, e um parâmetro de "nome bonito" sem consumidor é exatamente o
gancho morto que esta etapa está cortando em outros lugares.
> **Proponho:** ids crus. Nome de exibição entra quando houver uma interface
> que o consuma.

**3. Golden de apresentação é separado de golden de regra.**
Misturar estraga os dois: um é regravável à vontade, o outro exige uma frase no
commit.
> **Proponho:** `tests/render/data/*.txt`, fora de `tests/golden/data/`, com o
> README da pasta dizendo que ele se regrava sem cerimônia. Isso obriga a mover
> `pytest_addoption` de `tests/golden/conftest.py` para um `tests/conftest.py`
> na raiz — a opção só é visível abaixo do conftest que a registra.

**4. Nenhum campo de estado pode ser `None`.**
O guardião de lista branca (`test_state_guardrails._validar_valor`) já rejeita
`None` em runtime, mas o guardião estático não barra a anotação `| None`. A
primeira condição com `source: CreatureId | None` passaria no estático e
quebraria no runtime — ou pior, passaria nos dois se o campo viesse vazio no
estado gordo.
> **Proponho:** ausência se modela como tupla vazia, string vazia ou membro de
> enum. Condição auto-aplicada aponta para o próprio dono. Se um dia `None` for
> inevitável, entra na lista branca **e** em `ANOTACOES_PROIBIDAS` no mesmo
> commit.

**5. `RULES_VERSION` sobe quando o motor passa a calcular outro resultado** — e
não só quando o stream desloca.
Hoje `serde.py` ("qualquer regra") e o `CLAUDE.md` ("o contrato de consumo do
RNG") discordam, e pela leitura ampla ligar `derive_advantage_sources` na fatia
3 já obrigaria a subir.
> **Proponho:** a leitura ampla, escrita no ADR 0002 — **e** a regra de que as
> subidas são agrupadas num único commit de virada por fatia, nunca espalhadas
> por cinco commits que regravam os mesmos quatro arquivos.

**6. Campo novo no estado entra com invariante e com exemplo não-default.**
Dois buracos reais nos guardiões atuais: `serde.check_invariants` não cresce
sozinho (nenhuma trava cobra invariante para campo novo), e
`test_chaves_emitidas_batem_com_os_campos_declarados` só confere o **dump** — o
único teste que exercita o `load` é o round-trip, e se o exemplo do registro
`CODECS` usar o valor default em todo campo, o round-trip não prova nada.
> **Proponho:** todo commit de campo novo entra com (a) invariante em
> `check_invariants`, (b) teste em `test_invariants.py` adulterando o save de
> verdade, (c) exemplo no `CODECS` com valor **não-default** em todo campo, e
> (d) `_estado_gordo()` carregando o campo preenchido.

**7. `queries.is_standing` é partida em três antes da fatia 3.**
Hoje a função chamada "está de pé" quer dizer "tem vida". Na SRD 5.1, *prone* é
condição independente de vida. São cinco call sites com três perguntas
diferentes.
> **Proponho:** `is_alive` / `can_act` / `is_valid_target`, num commit de
> refatoração pura (goldens intactos, mypy apontando os cinco call sites), e
> **sem manter `is_standing` como alias** — alias deixa o call site errado
> verde.

---

## 3. A fatia 1 — narrador e higiene (4 passos)

Nenhum destes passos acrescenta campo de estado. **`SCHEMA_VERSION` e
`RULES_VERSION` ficam em 1, os quatro goldens de combate saem byte a byte
iguais, e `save_legado.json` continua carregando com o mesmo fingerprint** — e
é isso que prova que os passos estão certos.

> **Já feito no commit `2ce23a6`:** o funil `attack_math`, a varredura do
> guardião de imports estendida a `src/tacticore` inteiro com política por
> pacote, e `tape_from_events` fechada com `assert_never`. O plano original
> tinha cinco passos; sobraram quatro.

---

### Passo 1 — Higiene restante das travas

**Entrega.** `pytest_addoption` e a fixture `update_golden` movidos de
`tests/golden/conftest.py` para um `tests/conftest.py` na raiz, para o golden de
apresentação do passo 2 conseguir usar a flag. `gravar_ou_comparar` passa a
classificar a falha: mesma `rules_version` + outra `schema_version` = mudança de
**formato**, e a mensagem diz isso em vez de mandar "diga qual regra mudou" —
frase impossível de escrever com honestidade na maioria dos diffs da etapa 2.
`test_o_save_legado_ainda_carrega` parte em dois.

> **Correção factual:** a justificativa original do split estava errada. `load`
> **já** chama `check_invariants` e levanta (`serde.load_state`), então a
> garantia de invariante já existe e é mais forte do que o plano supunha. O
> valor do split é outro: separar a **garantia permanente** ("o save v1 carrega,
> para sempre") do **pin de formato** ("o fingerprint é este"), que é
> recalculado a cada salto de schema com a migração como justificativa escrita.

**Quem consome.** `tests/conftest.py` → o golden de apresentação do passo 2. A
classificação de falha → todo commit das fatias 2 e 3.

**Violação que prova a trava.** Um envelope montado com `schema_version`
adiantado tem que falhar dizendo *formato*; outro com `rules_version` adiantado,
dizendo *regra*. Os dois testes entram junto.

**RNG:** não. **Save:** não. **Goldens:** não regravam.

```
test(travas): diagnostico de formato contra regra e flag de golden na raiz
```

---

### Passo 2 — Narrador de texto, fora do core

**Entrega.** `src/tacticore/render/text.py` com `narrate_event` e `narrate`,
puras, sem `print` e sem abrir arquivo. `POLITICAS` do guardião de imports ganha
a linha do pacote `render`. `source_pkgs` do coverage passa a incluir
`tacticore.render` — senão a regra 4 fica falsa para ele.

**Quem consome.** `tacticore.__main__` (passo 3) e o golden de apresentação.

**Violação que prova a trava.** Um evento novo sem frase tem que virar **erro de
mypy**, não linha faltando no texto: o `match` fecha com `assert_never`, o mesmo
padrão de `serde.event_to_dict`. Conferido acrescentando um evento de mentira.

**Detalhe de gate:** o `case _: assert_never(event)` precisa de
`# pragma: no cover` como todos os irmãos do core, senão o primeiro commit da
fatia nasce vermelho por motivo de configuração.

**Testes.** Uma asserção de string exata por membro da união `Event` — são doze.
Um teste de que `render` não importa I/O nem aleatoriedade, e que o core
continua **sem conseguir** importar `render`.

**RNG:** não. **Save:** não. **Goldens:** não.

```
feat(render): narrador de texto do log, fora do core
```

---

### Passo 3 — Conteúdo e um comando que imprime um combate

**Entrega.** `src/tacticore/content/srd.py` com `BRUTAMONTES` e `DUELISTA`
construídos pelos construtores de verdade — e não pelos builders de
`core.testing`, que são andaime de teste. `tests/golden/test_encounters.py`
passa a importar de lá. `src/tacticore/__main__.py` roda um encontro com seed e
imprime o log narrado.

> **Armadilha:** `DUELISTA.estoque` usa `Ability.FOR` com força 10 — não por
> escolha, mas por default de `make_attack`. Um estoque de duelista devia usar
> DES. **A mudança é de endereço, não de valor:** `ability=Ability.FOR` é
> copiado como está, inclusive parecendo errado. Corrigir a ficha é outro
> commit, com os goldens regravados e a frase de justificativa.

> **Correção factual:** não dá para "narrar o `duelo.json`". O `serde` só tem
> `dump_*` de evento; não existe leitor. O golden de apresentação nasce de
> **rodar o combate e narrar**.

**Quem consome.** `__main__` e os quatro goldens de combate, que passam a
importar as fichas em vez de declará-las.

**Critério de aceite.** **Os quatro goldens saem byte a byte iguais.** Se um
mudou, a ficha mudou de valor na mudança de casa.

**RNG:** não. **Save:** não. **Goldens:** não regravam — e isso é o teste.

```
feat(content): fichas da SRD fora do teste e um comando que narra um encontro
```

---

### Passo 4 — ADR 0002

**Entrega.** `docs/adr/0002-*.md` com o que a fatia 2 vai cobrar e sai caro
descobrir no meio:

- **(a1)** A ordem de `legal_actions` é contrato dos goldens e só muda em commit
  isolado, com a frase no commit. `play_out` escolhe `acoes[0]` e gera três dos
  quatro goldens.
- **(a2)** Enquanto a ordem for incondicional, ação nova entra antes de
  `EndTurnAction`. **A fatia 2 torna a ordem condicional ao estado** — com
  alcance, um ataque fora de alcance some da lista e `acoes[0]` deixa de ser
  ataque. Quando isso acontecer, a política de ordenação é reescrita aqui.
- **(b)** `advance_turn` **não consome RNG** na etapa 2 inteira. Nada de
  salvaguarda pelo relógio do turno.
- **(c)** Quando salvaguarda entrar: quadro fixo de dois d20, pelo argumento
  idêntico à decisão 3 do ADR 0001.
- **(d)** `RULES_VERSION` sobe quando o motor calcula outro resultado, agrupado
  num commit de virada por fatia.
- **(e)** Toda simplificação de regra da SRD acrescenta uma linha em
  `docs/srd-atribuicao.md` **no mesmo commit**. A tabela está vazia desde o
  commit 1 e o `CLAUDE.md` a torna obrigatória — nenhum guardião cobra, então é
  regra social escrita.
- **(f)** Dívida conhecida e registrada: `d20_check` fecha o bônus num `int` e
  `AttackRolled` decompõe em campos fixos. A primeira Bênção (+1d4) é um dado
  **físico** dentro do bônus e desloca o stream inteiro. O quadro fixo de dois
  d20 protege contra vantagem e **não** protege contra isso.

**Quem consome.** Todos os passos das fatias 2 e 3.

**Violação que prova a trava.** A cláusula (a1) vira teste: *quando
`legal_actions` não é vazia, o último item é `EndTurnAction`* — mais o par
óbvio, *ela só é vazia com combate encerrado ou ator caído*. São dois asserts;
o enunciado ingênuo ("é sempre o último") é falso, porque a lista é vazia em
dois casos legítimos.

**RNG:** não. **Save:** não. **Goldens:** não.

```
docs(adr): 0002 decide ordem do menu, relogio sem dado e a divida da parcela
```

---

## 4. Fatia 2 — grid, movimento e alcance (5 passos)

Esta é a fatia que **paga a migração de save**, e ela foi escolhida para isso
justamente por não encostar no contrato de consumo do RNG: nenhum dado novo,
nenhum braço novo na fita, o quadro fixo de dois d20 intacto.

> **A migração NÃO é o commit zero.** Máquina de migração sem nenhum salto real
> é código morto por construção — e este repositório já tem o exemplar do que
> isso vira. A máquina nasce no commit do primeiro campo de verdade.

| # | Passo | Entrega | Impacto |
|---|---|---|---|
| 5 | Posição e a máquina de migração | `model.Position(x, y)` como **dataclass, nunca `tuple[int, int]`**; `Combatant.position` sem default; acessores com default, `SCHEMA_VERSIONS_ACEITAS`, uma função por salto | **Save: quebra.** `SCHEMA_VERSION` → 2. Goldens regravam (o `final_fingerprint` muda) |
| 6 | Movimento que move | `MoveAction.distance_ft` → `to: Position`; distância de Chebyshev; economia de turno em pés continua a mesma | Save: não. Goldens regravam |
| 7 | Alcance de ataque | `AttackProfile.range_ft` — campo novo dentro de `AttackProfile` → `Statblock` → save, mais um codec e mais uma invariante. `RejectionReason.OUT_OF_RANGE` | **Save: quebra.** `SCHEMA_VERSION` → 3, ou agrupado com o passo 5 |
| 8 | O primeiro consumidor real de `derive_advantage_sources` | "Ataque à distância com inimigo adjacente" dá desvantagem. Calculável de `(state, action)` sem alargar a assinatura | **RULES_VERSION sobe.** Goldens regravam |
| 9 | Goldens com grid e reescrita da cláusula (a2) | Encontros canônicos com posição; a política de ordenação de `legal_actions` reescrita no ADR 0002 | Goldens regravam |

**A decisão que precisa ser tomada olhando um combate narrado, e não antes:** o
que conta como movimento canônico em `legal_actions`. Hoje sai exatamente um
`MoveAction` gastando o orçamento inteiro; com grid, "todas as casas
alcançáveis" é um conjunto grande e "uma casa canônica" é arbitrário. É por isso
que o narrador vem antes.

---

## 5. Fatia 3 — Caído inteiro e alcance longo (6 passos) ✅

> **O recorte mudou, e mudou por inteiro.** O plano original era "Caído e Cego".
> Cego saiu. As três fontes dele na SRD — magia, salvaguarda e iluminação —
> estão bloqueadas por decisão já escrita neste mesmo documento, e **nada em
> `actions.py` removeria a condição**: um cego nasceria cego e morreria cego, o
> que é aritmeticamente `−2` em `attack_math` com narração diferente.
>
> No lugar dele entrou `AttackProfile.long_range_ft` — a dívida que o próprio
> repositório tinha assinado em dois lugares, um deles prometendo que o alcance
> longo "chega no passo seguinte". O passo seguinte levou uma fatia inteira.

**O critério de corte também mudou.** O original — "entram as condições cujo
efeito cabe **inteiro** em `advantage_sources`" — reprova Caído, porque metade
das cláusulas da SRD dele é custo de movimento e não vantagem. O que vale:

> Entra a regra cujo efeito cabe nos vocabulários que o motor **já tem** —
> fontes de vantagem e orçamento de movimento em pés — e cuja **fonte existe
> dentro do motor**.

Caído passa nos dois testes: o efeito cabe (três cláusulas em `advantage_sources`,
uma em pés de movimento) e a remoção existe (`StandUpAction`). Cego passa no
primeiro e reprova no segundo.

| # | Passo | Entrega | Impacto |
|---|---|---|---|
| 10 | `is_standing` → `is_conscious` | **Uma** função, não três. `is_valid_target` não tem chamador possível e `can_act` nasceria idêntica | Renomeação pura: goldens intactos |
| 11 | Vocabulário e alcance longo | `Condition` StrEnum com um membro, `Combatant.conditions`, `AttackProfile.long_range_ft`, migração v3→v4 | **Save: quebra.** `SCHEMA_VERSION` → 4 |
| 12 | Caído afeta a rolagem | Três cláusulas, e as duas de alvo caído são **geometria** e não tipo de arma | `RULES_VERSION` → 5 |
| 13 | Alcance longo | Desvantagem *entre* curto e longo; recusa além do longo | `RULES_VERSION` → 6 |
| 14 | `StandUpAction` | Metade do deslocamento, **não** é ação. Evento `StoodUp` | `RULES_VERSION` → 7 |
| 15 | Golden do caído e correção do ADR | Encontro produzido pelo **piloto automático** | Um golden novo |

### O que a fatia ensinou

- **`is_standing` não precisava de três funções.** O plano pedia três; o código
  mostrou que duas não teriam chamador. Ler os nove call sites custou menos que
  escrever duas one-liners que ficariam para sempre idênticas.
- **A regra de Caído é geometria.** A SRD condiciona a vantagem a o *atacante*
  estar a 1,5 m, e não a arma ser corpo a corpo — e o motor tinha o campo
  errado à mão, três linhas acima, para fazer a leitura errada.
- **A primeira versão do alcance longo penalizava o impossível.** Marcava
  desvantagem para qualquer distância além do curto, inclusive além do longo,
  onde o ataque nem acontece.
- **O piloto automático é o teste de "isto é uma mecânica ou uma vitrine?"**
  Caído fecha a alça sozinho porque `StandUpAction` está no menu. Cego nunca
  fecharia.

## 6. A armadilha de migração, medida

Testado antes de escrever este plano: acrescentar
`Combatant.conditions: tuple[str, ...] = ()` **com codec** e carregar
`save_legado.json` dá

```
InvalidSaveError: state.combatants['bruto']: falta o campo 'conditions'
```

porque `serde._campo` levanta na chave ausente. **Um default de Python não
torna um save antigo carregável.** Pior: os 195 guardiões de arquitetura ficaram
verdes enquanto a compatibilidade quebrava — quem pega é o teste do save legado,
sozinho.

É por isso que a fatia 2 existe antes da 3, e por isso que a máquina de migração
é entrega de passo e não nota de rodapé.

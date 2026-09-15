# Etapa 3 — o jogador, o arcanista e o empurrão

**Status:** em andamento.

## A premissa que mudou o recorte

Em 37 commits ninguém nunca **escolheu** uma ação neste motor.

`legal_actions` nomeia no próprio docstring os dois consumidores que justificam
sua existência — "o menu que uma interface ou uma IA usaria" — e nenhum dos dois
existe. `__main__.combate_narrado` chama `play_out`, que escolhe `acoes[0]` e
cujo docstring diz, com todas as letras, "Nao e uma IA e nao tenta ser".

O esboço da etapa 3 no `CLAUDE.md` era uma lista de mecânicas: magias,
salvaguardas, IA, itens, classes, ataque de oportunidade, ação bônus,
multiataque, HP temporário, tipo de dano. **O que falta neste motor não é
mecânica, é um jogador** — e é o mesmo argumento que na etapa 2 produziu o
narrador, um degrau acima: um motor que se verifica mas não se joga o dono não
julga como jogo.

## As três fatias

| # | Fatia | Passos | Contrato |
|---|---|---|---|
| A | **O jogador** — travas, política com nome, tabuleiro, menu, driver, torneio | 7 | Zero. Nem RNG, nem save, nem regra, nem golden de regra. **Completa** |
| B | **O arcanista** — truque de ataque, a única magia que o motor já roda | 3 | `SCHEMA_VERSION` 4 para 5, uma migração. **Completa** |
| C | **Empurrar** — a primeira fonte de condição dentro do motor | 5 | O primeiro d20 fora de ataque; item 6 no contrato do RNG |

Quinze passos. É o teto que a etapa 2 estabeleceu na prática (quinze passos,
vinte commits). Se o fôlego acabar, corta-se a fatia C e depois a B: a fatia A é
a única cujo valor não depende de nenhuma das outras.

## O que fica de fora, e por quê

| O que fica fora | Por quê |
|---|---|
| **Salvaguarda** (`rules.saving_throw`, CD, proficiência em salvaguarda) | **Não existe produtor de CD.** `d20_check` tem um único chamador em `src/` (`engine.py:575`) e o único `dc` do repositório é `armor_class`. As três fontes possíveis estão bloqueadas: magia de espaço (fora de escopo), teste contra a morte (rolaria em `advance_turn`, a virada que o ADR 0002 §2 manda entrar sozinha) e condição que force salvaguarda (não existe). Seria função sem chamador e campo sem leitor pagando um salto de schema — exatamente o erro de `attack_bonus`/`damage_bonus`, nove commits escritas, testadas e nunca chamadas |
| **Área, Bola de Fogo, espaço de magia** | Quatro campos de estado independentes. Exige ADR próprio (N alvos = 2N d20, e N é geometria: não há quadro fixo possível) e uma v2 do contrato público — o item 3 do docstring de `tacticore.core` diz "Dano. Rolado **somente em acerto**", e `tests/test_contrato_publico.py` pina essa substring |
| **A parcela que vira dado** (ADR 0002 §6) | Com as fichas de hoje `attack_math` produz **sempre** duas parcelas: o evento publicaria a mesma informação noutra forma e o narrador imprimiria a mesma linha. O consumidor real (Bênção) exige magia de espaço, que exige salvaguarda, que exige CD. Vira linha na tabela de desvios, não passo |
| **A IA pontuadora** | As duas fichas não dão o que decidir. Contra CA 13, o estoque do duelista (+3 de ataque, 1d8+1d4) e a adaga (+6, 1d4+3) têm praticamente o mesmo dano esperado; e `_casa_canonica` já decidiu sozinha a única dimensão geométrica. IA volta quando houver multiataque ou ataque de oportunidade — e no primeiro commit com a trava de pureza, porque `apply` é oráculo: lê `position(state.rng)` do estado recebido |
| **Cego, Atordoado, Agarrado, duração** | Empurrar produz `CAIDO` e só. As fontes das outras são magia, salvaguarda e iluminação. Agarrado obriga `Condition` a virar dataclass, e `canonical_conditions` quebra em silêncio nesse dia |
| **Ataque de oportunidade, reação, ação bônus, multiataque** | Três viradas de uma vez cada, e não existe ponto no motor onde alguém que não é `turn_order.current` decida: `_validar_contexto` recusa com `NOT_YOUR_TURN`. O narrador também não tem hierarquia — `AttackRolled` não tem campo dizendo que aquilo foi reação |
| **`EVENTS_VERSION`** | Real e barato, mas as três mudanças que o justificariam estão todas fora. Entra no commit da primeira mudança de **forma** de evento já gravado em golden, e não antes |
| **Tipo de dano, resistência, HP temporário, morte separada de inconsciência, itens, classes** | Continuam sem consumidor nomeado, exatamente como na etapa 2 |

## Decisões tomadas antes de escrever código

**1. A fatia B monta o próprio catálogo.** Medido: `start_combat` guarda o
catálogo **inteiro** no estado (`engine.py:249`), `dump_state` serializa tudo e
`fingerprint` é sha256 disso. Acrescentar uma ficha a `content.srd.CATALOGO`
muda o fingerprint dos seis goldens de encontro sozinho — o do duelo sai de
`806bfe6d...` para outro — num commit em que nem `SCHEMA_VERSION` nem
`RULES_VERSION` se mexem, e aí `_diagnostico` classifica como "regressão até
prova em contrário". O golden do arcanista monta o próprio catálogo, como
`rodar_com_vantagem` já monta os próprios participantes.

**2. `RULES_VERSION` sobe só quando alguma entrada existente passa a calcular
outro resultado.** Vale para as duas fatias, e a régua é a mesma: o campo
`adds_ability_to_damage` com migração que escreve `true` não muda resultado
nenhum, então sobe **só** `SCHEMA_VERSION`. Empurrar não muda resultado de
nenhuma entrada existente, então não sobe nada. Subir "por segurança" produz
seis mensagens de "mudança de REGRA, diga qual regra mudou" sobre goldens onde
nada mudou — a mentira que o ADR 0002 §4 existe para impedir.

**3. `render.board` recebe o ESTADO.** A decisão 1 da etapa 2 dizia "nunca o
estado, nunca um `print`". A segunda metade continua valendo; a primeira não
sobrevive a um tabuleiro. Tabuleiro é **retrato** do estado, narração é **log**
de eventos, e as duas coisas leem fontes diferentes de propósito.

**4. O laço de combate continua único.** O docstring de `__main__` recusa por
escrito um segundo laço de decisão, e continua valendo: `core.testing` ganha um
**gerador** que cede `(estado, menu)` e recebe a `Action`, e `__main__` fica com
`print`, `input` e a cola. O laço fica sob o gate de cobertura, que é onde
`__main__` não está.

**5. O ADR 0001 §3 passa a declarar o quadro por TIPO de checagem.** Ele hoje
fala só de ataque, e é verdadeiro — mas **incompleto**: a iniciativa consome um
d20 e isso nunca foi declarado. Ataque 2, iniciativa 1, teste oposto 2 por lado.
Com o corolário que ninguém escreveu: o que vem **depois** da checagem pode
depender do resultado dela, como `expand_crit` já faz.

**6. Sucesso e falha automáticos não pulam a rolagem.** Num empurrão contra alvo
inconsciente a tentação é pular os d20 do defensor — e aí o consumo passa a
depender do **estado**, que é o modo de falha que o ADR 0001 §3 existe para
impedir. O precedente certo já está no código: `classify_attack` aplica o
automatismo do 20/1 **depois** da rolagem.

## Fatia A — o jogador

Nenhum destes passos acrescenta campo de estado, consome RNG ou toca regra.
`SCHEMA_VERSION` fica em 4, `RULES_VERSION` em 7, os seis goldens de encontro
saem byte a byte iguais e `save_legado.json` carrega com o mesmo fingerprint —
**e é isso que prova que os passos estão certos.**

| # | Passo | Quem consome | A violação que prova a trava |
|---|---|---|---|
| 1 | `print` e `input` são I/O, e o guardião só olhava import | O passo 6, e toda fatia seguinte | Um `print` em `core/queries.py` e um `input` em `content/srd.py` — arquivos **fora** do caminho narrado pelo CLI, senão quem fica vermelho é `tests/test_main.py` e não o guardião novo |
| 2 | `advance_turn` não consome RNG — a trava que o ADR 0002 §2 nunca teve | O dia em que a virada do §2 for necessária: apaga-se um teste com justificativa, em vez de uma frase de ADR que ninguém nota | Um `roll_die` injetado no laço de `advance_turn` |
| 3 | O piloto automático vira política com nome | Os passos 6 e 7, e o golden do empurrão na fatia C | Os seis goldens **byte a byte** iguais; e uma política de mentira que escolhe `acoes[-1]` tem que produzir log diferente, senão o parâmetro é decorativo |
| 4 | Tabuleiro em texto, o primeiro render que lê o estado | O passo 6 — e ninguém mais. Se não vier acompanhado dele, não entra | Mover um combatente **uma** casa muda o desenho |
| 5 | Menu numerado e leitura da escolha, puros | O passo 6 | Entrada fora da faixa não pode devolver ação que `legal_actions` não ofereceu: a assimetria deliberada de `validate` a aceitaria em silêncio |
| 6 | O primeiro turno que um humano escolhe neste motor | O dono. É aqui que ele para de verificar o motor e começa a julgá-lo | A do passo 1, agora exercitada; e uma escolha inválida seguida de uma válida tem que avançar o combate |
| 7 | A primeira afirmação falsificável sobre o jogo | As fatias B e C: sem ele, "o arcanista mudou o jogo" é opinião | Determinismo (mesmas seeds, mesmo placar) **e** falhar fora da faixa: um torneio que só imprime é `print` disfarçado de teste |

## Fatia B — o arcanista

O motor já roda Raio de Fogo inteiro: acerto por d20, 120 pés de alcance
validados, desvantagem com inimigo colado de graça. Erra uma coisa só —
`attack_math` soma o modificador de atributo ao dano **incondicionalmente**, e
truque não soma.

| # | Passo | Contrato | |
|---|---|---|---|
| 8 | `AttackProfile.adds_ability_to_damage`, com migração v4 para v5 | `SCHEMA_VERSION` 4 para 5. `RULES_VERSION` **não** sobe | feito |
| 9 | A ficha do arcanista e o Raio de Fogo | Nenhum. A ficha nasce fora do `CATALOGO` | feito |
| 10 | Golden do arcanista, com catálogo próprio | Golden novo, não regravação | feito |

### O que a execução desmentiu

A análise que precedeu a fatia acertou a forma e errou quatro afirmações, todas
pegas medindo. Ficam registradas porque o erro delas tem padrão: **as quatro
eram justificativas dramáticas para decisões que estavam certas por outro
motivo.**

**O campo entrou SEM default**, e a análise pedia `True`. O argumento dela era
que aqui o default seguro e o default óbvio coincidem. Coincidem mesmo — e é por
isso que o default é perigoso: `True` é exatamente o que faria o próximo truque
nascer errado e em silêncio, que é o bug que o campo existe para impedir. Sem
default, o erro vira argumento faltando. O default mora em
`core.testing.make_attack`, que é onde default de builder deve morar.

**`speed_ft` é 30, e é inerte.** A análise dizia que 25 era "a única peça de
balanceamento da ficha", porque com 30 contra os 30 do brutamontes o vão nunca
fecharia. Medido em 200 seeds, é falso nas duas metades: sob a política do
próprio golden, 25, 30 e 35 dão o **mesmo** placar (118/200) e zero passos; sob
o piloto automático, deslocamento **maior** piora o mago (90/200 com 25 contra
63/200 com 30). Motivo: `_casa_canonica` só oferece a casa que aproxima, então
**neste motor não existe recuo** e cada pé a mais só entra mais depressa no
machado. O docstring da ficha diz isso, em vez de inventar uma história.

**O exemplo não-default no `CODECS` não é o que segura o campo.** A análise
chamava isso de "achado decisivo": com o exemplo em `True`, um `load` que
descartasse a chave ficaria invisível. Conferido: fica **1 vermelho**, porque a
adulteração do save do mesmo commit pega o bug sozinha. O exemplo não-default
entra assim mesmo — é regra da casa e acrescenta a falha de round-trip —, mas
não pela razão que foi dada.

**São três linhas na tabela de desvios, e uma delas corrige a análise.** Ela
queria escrever que um truque de ataque é "a única magia da SRD cujo efeito
inteiro cabe em role o ataque, role o dano". É falso, e o próprio Raio de Fogo
desmente: ele acende objeto inflamável não usado nem carregado, e o motor
descarta isso. `docs/srd-atribuicao.md` é o único documento do projeto cuja
função é ser verdadeiro sobre a SRD, e frase bonita que não resiste à leitura
da magia não entra nele.

### O buraco que a fatia encontrou e não fechou

`test_os_goldens_nao_sao_todos_iguais` enumera os goldens numa lista literal em
vez de varrer a pasta. Medido: com o arquivo em disco e o nome fora da lista, a
suíte inteira passa. Acrescentar o nome é edição obrigatória de todo commit que
cria um golden, e **nenhum guardião cobra**. Está escrito em
`tests/golden/README.md`; trocar a lista por varredura é outro commit.

## Fatia C — empurrar

A primeira fonte de condição dentro do motor, e o primeiro d20 fora de ataque.

| # | Passo | Contrato |
|---|---|---|
| 11 | `rules.contest` — teste oposto, com desfecho de três estados | Nenhum: função pura, sem chamador ainda |
| 12 | `ShoveAction` e `ContestRolled` | Item 6 no contrato do RNG; ADR 0001 §3 reescrito por tipo de checagem |
| 13 | O menu oferece empurrar | Ordem de `legal_actions` — frase no commit, pelo ADR 0002 §1 |
| 14 | Golden do empurrão, com política própria | Golden novo |
| 15 | Fecho: `CLAUDE.md`, `README.md`, tabela de desvios | — |

`d20_check` **não serve** ao teste oposto: `dc` é obrigatório, a docstring diz
"Empate passa" e o corpo é `total >= dc` — o oposto exato da SRD, onde empate
significa que o alvo **resiste**. E não há ponto no motor onde o alvo decida, o
que torna o defensor determinístico: melhor de FOR/DES, com FOR desempatando, e
o evento grava qual atributo ele usou.

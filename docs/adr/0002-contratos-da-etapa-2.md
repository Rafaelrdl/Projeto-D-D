# ADR 0002 — Os contratos que a etapa 2 vai cobrar

**Status:** aceito
**Contexto:** escrito na fatia 1 da etapa 2, antes do grid existir.
**Corrigido nas fatias 2 e 3**, pelas cláusulas que a prática desmentiu — as
correções estão no corpo, com o motivo, e não substituem o texto original em
silêncio.

## Por que este documento existe agora

Cada decisão aqui custa uma frase hoje e custaria um dia de trabalho depois —
porque todas elas ficam congeladas dentro de arquivos de golden no momento em
que a primeira mecânica da fatia 2 entrar. Escrevê-las antes é mais barato que
descobri-las com quatro goldens e um formato de save já em cima.

---

## 1. A ordem de `legal_actions` é contrato, e ela vai deixar de ser fixa

`core.testing.play_out` escolhe `acoes[0]` e gera três dos quatro goldens de
combate. Isso faz da ordem de `legal_actions` um contrato de facto, sem nunca
ter sido decidida como contrato.

**(a1) — corrigida na fatia 3.** A versão original dizia que a ordem "só muda
em commit isolado". A fatia 3 a desmentiu duas vezes, e as duas por motivo
legítimo: o alcance longo mudou **o que** o menu oferece (ataques até a parede
nova em vez de até o alcance curto), e `StandUpAction` acrescentou um item. Nem
uma nem outra era "uma mudança de ordem" que coubesse num commit próprio — as
duas eram consequência de uma mecânica, e separá-las produziria um commit que
não entrega nada.

> Toda mudança na **ordem ou no conteúdo** de `legal_actions` é declarada no
> commit que a causa, com a frase que `tests/golden/README.md` exige. Ela não
> precisa de commit próprio; precisa de ser dita em voz alta, porque `play_out`
> escolhe `acoes[0]` e gera quatro dos sete goldens.

**(a2) — reescrita na fatia 2, como estava previsto.** A versão original dizia
"ação nova entra antes de `EndTurnAction`, que fecha a lista", e valia enquanto
a ordem fosse incondicional. Ela deixou de ser: com alcance de ataque, um ataque
fora de alcance **some da lista**, e `acoes[0]` deixa de ser um ataque para
virar um `MoveAction`. A política que a substitui:

> O menu é ordenado por **quanto a escolha custa e quão irreversível ela é**,
> do mais caro para o mais barato:
>
> 1. **Ataques ao alcance**, na ordem dos ataques na ficha × alvos por id.
>    Gastam a ação, que é o recurso que não volta no turno.
> 2. **Levantar-se**, quando o ator está caído e tem movimento para pagar.
>    Antes de andar, porque um caído que anda continua caído e volta a atacar
>    com desvantagem.
> 3. **A casa canônica**, quando existe uma que aproxima do inimigo mais perto.
>    Gasta movimento, que é divisível e parcialmente recuperável na rodada
>    seguinte.
> 4. **`EndTurnAction`**, sempre por último, sempre presente.
>
> A consequência deliberada: quando nada está ao alcance, `acoes[0]` é o
> movimento — e é assim que um combate que começa a 20 pés fecha distância em
> vez de travar. O `play_out` não decide nada; ele obedece a esta ordem, e é
> por isso que a ordem é contrato e não conveniência.

A trava continua sendo dupla, porque o enunciado ingênuo é falso: `legal_actions`
devolve `()` em dois casos legítimos (combate encerrado, ator caído).

---

## 2. `advance_turn` não consome RNG na etapa 2 inteira

Nada de "a condição termina com uma salvaguarda no fim do turno". Passar o turno
é hoje a única operação do motor que garantidamente não toca o stream, e essa
garantia é usada implicitamente por todo teste que conta posições do RNG.

Quando uma mecânica de relógio precisar rolar dado, isso é uma virada de
contrato — entra sozinha, num commit que diz isso no título.

---

## 3. Quando salvaguarda entrar: quadro fixo de dois d20

Pelo argumento idêntico à decisão 3 do ADR 0001. A alternativa faz a quantidade
de entropia consumida depender do resultado de uma regra, e então a primeira
condição que conceda vantagem numa salvaguarda desloca todo o resto do combate.

Fica escrito **agora**, antes de existir uma salvaguarda, para a primeira magia
não descobrir isso com goldens já congelados em cima.

---

## 4. Quando `RULES_VERSION` sobe

As duas fontes do repositório discordavam: `serde.RULES_VERSION` dizia "qualquer
regra" e o `CLAUDE.md` dizia "o contrato de consumo do RNG". A leitura ampla
vence:

> `RULES_VERSION` sobe quando o motor passa a **calcular outro resultado**, e
> não só quando o stream se desloca.

**A cláusula de agrupamento foi corrigida na fatia 2, e vale a pena dizer por
quê.** A versão original mandava agrupar as subidas "num único commit de virada
por fatia". A fatia 2 a desmentiu na prática: os passos 6, 7 e 8 mudaram o
resultado três vezes, por três motivos diferentes — movimento que move, alcance
que recusa, desvantagem que se aplica — e cada um tinha sua própria frase de
justificativa para escrever.

> O que a cláusula proíbe é fatiar **uma** mudança de resultado em vários
> commits que sobem a versão várias vezes. Três mudanças de resultado distintas
> sobem três vezes, e está certo: o contador é monotônico, não é escasso, e cada
> subida carrega uma frase que alguém consegue escrever com honestidade.

O sinal de que a regra está sendo seguida é o diagnóstico de golden conseguir
classificar cada diff. Na fatia 2 ele pegou um erro real: classificou o passo 7
como mudança de FORMATO "com as regras iguais", dizendo a verdade sobre o que eu
tinha declarado — e o que estava errado era eu não ter subido a versão.

---

## 5. Simplificação da SRD entra com linha na tabela

Toda regra da SRD 5.1 que o motor simplifica acrescenta uma linha em
`docs/srd-atribuicao.md` **no mesmo commit**. Nenhum guardião cobra isso — é
regra social, e por isso precisa estar escrita.

A tabela ficou vazia a etapa 1 inteira enquanto o `CLAUDE.md` a declarava
obrigatória. Foi preenchida retroativamente no commit deste ADR, e o tamanho da
lista é o argumento: são onze desvios que ninguém tinha anotado.

---

## 6. Dívida conhecida: a parcela que vira dado

`rules.d20_check` fecha o bônus num `int`, e `events.AttackRolled` decompõe a
conta em campos fixos (`ability_mod`, `proficiency`). Os dois assumem que tudo
que se soma a um d20 é um número já conhecido.

A primeira Bênção (+1d4 no ataque) quebra as duas coisas ao mesmo tempo: ela é
um **dado físico dentro do bônus**, então desloca o stream *e* não cabe em campo
fixo nenhum.

O quadro fixo de dois d20 do ADR 0001 protege contra vantagem mudar o
alinhamento do stream. **Ele não protege contra isso** — são problemas
diferentes, e é por isso que esta dívida está registrada em vez de assumida como
coberta.

Quando chegar a hora: `bonus` deixa de ser `int` e vira uma sequência de
parcelas nomeadas, algumas com dado. É mudança de assinatura em `rules`, de
formato em `AttackRolled` e de contrato de consumo do RNG — as três de uma vez,
o que significa uma fatia inteira dedicada a ela e não um commit.

# ADR 0002 — Os contratos que a etapa 2 vai cobrar

**Status:** aceito
**Contexto:** fatia 1 da etapa 2, antes do grid existir

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

**(a1)** A ordem de `legal_actions` **é contrato dos goldens** e só muda em
commit isolado, com a frase de justificativa que `tests/golden/README.md` exige.

**(a2)** Enquanto a ordem for **incondicional**, ação nova entra antes de
`EndTurnAction`, que fecha a lista.

> **Com data marcada para ser reescrita.** A fatia 2 torna a ordem *condicional
> ao estado*: com alcance de ataque, um ataque fora de alcance some da lista, e
> `acoes[0]` deixa de ser um ataque para virar um `MoveAction`. No commit em que
> isso acontecer, a cláusula (a2) é substituída por uma política de ordenação
> explícita — e o efeito sobre `play_out` é o ponto principal daquele commit,
> não uma nota de rodapé.

A trava de (a2) é dupla, porque o enunciado ingênuo é falso: `legal_actions`
devolve `()` em dois casos legítimos (combate encerrado, ator caído). O teste
afirma *quando não é vazia, o último item é `EndTurnAction`* **e** *ela só é
vazia nesses dois casos*.

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
vence, e com uma cláusula de agrupamento:

> `RULES_VERSION` sobe quando o motor passa a **calcular outro resultado**, e
> não só quando o stream se desloca. As subidas são agrupadas num **único commit
> de virada por fatia**, nunca espalhadas por cinco commits que regravam os
> mesmos quatro arquivos.

Sem o agrupamento, a fatia 3 regravaria os goldens três vezes, e a terceira
frase de justificativa seria escrita por alguém que já parou de ler as outras
duas.

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

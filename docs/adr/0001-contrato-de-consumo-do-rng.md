# ADR 0001 — O contrato de consumo do RNG

**Status:** aceito
**Contexto:** etapa 1 do motor de regras

## O problema

O projeto promete: *rodar um combate com a mesma seed dá exatamente o mesmo
resultado.* Essa promessa é mais frágil do que parece, porque ela não depende
só do gerador — depende também de **quantos** dados são rolados e **em que
ordem**.

Se ligar vantagem num ataque mudar de um para dois d20, todas as rolagens
seguintes daquele combate escorregam uma posição. O combate continua
determinístico, mas deixa de ser *o mesmo* combate. Um save antigo carregado
depois da mudança simula outra coisa, e todos os goldens quebram por um motivo
que nada tem a ver com a regra que foi alterada.

Ou seja: a ordem e a quantidade de saques são **API pública**, e precisam estar
escritas em algum lugar. Este é o lugar.

## As decisões

### 1. Gerador próprio, counter-based

`random.Random` foi descartado por dois motivos. O primeiro é que
`random.randint` não é contrato estável entre versões do CPython — a
implementação pode mudar, e um save de hoje precisa reproduzir o mesmo combate
no ano que vem. O segundo é que o estado do Mersenne Twister são 624 palavras
mais uma posição, e serializá-lo com segurança é mais difícil do que escrever
um gerador.

O escolhido é o splitmix64 de Vigna em forma indexada: a palavra `n` é
`mix(seed + (n + 1) * GOLDEN)`, calculada direto, sem iterar as anteriores. O
estado inteiro são dois inteiros, `seed` e `counter`, que cabem num JSON.

O deslocamento de um `GOLDEN` na indexação não é enfeite: `mix(0)` é `0`, então
sem ele `seed=0, counter=0` daria a palavra zero, e o primeiro dado de todo
combate com a seed que todo mundo digita primeiro sairia `1`.

### 2. Um dado físico consome exatamente uma palavra

O mapeamento palavra → face é multiply-shift de Lemire, `(word * faces) >> 64`,
**sem rejeição**. O laço de rejeição daria uniformidade perfeita, mas
consumiria um número variável de palavras por dado — e aí a quantidade de
entropia gasta passaria a depender do valor sorteado, que é exatamente o que
este documento existe para impedir.

O viés residual é da ordem de `faces / 2**64`, algo como 10⁻¹⁸ para um d20.

### 3. Ataque consome sempre dois d20

Inclusive sem vantagem. A alternativa — um dado em NORMAL, dois com vantagem —
faz o consumo depender do resultado de uma regra, e então uma condição nova que
conceda vantagem desloca todo o resto do combate.

Entropia desperdiçada custa zero. Regravar quarenta goldens porque alguém
implementou a condição "Caído" custa uma tarde.

Em NORMAL vale o primeiro dado; o segundo vai no evento como descartado, e
serve de prova de que o quadro fixo está sendo respeitado.

### 4. Iniciativa percorre os ids em ordem lexicográfica

E não na ordem em que os participantes foram passados. Sem isso, o mesmo
encontro montado com a lista embaralhada daria outro combate — e "embaralhar a
lista" é exatamente o que um carregador de cenário faz sem avisar.

### 5. Dano só é rolado em acerto

E da esquerda para a direita, um dado físico por chamada. No crítico, os dados
extras de cada termo saem **logo depois** dos originais daquele termo, e não no
fim da expressão: `1d8+1d6` crítico consome d8, d8, d6, d6.

A ausência de `DamageRolled` no log é, por construção, a prova de que um erro
não consumiu entropia.

### 6. Ação recusada não consome nada

Toda validação roda antes do primeiro toque no RNG. Sem essa garantia, dois
combates com a mesma seed divergiriam só porque um deles tentou uma jogada
ilegal pelo caminho — e o culpado seria muito difícil de achar.

## Consequências

- Qualquer mudança nos pontos acima obriga a incrementar `serde.RULES_VERSION`.
  Um save com `rules_version` diferente ainda carrega, mas quem lê o envelope
  sabe que o resultado vai divergir.
- Os goldens em `tests/golden/data/` são a trava executável deste documento.
- `fork(rng, label)`, que geraria streams independentes por rótulo, ficou de
  fora: seria o único vetor de não-determinismo do desenho se o rótulo virasse
  `hash(label)`, e não tem consumidor no escopo atual. Volta quando houver IA,
  com hash estável documentado.

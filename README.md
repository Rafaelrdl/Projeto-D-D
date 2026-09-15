# Tacticore

Motor de regras de combate tático por turnos, baseado na SRD 5.1, escrito como
biblioteca pura de Python e exercitado inteiramente por testes.

Não há engine de jogo nem interface gráfica. O núcleo recebe um estado de
combate e uma ação, e devolve um estado novo mais a lista de eventos do que
aconteceu. Uma camada fina por cima transforma esses eventos em texto.

```bash
uv sync
uv run python -m tacticore
```

```
bruto rola iniciativa: d20 2 -1 (DES 8) = 1
lamina rola iniciativa: d20 14 +3 (DES 17) = 17
ordem de iniciativa: lamina, bruto
== rodada 1 ==
turno de lamina: 1 acao, 35 pes
lamina ataca bruto com Adaga Arremessada: d20 15 +3 DES +3 prof = 21 vs CA 13 -> acerto
  dano: d4=1 +3 = 4
  bruto: 14 -> 10 hp (4 de dano)
lamina anda 15 pes (4,0) -> (1,0), 20 restantes
lamina encerra o turno
...
```

A conta sai aberta de propósito: a pergunta que se faz olhando um log de combate
é quase sempre "de onde saiu esse número".

## O que o motor faz

**Regras** — atributos e modificadores, d20 contra Classe de Armadura, vantagem
e desvantagem não-acumulativas, crítico no 20 natural dobrando os dados (e não o
modificador), falha automática no 1, dano por notação de dados, queda em 0 HP.

**Combate** — iniciativa determinística com desempate total, economia de turno
(uma ação, um movimento), times, fim de combate por aniquilação, e um menu de
ações legais que uma interface ou uma IA podem consumir.

**Grade** — posição em casas de 5 pés, movimento que custa e move, alcance de
ataque, e a primeira regra derivada do estado: atirar com um inimigo colado dá
desvantagem.

**Determinismo** — a mesma seed dá exatamente o mesmo combate, inclusive depois
de salvar e recarregar no meio de uma rodada.

## Rodando

```bash
uv run pytest                    # a suíte
uv run pytest --cov              # com o gate de cobertura
uv run pytest -m "not slow"      # sem o teste estatístico
uv run ruff check . && uv run ruff format .
uv run mypy
```

## As cinco regras da casa

1. `core/` não importa nada de engine, renderização, I/O ou rede.
2. Todo estado de combate é serializável (dataclasses -> dict -> JSON).
3. Aleatoriedade só através do `RngState` que vive dentro do estado.
4. Mecânica nova entra junto com teste.
5. Tipagem em toda assinatura pública, mypy strict.

Detalhes e o porquê de cada decisão em [CLAUDE.md](CLAUDE.md).

## Como o projeto está organizado

```
src/tacticore/
├─ core/       o motor de regras. Puro.
├─ render/     transforma o log em texto. Puro, não imprime.
├─ content/    fichas e encontros: dado de jogo. Puro.
└─ __main__.py o único lugar do projeto que faz I/O.
```

O `core` é dividido em camadas com dependência só para baixo, e um teste de
arquitetura reprova quem apontar para cima. As funções de regra (`rules.py`)
**nunca recebem o estado de combate** — elas recebem números e descritores.
Parece arbitrário e não é: regra que precisa do estado inteiro só pode ser
testada montando um combate, e a partir daí ninguém mais escreve o teste da
tabela de modificadores de 1 a 30.

## Tipos permitidos em campo de estado

`str`, `int`, `bool`, `StrEnum`, `tuple`, dataclass frozen e `Mapping[str, ...]`.

**Sem `float`** (toda regra do SRD é inteira; float no JSON é round-trip que
quase bate), **sem `set`** (ordem de iteração varia com `PYTHONHASHSEED` e quebra
determinismo de forma intermitente), **sem `list`/`dict` mutável**, sem chave
`int`, **sem `None`** — ausência se modela como tupla vazia ou membro de enum.

## O contrato de consumo do RNG

A ordem e a quantidade de dados rolados são **API pública**, não detalhe de
implementação: mudá-las desloca todas as rolagens seguintes de todo combate em
andamento e invalida todo save e todo golden existente.

O contrato está escrito no docstring de `tacticore.core` — onde ele é lido, na
hora de escrever a próxima regra — e o porquê de cada item está em
[docs/adr/0001](docs/adr/0001-contrato-de-consumo-do-rng.md). Um teste falha se
o docstring perder o bloco.

## Saves e migração

O envelope de save carrega três versões, cada uma respondendo a uma pergunta
diferente: `schema_version` (o formato mudou), `rules_version` (o resultado
mudou) e `rng_algo` (o gerador mudou).

**Um save antigo não carrega só porque o campo novo tem default** — o leitor
levanta na chave ausente. Compatibilidade exige uma função de migração por
salto, e os saltos são aplicados em cadeia. O `save_legado.json` congelado nos
testes está no formato v1 e hoje atravessa dois deles.

## Licença e atribuição

Este projeto usa material da SRD 5.1, disponibilizada sob
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).
A atribuição completa e a lista de desvios conscientes das regras originais
ficam em [docs/srd-atribuicao.md](docs/srd-atribuicao.md).

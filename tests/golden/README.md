# Goldens

Cada arquivo em `data/` é o log inteiro de um encontro canônico, congelado.
Eles existem para pegar a mudança que ninguém previu: uma refatoração que troca
a ordem de duas rolagens não quebra nenhum teste de unidade, e quebra todos
estes.

## A regra social

**Todo diff de golden precisa de uma frase no commit dizendo qual regra mudou e
por quê.** Sem isso, `--update-golden` vira um botão de "fazer o teste calar", e
a trava deixa de valer no exato momento em que ela seria útil.

Se o diff for grande e você não souber explicá-lo em uma frase, a mudança
provavelmente fez mais do que você pretendia.

## Regravar

```bash
uv run pytest tests/golden --update-golden
```

Nunca automático, nunca dentro da suíte normal. Depois de regravar, leia o diff
antes de commitar — é para isso que ele está em JSON legível.

## O que mais mora aqui

`data/save_legado.json` é um save gravado com o formato v1 e **congelado**. Ele
não é regravado por `--update-golden`. Se um dia ele parar de carregar, isso é
uma quebra de compatibilidade de save, e não um golden desatualizado.

## O que os goldens **não** cobrem

Eles pegam mudança de ordem, de quantidade de rolagens e de resultado agregado
— e é para isso que existem. Eles **não** cobrem cada ramo de regra: um combate
gravado só passa pelos ramos que aquela seed calhou de exercitar.

Conferido na prática, na hora de escrevê-los:

| Mudança injetada | Goldens que falharam |
|---|---|
| Limiar de crítico de 20 para 19 | 3 de 4 |
| Vantagem escolhendo o menor dado | só `vantagem` |
| Empate na vantagem pegando o 2º dado | **nenhum** |
| Movimento que debita mas não move | 3 de 5 |
| `legal_actions` ignorando alcance | os que usam o piloto automático |
| Desvantagem derivada deixando de ser aplicada | só `tiro_colado` |

A última linha é o ponto. Nos 20 ataques gravados, nenhum tirou os dois d20
iguais — o ramo de empate simplesmente não aparece. Quem cobre isso é
`tests/unit/test_d20.py::test_empate_escolhe_o_primeiro_dado`, e é lá que ele
deve ser coberto: forçar uma seed até o empate cair seria contorcer o golden
para fazer o trabalho de um teste de unidade.

A tabela também explica por que dois dos goldens existem. O piloto automático
nunca declara fonte de vantagem, então sem `vantagem.json` os goldens
exercitavam exclusivamente `NORMAL`. E ele nunca atira de perto — `legal_actions`
oferece a arma corpo a corpo primeiro, e de perto ela é melhor — então sem
`tiro_colado.json` a regra de "atirar com inimigo colado dá desvantagem" não
apareceria em log nenhum.

**Os dois têm um teste que cobra o que eles exercitam**, e não só o conteúdo
congelado. Sem isso, um golden pode virar mais um combate comum em silêncio e a
lacuna que ele tapava volta sozinha. Foi exatamente esse teste que reprovou a
primeira seed do `tiro_colado`: ela matava a atiradora na rodada 1, antes de ela
atirar.

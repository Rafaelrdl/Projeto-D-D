"""O tabuleiro em texto: um retrato do estado, e nao um log de eventos.

Este e o primeiro render do projeto que recebe `CombatState`. A decisao 1 da
etapa 2 dizia "nunca o estado, nunca um `print`", e a segunda metade continua
valendo integralmente -- nada aqui imprime. A primeira nao sobrevive a um
tabuleiro, e o motivo e que as duas coisas leem fontes diferentes de proposito:

- `narrate` conta **o que aconteceu**, e le eventos. Um evento e imutavel e
  vira linha uma vez so.
- `board` mostra **onde todo mundo esta agora**, e le o estado. Nao ha evento
  algum que responda isso: `MovementSpent` diz de onde para onde um combatente
  foi, e reconstruir o mapa a partir do log inteiro e trabalho que o estado ja
  fez.

Hoje a posicao so aparece no log como par de coordenadas dentro de
`MovementSpent`, e ninguem le ``(4,0) -> (1,0)`` de cabeca. Por isso o cabecalho
de coluna e o rotulo de linha trazem a coordenada **de verdade**, com sinal:
achar no desenho a casa que a narracao citou e o unico trabalho que este modulo
existe para poupar.
"""

from __future__ import annotations

from tacticore.core.ids import CreatureId
from tacticore.core.model import CombatState
from tacticore.core.queries import is_conscious

MARGEM = 1
"""Uma casa de folga em volta de todo mundo.

Sem folga, quem esta na borda parece encostado numa parede que nao existe --
este motor nao tem parede. Com folga, ve-se que ha para onde andar."""

VAZIA = "."
CAIDO = "x"
"""Glifo de quem esta a 0 HP. Ele continua ocupando a casa (ninguem sai da
ordem de iniciativa ao cair), e um tabuleiro que o escondesse mentiria sobre o
que bloqueia passagem."""

ALFABETO = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
"""O glifo vem da posicao na ordem de iniciativa, e nao da inicial do id.

Inicial colide -- `bruto` e `brutamontes` dariam o mesmo `B` -- e resolver
colisao de inicial e inventar regra de desempate onde ja existe uma ordem
canonica pronta. Ordem de iniciativa e, alem disso, a ordem que o jogador ja
leu no log, entao o numero do tabuleiro e o mesmo numero do `ordem de
iniciativa:` la em cima."""


def _glifo(indice: int) -> str:
    """Um caractere, sempre: cela de largura fixa mantem a grade alinhada."""
    return ALFABETO[indice] if indice < len(ALFABETO) else "?"


def board(state: CombatState) -> tuple[str, ...]:
    """O tabuleiro e a legenda, uma linha por linha de texto.

    Devolve linhas e nao uma string unica pelo mesmo motivo que `narrate`:
    quem imprime decide o separador, e quem testa compara item a item.
    """
    posicoes = {c.id: c.position for c in state.combatants.values()}
    glifos = {cid: _glifo(i) for i, cid in enumerate(state.turn_order.order)}

    xs = [p.x for p in posicoes.values()]
    ys = [p.y for p in posicoes.values()]
    x0, x1 = min(xs) - MARGEM, max(xs) + MARGEM
    y0, y1 = min(ys) - MARGEM, max(ys) + MARGEM

    ocupante: dict[tuple[int, int], CreatureId] = {
        (p.x, p.y): cid for cid, p in sorted(posicoes.items(), key=lambda kv: str(kv[0]))
    }

    largura = max(len(str(v)) for v in (*range(x0, x1 + 1), *range(y0, y1 + 1)))
    rotulo = max(largura, 1)

    linhas = [" " * rotulo + " " + " ".join(f"{x:>{largura}}" for x in range(x0, x1 + 1))]
    for y in range(y0, y1 + 1):
        celas = []
        for x in range(x0, x1 + 1):
            cid = ocupante.get((x, y))
            if cid is None:
                celas.append(f"{VAZIA:>{largura}}")
            elif is_conscious(state.combatants[cid]):
                celas.append(f"{glifos[cid]:>{largura}}")
            else:
                celas.append(f"{CAIDO:>{largura}}")
        linhas.append(f"{y:>{rotulo}} " + " ".join(celas))

    linhas.append("")
    linhas.extend(_legenda(state, glifos))
    return tuple(linhas)


def _legenda(state: CombatState, glifos: dict[CreatureId, str]) -> list[str]:
    """Quem e cada glifo, na ordem de iniciativa.

    Traz vida, time e condicoes porque sem elas o desenho responde "onde" e
    deixa o jogador sem "quanto falta" -- e as duas perguntas se fazem juntas,
    olhando o mesmo tabuleiro, na hora de escolher o alvo.
    """
    largura = max((len(str(c)) for c in state.turn_order.order), default=0)
    saida = []
    for cid in state.turn_order.order:
        c = state.combatants[cid]
        marca = glifos[cid] if is_conscious(c) else CAIDO
        extra = " " + ",".join(x.value.lower() for x in c.conditions) if c.conditions else ""
        saida.append(f"{marca} {cid:<{largura}}  {c.team}  {c.hp.current}/{c.hp.maximum} hp{extra}")
    return saida

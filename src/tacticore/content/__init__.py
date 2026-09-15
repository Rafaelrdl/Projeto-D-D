"""Conteudo: as fichas e os encontros que o motor joga.

Mora fora do `core` pelo mesmo motivo que `render`: nao e regra. Uma ficha de
goblin e **dado**, e dado de jogo nao pertence ao motor que o interpreta -- se
pertencesse, acrescentar um monstro seria mexer no core.

E puro como o core: nada aqui abre arquivo. As fichas sao constantes de modulo;
carregar de JSON e trabalho de quem tiver um JSON para carregar, e essa camada
nasce quando houver conteudo demais para caber em Python legivel.

**Esta fachada nao e o indice completo do conteudo.** `tacticore.content.
arcanista` tem uma ficha que fica deliberadamente fora do `CATALOGO` e fora
deste `__all__`, porque entrar em qualquer um dos dois mudaria o fingerprint
dos goldens de encontro. O motivo inteiro esta no docstring daquele modulo, que
e onde ele tem endereco.
"""

from __future__ import annotations

from tacticore.content.srd import BRUTAMONTES, CATALOGO, DUELISTA, duelo

__all__ = ("BRUTAMONTES", "CATALOGO", "DUELISTA", "duelo")

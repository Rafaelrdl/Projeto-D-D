"""Apresentacao: transforma o log do motor em coisa que se le.

Mora **fora** do `core` porque nao e regra. O core deliberadamente nao carrega
frase formatada dentro de evento -- `core.events` diz isso no proprio docstring
-- e este pacote e quem paga essa promessa: ele recebe os dados crus e monta o
texto.

Continua sendo codigo **puro**, como o core: nada aqui imprime, abre arquivo ou
consulta relogio. Quem escreve na tela e `tacticore.__main__`, e so ele.
"""

from __future__ import annotations

from tacticore.render.board import board
from tacticore.render.text import narrate, narrate_event

__all__ = ("board", "narrate", "narrate_event")

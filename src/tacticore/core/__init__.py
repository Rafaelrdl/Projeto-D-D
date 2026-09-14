"""Motor de regras puro: recebe estado + acao, devolve estado novo.

Este pacote nao importa nada de engine, renderizacao, I/O ou rede, e nao guarda
estado em global nem em singleton. Toda aleatoriedade passa pelo ``RngState``
que vive dentro do proprio estado de combate, de modo que rodar um combate com
a mesma seed produz exatamente o mesmo resultado -- inclusive depois de salvar
e recarregar no meio de uma rodada.

As camadas dependem so para baixo::

    ids / enums / errors -> rng / dice -> model -> actions / events
                         -> results -> rules -> queries -> engine

``tests/architecture/test_import_boundaries.py`` reprova qualquer violacao.

.. note::
   O contrato de consumo do RNG (ordem e quantidade de saques por acao) e API
   publica e sera publicado aqui e em ``docs/adr/0001`` quando as regras que ele
   descreve existirem.
"""

__all__: tuple[str, ...] = ()

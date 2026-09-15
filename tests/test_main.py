"""O comando, que e a unica camada com I/O.

O que se testa aqui e o contrato de linha de comando -- codigo de saida, o que
vai para stdout e o que vai para stderr. O conteudo das linhas e problema de
`tests/render/`, e o combate em si e problema de `tests/golden/`.
"""

from __future__ import annotations

import pytest

from tacticore.__main__ import SEED_PADRAO, USO, combate_narrado, main


def test_sem_argumento_roda_a_seed_padrao(capsys: pytest.CaptureFixture[str]):
    assert main([]) == 0
    saida = capsys.readouterr()
    assert saida.out.splitlines() == list(combate_narrado(SEED_PADRAO))
    assert saida.err == ""


def test_a_seed_vem_do_argumento(capsys: pytest.CaptureFixture[str]):
    assert main(["4242"]) == 0
    assert capsys.readouterr().out.splitlines() == list(combate_narrado(4242))


def test_seeds_diferentes_dao_combates_diferentes(capsys: pytest.CaptureFixture[str]):
    """Sem isto, um comando que ignorasse o argumento passaria no teste de cima."""
    main(["1"])
    um = capsys.readouterr().out
    main(["2"])
    dois = capsys.readouterr().out
    assert um != dois


def test_seed_que_nao_e_numero_e_recusada(capsys: pytest.CaptureFixture[str]):
    assert main(["abc"]) == 2
    saida = capsys.readouterr()
    assert saida.out == "", "erro nao vai para stdout"
    assert "seed invalida" in saida.err
    assert USO in saida.err


def test_argumento_a_mais_e_recusado(capsys: pytest.CaptureFixture[str]):
    assert main(["1", "2"]) == 2
    saida = capsys.readouterr()
    assert saida.out == ""
    assert USO in saida.err


def test_seed_negativa_e_aceita():
    """Nao ha motivo para recusar: o gerador mascara para 64 bits."""
    assert main(["-7"]) == 0


def test_o_combate_narrado_e_puro():
    """A funcao que o `main` usa nao imprime nada -- e por isso que da para
    testar o conteudo sem capturar saida."""
    assert combate_narrado(SEED_PADRAO) == combate_narrado(SEED_PADRAO)


def test_o_combate_termina():
    linhas = combate_narrado(SEED_PADRAO)
    assert linhas[-1].startswith("combate encerrado")

"""O comando, que e a unica camada com I/O.

O que se testa aqui e o contrato de linha de comando -- codigo de saida, o que
vai para stdout e o que vai para stderr. O conteudo das linhas e problema de
`tests/render/`, e o combate em si e problema de `tests/golden/`.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from tacticore.__main__ import (
    ABANDONO,
    CODIGO_DE_ABANDONO,
    FLAG_JOGAR,
    NAO_ENTENDI,
    SEED_PADRAO,
    USO,
    combate_narrado,
    main,
)


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


# ------------------------------------------------------ o modo --jogar -----


def digitando(monkeypatch: pytest.MonkeyPatch, *respostas: str) -> None:
    """Enfileira o que o jogador digita. Esgotada a fila, vem EOF.

    EOF no fim e deliberado e nao e conveniencia de teste: e o que acontece de
    verdade quando alguem fecha o terminal no meio de uma pergunta, e o unico
    jeito de um teste garantir que a fila acabou em vez de o combate ter
    seguido lendo string vazia para sempre.
    """
    fila = iter(respostas)

    def _input(prompt: str = "") -> str:
        try:
            return next(fila)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", _input)


SEMPRE_A_PRIMEIRA = ("1",) * 40


def subsequencia(procuradas: Sequence[str], dentro: Sequence[str]) -> bool:
    """Todas as `procuradas` aparecem em `dentro`, na mesma ordem."""
    resto = iter(dentro)
    return all(any(linha == candidata for candidata in resto) for linha in procuradas)


def test_jogar_escolhendo_sempre_a_primeira_da_o_combate_do_piloto(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A trava central do modo interativo: e o MESMO laco.

    `primeira_legal` escolhe `acoes[0]`, e um jogador que digita 1 toda vez
    escolhe a mesma coisa -- entao a narracao do combate jogado a mao tem que
    conter, em ordem, cada linha do combate do piloto automatico. Se
    divergisse, o comando interativo seria um segundo motor de decisao, que e
    justamente o que o docstring deste modulo recusa.
    """
    digitando(monkeypatch, *SEMPRE_A_PRIMEIRA)
    assert main([FLAG_JOGAR]) == 0

    saida = capsys.readouterr().out.splitlines()
    assert subsequencia(combate_narrado(SEED_PADRAO), saida)


def test_o_tabuleiro_e_o_menu_aparecem_no_turno_do_jogador(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    digitando(monkeypatch, *SEMPRE_A_PRIMEIRA)
    main([FLAG_JOGAR])
    saida = capsys.readouterr().out
    assert "encerrar o turno" in saida, "menu"
    assert "herois" in saida, "legenda do tabuleiro"


def test_escolha_invalida_pergunta_de_novo_e_nao_come_a_jogada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A trava que um teste de fumaca nao pega: um laco que tratasse `None`
    como "encerra o turno" rodaria ate o fim, sairia com 0 e teria comido a
    jogada de quem errou uma tecla.

    Por isso a asercao e de IGUALDADE com o combate sem erro de digitacao, e
    nao "terminou sem estourar".
    """
    digitando(monkeypatch, *SEMPRE_A_PRIMEIRA)
    main([FLAG_JOGAR])
    limpo = capsys.readouterr().out

    digitando(monkeypatch, "xyz", "0", "99", *SEMPRE_A_PRIMEIRA)
    assert main([FLAG_JOGAR]) == 0
    com_erro = capsys.readouterr()

    assert com_erro.out == limpo
    assert com_erro.err.count(NAO_ENTENDI) == 3


def test_fechar_o_terminal_no_meio_e_saida_normal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Ctrl+D numa pergunta nao e defeito, e quem sai assim nao quer ver
    traceback."""
    digitando(monkeypatch)
    assert main([FLAG_JOGAR]) == CODIGO_DE_ABANDONO
    assert ABANDONO in capsys.readouterr().err


# ------------------------------------------------- os argumentos novos -----


def test_a_flag_aceita_seed_antes_e_depois(monkeypatch: pytest.MonkeyPatch):
    for argv in ([FLAG_JOGAR, "4242"], ["4242", FLAG_JOGAR]):
        digitando(monkeypatch, *SEMPRE_A_PRIMEIRA)
        assert main(argv) == 0, argv


def test_a_flag_repetida_nao_vira_argumento_a_mais(monkeypatch: pytest.MonkeyPatch):
    """Ela e filtrada, e nao contada: repetir nao e erro de digitacao que
    mereca recusar o comando inteiro."""
    digitando(monkeypatch, *SEMPRE_A_PRIMEIRA)
    assert main([FLAG_JOGAR, FLAG_JOGAR]) == 0


def test_seed_invalida_com_a_flag_e_recusada_antes_de_perguntar_nada(
    capsys: pytest.CaptureFixture[str],
):
    """Sem `digitando`: se o comando chegasse a perguntar, `input` leria o
    stdin nulo do pytest e o teste quebraria com EOFError em vez de passar."""
    assert main(["abc", FLAG_JOGAR]) == 2
    assert "seed invalida" in capsys.readouterr().err


def test_dois_argumentos_alem_da_flag_continuam_recusados(capsys: pytest.CaptureFixture[str]):
    assert main(["1", "2", FLAG_JOGAR]) == 2
    assert USO in capsys.readouterr().err


def test_o_uso_menciona_a_flag():
    assert FLAG_JOGAR in USO

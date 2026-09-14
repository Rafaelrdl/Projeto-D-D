"""O RNG e a fundacao do determinismo: se ele escorregar, todo o resto mente."""

from __future__ import annotations

from collections import Counter

import pytest

from tacticore.core.errors import RngExhausted, ScriptedRngOutOfRange
from tacticore.core.rng import (
    ScriptedRng,
    SplitMix64,
    _word,
    position,
    roll_dice,
    roll_die,
)

# Vetores de referencia do splitmix64 de Vigna para seed 0. Sao publicados e
# verificaveis fora deste repositorio -- e por isso que eles provam alguma
# coisa. Vetor gerado pela propria implementacao nao prova nada.
VETORES_SEED_ZERO = (
    0xE220A8397B1DCDAF,
    0x6E789E6AA1B965F4,
    0x06C45D188009454F,
    0xF88BB8A8724C81EC,
)


@pytest.mark.parametrize(("indice", "esperado"), tuple(enumerate(VETORES_SEED_ZERO)))
def test_gerador_bate_com_o_splitmix64_de_referencia(indice: int, esperado: int):
    assert _word(0, indice) == esperado


def test_seed_zero_nao_degenera_no_primeiro_dado():
    """`mix(0)` e `0`. Sem o deslocamento de um golden, seed 0 daria d20 = 1.

    Regressao de um bug que nunca chegou a existir, mas que so aparece na seed
    que todo mundo digita primeiro quando esta testando alguma coisa.
    """
    face, _ = roll_die(SplitMix64(seed=0), 20)
    assert face != 1


def test_palavra_independe_da_ordem_de_chamada():
    """Counter-based: a palavra 7 e a palavra 7, com ou sem as seis anteriores."""
    direto = _word(1234, 7)
    rng = SplitMix64(seed=1234)
    for _ in range(7):
        _, rng = roll_die(rng, 20)
    assert _word(1234, position(rng)) == _word(1234, 7) == direto


def test_cada_dado_consome_exatamente_uma_posicao():
    """A invariante que torna o contrato de consumo do RNG verificavel."""
    rng: SplitMix64 | ScriptedRng = SplitMix64(seed=7)
    for esperado in range(1, 51):
        _, rng = roll_die(rng, 20)
        assert position(rng) == esperado


def test_roll_dice_consome_uma_posicao_por_dado():
    rng = SplitMix64(seed=7)
    faces, depois = roll_dice(rng, 8, 6)
    assert len(faces) == 8
    assert position(depois) == 8


def test_roll_dice_de_zero_dados_nao_consome_nada():
    rng = SplitMix64(seed=7)
    faces, depois = roll_dice(rng, 0, 6)
    assert faces == ()
    assert depois == rng


def test_rolagem_nao_muda_o_rng_original():
    """Se o RNG mutasse, `Rejected` devolvendo o mesmo estado seria mentira."""
    rng = SplitMix64(seed=99, counter=3)
    roll_die(rng, 20)
    assert rng.counter == 3


@pytest.mark.parametrize("faces", [2, 4, 6, 8, 10, 12, 20, 100])
def test_face_sempre_dentro_da_faixa(faces: int):
    rng: SplitMix64 | ScriptedRng = SplitMix64(seed=faces)
    for _ in range(2000):
        face, rng = roll_die(rng, faces)
        assert 1 <= face <= faces


def test_d1_sempre_um_e_ainda_assim_consome_posicao():
    face, depois = roll_die(SplitMix64(seed=5), 1)
    assert face == 1
    assert position(depois) == 1


@pytest.mark.parametrize("faces", [0, -1])
def test_dado_sem_faces_e_erro_de_programacao(faces: int):
    with pytest.raises(ValueError, match="ao menos uma face"):
        roll_die(SplitMix64(seed=1), faces)


def test_quantidade_negativa_de_dados_e_erro_de_programacao():
    with pytest.raises(ValueError, match="quantidade negativa"):
        roll_dice(SplitMix64(seed=1), -1, 6)


def test_mesma_seed_mesma_sequencia():
    a, _ = roll_dice(SplitMix64(seed=2024), 50, 20)
    b, _ = roll_dice(SplitMix64(seed=2024), 50, 20)
    assert a == b


def test_seeds_diferentes_divergem():
    a, _ = roll_dice(SplitMix64(seed=1), 50, 20)
    b, _ = roll_dice(SplitMix64(seed=2), 50, 20)
    assert a != b


def test_estado_reconstruido_continua_o_mesmo_futuro():
    """O ensaio do save/load: o que importa e (seed, counter), e nada mais."""
    rng = SplitMix64(seed=777)
    _, rng = roll_dice(rng, 13, 20)

    continuando, _ = roll_dice(rng, 10, 20)
    recarregado, _ = roll_dice(SplitMix64(seed=777, counter=position(rng)), 10, 20)
    assert continuando == recarregado


# --------------------------------------------------------------- fita ------


def test_fita_devolve_na_ordem_escrita():
    rng: SplitMix64 | ScriptedRng = ScriptedRng(script=(20, 1, 13))
    saidas = []
    for _ in range(3):
        face, rng = roll_die(rng, 20)
        saidas.append(face)
    assert saidas == [20, 1, 13]
    assert position(rng) == 3


def test_fita_recusa_valor_impossivel_para_o_dado():
    """Devolver 13 num d6 faria o teste afirmar uma regra que o motor nao tem.

    E o pior modo de falha possivel aqui: verde mentiroso.
    """
    with pytest.raises(ScriptedRngOutOfRange, match="impossivel num d6"):
        roll_die(ScriptedRng(script=(13,)), 6)


def test_fita_recusa_zero_e_negativo():
    with pytest.raises(ScriptedRngOutOfRange):
        roll_die(ScriptedRng(script=(0,)), 20)


def test_fita_esgotada_levanta_em_vez_de_ciclar():
    rng: SplitMix64 | ScriptedRng = ScriptedRng(script=(5, 5))
    _, rng = roll_die(rng, 20)
    _, rng = roll_die(rng, 20)
    with pytest.raises(RngExhausted, match="esgotada"):
        roll_die(rng, 20)


def test_fita_vazia_nao_consome_e_nao_rola():
    rng = ScriptedRng(script=())
    assert position(rng) == 0
    with pytest.raises(RngExhausted):
        roll_die(rng, 20)


# --------------------------------------------------------- estatistica -----


@pytest.mark.slow
def test_d20_e_uniforme_o_bastante():
    """Qui-quadrado sobre 1e6 d20: pega vies de mapeamento, nao vies do gerador.

    Fora do loop de desenvolvimento (`-m "not slow"`). Valor critico para 19
    graus de liberdade a p=0,001 e 43,82.
    """
    total = 1_000_000
    faces, _ = roll_dice(SplitMix64(seed=20250914), total, 20)
    contagem = Counter(faces)
    assert set(contagem) == set(range(1, 21))

    esperado = total / 20
    qui = sum((n - esperado) ** 2 / esperado for n in contagem.values())
    assert qui < 43.82, f"qui-quadrado {qui:.2f} alto demais para uniforme"

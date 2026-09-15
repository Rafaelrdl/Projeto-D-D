"""A primeira afirmacao falsificavel sobre o jogo.

Em 38 commits este projeto provou muita coisa sobre o motor e nenhuma sobre o
**jogo**: nao havia um numero em lugar nenhum dizendo se o duelo canonico e
equilibrado. Ele nao e, e agora esta escrito: o brutamontes ganha 370 de 500.

.. warning::
   **Isto e um golden de regra morando fora de `tests/golden/`.** O numero
   congela motor, fichas e politica ao mesmo tempo, e `_diagnostico` -- que
   classificaria o diff -- nao alcanca este arquivo. Por isso a mensagem de
   falha faz o trabalho dele a mao, nomeando as tres causas possiveis. Quando
   ela aparecer, a pergunta nao e "regravo?", e "qual das tres?".

**O placar e exato, e nao uma faixa.** Nao ha nada de estatistico aqui: as
seeds sao fixas e o motor e deterministico, entao rodar duas vezes da o mesmo
numero sempre. E uma faixa que aguentasse ruido inexistente so serviria para
nao falhar -- medido, tirar **um** ponto de vida do brutamontes move o placar
2,4 pontos percentuais, e uma faixa de +/-5 deixaria isso passar em silencio.

Marcado `slow` porque custa ~1,3s contra os 4,4s da suite inteira. Fora do
loop de desenvolvimento com ``uv run pytest -m "not slow"``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

import pytest

from tacticore.content.srd import BRUTAMONTES, CATALOGO, DUELISTA, duelo
from tacticore.core.actions import Action
from tacticore.core.engine import combat_result, start_combat
from tacticore.core.errors import CorruptStateError
from tacticore.core.ids import StatblockId
from tacticore.core.model import CombatState, Statblock
from tacticore.core.rng import SplitMix64, position
from tacticore.core.testing import Politica, play_out, primeira_legal

SEEDS = 500
"""Constante com nome para que mudar o tamanho do torneio apareca no diff.

Embutido na chamada, alguem "so aumentaria um pouco para ver" e o placar
esperado mudaria junto, sem que o diff dissesse por que."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Placar:
    """O que N duelos produziram. Tres numeros, tres perguntas diferentes."""

    vitorias: Mapping[str, int]
    """Quem ganha. Move com regra, com ficha e com politica."""

    rodadas: int
    """Quanto dura. Um combate que fica mais longo sem mudar quem ganha e uma
    mudanca que so este numero mostra."""

    dados: int
    """Quanta entropia foi consumida. Move com o **contrato de consumo do
    RNG**, e so com ele -- e por isso e o numero que separa "a regra mudou" de
    "o stream deslocou"."""


def placar(
    seeds: Sequence[int],
    *,
    politica: Politica = primeira_legal,
    catalogo: Mapping[StatblockId, Statblock] = CATALOGO,
) -> Placar:
    """Roda o duelo canonico uma vez por seed e soma o que aconteceu."""
    vitorias: Counter[str] = Counter()
    rodadas = 0
    dados = 0

    for seed in seeds:
        abertura = start_combat(
            statblocks=catalogo, participants=duelo(), rng=SplitMix64(seed=seed)
        )
        final, _ = play_out(abertura.state, politica=politica)

        desfecho = combat_result(final)
        assert desfecho is not None, f"seed {seed}: o combate nao terminou"
        vitorias[desfecho.winning_team or "ninguem"] += 1
        rodadas += final.turn_order.round_number
        dados += position(final.rng)

    return Placar(vitorias=dict(vitorias), rodadas=rodadas, dados=dados)


ESPERADO = Placar(
    vitorias={"herois": 370, "viloes": 130},
    rodadas=1098,
    dados=6567,
)
"""O duelo canonico sob `primeira_legal`, nas seeds 0 a 499.

74% para o brutamontes. Nao e equilibrio, e esta certo que nao seja: as duas
fichas nunca foram desenhadas uma contra a outra -- e uma delas carrega um
desvio conhecido (`DUELISTA.estoque` usa FOR com forca 10). Medido, corrigi-lo
leva o placar para 57%, e este numero e o que vai mostrar isso acontecendo."""

POR_QUE_MUDOU = (
    "o placar saiu do que estava declarado. Sao tres causas possiveis e elas "
    "sao coisas diferentes: (1) uma REGRA do motor mudou -- confira se os "
    "goldens de tests/golden/ tambem mexeram; (2) uma FICHA de content/srd.py "
    "mudou; (3) a POLITICA deste torneio mudou. As tres exigem uma frase no "
    "commit, e nenhuma delas se resolve regravando o numero sem saber qual foi."
)


def ultima_legal(state: CombatState, acoes: tuple[Action, ...]) -> Action:
    """Politica de mentira, para as violacoes abaixo."""
    return acoes[-1]


@pytest.mark.slow
def test_o_duelo_canonico_tem_o_placar_declarado():
    assert placar(range(SEEDS)) == ESPERADO, POR_QUE_MUDOU


@pytest.mark.slow
def test_o_torneio_e_deterministico():
    """As mesmas seeds, duas execucoes, o mesmo placar. Um torneio que variasse
    estaria lendo entropia de fora do estado -- e ai o numero declarado acima
    nao seria uma afirmacao sobre o jogo, mas sobre a sorte daquela rodada."""
    seeds = range(50)
    assert placar(seeds) == placar(seeds)


def test_o_torneio_acusa_uma_ficha_diferente():
    """A violacao que prova que o teste acima nao e decorativo.

    Um `placar` que ignorasse o catalogo, ou um assert de faixa larga demais,
    passariam com a ficha adulterada. Esta e a menor adulteracao possivel:
    **um** ponto de vida."""
    frageis = {
        BRUTAMONTES.id: replace(BRUTAMONTES, max_hp=BRUTAMONTES.max_hp - 1),
        DUELISTA.id: DUELISTA,
    }
    poucas = range(50)
    assert placar(poucas, catalogo=frageis) != placar(poucas)


def test_o_torneio_acusa_uma_politica_diferente():
    """A outra metade: o parametro `politica` chega no combate."""

    # Escolher sempre o ultimo item e escolher EndTurnAction para sempre: o
    # combate nunca termina, e `play_out` para no limite de acoes em vez de
    # pendurar o processo.
    with pytest.raises(CorruptStateError, match="nao terminou"):
        placar(range(20), politica=ultima_legal)


def test_o_placar_soma_o_numero_de_duelos():
    """Um `placar` que perdesse combates pelo caminho passaria nos de cima se
    perdesse os mesmos dos dois lados."""
    p = placar(range(30))
    assert sum(p.vitorias.values()) == 30

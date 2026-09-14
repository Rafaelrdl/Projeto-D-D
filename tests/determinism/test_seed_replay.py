"""As travas de determinismo.

A promessa do projeto e "mesma seed, mesmo resultado". Estes testes sao o que
transforma isso de intencao em contrato verificavel -- e o que vai avisar no
dia em que uma refatoracao inocente trocar a ordem de duas rolagens.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

from tacticore.core.actions import EndTurnAction
from tacticore.core.engine import apply, combat_result, start_combat
from tacticore.core.events import Event
from tacticore.core.model import CombatState
from tacticore.core.results import Applied
from tacticore.core.rng import ScriptedRng, SplitMix64, position
from tacticore.core.serde import dump, events_digest, fingerprint, load
from tacticore.core.testing import (
    make_attack,
    make_duelo,
    make_statblock,
    play_out,
    tape_from_events,
)

FICHA = make_statblock(
    id="lutador",
    armor_class=12,
    max_hp=12,
    attacks=(make_attack(damage="1d6+1"),),
)


def combate(seed: int = 4242) -> tuple[CombatState, tuple[Event, ...]]:
    """Um combate inteiro, da montagem ao ultimo abate."""
    catalogo, gente = make_duelo(ficha_a=FICHA, ficha_b=FICHA)
    abertura = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=seed))
    estado, log = play_out(abertura.state)
    return estado, (*abertura.events, *log)


# --------------------------------------------------------------- replay ----


def test_o_piloto_automatico_termina_o_combate():
    """Se isto falhar, todos os testes abaixo estariam comparando nada."""
    estado, log = combate()
    assert combat_result(estado) is not None
    assert len(log) > 10


def test_mesma_seed_mesmo_estado_e_mesmo_log():
    a_estado, a_log = combate()
    b_estado, b_log = combate()
    assert fingerprint(a_estado) == fingerprint(b_estado)
    assert events_digest(a_log) == events_digest(b_log)


def test_seeds_diferentes_dao_combates_diferentes():
    """Sem isto, um motor que ignorasse a seed passaria no teste de cima."""
    _, a_log = combate(seed=1)
    _, b_log = combate(seed=2)
    assert events_digest(a_log) != events_digest(b_log)


# -------------------------------------------------------- save no meio -----


def test_salvar_no_meio_e_continuar_da_o_mesmo_futuro():
    """A prova de que o RNG ser estado nao e enfeite.

    Com um `random.Random` injetado, este teste seria impossivel de passar: a
    posicao do stream nao estaria no save, e o combate recarregado seguiria
    outro caminho.
    """
    catalogo, gente = make_duelo(ficha_a=FICHA, ficha_b=FICHA)
    abertura = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=77))

    meio = abertura.state
    for _ in range(3):
        resultado = apply(meio, EndTurnAction(actor=meio.turn_order.current))
        assert isinstance(resultado, Applied)
        meio = resultado.state

    direto, log_direto = play_out(meio)
    recarregado, log_recarregado = play_out(load(dump(meio)))

    assert fingerprint(direto) == fingerprint(recarregado)
    assert events_digest(log_direto) == events_digest(log_recarregado)


def test_o_save_no_meio_carrega_a_posicao_do_stream():
    catalogo, gente = make_duelo(ficha_a=FICHA, ficha_b=FICHA)
    abertura = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=77))
    assert position(load(dump(abertura.state)).rng) == position(abertura.state.rng)


# --------------------------------------------------------- fita do log -----


def test_o_log_publica_todos_os_dados_rolados():
    """Prova de completude do log, sem precisar de um segundo redutor.

    Reproduzir o combate com a fita extraida do proprio log tem que devolver o
    log identico. Se algum dado tivesse sido rolado sem aparecer em evento
    nenhum, a fita ficaria curta e a reproducao estouraria com `RngExhausted`
    -- e se sobrasse, a posicao final do RNG denunciaria.
    """
    _, original = combate(seed=31337)
    fita = tape_from_events(original)

    catalogo, gente = make_duelo(ficha_a=FICHA, ficha_b=FICHA)
    abertura = start_combat(statblocks=catalogo, participants=gente, rng=ScriptedRng(script=fita))
    estado, resto = play_out(abertura.state)
    reproduzido = (*abertura.events, *resto)

    assert events_digest(reproduzido) == events_digest(original)
    assert position(estado.rng) == len(fita), "sobrou ou faltou dado na fita"


def test_a_fita_ignora_evento_sem_rolagem():
    """Ela extrai dados, nao eventos: turno, rodada e queda nao entram."""
    _, log = combate(seed=5)
    assert len(tape_from_events(log)) < len(log) * 2


# ------------------------------------------------------- PYTHONHASHSEED ----

_SCRIPT = textwrap.dedent(
    """
    from tacticore.core.engine import start_combat
    from tacticore.core.rng import SplitMix64
    from tacticore.core.serde import events_digest, fingerprint
    from tacticore.core.testing import (
        make_attack, make_duelo, make_statblock, play_out,
    )

    ficha = make_statblock(
        id="lutador", armor_class=12, max_hp=12,
        attacks=(make_attack(damage="1d6+1"),),
    )
    catalogo, gente = make_duelo(ficha_a=ficha, ficha_b=ficha)
    abertura = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=4242))
    estado, log = play_out(abertura.state)
    print(fingerprint(estado), events_digest((*abertura.events, *log)))
    """
)


def test_o_resultado_nao_depende_do_hash_seed():
    """Processos separados, nao so `PYTHONHASHSEED` trocado em memoria.

    A randomizacao de hash e fixada na inicializacao do interpretador: mudar a
    variavel de ambiente dentro do proprio processo nao tem efeito nenhum, e um
    teste que fizesse isso passaria sempre, provando nada. O risco real e
    alguem iterar um `set` ou um `dict` de chaves nao ordenadas em algum ponto
    do motor, e so subprocessos expoem isso.
    """
    saidas = set()
    for semente in ("0", "1", "random"):
        processo = subprocess.run(
            [sys.executable, "-c", _SCRIPT],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": semente, "PATH": ""},
        )
        saida = processo.stdout.strip()
        # Sem esta conferencia, tres saidas vazias dariam um conjunto de
        # tamanho um e o teste passaria provando exatamente nada.
        resumos = saida.split()
        assert len(resumos) == 2, f"saida inesperada do subprocesso: {saida!r}"
        assert all(len(r) == 64 for r in resumos), saida
        saidas.add(saida)

    assert len(saidas) == 1, f"o combate mudou com PYTHONHASHSEED: {saidas}"

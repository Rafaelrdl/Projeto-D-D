"""Montagem do combate: validacao, iniciativa e o primeiro turno."""

from __future__ import annotations

import json

import pytest

from tacticore.core.engine import Participant, start_combat
from tacticore.core.errors import InvalidEncounterError
from tacticore.core.events import InitiativeRolled, RoundStarted, TurnOrderSet, TurnStarted
from tacticore.core.ids import CreatureId, StatblockId
from tacticore.core.rng import ScriptedRng, SplitMix64, position
from tacticore.core.serde import check_invariants, dump, events_to_list, load
from tacticore.core.testing import (
    make_abilities,
    make_duelo,
    make_participant,
    make_statblock,
)

# Fitas curtas e legiveis: um d20 por participante, na ordem lexicografica dos
# ids. Com dois participantes, a fita tem exatamente dois valores.


def test_combate_nasce_em_andamento():
    catalogo, gente = make_duelo()
    resultado = start_combat(
        statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(10, 5))
    )

    estado = resultado.state
    assert estado.turn_order.round_number == 1
    assert estado.turn_order.current in estado.turn_order.order
    assert set(estado.combatants) == {"heroi", "vilao"}
    assert check_invariants(estado) == ()


def test_todo_mundo_entra_com_a_vida_cheia():
    catalogo, gente = make_duelo(ficha_a=make_statblock(id="tanque", max_hp=42))
    resultado = start_combat(
        statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(1, 2))
    )
    heroi = resultado.state.combatants[CreatureId("heroi")]
    assert heroi.hp.current == heroi.hp.maximum == 42


def test_orcamento_inicial_vem_do_deslocamento_da_ficha():
    catalogo, gente = make_duelo(ficha_a=make_statblock(id="veloz", speed_ft=40))
    resultado = start_combat(
        statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(1, 2))
    )
    orcamento = resultado.state.combatants[CreatureId("heroi")].budget
    assert orcamento.action_available is True
    assert orcamento.movement_remaining_ft == 40


# ------------------------------------------------------------ rolagens ------


def test_uma_rolagem_por_participante():
    catalogo, gente = make_duelo()
    resultado = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=1))
    assert position(resultado.state.rng) == 2


def test_as_rolagens_seguem_a_ordem_lexicografica_dos_ids():
    """Percorrer os ids ordenados, e nao a ordem em que foram passados, e o que
    faz o mesmo encontro dar o mesmo resultado com a lista embaralhada."""
    catalogo, gente = make_duelo(a="zora", b="alma")
    resultado = start_combat(
        statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(3, 18))
    )

    rolagens = [e for e in resultado.events if isinstance(e, InitiativeRolled)]
    assert [str(e.creature) for e in rolagens] == ["alma", "zora"]
    assert [e.d20 for e in rolagens] == [3, 18]


def test_lista_embaralhada_da_a_mesma_ordem():
    catalogo, gente = make_duelo()
    a = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=7))
    b = start_combat(
        statblocks=catalogo, participants=tuple(reversed(gente)), rng=SplitMix64(seed=7)
    )
    assert a.state == b.state


def test_a_rolagem_registra_a_conta_e_as_posicoes_do_rng():
    catalogo, gente = make_duelo(
        ficha_a=make_statblock(id="agil", abilities=make_abilities(destreza=16))
    )
    resultado = start_combat(
        statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(11, 4))
    )

    heroi = next(
        e for e in resultado.events if isinstance(e, InitiativeRolled) and e.creature == "heroi"
    )
    assert (heroi.d20, heroi.dex_score, heroi.dex_mod, heroi.total) == (11, 16, 3, 14)
    assert heroi.rng_after == heroi.rng_before + 1


def test_quem_tirou_mais_comeca():
    catalogo, gente = make_duelo(a="alma", b="zora")
    resultado = start_combat(
        statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(2, 19))
    )
    assert resultado.state.turn_order.order == ("zora", "alma")
    assert resultado.state.turn_order.current == "zora"


# -------------------------------------------------------------- eventos -----


def test_a_sequencia_de_eventos_da_abertura():
    catalogo, gente = make_duelo()
    resultado = start_combat(
        statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(10, 5))
    )

    tipos = [type(e) for e in resultado.events]
    assert tipos == [InitiativeRolled, InitiativeRolled, TurnOrderSet, RoundStarted, TurnStarted]


def test_a_ordem_final_e_gravada_no_evento():
    """Gravada e nao recalculada: replay confere o resultado em vez de refazer
    a regra de desempate e testar a mesma coisa duas vezes."""
    catalogo, gente = make_duelo()
    resultado = start_combat(
        statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(10, 5))
    )

    gravada = next(e for e in resultado.events if isinstance(e, TurnOrderSet))
    assert gravada.order == resultado.state.turn_order.order


def test_o_primeiro_turno_abre_com_o_orcamento_cheio():
    catalogo, gente = make_duelo()
    resultado = start_combat(
        statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(10, 5))
    )

    abertura = next(e for e in resultado.events if isinstance(e, TurnStarted))
    assert abertura.creature == resultado.state.turn_order.current
    assert abertura.budget.action_available is True


# ----------------------------------------------------------- validacao ------


def test_combate_de_um_so_e_recusado():
    catalogo, _ = make_duelo()
    with pytest.raises(InvalidEncounterError, match="ao menos 2 participantes"):
        start_combat(
            statblocks=catalogo,
            participants=(make_participant(id="sozinho", statblock_id="ficha_heroi"),),
            rng=ScriptedRng(script=(1,)),
        )


def test_combate_sem_ninguem_e_recusado():
    with pytest.raises(InvalidEncounterError, match="ao menos 2 participantes"):
        start_combat(statblocks={}, participants=(), rng=ScriptedRng(script=()))


def test_time_unico_e_recusado():
    """Sem dois lados, o combate ja nasceria terminado -- e a premissa de que
    `start_combat` sempre devolve combate em andamento seria falsa."""
    catalogo, _ = make_duelo()
    mesma_turma = (
        make_participant(id="a", statblock_id="ficha_heroi", team="herois"),
        make_participant(id="b", statblock_id="ficha_heroi", team="herois"),
    )
    with pytest.raises(InvalidEncounterError, match="ao menos 2 times"):
        start_combat(statblocks=catalogo, participants=mesma_turma, rng=ScriptedRng(script=(1, 2)))


def test_id_repetido_e_recusado():
    catalogo, _ = make_duelo()
    with pytest.raises(InvalidEncounterError, match="id repetido"):
        start_combat(
            statblocks=catalogo,
            participants=(
                make_participant(id="gemeo", statblock_id="ficha_heroi", team="herois"),
                make_participant(id="gemeo", statblock_id="ficha_vilao", team="viloes"),
            ),
            rng=ScriptedRng(script=(1, 2)),
        )


def test_ficha_inexistente_e_recusada():
    catalogo, _ = make_duelo()
    with pytest.raises(InvalidEncounterError, match="ficha inexistente"):
        start_combat(
            statblocks=catalogo,
            participants=(
                make_participant(id="a", statblock_id="ficha_heroi", team="herois"),
                make_participant(id="b", statblock_id="dragao", team="viloes"),
            ),
            rng=ScriptedRng(script=(1, 2)),
        )


def test_ficha_sem_vida_e_recusada():
    fantasma = make_statblock(id="fantasma", max_hp=0)
    catalogo, gente = make_duelo(ficha_b=fantasma)
    with pytest.raises(InvalidEncounterError, match="vida maxima 0"):
        start_combat(statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(1, 2)))


def test_o_erro_junta_todos_os_problemas():
    with pytest.raises(InvalidEncounterError) as capturado:
        start_combat(
            statblocks={},
            participants=(
                Participant(
                    id=CreatureId("so_um"), statblock_id=StatblockId("nenhuma"), team="herois"
                ),
            ),
            rng=ScriptedRng(script=()),
        )
    mensagem = str(capturado.value)
    assert "ao menos 2 participantes" in mensagem
    assert "ficha inexistente" in mensagem
    assert "ao menos 2 times" in mensagem


# ------------------------------------------------------------ serializa -----


def test_o_estado_recem_montado_sobrevive_ao_save():
    catalogo, gente = make_duelo()
    resultado = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=99))
    assert load(dump(resultado.state)) == resultado.state


def test_o_log_da_abertura_e_serializavel():
    """O log inteiro tem que virar JSON: e dele que o golden vai ser feito."""
    catalogo, gente = make_duelo()
    resultado = start_combat(
        statblocks=catalogo, participants=gente, rng=ScriptedRng(script=(10, 5))
    )
    emitido = events_to_list(resultado.events)
    assert json.loads(json.dumps(emitido)) == emitido
    assert [e["kind"] for e in emitido] == [
        "initiative_rolled",
        "initiative_rolled",
        "turn_order_set",
        "round_started",
        "turn_started",
    ]

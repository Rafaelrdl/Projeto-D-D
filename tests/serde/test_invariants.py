"""As invariantes conferidas ao carregar um save.

Cada uma corresponde a um jeito concreto de um JSON adulterado entrar no motor
e reaparecer como confusao muito depois: o turno de alguem que nao esta na
ordem, um combatente apontando para uma ficha que nao existe, HP acima do
maximo. Um teste por invariante, sempre adulterando o save de verdade.
"""

from __future__ import annotations

from typing import Any

import pytest

from tacticore.core.errors import InvalidSaveError
from tacticore.core.serde import check_invariants, dump, load
from tacticore.core.testing import make_combatant, make_statblock, make_state


def envelope_valido() -> dict[str, Any]:
    return dump(
        make_state(
            statblocks=(make_statblock(id="goblin"),),
            combatants=(
                make_combatant(id="goblin_1", statblock_id="goblin"),
                make_combatant(id="goblin_2", statblock_id="goblin"),
            ),
        )
    )


def test_o_save_de_partida_e_coerente():
    """Se este falhar, todos os de baixo passariam pelo motivo errado."""
    assert load(envelope_valido()) is not None
    assert check_invariants(load(envelope_valido())) == ()


def test_ficha_inexistente_e_recusada():
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["statblock_id"] = "dragao"
    with pytest.raises(InvalidSaveError, match="ficha inexistente 'dragao'"):
        load(env)


def test_combatente_sob_chave_errada_e_recusado():
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["id"] = "outro"
    with pytest.raises(InvalidSaveError, match="se diz 'outro'"):
        load(env)


def test_hp_acima_do_maximo_e_recusado():
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["hp"]["current"] = 99
    with pytest.raises(InvalidSaveError, match=r"hp 99 fora de 0\.\.10"):
        load(env)


def test_hp_negativo_e_recusado():
    """O motor satura em zero; HP negativo so chega por save adulterado."""
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["hp"]["current"] = -3
    with pytest.raises(InvalidSaveError, match="fora de"):
        load(env)


def test_movimento_negativo_e_recusado():
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["budget"]["movement_remaining_ft"] = -5
    with pytest.raises(InvalidSaveError, match="movimento negativo"):
        load(env)


def test_ordem_com_id_repetido_e_recusada():
    env = envelope_valido()
    env["state"]["turn_order"]["order"] = ["goblin_1", "goblin_1"]
    with pytest.raises(InvalidSaveError, match="id repetido"):
        load(env)


def test_ordem_que_nao_bate_com_os_combatentes_e_recusada():
    env = envelope_valido()
    env["state"]["turn_order"]["order"] = ["goblin_1"]
    with pytest.raises(InvalidSaveError, match="nao bate com a lista de combatentes"):
        load(env)


def test_turno_de_quem_nao_esta_na_ordem_e_recusado():
    env = envelope_valido()
    env["state"]["turn_order"]["current"] = "ninguem"
    with pytest.raises(InvalidSaveError, match="nao esta na ordem"):
        load(env)


def test_rodada_zero_e_recusada():
    env = envelope_valido()
    env["state"]["turn_order"]["round_number"] = 0
    with pytest.raises(InvalidSaveError, match="a primeira e 1"):
        load(env)


def test_ficha_sob_chave_errada_e_recusada():
    env = envelope_valido()
    env["state"]["statblocks"]["goblin"]["id"] = "orc"
    with pytest.raises(InvalidSaveError, match="ficha sob a chave"):
        load(env)


def test_hp_maximo_zero_e_recusado():
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["hp"] = {"current": 0, "maximum": 0}
    with pytest.raises(InvalidSaveError, match="hp maximo 0"):
        load(env)


def test_o_erro_junta_todos_os_problemas_de_uma_vez():
    """Corrigir save adulterado um erro por vez seria tortura."""
    env = envelope_valido()
    env["state"]["turn_order"]["round_number"] = 0
    env["state"]["turn_order"]["current"] = "ninguem"
    with pytest.raises(InvalidSaveError) as capturado:
        load(env)
    assert "nao esta na ordem" in str(capturado.value)
    assert "a primeira e 1" in str(capturado.value)

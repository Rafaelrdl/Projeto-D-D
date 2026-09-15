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


def test_duas_criaturas_na_mesma_casa_e_recusado():
    """Invariante nova da fatia 2. Sem ela, todo mundo empilha numa casa e
    "adjacente" deixa de querer dizer qualquer coisa."""
    env = envelope_valido()
    env["state"]["combatants"]["goblin_2"]["position"] = env["state"]["combatants"]["goblin_1"][
        "position"
    ]
    with pytest.raises(InvalidSaveError, match=r"a casa \(0, 0\) tem mais de um combatente"):
        load(env)


def test_posicao_com_tipo_errado_e_recusada():
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["position"] = {"x": "0", "y": 0}
    with pytest.raises(InvalidSaveError, match="esperava inteiro"):
        load(env)


def test_posicao_negativa_e_valida():
    """A grade nao tem borda: inventar uma seria inventar regra que a SRD nao tem."""
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["position"] = {"x": -40, "y": -9}
    assert load(env).combatants["goblin_1"].position.x == -40


def test_ataque_de_alcance_curto_demais_e_recusado():
    """Alcance zero nao e "corpo a corpo": e um ataque que nao acerta nada,
    nem a casa ao lado nem a propria. So chega ao motor por save adulterado."""
    env = envelope_valido()
    env["state"]["statblocks"]["goblin"]["attacks"][0]["range_ft"] = 0
    with pytest.raises(InvalidSaveError, match="alcanca 0 pes; o minimo e 5"):
        load(env)


def test_alcance_negativo_e_recusado():
    env = envelope_valido()
    env["state"]["statblocks"]["goblin"]["attacks"][0]["range_ft"] = -5
    with pytest.raises(InvalidSaveError, match="o minimo e 5"):
        load(env)


def test_alcance_de_uma_casa_e_o_minimo_valido():
    env = envelope_valido()
    env["state"]["statblocks"]["goblin"]["attacks"][0]["range_ft"] = 5
    assert load(env) is not None


# ------------------------------------------------- condicoes e alcance -----


def test_condicao_repetida_e_recusada():
    """Tupla aceita repeticao; o estado logico nao. Duas copias de CAIDO mudam
    o fingerprint sem mudar nada do que o motor calcula."""
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["conditions"] = ["CAIDO", "CAIDO"]
    with pytest.raises(InvalidSaveError, match="fora da ordem canonica ou repetidas"):
        load(env)


def test_condicao_desconhecida_e_recusada():
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["conditions"] = ["ENFEITICADO"]
    with pytest.raises(InvalidSaveError, match="condicao desconhecida"):
        load(env)


def test_condicao_com_tipo_errado_e_recusada():
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["conditions"] = [7]
    with pytest.raises(InvalidSaveError, match=r"conditions\[0\]: esperava texto"):
        load(env)


def test_lista_de_condicoes_vazia_e_valida():
    env = envelope_valido()
    env["state"]["combatants"]["goblin_1"]["conditions"] = []
    assert load(env).combatants["goblin_1"].conditions == ()


def test_alcance_longo_menor_que_o_curto_e_recusado():
    """Longo e o limite de fora; menor que o curto nao descreve arma nenhuma."""
    env = envelope_valido()
    env["state"]["statblocks"]["goblin"]["attacks"][0]["long_range_ft"] = 1
    with pytest.raises(InvalidSaveError, match="alcance longo 1 menor que o curto 5"):
        load(env)


def test_alcance_longo_igual_ao_curto_e_valido():
    """E o que toda arma corpo a corpo tem: nao existe "longe" para quem bate
    de perto."""
    env = envelope_valido()
    perfil = env["state"]["statblocks"]["goblin"]["attacks"][0]
    perfil["range_ft"] = perfil["long_range_ft"] = 5
    assert load(env) is not None

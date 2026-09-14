"""O envelope do save e as recusas na hora de abrir.

Save e dado externo: pode ter sido editado a mao, truncado, ou gerado por uma
versao do motor com bug. Cada recusa aqui existe para que o erro apareca na
hora de carregar, e nao tres turnos depois.
"""

from __future__ import annotations

import json

import pytest

from tacticore.core.errors import InvalidSaveError, UnsupportedSchemaVersion
from tacticore.core.model import CombatOutcome, CombatState
from tacticore.core.rng import ALGORITHM, SplitMix64
from tacticore.core.serde import (
    RULES_VERSION,
    SCHEMA_VERSION,
    canonical_json,
    dump,
    dump_combat_outcome,
    fingerprint,
    load,
    load_combat_outcome,
)
from tacticore.core.testing import make_combatant, make_statblock, make_state


def estado() -> CombatState:
    return make_state(
        statblocks=(make_statblock(id="goblin"),),
        combatants=(
            make_combatant(id="goblin_1", statblock_id="goblin", team="inimigos", hp=4),
            make_combatant(id="goblin_2", statblock_id="goblin", team="inimigos"),
        ),
        current="goblin_2",
        round_number=3,
        rng=SplitMix64(seed=2**64 - 1, counter=41),
    )


# ------------------------------------------------------------ envelope ------


def test_envelope_carrega_as_quatro_coisas():
    envelope = dump(estado())
    assert envelope["schema_version"] == SCHEMA_VERSION
    assert envelope["rules_version"] == RULES_VERSION
    assert envelope["rng_algo"] == ALGORITHM
    assert "state" in envelope


def test_ida_e_volta_pelo_texto_json():
    original = estado()
    assert load(json.loads(json.dumps(dump(original)))) == original


def test_seed_de_64_bits_sobrevive_como_texto_decimal():
    """Inteiro de 64 bits estoura a precisao de numero em JavaScript.

    Um dia alguem abre este save num navegador; a seed tem que continuar a
    mesma, e nao arredondada.
    """
    original = estado()
    envelope = json.loads(json.dumps(dump(original)))
    assert envelope["state"]["rng"]["seed"] == str(2**64 - 1)
    assert load(envelope).rng == original.rng


# ------------------------------------------------------------- versoes ------


def test_formato_desconhecido_e_recusado():
    envelope = dump(estado())
    envelope["schema_version"] = SCHEMA_VERSION + 1
    with pytest.raises(UnsupportedSchemaVersion, match="schema_version"):
        load(envelope)


def test_gerador_desconhecido_e_recusado():
    """Formato igual, stream diferente: o combate recarregado divergiria."""
    envelope = dump(estado())
    envelope["rng_algo"] = "mersenne/1"
    with pytest.raises(UnsupportedSchemaVersion, match="mersenne"):
        load(envelope)


def test_versao_de_regras_diferente_ainda_carrega():
    """Recusar tornaria impossivel migrar.

    O save continua descrevendo um estado valido; o que nao pode e carregar em
    silencio sem ninguem ter como saber que o resultado vai divergir -- e para
    isso o campo esta no envelope, onde da para ler antes de chamar `load`.
    """
    envelope = dump(estado())
    envelope["rules_version"] = RULES_VERSION + 7
    assert load(envelope) == estado()


def test_envelope_sem_versao_e_recusado():
    envelope = dump(estado())
    del envelope["schema_version"]
    with pytest.raises(InvalidSaveError, match="falta o campo 'schema_version'"):
        load(envelope)


# -------------------------------------------------- campos malformados ------


def test_booleano_onde_se_espera_inteiro_e_recusado():
    """`bool` e subclasse de `int` em Python; sem a checagem, `true` vira 1."""
    envelope = dump(estado())
    envelope["state"]["combatants"]["goblin_1"]["hp"]["current"] = True
    with pytest.raises(InvalidSaveError, match="esperava inteiro e achei bool"):
        load(envelope)


def test_texto_onde_se_espera_inteiro_e_recusado():
    envelope = dump(estado())
    envelope["state"]["turn_order"]["round_number"] = "3"
    with pytest.raises(InvalidSaveError, match="esperava inteiro e achei str"):
        load(envelope)


def test_campo_faltando_diz_o_caminho():
    envelope = dump(estado())
    del envelope["state"]["combatants"]["goblin_1"]["team"]
    with pytest.raises(InvalidSaveError, match=r"combatants\['goblin_1'\].*falta o campo 'team'"):
        load(envelope)


def test_seed_nao_decimal_e_recusada():
    envelope = dump(estado())
    envelope["state"]["rng"]["seed"] = "abc"
    with pytest.raises(InvalidSaveError, match="nao e um inteiro decimal"):
        load(envelope)


def test_gerador_de_tipo_desconhecido_e_recusado():
    envelope = dump(estado())
    envelope["state"]["rng"] = {"kind": "dados_de_verdade"}
    with pytest.raises(InvalidSaveError, match="gerador desconhecido"):
        load(envelope)


def test_atributo_desconhecido_no_ataque_e_recusado():
    envelope = dump(estado())
    envelope["state"]["statblocks"]["goblin"]["attacks"][0]["ability"] = "MAG"
    with pytest.raises(InvalidSaveError, match="atributo desconhecido"):
        load(envelope)


def test_fita_com_valor_nao_inteiro_e_recusada():
    envelope = dump(make_state())
    envelope["state"]["rng"] = {"kind": "scripted", "script": ["20"], "cursor": 0}
    with pytest.raises(InvalidSaveError, match=r"script\[0\]"):
        load(envelope)


# --------------------------------------------------------- fingerprint ------


def test_estados_iguais_tem_o_mesmo_resumo():
    assert fingerprint(estado()) == fingerprint(estado())


def test_um_ponto_de_vida_de_diferenca_muda_o_resumo():
    outro = make_state(
        statblocks=(make_statblock(id="goblin"),),
        combatants=(
            make_combatant(id="goblin_1", statblock_id="goblin", team="inimigos", hp=5),
            make_combatant(id="goblin_2", statblock_id="goblin", team="inimigos"),
        ),
        current="goblin_2",
        round_number=3,
        rng=SplitMix64(seed=2**64 - 1, counter=41),
    )
    assert fingerprint(outro) != fingerprint(estado())


def test_posicao_do_rng_entra_no_resumo():
    """Duas partidas identicas em HP mas em posicoes diferentes do stream tem
    futuros diferentes, e o resumo precisa dizer isso."""
    a = make_state(rng=SplitMix64(seed=1, counter=0))
    b = make_state(rng=SplitMix64(seed=1, counter=1))
    assert fingerprint(a) != fingerprint(b)


def test_json_canonico_ordena_as_chaves():
    texto = canonical_json({"b": 1, "a": 2})
    assert texto == '{"a":2,"b":1}'


def test_resumo_nao_depende_da_ordem_de_insercao():
    """Dois dicionarios com as mesmas chaves em ordens diferentes sao o mesmo
    estado, e tem que dar o mesmo resumo."""
    assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})


def test_inteiro_onde_se_espera_texto_e_recusado():
    envelope = dump(estado())
    envelope["state"]["combatants"]["goblin_1"]["team"] = 7
    with pytest.raises(InvalidSaveError, match="esperava texto e achei int"):
        load(envelope)


def test_texto_onde_se_espera_booleano_e_recusado():
    envelope = dump(estado())
    envelope["state"]["statblocks"]["goblin"]["attacks"][0]["proficient"] = "sim"
    with pytest.raises(InvalidSaveError, match="esperava booleano e achei str"):
        load(envelope)


def test_lista_onde_se_espera_objeto_e_recusada():
    envelope = dump(estado())
    envelope["state"]["combatants"]["goblin_1"]["hp"] = []
    with pytest.raises(InvalidSaveError, match="esperava objeto e achei list"):
        load(envelope)


def test_objeto_onde_se_espera_lista_e_recusado():
    envelope = dump(estado())
    envelope["state"]["statblocks"]["goblin"]["attacks"] = {}
    with pytest.raises(InvalidSaveError, match="esperava lista e achei dict"):
        load(envelope)


def test_item_de_lista_com_tipo_errado_e_recusado():
    envelope = dump(estado())
    envelope["state"]["statblocks"]["goblin"]["attacks"] = ["cimitarra"]
    with pytest.raises(InvalidSaveError, match=r"attacks\[0\]: esperava objeto e achei str"):
        load(envelope)


def test_ordem_de_iniciativa_com_valor_nao_textual_e_recusada():
    envelope = dump(estado())
    envelope["state"]["turn_order"]["order"] = [1, 2]
    with pytest.raises(InvalidSaveError, match=r"order\[0\]: esperava texto"):
        load(envelope)


def test_vencedor_nulo_sobrevive_ao_json():
    """Aniquilacao mutua e `winning_team: null`, e null tem que voltar como
    `None` e nao como a string "None"."""
    vazio = CombatOutcome(winning_team=None, last_round=3)
    ida = json.loads(json.dumps(dump_combat_outcome(vazio)))
    assert load_combat_outcome(ida, "t") == vazio


def test_vencedor_com_tipo_errado_e_recusado():
    with pytest.raises(InvalidSaveError, match="esperava texto ou nulo"):
        load_combat_outcome({"winning_team": 7, "last_round": 1}, "t")

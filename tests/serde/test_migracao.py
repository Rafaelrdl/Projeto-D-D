"""A migracao de save entre versoes de formato.

Este e o primeiro salto do projeto, e ele existe porque um campo obrigatorio
entrou no estado. Sem migracao, todo save gravado antes da fatia 2 viraria lixo
-- e "lixo" aqui nao e figura de linguagem: `serde._campo` levanta na chave
ausente, com ou sem default no lado do Python.

O que a migracao promete e que o combate **volta a rodar**, e nao que ele volte
a rodar igual: o save v1 nao contem posicao, entao a formacao e inventada. O que
ela nao pode fazer e inventar diferente a cada carga, ou inventar algo que a
propria checagem de invariante recusaria.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tacticore.core.errors import InvalidSaveError, UnsupportedSchemaVersion
from tacticore.core.model import PES_POR_CASA, CombatState
from tacticore.core.rng import ALGORITHM
from tacticore.core.serde import (
    SCHEMA_VERSION,
    SCHEMA_VERSIONS_ACEITAS,
    check_invariants,
    dump,
    dump_state,
    fingerprint,
    load,
)
from tacticore.core.testing import make_combatant, make_statblock, make_state

LEGADO = Path(__file__).parents[1] / "golden" / "data" / "save_legado.json"


def envelope_v1() -> dict[str, Any]:
    """Um save v1 de verdade, o mesmo arquivo congelado do golden."""
    bruto = json.loads(LEGADO.read_text(encoding="utf-8"))
    bruto.pop("final_fingerprint_esperado")
    return bruto


def estado_v2() -> CombatState:
    return make_state(
        statblocks=(make_statblock(id="ficha"),),
        combatants=(
            make_combatant(id="a", statblock_id="ficha", team="herois"),
            make_combatant(id="b", statblock_id="ficha", team="viloes"),
        ),
        posicoes={"a": (2, 3), "b": (-1, 7)},
    )


# ------------------------------------------------------------ versoes ------


def test_o_motor_le_a_versao_atual_e_as_antigas():
    assert SCHEMA_VERSION in SCHEMA_VERSIONS_ACEITAS
    assert tuple(range(1, SCHEMA_VERSION + 1)) == SCHEMA_VERSIONS_ACEITAS


def test_versao_do_futuro_e_recusada():
    """Migrar para tras e impossivel: o save tem campos que este motor nao sabe."""
    envelope = dump(estado_v2())
    envelope["schema_version"] = SCHEMA_VERSION + 1
    with pytest.raises(UnsupportedSchemaVersion, match="este motor le"):
        load(envelope)


def test_versao_zero_e_recusada():
    envelope = envelope_v1()
    envelope["schema_version"] = 0
    with pytest.raises(UnsupportedSchemaVersion):
        load(envelope)


def test_save_da_versao_atual_nao_passa_por_migracao():
    original = estado_v2()
    assert load(dump(original)) == original


# ------------------------------------------------------------- v1 -> v2 ----


def test_o_save_v1_carrega():
    """A garantia inteira: um arquivo gravado antes do campo existir ainda abre."""
    estado = load(envelope_v1())
    assert check_invariants(estado) == ()


def test_a_migracao_inventa_uma_fila_em_ordem_de_id():
    """Deterministica e em ordem lexicografica -- a mesma que `start_combat`
    usa para rolar iniciativa, entao nao ha um segundo criterio para aprender."""
    estado = load(envelope_v1())
    casas = {str(c.id): (c.position.x, c.position.y) for c in estado.combatants.values()}
    assert casas == {"bruto": (0, 0), "lamina": (1, 0)}


def test_a_migracao_respeita_a_invariante_que_ela_mesma_criou():
    """Enfileirar em (0,0) para todos seria mais simples e produziria um save
    que a propria checagem de carga recusa."""
    estado = load(envelope_v1())
    casas = [(c.position.x, c.position.y) for c in estado.combatants.values()]
    assert len(set(casas)) == len(casas)


def test_migrar_duas_vezes_da_o_mesmo_resultado():
    """Sem isto, um save v1 carregado hoje e amanha daria combates diferentes."""
    assert fingerprint(load(envelope_v1())) == fingerprint(load(envelope_v1()))


def test_o_save_migrado_pode_ser_regravado_na_versao_nova():
    """O caminho de saida: carregar v1, salvar v2, e o v2 nao precisa mais migrar."""
    migrado = load(envelope_v1())
    regravado = dump(migrado)
    assert regravado["schema_version"] == SCHEMA_VERSION
    assert load(regravado) == migrado


def test_a_migracao_so_acrescenta_os_campos_que_faltavam():
    """Vida, orcamento, ordem e RNG ficam intactos; entram posicao e alcance."""
    antes = envelope_v1()["state"]
    depois = dump_state(load(envelope_v1()))

    assert depois["turn_order"] == antes["turn_order"]
    assert depois["rng"] == antes["rng"]

    for chave, combatente in depois["combatants"].items():  # type: ignore[union-attr]
        original = antes["combatants"][chave]  # type: ignore[index]
        sem_posicao = {k: v for k, v in combatente.items() if k != "position"}
        assert sem_posicao == original

    for chave, ficha in depois["statblocks"].items():  # type: ignore[union-attr]
        original = antes["statblocks"][chave]  # type: ignore[index]
        sem_ataques = {k: v for k, v in ficha.items() if k != "attacks"}
        assert sem_ataques == {k: v for k, v in original.items() if k != "attacks"}
        for ataque, antigo in zip(ficha["attacks"], original["attacks"], strict=True):
            sem_alcance = {k: v for k, v in ataque.items() if k != "range_ft"}
            assert sem_alcance == antigo


def test_a_migracao_de_alcance_assume_corpo_a_corpo():
    """Cinco pes erra para o lado seguro: um arco migrado vira arma de perto,
    que e obviamente esquisito no log -- em vez de um soco que acerta a trinta
    metros, que ninguem notaria."""
    estado = load(envelope_v1())
    alcances = {a.range_ft for f in estado.statblocks.values() for a in f.attacks}
    assert alcances == {PES_POR_CASA}


def test_save_v1_sem_combatente_nenhum_nao_explode():
    """Caso degenerado: a migracao percorre um dicionario vazio e devolve outro.

    O estado resultante e recusado depois, pela checagem de invariante -- mas
    pela razao certa (ordem de iniciativa vazia), e nao com um IndexError vindo
    de dentro do migrador.
    """
    envelope = envelope_v1()
    envelope["state"]["combatants"] = {}
    with pytest.raises(InvalidSaveError, match="ordem de iniciativa"):
        load(envelope)


def test_o_envelope_v1_continua_com_o_algoritmo_de_rng_conferido():
    """Migracao de formato nao e desculpa para relaxar a checagem do gerador."""
    envelope = envelope_v1()
    envelope["rng_algo"] = "outro/1"
    with pytest.raises(UnsupportedSchemaVersion, match="outro/1"):
        load(envelope)
    assert ALGORITHM != "outro/1"

"""Encontros canonicos congelados.

Cada arquivo em `data/` e o log inteiro de um combate rodado com seed fixa. Um
teste de unidade nao pega a refatoracao que troca a ordem de duas rolagens;
estes pegam todas de uma vez.

Ler `README.md` desta pasta antes de rodar com `--update-golden`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tacticore.core import RULES_VERSION, SCHEMA_VERSION
from tacticore.core.actions import Action, AttackAction, EndTurnAction
from tacticore.core.engine import Participant, apply, combat_result, start_combat
from tacticore.core.events import Event
from tacticore.core.queries import is_standing, statblock_of
from tacticore.core.results import Applied
from tacticore.core.rng import ALGORITHM, SplitMix64
from tacticore.core.serde import canonical_json, events_to_list, fingerprint, load
from tacticore.core.testing import (
    make_abilities,
    make_attack,
    make_participant,
    make_statblock,
    play_out,
)

DADOS = Path(__file__).parent / "data"

BRUTAMONTES = make_statblock(
    id="brutamontes",
    name="Brutamontes",
    abilities=make_abilities(forca=16, destreza=8),
    armor_class=13,
    max_hp=14,
    proficiency_bonus=2,
    speed_ft=30,
    attacks=(make_attack(id="machado", name="Machado", damage="1d12+1"),),
)

DUELISTA = make_statblock(
    id="duelista",
    name="Duelista",
    abilities=make_abilities(forca=10, destreza=17),
    armor_class=15,
    max_hp=11,
    proficiency_bonus=3,
    speed_ft=35,
    attacks=(make_attack(id="estoque", name="Estoque", damage="1d8+1d4"),),
)

CATALOGO = {BRUTAMONTES.id: BRUTAMONTES, DUELISTA.id: DUELISTA}

# Os tres cobrem coisas diferentes: um duelo desigual, dois iguais (que
# exercitam o desempate de iniciativa) e um dois-contra-dois.
ENCONTROS: list[tuple[str, int, tuple[Participant, ...]]] = [
    (
        "duelo",
        20250914,
        (
            make_participant(id="bruto", statblock_id="brutamontes", team="herois"),
            make_participant(id="lamina", statblock_id="duelista", team="viloes"),
        ),
    ),
    (
        "gemeos",
        7,
        (
            make_participant(id="gemeo_a", statblock_id="duelista", team="herois"),
            make_participant(id="gemeo_b", statblock_id="duelista", team="viloes"),
        ),
    ),
    (
        "dois_contra_dois",
        31337,
        (
            make_participant(id="bruto_1", statblock_id="brutamontes", team="herois"),
            make_participant(id="lamina_1", statblock_id="duelista", team="herois"),
            make_participant(id="bruto_2", statblock_id="brutamontes", team="viloes"),
            make_participant(id="lamina_2", statblock_id="duelista", team="viloes"),
        ),
    ),
]
IDS = [nome for nome, _, _ in ENCONTROS]

VANTAGEM_SEED = 991


def envelope_de(seed: int, resumo: str, log: tuple[Event, ...]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "rules_version": RULES_VERSION,
        "rng_algo": ALGORITHM,
        "seed": str(seed),
        "final_fingerprint": resumo,
        "events": events_to_list(log),
    }


def gravar_ou_comparar(nome: str, atual: dict[str, Any], *, update_golden: bool) -> None:
    arquivo = DADOS / f"{nome}.json"
    if update_golden:
        arquivo.write_text(
            json.dumps(atual, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        pytest.skip(f"golden {nome} regravado")

    assert arquivo.is_file(), f"golden ausente; rode com --update-golden para criar {arquivo}"
    esperado = json.loads(arquivo.read_text(encoding="utf-8"))

    assert esperado["rules_version"] == RULES_VERSION, (
        "o golden foi gravado com outra versao de regras. Se a mudanca foi "
        "intencional, regrave e diga no commit qual regra mudou e por que."
    )
    assert canonical_json(atual) == canonical_json(esperado)


def rodar(seed: int, participantes: tuple[Participant, ...]) -> tuple[str, tuple[Event, ...]]:
    abertura = start_combat(
        statblocks=CATALOGO,
        participants=participantes,
        rng=SplitMix64(seed=seed),
    )
    estado, resto = play_out(abertura.state)
    return fingerprint(estado), (*abertura.events, *resto)


def rodar_com_vantagem(seed: int) -> tuple[str, tuple[Event, ...]]:
    """Um combate onde os ataques declaram vantagem e desvantagem.

    O piloto automatico nunca declara fonte nenhuma, entao os outros goldens
    exercitam apenas `NORMAL` -- e uma mudanca no desempate da vantagem passaria
    por eles sem ser vista. Aqui a rodada impar da vantagem e a par da
    desvantagem, de modo que os dois estados aparecem no mesmo log.
    """
    participantes = (
        make_participant(id="atacante", statblock_id="brutamontes", team="herois"),
        make_participant(id="defensor", statblock_id="duelista", team="viloes"),
    )
    abertura = start_combat(
        statblocks=CATALOGO, participants=participantes, rng=SplitMix64(seed=seed)
    )
    estado = abertura.state
    log: list[Event] = list(abertura.events)

    for _ in range(200):
        if combat_result(estado) is not None:
            break

        ator = estado.combatants[estado.turn_order.current]
        inimigos = sorted(
            (c.id for c in estado.combatants.values() if c.team != ator.team and is_standing(c)),
            key=str,
        )

        acao: Action
        if ator.budget.action_available and inimigos:
            impar = estado.turn_order.round_number % 2 == 1
            acao = AttackAction(
                actor=ator.id,
                target=inimigos[0],
                attack_id=statblock_of(estado, ator.id).attacks[0].id,
                advantage_sources=("flanqueando",) if impar else (),
                disadvantage_sources=() if impar else ("cegado",),
            )
        else:
            acao = EndTurnAction(actor=ator.id)

        resultado = apply(estado, acao)
        assert isinstance(resultado, Applied), resultado
        estado = resultado.state
        log.extend(resultado.events)

    return fingerprint(estado), tuple(log)


@pytest.mark.parametrize(("nome", "seed", "participantes"), ENCONTROS, ids=IDS)
def test_encontro_canonico(
    nome: str,
    seed: int,
    participantes: tuple[Participant, ...],
    update_golden: bool,
):
    resumo, log = rodar(seed, participantes)
    gravar_ou_comparar(nome, envelope_de(seed, resumo, log), update_golden=update_golden)


def test_encontro_com_vantagem(update_golden: bool):
    resumo, log = rodar_com_vantagem(VANTAGEM_SEED)
    gravar_ou_comparar(
        "vantagem", envelope_de(VANTAGEM_SEED, resumo, log), update_golden=update_golden
    )


def test_o_golden_de_vantagem_exercita_os_dois_estados():
    """Sem isto, o golden acima poderia virar mais um combate NORMAL em
    silencio, e a lacuna que ele existe para tapar voltaria sozinha."""
    gravado = json.loads((DADOS / "vantagem.json").read_text(encoding="utf-8"))
    estados = {e["advantage"] for e in gravado["events"] if e["kind"] == "attack_rolled"}
    assert estados == {"ADVANTAGE", "DISADVANTAGE"}


def test_os_goldens_nao_sao_todos_iguais():
    """Encontros que dessem o mesmo log nao provariam nada."""
    resumos = {
        json.loads((DADOS / f"{nome}.json").read_text(encoding="utf-8"))["final_fingerprint"]
        for nome in [*IDS, "vantagem"]
    }
    assert len(resumos) == len(IDS) + 1


def test_o_save_legado_ainda_carrega():
    """Compatibilidade de formato, e nao golden.

    Este arquivo NAO e regravado por `--update-golden`. Se ele parar de
    carregar, isso e uma quebra de save, e a correcao e um caminho de migracao
    -- nao apagar o arquivo.
    """
    envelope = json.loads((DADOS / "save_legado.json").read_text(encoding="utf-8"))
    esperado = envelope.pop("final_fingerprint_esperado")
    assert fingerprint(load(envelope)) == esperado

"""Encontros canonicos congelados.

Cada arquivo em `data/` e o log inteiro de um combate rodado com seed fixa. Um
teste de unidade nao pega a refatoracao que troca a ordem de duas rolagens;
estes pegam todas de uma vez.

Ler `README.md` desta pasta antes de rodar com `--update-golden`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from tacticore.content.arcanista import ARCANISTA, RAIO_DE_FOGO
from tacticore.content.srd import BRUTAMONTES, CATALOGO
from tacticore.core import RULES_VERSION, SCHEMA_VERSION
from tacticore.core.actions import Action, AttackAction, EndTurnAction, ShoveAction
from tacticore.core.engine import Participant, apply, combat_result, start_combat
from tacticore.core.enums import Condition
from tacticore.core.events import ContestRolled, Event
from tacticore.core.ids import AttackId, CreatureId, StatblockId
from tacticore.core.model import PES_POR_CASA, CombatState, Statblock
from tacticore.core.queries import is_conscious, statblock_of
from tacticore.core.results import Applied
from tacticore.core.rng import ALGORITHM, ScriptedRng, SplitMix64
from tacticore.core.serde import (
    canonical_json,
    check_invariants,
    events_to_list,
    fingerprint,
    load,
)
from tacticore.core.testing import (
    Politica,
    make_participant,
    play_out,
    primeira_legal,
    tape_from_events,
)

DADOS = Path(__file__).parent / "data"

# Os tres cobrem coisas diferentes: um duelo desigual, dois iguais (que
# exercitam o desempate de iniciativa) e um dois-contra-dois.
ENCONTROS: list[tuple[str, int, tuple[Participant, ...]]] = [
    (
        "duelo",
        20250914,
        (
            make_participant(
                id="bruto", statblock_id="brutamontes", team="herois", position=(0, 0)
            ),
            make_participant(id="lamina", statblock_id="duelista", team="viloes", position=(4, 0)),
        ),
    ),
    (
        "gemeos",
        7,
        (
            make_participant(id="gemeo_a", statblock_id="duelista", team="herois", position=(0, 0)),
            make_participant(id="gemeo_b", statblock_id="duelista", team="viloes", position=(4, 0)),
        ),
    ),
    (
        "dois_contra_dois",
        31337,
        (
            # Duas linhas de frente, uma de cada lado.
            make_participant(
                id="bruto_1", statblock_id="brutamontes", team="herois", position=(0, 0)
            ),
            make_participant(
                id="lamina_1", statblock_id="duelista", team="herois", position=(0, 1)
            ),
            make_participant(
                id="bruto_2", statblock_id="brutamontes", team="viloes", position=(4, 0)
            ),
            make_participant(
                id="lamina_2", statblock_id="duelista", team="viloes", position=(4, 1)
            ),
        ),
    ),
]
IDS = [nome for nome, _, _ in ENCONTROS]

VANTAGEM_SEED = 991
CAIDO_SEED = 4
"""Escolhida para o encontro acontecer, como a do tiro colado."""

TIRO_COLADO_SEED = 5
"""Escolhida para o encontro acontecer.

A primeira que tentei matava a atiradora na rodada 1, antes de ela atirar --
e o golden ficava verde sem exercitar nada. Foi o teste-guarda logo abaixo
que cobrou. Escolher seed para o combate ACONTECER e legitimo; escolher seed
ate um ramo raro de regra cair e que seria contorcer o golden para fazer o
trabalho de um teste de unidade."""
ADAGA = AttackId("adaga")


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

    assert canonical_json(atual) == canonical_json(esperado), _diagnostico(nome, esperado)


def _diagnostico(nome: str, esperado: dict[str, Any]) -> str:
    """Classifica a divergencia antes de mandar o dono explicar qual regra mudou.

    A mensagem antiga cobrava sempre uma frase sobre REGRA. Na etapa 2 a maioria
    dos diffs de golden vem de mudanca de FORMATO -- campo novo no estado, que
    mexe no `final_fingerprint` sem o motor calcular nada diferente -- e essa
    frase e impossivel de escrever com honestidade. Mandar escrever mentira e um
    jeito eficiente de ensinar a ignorar a mensagem.
    """
    regra_mudou = esperado.get("rules_version") != RULES_VERSION
    formato_mudou = esperado.get("schema_version") != SCHEMA_VERSION

    if regra_mudou:
        return (
            f"golden {nome}: mudanca de REGRA "
            f"(rules_version {esperado.get('rules_version')} -> {RULES_VERSION}). "
            "Regrave com --update-golden e diga no commit qual regra mudou e por que."
        )
    if formato_mudou:
        return (
            f"golden {nome}: mudanca de FORMATO "
            f"(schema_version {esperado.get('schema_version')} -> {SCHEMA_VERSION}), "
            "com as regras iguais. Regrave e cite a migracao no commit; nao invente "
            "uma regra que mudou."
        )
    return (
        f"golden {nome}: o log divergiu sem que rules_version nem schema_version "
        "mudassem. Isto e regressao ate prova em contrario -- confira o diff antes "
        "de pensar em regravar."
    )


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
        # Colados: este golden e sobre vantagem, e nao sobre andar. O laco
        # abaixo ataca sem consultar `legal_actions`, entao comecar longe o
        # transformaria num teste de OUT_OF_RANGE.
        make_participant(id="atacante", statblock_id="brutamontes", team="herois", position=(0, 0)),
        make_participant(id="defensor", statblock_id="duelista", team="viloes", position=(1, 0)),
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
            (c.id for c in estado.combatants.values() if c.team != ator.team and is_conscious(c)),
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


def rodar_com_tiro_colado(seed: int) -> tuple[str, tuple[Event, ...]]:
    """Um combate onde a atiradora insiste na adaga com o inimigo colado.

    O piloto automatico nunca faz isso: `legal_actions` oferece o estoque
    primeiro, e de perto ele e melhor. Este golden existe porque a regra de
    "atirar colado da desvantagem" nao aparece em nenhum dos outros quatro --
    e regra sem golden e regra que uma refatoracao de ordem de rolagem pode
    deslocar sem ninguem ver.
    """
    participantes = (
        make_participant(id="atiradora", statblock_id="duelista", team="herois", position=(0, 0)),
        make_participant(id="alvo", statblock_id="brutamontes", team="viloes", position=(1, 0)),
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
            (c.id for c in estado.combatants.values() if c.team != ator.team and is_conscious(c)),
            key=str,
        )

        acao: Action
        if ator.budget.action_available and inimigos:
            ficha = statblock_of(estado, ator.id)
            arma = ADAGA if any(a.id == ADAGA for a in ficha.attacks) else ficha.attacks[0].id
            acao = AttackAction(actor=ator.id, target=inimigos[0], attack_id=arma)
        else:
            acao = EndTurnAction(actor=ator.id)

        resultado = apply(estado, acao)
        assert isinstance(resultado, Applied), resultado
        estado = resultado.state
        log.extend(resultado.events)

    return fingerprint(estado), tuple(log)


def rodar_com_caido(seed: int) -> tuple[str, tuple[Event, ...]]:
    """Um combate que comeca com alguem no chao.

    Diferente de `vantagem` e `tiro_colado`, este usa o **piloto automatico**:
    `StandUpAction` esta no menu, entao o caido se levanta sozinho e o ciclo
    inteiro -- condicao aplicada pelo encontro, efeito na rolagem, remocao pela
    acao -- sai de `legal_actions` sem ninguem escrever o laco.

    E a diferenca entre uma mecanica que o motor JOGA e uma que ele so sabe
    representar.
    """
    participantes = (
        make_participant(
            id="derrubado",
            statblock_id="duelista",
            team="herois",
            position=(0, 0),
            conditions=(Condition.CAIDO,),
        ),
        make_participant(
            id="brutamontes", statblock_id="brutamontes", team="viloes", position=(1, 0)
        ),
    )
    abertura = start_combat(
        statblocks=CATALOGO, participants=participantes, rng=SplitMix64(seed=seed)
    )
    estado, resto = play_out(abertura.state)
    return fingerprint(estado), (*abertura.events, *resto)


def test_encontro_com_caido(update_golden: bool):
    resumo, log = rodar_com_caido(CAIDO_SEED)
    gravar_ou_comparar("caido", envelope_de(CAIDO_SEED, resumo, log), update_golden=update_golden)


def test_o_golden_do_caido_exercita_o_ciclo_inteiro():
    """Aplicada, com efeito na rolagem, e removida -- tudo no mesmo log.

    Sem isto, o golden poderia virar um combate comum em silencio no dia em que
    `StandUpAction` saisse do menu ou a condicao parasse de derivar fonte.
    """
    gravado = json.loads((DADOS / "caido.json").read_text(encoding="utf-8"))
    tipos = {e["kind"] for e in gravado["events"]}
    assert "stood_up" in tipos, "o caido se levanta sozinho"

    fontes = {
        f
        for e in gravado["events"]
        if e["kind"] == "attack_rolled"
        for f in (*e["advantage_sources"], *e["disadvantage_sources"])
    }
    assert "atacante caido" in fontes or "alvo caido, e eu estou colado" in fontes


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


def test_encontro_com_tiro_colado(update_golden: bool):
    resumo, log = rodar_com_tiro_colado(TIRO_COLADO_SEED)
    gravar_ou_comparar(
        "tiro_colado",
        envelope_de(TIRO_COLADO_SEED, resumo, log),
        update_golden=update_golden,
    )


def test_o_golden_de_tiro_colado_exercita_a_desvantagem_derivada():
    """Sem isto, o golden acima poderia virar mais um combate NORMAL em
    silencio -- exatamente o que aconteceu com os tres primeiros antes de o
    golden de vantagem existir."""
    gravado = json.loads((DADOS / "tiro_colado.json").read_text(encoding="utf-8"))
    derivadas = {
        fonte
        for e in gravado["events"]
        if e["kind"] == "attack_rolled"
        for fonte in e["disadvantage_sources"]
    }
    assert derivadas == {"inimigo adjacente"}


def test_o_golden_de_vantagem_exercita_os_dois_estados():
    """Sem isto, o golden acima poderia virar mais um combate NORMAL em
    silencio, e a lacuna que ele existe para tapar voltaria sozinha."""
    gravado = json.loads((DADOS / "vantagem.json").read_text(encoding="utf-8"))
    estados = {e["advantage"] for e in gravado["events"] if e["kind"] == "attack_rolled"}
    assert estados == {"ADVANTAGE", "DISADVANTAGE"}


# ------------------------------------------------------- o arcanista -------

ARCANISTA_SEED = 4
"""Escolhida para o encontro ACONTECER, como as duas acima.

Quatro tiros, tres acertos e um erro -- o erro importa porque e ele que prova,
dentro do arquivo, que errar nao rola dano. E o bruto fecha 24 -> 18 -> 12 -> 6
sem nunca encostar.
"""

CATALOGO_DO_ARCANISTA: Mapping[StatblockId, Statblock] = {
    ARCANISTA.id: ARCANISTA,
    BRUTAMONTES.id: BRUTAMONTES,
}
"""Montado aqui, e nao no `CATALOGO` global.

E o motivo inteiro de `content/arcanista.py` existir: a ficha dentro do
catalogo global entraria no estado de TODO encontro, e os seis goldens acima
mudariam de fingerprint sem nenhuma regra ter mudado. O molde e o mesmo de
`rodar_com_vantagem`, que ja monta os proprios participantes -- aqui monta-se
tambem o proprio catalogo.
"""

ALCANCE_DO_RAIO_EM_CASAS = RAIO_DE_FOGO.range_ft // PES_POR_CASA
"""A borda exata do alcance: 24 casas, 120 pes. Derivado do campo, para o
golden nascer na borda mesmo que o alcance mude um dia."""

MAGO = CreatureId("mago")


def so_atira(state: CombatState, acoes: tuple[Action, ...]) -> Action:
    """Politica propria: o mago atira e fica parado; o bruto joga sozinho.

    Nao e IA e nao tenta ser -- e o minimo que faz esta ficha aparecer. Com
    `primeira_legal` dos dois lados o mago gasta o movimento fechando distancia
    com o machado, porque `_casa_canonica` so oferece a casa que APROXIMA e
    neste motor nao existe recuo. Medido nesta seed: o mago anda duas vezes e
    o combate vira outro `tiro_colado`.

    Congelar os DOIS lados seria pior: o bruto viraria estatua e o log deixaria
    de ter adversario. So o mago tem politica.
    """
    if state.turn_order.current != MAGO:
        return primeira_legal(state, acoes)
    for acao in acoes:
        if isinstance(acao, AttackAction):
            return acao
    return EndTurnAction(actor=MAGO)


def rodar_arcanista(seed: int, *, politica: Politica = so_atira) -> tuple[str, tuple[Event, ...]]:
    """Um combate a 120 pes: a primeira ficha de artilharia do projeto.

    Sem laco a mao. `rodar_com_vantagem` e `rodar_com_tiro_colado` escrevem o
    proprio `for` porque precisavam de acoes que `legal_actions` nao oferece;
    aqui o tiro de 120 pes ESTA no menu, entao o molde certo e o da fatia A --
    `play_out` com uma `Politica` nomeada -- e o laco unico continua unico.
    """
    participantes = (
        make_participant(id="mago", statblock_id="arcanista", team="herois", position=(0, 0)),
        make_participant(
            id="bruto",
            statblock_id="brutamontes",
            team="viloes",
            position=(ALCANCE_DO_RAIO_EM_CASAS, 0),
        ),
    )
    abertura = start_combat(
        statblocks=CATALOGO_DO_ARCANISTA,
        participants=participantes,
        rng=SplitMix64(seed=seed),
    )
    estado, resto = play_out(abertura.state, politica=politica)
    return fingerprint(estado), (*abertura.events, *resto)


def test_encontro_do_arcanista(update_golden: bool):
    resumo, log = rodar_arcanista(ARCANISTA_SEED)
    gravar_ou_comparar(
        "arcanista", envelope_de(ARCANISTA_SEED, resumo, log), update_golden=update_golden
    )


def test_o_golden_do_arcanista_exercita_o_truque():
    """As duas metades da regra do truque, lidas do arquivo congelado.

    Sem isto o golden viraria mais um combate comum em silencio -- a mesma
    lacuna que os goldens de vantagem e de tiro colado ja cobram.
    """
    gravado = json.loads((DADOS / "arcanista.json").read_text(encoding="utf-8"))

    tiros = [e for e in gravado["events"] if e["kind"] == "attack_rolled" and e["actor"] == "mago"]
    assert tiros, "o arcanista precisa ter atirado"
    assert {e["attack_id"] for e in tiros} == {"raio_de_fogo"}
    assert {e["ability_mod"] for e in tiros} == {3}, "INT entra no ACERTO"

    danos = [e for e in gravado["events"] if e["kind"] == "damage_rolled" and e["actor"] == "mago"]
    assert danos, "sem acerto nenhum o arquivo nao provaria o dano"
    assert {e["roll"]["ability_bonus"] for e in danos} == {0}, "e nao entra no DANO"


def test_o_golden_do_arcanista_e_artilharia_e_nao_outro_tiro_colado():
    """O mago nao arreda pe e o bruto fecha distancia: e esse o combate.

    A asercao que carrega o peso e a do movimento, e ela e sobre a POLITICA:
    trocar `so_atira` por `primeira_legal` faz o mago andar (medido nesta seed:
    duas vezes) e dois tercos do log passam a ser sobre `_casa_canonica`, com o
    arquivo regravado e nenhum outro teste reclamando.
    """
    gravado = json.loads((DADOS / "arcanista.json").read_text(encoding="utf-8"))

    andou = [e for e in gravado["events"] if e["kind"] == "movement_spent"]
    assert not [e for e in andou if e["creature"] == "mago"], (
        "o arcanista atira parado; se ele anda, o golden virou sobre _casa_canonica"
    )
    assert [e for e in andou if e["creature"] == "bruto"], "e o bruto fecha distancia"

    fontes = {
        f
        for e in gravado["events"]
        if e["kind"] == "attack_rolled" and e["actor"] == "mago"
        for f in e["disadvantage_sources"]
    }
    assert fontes == set(), "nenhum tiro colado: isso e o que tiro_colado.json ja cobre"


# --------------------------------------------------------- o empurrao ------

EMPURRAO_SEED = 94
"""Escolhida para o encontro ACONTECER, como as tres acima.

Ela traz os TRES desfechos da disputa no mesmo log -- derruba, empate, resiste
-- e as tres fontes geometricas que estar caido produz. Varridas 400 seeds, so
14 dao os tres desfechos junto com vantagem e desvantagem derivadas, e duas
dessas 14 trazem tambem "alvo caido, e eu estou longe".
"""

EMPURRADOR = CreatureId("empurrador")


def empurra_se_der(state: CombatState, acoes: tuple[Action, ...]) -> Action:
    """Politica propria: o empurrador prefere derrubar; os outros dois jogam sozinhos.

    Nao e IA e nao tenta ser -- e o minimo que faz a mecanica aparecer. Empurrar
    e jogada DOMINADA no recorte de hoje (ver o docstring de `ShoveAction`),
    entao `primeira_legal` o oferece e nunca o escolhe: medido, zero vezes nos
    quatro goldens automaticos.

    Congela so o lado do empurrador. O atirador e o alvo continuam no piloto, e
    e deles que vem o resto do combate -- inclusive o levantar-se, que nenhuma
    politica precisa pedir.
    """
    if state.turn_order.current != EMPURRADOR:
        return primeira_legal(state, acoes)
    for acao in acoes:
        if isinstance(acao, ShoveAction):
            return acao
    return primeira_legal(state, acoes)


def rodar_com_empurrao(
    seed: int, *, politica: Politica = empurra_se_der
) -> tuple[str, tuple[Event, ...]]:
    """TRES combatentes, e nao um duelo. Isso e medida, nao gosto.

    Num duelo a vitima levanta SEMPRE no proprio turno -- levantar custa
    movimento e a acao dela ja foi gasta atacando --, entao quando o empurrador
    volta a agir nao ha mais ninguem no chao. Medido em 300 duelos: 621 quedas,
    e a fonte de vantagem "alvo caido, e eu estou colado" aparece em ZERO delas.
    Um golden em forma de duelo congelaria metade da regra que
    `test_a_regra_do_caido_e_GEOMETRIA_e_nao_tipo_de_arma` protege.

    Com um atirador que age entre o empurrador e o alvo, as tres fontes cabem
    no mesmo log.
    """
    participantes = (
        make_participant(
            id="empurrador", statblock_id="brutamontes", team="herois", position=(0, 0)
        ),
        make_participant(id="atirador", statblock_id="duelista", team="herois", position=(0, 4)),
        make_participant(id="alvo", statblock_id="duelista", team="viloes", position=(1, 0)),
    )
    abertura = start_combat(
        statblocks=CATALOGO, participants=participantes, rng=SplitMix64(seed=seed)
    )
    estado, resto = play_out(abertura.state, politica=politica)
    return fingerprint(estado), (*abertura.events, *resto)


def test_encontro_com_empurrao(update_golden: bool):
    resumo, log = rodar_com_empurrao(EMPURRAO_SEED)
    gravar_ou_comparar(
        "empurrao", envelope_de(EMPURRAO_SEED, resumo, log), update_golden=update_golden
    )


def test_o_golden_do_empurrao_exercita_os_TRES_desfechos():
    """Sem isto, o golden viraria mais um combate comum em silencio.

    O empate e o que mais precisa: o motor o trata igual a derrota, entao
    nenhum teste de EFEITO os distingue. Esta asercao e a frase propria do
    narrador sao as duas unicas coisas que seguram `ContestOutcome.TIE`
    existindo.
    """
    gravado = json.loads((DADOS / "empurrao.json").read_text(encoding="utf-8"))
    disputas = [e for e in gravado["events"] if e["kind"] == "contest_rolled"]
    assert {e["outcome"] for e in disputas} == {"SUCCESS", "TIE", "FAILURE"}


def test_o_golden_do_empurrao_congela_o_quadro_de_quatro_dados():
    """O item 6 do contrato, conferido de fora, no arquivo.

    Dois d20 por lado, sempre, qualquer que seja o desfecho: se o consumo
    dependesse de quem ganhou, o primeiro empate deslocaria todo o resto.
    """
    gravado = json.loads((DADOS / "empurrao.json").read_text(encoding="utf-8"))
    disputas = [e for e in gravado["events"] if e["kind"] == "contest_rolled"]
    assert disputas, "o golden precisa ter pelo menos uma disputa"
    assert {e["rng_after"] - e["rng_before"] for e in disputas} == {4}
    for e in disputas:
        assert len(e["actor_pair"]) == len(e["target_pair"]) == 2


def test_o_golden_do_empurrao_mostra_o_CICLO_inteiro_da_condicao():
    """Derrubar, sofrer por estar no chao, e levantar.

    A queda sozinha nao prova nada: o que interessa e que estar caido MUDE uma
    rolagem seguinte, e que a condicao saia depois. Sao as duas metades da
    regra geometrica do caido, e num duelo a primeira nunca aparece.
    """
    gravado = json.loads((DADOS / "empurrao.json").read_text(encoding="utf-8"))
    tipos = [e["kind"] for e in gravado["events"]]
    assert "knocked_prone" in tipos
    assert "stood_up" in tipos

    vantagens = {
        f for e in gravado["events"] if e["kind"] == "attack_rolled" for f in e["advantage_sources"]
    }
    desvantagens = {
        f
        for e in gravado["events"]
        if e["kind"] == "attack_rolled"
        for f in e["disadvantage_sources"]
    }
    assert "alvo caido, e eu estou colado" in vantagens, "quem bate de perto ganha vantagem"
    assert "atacante caido" in desvantagens, "e quem esta no chao ataca pior"


def test_o_golden_do_empurrao_se_reproduz_pela_propria_fita():
    """A trava contra `ContestRolled` no ramo "nao rola dado" de
    `tape_from_events` -- o erro que compila, passa no mypy e fica verde na
    suite inteira ate o primeiro combate com empurrao."""
    _, log = rodar_com_empurrao(EMPURRAO_SEED)
    fita = tape_from_events(log)

    disputas = sum(1 for e in log if isinstance(e, ContestRolled))
    assert disputas >= 3, "o golden tem tres desfechos, entao tem ao menos tres disputas"

    participantes = (
        make_participant(
            id="empurrador", statblock_id="brutamontes", team="herois", position=(0, 0)
        ),
        make_participant(id="atirador", statblock_id="duelista", team="herois", position=(0, 4)),
        make_participant(id="alvo", statblock_id="duelista", team="viloes", position=(1, 0)),
    )
    abertura = start_combat(
        statblocks=CATALOGO, participants=participantes, rng=ScriptedRng(script=fita)
    )
    _, resto = play_out(abertura.state, politica=empurra_se_der)
    assert events_to_list((*abertura.events, *resto)) == events_to_list(log)


def test_os_goldens_nao_sao_todos_iguais():
    """Encontros que dessem o mesmo log nao provariam nada."""
    nomes = [*IDS, "vantagem", "tiro_colado", "caido", "arcanista", "empurrao"]
    resumos = {
        json.loads((DADOS / f"{nome}.json").read_text(encoding="utf-8"))["final_fingerprint"]
        for nome in nomes
    }
    assert len(resumos) == len(nomes)


def _save_legado() -> tuple[dict[str, Any], str]:
    """O envelope congelado e o fingerprint que ele prometia, separados.

    Este arquivo NAO e regravado por `--update-golden`.
    """
    envelope = json.loads((DADOS / "save_legado.json").read_text(encoding="utf-8"))
    return envelope, envelope.pop("final_fingerprint_esperado")


def test_o_save_legado_ainda_carrega():
    """GARANTIA PERMANENTE, nunca relaxada: um save gravado no formato v1
    continua carregando e continua descrevendo um estado coerente.

    Se este parar de passar, a correcao e um caminho de migracao. Nao e
    regravar o arquivo, e nao e apagar o teste.
    """
    envelope, _ = _save_legado()
    estado = load(envelope)
    assert check_invariants(estado) == ()


def test_o_fingerprint_do_save_legado_e_este():
    """PIN DE FORMATO, e nao garantia.

    Separado do teste acima de proposito: este aqui **vai** falhar toda vez que
    um campo novo entrar no estado, porque o fingerprint cobre o estado inteiro.
    Quando isso acontecer, o valor e recalculado a mao e o commit cita a
    migracao que o justifica. Fundir os dois num assert so faria a garantia
    permanente ser relaxada junto, sem ninguem perceber.
    """
    envelope, esperado = _save_legado()
    assert fingerprint(load(envelope)) == esperado, (
        "--update-golden NAO regrava este arquivo: ele e o unico de tests/golden/data/ "
        "que se edita a mao. Rodar o botao de regravar deixa esta falha de pe, e e "
        "para deixar mesmo."
    )


# ------------------------------------------------- diagnostico da falha -----
# A trava so vale se souber classificar. Estes tres provam que ela dispara com
# a mensagem certa em cada caso -- sem eles, ela seria uma string bonita que
# ninguem nunca viu.


def test_diagnostico_de_mudanca_de_regra():
    velho = {"rules_version": RULES_VERSION - 1, "schema_version": SCHEMA_VERSION}
    mensagem = _diagnostico("duelo", velho)
    assert "REGRA" in mensagem
    assert "qual regra mudou" in mensagem


def test_diagnostico_de_mudanca_de_formato():
    """Regras iguais, formato diferente: o caso comum da etapa 2."""
    velho = {"rules_version": RULES_VERSION, "schema_version": SCHEMA_VERSION - 1}
    mensagem = _diagnostico("duelo", velho)
    assert "FORMATO" in mensagem
    assert "nao invente" in mensagem
    assert "REGRA" not in mensagem


def test_diagnostico_de_regressao_pura():
    """Nada de versao mudou e o log divergiu: ate prova em contrario, e bug."""
    igual = {"rules_version": RULES_VERSION, "schema_version": SCHEMA_VERSION}
    mensagem = _diagnostico("duelo", igual)
    assert "regressao" in mensagem


def test_regra_e_formato_juntos_reportam_regra():
    """Quando os dois mudam, o que importa e a regra: mudanca de resultado e a
    mais grave, e quem le precisa ver isso primeiro."""
    velho = {"rules_version": RULES_VERSION - 1, "schema_version": SCHEMA_VERSION - 1}
    assert "REGRA" in _diagnostico("duelo", velho)


def test_a_mensagem_chega_em_quem_roda_o_teste(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """O diagnostico so serve se vier junto do assert que falha.

    Com um golden de mentira num diretorio temporario: o `_diagnostico` le o
    ESPERADO, que e o arquivo em disco, e nao o atual -- foi assim que a
    primeira versao deste teste falhou, adulterando o lado errado.
    """
    monkeypatch.setattr("tests.golden.test_encounters.DADOS", tmp_path)

    antigo = envelope_de(1, "resumo_de_antigamente", ())
    antigo["schema_version"] = SCHEMA_VERSION - 1
    (tmp_path / "falso.json").write_text(json.dumps(antigo), encoding="utf-8")

    with pytest.raises(AssertionError, match="mudanca de FORMATO"):
        gravar_ou_comparar("falso", envelope_de(1, "resumo_de_agora", ()), update_golden=False)


def test_a_flag_de_regravacao_vem_do_conftest_da_raiz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, update_golden: bool
):
    """A fixture existe aqui, e e a mesma que `tests/render/` vai usar.

    Se `pytest_addoption` voltar para `tests/golden/conftest.py`, este teste
    continua passando -- mas o de `tests/render/` para de coletar. A trava de
    verdade e aquele; este so documenta de onde a fixture vem.
    """
    monkeypatch.setattr("tests.golden.test_encounters.DADOS", tmp_path)
    assert isinstance(update_golden, bool)

    with pytest.raises(pytest.skip.Exception, match="regravado"):
        gravar_ou_comparar("novo", envelope_de(1, "x", ()), update_golden=True)
    assert (tmp_path / "novo.json").is_file()

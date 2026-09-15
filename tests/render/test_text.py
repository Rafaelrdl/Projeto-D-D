"""Uma asercao de string exata por membro da uniao `Event`.

String exata e nao "contem": o que este pacote produz **e** a string, entao
afirmar sobre pedaco dela deixaria passar espaco duplicado, sinal errado e
ordem trocada -- justamente os defeitos que so aparecem lendo.

O teste de cobertura total no fim e o que impede a lista de envelhecer: evento
novo sem caso aqui reprova pelo nome, alem de ja reprovar no mypy por causa do
`assert_never`.
"""

from __future__ import annotations

import pytest

from tacticore.core.dice import DamageRoll, DieRoll
from tacticore.core.enums import (
    Ability,
    AdvantageState,
    AttackOutcome,
    ContestOutcome,
    SkipReason,
)
from tacticore.core.events import (
    AttackRolled,
    CombatEnded,
    ContestRolled,
    CreatureDowned,
    DamageRolled,
    Event,
    HpChanged,
    InitiativeRolled,
    KnockedProne,
    MovementSpent,
    RoundStarted,
    StoodUp,
    TurnEnded,
    TurnOrderSet,
    TurnSkipped,
    TurnStarted,
)
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import CombatOutcome, HitPoints, Position
from tacticore.core.testing import make_budget
from tacticore.render import narrate, narrate_event

HEROI = CreatureId("heroi")
VILAO = CreatureId("vilao")


def ataque(
    *,
    advantage: AdvantageState = AdvantageState.NORMAL,
    advantage_sources: tuple[str, ...] = (),
    disadvantage_sources: tuple[str, ...] = (),
    pair: tuple[int, int] = (15, 3),
    chosen_index: int = 0,
    natural: int = 15,
    outcome: AttackOutcome = AttackOutcome.HIT,
) -> AttackRolled:
    return AttackRolled(
        actor=HEROI,
        target=VILAO,
        attack_id=AttackId("espada"),
        attack_name="Espada Longa",
        advantage=advantage,
        advantage_sources=advantage_sources,
        disadvantage_sources=disadvantage_sources,
        pair=pair,
        chosen_index=chosen_index,  # type: ignore[arg-type]
        natural=natural,
        ability=Ability.FOR,
        ability_mod=3,
        proficiency=2,
        total=natural + 5,
        target_ac=14,
        target_was_down=False,
        outcome=outcome,
        rng_before=0,
        rng_after=2,
    )


def dano(*, critical: bool = False) -> DamageRoll:
    dados = (DieRoll(term_index=0, faces=8, value=6, from_crit=False),)
    if critical:
        dados = (*dados, DieRoll(term_index=0, faces=8, value=2, from_crit=True))
    return DamageRoll(
        dice=dados,
        flat=1,
        ability_bonus=3,
        critical=critical,
        total=sum(d.value for d in dados) + 4,
    )


# (evento, linha esperada) -- um por membro da uniao.
def disputa(outcome: ContestOutcome) -> ContestRolled:
    """A mesma rolagem com os tres desfechos.

    Os numeros nao batem com o desfecho de proposito: o que se testa aqui e a
    FRASE, e o narrador nao recalcula regra nenhuma. Os tres casos existem
    porque o empate tem frase propria, e ela e uma das duas coisas que seguram
    `ContestOutcome.TIE` existindo.
    """
    return ContestRolled(
        actor=HEROI,
        target=VILAO,
        actor_pair=(17, 4),
        actor_chosen_index=0,
        actor_natural=17,
        actor_ability=Ability.FOR,
        actor_bonus=3,
        actor_total=20,
        target_pair=(2, 11),
        target_chosen_index=1,
        target_natural=11,
        target_ability=Ability.DES,
        target_bonus=-1,
        target_total=10,
        outcome=outcome,
        rng_before=6,
        rng_after=10,
    )


CASOS: list[tuple[str, Event, str]] = [
    (
        "initiative_rolled",
        InitiativeRolled(
            creature=HEROI, d20=14, dex_mod=-1, dex_score=8, total=13, rng_before=0, rng_after=1
        ),
        "heroi rola iniciativa: d20 14 -1 (DES 8) = 13",
    ),
    (
        "turn_order_set",
        TurnOrderSet(order=(HEROI, VILAO)),
        "ordem de iniciativa: heroi, vilao",
    ),
    ("round_started", RoundStarted(round_number=3), "== rodada 3 =="),
    (
        "turn_started",
        TurnStarted(creature=HEROI, budget=make_budget(movement_remaining_ft=35)),
        "turno de heroi: 1 acao, 35 pes",
    ),
    (
        "turn_started_sem_acao",
        TurnStarted(
            creature=HEROI,
            budget=make_budget(action_available=False, movement_remaining_ft=0),
        ),
        "turno de heroi: sem acao, 0 pes",
    ),
    (
        "turn_skipped",
        TurnSkipped(creature=VILAO, reason=SkipReason.ACTOR_IS_DOWN),
        "vilao perde o turno (actor_is_down)",
    ),
    ("turn_ended", TurnEnded(creature=HEROI), "heroi encerra o turno"),
    (
        "movement_spent",
        MovementSpent(
            creature=HEROI,
            origin=Position(x=0, y=0),
            destination=Position(x=3, y=0),
            feet=15,
            remaining_ft=20,
        ),
        "heroi anda 15 pes (0,0) -> (3,0), 20 restantes",
    ),
    (
        "attack_rolled",
        ataque(),
        "heroi ataca vilao com Espada Longa: d20 15 +3 FOR +2 prof = 20 vs CA 14 -> acerto",
    ),
    (
        "attack_rolled_vantagem",
        ataque(
            advantage=AdvantageState.ADVANTAGE,
            advantage_sources=("flanqueando",),
            pair=(3, 19),
            chosen_index=1,
            natural=19,
        ),
        "heroi ataca vilao com Espada Longa: d20 3/19 vantagem (flanqueando) -> 19 "
        "+3 FOR +2 prof = 24 vs CA 14 -> acerto",
    ),
    (
        "attack_rolled_desvantagem",
        ataque(
            advantage=AdvantageState.DISADVANTAGE,
            disadvantage_sources=("cegado", "coberto"),
            pair=(19, 3),
            natural=3,
            outcome=AttackOutcome.MISS,
        ),
        "heroi ataca vilao com Espada Longa: d20 19/3 desvantagem (cegado, coberto) -> 3 "
        "+3 FOR +2 prof = 8 vs CA 14 -> erro",
    ),
    (
        "attack_rolled_critico",
        ataque(natural=20, outcome=AttackOutcome.CRITICAL_HIT),
        "heroi ataca vilao com Espada Longa: d20 20 +3 FOR +2 prof = 25 vs CA 14 -> ACERTO CRITICO",
    ),
    (
        "attack_rolled_falha_critica",
        ataque(natural=1, outcome=AttackOutcome.CRITICAL_MISS),
        "heroi ataca vilao com Espada Longa: d20 1 +3 FOR +2 prof = 6 vs CA 14 -> ERRO CRITICO",
    ),
    (
        "damage_rolled",
        DamageRolled(actor=HEROI, target=VILAO, roll=dano(), rng_before=2, rng_after=3),
        "  dano: d8=6 +4 = 10",
    ),
    (
        "damage_rolled_critico",
        DamageRolled(
            actor=HEROI, target=VILAO, roll=dano(critical=True), rng_before=2, rng_after=4
        ),
        "  dano critico: d8=6 d8=2 +4 = 12",
    ),
    (
        "hp_changed",
        HpChanged(
            creature=VILAO,
            before=HitPoints(current=14, maximum=14),
            after=HitPoints(current=4, maximum=14),
            dealt=10,
            overkill=0,
        ),
        "  vilao: 14 -> 4 hp (10 de dano)",
    ),
    (
        "hp_changed_com_excedente",
        HpChanged(
            creature=VILAO,
            before=HitPoints(current=3, maximum=14),
            after=HitPoints(current=0, maximum=14),
            dealt=3,
            overkill=7,
        ),
        "  vilao: 3 -> 0 hp (3 de dano, 7 desperdicados)",
    ),
    (
        "stood_up",
        StoodUp(creature=HEROI, feet=15, remaining_ft=20),
        "heroi levanta (15 pes, 20 restantes)",
    ),
    ("creature_downed", CreatureDowned(creature=VILAO), "  vilao cai"),
    (
        "contest_rolled_derruba",
        disputa(ContestOutcome.SUCCESS),
        "heroi empurra vilao: d20 17 +3 FOR = 20 vs d20 11 -1 DES = 10 -> DERRUBA",
    ),
    (
        "contest_rolled_resiste",
        disputa(ContestOutcome.FAILURE),
        "heroi empurra vilao: d20 17 +3 FOR = 20 vs d20 11 -1 DES = 10 -> resiste",
    ),
    (
        "contest_rolled_empate",
        disputa(ContestOutcome.TIE),
        "heroi empurra vilao: d20 17 +3 FOR = 20 vs d20 11 -1 DES = 10 -> empate, resiste",
    ),
    ("knocked_prone", KnockedProne(creature=VILAO), "  vilao cai no chao"),
    (
        "combat_ended",
        CombatEnded(outcome=CombatOutcome(winning_team="herois", last_round=3)),
        "combate encerrado na rodada 3: vitoria de herois",
    ),
    (
        "combat_ended_empate",
        CombatEnded(outcome=CombatOutcome(winning_team=None, last_round=5)),
        "combate encerrado na rodada 5: ninguem sobrou",
    ),
]


@pytest.mark.parametrize(
    ("evento", "esperado"),
    [(e, texto) for _, e, texto in CASOS],
    ids=[nome for nome, _, _ in CASOS],
)
def test_narrativa_de_cada_evento(evento: Event, esperado: str):
    assert narrate_event(evento) == esperado


def test_todo_evento_tem_caso_aqui():
    """Evento novo sem frase reprova pelo nome.

    O `assert_never` de `narrate_event` ja pega isso no mypy; este pega para
    quem rodar so a suite, e nomeia o culpado.
    """
    cobertos = {type(e) for _, e, _ in CASOS}
    # A uniao `Event` e um alias PEP 695; `__value__` da os membros dela.
    membros = set(Event.__value__.__args__)  # type: ignore[attr-defined]
    faltando = membros - cobertos
    assert not faltando, f"eventos sem narrativa testada: {sorted(c.__name__ for c in faltando)}"


def test_o_log_sai_na_ordem_em_que_aconteceu():
    eventos = [e for _, e, _ in CASOS[:3]]
    assert narrate(eventos) == tuple(texto for _, _, texto in CASOS[:3])


def test_log_vazio_nao_gera_linha():
    assert narrate(()) == ()


@pytest.mark.parametrize(("_nome", "evento", "_texto"), CASOS, ids=[n for n, _, _ in CASOS])
def test_nenhuma_linha_quebra_ou_vem_vazia(_nome: str, evento: Event, _texto: str):
    """Uma linha por evento e a promessa da API; quebra dentro a desmente."""
    linha = narrate_event(evento)
    assert linha
    assert "\n" not in linha
    assert linha == linha.rstrip()

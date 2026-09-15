"""O piloto automatico e a politica que ele usa.

`primeira_legal` nao e IA e nao tenta ser: escolhe sempre a primeira acao
legal, que e o que um teste de determinismo e um golden precisam. Os modos de
falha do laco sao testados porque a alternativa e um teste que trava em vez de
falhar.

O que se testa sobre o **parametro** `politica` e uma coisa so: que ele nao e
decorativo. Um default embutido por engano passaria em qualquer teste que so
conferisse que os goldens continuam iguais.
"""

from __future__ import annotations

import pytest

from tacticore.core.actions import Action, AttackAction
from tacticore.core.engine import combat_result, legal_actions, start_combat
from tacticore.core.errors import CorruptStateError
from tacticore.core.events import CombatEnded, Event
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import CombatState, Statblock
from tacticore.core.rng import SplitMix64
from tacticore.core.testing import (
    conduzir,
    make_attack,
    make_combatant,
    make_duelo,
    make_statblock,
    make_state,
    play_out,
    primeira_legal,
)

FICHA = make_statblock(
    id="lutador",
    armor_class=10,
    max_hp=8,
    attacks=(make_attack(damage="1d6+2"),),
)


def test_o_combate_termina_e_sobra_um_time():
    catalogo, gente = make_duelo(ficha_a=FICHA, ficha_b=FICHA)
    abertura = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=8))
    estado, log = play_out(abertura.state)

    desfecho = combat_result(estado)
    assert desfecho is not None
    assert desfecho.winning_team in {"herois", "viloes"}
    assert log


def test_combate_ja_encerrado_devolve_o_estado_intacto():
    acabado = make_state(
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes", hp=0),
        )
    )
    estado, log = play_out(acabado)
    assert estado is acabado
    assert log == ()


def test_sem_acao_legal_e_combate_em_andamento_e_bug_do_motor():
    """Estado que o chamador consegue montar: o dono do turno esta caido, mas o
    time dele tem alguem de pe. O avanco normal de turno nunca produz isto."""
    travado = make_state(
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes"),
            make_combatant(id="c", team="herois"),
        ),
        current="a",
    )
    with pytest.raises(CorruptStateError, match="sem acao legal"):
        play_out(travado)


def test_o_limite_de_acoes_falha_em_vez_de_travar():
    """Um bug de regra que impeça o combate de terminar tem que virar uma
    falha legivel, e nao um processo pendurado."""
    catalogo, gente = make_duelo(ficha_a=FICHA, ficha_b=FICHA)
    abertura = start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=8))
    with pytest.raises(CorruptStateError, match="nao terminou em 2 acoes"):
        play_out(abertura.state, max_actions=2)


# ------------------------------------------------------- a politica --------


FICHA_DE_DOIS_ATAQUES = make_statblock(
    id="lutador",
    armor_class=10,
    max_hp=8,
    attacks=(make_attack(id="soco", damage="1d6+2"), make_attack(id="chute", damage="1d4")),
)
"""Dois ataques, para o menu ter um segundo item que NAO e encerrar o turno.

Com um ataque so, toda politica que nao escolhe `acoes[0]` acaba escolhendo
`EndTurnAction` e o combate nunca termina -- o que prova que o parametro chega
no laco, mas nao prova que ele muda o combate."""


def duelo_aberto(ficha: Statblock = FICHA) -> CombatState:
    catalogo, gente = make_duelo(ficha_a=ficha, ficha_b=ficha)
    return start_combat(statblocks=catalogo, participants=gente, rng=SplitMix64(seed=8)).state


def test_primeira_legal_devolve_o_primeiro_item():
    estado = duelo_aberto()
    acoes = legal_actions(estado)
    assert primeira_legal(estado, acoes) is acoes[0]


def test_o_default_e_exatamente_a_politica_antiga():
    """O criterio de aceite do passo: passar `primeira_legal` a mao tem que dar
    o mesmo combate que nao passar nada. Se desse diferente, os seis goldens de
    encontro estariam regravando por causa de um refactor."""
    estado = duelo_aberto()
    assert play_out(estado) == play_out(estado, politica=primeira_legal)


def segunda_se_houver(state: CombatState, acoes: tuple[Action, ...]) -> Action:
    """Politica de mentira: existe so para provar que o parametro chega no laco."""
    return acoes[1] if len(acoes) > 1 else acoes[0]


def test_uma_politica_diferente_produz_um_combate_diferente():
    """Sem isto, um `acoes[0]` deixado por engano dentro do laco passaria em
    todos os testes acima: o default coincide com ele."""
    estado = duelo_aberto(FICHA_DE_DOIS_ATAQUES)
    _, padrao = play_out(estado)
    _, outra = play_out(estado, politica=segunda_se_houver)
    assert padrao != outra


def fora_do_menu(state: CombatState, acoes: tuple[Action, ...]) -> Action:
    """Ataca com quem nao e o dono do turno. `validate` recusa com NOT_YOUR_TURN."""
    intruso = next(c for c in sorted(state.combatants, key=str) if c != state.turn_order.current)
    return AttackAction(
        actor=CreatureId(intruso),
        target=state.turn_order.current,
        attack_id=AttackId("ataque"),
    )


def test_a_politica_que_escolhe_fora_do_menu_e_nomeada_no_erro():
    """Este ramo era inalcancavel e estava marcado `no cover`: com `acoes[0]`
    embutido, so um bug de `legal_actions` chegaria nele. Virou alcancavel no
    momento em que a escolha passou a vir de fora -- e a mensagem, que culpava
    `legal_actions`, passou a nomear quem de fato escolheu."""
    with pytest.raises(CorruptStateError, match=r"a politica fora_do_menu escolheu"):
        play_out(duelo_aberto(), politica=fora_do_menu)


# ------------------------------------------------------- o condutor --------
#
# `conduzir` existe para que continue havendo UM laco de combate no projeto.
# O docstring de `tacticore.__main__` recusa por escrito um segundo laco so
# para o CLI, e o CLI precisa de duas coisas que `play_out` nao da: narrar
# turno a turno e parar para ler a escolha.


def a_mao(state: CombatState) -> tuple[CombatState, tuple[Event, ...]]:
    """Conduz o combate a mao, como o comando faz, e devolve o mesmo par."""
    conducao = conduzir(state, origem="o teste")
    log: list[Event] = []
    passo = next(conducao)
    while True:
        log.extend(passo.events)
        if not passo.actions:
            return passo.state, tuple(log)
        passo = conducao.send(primeira_legal(passo.state, passo.actions))


def test_conduzir_a_mao_da_o_mesmo_que_play_out():
    """A trava central: sao o mesmo laco, e nao dois que se parecem.

    Se divergissem, o combate do comando interativo seria outro motor -- que e
    exatamente o que o docstring de `__main__` recusa."""
    estado = duelo_aberto()
    assert a_mao(estado) == play_out(estado)


def test_o_primeiro_passo_nao_tem_evento_e_tem_menu():
    passo = next(conduzir(duelo_aberto()))
    assert passo.events == ()
    assert passo.actions


def test_o_ultimo_passo_tem_menu_vazio_e_o_estado_final():
    """Menu vazio e o sinal de fim, e nao `StopIteration`: quem conduz para
    olhando o passo que recebeu, sem precisar de `try`."""
    estado = duelo_aberto()
    final, _ = a_mao(estado)
    assert combat_result(final) is not None


def test_os_eventos_dos_passos_somam_o_log_inteiro():
    """Cada passo carrega o que aconteceu desde o anterior. Se um passo
    perdesse os seus, o comando narraria menos que o golden."""
    estado = duelo_aberto()
    _, por_passo = a_mao(estado)
    _, de_uma_vez = play_out(estado)
    assert por_passo == de_uma_vez


def test_o_ultimo_passo_carrega_os_eventos_da_acao_final():
    """Sem isto, o fim do combate -- CombatEnded inclusive -- sumiria do log
    de quem conduz a mao, porque ele acontece na ultima acao."""
    conducao = conduzir(duelo_aberto())
    passo = next(conducao)
    while passo.actions:
        passo = conducao.send(primeira_legal(passo.state, passo.actions))
    assert any(isinstance(e, CombatEnded) for e in passo.events)


def test_o_condutor_nomeia_quem_mandou_a_acao_recusada():
    """De dentro do laco nao da para saber quem escolheu; `origem` e como
    `play_out` diz "a politica X" e o comando diz "o jogador"."""
    conducao = conduzir(duelo_aberto(), origem="o jogador")
    passo = next(conducao)
    intrusa = fora_do_menu(passo.state, passo.actions)
    with pytest.raises(CorruptStateError, match="o jogador escolheu"):
        conducao.send(intrusa)


def _conduzir_ate(estado: CombatState, quantas: int) -> None:
    conducao = conduzir(estado, max_actions=2)
    passo = next(conducao)
    for _ in range(quantas):
        passo = conducao.send(primeira_legal(passo.state, passo.actions))


def test_o_condutor_tambem_para_no_limite_de_acoes():
    with pytest.raises(CorruptStateError, match="nao terminou em 2 acoes"):
        _conduzir_ate(duelo_aberto(), 3)

"""Times, fim de combate e enumeracao de acoes legais."""

from __future__ import annotations

from tacticore.core.actions import Action, AttackAction, EndTurnAction, MoveAction, ShoveAction
from tacticore.core.engine import apply, combat_result, legal_actions
from tacticore.core.enums import Condition, RejectionReason
from tacticore.core.events import CombatEnded
from tacticore.core.ids import AttackId, CreatureId
from tacticore.core.model import CombatState, Position
from tacticore.core.results import Applied, Rejected
from tacticore.core.rng import ScriptedRng
from tacticore.core.serde import dump, load
from tacticore.core.testing import (
    make_attack,
    make_budget,
    make_combatant,
    make_statblock,
    make_state,
)

ESPADA = AttackId("espada")


def arena(
    *,
    hp_b: int = 6,
    extras: tuple[tuple[str, str, int], ...] = (),
    fita: tuple[int, ...] = (),
    budget_a: object = None,
    posicoes: dict[str, tuple[int, int]] | None = None,
    casas: int | None = None,
    conditions_b: tuple[Condition, ...] = (),
) -> CombatState:
    """`a` (herois) contra `b` (viloes), mais quem `extras` pedir."""
    ficha = make_statblock(
        id="ficha",
        armor_class=10,
        max_hp=10,
        speed_ft=30,
        attacks=(make_attack(id="espada", damage="1d6"),),
    )
    lutadores = [
        make_combatant(id="a", team="herois", budget=budget_a),  # type: ignore[arg-type]
        make_combatant(id="b", team="viloes", hp=hp_b, conditions=conditions_b),
    ]
    lutadores.extend(make_combatant(id=nome, team=time, hp=vida) for nome, time, vida in extras)
    return make_state(
        statblocks=(ficha,),
        combatants=tuple(lutadores),
        current="a",
        rng=ScriptedRng(script=fita),
        posicoes={"a": (0, 0), "b": (casas, 0)} if casas is not None else posicoes,
    )


def atacar(estado: CombatState, alvo: str = "b") -> Applied | Rejected:
    return apply(
        estado,
        AttackAction(actor=CreatureId("a"), target=CreatureId(alvo), attack_id=ESPADA),
    )


# ------------------------------------------------------ combat_result ------


def test_combate_com_dois_lados_de_pe_esta_em_andamento():
    assert combat_result(arena()) is None


def test_ultimo_abate_encerra_o_combate():
    resultado = atacar(arena(hp_b=1, fita=(15, 1, 6)))
    assert isinstance(resultado, Applied)

    desfecho = combat_result(resultado.state)
    assert desfecho is not None
    assert desfecho.winning_team == "herois"


def test_aniquilacao_mutua_tem_vencedor_nulo():
    """`winning_team=None` e empate, e nao "ainda rolando".

    Misturar os dois faria o combate nunca fechar em aniquilacao mutua -- era
    exatamente o bug de uma das propostas de arquitetura.
    """
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes", hp=0),
        )
    )
    desfecho = combat_result(estado)
    assert desfecho is not None
    assert desfecho.winning_team is None


def test_o_desfecho_guarda_a_rodada():
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes", hp=0),
        ),
        round_number=4,
    )
    desfecho = combat_result(estado)
    assert desfecho is not None
    assert desfecho.last_round == 4


def test_o_desfecho_e_derivado_e_nao_guardado():
    """Derivado resolve dois problemas: nada fica velho e nada some no save."""
    estado = arena()
    assert "outcome" not in dump(estado)["state"]
    assert combat_result(load(dump(estado))) == combat_result(estado)


def test_com_tres_times_derrubar_um_nao_acaba_o_combate():
    """`team` e string livre justamente para isto: tres faccoes e um monstro
    que troca de lado nao migram um enum sem bump de schema."""
    assert combat_result(arena(extras=(("c", "neutros", 10),))) is None

    # Viloes fora, mas herois e neutros continuam de pe: ainda ha dois lados.
    sem_viloes = arena(hp_b=0, extras=(("c", "neutros", 10),))
    assert combat_result(sem_viloes) is None


def test_com_tres_times_acaba_quando_sobra_um():
    so_neutros = arena(hp_b=0, extras=(("c", "neutros", 10), ("d", "herois", 0)))
    caidos = make_state(
        statblocks=tuple(so_neutros.statblocks.values()),
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes", hp=0),
            make_combatant(id="c", team="neutros"),
        ),
        current="c",
    )
    desfecho = combat_result(caidos)
    assert desfecho is not None
    assert desfecho.winning_team == "neutros"


# ------------------------------------------------------- CombatEnded -------


def test_o_fim_e_anunciado_exatamente_na_transicao():
    resultado = atacar(arena(hp_b=1, fita=(15, 1, 6)))
    assert isinstance(resultado, Applied)
    assert sum(isinstance(e, CombatEnded) for e in resultado.events) == 1
    assert isinstance(resultado.events[-1], CombatEnded)


def test_o_anuncio_carrega_o_desfecho():
    resultado = atacar(arena(hp_b=1, fita=(15, 1, 6)))
    assert isinstance(resultado, Applied)
    evento = resultado.events[-1]
    assert isinstance(evento, CombatEnded)
    assert evento.outcome == combat_result(resultado.state)


def test_acao_que_nao_encerra_nao_anuncia_nada():
    resultado = atacar(arena(hp_b=10, fita=(15, 1, 1)))
    assert isinstance(resultado, Applied)
    assert not any(isinstance(e, CombatEnded) for e in resultado.events)


def test_depois_do_fim_tudo_e_recusado():
    resultado = atacar(arena(hp_b=1, fita=(15, 1, 6)))
    assert isinstance(resultado, Applied)
    acabado = resultado.state

    for acao in (
        EndTurnAction(actor=CreatureId("a")),
        MoveAction(actor=CreatureId("a"), to=Position(x=0, y=1)),
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=ESPADA),
    ):
        recusa = apply(acabado, acao)
        assert isinstance(recusa, Rejected)
        assert recusa.reason is RejectionReason.COMBAT_OVER
        assert recusa.state is acabado


def test_o_fim_nao_e_anunciado_duas_vezes():
    """Depois do fim nada e aplicado, entao nao ha segunda transicao."""
    resultado = atacar(arena(hp_b=1, fita=(15, 1, 6)))
    assert isinstance(resultado, Applied)
    segunda = apply(resultado.state, EndTurnAction(actor=CreatureId("a")))
    assert isinstance(segunda, Rejected)


# ------------------------------------------------------ legal_actions ------


def test_o_menu_de_quem_ja_esta_colado_no_inimigo():
    """`make_state` enfileira, entao `a` e `b` nascem adjacentes.

    Sem movimento que melhore a posicao, o menu nao oferece andar -- e isso e o
    comportamento certo, nao uma lacuna."""
    acoes = legal_actions(arena())
    assert acoes == (
        AttackAction(actor=CreatureId("a"), target=CreatureId("b"), attack_id=ESPADA),
        # O empurrao entra no MESMO degrau do ataque, porque gasta a mesma
        # acao, e por ULTIMO dentro dele: `acoes[0]` continua sendo um ataque,
        # e e disso que o piloto automatico depende para terminar combate.
        ShoveAction(actor=CreatureId("a"), target=CreatureId("b")),
        EndTurnAction(actor=CreatureId("a")),
    )


def test_empurrar_vem_DEPOIS_de_todos_os_ataques():
    """A ordem do menu nao e preferencia estetica: e o que faz o combate acabar.

    Com o empurrao antes dos ataques, `primeira_legal` empurra todo turno,
    ninguem ataca, ninguem morre e `play_out` estoura em "o combate nao terminou
    em 500 acoes" -- medido, 38 testes vermelhos, incluindo quatro goldens e o
    torneio. Depois deles, `acoes[0]` nao muda.
    """
    tipos = [type(a) for a in legal_actions(arena())]
    assert tipos.index(AttackAction) < tipos.index(ShoveAction)
    assert tipos.index(ShoveAction) < tipos.index(EndTurnAction)


def test_o_menu_nao_oferece_empurrao_de_longe():
    """Empurrar exige casa adjacente, e o menu so oferece o que `validate`
    aceita -- a propriedade central de `legal_actions`."""
    acoes = legal_actions(arena(casas=3))
    assert not any(isinstance(a, ShoveAction) for a in acoes)


def test_o_menu_oferece_empurrao_a_quem_ja_esta_caido():
    """Derrubar quem esta no chao e legal na SRD, aqui e no-op, e `validate`
    aceita de qualquer jeito -- a mesma assimetria de atacar quem caiu.

    Um filtro nasceria como ramo que nenhum combate alcanca, e a decisao fica
    escrita aqui para nao virar esquecimento na proxima leitura.
    """
    acoes = legal_actions(arena(conditions_b=(Condition.CAIDO,)))
    assert any(isinstance(a, ShoveAction) for a in acoes)


def test_o_menu_oferece_uma_casa_so_e_nao_todas_as_alcancaveis():
    """Conjunto canonico e finito: com 30 pes sao 168 casas alcancaveis, e
    nenhuma interface mostraria isso. A curadoria e "a que mais aproxima"."""
    estado = arena(posicoes={"a": (0, 0), "b": (8, 0)})
    movimentos = [a for a in legal_actions(estado) if isinstance(a, MoveAction)]
    assert len(movimentos) == 1
    assert movimentos[0].to == Position(x=6, y=0)


def test_a_casa_canonica_aproxima_do_inimigo_mais_perto():
    estado = arena(posicoes={"a": (0, 0), "b": (20, 0), "c": (0, 9)}, extras=(("c", "viloes", 10),))
    movimentos = [a for a in legal_actions(estado) if isinstance(a, MoveAction)]
    assert movimentos[0].to == Position(x=0, y=6), "anda na direcao de c, nao de b"


def test_sem_movimento_restante_o_menu_nao_oferece_andar():
    estado = arena(
        posicoes={"a": (0, 0), "b": (8, 0)}, budget_a=make_budget(movement_remaining_ft=0)
    )
    assert not any(isinstance(a, MoveAction) for a in legal_actions(estado))


def test_sem_acao_restante_o_menu_nao_oferece_atacar():
    estado = arena(budget_a=make_budget(action_available=False))
    assert not any(isinstance(a, AttackAction) for a in legal_actions(estado))


def test_o_menu_so_oferece_inimigo_de_pe():
    """Assimetria deliberada: `apply` aceita atacar quem caiu, o menu nao
    oferece. Aqui e o cardapio, nao a definicao de legalidade."""
    estado = arena(extras=(("c", "viloes", 0),))
    alvos = {a.target for a in legal_actions(estado) if isinstance(a, AttackAction)}
    assert alvos == {"b"}


def test_o_menu_nao_oferece_aliado():
    estado = arena(extras=(("c", "herois", 10),))
    alvos = {a.target for a in legal_actions(estado) if isinstance(a, AttackAction)}
    assert alvos == {"b"}


def test_o_menu_e_um_por_par_de_ataque_e_alvo():
    """Com os dois alvos ao alcance de ambas as armas."""
    ficha = make_statblock(
        id="ficha",
        attacks=(make_attack(id="espada", range_ft=30), make_attack(id="arco", range_ft=30)),
    )
    estado = make_state(
        statblocks=(ficha,),
        combatants=(
            make_combatant(id="a", team="herois"),
            make_combatant(id="b", team="viloes"),
            make_combatant(id="c", team="viloes"),
        ),
        current="a",
    )
    ataques = [a for a in legal_actions(estado) if isinstance(a, AttackAction)]
    assert [(a.attack_id, a.target) for a in ataques] == [
        ("espada", "b"),
        ("espada", "c"),
        ("arco", "b"),
        ("arco", "c"),
    ]


def test_combate_encerrado_nao_oferece_nada():
    assert legal_actions(arena(hp_b=0)) == ()


def test_toda_acao_oferecida_e_aceita():
    """A propriedade central: o menu nunca oferece o que `apply` recusaria."""
    estados = [
        arena(),
        arena(budget_a=make_budget(movement_remaining_ft=5)),
        arena(budget_a=make_budget(action_available=False)),
        arena(extras=(("c", "viloes", 10), ("d", "viloes", 0))),
    ]
    for estado in estados:
        acoes: tuple[Action, ...] = legal_actions(estado)
        assert acoes, "um turno em andamento sempre tem ao menos EndTurn"
        for acao in acoes:
            resultado = apply(
                # Fita generosa: o ataque consome dois d20 mais os dados de dano.
                make_state(
                    statblocks=tuple(estado.statblocks.values()),
                    combatants=tuple(estado.combatants.values()),
                    order=tuple(estado.turn_order.order),
                    current=str(estado.turn_order.current),
                    rng=ScriptedRng(script=(10, 10, 3, 3, 3, 3)),
                ),
                acao,
            )
            assert isinstance(resultado, Applied), f"{acao} foi recusada: {resultado}"


def test_encerrar_o_turno_esta_sempre_no_menu():
    for estado in (
        arena(),
        arena(budget_a=make_budget(action_available=False, movement_remaining_ft=0)),
    ):
        assert any(isinstance(a, EndTurnAction) for a in legal_actions(estado))


def test_menu_vazio_para_quem_esta_caido():
    """Estado que o chamador consegue montar: o caido e o dono do turno, mas o
    time dele ainda tem gente de pe. O avanco normal de turno pula esse caso;
    o menu tambem nao pode oferecer nada."""
    estado = make_state(
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes"),
            make_combatant(id="c", team="herois"),
        ),
        current="a",
    )
    assert combat_result(estado) is None
    assert legal_actions(estado) == ()


# --------------------------------------------- contrato do ADR 0002 (a2) ----


def test_encerrar_o_turno_fecha_o_menu():
    """Cláusula (a2) do ADR 0002, na versao reescrita pela fatia 2.

    `play_out` escolhe `acoes[0]` e gera tres dos quatro goldens, entao a ordem
    de `legal_actions` e contrato de facto. Enquanto ela for incondicional,
    `EndTurnAction` fecha a lista e acao nova entra antes dele.

    O enunciado ingenuo ("EndTurn e sempre o ultimo") seria falso: a lista e
    vazia em dois casos legitimos. Dai o par de asercoes.
    """
    for estado in (
        arena(),
        arena(budget_a=make_budget(action_available=False)),
        arena(budget_a=make_budget(movement_remaining_ft=0)),
        arena(budget_a=make_budget(action_available=False, movement_remaining_ft=0)),
        arena(extras=(("c", "viloes", 10), ("d", "viloes", 0))),
    ):
        acoes = legal_actions(estado)
        assert acoes, "turno em andamento sempre tem ao menos EndTurn"
        assert isinstance(acoes[-1], EndTurnAction)
        assert sum(isinstance(a, EndTurnAction) for a in acoes) == 1


def test_o_menu_so_e_vazio_em_dois_casos():
    """A outra metade da cláusula: quando `legal_actions` devolve `()`.

    Se um terceiro caso aparecer, `play_out` passa a levantar CorruptStateError
    no meio de um combate legitimo -- e o golden que ele gera some junto.
    """
    acabado = arena(hp_b=0)
    assert combat_result(acabado) is not None
    assert legal_actions(acabado) == ()

    ator_caido = make_state(
        combatants=(
            make_combatant(id="a", team="herois", hp=0),
            make_combatant(id="b", team="viloes"),
            make_combatant(id="c", team="herois"),
        ),
        current="a",
    )
    assert combat_result(ator_caido) is None
    assert legal_actions(ator_caido) == ()


def test_a_ordem_do_menu_e_acao_movimento_encerrar():
    """A politica escrita no ADR 0002 (a2), como trava executavel.

    Ordenado por quanto a escolha custa e quao irreversivel ela e: primeiro o
    que gasta a acao, depois o que gasta movimento, por ultimo encerrar. E o
    `play_out` obedece a esta ordem para gerar tres dos seis goldens, entao ela
    e contrato e nao conveniencia.
    """
    # Precisa de arma a distancia para os tres aparecerem juntos: com arma de
    # perto, estar ao alcance ja significa estar adjacente, e ai nenhum
    # movimento melhora a distancia.
    ficha = make_statblock(id="ficha", speed_ft=30, attacks=(make_attack(id="arco", range_ft=30),))
    estado = make_state(
        statblocks=(ficha,),
        combatants=(
            make_combatant(id="a", statblock_id="ficha", team="herois"),
            make_combatant(id="b", statblock_id="ficha", team="viloes"),
        ),
        current="a",
        posicoes={"a": (0, 0), "b": (5, 0)},
    )
    tipos = [type(a) for a in legal_actions(estado)]

    assert tipos.index(AttackAction) < tipos.index(MoveAction)
    assert tipos.index(MoveAction) < tipos.index(EndTurnAction)


def test_sem_nada_ao_alcance_o_menu_comeca_pelo_movimento():
    """A consequencia deliberada da politica: e assim que um combate que comeca
    a 20 pes fecha distancia em vez de travar."""
    estado = arena(posicoes={"a": (0, 0), "b": (8, 0)})
    acoes = legal_actions(estado)
    assert isinstance(acoes[0], MoveAction)
    assert not any(isinstance(a, AttackAction) for a in acoes)

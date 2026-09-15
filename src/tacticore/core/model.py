"""O vocabulario de estado: dados imutaveis, zero comportamento.

Tudo aqui e ``frozen=True, slots=True, kw_only=True``, e a uniformidade e
proposital:

- ``frozen`` faz de "devolve estado novo" uma garantia do interpretador e nao
  uma promessa do autor, e da igualdade estrutural de graca -- que e o que
  sustenta os testes de determinismo (`estado_a == estado_b`);
- ``slots`` impede que alguem pendure um atributo que nao esta declarado, e
  portanto que nao serializa;
- ``kw_only`` impede a troca silenciosa de dois `int` adjacentes, do tipo
  `HitPoints(8, 12)` quando se queria `HitPoints(12, 8)`.

Os tipos permitidos em campo de estado sao ``str``, ``int``, ``bool``,
``StrEnum``, ``tuple``, dataclass frozen e ``Mapping[str, ...]``. **Nao entram
`float`** (toda regra da SRD e inteira; float em JSON e round-trip que quase
bate), **nem `set`** (ordem de iteracao varia com `PYTHONHASHSEED` e quebra o
determinismo de forma intermitente, que e o pior jeito de descobrir), nem
`list`/`dict` mutavel. `tests/architecture/test_state_guardrails.py` reprova a
violacao.

Nenhum campo derivado mora aqui. Quem quer saber se o combate acabou chama
`combat_result(state)`; guardar a resposta seria criar um segundo lugar onde a
verdade pode ficar velha.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tacticore.core.dice import DamageExpr
from tacticore.core.enums import Ability
from tacticore.core.ids import AttackId, CreatureId, StatblockId
from tacticore.core.rng import RngState


@dataclass(frozen=True, slots=True, kw_only=True)
class Abilities:
    """Os seis valores de atributo, como estao na ficha.

    Valores, nao modificadores: o modificador e `(valor - 10) // 2` e e
    derivado em `rules.ability_modifier`. Guardar os dois seria guardar a mesma
    informacao duas vezes, com um jeito de discordarem.
    """

    forca: int
    destreza: int
    constituicao: int
    inteligencia: int
    sabedoria: int
    carisma: int


PES_POR_CASA = 5
"""Quantos pes vale uma casa da grade.

Mora aqui e nao em `rules` porque e a **unidade** de `Position`, e nao uma
regra: quem converte casa em pes precisa dela tanto quanto quem valida um save.
Deixa-la em `rules` obrigaria `serde` a importar a camada de regra, que e
exatamente o que o guardiao de camadas existe para impedir -- e foi ele que
apontou isto.

O valor em si vem da SRD: uma casa de 5 pes, na horizontal, na vertical e na
diagonal.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Position:
    """Uma casa do tabuleiro, em coordenadas de casa e nao de pes.

    Dataclass e nao `tuple[int, int]` por tres motivos que so aparecem depois:
    `p.x` nao troca de lugar com `p.y` num refactor, o serializador emite
    `{"x": 3, "y": 0}` em vez de `[3, 0]` (que ninguem consegue ler no diff de
    um golden), e o dia em que existir altura o campo entra aqui em vez de
    quebrar toda desestruturacao de tupla do projeto.

    A grade nao tem limite. Coordenada negativa e valida: o encontro escolhe a
    origem, e inventar uma borda seria inventar uma regra que a SRD nao tem.
    """

    x: int
    y: int


@dataclass(frozen=True, slots=True, kw_only=True)
class HitPoints:
    """Pontos de vida atuais e maximos.

    Dataclass e nao `int` solto de proposito: quando HP temporario e a
    distincao entre morto e inconsciente entrarem, eles viram campos com
    default aqui dentro, em vez de uma troca de assinatura em cada funcao que
    hoje recebe um `int`.
    """

    current: int
    maximum: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AttackProfile:
    """Um ataque declarado numa ficha."""

    id: AttackId
    name: str
    """Nome exibivel. E **dado**, nao apresentacao: sem ele o log vira charada."""

    ability: Ability
    """O atributo que entra no acerto e no dano.

    Um so por enquanto. Quando acuidade entrar, vira `tuple[Ability, ...]` e a
    regra passa a escolher o melhor -- campo trocado, nao assinatura.
    """

    proficient: bool
    damage: DamageExpr

    range_ft: int
    """Ate onde o ataque alcanca, em pes.

    Sem default, pelo mesmo motivo que `Combatant.position`: um default aqui
    pareceria manter os saves v2 carregando e nao manteria. E `5` -- o alcance
    de uma arma corpo a corpo -- e justamente o valor que alguem escolheria como
    default sem pensar, o que faria toda arma de arremesso nascer errada e em
    silencio.

    A SRD tem alcance curto e longo para armas a distancia, com desvantagem no
    longo. Aqui e um numero so; o segundo esta registrado em
    `docs/srd-atribuicao.md`."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Statblock:
    """A ficha: o que e verdade sobre um tipo de criatura, nao sobre uma copia.

    Fica no catalogo do estado e e compartilhada. Oito goblins identicos sao
    oito `Combatant` apontando para um `Statblock`, e uma condicao aplicada a
    um deles nao pode encostar nos outros sete -- e por isso que a ficha e o
    participante sao coisas separadas.
    """

    id: StatblockId
    name: str
    abilities: Abilities
    armor_class: int
    max_hp: int
    proficiency_bonus: int
    """Explicito na ficha, nunca derivado de nivel ou CR por tabela.

    Tabela de proficiencia e conteudo; deixar o motor deduzi-la seria botar
    conteudo dentro da regra, e o primeiro monstro que fugir da tabela viraria
    um caso especial no codigo.
    """

    speed_ft: int
    attacks: tuple[AttackProfile, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnBudget:
    """O que ainda da para fazer neste turno.

    Acao bonus e reacao ficam de fora agora. Nao e esquecimento: `TurnBudget` e
    frozen, entao acrescentar dois bools com default depois nao quebra save
    nenhum. Eles entram junto com a primeira mecanica que os consuma, como
    manda a regra de "mecanica nova entra junto com teste".

    O movimento e `int` de pes, e nao um bool de "ja andou": Dash e terreno
    dificil precisam de um orcamento, nao de uma chave liga-desliga.
    """

    action_available: bool
    movement_remaining_ft: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Combatant:
    """Uma criatura **neste** combate: o que e volatil e so dela."""

    id: CreatureId
    statblock_id: StatblockId
    team: str
    """String livre, nao enum. Tres faccoes, neutros e monstro que troca de
    lado no meio da luta nao migram um enum sem bump de schema."""

    hp: HitPoints
    budget: TurnBudget

    position: Position
    """Sem default, e isso e uma escolha.

    Um default aqui pareceria manter os saves v1 carregando, e nao manteria --
    `serde._campo` levanta na chave ausente, com ou sem default no Python. O que
    faz save antigo carregar e a migracao, e deixar o campo obrigatorio impede
    que alguem acredite no contrario."""


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnOrder:
    """A ordem de iniciativa e onde estamos nela."""

    order: tuple[CreatureId, ...]
    """Fixada em `start_combat`. Ninguem sai da ordem ao cair -- sair mudaria
    os indices de todo mundo no meio da rodada."""

    current: CreatureId
    """De quem e o turno. Guardado como **id e nunca como indice**: indice e uma
    classe inteira de bug de deslocamento que simplesmente deixa de existir."""

    round_number: int
    """Comeca em 1."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CombatState:
    """O estado inteiro do combate. Nada fora daqui.

    `Mapping` e nao `dict` nas colecoes: mypy ja barra `state.combatants[x] = y`
    em tempo de checagem, sem precisar de um guardiao em tempo de execucao.
    """

    statblocks: Mapping[StatblockId, Statblock]
    combatants: Mapping[CreatureId, Combatant]
    turn_order: TurnOrder
    rng: RngState
    """O RNG **e** estado. Sem isto, salvar e recarregar no meio de uma rodada
    mudaria o futuro do combate, e a promessa de determinismo valeria so para
    combates rodados de uma sentada."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CombatOutcome:
    """Como o combate terminou.

    Mora em `model.py`, e nao em `results.py`, por um motivo estrutural:
    `events.CombatEnded` precisa dele e `results` precisa de `events`. Em
    `results`, as dependencias fechariam um ciclo -- e referencia adiante em
    string nao salvaria o `serde`, que precisa do simbolo em tempo de execucao.

    Nunca e guardado no `CombatState`: quem quer saber chama
    `engine.combat_result(state)`. Guardar criaria um segundo lugar onde a
    verdade pode ficar velha, e ele se perderia no round-trip do save.
    """

    winning_team: str | None
    """`None` quer dizer **aniquilacao mutua**, e nao "ainda rolando".

    Combate em andamento e `combat_result(state) is None`, que e outra coisa.
    Misturar os dois foi um bug real numa das propostas de arquitetura: com
    `str | None` sozinho, o combate nunca fechava em empate.
    """

    last_round: int

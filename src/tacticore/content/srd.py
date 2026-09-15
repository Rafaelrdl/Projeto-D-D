"""Duas fichas e o encontro que as usa.

Construidas pelos construtores de verdade, e nao por `core.testing` -- aqueles
sao andaime de teste, cheios de default conveniente, e conteudo de jogo nao
deve herdar default nenhum sem alguem ter escolhido.

.. warning::
   `DUELISTA.estoque` usa ``Ability.FOR`` com forca 10, o que da +0 num duelista
   de DES 17. Isso **nao** e escolha de design: e o default de
   `core.testing.make_attack` que entrou sem ninguem olhar quando estas fichas
   moravam dentro de `tests/golden/test_encounters.py`. Esta copiado como
   estava, de proposito -- a mudanca de casa precisa ser de endereco e nao de
   valor, senao nao da para provar que ela foi neutra comparando os goldens.

   Corrigir para `Ability.DES` e outro commit, com os quatro goldens regravados
   e a frase de justificativa que o `tests/golden/README.md` exige.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from tacticore.core.dice import parse_dice
from tacticore.core.engine import Participant
from tacticore.core.enums import Ability
from tacticore.core.ids import AttackId, CreatureId, StatblockId
from tacticore.core.model import Abilities, AttackProfile, Position, Statblock

BRUTAMONTES: Final = Statblock(
    id=StatblockId("brutamontes"),
    name="Brutamontes",
    abilities=Abilities(
        forca=16,
        destreza=8,
        constituicao=10,
        inteligencia=10,
        sabedoria=10,
        carisma=10,
    ),
    armor_class=13,
    max_hp=14,
    proficiency_bonus=2,
    speed_ft=30,
    attacks=(
        AttackProfile(
            id=AttackId("machado"),
            name="Machado",
            ability=Ability.FOR,
            proficient=True,
            damage=parse_dice("1d12+1"),
        ),
    ),
)
"""Lento e forte: DES 8 costuma agir por ultimo, e o d12 fecha combate rapido."""

DUELISTA: Final = Statblock(
    id=StatblockId("duelista"),
    name="Duelista",
    abilities=Abilities(
        forca=10,
        destreza=17,
        constituicao=10,
        inteligencia=10,
        sabedoria=10,
        carisma=10,
    ),
    armor_class=15,
    max_hp=11,
    proficiency_bonus=3,
    speed_ft=35,
    attacks=(
        AttackProfile(
            id=AttackId("estoque"),
            name="Estoque",
            # Ver o aviso no topo do modulo: FOR aqui e heranca de default, nao
            # escolha. Nao corrigir neste commit.
            ability=Ability.FOR,
            proficient=True,
            damage=parse_dice("1d8+1d4"),
        ),
    ),
)
"""Rapido e fragil: DES 17 quase sempre abre a rodada, e 11 de vida nao perdoa."""

CATALOGO: Final[Mapping[StatblockId, Statblock]] = {
    BRUTAMONTES.id: BRUTAMONTES,
    DUELISTA.id: DUELISTA,
}


DISTANCIA_DE_ABERTURA = 4
"""Quatro casas, ou seja 20 pes: fora do alcance de qualquer arma corpo a corpo.

Comecar colado tornaria o movimento decorativo -- o combate inteiro caberia em
ataques, e o grid nao apareceria no log. Comecar longe demais gastaria rodadas
so andando. Quatro casas resolvem em um deslocamento e obrigam o primeiro turno
a ser uma escolha."""


def duelo(
    *,
    heroi: str = "bruto",
    vilao: str = "lamina",
) -> tuple[Participant, ...]:
    """O encontro de dois: brutamontes contra duelista, um de cada lado."""
    return (
        Participant(
            id=CreatureId(heroi),
            statblock_id=BRUTAMONTES.id,
            team="herois",
            position=Position(x=0, y=0),
        ),
        Participant(
            id=CreatureId(vilao),
            statblock_id=DUELISTA.id,
            team="viloes",
            position=Position(x=DISTANCIA_DE_ABERTURA, y=0),
        ),
    )

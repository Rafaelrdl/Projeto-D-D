"""A ficha do arcanista e o truque que ela existe para rodar.

Mora em modulo proprio, e nao ao lado das outras duas em `srd.py`, por uma
razao que so tem endereco aqui: **esta ficha nao pode entrar no `CATALOGO`**.
`start_combat` guarda o catalogo inteiro dentro do estado e `fingerprint` e
sha256 disso, entao acrescenta-la ao dicionario mudaria o `final_fingerprint`
dos seis goldens de encontro num commit em que nenhuma regra mudou -- e
`_diagnostico` classificaria isso como "regressao ate prova em contrario", que
e a pior das tres mensagens e a que manda procurar bug onde nao ha.

Um comentario tres linhas acima do dicionario em `srd.py` nao sobreviveria ao
primeiro leitor que achasse a ausencia um esquecimento. Um modulo separado
sobrevive: para pos-la no catalogo, alguem precisa primeiro passar por aqui.

Pelo mesmo motivo um degrau acima, ela **nao** entra em
`tacticore.content.__all__`.
"""

from __future__ import annotations

from typing import Final

from tacticore.core.dice import parse_dice
from tacticore.core.enums import Ability
from tacticore.core.ids import AttackId, StatblockId
from tacticore.core.model import Abilities, AttackProfile, Statblock

RAIO_DE_FOGO: Final = AttackProfile(
    id=AttackId("raio_de_fogo"),
    name="Raio de Fogo",
    ability=Ability.INT,
    proficient=True,
    # 1d10 e o dano de 1o nivel, congelado. O truque escala com o NIVEL do
    # conjurador na SRD (2d10 no 5o, 3d10 no 11o, 4d10 no 17o) e `Statblock`
    # nao tem nivel -- ver `docs/srd-atribuicao.md`.
    damage=parse_dice("1d10"),
    # A razao de ser desta ficha. A SRD manda somar o modificador "ao atacar
    # com uma arma"; para magia, ela manda a descricao dizer quais dados rolar
    # e se ha modificador. A de Raio de Fogo nao manda somar nada.
    adds_ability_to_damage=False,
    # 120 pes, e sem faixa longa: alcance de magia e um numero so, e a
    # penalidade de alcance longo e propriedade de ARMA. Igualar os dois diz
    # "nao ha longe", que e a mesma leitura que a migracao v3->v4 fez para toda
    # arma corpo a corpo.
    range_ft=120,
    long_range_ft=120,
)
"""O truque de ataque que este motor ja rodava quase inteiro sem saber.

Acerto por d20 com `INT + proficiencia`, que e exatamente o "spell attack
bonus" da SRD; 120 pes validados pela grade; desvantagem com inimigo colado,
que `derive_advantage_sources` deriva de graca. Faltava so o dano, e era o
campo da fatia B.

O que o motor **descarta** e a clausula final da magia -- um objeto inflamavel
atingido pega fogo se nao estiver sendo usado ou carregado. Nao ha objeto neste
motor. Esta na tabela de desvios.
"""

ARCANISTA: Final = Statblock(
    id=StatblockId("arcanista"),
    name="Arcanista",
    abilities=Abilities(
        # FOR 8 e a menor do projeto, e hoje nao tem leitor nenhum. E o gancho
        # NOMEADO da fatia C: Empurrar e teste de atributo oposto, e a ficha
        # mais facil de derrubar e a que mais sofre por ficar caida.
        forca=8,
        destreza=14,
        constituicao=12,
        # INT 16 da +3, que com proficiencia +2 da ataque +5 -- o MESMO +5 do
        # machado do brutamontes. A pontaria desta ficha e de proposito um
        # numero que o projeto ja conhece: a unica coisa nova nela e o alcance.
        inteligencia=16,
        sabedoria=12,
        carisma=10,
    ),
    # 10 + DES 2, sem armadura: a menor CA do projeto.
    armor_class=12,
    max_hp=10,
    proficiency_bonus=2,
    # 30 pes, o deslocamento humano padrao da SRD -- e **hoje ele e inerte**,
    # o que vale dizer em voz alta em vez de inventar uma historia de
    # balanceamento para ele.
    #
    # Medido, 200 seeds, arcanista contra brutamontes: com uma politica que
    # atira e fica parado, 25, 30 e 35 dao o MESMO placar (118/200) e zero
    # passos. Com o piloto automatico, deslocamento MAIOR piora o mago (90/200
    # com 25, 63/200 com 30 e com 35), porque `_casa_canonica` so oferece a
    # casa que APROXIMA: neste motor nao existe recuo, e cada pe a mais so
    # entra mais depressa no machado.
    #
    # No dia em que o menu oferecer uma casa que afasta, este numero passa a
    # decidir o combate. Ate la, e flavor honesto.
    speed_ft=30,
    attacks=(RAIO_DE_FOGO,),
)
"""Artilharia: dez de vida, a menor CA do projeto e nenhum ataque de perto.

O combate que ela produz tem a forma certa e esta medido. A 120 pes o mago
ganha 118 de 200; a 20 pes -- a distancia de abertura dos outros encontros --
ganha 16 de 200. Dominante longe, sem resposta colado.

CON, SAB e CAR nao tem leitor nenhum no motor, e isto esta escrito aqui em vez
de justificado: inventar razao para numero que ninguem le e exatamente como
nasce um campo sem consumidor.
"""

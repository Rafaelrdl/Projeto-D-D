# Atribuição e desvios da SRD 5.1

## Atribuição

Este trabalho inclui material da System Reference Document 5.1 ("SRD 5.1") da
Wizards of the Coast LLC, disponível em <https://dnd.wizards.com/resources/systems-reference-document>.
A SRD 5.1 é licenciada sob a Creative Commons Attribution 4.0 International
License, disponível em <https://creativecommons.org/licenses/by/4.0/legalcode>.

## Desvios conscientes

Cada linha aqui é uma simplificação deliberada, não um esquecimento. Quando uma
delas for implementada, a linha sai daqui e vira teste.

Manter esta tabela é obrigação de commit, não de revisão: **toda regra que o
motor simplifica acrescenta uma linha aqui no mesmo commit que a simplifica**
(ADR 0002, decisão 5). Nenhum guardião automático cobra isso.

### Vida, queda e morte

| Regra da SRD | O que fazemos | Por quê |
|---|---|---|
| Criatura a 0 HP fica **Inconsciente**, e ataques contra ela têm vantagem — crítico automático em corpo a corpo a 1,5 m | Criatura a 0 HP só "caiu". Nenhuma vantagem é concedida, e o evento marca `target_was_down` | Vantagem derivada do estado depende de condições existirem. Entra na fatia 3 |
| Testes de resistência contra a morte, estabilização, morte instantânea por excedente ≥ máximo | Nada disso. O excedente é registrado em `HpChanged.overkill` e não faz nada | O excedente guardado agora é o que torna a morte instantânea barata depois |
| Cura, HP temporário | Não existem. `apply_damage` recusa valor negativo em vez de curar | Cura tem regra própria (limite no máximo, efeito em quem está a zero) e merece função própria |

### Ataque e dano

| Regra da SRD | O que fazemos | Por quê |
|---|---|---|
| Armas à distância têm alcance **curto e longo**, com desvantagem no longo | Implementado: `range_ft` é o curto, `long_range_ft` é a parede, e entre os dois há desvantagem | — |
| Tipo de dano, resistência, vulnerabilidade, imunidade | Dano não tem tipo | Tipo sem resistência implementada é campo inerte no objeto mais serializado do projeto |
| Multiataque | Uma ação, um ataque | Muda o contrato de consumo do RNG por ação |
| Corpo a corpo e à distância são **tipos de arma**, e não consequência do alcance | "À distância" é `range_ft > 5` | É o mesmo conjunto enquanto não houver arma de haste. Uma alabarda tem alcance 10 e é corpo a corpo: no dia em que uma entrar, `AttackProfile` ganha o tipo e este critério sai |
| Acuidade (usar DES com arma de acuidade) | `AttackProfile.ability` é um atributo só | Vira `tuple[Ability, ...]` quando entrar |
| Atacar a si mesmo é mecanicamente legal | Recusado com `SELF_TARGET_NOT_ALLOWED` | Na prática é sempre bug de chamador ou de IA. A exceção volta como campo com default quando houver efeito em área |
| Bônus de proficiência derivado de nível ou CR | Campo explícito na ficha | Tabela de proficiência é conteúdo; deixar o motor deduzi-la é pôr conteúdo dentro da regra |
| Truques de dano escalam com o **nível do personagem** (Raio de Fogo: 1d10, depois 2d10 no 5º, 3d10 no 11º e 4d10 no 17º) | A ficha congela `1d10`, o valor de 1º nível | Não existe nível no motor, e pelo mesmo motivo que `proficiency_bonus` é campo explícito: tabela de progressão é conteúdo. Escalar exigiria um campo de nível lido só aqui |
| Raio de Fogo acende um **objeto inflamável** atingido, se ele não estiver sendo usado ou carregado | Nada acontece: o motor roda só a metade de ataque e dano | Não existe objeto neste motor, nem alvo que não seja criatura. É a cláusula que impede dizer que o truque "roda inteiro" |
| Magia tem escola, nível, tempo de conjuração, componentes (V, S, M), duração e concentração | Raio de Fogo é um `AttackProfile` como o machado: atributo, proficiência, dado e alcance | Um truque de **ataque** é a magia da SRD cujo efeito mais se aproxima de "role o ataque, role o dano" — e nem ele chega lá (ver a linha acima). Nenhum dos outros campos teria leitor, e campo sem leitor no objeto mais serializado do projeto é o erro que `attack_bonus` já custou nove commits |

### Iniciativa e turno

| Regra da SRD | O que fazemos | Por quê |
|---|---|---|
| Empate de iniciativa é decidido pelo mestre | Desempate por valor de Destreza e, persistindo, por id | Não há mestre. Empate resolvido pela ordem de montagem mataria o determinismo em silêncio |
| Ação bônus e reação | `TurnBudget` só tem ação e movimento | Entram junto com a primeira mecânica que as consuma |
| Ataque de oportunidade | Não existe | Faz o movimento consumir RNG pela primeira vez |
| Caído: o caído só pode **rastejar**, e rastejar custa o dobro | Ele anda normalmente | Custo de terreno não existe; a grade é vazia e sem terreno difícil |
| Caído vem de **Empurrar** (opção da ação de Ataque) ou de magia | A única fonte é o encontro: `Participant.conditions` | Empurrar é teste de atributo oposto — d20 contra d20 — e com o quadro fixo de dois d20 são quatro dados por empurrão. Seria a primeira mecânica a consumir RNG fora de ataque, e o ADR 0002 manda que ela entre sozinha |
| **Cego**, e as outras condições da SRD | Só Caído existe | As três fontes de Cego — magia, salvaguarda e iluminação — estão fora de escopo por decisão escrita, e nada removeria a condição. Um cego nasceria cego e morreria cego |

### Grade e movimento

| Regra da SRD | O que fazemos | Por quê |
|---|---|---|
| Variante opcional: cada segunda diagonal custa 10 pés em vez de 5 | Toda diagonal custa 5 pés (a regra de grade padrão) | A variante corrige a geometria e cobra por isso uma conta **com estado** — lembrar quantas diagonais já foram gastas no turno — dentro do que hoje é uma função pura de quatro inteiros |
| Terreno difícil, obstáculos, cobertura | A grade é vazia e infinita | Nada disso tem consumidor ainda; terreno sem alcance e sem linha de visão seria campo inerte |
| Mover-se através da casa de um aliado é permitido; terminar nela não é | Duas criaturas nunca ocupam a mesma casa, e o movimento não tem trajeto — só origem e destino | Sem trajeto, "atravessar" não é uma pergunta que o motor consiga fazer |

### Notação de dados

| Regra da SRD | O que fazemos | Por quê |
|---|---|---|
| — | `2d6-1d4` (termo de dados negativo) é recusado pela gramática | Não existe nas regras implementadas, e tornaria ambígua a pergunta "o que dobra no crítico?" |

---

A tabela nasceu com **onze** linhas, todas retroativas: ficou vazia do commit 1
ao commit 20 enquanto o `CLAUDE.md` a declarava obrigatória, e nenhum dos
desvios da etapa 1 tinha sido anotado no momento em que foi feito.

É por isso que o ADR 0002 torna a manutenção dela obrigação de commit, e não de
revisão. Desde então ela cresce junto com o código — a fatia 2 acrescentou as
quatro linhas de grade e movimento e a de corpo a corpo contra à distância, no
mesmo commit em que cada simplificação entrou.

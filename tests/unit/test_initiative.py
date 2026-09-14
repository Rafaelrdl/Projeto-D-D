"""A chave de ordenacao da iniciativa.

Testada isolada do combate porque e uma funcao de tres numeros e um id. O que
importa aqui e que ela seja uma ordem **total**: se sobrar empate de verdade,
a ordem cai na ordem de montagem do encontro e o determinismo morre em
silencio -- dois goblins identicos e o caso comum, nao o exotico.
"""

from __future__ import annotations

from tacticore.core.ids import CreatureId
from tacticore.core.rules import InitiativeEntry, ability_modifier, initiative_sort_key


def entrada(creature: str, d20: int, dex_score: int) -> InitiativeEntry:
    mod = ability_modifier(dex_score)
    return InitiativeEntry(
        creature=CreatureId(creature),
        d20=d20,
        dex_mod=mod,
        dex_score=dex_score,
        total=d20 + mod,
    )


def ordenar(*entradas: InitiativeEntry) -> list[str]:
    return [str(e.creature) for e in sorted(entradas, key=initiative_sort_key)]


def test_total_maior_vem_primeiro():
    assert ordenar(entrada("a", 5, 10), entrada("b", 18, 10)) == ["b", "a"]


def test_empate_no_total_desempata_por_destreza():
    """`a` rolou mais no dado, mas `b` tem mais Destreza e o mesmo total."""
    assert ordenar(entrada("a", 15, 10), entrada("b", 13, 14)) == ["b", "a"]


def test_destreza_16_e_17_desempatam_apesar_do_mesmo_modificador():
    """O motivo de a chave usar o VALOR e nao o modificador de Destreza."""
    assert ability_modifier(16) == ability_modifier(17)
    assert ordenar(entrada("a", 10, 16), entrada("b", 10, 17)) == ["b", "a"]


def test_empate_absoluto_desempata_pelo_id():
    """Arbitrario, mas estavel -- e portanto reproduzivel."""
    assert ordenar(entrada("zora", 10, 12), entrada("alma", 10, 12)) == ["alma", "zora"]


def test_a_ordem_nao_depende_da_ordem_de_entrada():
    a, b, c = entrada("a", 10, 12), entrada("b", 10, 12), entrada("c", 20, 8)
    assert ordenar(a, b, c) == ordenar(c, b, a) == ordenar(b, c, a)


def test_a_chave_e_uma_ordem_total():
    """Nenhum par distinto pode ter a mesma chave."""
    entradas = [
        entrada(nome, d20, dex) for nome in ("a", "b") for d20 in (1, 10, 20) for dex in (8, 16, 17)
    ]
    chaves = [initiative_sort_key(e) for e in entradas]
    assert len(set(chaves)) == len(chaves)


def test_destreza_negativa_nao_quebra_a_ordem():
    assert ordenar(entrada("lento", 20, 4), entrada("rapido", 18, 20)) == ["rapido", "lento"]

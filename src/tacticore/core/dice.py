"""Notacao de dados: gramatica estrita na entrada, estrutura no estado.

``"1d8+3"`` e **formato de autoria**. Ele entra uma vez, vindo de fora do
motor, e vira ``DamageExpr``. O estado de combate guarda a estrutura, nunca a
string: reparsear a cada rolagem seria trabalho repetido, e -- pior -- daria a
uma expressao malformada varias chances de entrar no jogo em vez de uma.

A gramatica::

    expr := term (('+' | '-') term)*
    term := [count] ('d' | 'D') faces | inteiro

Regras que valem a pena saber de cor:

- ``d8`` e ``1d8`` sao a mesma coisa, e ``D`` maiusculo vale.
- Espaco e tolerado nas pontas e em volta dos operadores, e **so ali**.
  ``1d8 3`` e erro, e nao ``1d83``.
- ``1 <= count <= 100`` e ``2 <= faces <= 1000``. Os limites existem para que
  ``"9999d9999"`` vindo de um arquivo de dados vire erro em vez de travar o
  processo.
- ``-`` so aparece antes de um termo inteiro. ``1d8-1`` vale, ``2d6-1d4`` nao:
  subtrair dados nao existe nas regras que estamos implementando, e um termo
  de dados negativo tornaria ambigua a pergunta "o que dobra no critico?".
- A ordem dos termos e preservada e termos iguais **nao** sao agrupados:
  ``1d6+1d6`` sao dois termos. No critico cada um dobra por conta propria, e
  ``doubles_on_crit`` e por termo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tacticore.core.errors import DiceSyntaxError
from tacticore.core.rng import RngState, roll_dice

MIN_COUNT = 1
MAX_COUNT = 100
MIN_FACES = 2
MAX_FACES = 1000

_TERMO = re.compile(r"(?:(?P<count>\d+)?[dD](?P<faces>\d+))|(?P<flat>\d+)")


def _pular_espaco(text: str, pos: int) -> int:
    """Avanca sobre espaco em branco.

    Espaco e tolerado nas pontas e em volta dos operadores, e **so ali**: um
    termo nao pode ter espaco dentro. Remover todo espaco antes de parsear
    seria mais curto e leria `"1d8 3"` como `"1d83"` -- um d83 silencioso onde
    o autor quis dois termos e esqueceu o operador.
    """
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


@dataclass(frozen=True, slots=True, kw_only=True)
class DiceTerm:
    """Um grupo de dados iguais, como ``2d6``."""

    count: int
    faces: int
    doubles_on_crit: bool = True
    """Se este termo dobra a contagem num acerto critico.

    Praticamente todo dano dobra, entao o default e `True`. O campo existe
    porque o primeiro dado bonus que **nao** dobra chega junto com magias, e
    sem ele essa mecanica exigiria mudar o formato serializado. Com ele, e um
    bool com default: campo novo, save antigo continua carregando.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class DamageExpr:
    """A expressao de dano ja estruturada: os grupos de dados mais um fixo."""

    terms: tuple[DiceTerm, ...] = ()
    flat: int = 0


def _erro(texto: str, motivo: str) -> DiceSyntaxError:
    return DiceSyntaxError(f"notacao de dados invalida {texto!r}: {motivo}")


def _termo_de_dados(texto: str, count_bruto: str | None, faces_bruto: str) -> DiceTerm:
    count = 1 if count_bruto is None else int(count_bruto)
    faces = int(faces_bruto)

    if not MIN_COUNT <= count <= MAX_COUNT:
        raise _erro(texto, f"quantidade de dados fora de {MIN_COUNT}..{MAX_COUNT}: {count}")
    if not MIN_FACES <= faces <= MAX_FACES:
        raise _erro(texto, f"faces fora de {MIN_FACES}..{MAX_FACES}: {faces}")

    return DiceTerm(count=count, faces=faces)


def parse_dice(text: str) -> DamageExpr:
    """Le a notacao de autoria e devolve a expressao estruturada.

    Levanta `DiceSyntaxError` em qualquer coisa que nao case com a gramatica,
    incluindo sobra no fim da string -- aceitar ``"1d8lixo"`` como ``1d8`` e o
    tipo de tolerancia que vira bug de dano meses depois.
    """
    fim = len(text)
    pos = _pular_espaco(text, 0)
    if pos == fim:
        raise _erro(text, "expressao vazia")
    if text[pos] in "+-":
        raise _erro(text, "a expressao nao pode comecar com sinal")

    terms: list[DiceTerm] = []
    flat = 0
    sinal = 1

    while True:
        casamento = _TERMO.match(text, pos)
        if casamento is None:
            raise _erro(text, f"nao entendi o termo que comeca em {text[pos:]!r}")

        if casamento.group("flat") is not None:
            flat += sinal * int(casamento.group("flat"))
        elif sinal < 0:
            raise _erro(text, "termo de dados negativo nao existe nas regras")
        else:
            terms.append(_termo_de_dados(text, casamento.group("count"), casamento.group("faces")))

        pos = _pular_espaco(text, casamento.end())
        if pos == fim:
            return DamageExpr(terms=tuple(terms), flat=flat)

        operador = text[pos]
        if operador not in "+-":
            raise _erro(text, f"esperava + ou - e achei {operador!r}")
        sinal = 1 if operador == "+" else -1
        pos = _pular_espaco(text, pos + 1)
        if pos == fim:
            raise _erro(text, f"a expressao termina em {operador!r}, sem termo depois")


@dataclass(frozen=True, slots=True, kw_only=True)
class DieRoll:
    """Um dado fisico rolado, com de onde ele veio.

    Dado a dado e nao so a soma: o teste de critico vira uma asercao sobre a
    lista (`quantos dados sairam, quais vieram do critico`) em vez de aritmetica
    invertida sobre o total, que passaria por acidente com o numero certo pelo
    motivo errado.
    """

    term_index: int
    """Indice do termo na expressao **original**, para o log mapear no que o
    autor escreveu mesmo depois da expansao do critico."""

    faces: int
    value: int
    from_crit: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class DamageRoll:
    """O resultado de uma rolagem de dano, com a conta aberta."""

    dice: tuple[DieRoll, ...]
    flat: int
    ability_bonus: int
    critical: bool
    total: int
    """Soma **crua**: `sum(dice) + flat + ability_bonus`, podendo dar negativo.

    O piso em zero mora num lugar so, `apply_damage`. Pisar aqui quebraria a
    identidade acima em qualquer `1d4-3`, e a conta decomposta do log deixaria
    de fechar exatamente nos casos em que alguem for conferir.
    """


def expand_crit(expr: DamageExpr) -> DamageExpr:
    """Dobra a **contagem** de cada termo que dobra no critico.

    Dobrar a contagem (`1d8` -> `2d8`) nao e o mesmo que dobrar o resultado
    (`1d8 * 2`): as distribuicoes sao diferentes, e a SRD pede a primeira. O
    fixo nao e tocado -- ele entra uma vez so.
    """
    return DamageExpr(
        terms=tuple(
            DiceTerm(count=t.count * 2, faces=t.faces, doubles_on_crit=t.doubles_on_crit)
            if t.doubles_on_crit
            else t
            for t in expr.terms
        ),
        flat=expr.flat,
    )


def roll_damage(
    rng: RngState,
    expr: DamageExpr,
    *,
    ability_bonus: int,
    critical: bool,
) -> tuple[DamageRoll, RngState]:
    """Rola o dano, um dado fisico por posicao do stream, da esquerda para a direita.

    No critico os dados extras de um termo saem **logo depois** dos originais
    daquele termo, e nao no fim da expressao: `1d8+1d6` critico consome d8, d8,
    d6, d6. E a mesma ordem que `expand_crit` descreve, e ela e contrato --
    trocar a ordem desloca todo o resto do combate.
    """
    efetiva = expand_crit(expr) if critical else expr

    dice: list[DieRoll] = []
    current = rng
    for indice, (original, termo) in enumerate(zip(expr.terms, efetiva.terms, strict=True)):
        valores, current = roll_dice(current, termo.count, termo.faces)
        dice.extend(
            DieRoll(
                term_index=indice,
                faces=termo.faces,
                value=valor,
                from_crit=posicao >= original.count,
            )
            for posicao, valor in enumerate(valores)
        )

    total = sum(d.value for d in dice) + expr.flat + ability_bonus
    roll = DamageRoll(
        dice=tuple(dice),
        flat=expr.flat,
        ability_bonus=ability_bonus,
        critical=critical,
        total=total,
    )
    return roll, current

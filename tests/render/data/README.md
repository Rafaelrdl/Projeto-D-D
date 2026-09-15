# Golden de apresentação

`duelo.txt` é o combate da seed padrão narrado em texto, e `tabuleiro.txt` é o
mesmo combate retratado na abertura e no fim.

**Este golden se regrava sem cerimônia.** Ele é de apresentação: um diff aqui é
quase sempre "mudei a redação de uma linha", e não há nada a justificar.

```bash
uv run pytest tests/render --update-golden
```

É o oposto de `tests/golden/data/`, onde um diff significa que o motor passou a
calcular outra coisa e o commit precisa dizer qual regra mudou. Os dois vivem em
pastas separadas exatamente para que a disciplina de um não contamine o outro —
misturados, ou você justifica mudanças de vírgula, ou para de justificar
mudanças de regra.

**Quando o diff for evento novo aparecendo no log**, e não redação: regrave
aqui, mas a explicação vai no commit de `tests/golden/`.

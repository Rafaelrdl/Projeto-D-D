"""Fumaca: o pacote existe, esta instalado e e o do `src/`.

Sem src layout, `import tacticore` pegaria o diretorio de trabalho e a suite
passaria a testar os arquivos soltos do repositorio em vez do pacote instalado
-- diferenca que so aparece no CI, e tarde.
"""

from __future__ import annotations

from pathlib import Path

import tacticore
import tacticore.core


def test_pacote_resolve_para_o_src_layout():
    raiz = Path(tacticore.__file__).parent
    assert raiz.name == "tacticore"
    assert raiz.parent.name == "src", (
        f"`tacticore` resolveu para {raiz}, fora de src/: o pacote instalado nao e o do repositorio"
    )


def test_pacote_se_declara_tipado():
    marcador = Path(tacticore.__file__).parent / "py.typed"
    assert marcador.is_file(), "py.typed ausente: consumidores perdem a tipagem"


def test_core_expoe_api_publica():
    assert "apply" in tacticore.core.__all__

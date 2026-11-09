"""Guarda de pureza (AGENTS.md): estes módulos não importam Panda3D, Qt ou Win32."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src" / "sejoga"
_PROIBIDOS = {"panda3d", "direct", "pyside6", "pyqt5", "pyqt6", "shiboken6", "win32", "pywin32"}


@pytest.mark.parametrize("relativo", [
    "nucleo/model.py", "nucleo/rig.py", "nucleo/assets.py", "config.py",
    "nucleo/malha_corte.py", "nucleo/cinematica.py", "animacao/dedos_cascata.py", "animacao/dedos_tuning.py",
])
def test_modulo_nao_importa_engine(relativo: str) -> None:
    arvore = ast.parse((_SRC / relativo).read_text(encoding="utf-8"))
    importados: list[str] = []

    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.extend(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.append(no.module)

    for modulo in importados:
        raiz = modulo.lower().split(".")[0]
        assert raiz not in _PROIBIDOS and not raiz.startswith("win32"), f"{relativo}: {modulo}"

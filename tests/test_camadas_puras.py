"""Guarda de camadas (AGENTS.md): pacotes puros não importam engine nem camadas acima."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src" / "sejoga"
_PROIBIDOS = {
    "panda3d",
    "direct",
    "pyside6",
    "pyqt5",
    "pyqt6",
    "shiboken6",
    "win32",
    "pywin32",
}
_PACOTES_PUROS = ("nucleo", "rig_mapa", "animacao")
_MODULOS_RAIZ_PUROS = ("configuracao.py",)


def _listar_modulos_puros() -> list[str]:
    relativos = [
        caminho.relative_to(_SRC).as_posix()
        for pacote in _PACOTES_PUROS
        for caminho in sorted((_SRC / pacote).glob("*.py"))
    ]
    return relativos + [nome for nome in _MODULOS_RAIZ_PUROS if (_SRC / nome).exists()]


def _listar_importados(relativo: str) -> list[str]:
    arvore = ast.parse((_SRC / relativo).read_text(encoding="utf-8-sig"))
    importados: list[str] = []

    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.extend(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.append(no.module)

    return importados


@pytest.mark.parametrize("relativo", _listar_modulos_puros())
def test_modulo_puro_sem_engine_nao_importa_panda_qt_win32(relativo: str) -> None:
    for modulo in _listar_importados(relativo):
        raiz = modulo.lower().split(".")[0]
        assert raiz not in _PROIBIDOS, f"{relativo}: {modulo}"
        assert not raiz.startswith("win32"), f"{relativo}: {modulo}"


_MODULOS_NUCLEO = [m for m in _listar_modulos_puros() if m.startswith("nucleo/")]


@pytest.mark.parametrize("relativo", _MODULOS_NUCLEO)
def test_modulo_nucleo_camada_base_nao_importa_animacao_nem_rig_mapa(
    relativo: str,
) -> None:
    for modulo in _listar_importados(relativo):
        assert not modulo.startswith("sejoga.animacao"), f"{relativo}: {modulo}"
        assert not modulo.startswith("sejoga.rig_mapa"), f"{relativo}: {modulo}"

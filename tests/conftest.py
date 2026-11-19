"""Configuração compartilhada do pytest: pré-carrega PySide6 antes de Panda3D no Windows."""

from __future__ import annotations

from contextlib import suppress

with suppress(ImportError):
    from PySide6 import QtCore  # noqa: F401

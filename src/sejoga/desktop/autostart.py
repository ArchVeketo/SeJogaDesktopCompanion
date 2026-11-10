"""Autostart via atalho .lnk na pasta Startup do usuário (puro Win32).

A fonte de verdade do autostart é um atalho ``SeJoga Companion.lnk`` na pasta
``Startup`` do usuário apontando para o ``SeJogaLauncher.exe`` instalado — o
mesmo alvo dos atalhos do instalador, nunca ``HKCU\\...\\Run``.

Guard clause no estilo de ``reescrever_canal_channel_info``: em modo fonte/dev
(sem launcher instalado), ``ativar``/``desativar`` são inertes e retornam
``False``; ``esta_ativo`` verifica apenas a existência do atalho.

Este módulo só importa Win32 (via pywin32); nunca Panda3D nem Qt.
"""

from __future__ import annotations

import os
from pathlib import Path

from sejoga.distribuicao.atualizador import installed_launcher

NOME_ATALHO = "SeJoga Companion.lnk"


def caminho_atalho() -> Path:
    """``%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\<atalho>``."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / NOME_ATALHO


def esta_ativo() -> bool:
    """Autostart está ligado se o atalho existir na pasta Startup."""
    return caminho_atalho().is_file()


def ativar() -> bool:
    """Cria o atalho apontando para o launcher instalado.

    Guard clause: sem launcher instalado (modo fonte/dev) é inerte e retorna
    ``False``.
    """
    launcher = installed_launcher()

    if launcher is None:
        return False

    import pythoncom
    import win32com.client

    atalho = caminho_atalho()
    atalho.parent.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        link = shell.CreateShortcut(str(atalho))
        link.TargetPath = str(launcher)
        link.WorkingDirectory = str(launcher.parent)
        link.IconLocation = str(launcher)
        link.Save()
    finally:
        pythoncom.CoUninitialize()

    return True


def desativar() -> bool:
    """Remove o atalho da pasta Startup.

    Guard clause: sem launcher instalado (modo fonte/dev) é inerte e retorna
    ``False``.
    """
    if installed_launcher() is None:
        return False

    caminho_atalho().unlink(missing_ok=True)

    return True

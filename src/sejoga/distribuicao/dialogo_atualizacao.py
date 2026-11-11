"""Non-blocking update checks; the stable agent applies machine-wide runtime packages."""

from __future__ import annotations

import contextlib
import json
import logging
import threading
from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

from sejoga.configuracao import Settings, load_settings
from sejoga.distribuicao.atualizador import (
    CHANNELS,
    Update,
    check_update,
    installed_launcher,
    installed_release,
)


class UpdateDialog(QDialog):
    """Diálogo que confere, baixa e aplica a atualização."""

    completed = Signal(object)

    def __init__(
        self, on_install_started: Callable[[], None], settings: Settings | None = None, parent=None
    ):
        """Monta o diálogo e inicia a consulta ao feed."""
        super().__init__(parent)
        self.setWindowTitle("Atualizações — SeJoga Companion")
        self.setMinimumWidth(420)
        # O canal efetivo vem da config do usuário, não do release-info.json.
        self._settings = settings or load_settings()
        self.current = installed_release()
        self.launcher = installed_launcher()
        self.on_install_started = on_install_started
        self.candidate: Update | None = None
        self._busy = False
        layout = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.action = QPushButton("Buscar atualizações")
        self.action.clicked.connect(self._action)
        layout.addWidget(self.action)
        self.completed.connect(self._completed)
        if self.launcher:
            self.status.setText(
                f"Canal atual: {self._canal()}\n"
                "As atualizações vêm das releases oficiais do projeto."
            )
        else:
            self.status.setText(
                "Instale o SeJoga pelo instalador oficial para receber "
                "atualizações por aqui."
            )
            self.action.setEnabled(False)

    def _canal(self) -> str:
        """Canal escolhido na config (fonte de verdade da checagem)."""
        return self._settings.update.channel

    def atualizar_config(self, settings: Settings) -> None:
        """Mantém o diálogo sincronizado quando o usuário troca o canal."""
        self._settings = settings
        self.candidate = None
        if self.launcher and not self._busy:
            self.status.setText(
                f"Canal atual: {self._canal()}\n"
                "As atualizações vêm das releases oficiais do projeto."
            )
            self.action.setText("Buscar atualizações")

    def _start(self, canal: str) -> None:
        self._busy = True
        self.action.setEnabled(False)

        def run():
            try:
                result = (canal, "checked", check_update(self.current, channel=canal))
            except Exception as exc:
                logging.getLogger("sejoga").warning("Update failed: %s", exc)
                result = (canal, "error", str(exc))
            with contextlib.suppress(RuntimeError):
                self.completed.emit(result)

        threading.Thread(target=run, name="sejoga-updater", daemon=True).start()

    def _action(self) -> None:
        if self._busy or self.launcher is None:
            return
        if self.candidate is None:
            self.status.setText("Buscando atualizações…")
            # O canal da config define qual feed consultar.
            canal = self._canal()
            self._start(canal)
        else:
            self._install()

    def _install(self) -> None:
        if self.launcher is None or self.candidate is None:
            return
        canal = self.candidate.channel
        if canal != self._canal() or canal not in CHANNELS:
            return
        answer = QMessageBox.question(
            self,
            "Aplicar atualização?",
            "O Mário será fechado agora e aparecerá apenas uma barra de progresso enquanto "
            "o atualizador baixa, verifica e instala a nova versão. "
            "O Windows solicitará permissão de administrador para atualizar todos os usuários. "
            "Ao terminar, o Mário reabre automaticamente (se você cancelar a permissão, "
            "ele também volta). Suas configurações serão preservadas.\n\nAtualizar agora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes or canal != self._canal():
            return
        import win32api

        try:
            metadata = json.loads(
                (self.launcher.parent / "channel-info.json").read_text(encoding="utf-8-sig")
            )
            if canal != metadata["channel"]:
                version = win32api.GetFileVersionInfo(str(self.launcher), "\\")
                if version["FileVersionMS"] < (1 << 16 | 1):
                    raise ValueError("Instale o launcher mais recente para trocar de canal.")
            win32api.ShellExecute(
                0, "open", str(self.launcher), f"--update --channel {canal}", str(self.launcher.parent), 1
            )
        except Exception as exc:
            self.status.setText(f"Atualização não iniciada: {exc}")
        else:
            self.accept()
            self.on_install_started()

    def _completed(self, result) -> None:
        self._busy = False
        self.action.setEnabled(True)
        canal, kind, value = result
        if canal != self._canal():
            self.atualizar_config(self._settings)
            return
        if kind == "error":
            self.status.setText(f"Não foi possível buscar atualizações: {value}")
        elif kind == "checked":
            self.candidate = value
            if value is None:
                self.status.setText(
                    f"Nenhuma atualização disponível no canal {self._canal()}."
                )
                self.action.setText("Buscar atualizações")
            else:
                self.status.setText(
                    f"Versão {value.version} disponível · canal {value.channel}\n"
                    f"Download: {value.size / 1024 / 1024:.1f} MB"
                )
                self.action.setText("Atualizar agora")

    def reject(self) -> None:
        """Fecha o diálogo sem aplicar a atualização."""
        # Hiding does not delete the QObject while its worker is running.
        self.hide()

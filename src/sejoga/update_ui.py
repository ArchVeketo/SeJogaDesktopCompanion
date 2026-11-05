"""Non-blocking update checks; the stable agent applies machine-wide runtime packages."""
from __future__ import annotations

import contextlib
import logging
import threading
from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

from .updater import Update, check_update, installed_launcher, installed_release


class UpdateDialog(QDialog):
    completed = Signal(object)

    def __init__(self, on_install_started: Callable[[], None]):
        super().__init__()
        self.setWindowTitle('Atualizações — SeJoga Companion')
        self.setMinimumWidth(420)
        self.current = installed_release()
        self.launcher = installed_launcher()
        self.on_install_started = on_install_started
        self.candidate: Update | None = None
        self._busy = False
        layout = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.action = QPushButton('Verificar atualizações')
        self.action.clicked.connect(self._action)
        layout.addWidget(self.action)
        self.completed.connect(self._completed)
        if self.current and self.launcher:
            self.status.setText(f'Versão {self.current.version} · canal {self.current.channel}\n'
                                'As atualizações vêm das releases oficiais do projeto.')
        else:
            self.status.setText('Instale o SeJoga pelo instalador oficial de release, pré-release '
                                'ou nightly para receber atualizações por aqui.')
            self.action.setEnabled(False)

    def _start(self, work: Callable, kind: str) -> None:
        self._busy = True
        self.action.setEnabled(False)

        def run():
            try:
                result = (kind, work())
            except Exception as exc:
                logging.getLogger('sejoga').warning('Update failed: %s', exc)
                result = ('error', str(exc))
            with contextlib.suppress(RuntimeError):
                self.completed.emit(result)

        threading.Thread(target=run, name='sejoga-updater', daemon=True).start()

    def _action(self) -> None:
        if self._busy or self.current is None:
            return
        if self.candidate is None:
            self.status.setText('Consultando as releases oficiais…')
            current = self.current
            self._start(lambda: check_update(current), 'checked')
        else:
            self._install()

    def _install(self) -> None:
        if self.launcher is None:
            return
        answer = QMessageBox.question(
            self, 'Aplicar atualização?',
            'O atualizador vai baixar e verificar a versão atual deste canal. '
            'O Windows solicitará permissão de administrador para atualizar todos os usuários. '
            'O Mário só será fechado depois da preparação do pacote e será reaberto ao terminar. '
            'Suas configurações serão preservadas.\n\nAtualizar agora?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        import win32api
        try:
            win32api.ShellExecute(0, 'open', str(self.launcher), '--update', str(self.launcher.parent), 1)
        except Exception as exc:
            self.status.setText(f'Atualização não iniciada: {exc}')
        else:
            self.accept()
            self.on_install_started()

    def _completed(self, result) -> None:
        self._busy = False
        self.action.setEnabled(True)
        kind, value = result
        if kind == 'error':
            self.status.setText(f'Não foi possível concluir a atualização: {value}')
        elif kind == 'checked':
            self.candidate = value
            if value is None:
                self.status.setText('Nenhuma atualização compatível encontrada neste canal.')
            else:
                self.status.setText(f'Nova versão: {value.version} · {value.channel}\n'
                                    f'Download: {value.size / 1024 / 1024:.1f} MB')
                self.action.setText('Atualizar agora')

    def reject(self) -> None:
        # Hiding does not delete the QObject while its worker is running.
        self.hide()

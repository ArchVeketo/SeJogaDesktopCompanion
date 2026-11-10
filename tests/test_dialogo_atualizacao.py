"""Fluxo de atualização fecha->barra->reabre, sem exigir GPU/UAC.

Cobre o handoff ao launcher nativo e o disparo do fechamento do companion a
partir dos dois pontos de UI (UpdateDialog da bandeja e SettingsDialog). A barra
de progresso real, a elevação UAC e o reabrir visual são validados na máquina
com GPU (ver docs/validacao-updater-gpu.md)."""
import logging
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

if sys.platform != "win32":
    pytest.skip("Fluxo de atualização é específico do Windows", allow_module_level=True)
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from sejoga.configuracao import Settings
from sejoga.distribuicao.dialogo_atualizacao import UpdateDialog
from sejoga.distribuicao.atualizador import ReleaseInfo, Update


def _app():
    return QApplication.instance() or QApplication([])


def _launcher(tmp_path):
    launcher = tmp_path / "SeJogaLauncher.exe"
    launcher.write_bytes(b"fixture nunca executada")
    (tmp_path / "channel-info.json").write_text(
        '{"channel": "release", "scope": "machine"}', encoding="utf-8")
    return launcher


def test_confirmar_atualizacao_faz_handoff_e_fecha_o_companion(tmp_path):
    """Confirmar dispara ShellExecute(--update), aceita o diálogo e chama o
    callback que fecha o companion (fecha->barra->reabre)."""
    _app()
    launcher = _launcher(tmp_path)
    fechou = []
    with (patch("sejoga.distribuicao.dialogo_atualizacao.installed_release",
                return_value=ReleaseInfo("0.1.0", "release")),
          patch("sejoga.distribuicao.dialogo_atualizacao.installed_launcher", return_value=launcher),
          patch("win32api.ShellExecute") as shell,
          patch.object(QMessageBox, "question",
                       return_value=QMessageBox.StandardButton.Yes)):
        dialog = UpdateDialog(lambda: fechou.append(True), Settings())
        dialog.candidate = Update("0.2.0", "release", "p.zip", "", "a" * 64, 4096, 2)
        dialog._install()
    shell.assert_called_once()
    assert shell.call_args.args[3] == "--update"
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert fechou == [True]
    dialog.close()


def test_recusar_atualizacao_nao_fecha_nem_faz_handoff(tmp_path):
    _app()
    launcher = _launcher(tmp_path)
    fechou = []
    with (patch("sejoga.distribuicao.dialogo_atualizacao.installed_release",
                return_value=ReleaseInfo("0.1.0", "release")),
          patch("sejoga.distribuicao.dialogo_atualizacao.installed_launcher", return_value=launcher),
          patch("win32api.ShellExecute") as shell,
          patch.object(QMessageBox, "question",
                       return_value=QMessageBox.StandardButton.No)):
        dialog = UpdateDialog(lambda: fechou.append(True), Settings())
        dialog.candidate = Update("0.2.0", "release", "p.zip", "", "a" * 64, 4096, 2)
        dialog._install()
    shell.assert_not_called()
    assert fechou == []
    dialog.close()


def test_falha_no_handoff_mantem_o_companion_aberto(tmp_path):
    """Se o ShellExecute falhar, não fecha o companion e mostra o erro."""
    _app()
    launcher = _launcher(tmp_path)
    fechou = []
    with (patch("sejoga.distribuicao.dialogo_atualizacao.installed_release",
                return_value=ReleaseInfo("0.1.0", "release")),
          patch("sejoga.distribuicao.dialogo_atualizacao.installed_launcher", return_value=launcher),
          patch("win32api.ShellExecute", side_effect=OSError("sem shell")),
          patch.object(QMessageBox, "question",
                       return_value=QMessageBox.StandardButton.Yes)):
        dialog = UpdateDialog(lambda: fechou.append(True), Settings())
        dialog.candidate = Update("0.2.0", "release", "p.zip", "", "a" * 64, 4096, 2)
        dialog._install()
    assert fechou == []
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "não iniciada" in dialog.status.text()
    dialog.close()


def test_settings_dialog_sinaliza_fechamento_no_handoff(tmp_path):
    """SettingsDialog também fecha o companion ao delegar ao launcher."""
    from sejoga.desktop.interface import SettingsDialog
    _app()
    launcher = _launcher(tmp_path)
    fechou = []
    with (patch("sejoga.distribuicao.atualizador.installed_launcher", return_value=launcher),
          patch("win32api.ShellExecute") as shell):
        dialog = SettingsDialog(Settings())
        dialog.atualizacao_iniciada.connect(lambda: fechou.append(True))
        dialog._iniciar_atualizacao("release")
    shell.assert_called_once()
    assert shell.call_args.args[3] == "--update"
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert fechou == [True]
    dialog.close()


def test_ao_iniciar_atualizacao_chama_quit_app():
    """O handler do OverlayApp fecha o companion via quit_app."""
    from sejoga.render.window import OverlayApp
    chamadas = []
    stub = SimpleNamespace(logger=logging.getLogger("teste-sejoga"),
                           quit_app=lambda: chamadas.append(True))
    OverlayApp._ao_iniciar_atualizacao(stub)
    assert chamadas == [True]

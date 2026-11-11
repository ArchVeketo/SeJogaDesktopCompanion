"""Exercise the actual Qt update flow with an isolated, offline release provider."""

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication, QMessageBox

from sejoga.configuracao import Settings
from sejoga.desktop.interface import SettingsDialog
from sejoga.distribuicao.atualizador import ReleaseInfo, Update
from sejoga.distribuicao.dialogo_atualizacao import UpdateDialog


def main():  # noqa: PLR0915  # TODO convenção: ferramenta de captura/GPU: fatiar sem rodar na GPU arrisca a saída; lote próprio
    """Executa o smoke do atualizador."""
    app = QApplication.instance() or QApplication([])
    profile = Path(tempfile.mkdtemp(prefix="sejoga-updater-smoke-"))
    launcher = profile / "SeJogaLauncher.exe"
    launcher.write_bytes(b"offline fixture; never executed")
    channel_info = profile / "channel-info.json"
    channel_info.write_text(
        json.dumps({"channel": "release", "scope": "machine"}), encoding="utf-8"
    )
    update = Update("0.2.0", "release", "package.zip", "", "a" * 64, 4096, 2)
    settings = Settings()  # canal padrão: release
    started = []

    def finish_worker(dialog):
        deadline = time.monotonic() + 5
        while dialog._busy and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()
        assert not dialog._busy, "Update worker did not finish"

    # Bandeja: buscar -> versão disponível -> recusar -> confirmar -> handoff.
    with (
        patch(
            "sejoga.distribuicao.dialogo_atualizacao.installed_release",
            return_value=ReleaseInfo("0.1.0", "release"),
        ),
        patch(
            "sejoga.distribuicao.dialogo_atualizacao.installed_launcher",
            return_value=launcher,
        ),
        patch(
            "sejoga.distribuicao.dialogo_atualizacao.check_update", return_value=update
        ),
        patch("win32api.ShellExecute") as launch,
    ):
        dialog = UpdateDialog(lambda: started.append(True), settings)
        dialog.show()
        dialog._action()
        finish_worker(dialog)
        assert dialog.candidate == update
        assert "0.2.0" in dialog.status.text()
        dialog.grab().save(str(profile / "available.png"))
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.No
        ):
            dialog._action()
            finish_worker(dialog)
        launch.assert_not_called()
        assert not started
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ):
            dialog._action()
            finish_worker(dialog)
        launch.assert_called_once()
        assert launch.call_args.args[3] == "--update --channel release"
        assert started == [True]
        dialog.close()

    # Bandeja: 404/sem atualização mostra 'nenhuma atualização' e não trava.
    with (
        patch(
            "sejoga.distribuicao.dialogo_atualizacao.installed_release",
            return_value=ReleaseInfo("0.1.0", "release"),
        ),
        patch(
            "sejoga.distribuicao.dialogo_atualizacao.installed_launcher",
            return_value=launcher,
        ),
        patch(
            "sejoga.distribuicao.dialogo_atualizacao.check_update", return_value=None
        ),
    ):
        dialog = UpdateDialog(lambda: None, settings)
        dialog._action()
        finish_worker(dialog)
        assert dialog.candidate is None
        assert "Nenhuma atualização" in dialog.status.text()
        assert dialog.action.isEnabled()
        dialog.close()

    # Bandeja: erro de rede recupera sem travar.
    with (
        patch(
            "sejoga.distribuicao.dialogo_atualizacao.installed_release",
            return_value=ReleaseInfo("0.1.0", "release"),
        ),
        patch(
            "sejoga.distribuicao.dialogo_atualizacao.installed_launcher",
            return_value=launcher,
        ),
        patch(
            "sejoga.distribuicao.dialogo_atualizacao.check_update",
            side_effect=OSError("offline"),
        ),
    ):
        dialog = UpdateDialog(lambda: None, settings)
        dialog._action()
        finish_worker(dialog)
        assert dialog.action.isEnabled()
        assert "offline" in dialog.status.text()
        dialog.close()

    # Configurações: o canal selecionado acompanha a busca e o handoff.
    settings.update.channel = "prerelease"
    preview = Update("0.2.0rc1", "prerelease", "package.zip", "", "a" * 64, 4096, 2)
    with (
        patch("sejoga.distribuicao.dialogo_atualizacao.installed_launcher", return_value=launcher),
        patch("sejoga.distribuicao.dialogo_atualizacao.installed_release", return_value=None),
        patch("sejoga.distribuicao.dialogo_atualizacao.check_update", return_value=preview) as check,
        patch("win32api.GetFileVersionInfo", return_value={"FileVersionMS": 0x00010001}),
        patch("win32api.ShellExecute") as launch,
        patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
    ):
        dialog = SettingsDialog(settings)
        dialog._buscar_atualizacoes()
        shared = dialog._update_dialog
        finish_worker(shared)
        check.assert_called_once_with(None, channel="prerelease")
        assert "0.2.0rc1" in shared.status.text()
        shared._action()
        launch.assert_called_once()
        assert launch.call_args.args[3] == "--update --channel prerelease"
        assert json.loads(channel_info.read_text(encoding="utf-8"))["channel"] == "release"
        dialog.close()

    print(f"PASS: busca, status, confirmação, recusa, erro e handoff por canal. {profile}")


if __name__ == "__main__":
    main()

"""Exercise the actual Qt update flow with an isolated, offline release provider."""
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))

from PySide6.QtWidgets import QApplication, QMessageBox

from sejoga.update_ui import UpdateDialog
from sejoga.updater import ReleaseInfo, Update


def main():
    app = QApplication.instance() or QApplication([])
    profile = Path(tempfile.mkdtemp(prefix='sejoga-updater-smoke-'))
    launcher = profile/'SeJogaLauncher.exe'
    launcher.write_bytes(b'offline fixture; never executed')
    update = Update('0.2.0', 'release', 'package.zip', '', 'a'*64, 4096, 2)
    started = []

    def finish_worker(dialog):
        deadline = time.monotonic()+5
        while dialog._busy and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        app.processEvents()
        assert not dialog._busy, 'Update worker did not finish'

    with (patch('sejoga.update_ui.installed_release', return_value=ReleaseInfo('0.1.0', 'release')),
          patch('sejoga.update_ui.installed_launcher', return_value=launcher),
          patch('sejoga.update_ui.check_update', return_value=update),
          patch('win32api.ShellExecute') as launch):
        dialog = UpdateDialog(lambda: started.append(True))
        dialog.show()
        dialog._action()
        finish_worker(dialog)
        assert dialog.candidate == update
        assert '0.2.0' in dialog.status.text()
        dialog.grab().save(str(profile/'available.png'))
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            dialog._action()
            finish_worker(dialog)
        launch.assert_not_called()
        assert not started
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            dialog._action()
            finish_worker(dialog)
        launch.assert_called_once()
        assert launch.call_args.args[3] == '--update'
        assert started == [True]
        dialog.close()
    with (patch('sejoga.update_ui.installed_release', return_value=ReleaseInfo('0.1.0', 'release')),
          patch('sejoga.update_ui.installed_launcher', return_value=launcher),
          patch('sejoga.update_ui.check_update', side_effect=OSError('offline'))):
        dialog = UpdateDialog(lambda: None)
        dialog._action()
        finish_worker(dialog)
        assert dialog.action.isEnabled()
        assert 'offline' in dialog.status.text()
        dialog.close()
    print(f'PASS: check, offer, decline, stable launcher handoff, consent, error recovery. {profile}')


if __name__ == '__main__':
    main()

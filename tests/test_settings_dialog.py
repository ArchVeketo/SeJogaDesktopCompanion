import sys
import pytest

if sys.platform != "win32":
    pytest.skip("Windows settings dialog", allow_module_level=True)
pytest.importorskip("PySide6")


def test_save_dialog_uses_fallback_and_emits_saved_settings(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QDialog
    from sejoga import config
    from sejoga.ui import SettingsDialog
    app = QApplication.instance() or QApplication([])
    primary = tmp_path / "locked" / "config.toml"
    fallback = tmp_path / "fallback" / "config.toml"
    original = config._write_settings
    monkeypatch.delenv("SEJOGA_CONFIG_PATH", raising=False)
    monkeypatch.setattr(config, "default_config_path", lambda: primary)
    monkeypatch.setattr(config, "fallback_config_path", lambda: fallback)
    def write(path, payload):
        if path == primary:
            raise PermissionError("locked profile")
        original(path, payload)
    monkeypatch.setattr(config, "_write_settings", write)
    dialog = SettingsDialog(config.Settings())
    updates = []
    dialog.settings_applied.connect(updates.append)
    dialog.outline_width_input.setValue(4.5)
    dialog.sensitivity_input.setValue(.8)
    dialog.dance_chance_input.setValue(.65)
    dialog.beat_input.setChecked(False)
    dialog.personality_input.setCurrentIndex(dialog.personality_input.findData("fighter"))
    dialog._save()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert updates[0].window.outline_width == 4.5
    assert config.load_settings(fallback).window.outline_width == 4.5
    assert config.load_settings(fallback).behavior.idle_personality == "fighter"
    reopened = SettingsDialog(config.load_settings(fallback))
    assert reopened.personality_input.currentData() == "fighter"
    assert reopened.sensitivity_input.value() == .8
    assert reopened.dance_chance_input.value() == .65
    assert not reopened.beat_input.isChecked()
    reopened.close()
    dialog.close()

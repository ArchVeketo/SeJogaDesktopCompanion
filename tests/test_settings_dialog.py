import sys

import pytest

if sys.platform != "win32":
    pytest.skip("Windows settings dialog", allow_module_level=True)
pytest.importorskip("PySide6")


def test_save_dialog_uses_fallback_and_emits_saved_settings(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QDialog

    from sejoga import config
    from sejoga.desktop.ui import SettingsDialog
    app = QApplication.instance() or QApplication([])  # noqa: F841  # intencional: mantem a QApplication viva durante o teste (evita GC)
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
    dialog.outline_breath_input.setValue(.7)
    dialog.sensitivity_input.setValue(.8)
    dialog.dance_chance_input.setValue(.65)
    dialog.beat_input.setChecked(False)
    dialog.dance_style_input.setCurrentIndex(dialog.dance_style_input.findData('rock'))
    dialog.personality_input.setCurrentIndex(dialog.personality_input.findData("fighter"))
    dialog._save()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert updates[0].window.outline_width == 4.5
    assert updates[0].window.outline_breath == .7
    assert config.load_settings(fallback).window.outline_width == 4.5
    assert config.load_settings(fallback).window.outline_breath == .7
    assert config.load_settings(fallback).behavior.idle_personality == "fighter"
    reopened = SettingsDialog(config.load_settings(fallback))
    assert reopened.personality_input.currentData() == "fighter"
    assert reopened.outline_breath_input.value() == .7
    assert reopened.sensitivity_input.value() == .8
    assert reopened.dance_chance_input.value() == .65
    assert not reopened.beat_input.isChecked()
    assert reopened.dance_style_input.currentData() == 'rock'
    reopened.close()
    dialog.close()


def test_novos_campos_persistem_e_reabrem(tmp_path, monkeypatch):
    """FPS, monitor preferido, color key de diagnóstico e nível de log."""
    from PySide6.QtWidgets import QApplication, QDialog

    from sejoga import config
    from sejoga.desktop import autostart, ui
    from sejoga.desktop.ui import SettingsDialog
    app = QApplication.instance() or QApplication([])  # noqa: F841  # intencional: mantem a QApplication viva durante o teste (evita GC)
    destino = tmp_path / "config.toml"
    monkeypatch.setenv("SEJOGA_CONFIG_PATH", str(destino))
    monkeypatch.setattr(config, "default_config_path", lambda: destino)
    monkeypatch.setattr(ui, "default_config_path", lambda: destino)
    # Autostart mockado para não tocar a pasta Startup real do usuário.
    ativacoes: list[bool] = []
    monkeypatch.setattr(autostart, "esta_ativo", lambda: False)
    monkeypatch.setattr(autostart, "ativar", lambda: ativacoes.append(True) or True)
    monkeypatch.setattr(autostart, "desativar", lambda: ativacoes.append(False) or True)

    dialog = SettingsDialog(config.Settings())
    updates = []
    dialog.settings_applied.connect(updates.append)
    dialog.fps_input.setValue(90)
    dialog.diagnostic_input.setChecked(True)
    dialog.log_level_input.setCurrentIndex(dialog.log_level_input.findData("DEBUG"))
    dialog.autostart_input.setChecked(True)
    # Monitor preferido: usa o último índice real disponível, se houver.
    if dialog.monitor_input.count() > 1:
        dialog.monitor_input.setCurrentIndex(dialog.monitor_input.count() - 1)
    monitor_esperado = dialog.monitor_input.currentData()
    dialog._save()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert updates[0].window.fps == 90
    assert updates[0].window.diagnostic_colorkey is True
    assert updates[0].window.preferred_monitor == monitor_esperado
    assert updates[0].logging.level == "DEBUG"
    assert ativacoes == [True]

    salvo = config.load_settings(destino)
    assert salvo.window.fps == 90
    assert salvo.window.diagnostic_colorkey is True
    assert salvo.window.preferred_monitor == monitor_esperado
    assert salvo.logging.level == "DEBUG"

    reopened = SettingsDialog(salvo)
    assert reopened.fps_input.value() == 90
    assert reopened.diagnostic_input.isChecked()
    assert reopened.log_level_input.currentData() == "DEBUG"
    assert reopened.monitor_input.currentData() == monitor_esperado
    reopened.close()
    dialog.close()

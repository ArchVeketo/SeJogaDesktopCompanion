"""Testa o diálogo de configurações e a persistência dos campos."""

import sys

import pytest

if sys.platform != "win32":
    pytest.skip("Windows settings dialog", allow_module_level=True)
pytest.importorskip("PySide6")


def test_save_dialog_uses_fallback_and_emits_saved_settings(tmp_path, monkeypatch):  # noqa: PLR0915  # TODO convenção: teste de cenário longo; dividir em lote próprio
    from PySide6.QtWidgets import QApplication, QDialog

    from sejoga import configuracao
    from sejoga.desktop.interface import SettingsDialog

    app = QApplication.instance() or QApplication([])  # noqa: F841  # intencional: mantem a QApplication viva durante o teste (evita GC)
    primary = tmp_path / "locked" / "config.toml"
    fallback = tmp_path / "fallback" / "config.toml"
    original = configuracao._write_settings
    monkeypatch.delenv("SEJOGA_CONFIG_PATH", raising=False)
    monkeypatch.setattr(configuracao, "default_config_path", lambda: primary)
    monkeypatch.setattr(configuracao, "fallback_config_path", lambda: fallback)

    def write(path, payload):
        if path == primary:
            raise PermissionError("locked profile")
        original(path, payload)

    monkeypatch.setattr(configuracao, "_write_settings", write)
    dialog = SettingsDialog(configuracao.Settings())
    updates = []
    dialog.settings_applied.connect(updates.append)
    dialog.outline_width_input.setValue(4.5)
    dialog.outline_breath_input.setValue(0.7)
    # Botão de cor do color key existe e a cor escolhida é persistida.
    assert dialog.colorkey_color_button.text() == "#FF00FF"
    dialog._colorkey_color = "#00FF00"
    dialog.sensitivity_input.setValue(0.8)
    dialog.dance_chance_input.setValue(0.65)
    dialog.beat_input.setChecked(False)
    dialog.dance_style_input.setCurrentIndex(dialog.dance_style_input.findData("rock"))
    dialog.personality_input.setCurrentIndex(
        dialog.personality_input.findData("fighter")
    )
    dialog._save()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert updates[0].window.outline_width == 4.5
    assert updates[0].window.outline_breath == 0.7
    assert updates[0].window.colorkey_color == "#00FF00"
    assert configuracao.load_settings(fallback).window.colorkey_color == "#00FF00"
    assert configuracao.load_settings(fallback).window.outline_width == 4.5
    assert configuracao.load_settings(fallback).window.outline_breath == 0.7
    assert configuracao.load_settings(fallback).behavior.idle_personality == "fighter"
    reopened = SettingsDialog(configuracao.load_settings(fallback))
    assert reopened.colorkey_color_button.text() == "#00FF00"
    assert reopened.personality_input.currentData() == "fighter"
    assert reopened.outline_breath_input.value() == 0.7
    assert reopened.sensitivity_input.value() == 0.8
    assert reopened.dance_chance_input.value() == 0.65
    assert not reopened.beat_input.isChecked()
    assert reopened.dance_style_input.currentData() == "rock"
    reopened.close()
    dialog.close()


def test_novos_campos_persistem_e_reabrem(tmp_path, monkeypatch):  # noqa: PLR0915  # TODO convenção: teste de cenário longo; dividir em lote próprio
    """FPS, monitor preferido, color key de diagnóstico e nível de log."""
    from PySide6.QtWidgets import QApplication, QDialog

    from sejoga import configuracao
    from sejoga.desktop import inicializacao_automatica, interface
    from sejoga.desktop.interface import SettingsDialog

    app = QApplication.instance() or QApplication([])  # noqa: F841  # intencional: mantem a QApplication viva durante o teste (evita GC)
    destino = tmp_path / "config.toml"
    monkeypatch.setenv("SEJOGA_CONFIG_PATH", str(destino))
    monkeypatch.setattr(configuracao, "default_config_path", lambda: destino)
    monkeypatch.setattr(interface, "default_config_path", lambda: destino)
    # Autostart mockado para não tocar a pasta Startup real do usuário.
    ativacoes: list[bool] = []
    monkeypatch.setattr(inicializacao_automatica, "esta_ativo", lambda: False)
    monkeypatch.setattr(
        inicializacao_automatica, "ativar", lambda: ativacoes.append(True) or True
    )
    monkeypatch.setattr(
        inicializacao_automatica, "desativar", lambda: ativacoes.append(False) or True
    )

    dialog = SettingsDialog(configuracao.Settings())
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

    salvo = configuracao.load_settings(destino)
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

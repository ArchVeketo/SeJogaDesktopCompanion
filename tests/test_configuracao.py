"""Testes de configuração: defaults, serialização e resiliência."""

from __future__ import annotations

import pytest

from sejoga.configuracao import Settings, load_settings, save_settings


def test_defaults():
    s = Settings()
    assert s.window.mode == "overlay"
    assert s.window.always_on_top is True
    assert s.physics.enabled is True
    assert s.music.source == "media_session"
    assert s.update.channel == "release"
    assert 0 < s.window.scale <= 4


def test_roundtrip(tmp_path):
    path = tmp_path / "config.toml"
    s = Settings()
    s.window.scale = 1.75
    s.window.outline_color = "#23B7E9"
    s.window.colorkey_color = "#00FF00"
    s.window.outline_width = 4.0
    s.window.outline_enabled = False
    s.window.mode = "desktop"
    s.physics.bounce = 0.2
    s.music.enabled = False
    s.update.channel = "prerelease"

    save_settings(s, path)
    assert path.is_file()

    loaded = load_settings(path)
    assert loaded.window.scale == pytest.approx(1.75)
    assert loaded.window.outline_color == "#23B7E9"
    assert loaded.window.colorkey_color == "#00FF00"
    assert loaded.window.outline_width == 4.0
    assert loaded.window.outline_enabled is False
    assert loaded.window.mode == "desktop"
    assert loaded.physics.bounce == pytest.approx(0.2)
    assert loaded.music.enabled is False
    assert loaded.update.channel == "prerelease"


def test_corrupted_file_falls_back_to_defaults(tmp_path, capsys):
    path = tmp_path / "config.toml"
    path.write_text("isto nao e toml = = =", encoding="utf-8")
    s = load_settings(path)
    assert s.window.mode == "overlay"
    assert "config inválido" in capsys.readouterr().out


def test_unknown_fields_are_ignored(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[obsoleto]\nx = 1\n[window]\nscale = 2.0\n", encoding="utf-8")
    s = load_settings(path)
    assert s.window.scale == pytest.approx(2.0)


def test_validation_rejects_bad_values():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(window={"scale": -1.0})


def test_colorkey_default_e_magenta():
    assert Settings().window.colorkey_color == "#FF00FF"


def test_colorkey_rejects_invalid_hex():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(window={"colorkey_color": "verde"})
    with pytest.raises(ValidationError):
        Settings(window={"colorkey_color": "#FFF"})


def test_colorkey_ausente_carrega_sem_erro(tmp_path):
    """Config antigo sem o campo carrega com o default (migração tolerante)."""
    path = tmp_path / "config.toml"
    path.write_text("[window]\nscale = 1.5\n", encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.window.colorkey_color == "#FF00FF"


def test_permission_denied_uses_persistent_fallback(tmp_path, monkeypatch):
    from sejoga import configuracao
    primary = tmp_path / "locked" / "config.toml"
    fallback = tmp_path / "fallback" / "config.toml"
    original = configuracao._write_settings
    monkeypatch.delenv("SEJOGA_CONFIG_PATH", raising=False)
    monkeypatch.setattr(configuracao, "default_config_path", lambda: fallback if fallback.exists() else primary)
    monkeypatch.setattr(configuracao, "fallback_config_path", lambda: fallback)
    def write(path, payload):
        if path == primary:
            raise PermissionError("locked profile")
        original(path, payload)
    monkeypatch.setattr(configuracao, "_write_settings", write)
    settings = Settings()
    settings.window.outline_color = "#00FF00"
    assert save_settings(settings) == fallback
    assert load_settings().window.outline_color == "#00FF00"
    with pytest.raises(PermissionError):
        save_settings(settings, primary)


def test_save_ignores_stale_shared_temp_file(tmp_path):
    path = tmp_path / "config.toml"
    stale = tmp_path / "config.toml.tmp"
    stale.write_text("belongs to another instance")
    save_settings(Settings(), path)
    assert load_settings(path).window.outline_enabled
    assert stale.read_text() == "belongs to another instance"
    assert list(tmp_path.glob("config-*.tmp")) == []


def test_locked_profile_directories_use_portable_bundle_profile(tmp_path, monkeypatch):
    from sejoga import configuracao
    primary = tmp_path / "local" / "config.toml"
    roaming = tmp_path / "roaming" / "config.toml"
    portable = tmp_path / "bundle" / "user-data" / "config.toml"
    original = configuracao._write_settings
    monkeypatch.delenv("SEJOGA_CONFIG_PATH", raising=False)
    monkeypatch.setattr(configuracao, "default_config_path", lambda: portable if portable.exists() else primary)
    monkeypatch.setattr(configuracao, "fallback_config_path", lambda: roaming)
    monkeypatch.setattr(configuracao, "portable_config_path", lambda: portable)
    def write(path, payload):
        if path in (primary, roaming):
            raise PermissionError("locked profile")
        original(path, payload)
    monkeypatch.setattr(configuracao, "_write_settings", write)
    settings = Settings()
    settings.window.outline_width = 3.5
    assert save_settings(settings) == portable
    assert load_settings().window.outline_width == 3.5

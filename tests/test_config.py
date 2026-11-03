"""Testes de configuração: defaults, serialização e resiliência."""

from __future__ import annotations

import pytest

from sejoga.config import Settings, load_settings, save_settings


def test_defaults():
    s = Settings()
    assert s.window.mode == "overlay"
    assert s.window.always_on_top is True
    assert s.physics.enabled is True
    assert s.music.source == "media_session"
    assert 0 < s.window.scale <= 4


def test_roundtrip(tmp_path):
    path = tmp_path / "config.toml"
    s = Settings()
    s.window.scale = 1.75
    s.window.mode = "desktop"
    s.physics.bounce = 0.2
    s.music.enabled = False

    save_settings(s, path)
    assert path.is_file()

    loaded = load_settings(path)
    assert loaded.window.scale == pytest.approx(1.75)
    assert loaded.window.mode == "desktop"
    assert loaded.physics.bounce == pytest.approx(0.2)
    assert loaded.music.enabled is False


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

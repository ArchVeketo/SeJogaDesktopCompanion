"""Modelo de configuração do companion, com persistência em TOML.

Princípios:

* **Defaults seguros** — o app abre sem configuração nenhuma.
* **Um arquivo por usuário** em ``%LOCALAPPDATA%`` (via ``platformdirs``),
  nunca dentro da pasta do projeto.
* **Migração tolerante** — campos desconhecidos são ignorados para que um
  config antigo não derrube o app após um update.
* **Serialização explícita** — só o que está no schema é gravado.

Uso::

    from sejoga.config import load_settings, save_settings

    settings = load_settings()
    settings.window.mode = "desktop"
    save_settings(settings)
"""

from __future__ import annotations

import errno
import logging
import os
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "SeJogaDesktopCompanion"
APP_AUTHOR = "ArchVeketo"


def profile_app_name() -> str:
    """Stable profiles keep their path; preview channels stay isolated."""
    from .updater import installed_release
    release = installed_release()
    return APP_NAME if release is None or release.channel == 'release' else f'{APP_NAME}-{release.channel}'


def default_config_path() -> Path:
    """``%LOCALAPPDATA%/SeJogaDesktopCompanion/config.toml`` no Windows."""
    from platformdirs import user_config_dir

    override = os.environ.get("SEJOGA_CONFIG_PATH")
    if override:
        return Path(override).expanduser().resolve()
    portable = portable_config_path()
    if portable is not None and portable.is_file():
        return portable
    fallback = fallback_config_path()
    if fallback.is_file():
        return fallback
    return Path(user_config_dir(profile_app_name(), APP_AUTHOR)) / "config.toml"


def fallback_config_path() -> Path:
    """Perfil persistente alternativo quando a pasta original recusa escrita."""
    from platformdirs import user_config_dir

    return Path(user_config_dir(profile_app_name(), appauthor=False, roaming=True)) / "config.toml"


def portable_config_path() -> Path | None:
    """Última alternativa para bundles executados em ambientes restritos."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "user-data" / "config.toml"
    return None


class WindowSettings(BaseModel):
    """Comportamento da janela que hospeda o personagem."""

    mode: Literal["overlay", "desktop"] = "overlay"
    """``overlay`` = acima de todas as janelas; ``desktop`` = atrás delas."""

    always_on_top: bool = True
    click_through_transparent: bool = True
    """Deixa o mouse atravessar onde o pixel é transparente."""

    size: int = 480
    """Lado (px) da janela quadrada que contém o modelo."""

    scale: float = Field(default=1.0, gt=0.1, le=4.0)
    """Multiplicador do enquadramento automático (1.0 ocupa até 70% do overlay)."""
    outline_enabled: bool = True
    outline_color: str = Field(default="#FF65CC", pattern=r"^#[0-9A-Fa-f]{6}$")
    outline_width: float = Field(default=2.5, ge=0.5, le=8.0)
    outline_breath: float = Field(default=0.4, ge=0.0, le=1.0)
    """Intensidade da respiração do contorno (0 = linha estática)."""
    fps: int = Field(default=60, ge=15, le=240)
    start_position: tuple[int, int] | None = None
    """Canto superior esquerdo em coordenadas de tela; ``None`` = canto inferior direito."""


class PhysicsSettings(BaseModel):
    """Física de tela (espaço 2D) para arrastar e arremessar."""

    enabled: bool = True
    mascot_radius: float = Field(default=40.0, gt=0)
    """Raio de colisão do mascote, em pixels."""

    gravity: float = Field(default=2400.0, ge=0.0)
    """px/s² — usada só quando o personagem "cai"."""

    mass: float = Field(default=2.4, gt=0.0, le=20.0)
    """Massa relativa; reduz a resposta a impulsos aplicados pelo ambiente."""
    bounce: float = Field(default=0.22, ge=0.0, le=1.0)
    friction: float = Field(default=0.94, ge=0.0, le=1.0)
    throw_multiplier: float = Field(default=0.82, gt=0.0, le=5.0)
    collide_with_windows: bool = True
    """Quica também nas bordas de outras janelas, não só da tela."""

    wall_thickness: int = Field(default=2, ge=0, le=32)


class MusicSettings(BaseModel):
    """Como o companion percebe e reage à música."""

    enabled: bool = True
    source: Literal["media_session", "loopback", "off"] = "media_session"
    """``media_session`` = metadados/fase via SMTC; ``loopback`` = áudio do sistema."""

    react_to_beat: bool = True
    sensitivity: float = Field(default=0.6, ge=0.0, le=1.0)
    dance_chance: float = Field(default=0.35, ge=0.0, le=1.0)
    dance_style: Literal['auto', 'head_bob', 'hip_hop', 'rock', 'breakdance'] = 'auto'


class BehaviorSettings(BaseModel):
    """Personalidade e autonomia."""

    idle_animation: bool = True
    idle_personality: Literal[
        "auto", "calm", "curious", "playful", "shy", "confident",
        "street", "fighter", "rhythm", "stylish",
    ] = "auto"
    wander: bool = True
    react_to_click: bool = True
    react_to_drag: bool = True
    sleep_after_idle_seconds: int = Field(default=90, ge=0)


class AudioSettings(BaseModel):
    """Sons do próprio companion (não confundir com a música do sistema)."""

    enabled: bool = True
    master_volume: float = Field(default=0.8, ge=0.0, le=1.0)


class HotkeySettings(BaseModel):
    """Atalhos globais (formato ``ctrl+alt+x``)."""

    toggle_overlay: str = "ctrl+alt+t"
    open_settings: str = "ctrl+alt+s"
    summon: str = "ctrl+alt+m"
    toggle_debug: str = "ctrl+alt+f11"
    capture_frame: str = "ctrl+alt+p"
    toggle_frame_recording: str = "ctrl+alt+r"


class Settings(BaseSettings):
    """Configuração raiz. Cada seção vira uma tabela no TOML."""

    model_config = SettingsConfigDict(
        env_prefix="SEJOGA_",
        env_nested_delimiter="__",
        extra="ignore",
        validate_assignment=True,
    )

    window: WindowSettings = Field(default_factory=WindowSettings)
    physics: PhysicsSettings = Field(default_factory=PhysicsSettings)
    music: MusicSettings = Field(default_factory=MusicSettings)
    behavior: BehaviorSettings = Field(default_factory=BehaviorSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    hotkeys: HotkeySettings = Field(default_factory=HotkeySettings)
    first_run_done: bool = False


def load_settings(path: Path | None = None) -> Settings:
    """Carrega do TOML (se existir), com defaults e env por cima.

    Variáveis de ambiente no formato ``SEJOGA_WINDOW__SCALE=1.5`` continuam
    funcionando porque o ``tomllib`` só preenche o que falta.
    """
    path = path or default_config_path()
    data: dict = {}
    if path.is_file():
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:  # config corrompido não derruba o app
            print(f"[sejoga] config inválido em {path}: {exc}; usando defaults")
            data = {}
    return Settings(**data)


def save_settings(settings: Settings, path: Path | None = None) -> Path:
    """Grava o config atomicamente (arquivo temporário + ``os.replace``)."""
    from tomli_w import dumps

    payload = dumps(settings.model_dump(mode="json", exclude_none=True))
    explicit = path is not None or bool(os.environ.get("SEJOGA_CONFIG_PATH"))
    path = path or default_config_path()
    try:
        _write_settings(path, payload)
    except PermissionError:
        fallback = fallback_config_path()
        if explicit:
            raise
        try:
            _write_settings(fallback, payload)
        except PermissionError:
            portable = portable_config_path()
            if portable is None:
                raise
            _write_settings(portable, payload)
            fallback = portable
        logging.getLogger("sejoga").warning("Configuration moved from %s to %s (permission denied)", path, fallback)
        path = fallback
    return path


def _write_settings(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # A stale shared .tmp can have different ACLs or belong to another instance.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix="config-", suffix=".tmp", delete=False) as stream:
        tmp = Path(stream.name)
        stream.write(payload)
    try:
        try:
            tmp.replace(path)
        except OSError as exc:
            if exc.errno != errno.EXDEV and getattr(exc, "winerror", None) != 17:
                raise
            path.write_text(payload, encoding="utf-8")
    finally:
        tmp.unlink(missing_ok=True)

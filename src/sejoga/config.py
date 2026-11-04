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

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "SeJogaDesktopCompanion"
APP_AUTHOR = "ArchVeketo"


def default_config_path() -> Path:
    """``%LOCALAPPDATA%/SeJogaDesktopCompanion/config.toml`` no Windows."""
    from platformdirs import user_config_dir

    return Path(user_config_dir(APP_NAME, APP_AUTHOR)) / "config.toml"


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

    bounce: float = Field(default=0.55, ge=0.0, le=1.0)
    friction: float = Field(default=0.88, ge=0.0, le=1.0)
    throw_multiplier: float = Field(default=1.0, gt=0.0, le=5.0)
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


class BehaviorSettings(BaseModel):
    """Personalidade e autonomia."""

    idle_animation: bool = True
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

    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclui None para serialização TOML válida
    payload = dumps(settings.model_dump(mode="json", exclude_none=True))
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
    return path

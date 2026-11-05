"""Diálogo de preferências do companion."""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from .config import Settings, save_settings


class SettingsDialog(QDialog):
    """Edita preferências e salva uma cópia validada em TOML."""

    settings_applied = Signal(object)

    def __init__(self, settings: Settings):
        super().__init__()
        self._settings = settings.model_copy(deep=True)
        self.setWindowTitle("Configurações do SeJoga Companion")
        self.setMinimumWidth(420)

        self.size_input = QSpinBox()
        self.size_input.setRange(240, 960)
        self.size_input.setSingleStep(40)
        self.size_input.setSuffix(" px")
        self.size_input.setValue(settings.window.size)

        self.scale_input = QDoubleSpinBox()
        self.scale_input.setRange(0.5, 2.5)
        self.scale_input.setSingleStep(0.1)
        self.scale_input.setDecimals(1)
        self.scale_input.setValue(settings.window.scale)

        self.outline_input = QCheckBox("Mostrar contorno")
        self.outline_input.setChecked(settings.window.outline_enabled)
        self.outline_width_input = QDoubleSpinBox()
        self.outline_width_input.setRange(0.5, 8.0)
        self.outline_width_input.setSingleStep(0.5)
        self.outline_width_input.setDecimals(1)
        self.outline_width_input.setSuffix(" px")
        self.outline_width_input.setValue(settings.window.outline_width)
        self._outline_color = settings.window.outline_color.upper()
        self.outline_color_button = QPushButton()
        self._show_outline_color()
        self.outline_color_button.clicked.connect(self._choose_outline_color)

        self.physics_input = QCheckBox("Ativar física de tela")
        self.physics_input.setChecked(settings.physics.enabled)

        self.idle_input = QCheckBox("Variar as animações quando estiver parado")
        self.idle_input.setChecked(settings.behavior.idle_animation)

        self.personality_input = QComboBox()
        for key, label in (("auto", "Automática"), ("calm", "Tranquila"), ("curious", "Curiosa"),
                           ("playful", "Brincalhona"), ("shy", "Tímida"), ("confident", "Confiante"),
                           ("street", "Street groove · Bomb Rush"), ("fighter", "Guarda · Lethal League"),
                           ("rhythm", "Ritmada · Hi-Fi Rush"), ("stylish", "Estilosa · Persona 5")):
            self.personality_input.addItem(label, key)
        self.personality_input.setCurrentIndex(self.personality_input.findData(settings.behavior.idle_personality))
        self.personality_input.setEnabled(self.idle_input.isChecked())
        self.idle_input.toggled.connect(self.personality_input.setEnabled)

        self.react_click_input = QCheckBox("Reagir ao cursor e aos cliques")
        self.react_click_input.setChecked(settings.behavior.react_to_click)
        self.react_drag_input = QCheckBox("Permitir arrastar o mascote")
        self.react_drag_input.setChecked(settings.behavior.react_to_drag)

        self.z_order_input = QComboBox()
        self.z_order_input.addItem("Sempre no topo", "topmost")
        self.z_order_input.addItem("Janela normal", "normal")
        self.z_order_input.addItem("Atrás das janelas", "desktop")
        z_order = "desktop" if settings.window.mode == "desktop" else (
            "topmost" if settings.window.always_on_top else "normal"
        )
        self.z_order_input.setCurrentIndex(self.z_order_input.findData(z_order))

        self.music_input = QComboBox()
        self.music_input.addItem("Desligada", "off")
        self.music_input.addItem("Sessão de mídia do Windows", "media_session")
        self.music_input.addItem("Áudio do sistema (loopback)", "loopback")
        self.music_input.setCurrentIndex(self.music_input.findData(settings.music.source))
        self.beat_input = QCheckBox("Reagir à batida")
        self.beat_input.setChecked(settings.music.react_to_beat)
        self.sensitivity_input = QDoubleSpinBox()
        self.sensitivity_input.setRange(0, 1)
        self.sensitivity_input.setSingleStep(.05)
        self.sensitivity_input.setValue(settings.music.sensitivity)
        self.dance_chance_input = QDoubleSpinBox()
        self.dance_chance_input.setRange(0, 1)
        self.dance_chance_input.setSingleStep(.05)
        self.dance_chance_input.setValue(settings.music.dance_chance)

        self.hotkey_inputs = {
            name: QLineEdit(getattr(settings.hotkeys, name))
            for name in settings.hotkeys.model_dump()
        }

        form = QFormLayout()
        form.addRow("Tamanho da janela", self.size_input)
        form.addRow("Escala do mascote", self.scale_input)
        form.addRow(self.outline_input)
        form.addRow("Cor do contorno", self.outline_color_button)
        form.addRow("Espessura do contorno", self.outline_width_input)
        form.addRow(self.physics_input)
        form.addRow(self.idle_input)
        form.addRow("Personalidade", self.personality_input)
        form.addRow(self.react_click_input)
        form.addRow(self.react_drag_input)
        form.addRow("Posição da janela", self.z_order_input)
        form.addRow("Reação à música", self.music_input)
        form.addRow(self.beat_input)
        form.addRow("Sensibilidade da batida", self.sensitivity_input)
        form.addRow("Frequência de dança (0–1)", self.dance_chance_input)
        for name, label in (
            ("toggle_overlay", "Mostrar/ocultar"),
            ("open_settings", "Abrir configurações"),
            ("summon", "Chamar mascote"),
            ("toggle_debug", "HUD de diagnóstico"),
            ("capture_frame", "Capturar frame"),
            ("toggle_frame_recording", "Gravar frames"),
        ):
            form.addRow(f"Atalho: {label}", self.hotkey_inputs[name])

        self.restart_notice = QLabel(
            "Tamanho da janela e física são aplicados ao reiniciar o companion."
        )
        self.restart_notice.setWordWrap(True)
        self.loopback_notice = QLabel(
            "Loopback requer a dependência opcional soundcard (extra music-loopback)."
        )
        self.loopback_notice.setWordWrap(True)
        self.hotkey_notice = QLabel("Use combinações como ctrl+alt+m. As alterações são aplicadas ao salvar.")
        self.hotkey_notice.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.restart_notice)
        layout.addWidget(self.loopback_notice)
        layout.addWidget(self.hotkey_notice)
        layout.addWidget(buttons)

    def _show_outline_color(self) -> None:
        self.outline_color_button.setText(self._outline_color)
        self.outline_color_button.setStyleSheet(
            f"background-color: {self._outline_color}; color: #202020;"
        )

    def _choose_outline_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._outline_color), self, "Cor do contorno")
        if color.isValid():
            self._outline_color = color.name().upper()
            self._show_outline_color()

    def _save(self) -> None:
        updated = self._settings.model_copy(deep=True)
        updated.window.size = self.size_input.value()
        updated.window.scale = self.scale_input.value()
        updated.window.outline_enabled = self.outline_input.isChecked()
        updated.window.outline_color = self._outline_color
        updated.window.outline_width = self.outline_width_input.value()
        updated.physics.enabled = self.physics_input.isChecked()
        updated.behavior.idle_animation = self.idle_input.isChecked()
        updated.behavior.idle_personality = self.personality_input.currentData()
        updated.behavior.react_to_click = self.react_click_input.isChecked()
        updated.behavior.react_to_drag = self.react_drag_input.isChecked()
        z_order = self.z_order_input.currentData()
        updated.window.mode = "desktop" if z_order == "desktop" else "overlay"
        updated.window.always_on_top = z_order == "topmost"
        updated.music.source = self.music_input.currentData()
        updated.music.react_to_beat = self.beat_input.isChecked()
        updated.music.sensitivity = self.sensitivity_input.value()
        updated.music.dance_chance = self.dance_chance_input.value()

        normalized_hotkeys: dict[tuple[int, int], str] = {}
        try:
            for name, field in self.hotkey_inputs.items():
                shortcut = field.text().strip().lower()
                parsed = HotkeyManager._parse_shortcut(shortcut)
                if parsed in normalized_hotkeys:
                    raise ValueError(
                        f"{shortcut} conflita com {normalized_hotkeys[parsed]}. Cada ação precisa de um atalho único."
                    )
                normalized_hotkeys[parsed] = shortcut
                setattr(updated.hotkeys, name, shortcut)
        except ValueError as exc:
            QMessageBox.warning(self, "Atalho inválido", str(exc))
            return

        try:
            save_settings(updated)
        except Exception as exc:
            QMessageBox.critical(self, "Falha ao salvar", f"Não foi possível salvar as configurações:\n{exc}")
            return

        self.settings_applied.emit(updated)
        self.accept()


_WM_HOTKEY = 0x0312
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN = 0x0008
_MOD_NOREPEAT = 0x4000


class _Message(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class _HotkeyBridge(QObject):
    activated = Signal(int)


class HotkeyManager:
    """Registra atalhos globais Win32 e encaminha os eventos ao Qt."""

    _MODIFIERS = {
        "alt": _MOD_ALT,
        "ctrl": _MOD_CONTROL,
        "control": _MOD_CONTROL,
        "shift": _MOD_SHIFT,
        "win": _MOD_WIN,
        "meta": _MOD_WIN,
    }
    _KEYS = {
        "backspace": 0x08,
        "tab": 0x09,
        "enter": 0x0D,
        "return": 0x0D,
        "esc": 0x1B,
        "escape": 0x1B,
        "space": 0x20,
        "delete": 0x2E,
        "home": 0x24,
        "end": 0x23,
        "pageup": 0x21,
        "pagedown": 0x22,
        "up": 0x26,
        "down": 0x28,
        "left": 0x25,
        "right": 0x27,
    }

    def __init__(self, shortcuts: dict[str, str], callbacks: dict[str, Callable[[], None]]):
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._shortcuts: list[tuple[int, str, int, int]] = []
        self._registered_ids: list[int] = []
        self.unavailable_shortcuts: list[str] = []
        self._thread_id = 0
        self._ready = threading.Event()
        self._bridge = _HotkeyBridge()
        self._bridge.activated.connect(self._dispatch)
        self._register = ctypes.windll.user32.RegisterHotKey
        self._unregister = ctypes.windll.user32.UnregisterHotKey
        self._register.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
        self._register.restype = wintypes.BOOL
        self._unregister.argtypes = (wintypes.HWND, ctypes.c_int)
        self._unregister.restype = wintypes.BOOL
        for index, (name, shortcut) in enumerate(shortcuts.items(), start=1):
            callback = callbacks.get(name)
            if callback is None:
                continue
            try:
                modifiers, key = self._parse_shortcut(shortcut)
            except ValueError as exc:
                print(f"[hotkeys] {exc}")
                continue
            hotkey_id = 0x534A + index
            self._shortcuts.append((hotkey_id, shortcut, modifiers | _MOD_NOREPEAT, key))
            self._callbacks[hotkey_id] = callback

        self._thread = threading.Thread(target=self._message_loop, name="global-hotkeys", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)

    @classmethod
    def _parse_shortcut(cls, shortcut: str) -> tuple[int, int]:
        parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
        if not parts:
            raise ValueError("empty shortcut")
        modifiers = 0
        for part in parts[:-1]:
            if part not in cls._MODIFIERS:
                raise ValueError(f"unknown modifier in shortcut: {shortcut}")
            modifier = cls._MODIFIERS[part]
            if modifiers & modifier:
                raise ValueError(f"modifier repeated in shortcut: {shortcut}")
            modifiers |= modifier
        key_name = parts[-1]
        if key_name in cls._KEYS:
            key = cls._KEYS[key_name]
        elif len(key_name) == 1 and key_name.isascii() and key_name.isalnum():
            key = ord(key_name.upper())
        elif key_name.startswith("f") and key_name[1:].isdigit() and 1 <= int(key_name[1:]) <= 24:
            key = 0x70 + int(key_name[1:]) - 1
        else:
            raise ValueError(f"unsupported key in shortcut: {shortcut}")
        if modifiers == 0:
            raise ValueError(f"global shortcuts require a modifier: {shortcut}")
        return modifiers, key

    def _message_loop(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        # Cria a message queue da thread antes de registrar os atalhos globais.
        message = _Message()
        user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
        for hotkey_id, shortcut, modifiers, key in self._shortcuts:
            if self._register(None, hotkey_id, modifiers, key):
                self._registered_ids.append(hotkey_id)
            else:
                self.unavailable_shortcuts.append(shortcut)
                print(f"[hotkeys] shortcut unavailable: {shortcut}")
        self._ready.set()

        while True:
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result <= 0:
                break
            if message.message == _WM_HOTKEY:
                self._bridge.activated.emit(int(message.wParam))

        for hotkey_id in self._registered_ids:
            self._unregister(None, hotkey_id)
        self._registered_ids.clear()

    def _dispatch(self, hotkey_id: int) -> None:
        callback = self._callbacks.get(hotkey_id)
        if callback is not None:
            callback()

    def close(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

"""Diálogo de preferências do companion."""

from __future__ import annotations

import contextlib
import ctypes
import logging
import os
import threading
from collections.abc import Callable
from ctypes import wintypes
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from sejoga.distribuicao.updater import Update

    # Resultado da busca em thread: ("ok", Update|None) no sucesso ou ("erro", mensagem).
    ResultadoBusca = tuple[str, "Update | None"] | tuple[str, str]

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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from sejoga.config import Settings, default_config_path, save_settings
from sejoga.desktop import autostart
from sejoga.desktop import desktop_const as C


class SettingsDialog(QDialog):
    """Edita preferências e salva uma cópia validada em TOML."""

    settings_applied = Signal(object)
    # Emitido quando o handoff ao launcher nativo acontece: o companion deve fechar
    # para não ficar renderizando atrás da barra de progresso (fluxo fecha->barra->reabre).
    atualizacao_iniciada = Signal()
    # Resultado da busca de atualizações feita em thread (ver _buscar_atualizacoes).
    _busca_concluida = Signal(object)

    def __init__(self, settings: Settings):
        super().__init__()
        self._settings = settings.model_copy(deep=True)
        self.setWindowTitle("Configurações do SeJoga Companion")
        self.setMinimumWidth(C.DIALOGO_LARGURA_MINIMA)
        self._buscando_atualizacao = False
        self._atualizacao_disponivel: object | None = None

        self.size_input = QSpinBox()
        self.size_input.setRange(C.TAMANHO_JANELA_MINIMO, C.TAMANHO_JANELA_MAXIMO)
        self.size_input.setSingleStep(C.TAMANHO_JANELA_PASSO)
        self.size_input.setSuffix(" px")
        self.size_input.setValue(settings.window.size)

        self.scale_input = QDoubleSpinBox()
        self.scale_input.setRange(C.ESCALA_MINIMA, C.ESCALA_MAXIMA)
        self.scale_input.setSingleStep(C.ESCALA_PASSO)
        self.scale_input.setDecimals(C.ESCALA_CASAS)
        self.scale_input.setValue(settings.window.scale)

        self.outline_input = QCheckBox("Mostrar contorno")
        self.outline_input.setChecked(settings.window.outline_enabled)
        self.outline_width_input = QDoubleSpinBox()
        self.outline_width_input.setRange(C.CONTORNO_LARGURA_MINIMA, C.CONTORNO_LARGURA_MAXIMA)
        self.outline_width_input.setSingleStep(C.CONTORNO_LARGURA_PASSO)
        self.outline_width_input.setDecimals(C.CONTORNO_LARGURA_CASAS)
        self.outline_width_input.setSuffix(" px")
        self.outline_width_input.setValue(settings.window.outline_width)
        self.outline_breath_input = QDoubleSpinBox()
        self.outline_breath_input.setRange(C.CONTORNO_RESPIRACAO_MINIMA, C.CONTORNO_RESPIRACAO_MAXIMA)
        self.outline_breath_input.setSingleStep(C.CONTORNO_RESPIRACAO_PASSO)
        self.outline_breath_input.setDecimals(C.CONTORNO_RESPIRACAO_CASAS)
        self.outline_breath_input.setValue(settings.window.outline_breath)
        self._outline_color = settings.window.outline_color.upper()
        self.outline_color_button = QPushButton()
        self._show_outline_color()
        self.outline_color_button.clicked.connect(self._choose_outline_color)

        self._colorkey_color = settings.window.colorkey_color.upper()
        self.colorkey_color_button = QPushButton()
        self._show_colorkey_color()
        self.colorkey_color_button.clicked.connect(self._choose_colorkey_color)

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
        self.sensitivity_input.setRange(C.FRACAO_MINIMA, C.FRACAO_MAXIMA)
        self.sensitivity_input.setSingleStep(C.FRACAO_PASSO)
        self.sensitivity_input.setValue(settings.music.sensitivity)
        self.dance_chance_input = QDoubleSpinBox()
        self.dance_chance_input.setRange(C.FRACAO_MINIMA, C.FRACAO_MAXIMA)
        self.dance_chance_input.setSingleStep(C.FRACAO_PASSO)
        self.dance_chance_input.setValue(settings.music.dance_chance)
        self.dance_style_input = QComboBox()
        for key, label in (('auto','Automático pelo áudio'), ('head_bob','Head bob tranquilo'),
                           ('hip_hop','Hip hop'), ('rock','Rock'), ('breakdance','Breakdance')):
            self.dance_style_input.addItem(label, key)
        self.dance_style_input.setCurrentIndex(self.dance_style_input.findData(settings.music.dance_style))

        # Canal de atualização (persistido em settings.update.channel).
        self.channel_input = QComboBox()
        for key, label in (("release", "Estável (release)"), ("prerelease", "Pré-release"),
                           ("nightly", "Nightly")):
            self.channel_input.addItem(label, key)
        self.channel_input.setCurrentIndex(self.channel_input.findData(settings.update.channel))

        # Botão "Buscar atualizações" + rótulo de status (busca roda em thread).
        self.check_update_button = QPushButton("Buscar atualizações")
        self.check_update_button.clicked.connect(self._buscar_atualizacoes)
        self.update_status_label = QLabel("")
        self.update_status_label.setWordWrap(True)
        self._busca_concluida.connect(self._ao_concluir_busca)
        update_row = QHBoxLayout()
        update_row.addWidget(self.check_update_button)
        update_row.addWidget(self.update_status_label, 1)

        # (1) Iniciar com o Windows: estado inicial lido do atalho real na Startup.
        self.autostart_input = QCheckBox("Iniciar com o Windows")
        with contextlib.suppress(Exception):
            self.autostart_input.setChecked(autostart.esta_ativo())

        # (7) FPS alvo do mascote (aplicado ao vivo pelo OverlayApp).
        self.fps_input = QSpinBox()
        self.fps_input.setRange(C.FPS_MINIMO, C.FPS_MAXIMO)
        self.fps_input.setSingleStep(C.FPS_PASSO)
        self.fps_input.setSuffix(C.FPS_SUFIXO)
        self.fps_input.setValue(settings.window.fps)

        # (6) Monitor preferido para a posição inicial (Automático = None).
        self.monitor_input = QComboBox()
        self.monitor_input.addItem("Automático", None)
        with contextlib.suppress(Exception):
            import win32api
            for indice in range(len(win32api.EnumDisplayMonitors())):
                self.monitor_input.addItem(f"Monitor {indice + 1}", indice)
        alvo_monitor = self.monitor_input.findData(settings.window.preferred_monitor)
        self.monitor_input.setCurrentIndex(alvo_monitor if alvo_monitor >= 0 else 0)

        # (3) Diagnóstico: liga o fundo rosa do color key (desligado no uso normal).
        self.diagnostic_input = QCheckBox("Diagnóstico (color key rosa)")
        self.diagnostic_input.setChecked(settings.window.diagnostic_colorkey)

        # (4) Nível de log + limpeza dos arquivos de log.
        self.log_level_input = QComboBox()
        for nivel in ("DEBUG", "INFO", "WARNING"):
            self.log_level_input.addItem(nivel, nivel)
        nivel_atual = self.log_level_input.findData(settings.logging.level)
        self.log_level_input.setCurrentIndex(nivel_atual if nivel_atual >= 0 else 0)
        self.clear_logs_button = QPushButton("Limpar logs")
        self.clear_logs_button.clicked.connect(self._limpar_logs)
        log_row = QHBoxLayout()
        log_row.addWidget(self.log_level_input, 1)
        log_row.addWidget(self.clear_logs_button)

        # (2) Atalhos de pastas (logs, capturas) e (5) perfil do usuário.
        self.open_logs_button = QPushButton("Abrir pasta de logs")
        self.open_logs_button.clicked.connect(self._abrir_pasta_logs)
        self.open_captures_button = QPushButton("Abrir pasta de capturas")
        self.open_captures_button.clicked.connect(self._abrir_pasta_capturas)
        pastas_row = QHBoxLayout()
        pastas_row.addWidget(self.open_logs_button)
        pastas_row.addWidget(self.open_captures_button)

        self.profile_path_label = QLabel(str(default_config_path()))
        self.profile_path_label.setWordWrap(True)
        self.open_profile_button = QPushButton("Abrir perfil")
        self.open_profile_button.clicked.connect(self._abrir_perfil)

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
        form.addRow("Respiração do contorno", self.outline_breath_input)
        form.addRow("Cor do color key", self.colorkey_color_button)
        form.addRow(self.physics_input)
        form.addRow(self.idle_input)
        form.addRow("Personalidade", self.personality_input)
        form.addRow(self.react_click_input)
        form.addRow(self.react_drag_input)
        form.addRow("Posição da janela", self.z_order_input)
        form.addRow("Reação à música", self.music_input)
        form.addRow(self.beat_input)
        form.addRow("Sensibilidade da batida", self.sensitivity_input)
        form.addRow("Frequência de dança (0–1)", self.dance_chance_input)  # noqa: RUF001  # intencional: travessao de intervalo (en dash) no rotulo exibido
        form.addRow("Estilo de dança", self.dance_style_input)
        form.addRow("FPS alvo", self.fps_input)
        form.addRow("Monitor preferido", self.monitor_input)
        form.addRow(self.autostart_input)
        form.addRow(self.diagnostic_input)
        form.addRow("Canal de atualização", self.channel_input)
        form.addRow("Atualizações", update_row)
        form.addRow("Nível de log", log_row)
        form.addRow("Pastas", pastas_row)
        form.addRow("Perfil", self.profile_path_label)
        form.addRow("", self.open_profile_button)
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

    def _show_colorkey_color(self) -> None:
        self.colorkey_color_button.setText(self._colorkey_color)
        self.colorkey_color_button.setStyleSheet(
            f"background-color: {self._colorkey_color}; color: #202020;"
        )

    def _choose_colorkey_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._colorkey_color), self, "Cor do color key")
        if color.isValid():
            self._colorkey_color = color.name().upper()
            self._show_colorkey_color()

    def _abrir_pasta(self, pasta) -> None:
        """Abre uma pasta no Explorer, criando-a se faltar (guard clause)."""
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            os.startfile(str(pasta))  # abre pasta do próprio perfil no Explorer
        except OSError as exc:
            logging.getLogger("sejoga").warning("Não foi possível abrir %s: %s", pasta, exc)

    def _abrir_pasta_logs(self) -> None:
        self._abrir_pasta(default_config_path().parent / "logs")

    def _abrir_pasta_capturas(self) -> None:
        self._abrir_pasta(default_config_path().parent / "debug-captures")

    def _abrir_perfil(self) -> None:
        self._abrir_pasta(default_config_path().parent)

    def _limpar_logs(self) -> None:
        """Remove os logs após confirmação, sem derrubar o diálogo em erro."""
        resposta = QMessageBox.question(
            self, "Limpar logs",
            "Remover todos os arquivos de log do perfil?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return
        try:
            from sejoga.render.debug import limpar_logs
            removidos = limpar_logs()
        except OSError as exc:
            QMessageBox.warning(self, "Falha ao limpar logs", str(exc))
            return
        QMessageBox.information(self, "Logs", f"{removidos} arquivo(s) removido(s).")

    def _save(self) -> None:
        updated = self._settings.model_copy(deep=True)
        updated.window.size = self.size_input.value()
        updated.window.scale = self.scale_input.value()
        updated.window.outline_enabled = self.outline_input.isChecked()
        updated.window.outline_color = self._outline_color
        updated.window.colorkey_color = self._colorkey_color
        updated.window.outline_width = self.outline_width_input.value()
        updated.window.outline_breath = self.outline_breath_input.value()
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
        updated.music.dance_style = self.dance_style_input.currentData()
        updated.update.channel = self.channel_input.currentData()
        updated.window.fps = self.fps_input.value()
        updated.window.preferred_monitor = self.monitor_input.currentData()
        updated.window.diagnostic_colorkey = self.diagnostic_input.isChecked()
        updated.window.autostart = self.autostart_input.isChecked()
        updated.logging.level = self.log_level_input.currentData()

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

        # Autostart: a fonte de verdade é o atalho .lnk; a guard clause interna
        # torna isto inerte em modo fonte/dev (sem launcher instalado).
        with contextlib.suppress(Exception):
            if updated.window.autostart:
                autostart.ativar()
            else:
                autostart.desativar()

        self.settings_applied.emit(updated)
        self.accept()

    def _buscar_atualizacoes(self) -> None:
        """Busca o feed do canal selecionado sem bloquear a UI (thread + Signal)."""
        if self._buscando_atualizacao:
            return
        from sejoga.distribuicao.updater import (
            check_update,
            installed_launcher,
            release_para_checagem,
        )

        if installed_launcher() is None:
            self.update_status_label.setText(
                "Instale o SeJoga pelo instalador oficial para buscar atualizações."
            )
            return

        canal = self.channel_input.currentData()
        self._buscando_atualizacao = True
        self._atualizacao_disponivel = None
        self.check_update_button.setEnabled(False)
        self.update_status_label.setText("Buscando atualizações…")

        def tarefa() -> None:
            resultado: ResultadoBusca
            try:
                resultado = ("ok", check_update(release_para_checagem(canal)))
            except Exception as exc:  # degradação graciosa: rede/feed indisponível
                logging.getLogger("sejoga").warning("Busca de atualização falhou: %s", exc)
                resultado = ("erro", str(exc))
            with contextlib.suppress(RuntimeError):
                self._busca_concluida.emit(resultado)

        threading.Thread(target=tarefa, name="sejoga-busca-update", daemon=True).start()

    def _ao_concluir_busca(self, resultado: ResultadoBusca) -> None:
        self._buscando_atualizacao = False
        self.check_update_button.setEnabled(True)
        tipo, valor = resultado
        canal = self.channel_input.currentData()
        if tipo == "erro" or isinstance(valor, str):
            self.update_status_label.setText(f"Erro ao buscar atualizações: {valor}")
            return
        if valor is None:
            self.update_status_label.setText(f"Nenhuma atualização disponível no canal {canal}.")
            return
        self._atualizacao_disponivel = valor
        self.update_status_label.setText(f"Versão {valor.version} disponível no canal {canal}.")
        resposta = QMessageBox.question(
            self, "Atualização disponível",
            f"Versão {valor.version} está disponível no canal {canal}.\n\n"
            "Deseja atualizar agora? O Mário será fechado e aparecerá apenas uma barra "
            "de progresso. O Windows pedirá permissão de administrador e o Mário será "
            "reaberto ao terminar (ou se você cancelar a permissão). "
            "Suas configurações serão preservadas.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resposta == QMessageBox.StandardButton.Yes:
            self._iniciar_atualizacao(canal)

    def _iniciar_atualizacao(self, canal: str) -> None:
        """Delega ao launcher nativo, apontando o channel-info.json ao canal."""
        from sejoga.distribuicao.updater import installed_launcher, reescrever_canal_channel_info

        launcher = installed_launcher()
        if launcher is None:
            return
        reescrever_canal_channel_info(launcher.parent / "channel-info.json", canal)
        import win32api
        try:
            win32api.ShellExecute(0, "open", str(launcher), "--update", str(launcher.parent), 1)
        except Exception as exc:
            self.update_status_label.setText(f"Atualização não iniciada: {exc}")
        else:
            # Handoff feito: fecha o diálogo e sinaliza para o companion encerrar.
            # O launcher assume a barra e reabre o mascote ao terminar.
            self.accept()
            self.atualizacao_iniciada.emit()


_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
# Base dos ids de atalho global ("SJ" em ASCII); cada atalho soma seu índice.
_HOTKEY_ID_BASE = 0x534A
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

    _MODIFIERS: ClassVar[dict[str, int]] = {
        "alt": _MOD_ALT,
        "ctrl": _MOD_CONTROL,
        "control": _MOD_CONTROL,
        "shift": _MOD_SHIFT,
        "win": _MOD_WIN,
        "meta": _MOD_WIN,
    }
    _KEYS: ClassVar[dict[str, int]] = {
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
            hotkey_id = _HOTKEY_ID_BASE + index
            self._shortcuts.append((hotkey_id, shortcut, modifiers | _MOD_NOREPEAT, key))
            self._callbacks[hotkey_id] = callback

        self._thread = threading.Thread(target=self._message_loop, name="global-hotkeys", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=C.THREAD_TIMEOUT)

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
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)
        if self._thread.is_alive():
            self._thread.join(timeout=C.THREAD_TIMEOUT)

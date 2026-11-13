"""
OverlayWindow — Janela transparente always-on-top com render 3D (Panda3D) + PySide6 system tray.

Arquitetura:
- Panda3D cria a janela principal (HWND nativo) via ShowBase
- Win32 API aplica: WS_EX_LAYERED + color key (magenta) + click-through seletivo
- PySide6 usado APENAS para QSystemTrayIcon (system tray)
- Eventos de mouse/drag via Win32 polling no task loop do Panda3D
- Z-order toggle: HWND_TOPMOST / HWND_BOTTOM / HWND_NOTOPMOST
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import math
import os
import sys
import time
from typing import Any, cast

# Win32 API
import win32api
import win32con
import win32gui

# Load Qt before Panda3D: their Windows bundles ship different MSVC runtime
# DLLs, and the first loaded copy wins for the whole process.
from PySide6.QtGui import QActionGroup, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

# isort: split
# Configure Panda before ShowBase, but only after Qt's runtime DLLs are loaded.
from panda3d.core import loadPrcFileData

loadPrcFileData("", "window-type none")
loadPrcFileData("", "load-display pandagl")
loadPrcFileData("", "aux-display p3tinydisplay")
loadPrcFileData("", "framebuffer-alpha 1")
loadPrcFileData("", "framebuffer-multisample 1")
loadPrcFileData("", "multisamples 4")
loadPrcFileData("", "win-size 480 480")
loadPrcFileData("", "win-origin 0 0")
loadPrcFileData("", "undecorated 1")
loadPrcFileData("", "cursor-hidden 0")

# Panda3D imports (depois do loadPrcFileData)
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import (
    FrameBufferProperties,
    Point3,
    Vec3,
    WindowProperties,
)

from sejoga.animacao.animacao_entrada import IntroAnimation, IntroFrame
from sejoga.animacao.animacao_saida import ExitAnimation
from sejoga.animacao.atencao_hover import HoverAttention

# Project imports
from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
from sejoga.animacao.foco_atencao import (
    PRIORIDADE_BEAT,
    PRIORIDADE_BORDA,
    PRIORIDADE_CURSOR,
    PRIORIDADE_FOCO,
    GateAtencao,
    GatilhoAtencao,
)
from sejoga.animacao.interacao_mouse import MouseInteraction
from sejoga.configuracao import Settings, load_settings, save_settings
from sejoga.desktop.fisica import create_physics
from sejoga.desktop.integracao_desktop import DesktopIntegration
from sejoga.desktop.interface import HotkeyManager, SettingsDialog
from sejoga.desktop.registro_bandeja import TrayRegistration
from sejoga.musica.escuta_musica import MusicListener
from sejoga.nucleo.esqueleto import IdlePersonality
from sejoga.nucleo.recursos import brand_dir
from sejoga.render.chroma_tuning import derivar_chroma, pixel_e_chroma
from sejoga.render.depuracao import DebugTools, configure_logging
from sejoga.render.envelope_janela import MARGEM_ANTICORTE, degrau_para
from sejoga.render.janela_const import (
    ATENCAO_BORDA_MARGEM_PX,
    COLISAO_DIVISOR_DIRECAO,
    COLISAO_DIVISOR_FORCA,
    DELAY_CALIBRAR_COLOR_KEY,
    DELAY_RESTAURAR_Z_ORDER,
    DOUBLE_CLICK_DISTANCIA_MINIMA,
    DOUBLE_CLICK_DIVISOR_METRICA,
    DRAG_DIVISOR_DIRECAO,
    DRAG_DIVISOR_INTENSIDADE,
    FRAMEBUFFER_ALPHA_BITS,
    FRAMEBUFFER_DEPTH_BITS,
    FRAMEBUFFER_MULTISAMPLES,
    FRAMEBUFFER_STENCIL_BITS,
    MARGEM_CANTO_HORIZONTAL,
    MARGEM_CANTO_VERTICAL,
    MILISSEGUNDOS_POR_SEGUNDO,
    OFFSET_APOIO_FISICO,
    TILT_DIVISOR_VELOCIDADE,
    TILT_GRAUS_MAXIMO,
    TILT_VELOCIDADE_MINIMA,
    TRAY_NOTIFICACAO_ATALHO_MS,
    TRAY_NOTIFICACAO_MS,
    TRAY_NOTIFICACAO_REINICIO_MS,
)
from sejoga.render.renderizador import Panda3DRenderer
from sejoga.render.sobreposicao_win32 import (
    COLOR_KEY,
    GWL_EXSTYLE,
    HWND_BOTTOM,
    HWND_NOTOPMOST,
    HWND_TOPMOST,
    LWA_ALPHA,
    LWA_COLORKEY,
    SWP_NOACTIVATE,
    SWP_NOMOVE,
    SWP_NOSIZE,
    SWP_NOZORDER,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOPMOST,
    WS_EX_TRANSPARENT,
)

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

logger = logging.getLogger(__name__)

# ============================================================
# OverlayApp - Main Application
# ============================================================


class OverlayApp(ShowBase):
    """Aplicação principal - Panda3D ShowBase + Win32 layered window + PySide6 tray."""

    def __init__(self, settings: Settings):  # noqa: PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        """Monta a janela, o renderer, a física, a bandeja e as tarefas."""
        DesktopIntegration.set_app_id()
        ShowBase.__init__(self, windowType="none")

        self.settings = settings
        self.settings_obj = settings
        self.renderer: Any = None
        self.physics: Any = None
        self.music_listener: MusicListener | None = None
        self.debug_tools: DebugTools | None = None
        self.desktop: DesktopIntegration | None = None
        self._exit_started = None
        self._exit_style = "classic"
        self._exit_preview = False
        self._exit_last_tick = time.perf_counter()
        self._intro_started: float | None = None
        self._intro_motion: IntroAnimation | None = None
        self._intro_last_loco: str | None = None
        self._force_exit = False

        self._is_topmost = settings.window.always_on_top
        self._is_bottom = settings.window.mode == "desktop"
        self._background_key = COLOR_KEY
        self._drag_active = False
        self._drag_start_pos: tuple[int, int] = (0, 0)
        self._window_start_pos: tuple[int, int] = (0, 0)
        self._drag_direction = 0.0
        self._drag_intensity = 0.0
        self._animation_last_tick = time.perf_counter()
        self._physics_last_tick = time.perf_counter()
        self._mouse_hovered = False
        self._mouse_local = (0, 0)
        self._mouse_screen = None
        self._body_grab_point = None
        self._native_buttons: set[str] = set()
        self._hover_attention = HoverAttention()
        # Camada de olhar/atenção: escolhe o alvo entre gatilhos concorrentes.
        self._gate_atencao = GateAtencao()
        # Foco em foreground usado pelo gatilho de atenção (distinto do
        # _hover_foreground do gate de hover): marca "algo mudou" por um curto
        # tempo para o mascote virar a cabeça naquela direção.
        self._atencao_foreground = win32gui.GetForegroundWindow()
        self._atencao_foco_restante = 0.0
        self._hover_foreground = win32gui.GetForegroundWindow()
        self._busy_cursors = {
            win32gui.LoadCursor(0, cursor)
            for cursor in (
                win32con.IDC_IBEAM,
                win32con.IDC_HAND,
                win32con.IDC_SIZEALL,
                win32con.IDC_SIZENS,
                win32con.IDC_SIZEWE,
            )
        }
        self.mouse_interaction = MouseInteraction(
            buttons=self._mouse_buttons(),
            double_click_seconds=user32.GetDoubleClickTime()
            / MILISSEGUNDOS_POR_SEGUNDO,
            double_click_distance=max(
                DOUBLE_CLICK_DISTANCIA_MINIMA,
                win32api.GetSystemMetrics(win32con.SM_CXDOUBLECLK)
                / DOUBLE_CLICK_DIVISOR_METRICA,
            ),
        )
        self.animation_controller: AnimationController | None = None

        self.qt_app: Any = None
        self.tray_icon: Any = None
        self.tray_menu: Any = None
        self._settings_dialog: SettingsDialog | None = None
        self._topmost_action: Any = None
        self._debug_action: Any = None
        self._recording_action: Any = None
        self.hotkey_manager: HotkeyManager | None = None

        self.logger = configure_logging()
        self._drag_active = False
        self._drag_start_pos = (0, 0)
        self._window_start_pos = (0, 0)
        # Estado do hot path pré-inicializado (evita hasattr/getattr por frame).
        size = self.settings.window.size
        self._physics_local = (
            size / 2,
            size - self.settings.physics.mascot_radius - OFFSET_APOIO_FISICO,
        )
        self._offset_mascote = self._physics_local
        self._mascot_screen = self._offset_mascote
        self._desktop_rect = None
        self._canvas_origin = None
        self._canvas_request = None
        self._canvas_shrink_in = 0.0
        self._canvas_measure_in = 0.0
        self._display_check = 0.0
        self._destino_caminhada_x: float | None = None

        self._init_pyside()
        self._create_panda_window()
        self._setup_win32()
        self._init_renderer()
        self._setup_mouse_hooks()
        if self.renderer and self.renderer.rig:
            self.animation_controller = AnimationController(
                self.renderer.rig, model=self._carregar_modelo_colisao()
            )
            self.animation_controller.set_idle_personality(
                self.settings.behavior.idle_personality
            )
        if self.renderer:
            self.debug_tools = DebugTools(
                self,
                self._on_recording_changed,
                self.settings.hotkeys.toggle_debug,
            )
        self.music_listener = MusicListener(self.settings.music)
        self.music_listener.start()
        self._setup_tray()
        self._setup_timers()
        self._hotkey_callbacks = {
            "toggle_overlay": self.toggle_visibility,
            "open_settings": self.open_settings_dialog,
            "summon": self.summon_overlay,
            "toggle_debug": self.toggle_debug_overlay,
            "capture_frame": self.capture_debug_frame,
            "toggle_frame_recording": self.toggle_frame_recording,
        }
        self.hotkey_manager = HotkeyManager(
            self.settings.hotkeys.model_dump(), self._hotkey_callbacks
        )
        if self.hotkey_manager.unavailable_shortcuts:
            self.logger.warning(
                "Unavailable global shortcuts: %s",
                ", ".join(self.hotkey_manager.unavailable_shortcuts),
            )
        self._apply_window_state()
        self.taskMgr.doMethodLater(
            DELAY_RESTAURAR_Z_ORDER, self._restore_z_order, "restore-z-order"
        )
        self.taskMgr.doMethodLater(
            DELAY_CALIBRAR_COLOR_KEY, self._calibrate_background_key, "background-key"
        )
        self._init_physics()
        icon = brand_dir() / "companion.ico"
        # _init_pyside() (chamado acima) ja definiu qt_app.
        assert self.qt_app is not None
        self.qt_app.setWindowIcon(QIcon(str(icon)))
        self.desktop = DesktopIntegration(self.hwnd, icon)
        if self.settings.window.intro_animation != "padrao":
            self.start_intro(self.settings.window.intro_animation)

        self.logger.info("OverlayApp inicializado.")

    def _init_pyside(self) -> None:
        self.qt_app = QApplication.instance() or QApplication(sys.argv)
        self.qt_app.setApplicationName("SeJoga Companion")
        self.qt_app.setApplicationDisplayName("SeJoga Desktop Companion")
        self.qt_app.setOrganizationName("ArchVeketo")
        self.qt_app.setQuitOnLastWindowClosed(False)

    def _create_panda_window(self) -> None:
        wp = WindowProperties()
        wp.setSize(self.settings.window.size, self.settings.window.size)
        wp.setOrigin(0, 0)
        wp.setFullscreen(False)
        wp.setCursorHidden(False)
        wp.setTitle("SeJogaDesktopCompanion")

        fbprops = FrameBufferProperties()
        fbprops.setRgbColor(True)
        fbprops.setAlphaBits(FRAMEBUFFER_ALPHA_BITS)
        fbprops.setDepthBits(FRAMEBUFFER_DEPTH_BITS)
        fbprops.setStencilBits(FRAMEBUFFER_STENCIL_BITS)
        fbprops.setMultisamples(FRAMEBUFFER_MULTISAMPLES)

        self.openDefaultWindow(props=wp, fbprops=fbprops)

        # Clear com a cor do color key configurada (alpha zero preserva a
        # cobertura MSAA que o chroma resolve usa).
        self._chroma = derivar_chroma(self.settings.window.colorkey_color)
        self.win.setClearColor(self._chroma.clear_rgba)
        self.win.setClearColorActive(True)

        self.disableMouse()

    def windowEvent(self, win):
        """Confirma origem, lente e framebuffer na notificação do Panda."""
        super().windowEvent(win)
        if win == self.win and getattr(self, "_canvas_request", None) is not None:
            self._confirmar_canvas()

    def _get_hwnd(self) -> int:
        """Extract integer HWND from Panda3D WindowHandle."""
        wh = self.win.getWindowHandle()
        # Try various WindowHandle API methods
        if hasattr(wh, "getHandle"):
            return int(wh.getHandle())
        elif hasattr(wh, "asInt"):
            return wh.asInt()
        elif hasattr(wh, "__int__"):
            return int(wh)
        elif hasattr(wh, "handle"):
            return int(wh.handle)
        else:
            # String representation is typically a hex address like '0000000000360D5E'
            wh_str = str(wh).strip()
            if wh_str.startswith("0x") or all(
                c in "0123456789abcdefABCDEF" for c in wh_str
            ):
                return int(wh_str, 16)
            return int(wh_str)

    def _setup_win32(self) -> None:
        self.hwnd = self._get_hwnd()

        ex_style = win32gui.GetWindowLong(self.hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_LAYERED | WS_EX_NOACTIVATE
        if self._is_topmost:
            ex_style |= WS_EX_TOPMOST
        win32gui.SetWindowLong(self.hwnd, GWL_EXSTYLE, ex_style)

        self._refresh_background_mode()
        self._update_z_order()

        with contextlib.suppress(Exception):
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

    def _refresh_background_mode(self) -> None:
        """Windows uses the final framebuffer color, after PBR tone mapping."""
        ex_style = win32gui.GetWindowLong(self.hwnd, GWL_EXSTYLE)
        if ex_style & WS_EX_TRANSPARENT:
            win32gui.SetWindowLong(
                self.hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_TRANSPARENT
            )
        # LWA_ALPHA mostra o fundo (rosa) do color key: usado pelo HUD de
        # diagnóstico e pelo toggle explícito diagnostic_colorkey da config.
        mostrar_fundo = (
            self.debug_tools and self.debug_tools.visible
        ) or self.settings.window.diagnostic_colorkey
        if mostrar_fundo:
            win32gui.SetLayeredWindowAttributes(
                self.hwnd, self._background_key, 255, LWA_ALPHA
            )
        else:
            win32gui.SetLayeredWindowAttributes(
                self.hwnd, self._background_key, 255, LWA_COLORKEY
            )

    def _calibrate_background_key(self, task: Task) -> int:
        if not win32gui.IsWindow(self.hwnd):
            return Task.done
        image = self.win.getScreenshot()
        if image:
            pixels = memoryview(bytes(image.getRamImageAs("RGB")))
            largura, altura = image.getXSize(), image.getYSize()
            cantos = (0, largura - 1, largura * (altura - 1), largura * altura - 1)
            amostras = {tuple(pixels[3 * canto : 3 * canto + 3]) for canto in cantos}
            if len(amostras) == 1 and pixel_e_chroma((rgb := amostras.pop()), self._chroma):
                red, green, blue = rgb
                self._background_key = red | (green << 8) | (blue << 16)
                self._refresh_background_mode()
        return Task.done

    def _update_z_order(self) -> None:
        order = (
            HWND_BOTTOM
            if self._is_bottom
            else HWND_TOPMOST
            if self._is_topmost
            else HWND_NOTOPMOST
        )
        win32gui.SetWindowPos(
            self.hwnd, order, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        )

    def _restore_z_order(self, task: Task) -> int:
        if win32gui.IsWindow(self.hwnd):
            if self.desktop:
                self.desktop.apply_style()
            self._update_z_order()
        return Task.done

    def _retangulo_monitor_preferido(self) -> tuple[int, int, int, int]:
        """Retângulo de trabalho do monitor preferido (left, top, right, bottom).

        Resolve o índice de ``settings.window.preferred_monitor`` pela ordem de
        ``EnumDisplayMonitors``; se ``None`` ou o índice não existir mais, recai
        no monitor primário.
        """
        indice = self.settings.window.preferred_monitor
        if indice is not None:
            with contextlib.suppress(Exception):
                monitores = win32api.EnumDisplayMonitors()
                if 0 <= indice < len(monitores):
                    handle = monitores[indice][0]
                    return tuple(win32api.GetMonitorInfo(handle)["Work"])
        # Fallback: monitor primário (origem 0,0 pela métrica de tela).
        return (0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))

    def _apply_window_state(self) -> None:
        """Aplica tamanho, posição inicial e estilos definidos nas configurações."""
        size = self.settings.window.size
        start_position = self.settings.window.start_position
        if start_position is None:
            left, top, right, bottom = self._retangulo_monitor_preferido()
            x = max(left, right - size - MARGEM_CANTO_HORIZONTAL)
            y = max(top, bottom - size - MARGEM_CANTO_VERTICAL)
        else:
            x, y = (int(start_position[0]), int(start_position[1]))

        self._mascot_screen = (x + self._offset_mascote[0], y + self._offset_mascote[1])
        self._sincronizar_desktop(0.0)
        self._refresh_background_mode()
        self._update_z_order()

    def _init_renderer(self) -> None:
        # Panda3DRenderer is defined in this same file
        self.renderer = Panda3DRenderer(
            self, self._get_hwnd(), self.settings.window.size, self.settings.window.size
        )

    def _carregar_modelo_colisao(self):
        """Carrega o ``Model`` puro para a correção pontual de colisão (FEAT-B).

        A correção amortecida no ``AnimationController`` mede as partes do rig a
        partir deste modelo. É o mesmo glTF/GLB do render, lido pelo leitor puro
        (``sejoga.nucleo.modelo``), independente do Panda3D. Falha de carga NÃO derruba
        o companion: devolve ``None`` e a correção fica inerte.
        """
        try:
            from sejoga.nucleo.modelo import load_model
            from sejoga.nucleo.recursos import resolve_model

            return load_model(resolve_model())
        except Exception:
            return None

    def _init_physics(self) -> None:
        """Inicializa sistema de física 2D (pymunk)."""
        if not self.settings.physics.enabled:
            return

        # Obtém dimensões da tela
        import win32api

        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)

        self.physics = create_physics(
            mascot_radius=self.settings.physics.mascot_radius,
            screen_width=screen_w,
            screen_height=screen_h,
            own_hwnd=self.hwnd,
            own_pid=os.getpid(),
            settings=self.settings,
        )

        self._set_physics_monitor(self._mascot_screen)
        self.physics.set_position(*self._mascot_screen)
        self.physics.set_gravity(True)
        self._last_rest_position: tuple[int, int] | None = None
        self._was_grounded = False
        self.physics.on_collision = self._on_physics_collision

        # Configura callback de mudança de estado
        self.physics.on_state_change = self._on_physics_state_change

        # Adiciona task de física (120 Hz)
        self.taskMgr.add(self._physics_tick, "physics-tick", priority=10)

    def _on_physics_state_change(self, state) -> None:
        """Callback quando estado da física muda."""
        if not win32gui.IsWindow(self.hwnd):
            return
        if state.grounded and not self._was_grounded and self.animation_controller:
            self.animation_controller.interact("land")
        self._was_grounded = state.grounded
        self._posicionar_mascote(*state.position)
        x = round(state.position[0] - self._offset_mascote[0])
        y = round(state.position[1] - self._offset_mascote[1])
        self.settings.window.start_position = (x, y)
        if (
            state.grounded
            and math.hypot(*state.velocity) < 5
            and self._last_rest_position != (x, y)
        ):
            self._last_rest_position = (x, y)
            self._persist_settings()

    def _set_physics_monitor(self, point) -> None:
        monitor = win32api.MonitorFromPoint(tuple(map(int, point)), 2)
        self.physics.set_bounds(win32api.GetMonitorInfo(monitor)["Work"])

    def _on_physics_collision(self, kind, velocity) -> None:
        self.logger.info("Physics %s velocity=%s", kind, velocity)
        if self.animation_controller:
            self.animation_controller.interact(
                "hit",
                direction=max(-1, min(1, velocity[0] / COLISAO_DIVISOR_DIRECAO)),
                strength=min(2, math.hypot(*velocity) / COLISAO_DIVISOR_FORCA),
            )

    def _physics_tick(self, task: Task) -> int:
        """Task de física - roda a 120 Hz."""
        if not self.physics:
            return Task.cont
        if not win32gui.IsWindow(self.hwnd):
            self.userExit()
            return Task.done

        now = time.perf_counter()
        dt = now - self._physics_last_tick
        self._physics_last_tick = now
        if not self._drag_active and self._exit_started is None:
            self.physics.step(dt)
        return Task.cont

    def _sync_model_with_physics(self) -> None:
        """Sincroniza modelo 3D com estado da física."""
        if not self.physics or not self.renderer or not self.renderer.model_np:
            return

        state = self.physics.get_state()
        # Durante drag, sempre atualiza a posição para seguir o mouse em tempo
        # real e evitar que o personagem fique travado no ar.
        pos = self._physics_local
        if (
            self._drag_active
            or self._intro_motion is not None
            or pos != getattr(self, "_last_model_pos", None)
        ):
            self._last_model_pos = pos
            self.renderer.set_model_screen_position(*pos)

        vx, vy = state.velocity
        tilt_z = getattr(self, "_last_tilt_z", None)
        if not state.grounded and math.hypot(vx, vy) > TILT_VELOCIDADE_MINIMA:
            new_z = max(
                -TILT_GRAUS_MAXIMO,
                min(TILT_GRAUS_MAXIMO, -vx / TILT_DIVISOR_VELOCIDADE),
            )
            if new_z != tilt_z:
                self._last_tilt_z = new_z
                self.renderer.set_model_rotation(z=new_z)
        else:
            if tilt_z is not None:
                self._last_tilt_z = None
                self.renderer.set_model_rotation()

    # Janela (em segundos) em que uma troca de foreground mantém a atenção do
    # mascote virada para a janela recém-ativada. CALIBRÁVEL (validar na GPU).
    _ATENCAO_FOCO_SEGUNDOS = 1.2
    # Energia mínima da batida para virar micro-reação de atenção rítmica.
    _ATENCAO_BEAT_FORCA_MINIMA = 0.15

    def _adicionar_gatilho_beat(self, gatilhos, music, centro_tela, largura) -> None:
        """Alterna o lado na transicao da batida musical sem sortear a cada quadro."""
        beat_ativo = bool(
            music
            and music.beat_detected
            and music.audio_level >= self._ATENCAO_BEAT_FORCA_MINIMA
        )
        if beat_ativo:
            if not getattr(self, "_beat_atencao_anterior", False):
                self._beat_atencao_lado = -getattr(self, "_beat_atencao_lado", -1.0)
            ponto_beat = (
                centro_tela[0] + self._beat_atencao_lado * largura,
                centro_tela[1],
            )
            gatilhos.append(
                GatilhoAtencao(
                    "beat", ponto_beat, PRIORIDADE_BEAT, forca=music.audio_level
                )
            )
        self._beat_atencao_anterior = beat_ativo

    def _resolver_alvo_atencao(self, dt, music, state):  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        """Monta os gatilhos não-invasivos e devolve o alvo de olhar do quadro.

        Gatilhos (nenhum lê conteúdo/pixels da tela):
        - cursor GLOBAL (win32api): olhar para o cursor mesmo fora da janela;
        - troca de janela em foco (GetForegroundWindow): "algo mudou", vira a
          cabeça para a direção/borda da nova janela por um curto tempo;
        - batida/energia (music_listener): micro-reação rítmica de atenção;
        - borda de tela mais próxima: olhar para a borda de onde "veio" algo;
        """
        self._atencao_foco_restante = max(0.0, self._atencao_foco_restante - dt)
        gatilhos: list[GatilhoAtencao] = []

        largura = altura = self.settings.window.size
        centro_tela = (self._mascot_screen[0], self._mascot_screen[1] - altura * 0.25)
        origem = (centro_tela[0] - largura / 2, centro_tela[1] - altura * 0.52)

        # Cursor global: o alvo é a posição do cursor em coordenadas de tela.
        if self._mouse_screen is not None:
            gatilhos.append(
                GatilhoAtencao("cursor", self._mouse_screen, PRIORIDADE_CURSOR)
            )

        # Troca de janela em foco: marca atenção por _ATENCAO_FOCO_SEGUNDOS e
        # olha para o centro da janela recém-ativada (borda de onde "surgiu").
        foreground = win32gui.GetForegroundWindow()
        if foreground != self._atencao_foreground:
            self._atencao_foreground = foreground
            if foreground and foreground != self.hwnd:
                self._atencao_foco_restante = self._ATENCAO_FOCO_SEGUNDOS
                self._atencao_foco_ponto = self._centro_da_janela(
                    foreground, centro_tela
                )
        if self._atencao_foco_restante > 0 and getattr(
            self, "_atencao_foco_ponto", None
        ):
            gatilhos.append(
                GatilhoAtencao("foco", self._atencao_foco_ponto, PRIORIDADE_FOCO)
            )

        self._adicionar_gatilho_beat(gatilhos, music, centro_tela, largura)

        # Borda de tela mais próxima da posição física do mascote: olhar para a
        # borda de onde "veio" algo (ex.: o mascote acabou de bater na borda).
        if state is not None:
            ponto_borda = self._borda_mais_proxima(state.position)
            if ponto_borda is not None:
                gatilhos.append(GatilhoAtencao("borda", ponto_borda, PRIORIDADE_BORDA))

        alvo = self._gate_atencao.atualizar(
            dt,
            gatilhos=gatilhos,
            origem_janela=(origem[0], origem[1]),
            largura=largura,
            altura=altura,
            habilitado=self.settings.behavior.react_to_attention,
            ambiente_habilitado=False,
        )
        return alvo

    def _centro_da_janela(self, hwnd, padrao):
        """Centro de uma janela em coordenadas de tela, com fallback seguro."""
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except win32gui.error:
            return padrao
        return ((left + right) * 0.5, (top + bottom) * 0.5)

    def _borda_mais_proxima(self, posicao):
        """Ponto na borda do monitor mais próxima da posição física do mascote.

        Só dispara perto da borda (dentro de ATENCAO_BORDA_MARGEM_PX) para não
        competir o tempo todo com cursor/foco.
        """
        try:
            monitor = win32api.MonitorFromPoint(tuple(map(int, posicao)), 2)
            left, top, right, bottom = win32api.GetMonitorInfo(monitor)["Work"]
        except Exception:
            return None
        x, y = posicao
        dist = {
            "esq": x - left,
            "dir": right - x,
            "cima": y - top,
            "baixo": bottom - y,
        }
        lado = min(dist, key=dist.get)
        if dist[lado] > ATENCAO_BORDA_MARGEM_PX:
            return None
        return {
            "esq": (left, y),
            "dir": (right, y),
            "cima": (x, top),
            "baixo": (x, bottom),
        }[lado]

    def _atualizar_intro_e_musica(self, now: float):
        intro_frame = None
        if self._intro_motion is not None and self._intro_started is not None:
            intro_frame = self._intro_motion.sample(now - self._intro_started)
            if intro_frame.locomotion == "land" and self._intro_last_loco != "land":
                self.animation_controller.interact("land", strength=0.9)
            elif intro_frame.locomotion == "virtual_insanity" and (
                self.animation_controller._reaction is None
                or self.animation_controller._reaction.value != "virtual_insanity"
            ):
                self.animation_controller._cooldowns.pop("virtual_insanity", None)
                self.animation_controller.interact(
                    "virtual_insanity", direction=float(self._intro_motion.side)
                )
            elif (
                intro_frame.locomotion == "idle"
                and self._intro_last_loco == "virtual_insanity"
                and self.animation_controller._reaction
                == AnimationState.VIRTUAL_INSANITY
            ):
                self.animation_controller._reaction = None
            self._intro_last_loco = intro_frame.locomotion
            self.animation_controller.definir_orientacao("frente")

        music = self.music_listener.snapshot if self.music_listener else None
        music_playing = bool(music and music.is_playing)
        music_intensity = music.audio_level if music else 0.0
        if music_playing and music_intensity == 0.0:
            music_intensity = 0.25
        if intro_frame is not None and intro_frame.locomotion == "dance":
            music_playing = True
            music_intensity = 0.65
        return intro_frame, music, music_playing, music_intensity

    def _animation_tick(self) -> None:  # noqa: PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        if self._exit_started is not None:
            self._exit_tick()
            return
        if not self.renderer or not self.animation_controller:
            return

        now = time.perf_counter()
        dt = now - self._animation_last_tick
        self._animation_last_tick = now
        state = self.physics.get_state() if self.physics else None
        if self.physics:
            self.animation_controller.agencia.definir_limites_tela(*self.physics.bounds)
        self.renderer._physics_velocity = state.velocity if state else (0.0, 0.0)
        self._atualizar_caminhada_horizontal(state)
        state = self.physics.get_state() if self.physics else None

        intro_frame, music, music_playing, music_intensity = (
            self._atualizar_intro_e_musica(now)
        )
        self.animation_controller.dance_motion.override = (
            self.settings.music.dance_style
        )
        alvo = self._resolver_alvo_atencao(dt, music, state)
        vel_ctrl = state.velocity if state else (0.0, 0.0)
        grounded_ctrl = state.grounded if state else True
        gravity_ctrl = state.gravity_active if state else False
        dragging_ctrl = self._drag_active
        if intro_frame is not None:
            dragging_ctrl = False
            if intro_frame.locomotion == "run":
                vel_ctrl = (660.0 * self._intro_motion.side, 0.0)
                grounded_ctrl = True
                gravity_ctrl = False
            elif intro_frame.locomotion == "fall":
                vel_ctrl = (0.0, 380.0)
                grounded_ctrl = False
                gravity_ctrl = True
        pose = self.animation_controller.update(
            dt,
            velocity=vel_ctrl,
            grounded=grounded_ctrl,
            gravity_active=gravity_ctrl,
            dragging=dragging_ctrl,
            grab_part=getattr(self, "_body_grab_part", "body"),
            drag_direction=self._drag_direction,
            drag_intensity=self._drag_intensity,
            music_playing=music_playing,
            music_intensity=music_intensity,
            music_bass=music.bass_level if music else 0,
            music_bpm=music.bpm if music else None,
            dance_chance=self.settings.music.dance_chance,
            react_to_beat=self.settings.music.react_to_beat,
            beat_detected=bool(music and music.beat_detected),
            idle_enabled=self.settings.behavior.idle_animation,
            sleep_after_idle_seconds=self.settings.behavior.sleep_after_idle_seconds,
            hovered=self._mouse_hovered and self.settings.behavior.react_to_click,
            look_direction=alvo.direcao,
            look_vertical=alvo.vertical,
            fonte_atencao=alvo.fonte,
            pointer_position=self._mouse_screen,
        )
        if (
            alvo.surpresa
            and self.settings.behavior.react_to_click
            and alvo.fonte not in ("beat", "ambiente")
        ):
            # Susto temporizado no mesmo padrão das outras reações.
            self.animation_controller.interact(
                "surprise", direction=alvo.direcao, strength=alvo.forca
            )
        self.renderer.aplicar_profundidade_visual(
            self.animation_controller.profundidade.escala_atual,
            self.animation_controller.profundidade.subida_atual,
        )
        self.renderer.apply_rig_pose(pose)
        self.renderer.lower_body.apply(
            self.animation_controller.leg_motion.pose,
            bool(not self._drag_active and (state.grounded if state else True)),
            dt=dt,
        )
        self.renderer.apply_body_motion(
            self.animation_controller.body_motion.snapshot,
            self._body_grab_point,
            grounded=state.grounded if state else True,
            dragging=self._drag_active,
            # Giro de corpo PONTUAL: no uso normal (idle/hover) o corpo fica de
            # frente. O olhar (alvo.direcao) segue movendo cabeça/tronco/braço
            # via look_direction/look_vertical no controller, mas NÃO vira mais
            # o corpo. O giro só ocorre por angulo_giro_pedido explícito
            # (pacotes de animação, orientação manual ou caminhada).
            direcao_olhar=0.0,
            angulo_giro_pedido=self.animation_controller.angulo_giro_pedido,
        )
        self.renderer.update_appendages(
            dt, self.animation_controller.appendage_remaining > 0
        )
        # ── Controle do cursor Win32 durante teimosia (manifesto §1.4) ───
        self._sincronizar_cursor_teimosia()
        self._sincronizar_desktop(dt)
        self._sincronizar_mouse_e_abertura(state, intro_frame, dt)

    def _sincronizar_mouse_e_abertura(
        self,
        state: Any,
        intro_frame: IntroFrame | None,
        dt: float,
    ) -> None:
        if self.renderer.tentacle_director:
            mouse_world = Point3(
                (self._mouse_local[0] - self.renderer.width / 2)
                * self.renderer._view_width
                / self.renderer.width,
                0,
                self.renderer._view_target_z
                + (self.renderer.height / 2 - self._mouse_local[1])
                * self.renderer._view_height
                / self.renderer.height,
            )
            mouse_local = self.renderer.model_np.getRelativePoint(
                self.render, mouse_world
            )
            self.renderer.tentacle_director.set_mouse(mouse_local, Vec3(0))
        if state:
            self._sync_model_with_physics()
        if intro_frame is not None:
            self.renderer.apply_intro_effect(intro_frame)
            if intro_frame.finished:
                self._intro_motion = None
                self._intro_started = None
                self._intro_last_loco = None
                self._last_model_pos = None
                if self.animation_controller._reaction == AnimationState.VIRTUAL_INSANITY:
                    self.animation_controller._reaction = None
                self.animation_controller.definir_orientacao(None)
                self.renderer.restore_intro_effect()
        if self.debug_tools:
            self.debug_tools.update(dt)

    def set_debug_overlay(self, enabled: bool) -> None:
        """Liga ou desliga o overlay de depuração."""
        if self.debug_tools:
            self.debug_tools.set_visible(enabled)
            self._refresh_background_mode()
            self._set_action_checked(self._debug_action, enabled)

    def toggle_debug_overlay(self) -> None:
        """Alterna o overlay de depuração."""
        if self.debug_tools:
            self.set_debug_overlay(not self.debug_tools.visible)

    def capture_debug_frame(self) -> None:
        """Captura um frame de depuração."""
        if not self.debug_tools:
            return
        path = self.debug_tools.capture_once()
        if self.tray_icon:
            if path:
                self.tray_icon.showMessage(
                    "Frame capturado",
                    str(path),
                    QSystemTrayIcon.MessageIcon.Information,
                    TRAY_NOTIFICACAO_MS,
                )
            else:
                self.tray_icon.showMessage(
                    "Captura falhou",
                    "Veja o log para detalhes.",
                    QSystemTrayIcon.MessageIcon.Warning,
                    TRAY_NOTIFICACAO_MS,
                )

    def set_frame_recording(self, enabled: bool) -> None:
        """Liga ou desliga a gravação de frames."""
        if self.debug_tools:
            self.debug_tools.set_recording(enabled)

    def toggle_frame_recording(self) -> None:
        """Alterna a gravação de frames."""
        if self.debug_tools:
            self.debug_tools.toggle_recording()

    def _on_recording_changed(self, recording: bool) -> None:
        self._refresh_background_mode()
        self._set_action_checked(self._recording_action, recording)
        if self.tray_icon:
            limite = DebugTools.MAX_RECORDING_FRAMES
            message = (
                f"Gravação iniciada (máximo {limite} frames)."
                if recording
                else "Gravação encerrada."
            )
            self.tray_icon.showMessage(
                "Diagnóstico",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                TRAY_NOTIFICACAO_MS,
            )

    def _posicionar_mascote(self, x, y):
        self._mascot_screen = (x, y)
        if self._canvas_origin is not None:
            self._reposicionar_canvas()
            self._atualizar_posicao_local()

    def _atualizar_posicao_local(self):
        x, y = self._mascot_screen
        left, top = self._canvas_origin
        self._physics_local = (x - left, y - top)
        if self._exit_started is None:
            self.renderer.set_model_screen_position(*self._physics_local)
        if self._mouse_screen is not None:
            mx, my = self._mouse_screen
            self._mouse_local = (mx - left, my - top)

    def _origem_canvas(self, width, height):
        left, top, desktop_width, desktop_height = self._desktop_rect
        x, y = self._mascot_screen
        margem = min(self.settings.window.size * 0.42, height * 0.25)
        return (
            min(left + desktop_width - width, max(left, round(x - width / 2))),
            min(top + desktop_height - height, max(top, round(y - height + margem))),
        )

    def _reposicionar_canvas(self, *, forcar=False):
        if not forcar and self._canvas_request is not None:
            return
        width, height = self.renderer.width, self.renderer.height
        alvo = self._origem_canvas(width, height)
        atual = self._canvas_origin
        if alvo == atual:
            return
        if (
            not forcar
            and atual
            and abs(alvo[0] - atual[0]) <= 1
            and abs(alvo[1] - atual[1]) <= 1
        ):
            # Histerese mínima de 1px evita chamadas excessivas sem atraso perceptível.
            return
        try:
            # No deslocamento livre durante saída (forcar=True), omitir SWP_NOREDRAW
            # evita quadros parciais/travados no DWM quando o canvas desliza rápido.
            flags = (
                SWP_NOSIZE
                | SWP_NOZORDER
                | SWP_NOACTIVATE
                | 0x0400
                | (0 if forcar else win32con.SWP_NOREDRAW)
            )
            win32gui.SetWindowPos(
                self.hwnd, 0, *alvo, 0, 0,
                flags,
            )
            self._canvas_origin = alvo
        except win32gui.error as exc:
            if exc.winerror != 1400:
                raise

    def _sincronizar_cursor_teimosia(self) -> None:
        """Oculta/restaura o cursor Win32 durante teimosia (manifesto §1.4).

        Fase 'roubo': oculta o cursor (Mário engole o mouse).
        Fase 'cospe': restaura o cursor (Mário cospe o mouse de volta).
        """
        if not self.animation_controller:
            return
        fase = getattr(self.animation_controller, "_teimosia_fase", None)
        cursor_oculto = getattr(self.animation_controller, "_cursor_oculto", False)

        if fase == "roubo" and not cursor_oculto:
            # Ocultar cursor do Windows
            try:
                win32api.ShowCursor(False)
                self.animation_controller._cursor_oculto = True
            except Exception:
                pass  # Não quebrar a animação se falhar

        elif fase == "cospe" and cursor_oculto:
            # Restaurar cursor do Windows
            try:
                win32api.ShowCursor(True)
                self.animation_controller._cursor_oculto = False
            except Exception:
                pass

        # Segurança: se a teimosia terminou e o cursor ainda está oculto, restaurar
        if self.animation_controller.state.value != "teimosia" and cursor_oculto:
            try:
                win32api.ShowCursor(True)
                self.animation_controller._cursor_oculto = False
            except Exception:
                pass

    def _sincronizar_desktop(self, dt):
        """Atualiza topologia e posiciona a janela."""
        if not win32gui.IsWindow(self.hwnd):
            return
        self._confirmar_canvas()
        self._display_check -= dt
        if self._display_check <= 0:
            self._display_check = 0.5
            self._ler_topologia()
        if self._desktop_rect is not None and self._canvas_request is None:
            # Ajusta tamanho apenas quando necessário (tamanho fixo por degrau)
            # e depois só reposiciona para seguir o mascote.
            self._ajustar_canvas(dt)
            self._reposicionar_canvas()

    def _ler_topologia(self):
        rect = tuple(win32api.GetSystemMetrics(i) for i in (76, 77, 78, 79))
        if min(rect[2:]) <= 0 or rect == self._desktop_rect:
            return
        self._desktop_rect = rect
        x, y = self._mascot_screen
        monitor = win32api.MonitorFromPoint((round(x), round(y)), 2)
        info = win32api.GetMonitorInfo(monitor)
        left, top, right, bottom = info["Monitor"]
        if not (left <= x < right and top <= y < bottom):
            left, top, right, bottom = info["Work"]
            margem = self.settings.physics.mascot_radius
            x = min(right - margem, max(left + margem, x))
            y = min(bottom - margem, max(top + margem, y))
        if self.physics:
            self.physics.set_bounds(info["Work"])
            if (x, y) != self._mascot_screen:
                self.physics.set_position(x, y)
        self._mascot_screen = (x, y)
        self._canvas_measure_in = 0.0
        if self._canvas_origin and self.renderer.width <= rect[2] and self.renderer.height <= rect[3]:
            self._reposicionar_canvas(forcar=True)
            self._atualizar_posicao_local()

    def _confirmar_canvas(self):
        if self._canvas_request is None:
            return
        width, height, origem = self._canvas_request
        if (self.win.getXSize(), self.win.getYSize()) != (width, height):
            return
        if win32gui.ClientToScreen(self.hwnd, (0, 0)) != origem:
            return
        renderer = self.renderer
        units = renderer._view_height / renderer.height
        renderer.width, renderer.height = width, height
        renderer._view_width, renderer._view_height = units * width, units * height
        self.cam.node().getLens().setFilmSize(renderer._view_width, renderer._view_height)
        if renderer._filter_manager is not None:
            renderer._filter_manager.resizeBuffers()
        self._canvas_origin = origem
        self._canvas_request = None
        self._atualizar_posicao_local()

    def _ajustar_canvas(self, dt):
        # Solução radical: tamanho fixo baseado no degrau de envelope.
        # Nunca chama getTightBounds() durante animação — elimina flicker
        # causado por variação de bounds a cada pose.
        palco = self.renderer.music_speaker
        grande = (
            palco.was_dancing
            or palco.visibility > 0.005
            or (
                self._intro_motion is not None
                and self._intro_motion.style == "virtual_insanity_in"
            )
        )
        base = round(self.settings.window.size * max(1.0, self.settings.window.scale))
        # Usa degrau fixo: 2*base para normal, 3*base para dança.
        # O degrau 2*base acomoda qualquer pose do mascote sem cortar.
        if grande:
            width = base * 3
            height = round(base * 2.2)
        elif self._drag_active:
            width = base * 2
            height = base * 2
        else:
            width = base * 2
            height = base * 2
        width = min(width, self._desktop_rect[2])
        height = min(height, self._desktop_rect[3])
        atual = (self.renderer.width, self.renderer.height)
        tamanho = (width, height)
        if tamanho == atual and self._canvas_origin is not None:
            self._canvas_shrink_in = 0.0
            return
        if self._aguardar_encolhimento_canvas(dt, atual, tamanho):
            return
        self._canvas_shrink_in = 0.0
        self._redimensionar_canvas(width, height)

    def _aguardar_encolhimento_canvas(
        self, dt: float, atual: tuple[int, int], novo: tuple[int, int]
    ) -> bool:
        cresce = novo[0] > atual[0] or novo[1] > atual[1]
        corte_desktop = (
            atual[0] > self._desktop_rect[2] or atual[1] > self._desktop_rect[3]
        )
        if self._canvas_origin is None or cresce or corte_desktop:
            self._canvas_shrink_in = 0.0
            return False
        if self._canvas_shrink_in <= 0.0:
            self._canvas_shrink_in = 0.6
            return True
        self._canvas_shrink_in -= dt
        return self._canvas_shrink_in > 0.0

    def _redimensionar_canvas(self, width, height):
        origem = self._origem_canvas(width, height)
        self._canvas_request = (width, height, origem)
        if self._canvas_origin is None:
            properties = WindowProperties()
            properties.setOrigin(*origem)
            properties.setSize(width, height)
            self.win.requestProperties(properties)
            return
        # Resize sem SWP_NOREDRAW: o DWM compósita corretamente sem flicker.
        # SWP_NOSENDCHANGENOTIFY (0x0400) impede WM_WINDOWPOSCHANGING/CHANGED extras.
        win32gui.SetWindowPos(
            self.hwnd, 0, *origem, width, height,
            SWP_NOZORDER | SWP_NOACTIVATE | 0x0400,
        )
        self._confirmar_canvas()
        if self._canvas_request is None:
            # O primeiro quadro prepara os buffers WGL redimensionados.
            self.graphicsEngine.renderFrame()

    def _tamanho_canvas(self, base, palco):
        if palco:
            return base * 3, round(base * 2.2)
        if self._drag_active:
            return base * 2, base * 2
        if self._canvas_origin is None:
            return base, base
        limites = self.renderer.model_np.getTightBounds(self.cam)
        if not limites:
            return base, base
        low, high = limites
        anchor = self.renderer.model_anchor.getPos(self.cam)
        units = self.renderer._view_height / self.renderer.height
        largura = 2 * max(abs(low.x - anchor.x), abs(high.x - anchor.x)) / units
        altura = max((high.z - anchor.z) / 0.72, (anchor.z - low.z) / 0.24) / units
        # Histerese generosa: animações como "cair" esticam o personagem muito
        # além da pose normal. 10% ou 40px evita que variações de pose causem
        # resize constante da janela (principal causa de flicker).
        atual_w = self.renderer.width
        atual_h = self.renderer.height
        raw_lado = degrau_para(max(largura, altura) - MARGEM_ANTICORTE / 2, base)
        diff = abs(raw_lado - atual_w)
        if diff < max(atual_w * 0.10, 40):
            return atual_w, atual_h
        return raw_lado, raw_lado

    def _montar_menus_previas_bandeja(self) -> None:
        dance_preview = self.tray_menu.addMenu("Prévia de dança (sem som)")
        for style, label in (
            ("head_bob", "Head bob"),
            ("hip_hop", "Hip hop"),
            ("rock", "Rock"),
            ("breakdance", "Breakdance"),
        ):
            dance_preview.addAction(label).triggered.connect(
                lambda _checked=False, style=style: (
                    self.animation_controller.preview_dance(style)  # type: ignore[union-attr]
                )
            )
        intro_preview = self.tray_menu.addMenu("Prévia de aberturas")
        for style, label in (
            ("fade_in", "Fade in (dissolver)"),
            ("virtual_insanity_in", "Virtual Insanity (deslizando)"),
            ("run_from_depth", "Correndo do fundo"),
            ("kagebunshin_in", "Entrada ninja (Kage Bunshin)"),
        ):
            intro_preview.addAction(label).triggered.connect(
                lambda _checked=False, style=style: self.start_intro(style)
            )
        exit_preview = self.tray_menu.addMenu("Prévia de encerramentos")
        for style, label in (
            ("classic", "Clássica (arremesso)"),
            ("sonic_classic", "Sonic Classic (morte)"),
            ("fnf_blue_balls", "FNF Blue Balls"),
            ("lego_disassemble", "Desmontar LEGO"),
            ("thanos_snap", "Desintegrar (Thanos)"),
            ("peace_fade_out", "Fade out Peace Sign"),
            ("virtual_insanity_out", "Virtual Insanity (deslizando)"),
        ):
            exit_preview.addAction(label).triggered.connect(
                lambda _checked=False, style=style: self.preview_exit(style)
            )

    def _setup_tray(self) -> None:  # noqa: PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        """Cria o ícone e o menu da bandeja do sistema."""
        icon_path = brand_dir() / "companion.ico"
        icon = QIcon(str(icon_path))
        if icon.isNull():
            icon = QIcon(str(icon_path.with_suffix(".png")))
        self.tray_icon = QSystemTrayIcon(icon, self.qt_app)
        self.tray_icon.setToolTip("SeJoga Desktop Companion")

        self.tray_menu = QMenu()
        toggle_action = self.tray_menu.addAction("Mostrar / ocultar")
        toggle_action.triggered.connect(lambda _checked=False: self.toggle_visibility())

        self.tray_menu.addSeparator()
        self._montar_menus_previas_bandeja()

        self._topmost_action = self.tray_menu.addAction("Sempre no topo")
        self._topmost_action.setCheckable(True)
        self._topmost_action.setChecked(self._is_topmost)
        self._topmost_action.toggled.connect(self.set_topmost)

        settings_action = self.tray_menu.addAction("Configurações...")
        settings_action.triggered.connect(
            lambda _checked=False: self.open_settings_dialog()
        )

        from sejoga.distribuicao.dialogo_atualizacao import UpdateDialog

        # Fluxo fecha->barra->reabre: ao confirmar a atualização, o launcher nativo
        # assume (download/verificação/instalação com barra de progresso própria) e
        # pede elevação. O companion fecha aqui para não ficar renderizando atrás da
        # barra (o "bloco preto"); o launcher reabre o mascote ao terminar, inclusive
        # se o usuário cancelar o UAC.
        # O canal da config (não o release-info.json) decide qual feed consultar.
        self._update_dialog = UpdateDialog(self._ao_iniciar_atualizacao, self.settings)
        canal = self.settings.update.channel
        if self._update_dialog.current:
            current = self._update_dialog.current
            self.tray_icon.setToolTip(f"SeJoga Companion · {canal} · {current.version}")
        else:
            self.tray_icon.setToolTip(f"SeJoga Companion · canal {canal}")
        # Item único na bandeja: busca e pergunta se o usuário quer atualizar.
        self._update_action = self.tray_menu.addAction("Buscar atualizações...")
        self._update_action.setToolTip(f"Canal de atualização: {canal}")
        self._update_action.triggered.connect(
            lambda _checked=False: self._update_dialog.show()
        )

        debug_shortcut = self.settings.hotkeys.toggle_debug.upper()
        self._debug_action = self.tray_menu.addAction(f"Diagnóstico ({debug_shortcut})")
        self._debug_action.setCheckable(True)
        self._debug_action.toggled.connect(self.set_debug_overlay)
        capture_action = self.tray_menu.addAction("Capturar frame (Ctrl+Alt+P)")
        capture_action.triggered.connect(
            lambda _checked=False: self.capture_debug_frame()
        )
        self._recording_action = self.tray_menu.addAction("Gravar frames (Ctrl+Alt+R)")
        self._recording_action.setCheckable(True)
        self._recording_action.toggled.connect(self.set_frame_recording)

        self.tray_menu.addSeparator()
        personality_menu = self.tray_menu.addMenu("Personalidade do idle")
        personality_group = QActionGroup(personality_menu)
        personality_group.setExclusive(True)
        self._personality_actions = {}
        for value, label in (
            ("auto", "Padrão"),
            ("calm", "Tranquila"),
            ("curious", "Curiosa"),
            ("playful", "Brincalhona"),
            ("shy", "Tímida"),
            ("confident", "Confiante"),
            ("street", "Street groove · Bomb Rush"),
            ("fighter", "Guarda e provocação · Lethal League"),
            ("rhythm", "Ritmada · Hi-Fi Rush"),
            ("stylish", "Estilosa · Persona 5"),
        ):
            action = personality_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.settings.behavior.idle_personality == value)
            personality_group.addAction(action)
            action.triggered.connect(
                lambda _checked=False, personality=value: self._set_idle_personality(
                    personality
                )
            )
            self._personality_actions[value] = action

        dormir_menu = self.tray_menu.addMenu("Dormir")
        dormir_menu.addAction("Dormir em pé").triggered.connect(
            lambda: self.animation_controller.colocar_para_dormir("em_pe")
            if self.animation_controller
            else None
        )
        dormir_menu.addAction("Dormir sentado").triggered.connect(
            lambda: self.animation_controller.colocar_para_dormir("sentado")
            if self.animation_controller
            else None
        )
        dormir_menu.addAction("Dormir deitado").triggered.connect(
            lambda: self.animation_controller.colocar_para_dormir("deitado")
            if self.animation_controller
            else None
        )
        dormir_menu.addSeparator()
        dormir_menu.addAction("Acordar").triggered.connect(
            lambda: self.animation_controller.acordar()
            if self.animation_controller
            else None
        )

        for label, kind in (
            ("Acenar", "wave"),
            ("Abrir as mãos", "open_hands"),
            ("Fechar os punhos", "close_fists"),
            ("Soltar os ombros", "stretch"),
            ("Mostrar tentáculos", "peek"),
            ("Espirro de tentáculos", "sneeze"),
        ):
            action = self.tray_menu.addAction(label)
            # callback só dispara após o init: animation_controller já definido
            action.triggered.connect(
                lambda _checked=False, kind=kind: self.animation_controller.interact(  # type: ignore[union-attr]
                    kind
                )
            )

        self.tray_menu.addSeparator()
        olhar_tela_action = self.tray_menu.addAction("Olhar a tela")
        olhar_tela_action.triggered.connect(
            lambda _checked=False: (
                self.animation_controller.iniciar_pacote_olhar_tela()  # type: ignore[union-attr]
            )
        )

        profundidade_menu = self.tray_menu.addMenu("Profundidade")
        for nivel_valor, nivel_rotulo in (
            ("perto", "Perto"),
            ("medio", "Médio"),
            ("longe", "Longe"),
        ):
            profundidade_menu.addAction(nivel_rotulo).triggered.connect(
                lambda _checked=False, n=nivel_valor: (
                    self.animation_controller.definir_profundidade(n)  # type: ignore[union-attr]
                )
            )
        profundidade_menu.addSeparator()
        profundidade_menu.addAction("Caminhar para o fundo").triggered.connect(
            lambda _checked=False: (
                self.animation_controller.caminhar_para_fundo()  # type: ignore[union-attr]
            )
        )
        profundidade_menu.addAction("Caminhar para a frente").triggered.connect(
            lambda _checked=False: (
                self.animation_controller.caminhar_para_frente()  # type: ignore[union-attr]
            )
        )

        orientacao_menu = self.tray_menu.addMenu("Orientação")
        for ori_valor, ori_rotulo in (
            ("frente", "Frente"),
            ("perfil", "Perfil"),
            ("costas", "Costas"),
        ):
            orientacao_menu.addAction(ori_rotulo).triggered.connect(
                lambda _checked=False, o=ori_valor: (
                    self.animation_controller.definir_orientacao(o)  # type: ignore[union-attr]
                )
            )

        self.tray_menu.addAction("Caminhar até o mouse").triggered.connect(
            lambda _checked=False: self.caminhar_ate_mouse()
        )
        self.tray_menu.addAction("Caminhar para destino aleatório").triggered.connect(
            lambda _checked=False: self.caminhar_destino_aleatorio()
        )
        self.tray_menu.addAction("Voltar ao plano (frente)").triggered.connect(
            lambda _checked=False: self._voltar_ao_plano_frontal()
        )
        self.tray_menu.addSeparator()
        quit_action = self.tray_menu.addAction("Encerrar Mário")
        quit_action.triggered.connect(lambda _checked=False: self.quit_app())

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.setVisible(True)
        self.tray_icon.show()
        self.tray_registration = TrayRegistration(icon_path)
        self.taskMgr.doMethodLater(
            0.75, self._ensure_tray_registration, "tray-registration"
        )
        QApplication.processEvents()
        if icon.isNull() or not self.tray_icon.isVisible():
            self.logger.warning(
                "System tray icon did not become visible (icon=%s, tray_available=%s)",
                icon_path,
                QSystemTrayIcon.isSystemTrayAvailable(),
            )

    def _ensure_tray_registration(self, task):
        if self._exit_started is not None:
            return Task.done
        status = self.tray_registration.ensure()
        if not status["registered"]:
            self.logger.warning("Tray icon has no Shell registration: %s", status)
        task.delayTime = 60.0 if status["registered"] else 3.0
        return Task.again

    def _set_idle_personality(self, personality: str) -> None:
        """Aplica e salva a personalidade sem interromper o gesto atual."""
        if personality != "auto" and personality not in {
            p.value for p in IdlePersonality
        }:
            return
        # Validado acima: personality e um dos literais aceitos pelo settings.
        self.settings.behavior.idle_personality = cast(Any, personality)
        if self.animation_controller:
            self.animation_controller.set_idle_personality(personality)
        self._persist_settings()

    def _voltar_ao_plano_frontal(self) -> None:
        """Interrompe caminhadas/pacotes e retorna a `perto` e `frente` (§8.5.2)."""
        self._destino_caminhada_x = None
        if self.animation_controller:
            self.animation_controller.voltar_ao_plano()

    def caminhar_ate_mouse(self) -> None:
        """Define a posição X atual do cursor como destino de caminhada (§8.5.2)."""
        if self._mouse_screen is not None:
            self._destino_caminhada_x = float(self._mouse_screen[0])
            return
        with contextlib.suppress(Exception):
            self._destino_caminhada_x = float(win32gui.GetCursorPos()[0])

    def caminhar_destino_aleatorio(self) -> None:
        """Escolhe um destino horizontal aleatório na área útil do monitor atual."""
        import random as _rnd

        left, _top, right, _bottom = self._retangulo_monitor_preferido()
        margem = max(80, self.settings.window.size // 2)
        if right - left > 2 * margem:
            self._destino_caminhada_x = float(
                _rnd.uniform(left + margem, right - margem)
            )

    def _velocidade_caminhada_teimosia(self, ctrl, state) -> float | None:
        if (
            ctrl is None
            or ctrl.state is None
            or ctrl.state.value != "teimosia"
            or getattr(ctrl, "_teimosia_fase", None) != "roubo"
        ):
            return None
        meta = ctrl.agencia.meta_ativa
        alvo_x = (
            meta.alvo_x
            if meta is not None
            else (self.physics.bounds[0] + self.physics.bounds[2]) * 0.5
        )
        dx = alvo_x - state.position[0]
        return (240.0 if dx > 0 else -240.0) if abs(dx) > 12.0 else 0.0

    def _atualizar_caminhada_horizontal(self, state: Any) -> None:
        """Conduz a caminhada horizontal (manual, agência autônoma ou roubo do mouse)."""
        if not self.physics:
            return
        self.physics.walk_velocity_x = None
        if self._drag_active:
            self._destino_caminhada_x = None
        if state is None or not state.grounded:
            return

        ctrl = self.animation_controller
        roubo_vel = self._velocidade_caminhada_teimosia(ctrl, state)
        if roubo_vel is not None:
            self.physics.walk_velocity_x = roubo_vel or None
            return

        if self._destino_caminhada_x is not None:
            dx = self._destino_caminhada_x - state.position[0]
            if abs(dx) <= 4.0:
                self._destino_caminhada_x = None
                return
            self.physics.walk_velocity_x = max(-180.0, min(180.0, dx * 6.0))
            return

        # Caminhada autônoma pela Agência (vontade própria do Mário)
        meta = ctrl.agencia.meta_ativa if (ctrl is not None and ctrl.agencia.tem_meta_ativa) else None
        if (
            meta is not None
            and ctrl.state is not None
            and ctrl.state.value in ("idle", "walk")
            and not self._mouse_hovered
            and meta.tipo.value in (2, 3, 4)
        ):
            dx = meta.alvo_x - state.position[0]
            if abs(dx) <= 8.0:
                ctrl.agencia.registrar_meta_alcançada()
                return
            self.physics.walk_velocity_x = max(-150.0, min(150.0, dx * 4.5))

    def _setup_timers(self) -> None:
        """Agenda a animação e bombeia os eventos do Qt junto ao loop Panda3D."""
        from panda3d.core import ClockObject

        clock = ClockObject.getGlobalClock()
        clock.setMode(ClockObject.MLimited)
        clock.setFrameRate(self.settings.window.fps)
        self.taskMgr.add(self._process_qt_events, "qt-event-pump", sort=40)
        self.taskMgr.add(self._animate_frame, "animation-frame", sort=45)

    def _animate_frame(self, task):
        self._animation_tick()
        return Task.cont

    def _process_qt_events(self, task: Task) -> int:
        QApplication.processEvents()
        if self.desktop:
            for request in self.desktop.requests[:]:
                self.desktop.requests.remove(request)
                if request == "quit":
                    self.quit_app()
                elif request == "settings" and self._exit_started is None:
                    self.open_settings_dialog()
                elif (
                    request == "peek"
                    and self._exit_started is None
                    and self.animation_controller
                ):
                    self.animation_controller.interact("peek")
                elif (
                    request.startswith("dance:")
                    and self._exit_started is None
                    and self.animation_controller
                ):
                    self.animation_controller.preview_dance(request.split(":", 1)[1])
                elif request == "capture" and self.debug_tools:
                    self.debug_tools.capture_once()
        return Task.cont

    def _on_tray_activated(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()

    def _setup_mouse_hooks(self) -> None:
        for event, button in (
            ("mouse1", "left"),
            ("mouse2", "middle"),
            ("mouse3", "right"),
        ):
            self.accept(event, self._native_mouse_button, [button, True])
            self.accept(event + "-up", self._native_mouse_button, [button, False])
        self.taskMgr.add(self._mouse_poll, "mouse-poll")

    def _native_mouse_button(self, button: str, pressed: bool) -> None:
        if self._exit_started is not None:
            return
        if pressed:
            self._native_buttons.add(button)
            if win32gui.IsWindow(self.hwnd) and self._settings_dialog is None:
                win32gui.SetCapture(self.hwnd)
        else:
            self._native_buttons.discard(button)
            if not self._native_buttons and win32gui.GetCapture() == self.hwnd:
                win32gui.ReleaseCapture()
        self.logger.info("Native mouse %s %s", button, "down" if pressed else "up")

    def _mouse_buttons(self) -> frozenset[str]:
        return frozenset(self._native_buttons) | frozenset(
            name
            for name, key in (
                ("left", win32con.VK_LBUTTON),
                ("right", win32con.VK_RBUTTON),
                ("middle", win32con.VK_MBUTTON),
            )
            if win32api.GetAsyncKeyState(key) & 0x8000
        )

    def _mouse_poll(self, task: Task) -> int:  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        if not win32gui.IsWindow(self.hwnd):
            return Task.done
        try:
            position = win32gui.GetCursorPos()
        except win32gui.error as exc:
            if exc.winerror == 5:
                # The input desktop is unavailable while Windows is locked or
                # showing a secure desktop. Resume polling when it returns.
                return Task.cont
            raise
        self._mouse_screen = position
        buttons = self._mouse_buttons()
        self._mouse_local = win32gui.ScreenToClient(self.hwnd, position)
        enabled = (
            bool(win32gui.IsWindowVisible(self.hwnd)) and self._settings_dialog is None
        )
        enabled = enabled and not bool(
            win32api.GetAsyncKeyState(win32con.VK_ESCAPE) & 0x8000
        )
        # Com o mascote oculto/desabilitado, hit e hover são sempre falsos:
        # pula o hit_test (traversal de colisão), a varredura de ~43 teclas e as
        # chamadas Win32 de hover, que não alterariam o resultado.
        hit = enabled and self.renderer.hit_test(*self._mouse_local)
        newly_pressed = buttons - self.mouse_interaction.buttons
        if newly_pressed:
            self.logger.info(
                "Mouse press buttons=%s hit=%s target=%s own=%s",
                sorted(newly_pressed),
                hit,
                win32gui.WindowFromPoint(position),
                self.hwnd,
            )
        if hit and not self._drag_active:
            target = win32gui.WindowFromPoint(position)
            hit = target == self.hwnd or win32gui.IsChild(self.hwnd, target)
        if hit and "left" in newly_pressed:
            self._body_grab_point = Vec3(self.renderer._pick_point_model)
            self._body_grab_part = getattr(self.renderer, "_pick_part", "body")
        events = self.mouse_interaction.update(
            position,
            buttons,
            hit=hit,
            enabled=enabled,
            allow_drag=self.settings.behavior.react_to_drag,
            allow_click=self.settings.behavior.react_to_click,
        )
        previous_hover = self._mouse_hovered
        if not enabled:
            # Hover forçado a falso; mantém o foreground sincronizado para a
            # próxima reavaliação quando o mascote voltar a ficar interativo.
            self._hover_foreground = win32gui.GetForegroundWindow()
            self._mouse_hovered = False
        else:
            size = self.settings.window.size
            dx = (position[0] - self._mascot_screen[0]) / (size * 0.95)
            dy = (position[1] - self._mascot_screen[1] + size * 0.25) / (size * 0.85)
            in_hover_zone = dx * dx + dy * dy <= 1.2
            tick = getattr(self, "_hover_poll_tick", 0)
            self._hover_poll_tick = tick + 1
            foreground = win32gui.GetForegroundWindow()
            focus_changed = foreground != self._hover_foreground
            self._hover_foreground = foreground
            if in_hover_zone or focus_changed or tick % 4 == 0:
                typing = foreground != self.hwnd and any(
                    win32api.GetAsyncKeyState(key) & 0x8000
                    for key in (
                        *range(0x30, 0x5B),
                        win32con.VK_SPACE,
                        win32con.VK_BACK,
                        win32con.VK_RETURN,
                    )
                )
                target = win32gui.WindowFromPoint(position)
                target_class = win32gui.GetClassName(target) if target else ""
                busy_cursor = target != self.hwnd and (
                    win32gui.GetCursorInfo()[1] in self._busy_cursors
                    or target_class
                    in (
                        "#32768",
                        "Button",
                        "Edit",
                        "ComboBox",
                        "ListBox",
                        "SysTreeView32",
                        "SysListView32",
                        "ToolbarWindow32",
                    )
                    or "Popup" in target_class
                )
                self._cached_typing = bool(typing)
                self._cached_busy_cursor = busy_cursor
            else:
                typing = getattr(self, "_cached_typing", False)
                busy_cursor = getattr(self, "_cached_busy_cursor", False)
            allowed = self._hover_attention.update(
                time.perf_counter(),
                external_press=bool(buttons)
                and not self.mouse_interaction.has_press
                and not self._drag_active,
                typing=bool(typing),
                busy_cursor=busy_cursor,
                focus_changed=focus_changed,
            )
            self._mouse_hovered = (
                allowed and not self._drag_active and dx * dx + dy * dy <= 1
            )
        if self._mouse_hovered and not previous_hover and self.animation_controller:
            self.animation_controller.interact("hover_enter")
        for event in events:
            if event.kind in ("hover_enter", "click", "double_click", "pet", "poke"):
                if (
                    self.settings.behavior.react_to_click
                    and self.animation_controller
                    and (event.kind != "hover_enter" or self._mouse_hovered)
                ):
                    self.animation_controller.interact(event.kind)
            elif event.kind == "drag_start":
                self._drag_active = True
                self._drag_start_pos = self.mouse_interaction.press_position or position
                self._window_start_pos = self._mascot_screen
                if self.physics:
                    self.physics.start_drag(*self._drag_start_pos)
                if self.animation_controller:
                    self.animation_controller.interact("drag_start")
            elif event.kind in ("drag_move", "drag_end"):
                dx = position[0] - self._drag_start_pos[0]
                dy = position[1] - self._drag_start_pos[1]
                self._drag_direction = max(-1.0, min(1.0, dx / DRAG_DIVISOR_DIRECAO))
                self._drag_intensity = min(
                    1.0, math.hypot(dx, dy) / DRAG_DIVISOR_INTENSIDADE
                )
                self._posicionar_mascote(
                    self._window_start_pos[0] + dx, self._window_start_pos[1] + dy
                )
                if self.physics:
                    self.physics.update_drag(*position)
            if event.kind in ("drag_end", "drag_cancel"):
                if self.physics:
                    self._set_physics_monitor(self.physics.get_state().position)
                    self.physics.end_drag(cancel=event.kind == "drag_cancel")
                self._drag_active = False
                self._drag_direction = 0.0
                self._drag_intensity = 0.0
                self.settings.window.start_position = tuple(
                    round(valor - offset)
                    for valor, offset in zip(self._mascot_screen, self._offset_mascote, strict=True)
                )
                self._persist_settings()
            if event.kind != "drag_move":
                self.logger.info("Mouse %s at %s", event.kind, position)
        return Task.cont

    def toggle_visibility(self) -> None:
        """Mostra ou esconde o mascote."""
        if win32gui.IsWindowVisible(self.hwnd):
            win32gui.ShowWindow(self.hwnd, 0)
        else:
            win32gui.ShowWindow(self.hwnd, 5)

    def summon_overlay(self) -> None:
        """Mostra o mascote e o traz para frente sem alterar sua posição salva."""
        self._is_bottom = False
        self._is_topmost = True
        self.settings.window.mode = "overlay"
        self.settings.window.always_on_top = True
        self._update_z_order()
        self._set_action_checked(self._topmost_action, True)
        win32gui.ShowWindow(self.hwnd, 5)
        self._persist_settings()

    def set_topmost(self, checked: bool) -> None:
        """Mantém a janela acima das outras."""
        self._is_topmost = checked
        self._is_bottom = False
        self._update_z_order()
        self.settings.window.always_on_top = checked
        self.settings.window.mode = "overlay"
        self._persist_settings()

    def set_bottom(self, checked: bool) -> None:
        """Mantém a janela abaixo das outras."""
        self._is_bottom = checked
        self._is_topmost = False
        self._update_z_order()
        self.settings.window.mode = "desktop" if checked else "overlay"
        self._persist_settings()

    def open_settings_dialog(self) -> None:
        """Abre o diálogo de configurações."""
        if self._settings_dialog is not None:
            self._settings_dialog.show()
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return

        dialog = SettingsDialog(self.settings)
        dialog.settings_applied.connect(self._apply_settings)
        dialog.atualizacao_iniciada.connect(self._ao_iniciar_atualizacao)
        dialog.finished.connect(lambda _result: setattr(self, "_settings_dialog", None))
        self._settings_dialog = dialog
        dialog.show()

    def _apply_settings(self, updated: Settings) -> None:  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        previous = self.settings
        updated.window.start_position = previous.window.start_position
        restart_required = (
            previous.window.size != updated.window.size
            or previous.window.preferred_monitor != updated.window.preferred_monitor
            or previous.physics != updated.physics
        )
        music_changed = previous.music != updated.music
        hotkeys_changed = previous.hotkeys != updated.hotkeys

        channel_changed = previous.update.channel != updated.update.channel

        self.settings = updated
        self.settings_obj = updated
        self._is_bottom = updated.window.mode == "desktop"
        self._is_topmost = updated.window.always_on_top and not self._is_bottom
        self._update_z_order()
        if channel_changed:
            # Mantém o diálogo da bandeja e o tooltip coerentes com o novo canal.
            self._update_dialog.atualizar_config(updated)
            canal = updated.update.channel
            self._update_action.setToolTip(f"Canal de atualização: {canal}")
            if self._update_dialog.current:
                self.tray_icon.setToolTip(
                    f"SeJoga Companion · {canal} · {self._update_dialog.current.version}"
                )
            else:
                self.tray_icon.setToolTip(f"SeJoga Companion · canal {canal}")
        self._set_action_checked(self._topmost_action, self._is_topmost)
        if hotkeys_changed:
            if self.hotkey_manager:
                self.hotkey_manager.close()
            self.hotkey_manager = HotkeyManager(
                updated.hotkeys.model_dump(), self._hotkey_callbacks
            )
            unavailable = self.hotkey_manager.unavailable_shortcuts
            if unavailable:
                self.logger.warning(
                    "Unavailable global shortcuts after settings update: %s",
                    ", ".join(unavailable),
                )
                if self.tray_icon:
                    self.tray_icon.showMessage(
                        "Atalho indisponível",
                        "Já está sendo usado por outro programa: "
                        + ", ".join(unavailable),
                        QSystemTrayIcon.MessageIcon.Warning,
                        TRAY_NOTIFICACAO_ATALHO_MS,
                    )
        # FPS ao vivo: ajusta a taxa do clock global do Panda3D sem reiniciar.
        from panda3d.core import ClockObject

        ClockObject.getGlobalClock().setFrameRate(updated.window.fps)
        # Nível de log ao vivo (reconfigura o logger "sejoga").
        configure_logging(updated.logging.level)
        # Color key de diagnóstico: reusa o caminho de fundo existente.
        self._refresh_background_mode()
        if self.renderer:
            self.renderer.set_visual_scale(updated.window.scale)
            if previous.window.scale != updated.window.scale:
                self._display_check = 0
                self._sincronizar_desktop(0)
            self.renderer.set_outline_settings(updated.window)
        if self.animation_controller:
            self.animation_controller.set_idle_personality(
                updated.behavior.idle_personality
            )
        for value, action in self._personality_actions.items():
            self._set_action_checked(action, value == updated.behavior.idle_personality)

        if music_changed:
            if self.music_listener:
                self.music_listener.stop()
            self.music_listener = MusicListener(updated.music)
            self.music_listener.start()

        if restart_required and self.tray_icon:
            self.tray_icon.showMessage(
                "Configurações salvas",
                "Tamanho da janela e física serão aplicados ao reiniciar o companion.",
                QSystemTrayIcon.MessageIcon.Information,
                TRAY_NOTIFICACAO_REINICIO_MS,
            )

    @staticmethod
    def _set_action_checked(action, checked: bool) -> None:
        if action is None:
            return
        previous = action.blockSignals(True)
        action.setChecked(checked)
        action.blockSignals(previous)

    def _persist_settings(self) -> None:
        try:
            save_settings(self.settings)
        except OSError as exc:
            self.logger.error("Falha ao salvar configuração: %s", exc)

    def _ao_iniciar_atualizacao(self) -> None:
        """Fecha o companion quando a atualização inicia.

        O launcher nativo mostra só a barra de progresso e reabre o mascote ao
        terminar (ou se o usuário cancelar o UAC). Fechar aqui evita o mascote
        renderizando atrás da barra (o "bloco preto" relatado pelo usuário).
        """
        self.logger.info(
            "Atualização iniciada; fechando o companion para o launcher assumir."
        )
        self.quit_app()

    def quit_app(self) -> None:
        """Encerra o app."""
        self.userExit()

    def userExit(self) -> None:
        """Encerra o app pelo fluxo de saída do Panda3D."""
        if not self._force_exit and self.renderer and win32gui.IsWindow(self.hwnd):
            if self._exit_started is None:
                self._begin_exit()
            return
        self._finish_exit()

    def start_intro(self, style: str | None = None) -> None:
        """Inicia ou pré-visualiza uma animação de abertura no overlay atual."""
        if not self.renderer or self._exit_started is not None:
            return
        chosen = style or self.settings.window.intro_animation
        if chosen == "padrao":
            return
        self.renderer.restore_intro_effect()
        side = -1 if self._mascot_screen[0] > self._desktop_rect[0] + self._desktop_rect[2] * 0.5 else 1
        self._intro_motion = IntroAnimation(chosen, from_side=side)
        self._intro_started = time.perf_counter()
        self._intro_last_loco = None

    def preview_exit(self, style: str) -> None:
        """Reproduz prévia segura de encerramento/morte e restaura o mascote."""
        if not self.renderer or self._exit_started is not None:
            return
        self._begin_exit(style=style, preview=True)

    def _preparar_saida_definitiva(self) -> None:
        self._persist_settings()
        self.taskMgr.remove("physics-tick")
        self.taskMgr.remove("mouse-poll")
        self._native_buttons.clear()
        if win32gui.GetCapture() == self.hwnd:
            win32gui.ReleaseCapture()
        if self._settings_dialog:
            self._settings_dialog.reject()

    def _normalizar_pose_para_saida(self) -> None:
        self._intro_motion = None
        self._intro_started = None
        self._intro_last_loco = None
        self._canvas_request = None
        self._last_model_pos = None
        self._last_tilt_z = None
        if self.renderer:
            self.renderer.restore_intro_effect()
            self.renderer.set_model_rotation()
            self.renderer.set_model_screen_position(*self._physics_local)
        ctrl = self.animation_controller
        if ctrl is None:
            return
        ctrl.acordar()
        ctrl._reaction = None
        ctrl.definir_orientacao("frente")
        pose = ctrl.update(1 / 60, velocity=(0.0, 0.0), grounded=True, gravity_active=False)
        if self.renderer:
            self.renderer.apply_rig_pose(pose)
            self.renderer.lower_body.apply(ctrl.leg_motion.pose, True, dt=1 / 60)
            self.renderer.sync_exit_ground_offset(True)

    def _begin_exit(self, style: str | None = None, *, preview: bool = False):
        self._exit_preview = preview
        self._exit_style = style or self.settings.window.exit_animation
        self._exit_started = time.perf_counter()
        self._exit_last_tick = self._exit_started
        self._normalizar_pose_para_saida()
        if not preview:
            self._preparar_saida_definitiva()
        if win32gui.IsWindow(self.hwnd):
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)
            win32gui.SetWindowPos(
                self.hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
        bounds = (
            win32api.GetSystemMetrics(76),
            win32api.GetSystemMetrics(77),
            win32api.GetSystemMetrics(76) + win32api.GetSystemMetrics(78),
            win32api.GetSystemMetrics(77) + win32api.GetSystemMetrics(79),
        )
        self._exit_origin = tuple(
            round(v - o)
            for v, o in zip(self._mascot_screen, self._offset_mascote, strict=True)
        )
        self._exit_saved_mascot = self._mascot_screen
        self._exit_saved_canvas = self._canvas_origin
        self._exit_motion = ExitAnimation(
            self._exit_origin,
            self.settings.window.size,
            bounds,
            style=self._exit_style,
        )
        self._exit_style = self._exit_motion.style
        self.renderer.begin_exit_effect(self._exit_style)
        now = time.perf_counter()
        self._exit_started = now
        self._exit_last_tick = now
        self.logger.info(
            "Exit animation started (%s, preview=%s)", self._exit_style, preview
        )

    def _mover_canvas_saida(self, dx: int, dy: int) -> tuple[int, int]:
        saved_mascot = getattr(self, "_exit_saved_mascot", None)
        saved_canvas = getattr(self, "_exit_saved_canvas", None)
        if (
            saved_mascot is None
            or saved_canvas is None
            or self._desktop_rect is None
            or (dx == 0 and dy == 0)
        ):
            return 0, 0
        self._mascot_screen = (saved_mascot[0] + dx, saved_mascot[1] + dy)
        self._reposicionar_canvas(forcar=True)
        return (
            self._canvas_origin[0] - saved_canvas[0],
            self._canvas_origin[1] - saved_canvas[1],
        )

    def _encerrar_quadro_saida(self) -> None:
        if self._exit_preview:
            self._end_exit_preview()
        else:
            self._force_exit = True
            self._finish_exit()

    def _exit_tick(self):
        if not win32gui.IsWindow(self.hwnd):
            self._encerrar_quadro_saida()
            return
        now = time.perf_counter()
        dt = max(1.0 / 240.0, min(0.05, now - self._exit_last_tick))
        self._exit_last_tick = now
        frame = self._exit_motion.sample(now - self._exit_started)
        renderer = self.renderer
        if (
            self._exit_style != "classic"
            and frame.explode <= 0.0
            and self.animation_controller is not None
        ):
            self._atualizar_pose_durante_saida(dt, frame)
        dx = frame.x - self._exit_origin[0]
        dy = frame.y - self._exit_origin[1]
        cdx, cdy = self._mover_canvas_saida(dx, dy)
        if self._exit_style == "classic":
            renderer.set_exit_rotation(frame.roll)
            units = renderer._view_height / renderer.height
            renderer.exit_pivot.setX(renderer._exit_center.x + (dx - cdx) * units)
            renderer.exit_pivot.setZ(renderer._exit_center.z - (dy - cdy) * units)
        else:
            renderer.update_exit_effect(
                frame,
                (self._exit_origin[0] + cdx, self._exit_origin[1] + cdy),
                self._exit_style,
            )
        if self.debug_tools:
            self.debug_tools.update(1 / self.settings.window.fps)
        if frame.done:
            self._encerrar_quadro_saida()

    def _atualizar_pose_durante_saida(self, dt: float, frame) -> None:
        ctrl = self.animation_controller
        if ctrl is None or self.renderer._lego_snapshot:
            return
        ctrl.definir_orientacao("frente")
        loco = frame.locomotion
        if loco in ("hit", "peace", "open_hands", "blue_balls", "virtual_insanity"):
            if ctrl._reaction is None or ctrl._reaction.value != loco:
                ctrl._cooldowns.pop(loco, None)
                direction = (
                    float(self._exit_motion.direction)
                    if loco == "virtual_insanity"
                    else None
                )
                ctrl.interact(loco, direction=direction, strength=1.1)
        elif loco == "sleep" and ctrl.state != AnimationState.SLEEP:
            ctrl.colocar_para_dormir("deitado")
        vel = (0.0, 480.0) if loco == "fall" else (0.0, 0.0)
        pose = ctrl.update(
            dt,
            velocity=vel,
            grounded=loco != "fall",
            gravity_active=loco == "fall",
            music_playing=loco == "dance",
            music_intensity=0.7 if loco == "dance" else 0.0,
        )
        self.renderer.apply_rig_pose(pose)
        self.renderer.lower_body.apply(ctrl.leg_motion.pose, loco != "fall", dt=dt)
        self.renderer.sync_exit_ground_offset(loco != "fall")
        self.renderer.update_appendages(dt, False)

    def _end_exit_preview(self) -> None:
        self._exit_started = None
        self._exit_preview = False
        self._exit_style = "classic"
        if self.renderer is not None:
            self.renderer.restore_exit_effect()
        if self.animation_controller is not None:
            self.animation_controller.acordar()
            self.animation_controller.definir_orientacao(None)
            self.animation_controller._reaction = None
        saved_mascot = getattr(self, "_exit_saved_mascot", None)
        if saved_mascot is not None:
            self._mascot_screen = saved_mascot
            self._exit_saved_mascot = None
            self._exit_saved_canvas = None
            if getattr(self, "_desktop_rect", None) is not None:
                self._reposicionar_canvas(forcar=True)
                self._atualizar_posicao_local()

    def _finish_exit(self):
        self.taskMgr.remove("physics-tick")
        self.taskMgr.remove("mouse-poll")
        if self.desktop:
            self.desktop.close()
            self.desktop = None
        self.taskMgr.remove("animation-frame")
        if hasattr(self, "tray_icon") and self.tray_icon:
            self.tray_icon.hide()
        if hasattr(self, "tray_registration"):
            self.tray_registration.close()
        if self.music_listener:
            self.music_listener.stop()
        if self.debug_tools:
            self.debug_tools.close()
        if self.hotkey_manager:
            self.hotkey_manager.close()
        self._persist_settings()
        ShowBase.userExit(self)

    def run(self) -> None:
        """Roda o laço principal do app."""
        self.logger.info("Iniciando SeJogaDesktopCompanion...")
        try:
            ShowBase.run(self)
        except KeyboardInterrupt:
            self.userExit()


def create_app(settings: Settings | None = None):
    """Cria o app com as configurações dadas ou carregadas."""
    if settings is None:
        settings = load_settings()
    return OverlayApp(settings)


def main() -> int:
    """Inicia o app e devolve o código de saída."""
    settings = load_settings()
    app = OverlayApp(settings)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

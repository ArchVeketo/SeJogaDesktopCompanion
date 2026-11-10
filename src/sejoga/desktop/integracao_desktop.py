"""Ícone, entrada na barra de tarefas e menu do sistema da janela nativa."""

import ctypes
from typing import ClassVar

import win32con
import win32gui

from sejoga.desktop import desktop_const as const_desktop


class DesktopIntegration:
    """Integra a janela ao shell do Windows (AppID, estilo, sessão)."""

    SETTINGS = 0x1F10
    PEEK = 0x1F20
    DANCE_COMMANDS: ClassVar[dict[int, str]] = {
        0x1F30: "head_bob",
        0x1F40: "hip_hop",
        0x1F50: "rock",
        0x1F60: "breakdance",
    }
    CAPTURE = 0x1F70

    @staticmethod
    def set_app_id():
        """Define o AppUserModelID do processo."""
        shell32 = ctypes.windll.shell32
        shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
        shell32.SetCurrentProcessExplicitAppUserModelID(
            "ArchVeketo.SeJogaDesktopCompanion"
        )

    def __init__(self, hwnd, icon_path):
        """Prende o tratamento de mensagens à janela ``hwnd``."""
        self.hwnd = hwnd
        self.requests = []
        self._icons = []
        self.apply_style()
        for size, kind in (
            (const_desktop.ICONE_PEQUENO_LADO, win32con.ICON_SMALL),
            (const_desktop.ICONE_GRANDE_LADO, win32con.ICON_BIG),
        ):
            icon = win32gui.LoadImage(
                0,
                str(icon_path),
                win32con.IMAGE_ICON,
                size,
                size,
                win32con.LR_LOADFROMFILE,
            )
            self._icons.append(icon)
            win32gui.SendMessage(hwnd, win32con.WM_SETICON, kind, icon)
        menu = win32gui.GetSystemMenu(hwnd, False)
        win32gui.ModifyMenu(
            menu,
            win32con.SC_CLOSE,
            win32con.MF_BYCOMMAND | win32con.MF_STRING,
            win32con.SC_CLOSE,
            "Encerrar Mário",
        )
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, self.SETTINGS, "Configurações...")
        win32gui.AppendMenu(menu, win32con.MF_STRING, self.PEEK, "Mostrar tentáculos")
        for command, style in self.DANCE_COMMANDS.items():
            win32gui.AppendMenu(
                menu,
                win32con.MF_STRING,
                command,
                "Prévia silenciosa: " + style.replace("_", " "),
            )
        win32gui.AppendMenu(
            menu, win32con.MF_STRING, self.CAPTURE, "Capturar diagnóstico"
        )
        self._old_proc = win32gui.SetWindowLong(
            hwnd, win32con.GWL_WNDPROC, self._window_proc
        )

    def apply_style(self):
        """Aplica o estilo de janela do overlay."""
        window_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_STYLE)
        win32gui.SetWindowLong(
            self.hwnd, win32con.GWL_STYLE, window_style | win32con.WS_SYSMENU
        )
        style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
        style = (style | win32con.WS_EX_APPWINDOW) & ~win32con.WS_EX_TOOLWINDOW
        win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, style)
        win32gui.SetWindowPos(
            self.hwnd,
            0,
            0,
            0,
            0,
            0,
            win32con.SWP_FRAMECHANGED
            | win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOZORDER
            | win32con.SWP_NOACTIVATE,
        )

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == win32con.WM_QUERYENDSESSION:
            return 1  # Ready; do not close until shutdown is actually confirmed.
        if message == win32con.WM_ENDSESSION:
            if wparam:
                self.requests.append("quit")
            return 0
        if message == win32con.WM_CLOSE:
            self.requests.append("quit")
            return 0
        if message == win32con.WM_SYSCOMMAND:
            command = wparam & const_desktop.SYSCOMMAND_MASCARA
            if command in self.DANCE_COMMANDS:
                self.requests.append("dance:" + self.DANCE_COMMANDS[command])
                return 0
            if command == self.CAPTURE:
                self.requests.append("capture")
                return 0
            action = {
                win32con.SC_CLOSE: "quit",
                self.SETTINGS: "settings",
                self.PEEK: "peek",
            }.get(command)
            if action:
                self.requests.append(action)
                return 0
        return win32gui.CallWindowProc(self._old_proc, hwnd, message, wparam, lparam)

    def close(self):
        """Desfaz a integração e restaura a janela."""
        if win32gui.IsWindow(self.hwnd):
            restore = ctypes.windll.user32.SetWindowLongPtrW
            restore.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            restore.restype = ctypes.c_void_p
            restore(self.hwnd, win32con.GWL_WNDPROC, self._old_proc)
        for icon in self._icons:
            win32gui.DestroyIcon(icon)
        self._icons.clear()

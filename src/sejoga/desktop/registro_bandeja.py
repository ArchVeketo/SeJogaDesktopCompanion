"""Check the actual Shell registration, not only Qt's requested visibility.

Qt's Windows tray implementation uses uID=0 and WM_APP+101. If the Shell
rejects the initial registration, reuse that HWND/callback so its existing
QMenu and activation signals still work. No second tray icon is created.
"""

import ctypes
import os
from ctypes import wintypes

import win32con
import win32gui
import win32process

from sejoga.desktop import desktop_const as const_desktop


class GUID(ctypes.Structure):
    """Estrutura ``GUID`` do Win32."""

    _fields_ = [
        ("data1", wintypes.DWORD),
        ("data2", wintypes.WORD),
        ("data3", wintypes.WORD),
        ("data4", ctypes.c_ubyte * 8),
    ]


class IconIdentifier(ctypes.Structure):
    """Estrutura ``NOTIFYICONIDENTIFIER`` do Win32."""

    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("guidItem", GUID),
    ]


class IconData(ctypes.Structure):
    """Estrutura ``NOTIFYICONDATAW`` do Win32."""

    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


class TrayRegistration:
    """Registro do ícone na área de notificação do Windows."""

    def __init__(self, icon_path, tooltip="SeJoga Companion"):
        """Guarda o ícone e a dica do registro."""
        self.icon_path = icon_path
        self.tooltip = tooltip
        self._icon = None
        self._cached_hwnd = None
        self.last_status = {"registered": False, "rect": None, "hwnd": None}
        shell = ctypes.WinDLL("shell32", use_last_error=True)
        self._get_rect = shell.Shell_NotifyIconGetRect
        self._get_rect.argtypes = [
            ctypes.POINTER(IconIdentifier),
            ctypes.POINTER(wintypes.RECT),
        ]
        self._get_rect.restype = ctypes.c_long
        self._notify = shell.Shell_NotifyIconW
        self._notify.argtypes = [wintypes.DWORD, ctypes.POINTER(IconData)]
        self._notify.restype = wintypes.BOOL

    @staticmethod
    def find_window(pid=None):
        """Localiza a janela do ícone do processo ``pid``."""
        pid = pid or os.getpid()
        found = []

        def collect(hwnd, _):
            try:
                _, owner = win32process.GetWindowThreadProcessId(hwnd)
                if (
                    owner == pid
                    and "TrayIcon" in win32gui.GetClassName(hwnd)
                    and win32gui.GetWindowText(hwnd) == "QTrayIconMessageWindow"
                ):
                    found.append(hwnd)
            except win32gui.error:
                pass  # Another application may close a window during enumeration.

        win32gui.EnumWindows(collect, None)
        return found[0] if found else None

    def status(self, pid=None):
        """Consulta o estado do ícone na bandeja."""
        hwnd = self._cached_hwnd if pid is None else None
        if hwnd is not None and not win32gui.IsWindow(hwnd):
            hwnd = None
            self._cached_hwnd = None
        if hwnd is None:
            hwnd = self.find_window(pid)
            if pid is None and hwnd is not None:
                self._cached_hwnd = hwnd
        result = {"registered": False, "rect": None, "hwnd": hwnd}
        if hwnd:
            identifier = IconIdentifier()
            identifier.cbSize = ctypes.sizeof(identifier)
            identifier.hWnd = hwnd
            rect = wintypes.RECT()
            code = self._get_rect(ctypes.byref(identifier), ctypes.byref(rect))
            # S_FALSE is also a valid registered icon in the hidden overflow.
            registered = code >= 0
            if not registered and pid is None:
                self._cached_hwnd = None
            result.update(
                registered=registered,
                hresult=code,
                rect=[rect.left, rect.top, rect.right, rect.bottom]
                if registered
                else None,
            )
        self.last_status = result
        return result

    def ensure(self):
        """Garante que o ícone esteja registrado."""
        result = self.status()
        if result["registered"] or not result["hwnd"]:
            return result
        if not self._icon:
            self._icon = win32gui.LoadImage(
                0,
                str(self.icon_path),
                win32con.IMAGE_ICON,
                const_desktop.TRAY_ICONE_LADO,
                const_desktop.TRAY_ICONE_LADO,
                win32con.LR_LOADFROMFILE,
            )
        data = IconData()
        data.cbSize = ctypes.sizeof(data)
        data.hWnd = result["hwnd"]
        data.uID = const_desktop.TRAY_UID
        data.uFlags = const_desktop.TRAY_FLAGS  # MESSAGE | ICON | TIP | SHOWTIP
        data.uCallbackMessage = (
            win32con.WM_APP + const_desktop.TRAY_CALLBACK_MESSAGE_OFFSET
        )
        data.hIcon = self._icon
        data.szTip = self.tooltip[: const_desktop.TRAY_TOOLTIP_MAX]
        ctypes.set_last_error(0)
        added = bool(self._notify(const_desktop.NIM_ADD, ctypes.byref(data)))
        error = ctypes.get_last_error()
        if added:
            data.uVersion = const_desktop.NOTIFYICON_VERSION_4
            self._notify(const_desktop.NIM_SETVERSION, ctypes.byref(data))
        result = self.status()
        result.update(add_succeeded=added, add_error=error)
        return result

    def close(self):
        """Remove o registro do ícone."""
        if self._icon:
            win32gui.DestroyIcon(self._icon)
            self._icon = None

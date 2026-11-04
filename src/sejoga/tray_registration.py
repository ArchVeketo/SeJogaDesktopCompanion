"""Check the actual Shell registration, not only Qt's requested visibility.

Qt's Windows tray implementation uses uID=0 and WM_APP+101. If the Shell
rejects the initial registration, reuse that HWND/callback so its existing
QMenu and activation signals still work. No second tray icon is created.
"""
import ctypes
from ctypes import wintypes
import os

import win32con
import win32gui
import win32process


class GUID(ctypes.Structure):
    _fields_ = [("data1", wintypes.DWORD), ("data2", wintypes.WORD),
                ("data3", wintypes.WORD), ("data4", ctypes.c_ubyte * 8)]


class IconIdentifier(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT), ("guidItem", GUID)]


class IconData(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID),
                ("hBalloonIcon", wintypes.HICON)]


class TrayRegistration:
    def __init__(self, icon_path, tooltip="SeJoga Companion"):
        self.icon_path = icon_path
        self.tooltip = tooltip
        self._icon = None
        self.last_status = {"registered": False, "rect": None, "hwnd": None}
        shell = ctypes.WinDLL("shell32", use_last_error=True)
        self._get_rect = shell.Shell_NotifyIconGetRect
        self._get_rect.argtypes = [ctypes.POINTER(IconIdentifier), ctypes.POINTER(wintypes.RECT)]
        self._get_rect.restype = ctypes.c_long
        self._notify = shell.Shell_NotifyIconW
        self._notify.argtypes = [wintypes.DWORD, ctypes.POINTER(IconData)]
        self._notify.restype = wintypes.BOOL

    @staticmethod
    def find_window(pid=None):
        pid = pid or os.getpid()
        found = []
        def collect(hwnd, _):
            try:
                _, owner = win32process.GetWindowThreadProcessId(hwnd)
                if owner == pid and win32gui.GetWindowText(hwnd) == "QTrayIconMessageWindow":
                    found.append(hwnd)
            except win32gui.error:
                pass  # Another application may close a window during enumeration.
        win32gui.EnumWindows(collect, None)
        return found[0] if found else None

    def status(self, pid=None):
        hwnd = self.find_window(pid)
        result = {"registered": False, "rect": None, "hwnd": hwnd}
        if hwnd:
            identifier = IconIdentifier()
            identifier.cbSize = ctypes.sizeof(identifier)
            identifier.hWnd = hwnd
            rect = wintypes.RECT()
            code = self._get_rect(ctypes.byref(identifier), ctypes.byref(rect))
            # S_FALSE is also a valid registered icon in the hidden overflow.
            result.update(registered=code >= 0, hresult=code,
                          rect=[rect.left, rect.top, rect.right, rect.bottom] if code >= 0 else None)
        self.last_status = result
        return result

    def ensure(self):
        result = self.status()
        if result["registered"] or not result["hwnd"]:
            return result
        if not self._icon:
            self._icon = win32gui.LoadImage(0, str(self.icon_path), win32con.IMAGE_ICON,
                                           16, 16, win32con.LR_LOADFROMFILE)
        data = IconData()
        data.cbSize = ctypes.sizeof(data)
        data.hWnd = result["hwnd"]
        data.uID = 0
        data.uFlags = 1 | 2 | 4 | 0x80  # MESSAGE | ICON | TIP | SHOWTIP
        data.uCallbackMessage = win32con.WM_APP + 101
        data.hIcon = self._icon
        data.szTip = self.tooltip[:127]
        ctypes.set_last_error(0)
        added = bool(self._notify(0, ctypes.byref(data)))  # NIM_ADD
        error = ctypes.get_last_error()
        if added:
            data.uVersion = 4
            self._notify(4, ctypes.byref(data))  # NIM_SETVERSION
        result = self.status()
        result.update(add_succeeded=added, add_error=error)
        return result

    def close(self):
        if self._icon:
            win32gui.DestroyIcon(self._icon)
            self._icon = None

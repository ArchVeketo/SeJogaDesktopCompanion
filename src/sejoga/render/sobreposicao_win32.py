"""Constantes e helpers Win32 da janela overlay (layered window + color key).

Extraído de janela.py sem reescrever a lógica: apenas reúne as constantes de
estilo estendido, Z-order e SetWindowPos, além dos helpers que aplicam o
color key magenta calibrado (RGB 214,0,214 após o tone mapping do PBR).
"""

from __future__ import annotations

import ctypes

import win32gui

# ============================================================
# Win32 Constants
# ============================================================

GWL_EXSTYLE = -20
GWL_STYLE = -16

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000

LWA_COLORKEY = 0x00000001
LWA_ALPHA = 0x00000002

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
HWND_BOTTOM = 1

SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040

# The calibrated final framebuffer key is RGB(214, 0, 214); keep the clear color and Win32 key paired.
COLOR_KEY = 0x00D600D6


# ============================================================
# Helpers
# ============================================================

def set_window_ex_style(hwnd: int, add_flags: int = 0, remove_flags: int = 0) -> None:
    """Modifica extended window style."""
    ex_style = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
    ex_style = (ex_style | add_flags) & ~remove_flags
    win32gui.SetWindowLong(hwnd, GWL_EXSTYLE, ex_style)


def set_layered_window_attributes(hwnd: int, color_key: int = COLOR_KEY, alpha: int = 255, flags: int = LWA_COLORKEY) -> bool:
    """Define color key e/ou alpha para layered window."""
    return ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, color_key, alpha, flags)


def set_window_pos_zorder(hwnd: int, zorder: int) -> bool:
    """Define Z-order: HWND_TOPMOST (-1), HWND_NOTOPMOST (-2), HWND_BOTTOM (1)."""
    return ctypes.windll.user32.SetWindowPos(hwnd, zorder, 0, 0, 0, 0,
                                             SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

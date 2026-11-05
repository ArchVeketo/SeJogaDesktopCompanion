import win32con

from sejoga.desktop_shell import DesktopIntegration


def test_restart_manager_query_or_cancellation_does_not_close_the_app():
    desktop = DesktopIntegration.__new__(DesktopIntegration)
    desktop.requests = []
    assert desktop._window_proc(0, win32con.WM_QUERYENDSESSION, 0, 1) == 1
    assert desktop.requests == []
    assert desktop._window_proc(0, win32con.WM_ENDSESSION, 0, 1) == 0
    assert desktop.requests == []
    assert desktop._window_proc(0, win32con.WM_ENDSESSION, 1, 1) == 0
    assert desktop.requests == ['quit']

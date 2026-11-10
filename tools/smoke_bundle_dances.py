"""Validate silent previews and independent tentacles in the real Windows exe."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from sejoga.configuracao import Settings, save_settings


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, default=Path(os.environ['LOCALAPPDATA'])/'Programs/SeJogaCompanion/current/SeJogaCompanion.exe')
    args=parser.parse_args()
    import win32con
    import win32gui
    import win32process
    from PIL import ImageGrab

    from sejoga.desktop.desktop_shell import DesktopIntegration
    from sejoga.desktop.tray_registration import TrayRegistration
    profile=Path(tempfile.mkdtemp(prefix='sejoga-bundle-dances-'))
    settings=Settings()
    settings.window.start_position=(650,200)
    settings.window.outline_enabled=False
    settings.physics.enabled=settings.music.enabled=False
    save_settings(settings, profile/'config.toml')
    env=dict(os.environ, SEJOGA_CONFIG_PATH=str(profile/'config.toml'))
    process=subprocess.Popen([str(args.exe)],cwd=args.exe.parent,env=env)
    hwnd=None
    report={'profile':str(profile),'exe':str(args.exe),'previews':[]}
    def records():
        return [json.loads(line) for path in profile.glob('debug-captures/*/frames.jsonl')
                for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    def capture():
        count=len(records())
        win32gui.PostMessage(hwnd,win32con.WM_SYSCOMMAND,DesktopIntegration.CAPTURE,0)
        for _ in range(60):
            current=records()
            if len(current)>count:
                return current[-1]
            time.sleep(.1)
        raise AssertionError('Bundle did not write a diagnostic capture')
    try:
        for _ in range(200):
            found=[]
            win32gui.EnumWindows(lambda h,_,found=found: found.append(h) if win32process.GetWindowThreadProcessId(h)[1]==process.pid
                                 and win32gui.GetWindowText(h)=='SeJogaDesktopCompanion' else None,None)
            if found:
                hwnd=found[0];break
            assert process.poll() is None, process.returncode
            time.sleep(.1)
        assert hwnd
        time.sleep(2)
        registration=TrayRegistration(Path('assets/brand/companion.ico'))
        # The renderer creates its HWND before Qt and the recovery timer finish
        # registering the tray. Wait for readiness on a cold frozen startup.
        for _ in range(100):
            tray=registration.status(process.pid)
            if tray['registered']:
                break
            assert process.poll() is None, process.returncode
            time.sleep(.1)
        assert tray['registered'], tray
        report['tray']=tray
        baseline=capture()
        report['initial_state']=baseline['animation_state']
        for command,style in DesktopIntegration.DANCE_COMMANDS.items():
            win32gui.PostMessage(hwnd,win32con.WM_SYSCOMMAND,command,0)
            time.sleep(4)
            before=capture()
            assert before['animation_state']=='dance' and before['dance_style']==style, before
            win32gui.PostMessage(hwnd,win32con.WM_SYSCOMMAND,DesktopIntegration.PEEK,0)
            time.sleep(3)
            during=capture()
            assert during['animation_state']=='dance' and during['appendage_remaining']>0, during
            ImageGrab.grab().save(profile/f'{style}-desktop.png')
            report['previews'].append({'style':style,'state':during['animation_state'],
                                       'appendage_remaining':during['appendage_remaining']})
        win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
        report['exit_code']=process.wait(timeout=15)
        assert report['exit_code']==0
        (profile/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        if process.poll() is None:
            if hwnd and win32gui.IsWindow(hwnd):
                win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
            process.wait(timeout=15)


if __name__=='__main__':
    main()

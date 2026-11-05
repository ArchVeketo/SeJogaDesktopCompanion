"""Check chroma edges and stale desktop pixels through resize cycles."""
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from sejoga import config


def main():
    profile = Path(tempfile.mkdtemp(prefix='sejoga-resize-qa-'))
    config.default_config_path = lambda: profile/'config.toml'
    from sejoga.window import OverlayApp
    from PySide6.QtWidgets import QWidget
    from PySide6.QtCore import Qt
    from PIL import ImageGrab
    from panda3d.core import Filename, Point3
    import numpy as np
    import win32gui
    settings = config.Settings()
    settings.physics.enabled = settings.music.enabled = False
    settings.window.outline_enabled = False
    settings.window.start_position = (700,250)
    app = OverlayApp(settings)
    app.hotkey_manager.close()
    backing = QWidget()
    backing.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
    backing.setStyleSheet('background-color: rgb(32,48,64);')
    backing.setGeometry(350,100,1600,1250)
    backing.show()
    app._update_z_order()
    app.taskMgr.remove('mouse-poll')
    def frames(n):
        for _ in range(n):
            app.taskMgr.step()
            time.sleep(.016)
    results = {'profile':str(profile), 'sizes':[], 'ghost_pixels':[]}
    try:
        frames(45)
        image = app.win.getScreenshot()
        rgb = np.frombuffer(image.getRamImageAs('RGB'),dtype=np.uint8).reshape(-1,3).astype(float)
        key = np.array([214,0,214])
        distance = np.linalg.norm(rgb-key,axis=1)
        results['near_key_spill_pixels'] = int(((distance > 1)&(distance < 35)).sum())
        # Small isolated near-magenta texels exist in the source texture.
        # A continuous coverage fringe produces hundreds of these pixels.
        assert results['near_key_spill_pixels'] < 64, results
        image.write(Filename.fromOsSpecific(str(profile/'outline-off.png')))
        previous = win32gui.GetWindowRect(app.hwnd)
        for part in ('left-feet','right-arm','body'):
            app._body_grab_part = part
            app._body_grab_point = Point3(app.renderer._rig_nodes[part].getPos(app.renderer.model_np))
            app._window_start_pos = previous[:2]
            app._drag_active = True
            frames(80)
            results['sizes'].append(app.win.getXSize())
            previous = win32gui.GetWindowRect(app.hwnd)
            app.win.getScreenshot().write(Filename.fromOsSpecific(str(profile/f'{part}.png')))
            app._drag_active = False
            frames(200)
            current = win32gui.GetWindowRect(app.hwnd)
            app.qt_app.processEvents()
            frames(3)
            # Only inspect regions occupied by the old canvas and now vacated.
            area = (max(350,min(previous[0],current[0])),max(100,min(previous[1],current[1])),
                    min(1950,max(previous[2],current[2])),min(1350,max(previous[3],current[3])))
            desktop = np.array(ImageGrab.grab(bbox=area))
            yy,xx = np.indices(desktop.shape[:2]);xx+=area[0];yy+=area[1]
            outside = (xx<current[0])|(xx>=current[2])|(yy<current[1])|(yy>=current[3])
            ghosts = int((np.any(desktop[:,:,:3] != (32,48,64),axis=2)&outside).sum())
            results['ghost_pixels'].append(ghosts)
            assert ghosts == 0, results
            previous=current
        ImageGrab.grab().save(profile/'desktop.png')
        (profile/'results.json').write_text(json.dumps(results,indent=2))
        print(json.dumps(results,indent=2))
    finally:
        backing.close()
        app.userExit()


if __name__ == '__main__':
    main()

"""Visual QA isolado para o novo renderizador procedural de tentáculos."""
import sys, time, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import config
profile=Path(tempfile.mkdtemp(prefix="sejoga-new-tentacles-"))
config.default_config_path=lambda:profile/"config.toml"
from sejoga.window import OverlayApp
from panda3d.core import Filename
settings=config.Settings(); settings.physics.enabled=False; settings.music.enabled=False
settings.window.outline_enabled=False
app=OverlayApp(settings);app.hotkey_manager.close(); app.taskMgr.remove("mouse-poll")
renderer=app.renderer
def tick():
    pose=app.animation_controller.update(1/60)
    renderer.apply_rig_pose(pose)
    renderer.update_appendages(1/60, app.animation_controller.state.value=='peek')
app._animation_tick=tick
scale=renderer._view_height/renderer.height/renderer.model_np.getScale().x
assert .001 < scale < .02, scale
assert len(renderer.tentacle_pool.tentacles)==6
for tentacle in renderer.tentacle_pool.tentacles:
    assert max(s.length for s in tentacle.segments)<.2
    assert max(s.width for s in tentacle.segments)<.06
    assert abs(tentacle.anchor.x)<.3 and abs(tentacle.anchor.y)<.3 and .2<tentacle.anchor.z<1.2, tentacle.anchor

def capture(name):
    app.graphicsEngine.renderFrame(); app.graphicsEngine.renderFrame()
    path=profile/f"{name}.png"
    assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(path)))
    print(path)
try:
    for _ in range(30): app.taskMgr.step(); time.sleep(.016)
    capture("idle")
    app.animation_controller.interact("peek")
    for frame in range(180):
        app.taskMgr.step(); time.sleep(.016)
        if frame in (30,90,179): capture(f"curious-{frame}")
    # Every generated segment stays inside a conservative local model envelope.
    for tentacle in renderer.tentacle_pool.tentacles:
        if tentacle.state.value!="dormant":
            for seg in tentacle.segments:
                assert max(abs(seg.pos.x),abs(seg.pos.y)) < .6 and .2 < seg.pos.z < 1.2, seg.pos
    settings.window.outline_enabled=False
    renderer.set_outline_settings(settings.window)
    assert renderer.outline_np.isStashed()
    capture("outline-disabled")
    app.debug_tools.set_visible(True)
    app.taskMgr.step()
    capture("joint-axes")
    app.debug_tools.set_visible(False)
    renderer.model_np.setH(renderer.MODEL_FACING_HEADING + 35)
    renderer.outline_np.setH(renderer.MODEL_FACING_HEADING + 35)
    app.taskMgr.step()
    capture("three-quarter")
    renderer.model_np.setH(renderer.MODEL_FACING_HEADING)
    renderer.outline_np.setH(renderer.MODEL_FACING_HEADING)
    for frame in range(480):
        app.taskMgr.step()
        if frame in (150,240,330,479): capture(f"retract-{frame}")
    assert all(t.state.value=='dormant' for t in renderer.tentacle_pool.tentacles)
    print("QA",profile,"scale",scale)
finally:
    app.debug_tools.close(); app.music_listener.stop(); app.tray_icon.hide()
    app.desktop.close(); app.desktop=None; app.destroy()

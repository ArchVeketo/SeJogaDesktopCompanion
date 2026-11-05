"""Capture the full speaker entrance and settled musical pose."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from sejoga import config


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--style',default='head_bob',choices=('head_bob','hip_hop','rock','breakdance'))
    args=parser.parse_args()
    profile=Path(tempfile.mkdtemp(prefix='sejoga-music-scene-'))
    config.default_config_path=lambda:profile/'config.toml'
    from sejoga.window import OverlayApp
    from panda3d.core import Filename, Point3, Vec3
    from PIL import ImageGrab
    settings=config.Settings()
    settings.physics.enabled=settings.music.enabled=False
    settings.window.outline_enabled=False
    settings.window.start_position=(700,250)
    app=OverlayApp(settings)
    rest_feet=[app.renderer._rig_nodes[name].getTightBounds(app.renderer.model_np)[0].z
               for name in ('left-feet','right-feet')]
    app.hotkey_manager.close();app.taskMgr.remove('mouse-poll')
    app.animation_controller.preview_dance(args.style)
    captures=[]
    try:
        for frame in range(660):
            app.taskMgr.step()
            if frame in (15,35,50,70,90,115,140,180,300,480,659):
                app.win.getScreenshot().write(Filename.fromOsSpecific(str(profile/f'{frame:04}.png')))
                captures.append({'frame':frame,'speaker_age':app.renderer.music_speaker.age,
                                 'door_degrees':app.renderer.tentacle_director._door_current,
                                 'throw_limbs':len(app.renderer.tentacle_director.speaker_throw_limbs),
                                 'visible_slime':sum(not n.isHidden() for n in app.renderer.music_speaker.effects.slime)})
        speaker=app.renderer.music_speaker
        body=app.renderer._rig_nodes['body']
        low,high=body.find('**/mesh20').getTightBounds(body)
        plane,normal=speaker.support_in_stage()
        points=[app.renderer.model_anchor.getRelativePoint(body,Point3(x,low.y,z))
                for x in (low.x,high.x) for z in (low.z,high.z)]
        error=abs(min((point-plane).dot(normal) for point in points))/app.renderer.model_np.getScale().x
        foot_errors=[abs(app.renderer._rig_nodes[name].getTightBounds(app.renderer.model_anchor)[0].z-
                        app.renderer.model_np.getMat().xformPoint(Point3(0,0,rest_feet[i])).z)
                     /app.renderer.model_np.getScale().x for i,name in enumerate(('left-feet','right-feet'))]
        results={'profile':str(profile),'style':args.style,
                 'speaker_size':[speaker.width,speaker.depth,speaker.height],
                 'character_rest_size':list(speaker.character_size),
                 'back_contact_error_model_units':error,'foot_floor_errors':foot_errors,
                 'captures':captures,'canvas':app.renderer.width}
        (profile/'results.json').write_text(json.dumps(results,indent=2))
        print(json.dumps(results,indent=2),flush=True)
        assert speaker.width > speaker.character_size.x
        assert speaker.height > speaker.character_size.z
        assert any(c['throw_limbs'] and c['visible_slime'] for c in captures), results
        assert captures[-1]['throw_limbs']==captures[-1]['visible_slime']==0, results
        if args.style=='head_bob':
            assert error < .005,results
            assert max(foot_errors) < .005,results
        ImageGrab.grab().save(profile/'desktop.png')
        print('Scene checks passed.',flush=True)
    finally:
        app._force_exit=True
        try:
            app.userExit()
        except SystemExit:
            pass


if __name__=='__main__':main()

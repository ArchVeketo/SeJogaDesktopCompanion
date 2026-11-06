"""Measure complete render-loop cadence for each silent choreography."""
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from sejoga import config


def main():
    profile=Path(tempfile.mkdtemp(prefix='sejoga-dance-performance-'))
    config.default_config_path=lambda:profile/'config.toml'
    from sejoga.render.window import OverlayApp
    settings=config.Settings()
    settings.physics.enabled=settings.music.enabled=False
    settings.window.outline_enabled=False
    app=OverlayApp(settings)
    app.hotkey_manager.close();app.taskMgr.remove('mouse-poll')
    original=app._animation_tick
    costs=[];intervals=[];previous=None
    def tick():
        nonlocal previous
        start=time.perf_counter()
        if previous is not None:intervals.append((start-previous)*1000)
        previous=start
        original()
        costs.append((time.perf_counter()-start)*1000)
    app._animation_tick=tick
    results={'profile':str(profile)}
    try:
        for _ in range(40):app.taskMgr.step()
        for style in ('head_bob','hip_hop','rock','breakdance'):
            app.animation_controller.preview_dance(style)
            app.animation_controller._dance_preview_remaining=60
            for _ in range(90):app.taskMgr.step()
            costs.clear();intervals.clear();previous=None
            for frame in range(480):
                if frame==120:
                    app.animation_controller.interact('peek')
                app.taskMgr.step()
            results[style]={'fps':round(1000/statistics.mean(intervals),2),
                            'cpu_mean_ms':round(statistics.mean(costs),2),
                            'cpu_p95_ms':round(sorted(costs)[int(len(costs)*.95)],2)}
        (profile/'results.json').write_text(json.dumps(results,indent=2))
        print(json.dumps(results,indent=2))
    finally:
        app.userExit()


if __name__=='__main__':main()

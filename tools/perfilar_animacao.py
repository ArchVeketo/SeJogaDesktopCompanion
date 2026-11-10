"""Measure real frame cadence and animation CPU cost with an isolated profile."""

import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import configuracao


def main():  # noqa: PLR0915  # TODO convenção: ferramenta de captura/GPU: fatiar sem rodar na GPU arrisca a saída; lote próprio
    """Executa o perfil de animação."""
    profile = Path(tempfile.mkdtemp(prefix="sejoga-animation-profile-"))
    configuracao.default_config_path = lambda: profile / "config.toml"
    from sejoga.render.janela import OverlayApp

    settings = configuracao.Settings()
    settings.physics.enabled = False
    settings.music.enabled = False
    app = OverlayApp(settings)
    costs, intervals = [], []
    original_tick = app._animation_tick
    previous = None

    def measured_tick():
        nonlocal previous
        start = time.perf_counter()
        if previous is not None:
            intervals.append((start - previous) * 1000)
        previous = start
        original_tick()
        costs.append((time.perf_counter() - start) * 1000)

    app._animation_tick = measured_tick
    app.hotkey_manager.close()
    app.taskMgr.remove("mouse-poll")
    app._mouse_hovered = False
    results = {}
    try:  # noqa: PLR1702  # TODO convenção: ferramenta de captura/GPU: fatiar sem rodar na GPU arrisca a saída; lote próprio
        for _ in range(30):
            app.taskMgr.step()
        for name, count in (("idle", 120), ("peek", 480)):
            if name == "peek":
                app.animation_controller.interact("peek")
            costs.clear()
            intervals.clear()
            previous = None
            for frame in range(count):
                app.taskMgr.step()
                if name == "peek" and frame in (30, 180, 400):
                    app.debug_tools.capture_once()
            results[name] = {
                "updates": len(costs),
                "fps": round(1000 / statistics.mean(intervals), 2),
                "frame_p95_ms": round(sorted(intervals)[int(len(intervals) * 0.95)], 2),
                "animation_mean_ms": round(statistics.mean(costs), 2),
                "animation_p95_ms": round(sorted(costs)[int(len(costs) * 0.95)], 2),
            }
            assert len(costs) == count, "Animation must update once per rendered frame"
        (profile / "timings.json").write_text(json.dumps(results, indent=2))
        print(json.dumps({"profile": str(profile), **results}, indent=2))
    finally:
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.desktop.close()
        app.desktop = None
        app.destroy()


if __name__ == "__main__":
    main()

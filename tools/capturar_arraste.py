"""Capturas do renderer REAL com o mascote arrastado por cada parte (Parte 4).

Uma captura por parte pega (corpo, perna, braço), de frente e de lado, após o
ponteiro se mover por ``FRAMES`` quadros. Cada parte sobe um subprocesso (o
ShowBase abre uma vez por processo). Headless renderiza, mas só o olho do usuário
numa GPU real valida o resultado (recalibracao-gpu.md, C11 a C14).

Uso:
    set SEJOGA_CONFIG_PATH=C:\\tmp\\sejoga-cap\\config.toml
    python tools/capturar_arraste.py --saida <pasta>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
#: Parte pega -> nó do rig onde fica o ponto de pega.
PARTES = {"corpo": "body", "perna": "legs", "braco": "right-arm"}
#: Nome do grab_part que o BodyMotion espera para cada parte.
GRAB_PART = {"corpo": "body", "perna": "left-feet", "braco": "right-arm"}
CAMERAS = {"frente": 0.0, "lado": 90.0}
FRAMES = 90
#: Movimento circular do ponteiro (px) e período (quadros).
RAIO_PONTEIRO_PX = 90.0
PERIODO_QUADROS = 40.0
TIMEOUT_S = 240

_FILHO = """
import sys, tempfile
from math import sin, cos, tau
from pathlib import Path
raiz, parte, camera, saida = sys.argv[1:5]
sys.path.insert(0, raiz + "/src")
sys.path.insert(0, raiz + "/tools")
import capturar_arraste as c
from sejoga import config
perfil = Path(tempfile.mkdtemp(prefix="sejoga-arraste-"))
config.default_config_path = lambda: perfil / "config.toml"
from sejoga.render.window import OverlayApp
from panda3d.core import Filename
s = config.Settings(); s.physics.enabled = False; s.music.enabled = False
app = OverlayApp(s); app.hotkey_manager.close(); app.taskMgr.remove("mouse-poll")
r = app.renderer; a = app.animation_controller
r.set_model_rotation(y=c.CAMERAS[camera])
no = r._rig_nodes[c.PARTES[parte]]
def tick():
    k = tick.n; tick.n += 1
    ang = tau * k / c.PERIODO_QUADROS
    pose = a.update(1/60, grounded=True, dragging=True, grab_part=c.GRAB_PART[parte],
                    pointer_position=(600 + c.RAIO_PONTEIRO_PX * cos(ang), 300 + c.RAIO_PONTEIRO_PX * sin(ang)))
    r.apply_rig_pose(pose)
    grip = no.getPos(r.model_np)
    r.apply_body_motion(a.body_motion.snapshot, grip, grounded=True, dragging=True)
    r.update_appendages(1/60, False)
tick.n = 0
app._animation_tick = tick
for _ in range(c.FRAMES):
    app.taskMgr.step()
app.win.getScreenshot().write(Filename.fromOsSpecific(saida))
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Capturas do arraste por parte.")
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--rotulo", default="depois")
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    ambiente = dict(os.environ)
    ambiente.setdefault("SEJOGA_CONFIG_PATH", str(Path(tempfile.gettempdir()) / "sejoga-cap" / "config.toml"))
    falhas = 0

    for parte in PARTES:
        for camera in CAMERAS:
            destino = args.saida / f"{args.rotulo}-arraste-{parte}-{camera}.png"
            processo = subprocess.run(
                [sys.executable, "-c", _FILHO, str(RAIZ), parte, camera, str(destino)],
                cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=TIMEOUT_S,
            )

            if processo.returncode != 0 or not destino.exists():
                falhas += 1
                print(f"FALHOU {parte}/{camera}: {processo.stderr[-400:]}", file=sys.stderr)
            else:
                print(destino)

    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())

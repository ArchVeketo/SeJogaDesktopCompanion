"""Capturas dos dedos em cadeia (renderer REAL) abertos, meio fechados e fechados.

Uma captura por pose, vista (frente/lado) e contorno (com/sem), recortada em torno
da mão direita e ampliada sem filtro (pixel exato). Headless renderiza, mas só o
olho do usuário numa GPU real valida o resultado (recalibracao-gpu.md, C15 a C19).

Uso:
    python tools/capturar_dedos.py --saida <pasta>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
#: Pose -> flexão pedida (graus) para os cinco dedos, via tabela de gestos.
POSES = {"abertos": 0, "meio": 38, "fechados": 80}
VISTAS = {"frente": 0.0, "lado": 90.0}
QUADROS_POR_POSE = 60
#: Lado (px) do recorte em torno da mão e ampliação inteira do recorte.
RECORTE_PX = 150
AMPLIACAO = 4
TIMEOUT_S = 300
_FILHO = """
import sys, tempfile
from pathlib import Path
raiz, vista, contorno, pasta = sys.argv[1:5]
sys.path.insert(0, raiz + "/src")
sys.path.insert(0, raiz + "/tools")
import capturar_dedos as c
from sejoga import config
perfil = Path(tempfile.mkdtemp(prefix="sejoga-dedos-"))
config.default_config_path = lambda: perfil / "config.toml"
from sejoga.render.janela import OverlayApp
from sejoga.animacao import finger_gestures as fg
from panda3d.core import Filename, PNMImage, Point2, Point3
s = config.Settings(); s.physics.enabled = False; s.music.enabled = False
s.window.outline_enabled = contorno == "com"
app = OverlayApp(s); app.hotkey_manager.close(); app.taskMgr.remove("mouse-poll")
r = app.renderer
r.set_model_rotation(y=c.VISTAS[vista])
r.set_outline_settings(s.window)
atual = ["abertos"]
for nome, graus in c.POSES.items():
    fg.GESTURES["t_" + nome] = (graus,) * 5
original = r.finger_gestures.update
r.finger_gestures.update = lambda dt, gesto: original(dt, "t_" + atual[0])
for nome in c.POSES:
    atual[0] = nome
    for _ in range(c.QUADROS_POR_POSE):
        app.taskMgr.step()
    imagem = PNMImage()
    app.win.getScreenshot().store(imagem)
    mao = r._rig_nodes["fingers"].getPos(app.cam)
    tela = Point2()
    app.cam.node().getLens().project(Point3(mao), tela)
    cx = (tela.x + 1) / 2 * imagem.getXSize()
    cy = (1 - tela.y) / 2 * imagem.getYSize()
    lado = c.RECORTE_PX
    x0 = max(0, min(imagem.getXSize() - lado, int(cx - lado / 2)))
    y0 = max(0, min(imagem.getYSize() - lado, int(cy - lado / 2)))
    saida = PNMImage(lado * c.AMPLIACAO, lado * c.AMPLIACAO, 4)
    for y in range(lado * c.AMPLIACAO):
        for x in range(lado * c.AMPLIACAO):
            sx, sy = x0 + x // c.AMPLIACAO, y0 + y // c.AMPLIACAO
            saida.setXelA(x, y, imagem.getRed(sx, sy), imagem.getGreen(sx, sy), imagem.getBlue(sx, sy), 1.0)
    saida.write(Filename.fromOsSpecific(str(Path(pasta) / f"dedos-{nome}-{vista}-contorno-{contorno}.png")))
"""


def main() -> int:
    """Executa a captura e devolve o código de saída."""
    parser = argparse.ArgumentParser(description="Capturas dos dedos em cadeia.")
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    ambiente = dict(os.environ)
    ambiente.setdefault(
        "SEJOGA_CONFIG_PATH",
        str(Path(tempfile.gettempdir()) / "sejoga-cap" / "config.toml"),
    )
    falhas = 0

    for vista in VISTAS:
        for contorno in ("com", "sem"):
            processo = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    _FILHO,
                    str(RAIZ),
                    vista,
                    contorno,
                    str(args.saida),
                ],
                cwd=RAIZ,
                env=ambiente,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_S,
            )

            if processo.returncode != 0:
                falhas += 1
                print(
                    f"FALHOU {vista}/{contorno}: {processo.stderr[-600:]}",
                    file=sys.stderr,
                )
            else:
                print(f"ok {vista} contorno-{contorno}")

    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())

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
#: Ações do controlador usadas também no menu da bandeja.
POSES = {"relaxados": None, "abertos": "open_hands", "fechados": "close_fists"}
VISTAS = {"frente": 0.0, "lado": 90.0}
QUADROS_POR_POSE = 60
#: Lado (px) do recorte em torno da mão e ampliação inteira do recorte.
RECORTE_PX = 150
AMPLIACAO = 4
TIMEOUT_S = 300
_FILHO = """
import sys, time
from pathlib import Path
raiz, vista, contorno, pasta = sys.argv[1:5]
sys.path.insert(0, raiz + "/src")
sys.path.insert(0, raiz + "/tools")
import capturar_dedos as c
from sejoga.configuracao import Settings
from sejoga.render.janela import OverlayApp
from panda3d.core import Point2
from PIL import Image

s = Settings()
s.physics.enabled = s.music.enabled = False
s.window.outline_enabled = contorno == "com"
app = OverlayApp(s)
app.hotkey_manager.close()
app.taskMgr.remove("mouse-poll")
r = app.renderer
r.set_model_rotation(y=c.VISTAS[vista])
try:
    for nome, acao in c.POSES.items():
        if acao:
            app.animation_controller.interact(acao)
        for _ in range(c.QUADROS_POR_POSE):
            app.taskMgr.step()
            time.sleep(1 / 90)
        textura = app.win.getScreenshot()
        largura, altura = textura.getXSize(), textura.getYSize()
        imagem = Image.frombytes("RGB", (largura, altura), bytes(textura.getRamImageAs("RGB")))
        imagem = imagem.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        tela = Point2()
        assert app.cam.node().getLens().project(r._rig_nodes["fingers"].getPos(app.cam), tela)
        cx, cy = (tela.x + 1) * largura / 2, (1 - tela.y) * altura / 2
        lado = c.RECORTE_PX
        x0 = max(0, min(largura - lado, int(cx - lado / 2)))
        y0 = max(0, min(altura - lado, int(cy - lado / 2)))
        recorte = imagem.crop((x0, y0, x0 + lado, y0 + lado))
        recorte.resize((lado * c.AMPLIACAO,) * 2, Image.Resampling.NEAREST).save(
            Path(pasta) / f"dedos-{nome}-{vista}-contorno-{contorno}.png"
        )
finally:
    app.debug_tools.close()
    app.music_listener.stop()
    app.tray_icon.hide()
    app.desktop.close()
    app.destroy()

"""


def main() -> int:
    """Executa a captura e devolve o código de saída."""
    parser = argparse.ArgumentParser(description="Capturas dos dedos em cadeia.")
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    perfil = Path(tempfile.mkdtemp(prefix="sejoga-dedos-")) / "config.toml"
    ambiente = dict(os.environ, SEJOGA_CONFIG_PATH=str(perfil))
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

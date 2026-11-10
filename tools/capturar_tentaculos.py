"""Sequência de frames da onda dos tentáculos (renderer REAL), calmo e agitado.

Cada temperamento gera uma folha de contato com os quadros em intervalos fixos,
recortada em torno da cabeça e ampliada sem filtro (pixel exato). Headless
renderiza com p3tinydisplay, mas só o olho do usuário numa GPU real valida o
movimento (recalibracao-gpu.md, C20 a C24).

Uso:
    python tools/capturar_tentaculos.py --saida <pasta>
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

#: Temperamento -> nome de arquivo. Calmo é o mais lento; agitado, o mais rápido.
TEMPERAMENTOS = {"calm": "calmo", "playful": "agitado"}
#: Vista -> giro do modelo (graus). De lado a onda aparece no perfil; de frente ela se projeta no eixo da câmera.
VISTAS = {"frente": 0.0, "lado": 90.0}
PASSO_S = 1 / 30
#: Quadros de espera (2 s) até a porta abrir; a sequência termina antes dos 4,8 s do estado curioso.
QUADROS_ESPERA = 60
#: Quadros capturados e intervalo entre eles (cobre mais de um ciclo da onda calma).
QUADROS_CAPTURADOS = 12
INTERVALO_QUADROS = 6
COLUNAS = 4
#: Lado (px) do recorte em torno da cabeça e ampliação inteira.
RECORTE_PX = 220
AMPLIACAO = 2
TIMEOUT_S = 300

_FILHO = """
import sys, tempfile
from pathlib import Path
raiz, temperamento, vista, pasta = sys.argv[1:5]
sys.path.insert(0, raiz + "/src")
sys.path.insert(0, raiz + "/tools")
import capturar_tentaculos as c
from sejoga import config
perfil = Path(tempfile.mkdtemp(prefix="sejoga-tent-"))
config.default_config_path = lambda: perfil / "config.toml"
from sejoga.render.window import OverlayApp
from panda3d.core import ClockObject, Filename, PNMImage, Point2, Point3
s = config.Settings(); s.physics.enabled = False; s.music.enabled = False
app = OverlayApp(s); app.hotkey_manager.close(); app.taskMgr.remove("mouse-poll")
relogio = ClockObject.getGlobalClock()
relogio.setMode(ClockObject.MNonRealTime)
relogio.setDt(c.PASSO_S)
r = app.renderer
app.animation_controller.set_idle_personality(temperamento)
r.set_model_rotation(y=c.VISTAS[vista])
r.tentacle_director.trigger_curious()
for _ in range(c.QUADROS_ESPERA):
    app.taskMgr.step()
quadros = []
for indice in range(c.QUADROS_CAPTURADOS):
    for _ in range(c.INTERVALO_QUADROS):
        app.taskMgr.step()
    imagem = PNMImage()
    app.win.getScreenshot().store(imagem)
    cabeca = r._rig_nodes["head"].getPos(app.cam)
    tela = Point2()
    app.cam.node().getLens().project(Point3(cabeca), tela)
    cx = (tela.x + 1) / 2 * imagem.getXSize()
    cy = (1 - tela.y) / 2 * imagem.getYSize()
    lado = c.RECORTE_PX
    x0 = max(0, min(imagem.getXSize() - lado, int(cx - lado / 2)))
    y0 = max(0, min(imagem.getYSize() - lado, int(cy - lado / 2)))
    quadros.append((imagem, x0, y0))
colunas = c.COLUNAS
linhas = (len(quadros) + colunas - 1) // colunas
lado = c.RECORTE_PX * c.AMPLIACAO
folha = PNMImage(colunas * lado, linhas * lado, 4)
folha.fill(0.1, 0.1, 0.1)
folha.alphaFill(1.0)
for indice, (imagem, x0, y0) in enumerate(quadros):
    ox, oy = (indice % colunas) * lado, (indice // colunas) * lado
    for y in range(lado):
        for x in range(lado):
            sx, sy = x0 + x // c.AMPLIACAO, y0 + y // c.AMPLIACAO
            folha.setXelA(ox + x, oy + y, imagem.getRed(sx, sy), imagem.getGreen(sx, sy), imagem.getBlue(sx, sy), 1.0)
folha.write(Filename.fromOsSpecific(str(Path(pasta) / f"ondulacao-{c.TEMPERAMENTOS[temperamento]}-{vista}.png")))
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Sequência de frames da ondulação dos tentáculos.")
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    ambiente = dict(os.environ)
    ambiente.setdefault("SEJOGA_CONFIG_PATH", str(Path(tempfile.gettempdir()) / "sejoga-cap" / "config.toml"))
    falhas = 0
    for temperamento in TEMPERAMENTOS:
        for vista in VISTAS:
            processo = subprocess.run(
                [sys.executable, "-c", _FILHO, str(RAIZ), temperamento, vista, str(args.saida)],
                cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=TIMEOUT_S,
            )
            if processo.returncode != 0:
                falhas += 1
                print(f"FALHOU {temperamento}/{vista}: {processo.stderr[-800:]}", file=sys.stderr)
            else:
                print(f"ok {temperamento} {vista}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())

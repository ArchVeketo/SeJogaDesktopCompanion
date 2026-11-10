"""Sequências da coreografia tentáculos x porta (renderer REAL), calmo e agitado.

Uma execução por temperamento e vista grava três folhas de contato recortadas em
torno da cabeça, ampliadas sem filtro: abrir/empurrar, saída e fechar/esquecer/puxar.
Headless renderiza com p3tinydisplay; só o olho do usuário numa GPU real valida o
movimento (recalibracao-gpu.md, C25 a C32).

Uso:
    python tools/capturar_porta_tentaculos.py --saida <pasta>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

#: Temperamento -> nome de arquivo.
TEMPERAMENTOS = {"calm": "calmo", "playful": "agitado"}
#: Vista -> giro do modelo (graus).
VISTAS = {"frente": 0.0, "lado": 90.0}
PASSO_S = 1 / 30
#: Sequência -> início (passo; None = quando a porta é esquecida), intervalo e quantidade de quadros.
SEQUENCIAS = {
    "abrir": {"inicio": 0, "intervalo": 3, "quadros": 12},
    "saida": {"inicio": 36, "intervalo": 8, "quadros": 12},
    "fechar": {"inicio": None, "intervalo": 6, "quadros": 16},
}
#: Espirro (burst): saída violenta, 12 quadros a cada 2 passos.
SEQUENCIAS_ESPIRRO = {"espirro": {"inicio": 0, "intervalo": 2, "quadros": 12}}
#: Limite de passos para a coreografia inteira (calmo leva ~14 s).
PASSOS_MAXIMOS = 30 * 25
COLUNAS = 4
#: Lado (px) do recorte em torno da cabeça e ampliação inteira.
RECORTE_PX = 220
AMPLIACAO = 2
TIMEOUT_S = 600

_FILHO = """
import sys, tempfile
from pathlib import Path
raiz, temperamento, vista, pasta, modo = sys.argv[1:6]
sys.path.insert(0, raiz + "/src")
sys.path.insert(0, raiz + "/tools")
import capturar_porta_tentaculos as c
from sejoga import config
perfil = Path(tempfile.mkdtemp(prefix="sejoga-porta-"))
config.default_config_path = lambda: perfil / "config.toml"
from sejoga.render.janela import OverlayApp
from sejoga.tentaculos.coreografia_porta import FasePorta
from panda3d.core import ClockObject, Filename, PNMImage, Point2, Point3
s = config.Settings(); s.physics.enabled = False; s.music.enabled = False
app = OverlayApp(s); app.hotkey_manager.close(); app.taskMgr.remove("mouse-poll")
relogio = ClockObject.getGlobalClock()
relogio.setMode(ClockObject.MNonRealTime)
relogio.setDt(c.PASSO_S)
r = app.renderer
diretor = r.tentacle_director
app.animation_controller.set_idle_personality(temperamento)
r.set_model_rotation(y=c.VISTAS[vista])
sequencias = c.SEQUENCIAS_ESPIRRO if modo == "espirro" else c.SEQUENCIAS
(diretor.trigger_sneeze if modo == "espirro" else diretor.trigger_curious)()
inicios = {nome: cfg["inicio"] for nome, cfg in sequencias.items()}
quadros = {nome: [] for nome in sequencias}
fases = []
def recortar():
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
    return imagem, x0, y0
for passo in range(c.PASSOS_MAXIMOS):
    app.taskMgr.step()
    if "fechar" in inicios and inicios["fechar"] is None and diretor.coreografia.fase is FasePorta.ESQUECIDA:
        inicios["fechar"] = passo
    for nome, cfg in sequencias.items():
        inicio = inicios[nome]
        if inicio is None or passo < inicio or len(quadros[nome]) >= cfg["quadros"]:
            continue
        if (passo - inicio) % cfg["intervalo"] == 0:
            quadros[nome].append(recortar())
            fases.append((nome, passo, diretor.coreografia.fase.value, round(diretor._door_current, 1)))
    if all(len(quadros[nome]) >= cfg["quadros"] for nome, cfg in sequencias.items()):
        break
for nome, lista in quadros.items():
    colunas = c.COLUNAS
    linhas = (len(lista) + colunas - 1) // colunas
    lado = c.RECORTE_PX * c.AMPLIACAO
    folha = PNMImage(colunas * lado, linhas * lado, 4)
    folha.fill(0.1, 0.1, 0.1)
    folha.alphaFill(1.0)
    for indice, (imagem, x0, y0) in enumerate(lista):
        ox, oy = (indice % colunas) * lado, (indice // colunas) * lado
        for y in range(lado):
            for x in range(lado):
                sx, sy = x0 + x // c.AMPLIACAO, y0 + y // c.AMPLIACAO
                folha.setXelA(ox + x, oy + y, imagem.getRed(sx, sy), imagem.getGreen(sx, sy), imagem.getBlue(sx, sy), 1.0)
    folha.write(Filename.fromOsSpecific(str(Path(pasta) / f"porta-{nome}-{c.TEMPERAMENTOS[temperamento]}-{vista}.png")))
for linha in fases:
    print("quadro", *linha)
"""


def main() -> int:
    """Executa a captura e devolve o código de saída."""
    parser = argparse.ArgumentParser(
        description="Sequências da coreografia tentáculos x porta."
    )
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    ambiente = dict(os.environ)
    ambiente.setdefault(
        "SEJOGA_CONFIG_PATH",
        str(Path(tempfile.gettempdir()) / "sejoga-cap" / "config.toml"),
    )
    falhas = 0
    for temperamento in TEMPERAMENTOS:
        for vista, modo in [(v, "porta") for v in VISTAS] + [("lado", "espirro")]:
            processo = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    _FILHO,
                    str(RAIZ),
                    temperamento,
                    vista,
                    str(args.saida),
                    modo,
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
                    f"FALHOU {temperamento}/{vista}: {processo.stderr[-800:]}",
                    file=sys.stderr,
                )
            else:
                print(f"ok {temperamento} {vista}")
                print("\n".join(processo.stdout.splitlines()[-1:]))
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())

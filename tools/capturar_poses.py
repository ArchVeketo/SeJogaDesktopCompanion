"""Capturas do renderer REAL em lote (frente e lado) + folha de contato.

Para cada estado/gesto e cada câmera, sobe o app num subprocesso (o ShowBase só
abre uma vez por processo), roda ``--frames`` quadros com
``tools/verificar_eixos.capturar`` e guarda o último quadro em ``--saida``. No
fim monta ``folha-<rotulo>.png`` com tudo rotulado, para comparação visual.

``--raiz`` aponta outro checkout (ex.: worktree do commit anterior) para gerar
as capturas "antes" com o código daquele checkout.

Headless renderiza (p3tinydisplay/wgl offscreen), mas só o olho do usuário numa
GPU real valida a anatomia (ver recalibracao-gpu.md).

Uso:
    python tools/capturar_poses.py --rotulo depois
    python tools/capturar_poses.py --rotulo antes --raiz C:/tmp/sejoga-antes
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ_PADRAO = Path(__file__).resolve().parents[1]
SAIDA_PADRAO = RAIZ_PADRAO / ".agents" / "tasks" / "frente3-animacao" / "capturas" / "parte3"
ESTADOS_PADRAO = ("idle", "wave", "drag", "dance", "sleep", "stretch", "poke", "fall")
CAMERAS_PADRAO = ("frente", "lado")
#: Quadros por captura: o crossfade/colisão assentam em ~0.5 s.
FRAMES_PADRAO = 41
#: Tempo máximo (s) por subprocesso de captura.
TIMEOUT_CAPTURA_S = 240
#: Escala da miniatura na folha de contato e altura do rótulo (px).
ESCALA_MINIATURA = 0.5
ALTURA_ROTULO_PX = 16

_SCRIPT_FILHO = """
import sys
from pathlib import Path
raiz = Path(sys.argv[1])
sys.path.insert(0, str(raiz / "tools"))
sys.path.insert(0, str(raiz / "src"))
import verificar_eixos as ve
ve.PASTA_ARTEFATOS = Path(sys.argv[5])
ve.capturar(sys.argv[2], int(sys.argv[4]), sys.argv[3], prefixo="cap")
"""


def capturar_uma(raiz: Path, estado: str, camera: str, frames: int, destino: Path) -> bool:
    temporaria = destino.parent / f"_tmp-{estado}-{camera}"
    temporaria.mkdir(parents=True, exist_ok=True)
    ambiente = dict(os.environ, PYTHONPATH="")
    processo = subprocess.run(
        [sys.executable, "-c", _SCRIPT_FILHO, str(raiz), estado, camera, str(frames), str(temporaria)],
        cwd=raiz, env=ambiente, capture_output=True, text=True, timeout=TIMEOUT_CAPTURA_S,
    )
    pngs = sorted(temporaria.glob("cap-*.png"))
    ok = processo.returncode == 0 and bool(pngs)

    if ok:
        shutil.copyfile(pngs[-1], destino)
    else:
        print(f"FALHOU {estado}/{camera}: {processo.stderr[-400:]}", file=sys.stderr)

    shutil.rmtree(temporaria, ignore_errors=True)

    return ok


def folha_de_contato(arquivos: list[tuple[str, Path]], destino: Path, colunas: int) -> None:
    from PIL import Image, ImageDraw

    imagens = [(rotulo, Image.open(p).convert("RGB")) for rotulo, p in arquivos]
    largura = int(imagens[0][1].width * ESCALA_MINIATURA)
    altura = int(imagens[0][1].height * ESCALA_MINIATURA)
    linhas = (len(imagens) + colunas - 1) // colunas
    folha = Image.new("RGB", (largura * colunas, (altura + ALTURA_ROTULO_PX) * linhas), "white")
    desenho = ImageDraw.Draw(folha)

    for i, (rotulo, img) in enumerate(imagens):
        x, y = (i % colunas) * largura, (i // colunas) * (altura + ALTURA_ROTULO_PX)
        desenho.text((x + 4, y + 2), rotulo, fill="black")
        folha.paste(img.resize((largura, altura)), (x, y + ALTURA_ROTULO_PX))

    folha.save(destino)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capturas do renderer real em lote.")
    parser.add_argument("--rotulo", required=True, help="prefixo dos arquivos (ex.: antes, depois)")
    parser.add_argument("--raiz", type=Path, default=RAIZ_PADRAO, help="checkout cujo código renderiza")
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    parser.add_argument("--estados", default=",".join(ESTADOS_PADRAO))
    parser.add_argument("--cameras", default=",".join(CAMERAS_PADRAO))
    parser.add_argument("--frames", type=int, default=FRAMES_PADRAO)
    args = parser.parse_args()

    if not os.environ.get("SEJOGA_CONFIG_PATH"):
        print("Defina SEJOGA_CONFIG_PATH com um perfil isolado.", file=sys.stderr)
        return 2

    args.saida.mkdir(parents=True, exist_ok=True)
    cameras = args.cameras.split(",")
    feitos: list[tuple[str, Path]] = []

    for estado in args.estados.split(","):
        for camera in cameras:
            destino = args.saida / f"{args.rotulo}-{estado}-{camera}.png"

            if capturar_uma(args.raiz.resolve(), estado, camera, args.frames, destino):
                feitos.append((f"{args.rotulo} {estado} {camera}", destino))
                print(f"ok {destino.name}", flush=True)

    if feitos:
        folha = args.saida / f"folha-{args.rotulo}.png"
        folha_de_contato(feitos, folha, colunas=len(cameras) * 2)
        print(f"folha: {folha}")

    return 0 if feitos else 1


if __name__ == "__main__":
    sys.exit(main())

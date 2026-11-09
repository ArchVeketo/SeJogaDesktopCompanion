"""Oráculo VISUAL dos eixos de braço: projeta a ponta da mão em PIXELS de tela.

A câmera frontal só enxerga X/Y da tela, NUNCA a profundidade: isto é
regressão de pixel, não prova de eixo. A prova de eixo é a FK do grafo de cena
(``tests/test_cinematica_oraculo.py``, ``tools/oraculo_cena.py --eixos``). Este utilitário sobe o renderer
real offscreen, dispara um estado/gesto, roda N frames e, para cada frame,
PROJETA a ponta das mãos (``hand``/``hand2``) e o ombro (``right-arm``) na
câmera, devolvendo PIXELS de tela. Também salva PNG/GIF para revisão humana.

Serve de infra para o oráculo visual e é reusado pelo teste de pixel
(``tests/test_eixos_bracos_tela.py``). Sem GPU/offscreen, ``capturar`` levanta
``RenderIndisponivel`` (o teste faz skip; aqui o main imprime e sai).

Uso (a partir da raiz do repositório):
    python tools/verificar_eixos.py --estado idle --frames 6
    python tools/verificar_eixos.py --estado wave --frames 40 --camera frente
    python tools/verificar_eixos.py --estado wave --camera lado

A projeção segue o mesmo idioma de ``tools/smoke_native_body.py``:
``cam.node().getLens().project(cam.getRelativePoint(render, ponto), Point2)``
→ NDC → pixels (origem no topo-esquerda: y cresce para BAIXO).
"""
# Pilota atributos Optional do OverlayApp e troca _animation_tick, igual aos
# demais tools (preview_anim). mypy: disable-error-code="union-attr, method-assign"
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import config

#: Pasta onde os artefatos de verificação ficam para revisão humana.
PASTA_ARTEFATOS = Path(__file__).resolve().parents[1] / ".agents" / "tasks" / "conserto-eixos"

ESTILOS_DANCA = ("head_bob", "hip_hop", "rock", "breakdance")
GESTOS = (
    "wave", "stretch", "peek", "sneeze", "click", "double_click",
    "pet", "poke", "hang_loose", "thumbs_up", "finger_gun", "land", "hit",
)
ANGULOS_CAMERA = {"frente": 0, "lado": 90, "tras": 180, "cima": 0}


class RenderIndisponivel(RuntimeError):
    """Render offscreen não pôde iniciar (sem GPU/driver)."""


@dataclass(frozen=True, slots=True)
class FramePixels:
    """Pixels de tela de uma amostra de frame (origem no topo-esquerda)."""

    frame: int
    mao_dir: tuple[float, float]
    mao_esq: tuple[float, float]
    ombro_dir: tuple[float, float]
    centro: tuple[float, float]


def _perfil() -> Path:
    env = os.environ.get("SEJOGA_CONFIG_PATH")
    if env:
        destino = Path(env)
        destino.parent.mkdir(parents=True, exist_ok=True)
        return destino.parent
    return Path(tempfile.mkdtemp(prefix="sejoga-verificar-eixos-"))


def _pilotar(animation, estado: str):
    """Entrada de animation.update apropriada ao estado (igual a preview_anim)."""
    velocidade = (0.0, 0.0)
    arrastando = aterrado = False
    gravidade = musica = False
    aterrado = True
    if estado == "walk":
        velocidade = (120.0, 0.0)
    elif estado == "run":
        velocidade = (520.0, 0.0)
    elif estado == "drag":
        arrastando = True
    elif estado == "fall":
        aterrado = False
        gravidade = True
        velocidade = (0.0, 600.0)
    elif estado == "dance" or estado in ESTILOS_DANCA:
        musica = True
    return animation.update(
        1 / 60,
        velocity=velocidade,
        grounded=aterrado,
        gravity_active=gravidade,
        dragging=arrastando,
        music_playing=musica,
        music_intensity=1.0 if musica else 0.0,
        music_bass=0.8 if musica else 0.0,
        music_bpm=120 if musica else None,
        dance_chance=1.0 if musica else 0.0,
        react_to_beat=musica,
        beat_detected=musica,
        idle_enabled=True,
        sleep_after_idle_seconds=0 if estado == "sleep" else 600,
    )


def _projetar(renderer, ponto) -> tuple[float, float]:
    """Projeta um ponto do mundo em pixels de tela (origem topo-esquerda)."""
    from panda3d.core import Point2

    cam = renderer.showbase.cam
    ndc = Point2()
    cam.node().getLens().project(cam.getRelativePoint(renderer.showbase.render, ponto), ndc)
    x_px = (ndc.x + 1.0) * renderer.width / 2.0
    y_px = (1.0 - ndc.y) * renderer.height / 2.0
    return (x_px, y_px)


def _ponta_mao(renderer, nome: str):
    """Ponto de mundo da ponta da mão (topo do bounding box do nó da mão)."""
    from panda3d.core import Point3

    render = renderer.showbase.render
    no = renderer._rig_nodes.get(nome)
    if no is None:
        return None
    limites = no.getTightBounds(render)
    if not limites:
        return no.getPos(render)
    minimo, maximo = limites
    # Ponta = ponto mais ALTO (maior Z de mundo) do nó da mão, no centro X/Y.
    return Point3((minimo.x + maximo.x) * 0.5, (minimo.y + maximo.y) * 0.5, maximo.z)


def capturar(
    estado: str,
    frames: int = 6,
    camera: str = "frente",
    salvar: bool = True,
    prefixo: str | None = None,
) -> list[FramePixels]:
    """Sobe o renderer real, dispara ``estado`` e devolve pixels por frame.

    Levanta ``RenderIndisponivel`` se o offscreen não iniciar (sem GPU).
    """
    frames = max(1, frames)
    perfil = _perfil()
    config.default_config_path = lambda: perfil / "config.toml"

    # Qt antes de Panda3D/PIL (mesma ordem de preview_anim).
    # isort: off
    try:
        from sejoga.render.window import OverlayApp
        from panda3d.core import Filename, Point3
        from PIL import Image
    except Exception as exc:  # pragma: no cover - ambiente sem engine
        raise RenderIndisponivel(str(exc)) from exc
    # isort: on

    settings = config.Settings()
    settings.physics.enabled = False
    settings.music.enabled = False
    settings.behavior.sleep_after_idle_seconds = 0 if estado == "sleep" else 600

    try:
        app = OverlayApp(settings)
    except Exception as exc:  # pragma: no cover - sem GPU/offscreen
        raise RenderIndisponivel(str(exc)) from exc

    app.hotkey_manager.close()
    app.taskMgr.remove("mouse-poll")
    animation = app.animation_controller
    renderer = app.renderer

    if estado in ESTILOS_DANCA:
        animation.preview_dance(estado)
    elif estado in GESTOS:
        animation.interact(estado)

    if camera != "frente":
        renderer.set_model_rotation(y=ANGULOS_CAMERA[camera])
        if camera == "cima":
            renderer.set_model_rotation(x=60, y=0)

    def tick():
        pose = _pilotar(animation, estado)
        renderer.apply_rig_pose(pose)
        renderer.apply_body_motion(
            animation.body_motion.snapshot, None,
            grounded=True, dragging=estado == "drag",
        )
        renderer.update_appendages(1 / 60, animation.appendage_remaining > 0)

    app._animation_tick = tick

    amostras: list[FramePixels] = []
    pngs: list[Path] = []
    nome = prefixo or f"{estado}-{camera}"
    if salvar:
        PASTA_ARTEFATOS.mkdir(parents=True, exist_ok=True)

    try:
        for frame in range(frames):
            app.taskMgr.step()

            mao_dir = _ponta_mao(renderer, "hand")
            mao_esq = _ponta_mao(renderer, "hand2")
            ombro = renderer._rig_nodes.get("right-arm")
            ombro_pt = ombro.getPos(renderer.showbase.render) if ombro else Point3(0, 0, 0)
            centro_pt = renderer.model_np.getPos(renderer.showbase.render)

            amostras.append(
                FramePixels(
                    frame=frame,
                    mao_dir=_projetar(renderer, mao_dir) if mao_dir else (0.0, 0.0),
                    mao_esq=_projetar(renderer, mao_esq) if mao_esq else (0.0, 0.0),
                    ombro_dir=_projetar(renderer, ombro_pt),
                    centro=_projetar(renderer, centro_pt),
                )
            )

            if salvar and (frame % 2 == 0 or frame == frames - 1):
                caminho = PASTA_ARTEFATOS / f"{nome}-{frame:04}.png"
                app.win.getScreenshot().write(Filename.fromOsSpecific(str(caminho)))
                pngs.append(caminho)

        if salvar and pngs:
            quadros = [Image.open(c).convert("RGB") for c in pngs]
            gif = PASTA_ARTEFATOS / f"{nome}.gif"
            quadros[0].save(gif, save_all=True, append_images=quadros[1:], duration=66, loop=0)
            print(f"GIF: {gif}", flush=True)
            print(f"PNGs: {len(pngs)} em {PASTA_ARTEFATOS}", flush=True)
    finally:
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.desktop.close()
        app.desktop = None
        app.destroy()

    return amostras


def main() -> int:
    parser = argparse.ArgumentParser(description="Oráculo de eixos: projeta a mão em pixels de tela.")
    parser.add_argument("--estado", default="idle", help="estado ou gesto a renderizar")
    parser.add_argument("--frames", type=int, default=6, help="número de frames")
    parser.add_argument("--camera", default="frente", choices=list(ANGULOS_CAMERA), help="ângulo da câmera")
    parser.add_argument("--prefixo", default=None, help="prefixo do nome dos PNG/GIF")
    args = parser.parse_args()

    try:
        amostras = capturar(args.estado, args.frames, args.camera, prefixo=args.prefixo)
    except RenderIndisponivel as exc:
        print(f"RENDER INDISPONÍVEL (sem GPU/offscreen): {exc}", file=sys.stderr, flush=True)
        return 2

    for a in amostras:
        print(
            f"frame {a.frame:3d} | mao_dir=({a.mao_dir[0]:6.1f},{a.mao_dir[1]:6.1f}) "
            f"mao_esq=({a.mao_esq[0]:6.1f},{a.mao_esq[1]:6.1f}) "
            f"ombro=({a.ombro_dir[0]:6.1f},{a.ombro_dir[1]:6.1f}) "
            f"centro=({a.centro[0]:6.1f},{a.centro[1]:6.1f})",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

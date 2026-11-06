"""Prévia offscreen de um estado ou clipe de animação.

Renderiza uma sequência de PNG + um GIF usando perfil temporário
(SEJOGA_CONFIG_PATH quando definido, senão um diretório temporário), com
window-type offscreen e sem subir o app completo: física e música desligadas,
mouse-poll e hotkeys removidos, pilotando animation.update manualmente.

Uso (a partir da raiz do repositório):
    python tools/preview_anim.py --estado idle --frames 60
    python tools/preview_anim.py --estado head_bob --frames 120

Estados aceitos: qualquer valor de AnimationState (idle, walk, run, drag,
fall, dance, sleep, wave, stretch, peek, sneeze, ...) e os estilos de dança
head_bob / hip_hop / rock / breakdance.
"""
# Script de preview: pilota atributos do OverlayApp que são Optional e troca
# o _animation_tick, padrão já usado nos demais tools (ex. preview_tentacle_system).
# mypy: disable-error-code="union-attr, method-assign"
import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sejoga import config

# Estilos de dança aceitos diretamente como estado.
ESTILOS_DANCA = ("head_bob", "hip_hop", "rock", "breakdance")
# Gestos de interação disparados via controller.interact(kind).
GESTOS = (
    "wave", "stretch", "peek", "sneeze", "click", "double_click",
    "pet", "poke", "hang_loose", "thumbs_up", "finger_gun", "land", "hit",
)


def _perfil() -> Path:
    """Perfil isolado: usa SEJOGA_CONFIG_PATH quando definido."""
    env = os.environ.get("SEJOGA_CONFIG_PATH")
    if env:
        destino = Path(env)
        destino.parent.mkdir(parents=True, exist_ok=True)
        return destino.parent
    return Path(tempfile.mkdtemp(prefix="sejoga-preview-anim-"))


def _pilotar(animation, estado: str, drag_estado):
    """Aplica a entrada de animation.update apropriada para o estado pedido."""
    velocidade = (0.0, 0.0)
    arrastando = False
    aterrado = True
    gravidade = False
    musica = False
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Prévia offscreen de um estado de animação.")
    parser.add_argument("--estado", default="idle", help="estado ou estilo de dança a renderizar")
    parser.add_argument("--frames", type=int, default=60, help="número de frames a renderizar")
    parser.add_argument("--camera", default="frente", choices=["frente", "lado", "cima", "tras"],
                        help="ângulo da câmera: frente (padrão), lado, cima, tras")
    parser.add_argument("--personalidade", default=None,
                        help="personalidade de idle (street, fighter, stylish, rhythm, calm, curious, playful, shy, confident)")
    args = parser.parse_args()

    estado = args.estado
    frames = max(1, args.frames)
    camera = args.camera
    personalidade = args.personalidade

    perfil = _perfil()
    config.default_config_path = lambda: perfil / "config.toml"

    # Importa a janela (que carrega Qt) ANTES de Panda3D/PIL: os bundles do
    # Windows trazem runtimes MSVC diferentes e o primeiro carregado vence.
    # Panda3D antes de Qt quebra, então a ordem é fixada com isort: off/on.
    # isort: off
    from sejoga.render.window import OverlayApp
    from panda3d.core import Filename
    from PIL import Image
    # isort: on

    settings = config.Settings()
    settings.physics.enabled = False
    settings.music.enabled = False
    settings.behavior.sleep_after_idle_seconds = 0 if estado == "sleep" else 600

    app = OverlayApp(settings)
    app.hotkey_manager.close()
    app.taskMgr.remove("mouse-poll")
    animation = app.animation_controller

    # Define a personalidade de idle se especificada
    if personalidade:
        animation.set_idle_personality(personalidade)

    # Dispara o estado pedido antes do loop.
    if estado in ESTILOS_DANCA:
        animation.preview_dance(estado)
    elif estado in GESTOS:
        animation.interact(estado)

    # Rotaciona o modelo pra simular diferentes ângulos de câmera
    angulos_camera = {"frente": 0, "lado": 90, "tras": 180, "cima": 0}
    if camera != "frente":
        app.renderer.set_model_rotation(y=angulos_camera[camera])
        if camera == "cima":
            app.renderer.set_model_rotation(x=60, y=0)

    def tick():
        pose = _pilotar(animation, estado, app._drag_active)
        app.renderer.apply_rig_pose(pose)
        app.renderer.apply_body_motion(
            animation.body_motion.snapshot, None,
            grounded=True, dragging=estado == "drag",
        )
        app.renderer.update_appendages(1 / 60, animation.appendage_remaining > 0)

    app._animation_tick = tick

    gerados = []
    try:
        for frame in range(frames):
            app.taskMgr.step()
            if frame % 2 == 0 or frame == frames - 1:
                caminho = perfil / f"{estado}-{frame:04}.png"
                app.win.getScreenshot().write(Filename.fromOsSpecific(str(caminho)))
                gerados.append(caminho)
        quadros = [Image.open(c).convert("RGB") for c in gerados]
        if quadros:
            gif = perfil / f"{estado}.gif"
            quadros[0].save(gif, save_all=True, append_images=quadros[1:], duration=66, loop=0)
            print(f"GIF: {gif}", flush=True)
        print(f"PNGs: {len(gerados)} em {perfil}", flush=True)
    finally:
        app.debug_tools.close()
        app.music_listener.stop()
        app.tray_icon.hide()
        app.desktop.close()
        app.desktop = None
        app.destroy()
    return 0 if gerados else 1


if __name__ == "__main__":
    sys.exit(main())

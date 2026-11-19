"""Renderizador de previews em alta resolução (1024x1024, 70-85% de preenchimento).

Gera pranchas de inspeção visual multi-ângulo (frontal e 3/4) para manutenção
rápida do Mário sem depender de captura manual da área de trabalho:
  - idle_closed (frontal e 3/4)
  - head_open_interior (frontal e 3/4, foco no interior do armário e moldura)
  - curious_tentacles (frontal e 3/4, espiada com ventosas visíveis)
  - sneeze_tentacles (frontal e 3/4, espirro/enxurrada com todos os tentáculos)
  - hands_fingers (zoom nas mãos: aberta, punho fechado e joinha/rock)
  - dance_speaker (dança ativa com palco de 3 caixas e com rádio compacto)

Uso:
    python tools/render_preview.py [--saida .local/previews]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))


def _avancar_quadros(base, r, ctrl, n: int, dt: float = 1 / 60, visivel: bool = True) -> None:
    """Avança controlador, pose de rig, corpo, apêndices e Panda3D por ``n`` quadros."""
    for _ in range(n):
        pose = ctrl.update(dt)
        r.apply_rig_pose(pose)
        r.lower_body.apply(ctrl.leg_motion.pose, True, dt=dt)
        r.apply_body_motion(
            ctrl.body_motion.snapshot,
            grounded=True,
            dragging=False,
            angulo_giro_pedido=ctrl.angulo_giro_pedido,
        )
        r.update_appendages(dt, visivel)
        base.taskMgr.step()


def _enquadrar(
    base,
    r,
    nodos: list,
    *,
    yaw_graus: float = 0.0,
    pitch_graus: float = 0.0,
    preenchimento: float = 0.78,
    margem_extra: float = 1.0,
) -> None:
    """Posiciona a câmera ortográfica para que ``nodos`` ocupem ~78% do quadro 1024x1024."""
    from panda3d.core import NodePath, Point3, Vec3

    pivot = NodePath("cam-orbit")
    pivot.reparentTo(base.render)
    pivot.setPos(0, 0, 0)
    pivot.setHpr(yaw_graus, pitch_graus, 0.0)

    base.cam.reparentTo(pivot)
    base.cam.setPos(0, -25.0, 0)
    base.cam.lookAt(pivot)

    mins: list[Point3] = []
    maxs: list[Point3] = []
    for n in nodos:
        if n is None or n.isEmpty() or n.isHidden():
            continue
        b = n.getTightBounds(base.cam)
        if b is not None and b[0] != b[1]:
            mins.append(b[0])
            maxs.append(b[1])
    if not mins:
        b = r.model_np.getTightBounds(base.cam)
        mins.append(b[0])
        maxs.append(b[1])

    lo = Point3(min(p.x for p in mins), min(p.y for p in mins), min(p.z for p in mins))
    hi = Point3(max(p.x for p in maxs), max(p.y for p in maxs), max(p.z for p in maxs))
    centro_cam = (lo + hi) * 0.5
    centro_mundo = base.render.getRelativePoint(base.cam, centro_cam)

    largura = max(0.05, (hi.x - lo.x) * margem_extra)
    altura = max(0.05, (hi.z - lo.z) * margem_extra)
    span = max(largura, altura) / preenchimento

    pivot.setPos(centro_mundo)
    base.cam.setPos(0, -25.0, 0)
    base.cam.lookAt(pivot)
    base.cam.wrtReparentTo(base.render)
    pivot.removeNode()

    lens = base.cam.node().getLens()
    lens.setFilmSize(span, span)
    lens.setNearFar(0.1, 100.0)

    if r.outline_np:
        escala_modelo = max(1e-4, r.model_np.getSz(base.render))
        outline_px = float(base.settings.window.outline_width)
        thickness = (outline_px * span / 1024.0) / escala_modelo
        r.outline_np.setShaderInput("outline_thickness", thickness)
        r.outline_np.setShaderInput("outline_thickness_runtime", thickness)

    base.graphicsEngine.renderFrame()
    base.graphicsEngine.renderFrame()


def gerar_previews(pasta_saida: Path) -> list[Path]:
    """Renderiza todas as pranchas de diagnóstico e retorna a lista de arquivos."""
    from panda3d.core import loadPrcFileData

    loadPrcFileData("", "window-type offscreen")
    loadPrcFileData("", "win-size 1024 1024")
    from direct.showbase.ShowBase import ShowBase

    from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
    from sejoga.configuracao import load_settings
    from sejoga.render.renderizador import Panda3DRenderer

    pasta_saida.mkdir(parents=True, exist_ok=True)
    gerados: list[Path] = []

    base = ShowBase()
    base.settings = load_settings()
    base.settings.window.outline_enabled = True
    base.settings.window.outline_color = "#FFFF00"
    base.settings.window.outline_width = 2.8

    r = Panda3DRenderer(base, 0, 1024, 1024, use_chroma_resolve=False)
    if base.win:
        base.win.setClearColor((0.09, 0.09, 0.12, 1.0))
    ctrl = AnimationController(r.rig)
    base.animation_controller = ctrl

    def salvar(nome: str) -> Path:
        from panda3d.core import Filename

        caminho = pasta_saida / nome
        base.screenshot(Filename.fromOsSpecific(str(caminho)), defaultFilename=False)
        gerados.append(caminho)
        print(f"[preview] salvo: {caminho}")
        return caminho

    head_np = r._rig_nodes["head"]
    hand_r = r._rig_nodes["hand"]
    hand_l = r._rig_nodes["hand2"]

    # 1. IDLE CLOSED (corpo inteiro, 78% do quadro, frontal e 3/4)
    _avancar_quadros(base, r, ctrl, 30, visivel=False)
    _enquadrar(base, r, [r.model_np], yaw_graus=0.0, pitch_graus=-4.0, preenchimento=0.80)
    salvar("idle_closed_front.png")

    _enquadrar(base, r, [r.model_np], yaw_graus=32.0, pitch_graus=-6.0, preenchimento=0.80)
    salvar("idle_closed_34.png")

    # 2. HEAD OPEN INTERIOR (zoom na cabeça aberta com interior escuro e moldura)
    r._door_requested = 72.0
    r.tentacle_director._door_current = 72.0
    r.tentacle_director._door_requested = 72.0
    for _ in range(15):
        r.update_appendages(1 / 60, False)
        base.taskMgr.step()

    _enquadrar(base, r, [head_np], yaw_graus=0.0, pitch_graus=-3.0, preenchimento=0.78)
    salvar("head_open_interior_front.png")

    _enquadrar(base, r, [head_np], yaw_graus=28.0, pitch_graus=-8.0, preenchimento=0.78)
    salvar("head_open_interior_34.png")

    # 3. CURIOUS TENTACLES (espiada com ventosas visíveis)
    r._door_requested = 0.0
    r.tentacle_director.trigger_curious(2)
    for _ in range(135):
        r.update_appendages(1 / 60, True)
        base.taskMgr.step()
    nodos_curious = [head_np] + [
        t.mesh_node for t in r.tentacle_pool.tentacles if t.mesh_node and not t.mesh_node.isHidden()
    ]
    _enquadrar(base, r, nodos_curious, yaw_graus=0.0, pitch_graus=-4.0, preenchimento=0.78)
    salvar("curious_tentacles_front.png")

    _enquadrar(base, r, nodos_curious, yaw_graus=34.0, pitch_graus=-10.0, preenchimento=0.78)
    salvar("curious_tentacles_34.png")

    # 4. SNEEZE TENTACLES (espirro / enxurrada com TODOS os tentáculos saindo juntos)
    r.tentacle_director.encerrar_espiada(interromper=True)
    for _ in range(40):
        r.update_appendages(1 / 60, False)
        base.taskMgr.step()

    r.tentacle_director.trigger_sneeze()
    r._door_requested = 105.0
    r.tentacle_director._door_current = 105.0
    for _ in range(42):
        r.update_appendages(1 / 60, True)
        base.taskMgr.step()
    nodos_sneeze = [head_np] + [
        t.mesh_node for t in r.tentacle_pool.tentacles if t.mesh_node and not t.mesh_node.isHidden()
    ]
    _enquadrar(base, r, nodos_sneeze, yaw_graus=0.0, pitch_graus=-4.0, preenchimento=0.78)
    salvar("sneeze_tentacles_front.png")

    _enquadrar(base, r, nodos_sneeze, yaw_graus=32.0, pitch_graus=-10.0, preenchimento=0.78)
    salvar("sneeze_tentacles_34.png")

    # Limpa tentáculos antes das mãos e dança
    r._door_requested = 0.0
    r.tentacle_director.encerrar_espiada(interromper=True)
    r.tentacle_director._door_current = 0.0
    r.tentacle_director._door_requested = 0.0
    for _ in range(90):
        r.update_appendages(1 / 60, False)
        base.taskMgr.step()

    # 5. HANDS & FINGERS (zoom nas mãos/dedos: aberta, punho, joinha+apontar, paz+joinha)
    def _resetar_cenas_reacoes() -> None:
        ctrl._reaction = None
        ctrl._gesto_mao_esquerda = None
        ctrl._cena_idle_nome = ""
        ctrl._cena_idle_tempo = 0.0
        ctrl.cena_idle_amostra = type(ctrl.cena_idle_amostra)()
        ctrl._cooldowns.clear()
        _avancar_quadros(base, r, ctrl, 20, visivel=False)

    for nome_arq, gesto_dir, gesto_esq in (
        ("hands_fingers_open.png", "open_hands", None),
        ("hands_fingers_fist.png", "close_fists", None),
        ("hands_fingers_thumbsup.png", "thumbs_up", "point"),
        ("hands_fingers_peace.png", "peace", "thumbs_up"),
    ):
        _resetar_cenas_reacoes()
        ctrl.interact(gesto_dir, left_gesture=gesto_esq)
        _avancar_quadros(base, r, ctrl, 45, visivel=False)
        _enquadrar(
            base,
            r,
            [hand_r, hand_l],
            yaw_graus=14.0,
            pitch_graus=-10.0,
            preenchimento=0.78,
            margem_extra=1.22,
        )
        salvar(nome_arq)

    # 5b. NOVOS IDLES EXPRESSIVOS (conferir_luva, pensar_gabinete, segurar_porta_timido)
    for nome_arq, cena_nome, tempo_alvo, yaw_c in (
        ("idle_conferir_luva.png", "conferir_luva", 1.85, 16.0),
        ("idle_pensar_gabinete.png", "pensar_gabinete", 2.20, 8.0),
        ("idle_segurar_porta_timido.png", "segurar_porta_timido", 1.05, 22.0),
    ):
        _resetar_cenas_reacoes()
        ctrl.interact(cena_nome)
        _avancar_quadros(base, r, ctrl, max(1, round(tempo_alvo * 60)), visivel=False)
        _enquadrar(
            base,
            r,
            [r.model_np],
            yaw_graus=yaw_c,
            pitch_graus=-6.0,
            preenchimento=0.80,
        )
        salvar(nome_arq)

    _resetar_cenas_reacoes()

    # 6. DANCE + SPEAKER (palco 3 caixas e rádio compacto — prova zero crash!)
    ctrl.preview_dance("hip_hop")
    r.trocar_caixa_de_som("palco")
    _avancar_quadros(base, r, ctrl, 540, visivel=False)
    _enquadrar(
        base,
        r,
        [r.model_np, r.music_speaker.root],
        yaw_graus=16.0,
        pitch_graus=-6.0,
        preenchimento=0.78,
    )
    salvar("dance_speaker_palco.png")

    r.tentacle_director.encerrar_espiada(interromper=True)
    ctrl.preview_dance("hip_hop")
    r.trocar_caixa_de_som("radio")
    _avancar_quadros(base, r, ctrl, 420, visivel=False)
    _enquadrar(
        base,
        r,
        [r.model_np, r.music_speaker.root],
        yaw_graus=16.0,
        pitch_graus=-6.0,
        preenchimento=0.78,
    )
    salvar("dance_speaker_radio.png")

    return gerados


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera previews 1024x1024 ampliados do Mário.")
    parser.add_argument(
        "--saida",
        type=Path,
        default=RAIZ / ".local" / "previews",
        help="Pasta onde salvar os PNGs gerados.",
    )
    args = parser.parse_args()
    gerar_previews(args.saida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

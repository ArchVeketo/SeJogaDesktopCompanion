"""Viewport 3D Panda3D embutido no editor com câmera, picking, gizmo e overlays.

Carrega ``PySide6`` antes de importar ``panda3d`` em tempo de execução para evitar
conflitos de runtime MSVC no Windows e instancia ``Panda3DRenderer`` com
``use_chroma_resolve=False`` sobre fundo cinza neutro.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from sejoga.animacao import dados_autorais, ik_bracos
from sejoga.animacao.braco_tuning import POLO_COTOVELO_ANATOMICO
from sejoga.animacao.movimento_pernas import LegPose
from sejoga.configuracao import Settings
from sejoga.editor.ik_membros import (
    delta_euler_curto,
    extrair_estado_pernas,
    resolver_ik_perna,
    resolver_mira_coxa,
)
from sejoga.editor.roteiro import ObstaculoPrevia
from sejoga.editor.sessao_previa import STEP_SIM_S, QuadroPrevia
from sejoga.nucleo import cinematica as cin
from sejoga.nucleo.cinematica import BASE_ADICIONAL_GRAUS
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rotation3

if TYPE_CHECKING:
    from panda3d.core import NodePath

    from sejoga.render.renderizador import Panda3DRenderer

logger = logging.getLogger(__name__)

COR_FUNDO_NEUTRO: tuple[float, float, float, float] = (0.24, 0.25, 0.27, 1.0)
_COR_EIXO_X = (0.96, 0.34, 0.37, 1.0)
_COR_EIXO_Y = (0.31, 0.85, 0.49, 1.0)
_COR_EIXO_Z = (0.31, 0.63, 1.0, 1.0)
_PARES_ANCORAS_MAPA: tuple[tuple[str, str], ...] = (
    ("head", "head"),
    ("right-arm", "ombro_dir"),
    ("left-arm", "ombro_esq"),
    ("hand", "mao_dir"),
    ("hand2", "mao_esq"),
    ("left-feet", "pe_esq"),
    ("right-feet", "pe_dir"),
)


class ModoCamera(StrEnum):
    """Modos de câmera disponíveis na barra do viewport."""

    PERSPECTIVA = "perspectiva"
    FRONTAL = "frontal"
    LATERAL = "lateral"
    COMPANION = "companion"


class ModoFerramenta(StrEnum):
    """Ferramenta de manipulação 3D ativa no viewport."""

    GIRAR = "girar"
    MOVER = "mover"


@dataclass(frozen=True, slots=True)
class EstadoAlvoMover:
    """Descreve o alvo 3D editável quando ``ModoFerramenta.MOVER`` está ativo."""

    tipo: str = ""
    rotulo: str = ""
    valor_atual: tuple[float, float, float] = (0.0, 0.0, 0.0)
    ancora_vfx: str = "cabeca"
    grupo: str = ""
    modo_ik: str = ""
    juntas_afetadas: tuple[str, ...] = ()


@dataclass(slots=True)
class _EstadoDragMembro:
    """Snapshot capturado no início do arraste IK/mira para cálculo sem deriva."""

    alvo: EstadoAlvoMover
    handle_world_0: tuple[float, float, float]
    effector_world_0: tuple[float, float, float]
    pose_inicial_deg: dict[str, tuple[float, float, float]]
    polo_braco_alvo: tuple[float, float, float] | None = None
    pernas_inicial_lado: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    mira_piv_world: tuple[float, float, float] = (0.0, 0.0, 0.0)
    mira_v0_pai: tuple[float, float, float] = (0.0, -1.0, 0.0)
    mira_q0_pai: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)


_ALCA_FILHO_MIRA: dict[str, str] = {
    "right-arm": "ant-arm",
    "ant-arm": "hand",
    "left-arm": "ant-arm2",
    "ant-arm2": "hand2",
    "coxa-direita": "joelho-direito",
    "coxa-esquerda": "joelho-esquerdo",
    "abdomen": "peitoral",
    "peitoral": "head",
}


def _arm_effector_e_polo(
    render: Any,
    rig_nodes: dict[str, Any],
    g_braco: str,
    g_ant: str,
    g_mao: str,
    lado: str,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    from panda3d.core import Vec3

    ombro = rig_nodes.get(g_braco)
    cotovelo = rig_nodes.get(g_ant)
    mao = rig_nodes.get(g_mao)
    if ombro is None or cotovelo is None or mao is None:
        return (0.0, 0.0, 0.0), POLO_COTOVELO_ANATOMICO
    p_m = mao.getPos(render)
    eff = (float(p_m.x), float(p_m.y), float(p_m.z))
    pai = ombro.getParent()
    p_o = ombro.getPos(render)
    p_c = cotovelo.getPos(render)
    v_om = pai.getRelativeVector(render, p_m - p_o)
    v_oc = pai.getRelativeVector(render, p_c - p_o)
    len2 = v_om.lengthSquared()
    proj = (v_om * (v_oc.dot(v_om) / len2)) if len2 > 1e-8 else Vec3(0, 0, 0)
    v_polo = v_oc - proj
    if v_polo.length() < 0.04:
        return eff, POLO_COTOVELO_ANATOMICO
    v_polo.normalize()
    px, py, pz = cin.autoria_para_alvo((float(v_polo.x), float(v_polo.y), float(v_polo.z)))
    if lado == "left":
        px = -px
    return eff, (px, py, pz)


def _resolver_ik_braco_panda(
    model: Any,
    render: Any,
    rig_nodes: dict[str, Any],
    lado: str,
    p_alvo_eff: tuple[float, float, float],
    polo_t: tuple[float, float, float],
) -> dict[str, tuple[float, float, float]]:
    from panda3d.core import Vec3

    g_braco = "right-arm" if lado == "right" else "left-arm"
    ombro = rig_nodes.get(g_braco)
    if ombro is None:
        return {}
    pai = ombro.getParent()
    p_o = ombro.getPos(render)
    v_rel = pai.getRelativeVector(render, Vec3(*p_alvo_eff) - p_o)
    alvo_t = cin.autoria_para_alvo((float(v_rel.x), float(v_rel.y), float(v_rel.z)))
    rots = ik_bracos.braco_para(model, lado, alvo_t, polo=polo_t)
    return {
        grp: (
            round(math.degrees(rot.x), 4),
            round(math.degrees(rot.y), 4),
            round(math.degrees(rot.z), 4),
        )
        for grp, rot in rots.items()
    }


def _render_para_leg_base(
    lower_body: Any,
    model_np: Any,
    render: Any,
    p_world: tuple[float, float, float],
) -> tuple[float, float, float]:
    from panda3d.core import Mat4, Point3

    p_model = model_np.getRelativePoint(render, Point3(*p_world))
    mov = Mat4(lower_body._quadril_repouso_inverso * lower_body._quadril.getMat(model_np))
    mov.invertInPlace()
    p_loc = mov.xformPoint(p_model)
    return (float(p_loc.x), float(p_loc.y), float(p_loc.z))


def _quat_para_mira_euler(
    v0_pai: tuple[float, float, float],
    v1_pai: Any,
    q0_pai: tuple[float, float, float, float],
    base_hpr: tuple[float, float, float],
    extra_hpr: tuple[float, float, float],
    pose0_deg: tuple[float, float, float],
) -> tuple[float, float, float]:
    from panda3d.core import NodePath, Quat, Vec3

    u0 = Vec3(*v0_pai)
    u1 = Vec3(v1_pai)
    if u0.lengthSquared() < 1e-8 or u1.lengthSquared() < 1e-8:
        return pose0_deg
    u0.normalize()
    u1.normalize()
    dot = max(-1.0, min(1.0, float(u0.dot(u1))))
    q_swing = Quat()
    if dot < -0.9999:
        orto = Vec3(1, 0, 0) if abs(u0.x) < 0.9 else Vec3(0, 1, 0)
        ax = u0.cross(orto)
        ax.normalize()
        q_swing.setFromAxisAngleRad(math.pi, ax)
    elif dot < 0.999999:
        ax = u0.cross(u1)
        if ax.lengthSquared() > 1e-12:
            ax.normalize()
            q_swing.setFromAxisAngleRad(math.acos(dot), ax)
    q_new = Quat(*q0_pai) * q_swing
    tmp = NodePath("editor-mira-tmp")
    tmp.setQuat(q_new)
    h, p, r = tmp.getHpr()
    alvo = (
        float(p) - (base_hpr[1] + extra_hpr[1]),
        float(h) - (base_hpr[0] + extra_hpr[0]),
        float(r) - (base_hpr[2] + extra_hpr[2]),
    )
    dx, dy, dz = delta_euler_curto(alvo, pose0_deg)
    return (
        round(pose0_deg[0] + dx, 4),
        round(pose0_deg[1] + dy, 4),
        round(pose0_deg[2] + dz, 4),
    )


@dataclass(frozen=True, slots=True)
class EstadoOverlays:
    """Visibilidade das sobreposições opcionais no viewport 3D."""

    grade: bool = True
    ossos: bool = False
    contatos: bool = False
    ancoras: bool = False
    trilhas: bool = False
    comparar_salvo: bool = False


@dataclass(slots=True)
class EstadoCamera:
    """Parâmetros orbitais/ortográficos da câmera do editor."""

    modo: ModoCamera = ModoCamera.PERSPECTIVA
    yaw_graus: float = -24.0
    pitch_graus: float = 12.0
    distancia: float = 22.5
    zoom_ortho: float = 1.0
    alvo: tuple[float, float, float] = (0.0, 0.0, -0.56)
    lado_lateral_sinal: float = 1.0

    def orbitar(self, dx_ndc: float, dy_ndc: float) -> None:
        """Orbita a câmera ao redor do alvo a partir de delta normalizado."""
        if self.modo != ModoCamera.PERSPECTIVA:
            self.modo = ModoCamera.PERSPECTIVA
        self.yaw_graus = (self.yaw_graus - dx_ndc * 140.0) % 360.0
        self.pitch_graus = max(-78.0, min(78.0, self.pitch_graus - dy_ndc * 110.0))

    def pan(self, dx_ndc: float, dy_ndc: float) -> None:
        """Desloca o alvo perpendicularmente à direção de visão."""
        yaw_rad = math.radians(self.yaw_graus)
        escala = (
            self.distancia * 0.45
            if self.modo == ModoCamera.PERSPECTIVA
            else 6.0 / max(0.25, self.zoom_ortho)
        )
        rx, ry = math.cos(yaw_rad), math.sin(yaw_rad)
        tx, ty, tz = self.alvo
        self.alvo = (
            tx - rx * dx_ndc * escala,
            ty - ry * dx_ndc * escala,
            tz - dy_ndc * escala,
        )

    def zoom(self, passos: float) -> None:
        """Aproxima (``passos > 0``) ou afasta (``passos < 0``)."""
        fator = 0.88**passos
        if self.modo == ModoCamera.PERSPECTIVA:
            self.distancia = max(3.5, min(48.0, self.distancia * fator))
        else:
            self.zoom_ortho = max(0.35, min(6.0, self.zoom_ortho / fator))

    def enquadrar(self, centro: tuple[float, float, float]) -> None:
        """Centraliza e restaura a distância padrão ao redor de ``centro``."""
        self.alvo = centro
        self.distancia = 22.5
        self.zoom_ortho = 1.0
        if self.modo == ModoCamera.PERSPECTIVA:
            self.yaw_graus = -24.0
            self.pitch_graus = 12.0


_ESPEC_EIXOS_MUNDO: dict[str, tuple[float, float, float]] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}
_CORES_EIXOS: dict[str, tuple[float, float, float, float]] = {
    "x": _COR_EIXO_X,
    "y": _COR_EIXO_Y,
    "z": _COR_EIXO_Z,
}
# Convencao de Panda3D HPR usada por apply_rig_pose: (H=y->+Z, P=x->+X_H, R=z->+Y_node)
_ESPEC_ANEL_ROTACAO: dict[
    str, tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
] = {
    "x": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "y": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "z": ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
}


def _dist_e_frac_segmento_2d(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    aspect: float = 1.0,
) -> tuple[float, float]:
    ax, ay = a[0] * aspect, a[1]
    bx, by = b[0] * aspect, b[1]
    px, py = p[0] * aspect, p[1]
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    c2 = vx * vx + vy * vy
    t = 0.0 if c2 <= 1e-8 else max(0.0, min(1.0, (wx * vx + wy * vy) / c2))
    cx, cy = ax + t * vx, ay + t * vy
    return math.hypot(px - cx, py - cy), t


def _dist_ponto_segmento_2d(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    aspect: float = 1.0,
) -> float:
    return _dist_e_frac_segmento_2d(p, a, b, aspect)[0]


def _construir_circulo_gizmo(
    nome: str, eixo: str, raio: float, cor: tuple[float, float, float, float]
) -> NodePath:
    from panda3d.core import LineSegs, NodePath

    _, u_vec, v_vec = _ESPEC_ANEL_ROTACAO[eixo]
    segs = LineSegs(nome)
    segs.setThickness(3.4)
    segs.setColor(*cor)
    n_pts = 40
    for i in range(n_pts + 1):
        ang = math.tau * (i / n_pts)
        c, s = math.cos(ang) * raio, math.sin(ang) * raio
        pt = (
            u_vec[0] * c + v_vec[0] * s,
            u_vec[1] * c + v_vec[1] * s,
            u_vec[2] * c + v_vec[2] * s,
        )
        (segs.moveTo if i == 0 else segs.drawTo)(*pt)
    return NodePath(segs.create())


def _construir_seta_gizmo(
    nome: str,
    eixo: str,
    comprimento: float,
    cor: tuple[float, float, float, float],
) -> NodePath:
    from panda3d.core import LineSegs, NodePath, Vec3

    d = Vec3(*_ESPEC_EIXOS_MUNDO[eixo])
    ref = Vec3(0.0, 0.0, 1.0) if abs(d.z) < 0.9 else Vec3(1.0, 0.0, 0.0)
    u = d.cross(ref)
    u.normalize()
    v = d.cross(u)
    segs = LineSegs(nome)
    segs.setThickness(3.4)
    segs.setColor(*cor)
    base = d * (comprimento - 0.24)
    ponta = d * (comprimento + 0.16)
    segs.moveTo(0.0, 0.0, 0.0)
    segs.drawTo(ponta)
    anel = (
        base + u * 0.085,
        base + v * 0.085,
        base - u * 0.085,
        base - v * 0.085,
    )
    for i in range(4):
        segs.moveTo(anel[i])
        segs.drawTo(anel[(i + 1) % 4])
        segs.moveTo(anel[i])
        segs.drawTo(ponta)
    return NodePath(segs.create())


def _construir_origem_mover() -> NodePath:
    from panda3d.core import LineSegs, NodePath

    r = 0.11
    pts = ((r, 0, 0), (-r, 0, 0), (0, r, 0), (0, -r, 0), (0, 0, r), (0, 0, -r))
    segs = LineSegs("gizmo-mover-origem")
    segs.setThickness(2.2)
    segs.setColor(0.96, 0.96, 0.96, 0.95)
    for a, b in ((0, 2), (2, 1), (1, 3), (3, 0), (4, 0), (4, 2), (4, 1), (4, 3), (5, 0), (5, 2), (5, 1), (5, 3)):
        segs.moveTo(*pts[a])
        segs.drawTo(*pts[b])
    return NodePath(segs.create())


def _construir_caixa_arame(
    nome: str,
    centro: tuple[float, float, float],
    meia: tuple[float, float, float],
    cor: tuple[float, float, float, float],
) -> NodePath:
    from panda3d.core import LineSegs, NodePath

    cx, cy, cz = centro
    hx, hy, hz = meia
    cantos = [
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    ]
    arestas = (
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    )
    segs = LineSegs(nome)
    segs.setThickness(2.0)
    segs.setColor(*cor)
    for ia, ib in arestas:
        segs.moveTo(*cantos[ia])
        segs.drawTo(*cantos[ib])
    return NodePath(segs.create())


class _GizmoRotacao3D:
    """Manipulador visual X/Y/Z alinhado aos eixos intrínsecos de ``Rotation3``."""

    RAIO = 1.15

    def __init__(self, parent: NodePath) -> None:
        self._render_root = parent
        self.root = parent.attachNewNode("editor-gizmo-root")
        self.root.setBin("fixed", 42)
        self.root.setDepthTest(False)
        self.root.setDepthWrite(False)
        self.root.setLightOff(1)
        self.aneis = {
            e: _construir_circulo_gizmo(f"gizmo-{e}", e, self.RAIO, _CORES_EIXOS[e])
            for e in ("x", "y", "z")
        }
        for anel in self.aneis.values():
            anel.reparentTo(self.root)
        self.root.hide()

    def sincronizar(
        self,
        renderer: Panda3DRenderer,
        grupo: str | None,
        euler_deg: tuple[float, float, float],
        eixo_destacado: str | None = None,
        *,
        visivel: bool = True,
    ) -> None:
        """Posiciona os anéis no pivô de ``grupo`` com as orientações reais do HPR."""
        node = renderer._rig_nodes.get(grupo) if (visivel and grupo) else None
        if node is None or node.isEmpty():
            self.root.hide()
            return
        from panda3d.core import Quat

        self.root.show()
        self.root.setPos(node.getPos(self._render_root))
        self.root.setQuat(Quat.identQuat())
        quats = self._quaternions_eixos(renderer, str(grupo), node, euler_deg, Quat)
        for nome, anel in self.aneis.items():
            anel.setQuat(quats[nome])
            destaque = nome == eixo_destacado
            anel.setColorScale(*((1.4, 1.4, 1.4, 1.0) if destaque else (1.0, 1.0, 1.0, 0.85)))
            anel.setScale(1.06 if destaque else 1.0)

    def _quaternions_eixos(
        self,
        renderer: Panda3DRenderer,
        grupo: str,
        node: NodePath,
        euler_deg: tuple[float, float, float],
        quat_cls: Any,
    ) -> dict[str, Any]:
        parent = node.getParent()
        pq_w = (
            parent.getQuat(self._render_root)
            if not parent.isEmpty()
            else quat_cls.identQuat()
        )
        base_h = float(renderer._rig_base_hpr.get(grupo, (0.0, 0.0, 0.0))[0])
        extra_h = float(BASE_ADICIONAL_GRAUS.get(grupo, (0.0, 0.0, 0.0))[0])
        qh = quat_cls()
        qh.setHpr((base_h + extra_h + euler_deg[1], 0.0, 0.0))
        return {
            "x": qh * pq_w,
            "y": quat_cls(pq_w),
            "z": node.getQuat(self._render_root),
        }

    def escolher_eixo(
        self, cam: NodePath, mpos_ndc: tuple[float, float], aspect: float = 1.0
    ) -> tuple[str, tuple[float, float]] | None:
        """Retorna ``(eixo, tangente_aspect)`` se o ponteiro tocar um anel."""
        if self.root.isHidden():
            return None
        lens = cam.node().getLens()
        melhor: tuple[float, float, str, tuple[float, float, float]] | None = None
        for eixo in ("x", "y", "z"):
            amostras = self._projetar_anel(eixo, lens, cam, 36)
            melhor = self._melhor_segmento(eixo, amostras, mpos_ndc, aspect, melhor)
        if melhor is None:
            return None
        _, _, eixo_sel, pt_local = melhor
        tang = self._tangente_drag(eixo_sel, pt_local, lens, cam, aspect)
        return eixo_sel, tang

    @staticmethod
    def _melhor_segmento(
        eixo: str,
        amostras: list[tuple[float, float, float, tuple[float, float, float]]],
        mpos_ndc: tuple[float, float],
        aspect: float,
        melhor: tuple[float, float, str, tuple[float, float, float]] | None,
    ) -> tuple[float, float, str, tuple[float, float, float]] | None:
        for i in range(len(amostras) - 1):
            a, b = amostras[i], amostras[i + 1]
            d, frac = _dist_e_frac_segmento_2d(
                mpos_ndc, (a[0], a[1]), (b[0], b[1]), aspect
            )
            if d > 0.065:
                continue
            cam_y = a[2] + frac * (b[2] - a[2])
            mais_proximo = (
                melhor is None
                or d < melhor[0] - 0.012
                or (abs(d - melhor[0]) <= 0.012 and cam_y < melhor[1])
            )
            if mais_proximo:
                pa, pb = a[3], b[3]
                loc = (
                    pa[0] + frac * (pb[0] - pa[0]),
                    pa[1] + frac * (pb[1] - pa[1]),
                    pa[2] + frac * (pb[2] - pa[2]),
                )
                melhor = (d, cam_y, eixo, loc)
        return melhor

    def _projetar_anel(
        self, eixo: str, lens: Any, cam: NodePath, n_amostras: int
    ) -> list[tuple[float, float, float, tuple[float, float, float]]]:
        from panda3d.core import Point2, Point3

        _, u_vec, v_vec = _ESPEC_ANEL_ROTACAO[eixo]
        anel = self.aneis[eixo]
        amostras: list[tuple[float, float, float, tuple[float, float, float]]] = []
        p2d = Point2()
        for i in range(n_amostras + 1):
            ang = math.tau * (i / n_amostras)
            c, s = math.cos(ang) * self.RAIO, math.sin(ang) * self.RAIO
            lx = u_vec[0] * c + v_vec[0] * s
            ly = u_vec[1] * c + v_vec[1] * s
            lz = u_vec[2] * c + v_vec[2] * s
            p_cam = cam.getRelativePoint(anel, Point3(lx, ly, lz))
            if lens.project(p_cam, p2d):
                amostras.append((float(p2d.x), float(p2d.y), float(p_cam.y), (lx, ly, lz)))
        return amostras

    def _tangente_drag(
        self,
        eixo: str,
        pt_local: tuple[float, float, float],
        lens: Any,
        cam: NodePath,
        aspect: float,
    ) -> tuple[float, float]:
        from panda3d.core import Point2, Vec3

        ax_loc = _ESPEC_ANEL_ROTACAO[eixo][0]
        q_w = self.aneis[eixo].getQuat(self._render_root)
        ax_w = q_w.xform(Vec3(*ax_loc))
        r_w = q_w.xform(Vec3(*pt_local))
        t_w = ax_w.cross(r_w)
        piv_w = self.root.getPos(self._render_root)
        p_hit_w = piv_w + r_w
        p1, p2 = Point2(), Point2()
        c1 = cam.getRelativePoint(self._render_root, p_hit_w)
        c2 = cam.getRelativePoint(self._render_root, p_hit_w + t_w * 0.05)
        vx, vy = 0.0, 0.0
        if lens.project(c1, p1) and lens.project(c2, p2):
            vx, vy = (float(p2.x) - float(p1.x)) * aspect, float(p2.y) - float(p1.y)
        if math.hypot(vx, vy) < 1e-4:
            view_dir = cam.getPos(self._render_root) - piv_w
            view_dir.normalize()
            t_fb = ax_w.cross(view_dir)
            c2_fb = cam.getRelativePoint(self._render_root, p_hit_w + t_fb * 0.05)
            if lens.project(c1, p1) and lens.project(c2_fb, p2):
                vx, vy = (float(p2.x) - float(p1.x)) * aspect, float(p2.y) - float(p1.y)
        norm = math.hypot(vx, vy)
        if norm <= 1e-5:
            return (1.0, 0.0)
        return (vx / norm, vy / norm)


class _GizmoMovimento3D:
    """Manipulador visual X/Y/Z com setas para transladar alvos no espaço 3D."""

    COMPRIMENTO = 1.35

    def __init__(self, parent: NodePath) -> None:
        self._render_root = parent
        self.root = parent.attachNewNode("editor-gizmo-mover-root")
        self.root.setBin("fixed", 43)
        self.root.setDepthTest(False)
        self.root.setDepthWrite(False)
        self.root.setLightOff(1)
        self._origem = _construir_origem_mover()
        self._origem.reparentTo(self.root)
        self.setas = {
            e: _construir_seta_gizmo(f"mover-{e}", e, self.COMPRIMENTO, _CORES_EIXOS[e])
            for e in ("x", "y", "z")
        }
        for seta in self.setas.values():
            seta.reparentTo(self.root)
        self.root.hide()

    def sincronizar(
        self,
        pos_world: tuple[float, float, float] | None,
        eixo_destacado: str | None = None,
        *,
        visivel: bool = True,
    ) -> None:
        """Posiciona as setas X/Y/Z em ``pos_world`` alinhadas ao mundo."""
        if not visivel or pos_world is None:
            self.root.hide()
            return
        from panda3d.core import Quat

        self.root.show()
        self.root.setPos(*pos_world)
        self.root.setQuat(Quat.identQuat())
        for nome, seta in self.setas.items():
            destaque = nome == eixo_destacado
            seta.setColorScale(*((1.4, 1.4, 1.4, 1.0) if destaque else (1.0, 1.0, 1.0, 0.88)))
            seta.setScale(1.08 if destaque else 1.0)

    def escolher_eixo(
        self, cam: NodePath, mpos_ndc: tuple[float, float], aspect: float = 1.0
    ) -> tuple[str, tuple[float, float]] | None:
        """Retorna ``(eixo, jacobiana_aspect)`` se o ponteiro tocar uma seta."""
        from panda3d.core import Point2, Vec3

        if self.root.isHidden():
            return None
        lens = cam.node().getLens()
        piv = self.root.getPos(self._render_root)
        p0_c = cam.getRelativePoint(self._render_root, piv)
        p0_2d = Point2()
        if not lens.project(p0_c, p0_2d):
            return None
        melhor: tuple[float, float, str, tuple[float, float]] | None = None
        for eixo, dir_t in _ESPEC_EIXOS_MUNDO.items():
            cand = self._avaliar_seta(
                eixo, piv, p0_c, p0_2d, Vec3(*dir_t), cam, lens, mpos_ndc, aspect
            )
            if cand is None:
                continue
            d, cam_y, jac = cand
            if melhor is None or d < melhor[0] - 0.012 or (abs(d - melhor[0]) <= 0.012 and cam_y < melhor[1]):
                melhor = (d, cam_y, eixo, jac)
        return (melhor[2], melhor[3]) if melhor is not None else None

    def _avaliar_seta(
        self,
        eixo: str,
        piv: Any,
        p0_c: Any,
        p0_2d: Any,
        d_vec: Any,
        cam: NodePath,
        lens: Any,
        mpos_ndc: tuple[float, float],
        aspect: float,
    ) -> tuple[float, float, tuple[float, float]] | None:
        from panda3d.core import Point2

        p1_c = cam.getRelativePoint(self._render_root, piv + d_vec * self.COMPRIMENTO)
        p1_2d = Point2()
        if not lens.project(p1_c, p1_2d):
            return None
        if math.hypot((p1_2d.x - p0_2d.x) * aspect, p1_2d.y - p0_2d.y) < 0.025:
            return None
        d, frac = _dist_e_frac_segmento_2d(
            mpos_ndc, (float(p0_2d.x), float(p0_2d.y)), (float(p1_2d.x), float(p1_2d.y)), aspect
        )
        if d > 0.070:
            return None
        cam_y = float(p0_c.y) + frac * (float(p1_c.y) - float(p0_c.y))
        pe_c = cam.getRelativePoint(self._render_root, piv + d_vec * 0.25)
        pe_2d = Point2()
        if not lens.project(pe_c, pe_2d):
            return None
        jac = (
            (float(pe_2d.x) - float(p0_2d.x)) / 0.25 * aspect,
            (float(pe_2d.y) - float(p0_2d.y)) / 0.25,
        )
        return d, cam_y, jac


class _Overlays3D:
    """Camadas visuais opcionais (grade, ossos, contatos, âncoras, trilhas, fantasma)."""

    def __init__(self, renderer: Panda3DRenderer) -> None:
        self.renderer = renderer
        self.render = renderer.showbase.render
        self.root = self.render.attachNewNode("editor-overlays")
        self.root.setLightOff(1)
        self._node_grade = self._criar_grade()
        self._node_grade.reparentTo(self.root)
        self._node_ossos: NodePath | None = None
        self._node_contatos: NodePath | None = None
        self._node_ancoras: NodePath | None = None
        self._node_trilhas: NodePath | None = None
        self._ghost_root: NodePath | None = None
        self._ghost_nodes: dict[str, NodePath] = {}
        self._floor_offset_z = self._medir_floor_offset()
        self._preparar_fantasma()

    def _medir_floor_offset(self) -> float:
        anchor = self.renderer.model_anchor
        model_np = self.renderer.model_np
        if anchor is not None and model_np is not None:
            bounds = model_np.getTightBounds(self.render)
            if bounds:
                return float(bounds[0].z) - float(anchor.getZ())
        return -1.74

    def _criar_grade(self) -> NodePath:
        from panda3d.core import LineSegs, NodePath

        segs = LineSegs("overlay-grade")
        segs.setThickness(1.0)
        for i in range(-8, 9):
            coord = float(i)
            cor = (0.42, 0.45, 0.50, 0.85) if i == 0 else (0.31, 0.33, 0.36, 0.55)
            segs.setColor(*cor)
            segs.moveTo(coord, -8.0, 0.0)
            segs.drawTo(coord, 8.0, 0.0)
            segs.moveTo(-8.0, coord, 0.0)
            segs.drawTo(8.0, coord, 0.0)
        return NodePath(segs.create())

    def _preparar_fantasma(self) -> None:
        from panda3d.core import TransparencyAttrib

        model_np = self.renderer.model_np
        anchor = self.renderer.model_anchor
        if model_np is None or anchor is None:
            return
        ghost = model_np.copyTo(anchor)
        ghost.setName("editor-ghost-salvo")
        ghost.setScale(model_np.getScale())
        ghost.setPos(model_np.getPos())
        ghost.setTransparency(TransparencyAttrib.MAlpha, 1)
        ghost.setColorScale(0.35, 0.72, 1.0, 0.40)
        ghost.setCollideMask(0)
        ghost.hide()
        self._ghost_root = ghost
        for grupo in ALL_GROUPS:
            no = ghost.find(f"**/{grupo}")
            if not no.isEmpty():
                self._ghost_nodes[grupo] = no

    def atualizar(
        self,
        overlays: EstadoOverlays,
        junta_selecionada: str | None,
        obstaculo: ObstaculoPrevia,
        quadro: QuadroPrevia,
        quadro_salvo: QuadroPrevia | None,
        trilhas_pts: tuple[
            list[tuple[float, float, float]], list[tuple[float, float, float]]
        ]
        | None,
        guia_vfx: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None,
    ) -> None:
        """Sincroniza nós visuais dos overlays conforme bandeiras ativas."""
        (self._node_grade.show if overlays.grade else self._node_grade.hide)()
        if self.renderer.model_anchor is not None:
            self._node_grade.setZ(self.renderer.model_anchor.getZ() + self._floor_offset_z)
        self._atualizar_ossos(overlays.ossos, junta_selecionada)
        self._atualizar_contatos(overlays.contatos, obstaculo, quadro)
        self._atualizar_ancoras(overlays.ancoras, guia_vfx)
        self._atualizar_trilhas(overlays.trilhas, trilhas_pts)
        self._atualizar_fantasma(overlays.comparar_salvo, quadro_salvo)

    def _atualizar_ossos(self, ativo: bool, junta_selecionada: str | None) -> None:
        from panda3d.core import LineSegs

        if self._node_ossos is not None:
            self._node_ossos.removeNode()
            self._node_ossos = None
        if not ativo:
            return
        segs = LineSegs("overlay-ossos")
        segs.setThickness(2.0)
        for nome, node in self.renderer._rig_nodes.items():
            pai = node.getParent()
            if pai.isEmpty() or pai == self.renderer.model_np:
                continue
            segs.setColor(*(_COR_EIXO_Z if nome == junta_selecionada else (0.92, 0.84, 0.42, 0.85)))
            segs.moveTo(pai.getPos(self.render))
            segs.drawTo(node.getPos(self.render))
        self._node_ossos = self.root.attachNewNode(segs.create())
        self._node_ossos.setBin("fixed", 30)
        self._node_ossos.setDepthTest(False)

    def _atualizar_contatos(
        self, ativo: bool, obstaculo: ObstaculoPrevia, quadro: QuadroPrevia
    ) -> None:
        from panda3d.core import LineSegs

        if self._node_contatos is not None:
            self._node_contatos.removeNode()
            self._node_contatos = None
        if not ativo:
            return
        grupo_np = self.root.attachNewNode("overlay-contatos")
        if obstaculo.ativo:
            cor = (
                (1.0, 0.42, 0.25, 0.95)
                if quadro.contatos_obstaculo
                else (0.35, 0.90, 0.62, 0.85)
            )
            _construir_caixa_arame(
                "obstaculo-aabb", obstaculo.centro, obstaculo.meia_extensao, cor
            ).reparentTo(grupo_np)
        segs = LineSegs("contatos-marcas")
        segs.setThickness(3.0)
        segs.setColor(1.0, 0.35, 0.25, 1.0)
        for cx, cy, cz in quadro.contatos_obstaculo:
            r = 0.25
            segs.moveTo(cx - r, cy, cz)
            segs.drawTo(cx + r, cy, cz)
            segs.moveTo(cx, cy, cz - r)
            segs.drawTo(cx, cy, cz + r)
        grupo_np.attachNewNode(segs.create())
        grupo_np.setBin("fixed", 31)
        grupo_np.setDepthTest(False)
        self._node_contatos = grupo_np

    def _atualizar_ancoras(
        self,
        ativo: bool,
        guia_vfx: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None,
    ) -> None:
        from panda3d.core import LineSegs

        if self._node_ancoras is not None:
            self._node_ancoras.removeNode()
            self._node_ancoras = None
        if not ativo and guia_vfx is None:
            return
        segs = LineSegs("overlay-ancoras")
        segs.setThickness(2.2)
        if ativo:
            segs.setColor(1.0, 0.56, 0.86, 0.95)
            for grupo, _rotulo in _PARES_ANCORAS_MAPA:
                node = self.renderer._rig_nodes.get(grupo)
                if node is None:
                    continue
                p = node.getPos(self.render)
                self._desenhar_cruz_3d(segs, (p.x, p.y, p.z), 0.25)
        if guia_vfx is not None:
            anc_p, dst_p = guia_vfx
            segs.setColor(1.0, 0.72, 0.28, 0.95)
            self._desenhar_cruz_3d(segs, anc_p, 0.22)
            segs.moveTo(*anc_p)
            segs.drawTo(*dst_p)
        self._node_ancoras = self.root.attachNewNode(segs.create())
        self._node_ancoras.setBin("fixed", 32)
        self._node_ancoras.setDepthTest(False)

    @staticmethod
    def _desenhar_cruz_3d(segs: Any, p: tuple[float, float, float], r: float) -> None:
        x, y, z = p
        segs.moveTo(x - r, y, z)
        segs.drawTo(x + r, y, z)
        segs.moveTo(x, y, z - r)
        segs.drawTo(x, y, z + r)
        segs.moveTo(x, y - r, z)
        segs.drawTo(x, y + r, z)

    def _atualizar_trilhas(
        self,
        ativo: bool,
        trilhas_pts: tuple[
            list[tuple[float, float, float]], list[tuple[float, float, float]]
        ]
        | None,
    ) -> None:
        from panda3d.core import LineSegs, Point3

        if self._node_trilhas is not None:
            self._node_trilhas.removeNode()
            self._node_trilhas = None
        if not ativo or trilhas_pts is None or self.renderer.model_np is None:
            return
        model_np = self.renderer.model_np
        base_np = model_np.getChild(0) if model_np.getNumChildren() > 0 else model_np
        segs = LineSegs("overlay-trilhas")
        segs.setThickness(2.4)
        for pts, cor in (
            (trilhas_pts[0], (0.28, 0.85, 1.0, 0.85)),
            (trilhas_pts[1], (1.0, 0.68, 0.22, 0.95)),
        ):
            if len(pts) < 2:
                continue
            segs.setColor(*cor)
            for idx, (x, y, z) in enumerate(pts):
                w = self.render.getRelativePoint(base_np, Point3(x, y, z))
                (segs.moveTo if idx == 0 else segs.drawTo)(w)
        self._node_trilhas = self.root.attachNewNode(segs.create())

    def _atualizar_fantasma(
        self, ativo: bool, quadro_salvo: QuadroPrevia | None
    ) -> None:
        if self._ghost_root is None:
            return
        if not ativo or quadro_salvo is None:
            self._ghost_root.hide()
            return
        self._ghost_root.show()
        base_hpr = self.renderer._rig_base_hpr
        for grupo, rot in quadro_salvo.pose.items():
            node = self._ghost_nodes.get(grupo)
            if node is None:
                continue
            bh, bp, br = base_hpr.get(grupo, (0.0, 0.0, 0.0))
            node.setHpr(
                bh + math.degrees(rot.y),
                bp + math.degrees(rot.x),
                br + math.degrees(rot.z),
            )


class PandaViewportSession:
    """Sessão gráfica Panda3D do editor (suporta HWND Qt filho ou offscreen)."""

    def __init__(
        self,
        parent_hwnd: int,
        width: int,
        height: int,
        *,
        on_joint_selected: Callable[[str], None] | None = None,
        on_gizmo_start: Callable[[str, str], None] | None = None,
        on_gizmo_update: Callable[[str, tuple[float, float, float]], None] | None = None,
        on_gizmo_commit: Callable[[str, tuple[float, float, float]], None] | None = None,
        on_gizmo_cancel: Callable[[], None] | None = None,
        on_mover_start: Callable[[str, str], None] | None = None,
        on_mover_update: Callable[[str, Any], None] | None = None,
        on_mover_commit: Callable[[str, Any], None] | None = None,
        on_mover_cancel: Callable[[], None] | None = None,
    ) -> None:
        """Cria ShowBase, SimplePBR neutro, gizmos de rotação/movimento e picking."""
        self._inicializar_estado(
            on_joint_selected=on_joint_selected,
            on_gizmo_start=on_gizmo_start,
            on_gizmo_update=on_gizmo_update,
            on_gizmo_commit=on_gizmo_commit,
            on_gizmo_cancel=on_gizmo_cancel,
            on_mover_start=on_mover_start,
            on_mover_update=on_mover_update,
            on_mover_commit=on_mover_commit,
            on_mover_cancel=on_mover_cancel,
        )
        self.showbase = self._abrir_showbase(parent_hwnd, width, height)
        self.renderer = self._iniciar_renderer(parent_hwnd, width, height)
        self._alcas_locais_mira.update(self._medir_alcas_locais_mira())
        self._gizmo = _GizmoRotacao3D(self.showbase.render)
        self._gizmo_mover = _GizmoMovimento3D(self.showbase.render)
        self._overlays_3d = _Overlays3D(self.renderer)
        self._lado_direito_sinal = self._detectar_sinal_lateral()
        self.camera_estado.lado_lateral_sinal = self._lado_direito_sinal
        self._setup_editor_picking()
        self._bind_mouse_events()
        self.enquadrar()
        self.aplicar_camera()

    def _inicializar_estado(
        self,
        *,
        on_joint_selected: Callable[[str], None] | None,
        on_gizmo_start: Callable[[str, str], None] | None,
        on_gizmo_update: Callable[[str, tuple[float, float, float]], None] | None,
        on_gizmo_commit: Callable[[str, tuple[float, float, float]], None] | None,
        on_gizmo_cancel: Callable[[], None] | None,
        on_mover_start: Callable[[str, str], None] | None,
        on_mover_update: Callable[[str, Any], None] | None,
        on_mover_commit: Callable[[str, Any], None] | None,
        on_mover_cancel: Callable[[], None] | None,
    ) -> None:
        self._on_select = on_joint_selected
        self._on_gizmo_start = on_gizmo_start
        self._on_gizmo_update = on_gizmo_update
        self._on_gizmo_commit = on_gizmo_commit
        self._on_gizmo_cancel = on_gizmo_cancel
        self._on_mover_start = on_mover_start
        self._on_mover_update = on_mover_update
        self._on_mover_commit = on_mover_commit
        self._on_mover_cancel = on_mover_cancel
        self._inicializar_variaveis_sessao()

    def _inicializar_variaveis_sessao(self) -> None:
        self.camera_estado = EstadoCamera()
        self.overlays = EstadoOverlays()
        self.ferramenta = ModoFerramenta.GIRAR
        self._alvo_mover = EstadoAlvoMover()
        self.junta_selecionada: str | None = "right-arm"
        self._dados_rascunho: dict[str, Any] | None = None
        self._pose_atual: dict[str, Rotation3] = {}
        self._ultimo_quadro: QuadroPrevia | None = None
        self._ultimo_obstaculo: ObstaculoPrevia = ObstaculoPrevia()
        self._pose_euler_selecionada: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._mover_valor_atual: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._drag_modo: str | None = None
        self._drag_eixo: str | None = None
        self._hover_eixo: str | None = None
        self._drag_tangente: tuple[float, float] = (1.0, 0.0)
        self._drag_jacobiana: tuple[float, float] = (0.1, 0.0)
        self._drag_aspect: float = 1.0
        self._drag_inicio_mouse: tuple[float, float] = (0.0, 0.0)
        self._drag_inicio_euler: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._drag_inicio_mover: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._drag_membro: _EstadoDragMembro | None = None
        self._mover_poses_membro: dict[str, tuple[float, float, float]] = {}
        self._modelo_rig: Any = None
        self._alcas_locais_mira: dict[str, tuple[float, float, float]] = {}
        self._destroyed = False
        self._stepping = False

    def _abrir_showbase(self, parent_hwnd: int, width: int, height: int) -> Any:
        from panda3d.core import (
            FrameBufferProperties,
            WindowProperties,
            loadPrcFileData,
        )

        loadPrcFileData("", "window-type none")
        loadPrcFileData("", "sync-video false")
        loadPrcFileData("", "notify-level warning")
        from direct.showbase.ShowBase import ShowBase

        sb = ShowBase(windowType="none")
        sb.settings = Settings()
        wp = WindowProperties()
        wp.setSize(max(1, int(width)), max(1, int(height)))
        if parent_hwnd:
            wp.setParentWindow(int(parent_hwnd))
            wp.setOrigin(0, 0)
            wp.setUndecorated(True)
        fbprops = FrameBufferProperties()
        fbprops.setRgbColor(True)
        fbprops.setAlphaBits(8)
        fbprops.setDepthBits(24)
        fbprops.setStencilBits(8)
        fbprops.setMultisamples(4)
        sb.openDefaultWindow(
            props=wp, fbprops=fbprops, type="onscreen" if parent_hwnd else "offscreen"
        )
        if sb.win:
            sb.win.setClearColor(COR_FUNDO_NEUTRO)
            sb.win.setClearColorActive(True)
        sb.disableMouse()
        return sb

    def _iniciar_renderer(
        self, parent_hwnd: int, width: int, height: int
    ) -> Panda3DRenderer:
        from panda3d.core import Point3

        from sejoga.render.renderizador import Panda3DRenderer

        rend = Panda3DRenderer(
            self.showbase,
            int(parent_hwnd),
            max(1, int(width)),
            max(1, int(height)),
            use_chroma_resolve=False,
        )
        self._base_anchor_pos = (
            Point3(rend.model_anchor.getPos())
            if rend.model_anchor is not None
            else Point3(0, 0, 0)
        )
        return rend

    def _detectar_sinal_lateral(self) -> float:
        r_arm = self.renderer._rig_nodes.get("right-arm")
        if r_arm is None or self.renderer.model_anchor is None:
            return 1.0
        p = r_arm.getPos(self.showbase.render).x - self.renderer.model_anchor.getPos(self.showbase.render).x
        return 1.0 if p >= 0.0 else -1.0

    def _setup_editor_picking(self) -> None:
        from panda3d.core import (
            BitMask32,
            CollisionHandlerQueue,
            CollisionNode,
            CollisionRay,
            CollisionTraverser,
        )

        self._ed_ray = CollisionRay()
        cnode = CollisionNode("editor-pick-ray")
        cnode.addSolid(self._ed_ray)
        cnode.setFromCollideMask(BitMask32.bit(1))
        cnode.setIntoCollideMask(BitMask32.allOff())
        ray_np = self.showbase.cam.attachNewNode(cnode)
        self._ed_queue = CollisionHandlerQueue()
        self._ed_traverser = CollisionTraverser("editor-picking")
        self._ed_traverser.addCollider(ray_np, self._ed_queue)

    def _bind_mouse_events(self) -> None:
        sb = self.showbase
        sb.accept("mouse1", self._on_mouse1_down)
        sb.accept("mouse1-up", self._on_mouse1_up)
        sb.accept("mouse2", self._on_orbit_down)
        sb.accept("mouse2-up", self._on_camera_up)
        sb.accept("mouse3", self._on_orbit_down)
        sb.accept("mouse3-up", self._on_camera_up)
        sb.accept("wheel_up", self._on_wheel, [1.0])
        sb.accept("wheel_down", self._on_wheel, [-1.0])
        sb.accept("escape", self.cancelar_drag_gizmo)

    def _mpos(self) -> tuple[float, float] | None:
        mw = self.showbase.mouseWatcherNode
        if mw is None or not mw.hasMouse():
            return None
        pt = mw.getMouse()
        return (float(pt.x), float(pt.y))

    def _aspect_viewport(self) -> float:
        return max(0.25, self.renderer.width / max(1, self.renderer.height))

    def _on_mouse1_down(self) -> None:
        mp = self._mpos()
        if mp is None:
            return
        mw = self.showbase.mouseWatcherNode
        if mw is not None and mw.isButtonDown("alt"):
            self._drag_modo = "pan"
            self._drag_inicio_mouse = mp
            return
        aspect = self._aspect_viewport()
        if self.ferramenta == ModoFerramenta.MOVER and self._alvo_mover.tipo:
            hit_mover = self._gizmo_mover.escolher_eixo(self.showbase.cam, mp, aspect)
            if hit_mover is not None:
                self._iniciar_drag_mover(hit_mover[0], hit_mover[1], mp, aspect)
                return
        else:
            hit_gizmo = self._gizmo.escolher_eixo(self.showbase.cam, mp, aspect)
            if hit_gizmo is not None and self.junta_selecionada is not None:
                self._iniciar_drag_gizmo(hit_gizmo[0], hit_gizmo[1], mp, aspect)
                return
        grupo = self._pick_junta(mp)
        if grupo is not None:
            self.definir_junta_selecionada(grupo)
            if self._on_select:
                self._on_select(grupo)

    def _iniciar_drag_gizmo(
        self,
        eixo: str,
        tangente: tuple[float, float],
        mp: tuple[float, float],
        aspect: float = 1.0,
    ) -> None:
        self._drag_modo = "gizmo"
        self._drag_eixo = eixo
        self._drag_tangente = tangente
        self._drag_aspect = aspect
        self._drag_inicio_mouse = mp
        self._drag_inicio_euler = self._pose_euler_selecionada
        self._sincronizar_gizmo()
        if self._on_gizmo_start and self.junta_selecionada:
            self._on_gizmo_start(self.junta_selecionada, eixo)

    def _iniciar_drag_mover(
        self,
        eixo: str,
        jacobiana: tuple[float, float],
        mp: tuple[float, float],
        aspect: float = 1.0,
    ) -> None:
        self._drag_modo = "mover_gizmo"
        self._drag_eixo = eixo
        self._drag_jacobiana = jacobiana
        self._drag_aspect = aspect
        self._drag_inicio_mouse = mp
        self._mover_valor_atual = self._alvo_mover.valor_atual
        self._drag_inicio_mover = self._alvo_mover.valor_atual
        if self._alvo_mover.tipo == "membro":
            self._drag_membro = self._capturar_drag_membro(self._alvo_mover)
            self._mover_poses_membro = (
                dict(self._drag_membro.pose_inicial_deg) if self._drag_membro else {}
            )
        else:
            self._drag_membro = None
            self._mover_poses_membro = {}
        self._sincronizar_gizmo()
        if self._on_mover_start and self._alvo_mover.tipo:
            self._on_mover_start(self._alvo_mover.tipo, eixo)

    def _on_mouse1_up(self) -> None:
        if self._drag_modo == "gizmo" and self.junta_selecionada and self._on_gizmo_commit:
            self._on_gizmo_commit(self.junta_selecionada, self._pose_euler_selecionada)
        elif (
            self._drag_modo == "mover_gizmo"
            and self._alvo_mover.tipo
            and self._on_mover_commit
        ):
            payload: Any = (
                dict(self._mover_poses_membro)
                if self._alvo_mover.tipo == "membro"
                else self._mover_valor_atual
            )
            self._on_mover_commit(self._alvo_mover.tipo, payload)
        self._drag_modo = None
        self._drag_eixo = None
        self._drag_membro = None
        self._sincronizar_gizmo()

    def _on_orbit_down(self) -> None:
        mp = self._mpos()
        if mp is None:
            return
        mw = self.showbase.mouseWatcherNode
        eh_shift = mw is not None and mw.isButtonDown("shift")
        self._drag_modo = "pan" if eh_shift else "orbit"
        self._drag_inicio_mouse = mp

    def _on_camera_up(self) -> None:
        if self._drag_modo in ("orbit", "pan"):
            self._drag_modo = None

    def _on_wheel(self, delta: float) -> None:
        self.camera_estado.zoom(delta)
        self.aplicar_camera()

    def cancelar_drag_gizmo(self) -> bool:
        """Cancela arraste ativo restaurando rotação ou posição anterior."""
        modo = self._drag_modo
        if modo == "gizmo":
            self._drag_modo = None
            self._drag_eixo = None
            self._pose_euler_selecionada = self._drag_inicio_euler
            self._sincronizar_gizmo()
            if self._on_gizmo_cancel:
                self._on_gizmo_cancel()
            return True
        if modo == "mover_gizmo":
            self._drag_modo = None
            self._drag_eixo = None
            self._drag_membro = None
            self._mover_poses_membro = {}
            self._mover_valor_atual = self._drag_inicio_mover
            self._sincronizar_gizmo()
            if self._on_mover_cancel:
                self._on_mover_cancel()
            return True
        return False

    def _pick_junta(self, mp: tuple[float, float]) -> str | None:
        if self.renderer.model_np is None:
            return None
        self._ed_ray.setFromLens(self.showbase.cam.node(), mp[0], mp[1])
        self._ed_queue.clearEntries()
        self._ed_traverser.traverse(self.renderer.model_np)
        if not self._ed_queue.getNumEntries():
            return None
        self._ed_queue.sortEntries()
        no = self._ed_queue.getEntry(0).getIntoNodePath()
        while not no.isEmpty() and no != self.renderer.model_np:
            nome = no.getName()
            if nome in ALL_GROUPS:
                return str(nome)
            no = no.getParent()
        return None

    def resize(self, width: int, height: int) -> None:
        """Atualiza tamanho da janela nativa e proporção da lente."""
        from panda3d.core import WindowProperties

        if self._destroyed or not self.showbase.win:
            return
        w, h = max(1, int(width)), max(1, int(height))
        wp = WindowProperties()
        wp.setOrigin(0, 0)
        wp.setSize(w, h)
        self.showbase.win.requestProperties(wp)
        self.renderer.resize(w, h)
        self.aplicar_camera()

    def definir_modo_camera(self, modo: ModoCamera) -> None:
        """Troca entre Perspectiva, Frontal, Lateral e Companion."""
        self.camera_estado.modo = modo
        if modo == ModoCamera.LATERAL:
            self.camera_estado.yaw_graus = 90.0 * self._lado_direito_sinal
            self.camera_estado.pitch_graus = 0.0
        elif modo == ModoCamera.FRONTAL:
            self.camera_estado.yaw_graus = 0.0
            self.camera_estado.pitch_graus = 0.0
        self.aplicar_camera()

    def enquadrar(self) -> None:
        """Centraliza a câmera no personagem e restaura o zoom."""
        centro = (0.0, 0.0, float(self.renderer._view_target_z))
        if self.renderer.model_np is not None:
            bounds = self.renderer.model_np.getTightBounds(self.showbase.render)
            if bounds:
                mid = (bounds[0] + bounds[1]) * 0.5
                centro = (float(mid.x), float(mid.y), float(mid.z))
        elif self.renderer.model_anchor is not None:
            p = self.renderer.model_anchor.getPos(self.showbase.render)
            centro = (float(p.x), float(p.y), float(p.z) + 2.7)
        self.camera_estado.enquadrar(centro)
        self.aplicar_camera()

    def aplicar_camera(self) -> None:
        """Aplica estado da câmera no nó ``cam`` e sua lente."""
        from panda3d.core import OrthographicLens, PerspectiveLens

        cam = self.showbase.cam
        aspect = max(0.25, self.renderer.width / max(1, self.renderer.height))
        est = self.camera_estado
        if est.modo == ModoCamera.COMPANION:
            lens = OrthographicLens()
            lens.setFilmSize(12.4264 * aspect, 12.4264)
            lens.setNearFar(0.1, 100.0)
            cam.node().setLens(lens)
            cam.setPos(0.0, -15.0, float(self.renderer._view_target_z))
            cam.lookAt(0.0, 0.0, float(self.renderer._view_target_z))
            return
        dist = self._configurar_lente_editor(cam, est, aspect, OrthographicLens, PerspectiveLens)
        yaw_r = math.radians(est.yaw_graus)
        pitch_r = math.radians(est.pitch_graus)
        tx, ty, tz = est.alvo
        cam.setPos(
            tx + dist * math.cos(pitch_r) * math.sin(yaw_r),
            ty - dist * math.cos(pitch_r) * math.cos(yaw_r),
            tz + dist * math.sin(pitch_r),
        )
        cam.lookAt(tx, ty, tz)

    @staticmethod
    def _configurar_lente_editor(
        cam: Any,
        est: EstadoCamera,
        aspect: float,
        ortho_cls: Any,
        persp_cls: Any,
    ) -> float:
        if est.modo in (ModoCamera.FRONTAL, ModoCamera.LATERAL):
            h_film = 12.4264 / max(0.35, est.zoom_ortho)
            lens_o = ortho_cls()
            lens_o.setFilmSize(h_film * aspect, h_film)
            lens_o.setNearFar(0.5, 160.0)
            cam.node().setLens(lens_o)
            return 30.0
        lens_p = persp_cls()
        lens_p.setFov(38.0)
        lens_p.setNearFar(0.5, 160.0)
        lens_p.setAspectRatio(aspect)
        cam.node().setLens(lens_p)
        return est.distancia

    def definir_junta_selecionada(self, grupo: str | None) -> None:
        """Atualiza junta selecionada e reposiciona o manipulador 3D."""
        self.junta_selecionada = grupo
        self._atualizar_euler_selecionada()
        self._sincronizar_gizmo()

    def _contatos_visiveis(self) -> bool:
        return self.overlays.contatos or (
            self.ferramenta == ModoFerramenta.MOVER
            and self._alvo_mover.tipo == "obstaculo"
        )

    def _atualizar_overlays_ferramenta(self) -> None:
        self._overlays_3d._atualizar_ancoras(
            self.overlays.ancoras, self._guia_vfx_atual()
        )
        if self._ultimo_quadro is not None:
            self._overlays_3d._atualizar_contatos(
                self._contatos_visiveis(),
                self._ultimo_obstaculo,
                self._ultimo_quadro,
            )

    def definir_ferramenta(self, modo: ModoFerramenta) -> None:
        """Alterna entre manipulação de rotação (Girar) e translação (Mover)."""
        if self._drag_modo in ("gizmo", "mover_gizmo"):
            self.cancelar_drag_gizmo()
        self.ferramenta = modo
        self._hover_eixo = None
        self._sincronizar_gizmo()
        self._atualizar_overlays_ferramenta()

    def definir_alvo_mover(self, alvo: EstadoAlvoMover) -> None:
        """Define qual propriedade espacial será movida na ferramenta Mover."""
        self._alvo_mover = alvo
        if self._drag_modo != "mover_gizmo":
            self._mover_valor_atual = alvo.valor_atual
        self._sincronizar_gizmo()
        self._atualizar_overlays_ferramenta()

    def _atualizar_euler_selecionada(self) -> None:
        if self.junta_selecionada and self.junta_selecionada in self._pose_atual:
            r = self._pose_atual[self.junta_selecionada]
            self._pose_euler_selecionada = (
                math.degrees(r.x),
                math.degrees(r.y),
                math.degrees(r.z),
            )

    def _posicao_ancora_vfx(self, nome_ancora: str) -> tuple[float, float, float]:
        from panda3d.core import Point3

        ef = getattr(self.renderer, "efeitos_street", None)
        if ef is not None:
            ancs = ef._calcular_ancoras()
            mapa_legado = {
                "cabeca": "cabeca_topo",
                "pes": "pes",
                "tronco": "tronco",
                "fone_dir": "fone_dir",
                "fone_esq": "fone_esq",
                "raiva": "templo",
                "boca": "visor_lado",
                "antena_d": "antena_d",
                "antena_e": "antena_e",
                "antenas": "antenas_meio",
            }
            pt_loc = (
                ancs.get(nome_ancora)
                or ancs.get(mapa_legado.get(nome_ancora, "cabeca_topo"))
                or ancs.get("cabeca")
            )
            if pt_loc is not None:
                p = self.showbase.render.getRelativePoint(ef.root, Point3(pt_loc))
                return (float(p.x), float(p.y), float(p.z))
        return (
            float(self._base_anchor_pos.x),
            float(self._base_anchor_pos.y) - 2.2,
            float(self._base_anchor_pos.z) + 3.2,
        )

    def _obter_modelo_rig(self) -> Any:
        if self._modelo_rig is None:
            from sejoga.nucleo.modelo import load_model
            from sejoga.nucleo.recursos import resolve_model

            self._modelo_rig = load_model(resolve_model())
        return self._modelo_rig

    def _medir_alcas_locais_mira(self) -> dict[str, tuple[float, float, float]]:
        from panda3d.core import Vec3

        alcas: dict[str, tuple[float, float, float]] = {}
        alvos_terminais = (
            "head",
            "door",
            "fones",
            "fone-direito",
            "fone-esquerdo",
            "antena-direita",
            "antena-esquerda",
        )
        for grupo in alvos_terminais:
            node = self.renderer._rig_nodes.get(grupo)
            if node is None or node.isEmpty():
                continue
            bounds = node.getTightBounds(node)
            if bounds:
                c = (bounds[0] + bounds[1]) * 0.5
                if grupo == "head":
                    # Frente do rosto/visor no espaço local de ``head``.
                    p_face = node.getPos(self.showbase.render) + Vec3(0.0, -0.95, 1.15)
                    c = node.getRelativePoint(self.showbase.render, p_face)
                alcas[grupo] = (float(c.x), float(c.y), float(c.z))
        return alcas

    def _posicao_alca_membro(self, grupo: str) -> tuple[float, float, float] | None:
        from panda3d.core import Point3

        if not grupo:
            return None
        filho = _ALCA_FILHO_MIRA.get(grupo)
        if filho:
            node_f = self.renderer._rig_nodes.get(filho)
            if node_f is not None and not node_f.isEmpty():
                p = node_f.getPos(self.showbase.render)
                return (float(p.x), float(p.y), float(p.z))
        if grupo in ("canela-direita", "right-feet"):
            node_pe = self.renderer._rig_nodes.get("right-feet")
            if node_pe is not None and not node_pe.isEmpty():
                p = node_pe.getPos(self.showbase.render)
                return (float(p.x), float(p.y), float(p.z))
        if grupo in ("canela-esquerda", "left-feet"):
            node_pe = self.renderer._rig_nodes.get("left-feet")
            if node_pe is not None and not node_pe.isEmpty():
                p = node_pe.getPos(self.showbase.render)
                return (float(p.x), float(p.y), float(p.z))
        node = self.renderer._rig_nodes.get(grupo)
        if node is None or node.isEmpty():
            return None
        local = self._alcas_locais_mira.get(grupo)
        if local is not None:
            p = self.showbase.render.getRelativePoint(node, Point3(*local))
            return (float(p.x), float(p.y), float(p.z))
        p = node.getPos(self.showbase.render)
        return (float(p.x), float(p.y), float(p.z))

    def _posicao_mover_atual(self) -> tuple[float, float, float] | None:
        alvo = self._alvo_mover
        if not alvo.tipo:
            return None
        if alvo.tipo == "membro":
            return self._posicao_alca_membro(alvo.grupo)
        vx, vy, vz = (
            self._mover_valor_atual
            if self._drag_modo == "mover_gizmo"
            else alvo.valor_atual
        )
        if alvo.tipo == "obstaculo":
            return (vx, vy, vz)
        if alvo.tipo == "vfx":
            ax, ay, az = self._posicao_ancora_vfx(alvo.ancora_vfx)
            return (ax + vx, ay + vy, az + vz)
        node = self.renderer._rig_nodes.get("body")
        if node is not None and not node.isEmpty():
            p = node.getPos(self.showbase.render)
            return (float(p.x), float(p.y), float(p.z))
        return (
            float(self._base_anchor_pos.x) + vx,
            float(self._base_anchor_pos.y) + vy,
            float(self._base_anchor_pos.z) + vz + 1.4,
        )

    def _sincronizar_gizmo(self) -> None:
        destaque = self._drag_eixo or self._hover_eixo
        eh_mover = self.ferramenta == ModoFerramenta.MOVER
        self._gizmo.sincronizar(
            self.renderer,
            self.junta_selecionada,
            self._pose_euler_selecionada,
            destaque,
            visivel=not eh_mover,
        )
        pos_mv = self._posicao_mover_atual() if eh_mover else None
        self._gizmo_mover.sincronizar(
            pos_mv,
            destaque,
            visivel=eh_mover and pos_mv is not None,
        )

    def reiniciar_efeitos(self) -> None:
        """Limpa partículas e tentáculos em busca reversa ou retorno ao loop."""
        from sejoga.tentaculos.sistema_tentaculos import TentacleState

        ef = getattr(self.renderer, "efeitos_street", None)
        if ef is not None:
            ef.limpar()
        choque = getattr(self.renderer, "_choque_antenas_3d", None)
        if choque is not None:
            choque.ocultar()
        if self.renderer.tentacle_pool is not None:
            for t in self.renderer.tentacle_pool.tentacles:
                t.state = TentacleState.DORMANT
                t.reveal = 0.0
        if self.renderer.tentacle_director is not None:
            self.renderer.tentacle_director._door_current = 0.0
            self.renderer.tentacle_director.burst = False

    def _aplicar_obstaculo_tentaculos(self, obstaculo: ObstaculoPrevia | None) -> None:
        from panda3d.core import Mat4, Vec3

        from sejoga.tentaculos.restricoes_tentaculos import ObstacleBox

        pool = self.renderer.tentacle_pool
        if pool is None:
            return
        extra = None
        if obstaculo and obstaculo.ativo:
            cx, cy, cz = obstaculo.centro
            hx, hy, hz = obstaculo.meia_extensao
            extra = ObstacleBox(
                name="editor-obstaculo",
                low=Vec3(cx - hx, cy - hy, cz - hz),
                high=Vec3(cx + hx, cy + hy, cz + hz),
                to_local=Mat4.identMat(),
                to_model=Mat4.identMat(),
            )
        for limb in pool.tentacles:
            if limb.contacts is None:
                continue
            limpos = [b for b in limb.contacts.boxes if b.name != "editor-obstaculo"]
            if extra is not None:
                limpos.append(extra)
            limb.contacts.boxes = limpos

    def sincronizar_quadro(
        self,
        quadro: QuadroPrevia,
        *,
        controller: Any = None,
        quadro_salvo: QuadroPrevia | None = None,
        obstaculo: ObstaculoPrevia | None = None,
        trilhas_pts: tuple[
            list[tuple[float, float, float]], list[tuple[float, float, float]]
        ]
        | None = None,
        dados_rascunho: dict[str, Any] | None = None,
    ) -> None:
        """Aplica ``quadro`` à malha, pernas, tentáculos, VFX e overlays 3D."""
        if self._destroyed:
            return
        if dados_rascunho is not None:
            self._dados_rascunho = dados_rascunho
        self._pose_atual = dict(quadro.pose)
        if controller is not None:
            self.showbase.animation_controller = controller
        self.renderer.apply_rig_pose(quadro.pose)
        if getattr(self.renderer, "lower_body", None) is not None:
            self.renderer.lower_body.apply(quadro.pernas or LegPose(), True, dt=STEP_SIM_S)
        self._aplicar_transform_ancora(quadro)
        with dados_autorais.usar_rascunho(self._dados_rascunho):
            if self.renderer.tentacle_director is not None:
                self.renderer._door_requested = max(0.0, quadro.tentaculos_porta_aberta)
                self._aplicar_obstaculo_tentaculos(obstaculo)
                self.renderer.update_appendages(STEP_SIM_S, visible=quadro.tentaculos_ativos)
            self._atualizar_efeitos_quadro(quadro)
        self._atualizar_euler_selecionada()
        self._ultimo_quadro = quadro
        self._ultimo_obstaculo = obstaculo or ObstaculoPrevia()
        self._sincronizar_gizmo()
        overlays_ef = (
            replace(self.overlays, contatos=True)
            if self._contatos_visiveis() and not self.overlays.contatos
            else self.overlays
        )
        self._overlays_3d.atualizar(
            overlays_ef,
            self.junta_selecionada,
            self._ultimo_obstaculo,
            quadro,
            quadro_salvo,
            trilhas_pts,
            guia_vfx=self._guia_vfx_atual(),
        )

    def _guia_vfx_atual(self) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        if self.ferramenta != ModoFerramenta.MOVER or self._alvo_mover.tipo != "vfx":
            return None
        anc = self._posicao_ancora_vfx(self._alvo_mover.ancora_vfx)
        dst = self._posicao_mover_atual()
        return (anc, dst) if dst is not None else None

    def _aplicar_transform_ancora(self, quadro: QuadroPrevia) -> None:
        if self.renderer.model_anchor is None:
            return
        dx, dy, dz = quadro.deslocamento_corpo
        self.renderer.model_anchor.setPos(
            self._base_anchor_pos.x + dx,
            self._base_anchor_pos.y + dy,
            self._base_anchor_pos.z + dz,
        )
        px, py, pz = quadro.orientacao_graus
        self.renderer.model_anchor.setHpr(py, px, pz)
        self.renderer.model_anchor.setScale(quadro.escala)

    def _atualizar_efeitos_quadro(self, quadro: QuadroPrevia) -> None:
        ativos = set(quadro.janelas_vfx_ativas) | {e.nome for e in quadro.eventos_vfx}
        amostra = quadro.amostra_cena
        estouro = "estouro_fone" in ativos or bool(amostra and amostra.estouro_fone)
        choque = "choque_argolas" in ativos or bool(amostra and amostra.choque_argolas)
        efeitos_st = getattr(self.renderer, "efeitos_street", None)
        if efeitos_st is not None:
            params = {
                "estado": quadro.estado_contexto,
                "tempo_estado": quadro.tempo_s,
                "grounded": True,
                "velocidade": (560.0, 0.0) if "derrapagem" in ativos else (0.0, 0.0),
                "medo": "suor" in ativos,
                "tremor": "tremor" in ativos,
                "susto": "susto" in ativos,
                "raiva": "raiva" in ativos,
                "tontura": "tontura" in ativos,
                "sono": "zzz" in ativos,
                "estouro_fone": estouro,
                "choque_argolas": choque,
                "acento_danca": "notas" in ativos or quadro.batida_ativa,
                "deslizando": "derrapagem" in ativos,
                "comemorando": "comemoracao" in ativos,
                "som_fones": "ondas" in ativos or "notas" in ativos,
                "gosma_evento": "gosma" in ativos,
                "carinho": "carinho" in ativos,
            }
            efeitos_st.atualizar(STEP_SIM_S, params)
        choque_3d = getattr(self.renderer, "_choque_antenas_3d", None)
        if choque_3d is not None:
            if choque or estouro:
                choque_3d.atualizar(
                    STEP_SIM_S,
                    aviso_antena=0.35 if choque else 0.0,
                    choque_argolas=bool(choque or estouro),
                    permitir_ponte=True,
                )
            else:
                choque_3d.ocultar()

    def step(self) -> None:
        """Processa interação de mouse contínua e avança um passo do Panda3D."""
        if self._destroyed or self._stepping:
            return
        self._stepping = True
        try:
            with dados_autorais.usar_rascunho(self._dados_rascunho):
                self._processar_drag_ativo()
                self.showbase.taskMgr.step()
        finally:
            self._stepping = False

    def _processar_drag_ativo(self) -> None:
        if self._drag_modo is None:
            self._atualizar_hover_gizmo()
            return
        mp = self._mpos()
        if mp is None:
            return
        dx = mp[0] - self._drag_inicio_mouse[0]
        dy = mp[1] - self._drag_inicio_mouse[1]
        if self._drag_modo == "orbit":
            self._drag_inicio_mouse = mp
            self.camera_estado.orbitar(dx, dy)
            self.aplicar_camera()
        elif self._drag_modo == "pan":
            self._drag_inicio_mouse = mp
            self.camera_estado.pan(dx, dy)
            self.aplicar_camera()
        elif self._drag_modo == "gizmo" and self._drag_eixo and self.junta_selecionada:
            self._atualizar_drag_gizmo(dx, dy)
        elif self._drag_modo == "mover_gizmo" and self._drag_eixo and self._alvo_mover.tipo:
            self._atualizar_drag_mover(dx, dy)

    def _atualizar_drag_gizmo(self, dx: float, dy: float) -> None:
        proj = (dx * self._drag_aspect) * self._drag_tangente[0] + dy * self._drag_tangente[1]
        delta_graus = proj * 190.0
        bx, by, bz = self._drag_inicio_euler
        e = self._drag_eixo
        nova = (
            bx + (delta_graus if e == "x" else 0.0),
            by + (delta_graus if e == "y" else 0.0),
            bz + (delta_graus if e == "z" else 0.0),
        )
        self._pose_euler_selecionada = nova
        if self._on_gizmo_update and self.junta_selecionada:
            self._on_gizmo_update(self.junta_selecionada, nova)

    def _pose_graus_mapa(self, juntas: tuple[str, ...]) -> dict[str, tuple[float, float, float]]:
        saida: dict[str, tuple[float, float, float]] = {}
        for grp in juntas:
            rot = self._pose_atual.get(grp, Rotation3())
            saida[grp] = (math.degrees(rot.x), math.degrees(rot.y), math.degrees(rot.z))
        return saida

    def _capturar_drag_membro(self, alvo: EstadoAlvoMover) -> _EstadoDragMembro | None:
        handle0 = self._posicao_alca_membro(alvo.grupo)
        if handle0 is None:
            return None
        pose0 = self._pose_graus_mapa(alvo.juntas_afetadas or (alvo.grupo,))
        modo = alvo.modo_ik
        if modo in ("ik_braco_dir", "ik_braco_esq"):
            lado = "right" if modo == "ik_braco_dir" else "left"
            g_b, g_a, g_m = (
                ("right-arm", "ant-arm", "hand")
                if lado == "right"
                else ("left-arm", "ant-arm2", "hand2")
            )
            eff0, polo = _arm_effector_e_polo(
                self.showbase.render, self.renderer._rig_nodes, g_b, g_a, g_m, lado
            )
            return _EstadoDragMembro(alvo, handle0, eff0, pose0, polo_braco_alvo=polo)
        if modo in ("ik_perna_dir", "ik_perna_esq", "coxa_dir", "coxa_esq"):
            lado = "right" if modo.endswith("_dir") else "left"
            pernas0 = self._ultimo_quadro.pernas if self._ultimo_quadro else None
            estado_lado = extrair_estado_pernas(pernas0, lado)
            eff0 = self._effector_perna_world(lado, modo, handle0)
            return _EstadoDragMembro(
                alvo, handle0, eff0, pose0, pernas_inicial_lado=estado_lado
            )
        from panda3d.core import Vec3

        node = self.renderer._rig_nodes.get(alvo.grupo)
        if node is None or node.isEmpty():
            return None
        pai = node.getParent()
        piv = node.getPos(self.showbase.render)
        v0 = pai.getRelativeVector(
            self.showbase.render,
            Vec3(handle0[0] - piv.x, handle0[1] - piv.y, handle0[2] - piv.z),
        )
        q0 = node.getQuat(pai)
        return _EstadoDragMembro(
            alvo=alvo,
            handle_world_0=handle0,
            effector_world_0=handle0,
            pose_inicial_deg=pose0,
            mira_piv_world=(float(piv.x), float(piv.y), float(piv.z)),
            mira_v0_pai=(float(v0.x), float(v0.y), float(v0.z)),
            mira_q0_pai=(float(q0.getR()), float(q0.getI()), float(q0.getJ()), float(q0.getK())),
        )

    def _effector_perna_world(
        self,
        lado: str,
        modo: str,
        fallback: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        nome_no = (
            ("right-feet" if lado == "right" else "left-feet")
            if modo.startswith("ik_perna")
            else ("joelho-direito" if lado == "right" else "joelho-esquerdo")
        )
        no = self.renderer._rig_nodes.get(nome_no)
        if no is None or no.isEmpty():
            return fallback
        p = no.getPos(self.showbase.render)
        return (float(p.x), float(p.y), float(p.z))

    def _resolver_ik_membro_drag(
        self, p_handle_alvo: tuple[float, float, float]
    ) -> dict[str, tuple[float, float, float]]:
        drag = self._drag_membro
        if drag is None:
            return {}
        hx0, hy0, hz0 = drag.handle_world_0
        ex0, ey0, ez0 = drag.effector_world_0
        p_eff = (
            p_handle_alvo[0] + (ex0 - hx0),
            p_handle_alvo[1] + (ey0 - hy0),
            p_handle_alvo[2] + (ez0 - hz0),
        )
        modo = drag.alvo.modo_ik
        if modo in ("ik_braco_dir", "ik_braco_esq"):
            lado = "right" if modo == "ik_braco_dir" else "left"
            polo = drag.polo_braco_alvo or POLO_COTOVELO_ANATOMICO
            return _resolver_ik_braco_panda(
                self._obter_modelo_rig(),
                self.showbase.render,
                self.renderer._rig_nodes,
                lado,
                p_eff,
                polo,
            )
        if modo in ("ik_perna_dir", "ik_perna_esq", "coxa_dir", "coxa_esq"):
            return self._resolver_ik_perna_drag(drag, p_eff)
        from panda3d.core import Vec3

        node = self.renderer._rig_nodes.get(drag.alvo.grupo)
        if node is None or node.isEmpty():
            return dict(drag.pose_inicial_deg)
        pai = node.getParent()
        px, py, pz = drag.mira_piv_world
        v1 = pai.getRelativeVector(
            self.showbase.render,
            Vec3(p_eff[0] - px, p_eff[1] - py, p_eff[2] - pz),
        )
        pose0 = drag.pose_inicial_deg.get(drag.alvo.grupo, (0.0, 0.0, 0.0))
        bh, bp, br = self.renderer._rig_base_hpr.get(drag.alvo.grupo, (0.0, 0.0, 0.0))
        extra = BASE_ADICIONAL_GRAUS.get(drag.alvo.grupo, (0.0, 0.0, 0.0))
        rot = _quat_para_mira_euler(
            drag.mira_v0_pai,
            v1,
            drag.mira_q0_pai,
            (bh, bp, br),
            extra,
            pose0,
        )
        return {drag.alvo.grupo: rot}

    def _resolver_ik_perna_drag(
        self,
        drag: _EstadoDragMembro,
        p_eff: tuple[float, float, float],
    ) -> dict[str, tuple[float, float, float]]:
        lb = getattr(self.renderer, "lower_body", None)
        if lb is None or self.renderer.model_np is None:
            return dict(drag.pose_inicial_deg)
        lado = "right" if drag.alvo.modo_ik.endswith("_dir") else "left"
        dados = next((d for d in lb._lados if d["lado"] == lado), None)
        if dados is None:
            return dict(drag.pose_inicial_deg)
        p_loc = _render_para_leg_base(lb, self.renderer.model_np, self.showbase.render, p_eff)
        pq, pj, pt = dados["quadril"], dados["joelho"], dados["tornozelo"]
        q0, k0, r0, yaw0 = drag.pernas_inicial_lado
        coxa, _, canela, _ = dados["nomes"]
        c0 = drag.pose_inicial_deg.get(coxa, (0.0, 0.0, 0.0))
        if drag.alvo.modo_ik.startswith("coxa"):
            q_tot, roll_tot = resolver_mira_coxa(
                (pq.x, pq.y, pq.z), (pj.x, pj.y, pj.z), p_loc, yaw_graus=yaw0
            )
            return {
                coxa: (round(c0[0] + (q_tot - q0), 4), c0[1], round(c0[2] + (roll_tot - r0), 4))
            }
        q_tot, k_tot, roll_tot = resolver_ik_perna(
            (pq.x, pq.y, pq.z),
            (pj.x, pj.y, pj.z),
            (pt.x, pt.y, pt.z),
            p_loc,
            yaw_graus=yaw0,
        )
        n0 = drag.pose_inicial_deg.get(canela, (0.0, 0.0, 0.0))
        return {
            coxa: (round(c0[0] + (q_tot - q0), 4), c0[1], round(c0[2] + (roll_tot - r0), 4)),
            canela: (round(n0[0] + (k_tot - k0), 4), n0[1], n0[2]),
        }

    def _atualizar_drag_mover(self, dx: float, dy: float) -> None:
        jx, jy = self._drag_jacobiana
        denom = max(0.015**2, jx * jx + jy * jy)
        delta_m = ((dx * self._drag_aspect) * jx + dy * jy) / denom
        e = self._drag_eixo
        if self._alvo_mover.tipo == "membro" and self._drag_membro is not None:
            hx0, hy0, hz0 = self._drag_membro.handle_world_0
            p_alvo = (
                hx0 + (delta_m if e == "x" else 0.0),
                hy0 + (delta_m if e == "y" else 0.0),
                hz0 + (delta_m if e == "z" else 0.0),
            )
            poses = self._resolver_ik_membro_drag(p_alvo)
            self._mover_poses_membro = poses
            if self._on_mover_update:
                self._on_mover_update("membro", poses)
            return
        mx, my, mz = self._drag_inicio_mover
        novo = (
            round(mx + (delta_m if e == "x" else 0.0), 4),
            round(my + (delta_m if e == "y" else 0.0), 4),
            round(mz + (delta_m if e == "z" else 0.0), 4),
        )
        self._mover_valor_atual = novo
        if self._on_mover_update and self._alvo_mover.tipo:
            self._on_mover_update(self._alvo_mover.tipo, novo)

    def _atualizar_hover_gizmo(self) -> None:
        mp = self._mpos()
        if mp is None or not self.showbase.cam:
            novo = None
        else:
            aspect = self._aspect_viewport()
            if self.ferramenta == ModoFerramenta.MOVER:
                hit = self._gizmo_mover.escolher_eixo(self.showbase.cam, mp, aspect)
            else:
                hit = self._gizmo.escolher_eixo(self.showbase.cam, mp, aspect)
            novo = hit[0] if hit is not None else None
        if novo != self._hover_eixo:
            self._hover_eixo = novo
            self._sincronizar_gizmo()

    def destruir(self) -> None:
        """Encerra ShowBase e libera recursos gráficos sem vazamentos."""
        if self._destroyed:
            return
        self._destroyed = True
        try:
            self.showbase.ignoreAll()
            self.showbase.destroy()
        except Exception:
            logger.debug("Exceção ignorada ao destruir PandaViewportSession", exc_info=True)


class ViewportPandaWidget(QWidget):
    """Widget PySide6 que hospeda o viewport 3D nativo Panda3D no centro."""

    junta_selecionada = Signal(str)
    gizmo_iniciado = Signal(str, str)
    gizmo_atualizado = Signal(str, object)
    gizmo_confirmado = Signal(str, object)
    gizmo_cancelado = Signal()
    mover_iniciado = Signal(str, str)
    mover_atualizado = Signal(str, object)
    mover_confirmado = Signal(str, object)
    mover_cancelado = Signal()

    def __init__(self, parent: QWidget | None = None, *, habilitar_gpu: bool = True) -> None:
        """Inicializa o hospedeiro Qt do canvas 3D com timer de 60 Hz."""
        super().__init__(parent)
        self._habilitar_gpu = bool(habilitar_gpu)
        self._engine: PandaViewportSession | None = None
        self._overlays = EstadoOverlays()
        self._modo_cam = ModoCamera.PERSPECTIVA
        self._ferramenta = ModoFerramenta.GIRAR
        self._alvo_mover = EstadoAlvoMover()
        self._junta_pendente: str | None = "right-arm"
        self._ultimo_pacote: dict[str, Any] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._host = QWidget(self)
        self._host.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self._host.setMinimumSize(320, 240)
        layout.addWidget(self._host)

        self._fallback_label = QLabel("Viewport 3D aguardando contexto...", self)
        self._fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fallback_label.hide()
        layout.addWidget(self._fallback_label)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

    @property
    def engine(self) -> PandaViewportSession | None:
        """Instância subjacente do viewport Panda3D, quando inicializada."""
        return self._engine

    def inicializar_gpu(self) -> bool:
        """Cria a janela Panda3D embutida no HWND deste widget."""
        if self._engine is not None:
            return True
        if not self._habilitar_gpu:
            self._mostrar_fallback("Prévia 3D desabilitada neste modo.")
            return False
        dpr = max(1.0, float(self.devicePixelRatioF()))
        w_px = max(320, round(self._host.width() * dpr))
        h_px = max(240, round(self._host.height() * dpr))
        try:
            self._engine = PandaViewportSession(
                int(self._host.winId()),
                w_px,
                h_px,
                on_joint_selected=self.junta_selecionada.emit,
                on_gizmo_start=self.gizmo_iniciado.emit,
                on_gizmo_update=self.gizmo_atualizado.emit,
                on_gizmo_commit=self.gizmo_confirmado.emit,
                on_gizmo_cancel=self.gizmo_cancelado.emit,
                on_mover_start=self.mover_iniciado.emit,
                on_mover_update=self.mover_atualizado.emit,
                on_mover_commit=self.mover_confirmado.emit,
                on_mover_cancel=self.mover_cancelado.emit,
            )
            self._engine.overlays = self._overlays
            self._engine.definir_modo_camera(self._modo_cam)
            self._engine.definir_ferramenta(self._ferramenta)
            self._engine.definir_alvo_mover(self._alvo_mover)
            if self._junta_pendente:
                self._engine.definir_junta_selecionada(self._junta_pendente)
            if self._ultimo_pacote:
                self._engine.sincronizar_quadro(**self._ultimo_pacote)
            self._fallback_label.hide()
            self._host.show()
            if not self._timer.isActive():
                self._timer.start()
            return True
        except Exception as exc:
            self._mostrar_fallback(f"Falha ao abrir viewport 3D:\n{exc}")
            return False

    def _mostrar_fallback(self, texto: str) -> None:
        self._host.hide()
        self._fallback_label.setText(texto)
        self._fallback_label.show()

    def showEvent(self, event: Any) -> None:
        """Garante inicialização do contexto WGL apenas após criação do HWND nativo."""
        super().showEvent(event)
        if self._habilitar_gpu and self._engine is None:
            self.inicializar_gpu()

    def resizeEvent(self, event: Any) -> None:
        """Redimensiona o canvas Panda3D respeitando DPI do Windows."""
        super().resizeEvent(event)
        if self._engine is not None:
            dpr = max(1.0, float(self.devicePixelRatioF()))
            self._engine.resize(
                round(max(1, self._host.width()) * dpr),
                round(max(1, self._host.height()) * dpr),
            )

    def _on_tick(self) -> None:
        if self._engine is not None:
            self._engine.step()

    def definir_modo_camera(self, modo: ModoCamera) -> None:
        """Altera o modo de câmera ativa."""
        self._modo_cam = modo
        if self._engine is not None:
            self._engine.definir_modo_camera(modo)

    def enquadrar(self) -> None:
        """Restaura enquadramento no modelo."""
        if self._engine is not None:
            self._engine.enquadrar()

    def definir_overlays(self, overlays: EstadoOverlays) -> None:
        """Atualiza quais sobreposições 3D estão visíveis."""
        self._overlays = overlays
        if self._engine is not None:
            self._engine.overlays = overlays
            if self._ultimo_pacote:
                self._engine.sincronizar_quadro(**self._ultimo_pacote)

    def definir_junta_selecionada(self, grupo: str | None) -> None:
        """Atualiza o manipulador 3D para a junta ``grupo``."""
        self._junta_pendente = grupo
        if self._engine is not None:
            self._engine.definir_junta_selecionada(grupo)

    def definir_ferramenta(self, modo: ModoFerramenta) -> None:
        """Alterna o manipulador ativo entre Girar e Mover."""
        self._ferramenta = modo
        if self._engine is not None:
            self._engine.definir_ferramenta(modo)

    def definir_alvo_mover(self, alvo: EstadoAlvoMover) -> None:
        """Atualiza o alvo 3D exibido pelo manipulador de movimento."""
        self._alvo_mover = alvo
        if self._engine is not None:
            self._engine.definir_alvo_mover(alvo)

    def cancelar_drag_gizmo(self) -> bool:
        """Cancela arraste ativo no manipulador 3D se houver um em andamento."""
        if self._engine is not None:
            return self._engine.cancelar_drag_gizmo()
        return False

    def reiniciar_efeitos(self) -> None:
        """Limpa partículas e tentáculos em seek reverso."""
        if self._engine is not None:
            self._engine.reiniciar_efeitos()

    def sincronizar_quadro(
        self,
        quadro: QuadroPrevia,
        *,
        controller: Any = None,
        quadro_salvo: QuadroPrevia | None = None,
        obstaculo: ObstaculoPrevia | None = None,
        trilhas_pts: tuple[
            list[tuple[float, float, float]], list[tuple[float, float, float]]
        ]
        | None = None,
        dados_rascunho: dict[str, Any] | None = None,
    ) -> None:
        """Repassa o quadro avaliado pela sessão de prévia ao renderer Panda3D."""
        self._ultimo_pacote = {
            "quadro": quadro,
            "controller": controller,
            "quadro_salvo": quadro_salvo,
            "obstaculo": obstaculo,
            "trilhas_pts": trilhas_pts,
            "dados_rascunho": dados_rascunho,
        }
        if self._engine is not None:
            self._engine.sincronizar_quadro(**self._ultimo_pacote)

    def destruir(self) -> None:
        """Interrompe o timer Qt e libera o ShowBase embutido."""
        self._timer.stop()
        if self._engine is not None:
            self._engine.destruir()
            self._engine = None

    def closeEvent(self, event: Any) -> None:
        """Libera o ShowBase quando o widget fecha."""
        self.destruir()
        super().closeEvent(event)

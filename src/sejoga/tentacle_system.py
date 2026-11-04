"""Sistema procedural de tentáculos — SeJogaDesktopCompanion.

Tentáculos como chains de segmentos rígidos (low-poly), sem skin.
Cada tentáculo = lista de TentacleSegment com mola-amortecedor + overshoot impulsivo.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

from panda3d.core import Vec3, Quat, NodePath, TransformState

from .rig import Rig, IdlePersonality


# ============================================================
# Configuração visual / física
# ============================================================

DEFAULT_SEGMENTS = 12          # segmentos por tentáculo
SEGMENT_LENGTH = 16.0          # px por segmento
BASE_WIDTH = 8.0               # largura na base
TIP_WIDTH = 2.0                # largura na ponta
SUCKER_COUNT = 4               # ventosas por segmento (visual)

# Parâmetros de mola por personalidade
SPRING_PARAMS = {
    IdlePersonality.CALM:       dict(spring=80.0,  damper=12.0, impulse_chance=0.01, impulse_strength=8.0),
    IdlePersonality.CURIOUS:    dict(spring=100.0, damper=8.0,  impulse_chance=0.03, impulse_strength=15.0),
    IdlePersonality.PLAYFUL:    dict(spring=150.0, damper=6.0,  impulse_chance=0.08, impulse_strength=30.0),
    IdlePersonality.SHY:        dict(spring=60.0,  damper=15.0, impulse_chance=0.005, impulse_strength=5.0),
    IdlePersonality.CONFIDENT:  dict(spring=120.0, damper=10.0, impulse_chance=0.02, impulse_strength=20.0),
}

# Parâmetros por estado comportamental
STATE_PARAMS = {
    "dormant":      dict(max_len=0.0,   reach_speed=0.0,   curl=0.0,  jitter=0.0),
    "curious":      dict(max_len=0.35,  reach_speed=400.0, curl=0.1,  jitter=0.05),
    "reaching":     dict(max_len=1.0,   reach_speed=900.0, curl=0.2,  jitter=0.1),
    "grabbing":     dict(max_len=1.0,   reach_speed=600.0, curl=0.85, jitter=0.05),
    "spitting":     dict(max_len=1.15,  reach_speed=-800.0,curl=0.0,  jitter=0.15),
    "frenzy":       dict(max_len=1.2,   reach_speed=2200.0,curl=0.4,  jitter=0.35),
    "retracting":   dict(max_len=0.0,   reach_speed=-600.0,curl=0.0,  jitter=0.0),
}


# ============================================================
# Estruturas de dados
# ============================================================

@dataclass(slots=True)
class TentacleSegment:
    """Segmento individual de um tentáculo (low-poly, sem skin)."""
    pos: Vec3 = field(default_factory=Vec3)
    vel: Vec3 = field(default_factory=Vec3)
    rot: Quat = field(default_factory=Quat)
    length: float = SEGMENT_LENGTH
    width: float = BASE_WIDTH
    curl: float = 0.0              # 0=reto, 1=enrolado
    sucker_phase: float = 0.0      # fase visual das ventosas

    # Para rendering: nó Panda3D correspondente (criado sob demanda)
    node: Optional[NodePath] = None
    outline_node: Optional[NodePath] = None


class TentacleState(StrEnum):
    DORMANT = "dormant"
    CURIOUS = "curious"
    REACHING = "reaching"
    GRABBING = "grabbing"
    SPITTING = "spitting"
    FRENZY = "frenzy"
    RETRACTING = "retracting"


@dataclass
class Tentacle:
    """Um tentáculo completo: chain de segmentos + target + estado."""
    segments: list[TentacleSegment]
    anchor: Vec3                   # ponto de ancoragem (spawn point)
    target: Optional[Vec3] = None  # target no espaço mundial
    state: TentacleState = TentacleState.DORMANT
    state_time: float = 0.0
    params: dict = field(default_factory=dict)
    spring: float = 100.0
    damper: float = 10.0
    impulse_chance: float = 0.02
    impulse_strength: float = 15.0
    seed: int = 0
    unit_scale: float = 1.0

    # Visual: cor das ventosas (padrão: mesma cor do corpo)
    sucker_color: tuple[float, float, float, float] = (0.2, 0.6, 1.0, 0.9)

    def __post_init__(self):
        if not self.params:
            self.params = dict(STATE_PARAMS["dormant"])


# ============================================================
# Pool de tentáculos
# ============================================================

class TentaclePool:
    """Gerencia pool de tentáculos — spawn/despawn sob demanda."""

    def __init__(
        self,
        rig: Rig,
        model_np: NodePath,
        outline_np: NodePath,
        spawn_points: list[Vec3],
        rng: Optional[random.Random] = None,
        unit_scale: float = 1.0,
    ):
        self.rig = rig
        self.model_np = model_np
        self.outline_np = outline_np
        self.spawn_points = spawn_points
        self.rng = rng or random.Random()
        self.unit_scale = max(1e-6, unit_scale)
        self.tentacles: list[Tentacle] = []
        self._next_spawn_index = 0

        # Cria pool pré-alocado (inativo)
        for i, spawn_pt in enumerate(spawn_points):
            tentacle = self._create_tentacle(i, spawn_pt)
            tentacle.state = TentacleState.DORMANT
            self.tentacles.append(tentacle)

    def _create_tentacle(self, index: int, anchor: Vec3) -> Tentacle:
        segments = []
        seed = self.rng.randint(0, 1_000_000)
        for i in range(DEFAULT_SEGMENTS):
            t = i / (DEFAULT_SEGMENTS - 1) if DEFAULT_SEGMENTS > 1 else 0.0
            width = BASE_WIDTH * (1.0 - t * 0.75)  # taper
            seg = TentacleSegment(
                pos=Vec3(anchor),
                length=SEGMENT_LENGTH * self.unit_scale,
                width=width * self.unit_scale,
                sucker_phase=self.rng.uniform(0, 2 * math.pi),
            )
            segments.append(seg)

        params = dict(STATE_PARAMS["dormant"])
        personality = IdlePersonality.CALM
        sp = SPRING_PARAMS[personality]

        return Tentacle(
            segments=segments,
            anchor=anchor,
            state=TentacleState.DORMANT,
            params=params,
            spring=sp["spring"],
            damper=sp["damper"],
            impulse_chance=sp["impulse_chance"],
            impulse_strength=sp["impulse_strength"],
            seed=seed,
            unit_scale=self.unit_scale,
        )

    def get_available(self, count: int) -> list[Tentacle]:
        """Retorna até `count` tentáculos DORMANT, ativando-os."""
        available = [t for t in self.tentacles if t.state == TentacleState.DORMANT]
        self.rng.shuffle(available)
        selected = available[:count]
        for t in selected:
            t.state = TentacleState.CURIOUS
            t.state_time = 0.0
            t.params = dict(STATE_PARAMS["curious"])
        return selected

    def release(self, tentacle: Tentacle) -> None:
        """Devolve tentáculo ao pool (retract -> dormant)."""
        tentacle.state = TentacleState.RETRACTING
        tentacle.state_time = 0.0
        tentacle.params = dict(STATE_PARAMS["retracting"])
        tentacle.target = None

    def release_all(self) -> None:
        for t in self.tentacles:
            if t.state != TentacleState.DORMANT:
                self.release(t)

    def update_personality(self, personality: IdlePersonality) -> None:
        sp = SPRING_PARAMS[personality]
        for t in self.tentacles:
            t.spring = sp["spring"]
            t.damper = sp["damper"]
            t.impulse_chance = sp["impulse_chance"]
            t.impulse_strength = sp["impulse_strength"]


# ============================================================
# Director — alto nível
# ============================================================

class TentacleDirector:
    """Comportamento de alto nível: decide o que os tentáculos fazem."""

    def __init__(
        self,
        pool: TentaclePool,
        rig: Rig,
        model_np: NodePath,
        outline_np: NodePath,
        door_node: NodePath,
        rng: Optional[random.Random] = None,
    ):
        self.pool = pool
        self.rig = rig
        self.model_np = model_np
        self.outline_np = outline_np
        self.door_node = door_node
        self.rng = rng or random.Random()

        # Estado
        self.mouse_pos: Optional[Vec3] = None
        self.mouse_vel: Vec3 = Vec3(0, 0, 0)
        self.frenzy_mode = False
        self.frenzy_time = 0.0
        self.swallowing = False
        self.swallow_target: Optional[Vec3] = None
        self.swallow_time = 0.0

        # Door control
        self._door_requested = 0.0
        self._door_current = 0.0

        # Cooldowns
        self._curious_cooldown = 0.0
        self._curious_interval = self.rng.uniform(60.0, 100.0)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def set_mouse(self, pos: Vec3, vel: Vec3) -> None:
        self.mouse_pos = pos
        self.mouse_vel = vel

    def trigger_frenzy(self, duration: float = 3.0) -> None:
        """Ativa modo frenzy (bravo) — 6-8 tentáculos caóticos."""
        self.frenzy_mode = True
        self.frenzy_time = duration
        self._spawn_frenzy()

    def trigger_swallow(self, target_pos: Vec3, duration: float = 2.0) -> None:
        """Inicia sequência de engolir: target é engolido e cuspido depois."""
        self.swallowing = True
        self.swallow_target = target_pos
        self.swallow_time = duration
        self._spawn_swallow()

    def trigger_curious(self) -> None:
        """Força um momento curious (espiada)."""
        self._spawn_curious(count=2)

    def update(self, dt: float, idle_time: float, personality: IdlePersonality) -> None:
        """Atualiza todos os tentáculos e decide transições."""
        dt = min(dt, 0.05)  # clamp para estabilidade

        # Atualiza pool
        self.pool.update_personality(personality)

        # Frenzy
        if self.frenzy_mode:
            self.frenzy_time -= dt
            if self.frenzy_time <= 0:
                self.frenzy_mode = False
                self._retract_all()
            else:
                self._update_frenzy(dt)

        # Swallow sequence
        elif self.swallowing:
            self.swallow_time -= dt
            self._update_swallow(dt)
            if self.swallow_time <= 0:
                self.swallowing = False
                self._retract_all()

        # Curious ambient (só se não estiver em estado especial)
        else:
            self._curious_cooldown -= dt
            if self._curious_cooldown <= 0 and idle_time > 10.0:
                self._spawn_curious(count=1)
                self._curious_cooldown = self.rng.uniform(60.0, 100.0)

        # Atualiza cada tentáculo ativo
        for tentacle in self.pool.tentacles:
            if tentacle.state != TentacleState.DORMANT:
                self._update_tentacle(tentacle, dt)

        # Door sync
        self._update_door(dt)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _spawn_frenzy(self) -> None:
        active = self.pool.get_available(7)  # 6-8 tentáculos
        for i, t in enumerate(active):
            t.state = TentacleState.FRENZY
            t.state_time = 0.0
            t.params = dict(STATE_PARAMS["frenzy"])
            t.target = self._random_target_near_mouse(radius=120.0)
        # Porta aberta total
        self._door_requested = 135.0

    def _spawn_swallow(self) -> None:
        active = self.pool.get_available(6)
        for i, t in enumerate(active):
            t.state = TentacleState.REACHING
            t.state_time = 0.0
            t.params = dict(STATE_PARAMS["reaching"])
            # Stagger targets levemente
            offset = Vec3(
                self.rng.uniform(-30, 30),
                self.rng.uniform(-30, 30),
                0,
            )
            t.target = self.swallow_target + offset
        self._door_requested = 135.0

    def _spawn_curious(self, count: int = 2) -> None:
        active = self.pool.get_available(count)
        for t in active:
            t.state = TentacleState.CURIOUS
            t.state_time = 0.0
            t.params = dict(STATE_PARAMS["curious"])
            # The cabinet front is local +Y. Keep the reveal anchored to the
            # opening so it remains visible even when the desktop cursor is far away.
            t.target = t.anchor + Vec3(
                self.rng.uniform(-.035, .035),
                50.0 * self.pool.unit_scale,
                self.rng.uniform(-.025, .025),
            )
        self._door_requested = max(self._door_requested, 25.0)

    def _retract_all(self) -> None:
        for t in self.pool.tentacles:
            if t.state != TentacleState.DORMANT:
                self.pool.release(t)
        self._door_requested = 0.0

    def _update_tentacle(self, tentacle: Tentacle, dt: float) -> None:
        tentacle.state_time += dt

        # Transições de estado
        self._check_state_transition(tentacle)

        # Parâmetros atuais
        p = tentacle.params
        max_len = p["max_len"]
        reach_speed = p["reach_speed"]
        target_curl = p["curl"]
        jitter = p["jitter"]

        # Spring params
        spring = tentacle.spring
        damper = tentacle.damper

        # Atualiza cada segmento
        for i, seg in enumerate(tentacle.segments):
            t_param = i / (len(tentacle.segments) - 1) if len(tentacle.segments) > 1 else 0.0

            # Target position para este segmento
            if tentacle.target is not None and reach_speed != 0:
                # Interpola do anchor ao target baseado no progresso do tentáculo
                base_progress = min(1.0, tentacle.state_time * abs(reach_speed) / 400.0)
                seg_progress = min(1.0, base_progress * (1.0 + t_param * 0.5))
                target_pos = tentacle.anchor + (tentacle.target - tentacle.anchor) * seg_progress
            else:
                target_pos = tentacle.anchor

            # Jitter impulsivo (twitch aleatório)
            if self.rng.random() < tentacle.impulse_chance * dt * 60:
                impulse = Vec3(
                    self.rng.uniform(-1, 1) * tentacle.impulse_strength * tentacle.unit_scale,
                    self.rng.uniform(-1, 1) * tentacle.impulse_strength * tentacle.unit_scale,
                    self.rng.uniform(-1, 1) * tentacle.impulse_strength * tentacle.unit_scale * 0.5,
                )
                seg.vel += impulse

            # Spring-damper
            force = (target_pos - seg.pos) * spring
            damping = -seg.vel * damper
            seg.vel += (force + damping) * dt
            seg.pos += seg.vel * dt

            # Clamp length (não passa do max_len)
            from_anchor = seg.pos - tentacle.anchor
            dist = from_anchor.length()
            max_dist = max_len * (i + 1) * SEGMENT_LENGTH * tentacle.unit_scale
            if dist > max_dist:
                seg.pos = tentacle.anchor + from_anchor.normalized() * max_dist
                seg.vel = Vec3(0, 0, 0)

            # Rotação aponta na direção do movimento
            if seg.vel.length() > 0.5 * tentacle.unit_scale:
                forward = seg.vel.normalized()
                up = Vec3(0, 0, 1)
                axis = up.cross(forward)
                dot = max(-1.0, min(1.0, up.dot(forward)))
                if axis.lengthSquared() > 1e-10:
                    axis.normalize()
                    seg.rot = Quat()
                    seg.rot.setFromAxisAngle(math.degrees(math.acos(dot)), axis)
                elif dot < 0:
                    seg.rot = Quat()
                    seg.rot.setFromAxisAngle(180, Vec3(1, 0, 0))

            # Curl visual (enrolar ponta)
            curl_amount = target_curl * (1.0 - t_param * 0.3)
            if curl_amount > 0.01:
                # Rotaciona em torno do eixo local Y para enrolar
                curl_rot = Quat()
                curl_rot.setHpr(Vec3(curl_amount * 45.0, 0, 0))
                seg.rot = seg.rot * curl_rot

            # Sucker phase para animação visual
            seg.sucker_phase += dt * 3.0

    def _check_state_transition(self, tentacle: Tentacle) -> None:
        st = tentacle.state
        p = tentacle.params

        if st == TentacleState.CURIOUS:
            if tentacle.state_time > 4.0:
                tentacle.state = TentacleState.DORMANT
                self.pool.release(tentacle)

        elif st == TentacleState.REACHING:
            if tentacle.target:
                dist = (tentacle.target - tentacle.segments[-1].pos).length()
                if dist < 20.0 * tentacle.unit_scale or tentacle.state_time > 1.5:
                    tentacle.state = TentacleState.GRABBING
                    tentacle.state_time = 0.0
                    tentacle.params = dict(STATE_PARAMS["grabbing"])

        elif st == TentacleState.GRABBING:
            if tentacle.state_time > 0.8:
                # Se swallow mode, transiciona pra spitting
                if self.swallowing:
                    tentacle.state = TentacleState.SPITTING
                    tentacle.state_time = 0.0
                    tentacle.params = dict(STATE_PARAMS["spitting"])
                    # Target = fora da tela (cuspir)
                    eject_dir = Vec3(
                        self.rng.uniform(-1, 1),
                        self.rng.uniform(-1, 1),
                        0,
                    ).normalized()
                    tentacle.target = tentacle.anchor + eject_dir * 400.0
                else:
                    tentacle.state = TentacleState.RETRACTING
                    tentacle.state_time = 0.0
                    tentacle.params = dict(STATE_PARAMS["retracting"])

        elif st == TentacleState.SPITTING:
            if tentacle.target:
                dist = (tentacle.target - tentacle.segments[-1].pos).length()
                if dist < 30.0 * tentacle.unit_scale or tentacle.state_time > 1.0:
                    tentacle.state = TentacleState.RETRACTING
                    tentacle.state_time = 0.0
                    tentacle.params = dict(STATE_PARAMS["retracting"])

        elif st == TentacleState.FRENZY:
            # Frenzy mantém até director mandar parar
            pass

        elif st == TentacleState.RETRACTING:
            if tentacle.state_time > 1.2:
                tentacle.state = TentacleState.DORMANT
                self.pool.release(tentacle)

    def _update_frenzy(self, dt: float) -> None:
        # Targets caóticos que mudam frequentemente
        for t in self.pool.tentacles:
            if t.state == TentacleState.FRENZY and self.rng.random() < 0.02:
                t.target = self._random_target_near_mouse(radius=200.0)

    def _update_swallow(self, dt: float) -> None:
        # Fase 1: REACHING -> GRABBING (puxa mouse pra dentro)
        # Fase 2: SPITTING (cuspe pra fora)
        # O director controla o timing via swallow_time
        pass  # Lógica está em _check_state_transition

    def _update_door(self, dt: float) -> None:
        # Suaviza abertura/fechamento da porta
        diff = self._door_requested - self._door_current
        self._door_current += diff * min(1.0, dt * 8.0)
        if self.door_node:
            self.door_node.setH(self._door_current)

    def _random_target_near_mouse(self, radius: float) -> Vec3:
        if self.mouse_pos:
            angle = self.rng.uniform(0, 2 * math.pi)
            dist = self.rng.uniform(0, radius * self.pool.unit_scale)
            return self.mouse_pos + Vec3(
                math.cos(angle) * dist,
                math.sin(angle) * dist,
                0,
            )
        return Vec3(0, 0, 0)

    def _spawn_curious(self, count: int) -> None:
        active = self.pool.get_available(count)
        for t in active:
            t.state = TentacleState.CURIOUS
            t.state_time = 0.0
            t.params = dict(STATE_PARAMS["curious"])
            # The cabinet front is local +Y. Keep the reveal anchored to the
            # opening so it remains visible even when the desktop cursor is far away.
            t.target = t.anchor + Vec3(
                self.rng.uniform(-.035, .035),
                50.0 * self.pool.unit_scale,
                self.rng.uniform(-.025, .025),
            )
        self._door_requested = max(self._door_requested, 25.0)


# ============================================================
# Rendering helper
# ============================================================

def create_tentacle_geometry(
    tentacle: Tentacle,
    parent: NodePath,
    outline_parent: NodePath,
    color: tuple[float, float, float, float] = (0.2, 0.6, 1.0, 0.9),
) -> None:
    """Cria nós Panda3D para os segmentos do tentáculo (low-poly octogonal)."""
    from panda3d.core import Geom, GeomNode, GeomVertexData, GeomVertexFormat, GeomVertexWriter
    from panda3d.core import GeomTriangles, GeomVertexWriter, CullFaceAttrib

    for i, seg in enumerate(tentacle.segments):
        # Octogonal prism (low-poly tentacle segment)
        format = GeomVertexFormat.getV3n3c4()
        vdata = GeomVertexData(f"tentacle_seg_{i}", format, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        normal = GeomVertexWriter(vdata, "normal")
        color_writer = GeomVertexWriter(vdata, "color")

        # Octogonal cross-section
        sides = 8
        radius_base = seg.width * 0.5
        radius_tip = seg.width * 0.5 * 0.95  # leve taper

        for ring in range(2):  # base e ponta
            radius = radius_base if ring == 0 else radius_tip
            z = 0.0 if ring == 0 else seg.length
            for s in range(sides):
                angle = 2 * math.pi * s / sides
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                vertex.addData3(x, y, z)
                # Normal aponta para fora
                normal.addData3(math.cos(angle), math.sin(angle), 0)
                color_writer.addData4f(*tentacle.sucker_color)

        # Triângulos conectando os dois anéis
        tri = GeomTriangles(Geom.UHStatic)
        for s in range(sides):
            s_next = (s + 1) % sides
            # Base triangle
            tri.addVertices(s, s_next, s + sides)
            # Tip triangle (winding invertido)
            tri.addVertices(s + sides, s_next + sides, s_next)
            # Side quads (2 tris each)
            tri.addVertices(s, s_next, s_next + sides)
            tri.addVertices(s, s_next + sides, s + sides)

        tri.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(tri)

        node = GeomNode(f"tentacle_seg")
        node.addGeom(geom)
        np = parent.attachNewNode(node)
        np.setTwoSided(True)

        # Outline copy
        outline_np = np.copyTo(outline_parent)
        outline_np.setName(f"tentacle_seg_outline")

        seg.node = np
        seg.outline_node = outline_np


def update_tentacle_render(tentacle: Tentacle) -> None:
    """Atualiza transform dos nós Panda3D baseado nos segmentos."""
    for seg in tentacle.segments:
        if seg.node:
            seg.node.setPos(seg.pos)
            seg.node.setQuat(seg.rot)
        if seg.outline_node:
            seg.outline_node.setPos(seg.pos)
            seg.outline_node.setQuat(seg.rot)
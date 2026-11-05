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
from .tentacle_constraints import TentacleContacts


# ============================================================
# Configuração visual / física
# ============================================================

DEFAULT_SEGMENTS = 24          # segmentos por tentáculo
SEGMENT_LENGTH = 8.0          # px por segmento
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
for _style, _base in (
    (IdlePersonality.STREET, IdlePersonality.CALM),
    (IdlePersonality.FIGHTER, IdlePersonality.CONFIDENT),
    (IdlePersonality.RHYTHM, IdlePersonality.CALM),
    (IdlePersonality.STYLISH, IdlePersonality.CURIOUS),
):
    SPRING_PARAMS[_style] = dict(SPRING_PARAMS[_base])

# Parâmetros por estado comportamental
STATE_PARAMS = {
    "dormant":      dict(max_len=0.0,   reach_speed=0.0,   curl=0.0,  jitter=0.0),
    "curious":      dict(max_len=0.40,  reach_speed=400.0, curl=0.1,  jitter=0.05),
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
    mesh_node: Optional[NodePath] = None
    outline_mesh_node: Optional[NodePath] = None
    mesh_vdata: object = None
    outline_vdata: object = None
    template_vertices: list = field(default_factory=list)
    template_normals: list = field(default_factory=list)
    rest_vertices: list = field(default_factory=list)
    retract_from: list[Vec3] = field(default_factory=list)
    reveal: float = 0.0
    retract_reveal: float = 0.0
    frames: list = field(default_factory=list)
    axis_nodes: list = field(default_factory=list)
    reference_front: Vec3 = field(default_factory=lambda: Vec3(0, 1, 0))
    contacts: Optional[TentacleContacts] = None

    length_scale: float = 1.0
    girth_scale: float = 1.0

    def visible_tip(self):
        sample = max(0.0, min(1.0, self.reveal)) * (len(self.segments) - 1)
        index = min(len(self.segments) - 2, int(sample))
        blend = sample - index
        return self.segments[index].pos * (1 - blend) + self.segments[index + 1].pos * blend

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
        selected = available[:count]
        for t in selected:
            t.state = TentacleState.CURIOUS
            t.state_time = 0.0
            t.params = dict(STATE_PARAMS["curious"])
        return selected

    def release(self, tentacle: Tentacle) -> None:
        """Devolve tentáculo ao pool (retract -> dormant)."""
        if tentacle.state in (TentacleState.DORMANT, TentacleState.RETRACTING):
            return
        tentacle.retract_from = [Vec3(segment.pos) for segment in tentacle.segments]
        tentacle.retract_reveal = tentacle.reveal
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
        self.burst = False
        self.appearance_count = 1

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
        self._spawn_curious(count=self.rng.choices((1, 2, 3, 4, 6), weights=(16, 44, 25, 12, 3), k=1)[0])

    def trigger_sneeze(self):
        self.burst = True
        self._spawn_curious(6)
        for limb in self.pool.tentacles:
            if limb.state == TentacleState.CURIOUS:
                limb.state_time = 0
                limb.target = limb.anchor + (limb.target - limb.anchor) * 2.0
                for segment in limb.segments:
                    segment.length *= 2.0
                limb.spring = 260
                limb.damper = 27
        self._door_requested = 130

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
                self.trigger_curious()
                self._curious_cooldown = self.rng.uniform(60.0, 100.0)

        # Atualiza cada tentáculo ativo
        for tentacle in self.pool.tentacles:
            if tentacle.state != TentacleState.DORMANT:
                self._update_tentacle(tentacle, dt)
        self._separate_tentacles()

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

    def _retract_all(self) -> None:
        for t in self.pool.tentacles:
            if t.state != TentacleState.DORMANT:
                self.pool.release(t)
        self._door_requested = 0.0

    def _update_tentacle(self, tentacle: Tentacle, dt: float) -> None:
        if tentacle.state == TentacleState.CURIOUS and self._door_current < 50.0:
            return
        tentacle.state_time += dt

        if tentacle.state == TentacleState.RETRACTING:
            progress = min(1.0, max(0.0, tentacle.state_time / (.45 if self.burst else 1.5)))
            eased = progress ** 3 * (10 - 15 * progress + 6 * progress * progress)
            tentacle.reveal = tentacle.retract_reveal * (1 - eased)
            if progress >= 1.0:
                tentacle.state = TentacleState.DORMANT
                tentacle.params = dict(STATE_PARAMS["dormant"])
                tentacle.retract_from.clear()
                tentacle.reveal = 0.0
            return

        # Transições de estado
        self._check_state_transition(tentacle)
        if tentacle.state in (TentacleState.RETRACTING, TentacleState.DORMANT):
            return

        # Parâmetros atuais
        p = tentacle.params
        reveal_time = max(0.0, min(1.0, tentacle.state_time / (.16 if self.burst else 1.8)))
        tentacle.reveal = reveal_time ** 3 * (10 - 15 * reveal_time + 6 * reveal_time ** 2)
        max_len = p["max_len"]
        reach_speed = p["reach_speed"]
        target_curl = p["curl"]

        # Spring params
        spring = 380 if self.burst else tentacle.spring
        damper = 30 if self.burst else tentacle.damper

        # Atualiza cada segmento
        for i, seg in enumerate(tentacle.segments):
            if i == 0:
                seg.pos = Vec3(tentacle.anchor)
                seg.vel = Vec3(0)
                continue
            t_param = i / (len(tentacle.segments) - 1) if len(tentacle.segments) > 1 else 0.0

            # Target position para este segmento
            if tentacle.target is not None and reach_speed != 0:
                # Interpola do anchor ao target baseado no progresso do tentáculo
                # Solve the complete curve; reveal samples a growing part of it.
                # The cross section keeps its volume instead of growing from zero.
                seg_progress = t_param
                delta = tentacle.target - tentacle.anchor
                forward = tentacle.reference_front
                a = tentacle.anchor + forward * .22 + Vec3(0, 0, .02)
                b = tentacle.anchor + delta * 1.15 + forward * .08 + Vec3(0, 0, .06 + target_curl * .04)
                u = seg_progress
                v = 1 - u
                target_pos = (tentacle.anchor * (v ** 3) + a * (3 * v * v * u) +
                              b * (3 * v * u * u) + tentacle.target * (u ** 3))
                arch = math.sin(math.pi * t_param)
                phase = tentacle.state_time * (5.0 if self.burst else 1.5) - t_param * (7.5 if self.burst else 2.0) + tentacle.seed * .001
                if self.burst:
                    # A travelling bend with delayed tips, rather than rigid spokes.
                    wave = math.sin(math.pi * t_param) * math.sin(phase)
                    target_pos += Vec3(.065 * wave, .045 * math.cos(phase) * arch,
                                       .075 * math.sin(phase - .7) * arch)
                target_pos += Vec3(
                    math.sin(phase) * 4.0 * tentacle.unit_scale * arch,
                    8.0 * tentacle.unit_scale * arch,
                    12.0 * tentacle.unit_scale * arch,
                )
            else:
                target_pos = tentacle.anchor

            # Jitter impulsivo (twitch aleatório)
            if tentacle.state != TentacleState.CURIOUS and self.rng.random() < tentacle.impulse_chance * dt * 60:
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
            max_dist = max_len * (i + 1) * tentacle.segments[i].length * (2.5 if self.burst else 1)
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
    def _separate_tentacles(self):
        # Preserve embedded roots; solve the visible bodies as tapered spheres.
        active = [t for t in self.pool.tentacles
                  if t.state != TentacleState.DORMANT and t.reveal > .15]
        # Spatial bins discard distant pairs before narrow-phase checks.
        cell = .18
        for _ in range(2):
            bins = {}
            for owner, limb in enumerate(active):
                for i, segment in enumerate(limb.segments[2:], 2):
                    radius = (.072 * (1 - .88*i/(len(limb.segments)-1)) + .008) * limb.girth_scale
                    key = tuple(math.floor(segment.pos[k]/cell) for k in range(3))
                    for x in range(key[0]-1, key[0]+2):
                        for y in range(key[1]-1, key[1]+2):
                            for z in range(key[2]-1, key[2]+2):
                                for other_owner, other, other_radius in bins.get((x,y,z), ()):
                                    if owner == other_owner:
                                        continue
                                    delta = segment.pos - other.pos
                                    squared = delta.lengthSquared()
                                    if squared >= (radius+other_radius)**2:
                                        continue
                                    distance = math.sqrt(squared)
                                    normal = delta/distance if distance > 1e-7 else Vec3(1,0,0)
                                    correction = normal * min(.012, (radius+other_radius-distance)*.5)
                                    segment.pos += correction
                                    other.pos -= correction
                                    closing = (segment.vel-other.vel).dot(normal)
                                    if closing < 0:
                                        segment.vel -= normal*closing*.5
                                        other.vel += normal*closing*.5
                    bins.setdefault(key, []).append((owner, segment, radius))
        for limb in self.pool.tentacles:
            if limb.state != TentacleState.DORMANT:
                self._solve_contacts(limb)

    def _solve_contacts(self, tentacle):
        if not tentacle.contacts:
            return
        # Alternate smoothing, link-length limits and swept-sphere projection.
        # Radii include the suction cups and the mantle, not only the centerline.
        nearby = tentacle.contacts.region([segment.pos for segment in tentacle.segments], .13)
        for _ in range(3):
            for index in range(1, len(tentacle.segments)):
                segment = tentacle.segments[index]
                u = index / (len(tentacle.segments) - 1)
                radius = (.072 * (1 - .88 * u) + .008) * tentacle.girth_scale
                previous = tentacle.segments[index - 1]
                if index + 1 < len(tentacle.segments):
                    midpoint = (previous.pos + tentacle.segments[index + 1].pos) * .5
                    segment.pos += (midpoint - segment.pos) * .18
                delta = segment.pos - previous.pos
                limit = segment.length * .65
                if delta.lengthSquared() > limit * limit:
                    segment.pos = previous.pos + delta.normalized() * limit
                # Mid-link samples prevent a link cutting through a thin door.
                midpoint = (previous.pos + segment.pos) * .5
                projected_mid = tentacle.contacts.project(midpoint, radius, nearby)
                segment.pos += (projected_mid - midpoint)
                before = Vec3(segment.pos)
                segment.pos = tentacle.contacts.project(segment.pos, radius, nearby)
                correction = segment.pos - before
                if correction.lengthSquared() > 1e-12:
                    normal = correction.normalized()
                    incoming = segment.vel.dot(normal)
                    if incoming < 0:
                        segment.vel -= normal * incoming

    def _check_state_transition(self, tentacle: Tentacle) -> None:
        st = tentacle.state
        p = tentacle.params

        if st == TentacleState.CURIOUS:
            if tentacle.state_time > (.95 if self.burst else 4.8):
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
                    self.pool.release(tentacle)

        elif st == TentacleState.SPITTING:
            if tentacle.target:
                dist = (tentacle.target - tentacle.segments[-1].pos).length()
                if dist < 30.0 * tentacle.unit_scale or tentacle.state_time > 1.0:
                    self.pool.release(tentacle)

        elif st == TentacleState.FRENZY:
            # Frenzy mantém até director mandar parar
            pass

        elif st == TentacleState.RETRACTING:
            if tentacle.state_time > 1.2:
                tentacle.state = TentacleState.DORMANT
                tentacle.params = dict(STATE_PARAMS["dormant"])
                tentacle.target = None
                for segment in tentacle.segments:
                    segment.pos = Vec3(tentacle.anchor)
                    segment.vel = Vec3(0)

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
        opening = diff > 0
        speed = 620 if self.burst else 38 + 14 * (self.appearance_count - 1)
        delta = diff * (1.0 - math.exp(-dt * (14 if self.burst else 3 + self.appearance_count * .5)))
        limit = (speed if opening else 38) * dt
        self._door_current += max(-limit, min(limit, delta))
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
        self.appearance_count = count
        active = self.pool.get_available(count)
        for index, t in enumerate(active):
            t.length_scale = self.rng.uniform(1.02, 1.22) if index % 2 == 0 else self.rng.uniform(.60, .78)
            t.girth_scale = self.rng.uniform(.95, 1.10) if index % 2 == 0 else self.rng.uniform(.62, .78)
            for segment in t.segments:
                segment.length = SEGMENT_LENGTH * self.pool.unit_scale * t.length_scale
            t.state = TentacleState.CURIOUS
            # Stagger the pair so the second tentacle follows the first.
            t.state_time = -0.48 * index
            t.params = dict(STATE_PARAMS["curious"])
            # Concept silhouette: crown, side curl, then lower tendrils.
            # Targets have independent depth so the limbs do not form a flat fan.
            offsets = ((-48, 55, 46), (58, 38, -32), (-64, 32, 8),
                       (32, 68, -48), (42, 44, 50), (-30, 76, -40))
            offset = Vec3(*offsets[index % len(offsets)]) * self.pool.unit_scale * t.length_scale
            t.target = t.anchor + offset
        self._door_requested = max(self._door_requested, 85.0)


# ============================================================
# Rendering helper
# ============================================================

def create_tentacle_geometry(
    tentacle: Tentacle,
    parent: NodePath,
    outline_parent: NodePath,
    color: tuple[float, float, float, float] = (0.2, 0.6, 1.0, 0.9),
) -> None:
    """Cria a malha grossa aprovada com poucos anéis e ventosas articuláveis."""
    from panda3d.core import (
        Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
        GeomVertexWriter, LineSegs, Texture,
    )

    vertices, normals, colors, indices = [], [], [], []

    def add_vertex(point, normal, color):
        index = len(vertices)
        vertices.append(point)
        normals.append(normal)
        colors.append(color)
        return index

    def add_triangle(a, b, c):
        indices.extend((a, b, c))

    def add_quad(a, b, c, d):
        add_triangle(a, b, c)
        add_triangle(a, c, d)

    profile = [(0, .044, 0), (.075, .083, -.007), (.15, .071, -.006),
               (.23, .056, .005), (.31, .041, .025), (.39, .023, .056), (.48, .001, .10)]
    profile = [(z * .9, radius * 1.15, bend * 1.15) for z, radius, bend in profile]
    palette = [(.78, .045, .23, 1), (.94, .08, .32, 1), (1, .16, .42, 1),
               (.86, .06, .28, 1), (.60, .025, .15, 1), (.42, .012, .085, 1),
               (.49, .018, .11, 1), (.66, .03, .18, 1)]
    sides = 8
    rings = []
    for z, radius, bend in profile:
        ring = []
        for side in range(sides):
            angle = side * math.tau / sides - math.pi / 8
            ring.append(add_vertex(
                (bend + radius * math.cos(angle), radius * math.sin(angle), z),
                (math.cos(angle), math.sin(angle), 0), palette[side],
            ))
        rings.append(ring)
    for row in range(len(rings) - 1):
        for side in range(sides):
            nxt = (side + 1) % sides
            add_quad(rings[row][side], rings[row][nxt], rings[row + 1][nxt], rings[row + 1][side])
    center = add_vertex((0, 0, 0), (0, 0, -1), (.42, .012, .085, 1))
    for side in range(sides):
        add_triangle(center, rings[0][(side + 1) % sides], rings[0][side])

    # Four raised hexagonal cups sit on the camera-facing side of the mantle.
    for z, body_radius, bend, radius in ((.09, .080, -.007, .026), (.18, .065, 0, .024),
                                         (.275, .047, .017, .020), (.355, .030, .042, .015)):
        z, body_radius, bend, radius = z * .9, body_radius * 1.15, bend * 1.15, radius * 1.1
        base_y = body_radius * math.cos(math.pi / 8)
        cup_rings = []
        for ring_radius, depth, color in (
            (radius, 0.0, (.90, .055, .28, 1)),
            (radius, .025, (1, .28, .52, 1)),
            (radius * .58, .026, (.64, .02, .15, 1)),
            (radius * .45, .006, (.25, .006, .045, 1)),
        ):
            cup = []
            for side in range(6):
                angle = side * math.tau / 6
                point = (bend + ring_radius * math.cos(angle), base_y + depth,
                         z + ring_radius * math.sin(angle))
                cup.append(add_vertex(point, (0, 1, 0), color))
            cup_rings.append(cup)
        for row in range(3):
            for side in range(6):
                nxt = (side + 1) % 6
                add_quad(cup_rings[row][side], cup_rings[row + 1][side],
                         cup_rings[row + 1][nxt], cup_rings[row][nxt])
        cup_center = add_vertex((bend, base_y + .006, z), (0, 1, 0), (.25, .006, .045, 1))
        for side in range(6):
            add_triangle(cup_center, cup_rings[3][(side + 1) % 6], cup_rings[3][side])

    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("procedural-tentacle", fmt, Geom.UHDynamic)
    vw, nw, cw = (GeomVertexWriter(vdata, name) for name in ("vertex", "normal", "color"))
    for vertex, normal, color in zip(vertices, normals, colors):
        vw.addData3(*vertex)
        nw.addData3(*normal)
        cw.addData4f(*color)
    triangles = GeomTriangles(Geom.UHStatic)
    for i in range(0, len(indices), 3):
        triangles.addVertices(*indices[i:i + 3])
    triangles.closePrimitive()
    geom = Geom(vdata)
    geom.addPrimitive(triangles)
    geom_node = GeomNode("procedural-tentacle")
    geom_node.addGeom(geom)
    mesh_node = parent.attachNewNode(geom_node)
    mesh_node.setTwoSided(True)
    mesh_node.setName("procedural-tentacle")
    # A real opaque white texture keeps the alpha-tested outline and exit
    # shader independent from whatever texture the cabinet inherited.
    white = Texture("tentacle-opaque")
    white.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRgba)
    white.setRamImage(bytes((255, 255, 255, 255)))
    mesh_node.setTexture(white, 1)

    outline_node = mesh_node.copyTo(outline_parent)
    outline_node.setName("procedural-tentacle-outline")
    tentacle.mesh_node = mesh_node
    tentacle.outline_mesh_node = outline_node
    tentacle.mesh_vdata = vdata
    # Both shells share the same deforming vertex data. Rewriting a duplicate
    # would double the skinning and collision work without changing the pose.
    tentacle.outline_vdata = vdata
    tentacle.template_vertices = vertices
    tentacle.template_normals = normals
    profile_center = ((0, 0), (.0675, -.00805), (.135, -.0069),
                      (.207, .00575), (.279, .02875), (.351, .0644), (.432, .115))
    for x, y, z in vertices:
        bend = .115
        for (za, xa), (zb, xb) in zip(profile_center, profile_center[1:]):
            if z <= zb:
                bend = xa + (xb - xa) * max(0, (z - za) / (zb - za))
                break
        tentacle.rest_vertices.append((z / .432, (x - bend) * .65, y * .65))
    lines = LineSegs("tentacle-joint-axes")
    lines.setThickness(1.5)
    for color, endpoint in (((1, .15, .15, 1), (.035, 0, 0)),
                            ((.15, 1, .2, 1), (0, .035, 0)),
                            ((.2, .4, 1, 1), (0, 0, .05))):
        lines.setColor(*color)
        lines.moveTo(0, 0, 0)
        lines.drawTo(*endpoint)
    axes = lines.create()
    for index in range(len(tentacle.segments)):
        node = NodePath(axes).copyTo(parent)
        node.setName(f"tentacle-joint-{index}")
        node.setLightOff(1)
        node.setCollideMask(0)
        node.setDepthTest(False)
        node.setDepthWrite(False)
        node.setBin("fixed", 100)
        node.setScale(1.8)
        node.hide()
        tentacle.axis_nodes.append(node)
    # Keep the small source profile so the per-frame curve update stays light.


def update_tentacle_render(tentacle: Tentacle) -> None:
    """Deforma a malha low-poly na curva procedural dos pontos da mola."""
    if not tentacle.mesh_node or not tentacle.segments or not tentacle.mesh_vdata:
        return
    from panda3d.core import GeomVertexRewriter, Mat3, Quat, Vec3

    points = [Vec3(seg.pos) for seg in tentacle.segments]
    nearby = tentacle.contacts.region(points) if tentacle.contacts else []
    # Rotation-minimizing frames: carry the previous transverse axis along
    # the curve, then add distributed twist. No camera-facing/billboard axis.
    frames = []
    front = Vec3(tentacle.reference_front)
    for index, center in enumerate(points):
        tangent = points[min(index + 1, len(points) - 1)] - points[max(0, index - 1)]
        if tangent.lengthSquared() < 1e-10:
            tangent = Vec3(0, 0, 1)
        tangent.normalize()
        front -= tangent * front.dot(tangent)
        if front.lengthSquared() < 1e-6:
            front = Vec3(0, 0, 1) - tangent * tangent.z
        if front.lengthSquared() < 1e-6:
            front = Vec3(1, 0, 0) - tangent * tangent.x
        front.normalize()
        right = front.cross(tangent).normalized()
        u = index / (len(points) - 1)
        twist = (.45 + math.sin(tentacle.state_time * .85 + tentacle.seed * .001) * .3) * u
        transverse_x = right * math.cos(twist) + front * math.sin(twist)
        transverse_y = front * math.cos(twist) - right * math.sin(twist)
        frames.append((center, tangent, transverse_x, transverse_y))
        orientation = Mat3(*transverse_x, *transverse_y, *tangent)
        rotation = Quat()
        rotation.setFromMatrix(orientation)
        tentacle.segments[index].rot = rotation
        if index < len(tentacle.axis_nodes):
            tentacle.axis_nodes[index].setPos(center)
            tentacle.axis_nodes[index].setQuat(rotation)
    tentacle.frames = frames
    cache = {}

    def frame_at(t: float):
        # Slide the visible length out of the opening while preserving radius.
        sample = max(0.0, min(1.0, t)) * tentacle.reveal * (len(points) - 1)
        index = min(len(points) - 2, int(sample))
        alpha = sample - index
        p0, p1 = points[max(0, index - 1)], points[index]
        p2, p3 = points[index + 1], points[min(len(points) - 1, index + 2)]
        a = -p0 + p2
        b = p0 * 2 - p1 * 5 + p2 * 4 - p3
        c = -p0 + p1 * 3 - p2 * 3 + p3
        center = (p1 * 2 + a * alpha + b * alpha ** 2 + c * alpha ** 3) * .5
        tangent = (a + b * (2 * alpha) + c * (3 * alpha ** 2)) * .5
        if tangent.lengthSquared() < 1e-10:
            tangent = frames[index][1]
        tangent.normalize()
        right = frames[index][2] * (1 - alpha) + frames[index + 1][2] * alpha
        right -= tangent * right.dot(tangent)
        right.normalize()
        front = tangent.cross(right).normalized()
        return center, tangent, right, front

    def deform(vdata) -> None:
        vertex_writer = GeomVertexRewriter(vdata, "vertex")
        normal_writer = GeomVertexRewriter(vdata, "normal")
        for (u, x, y), local_normal in zip(tentacle.rest_vertices, tentacle.template_normals):
            if u not in cache:
                frame = frame_at(u)
                center = frame[0]
                radius = .09*tentacle.girth_scale
                ring_boxes = [box for box in nearby
                              if box.model_low.x-radius <= center.x <= box.model_high.x+radius
                              and box.model_low.y-radius <= center.y <= box.model_high.y+radius
                              and box.model_low.z-radius <= center.z <= box.model_high.z+radius]
                cache[u] = (frame, ring_boxes)
            (center, tangent, right, front), ring_boxes = cache[u]
            position = center + (right * x + front * y) * tentacle.girth_scale
            for obstacle in ring_boxes:
                position = obstacle.project(position, .002)
            nx, ny, nz = local_normal
            normal = right * nx + front * ny + tangent * nz
            if normal.lengthSquared() > 1e-10:
                normal.normalize()
            vertex_writer.setData3(position)
            normal_writer.setData3(normal)

    deform(tentacle.mesh_vdata)

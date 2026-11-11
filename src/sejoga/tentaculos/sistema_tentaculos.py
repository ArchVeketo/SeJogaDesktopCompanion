"""Sistema procedural de tentáculos — SeJogaDesktopCompanion.

Tentáculos como chains de segmentos rígidos (low-poly), sem skin.
Cada tentáculo = lista de TentacleSegment com mola-amortecedor + overshoot impulsivo.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import pairwise

from panda3d.core import GeomVertexRewriter, NodePath, Quat, Vec3

from sejoga.nucleo.esqueleto import IdlePersonality, Rig
from sejoga.tentaculos import coreografia_porta as coreo
from sejoga.tentaculos.ondulacao import (
    FASE_POR_SEMENTE_RAD,
    ONDULACAO_CALMA,
    ONDULACAO_ESPIRRO,
    ONDULACAO_POR_TEMPERAMENTO,
    OndulacaoTuning,
    deslocamento_ondulante,
)
from sejoga.tentaculos.restricoes_tentaculos import TentacleContacts

# Tolerância ao tratar a base da frente como degenerada (frente quase vertical).
EPSILON_BASE_FRENTE = 1e-6

# ============================================================
# Configuração visual / física
# ============================================================

DEFAULT_SEGMENTS = 24  # segmentos por tentáculo
SEGMENT_LENGTH = 8.0  # px por segmento
BASE_WIDTH = 8.0  # largura na base
TIP_WIDTH = 2.0  # largura na ponta
SUCKER_COUNT = 4  # ventosas por segmento (visual)

# Parâmetros de mola por personalidade
SPRING_PARAMS = {
    IdlePersonality.CALM: dict(
        spring=80.0, damper=12.0, impulse_chance=0.01, impulse_strength=8.0
    ),
    IdlePersonality.CURIOUS: dict(
        spring=100.0, damper=8.0, impulse_chance=0.03, impulse_strength=15.0
    ),
    IdlePersonality.PLAYFUL: dict(
        spring=150.0, damper=6.0, impulse_chance=0.08, impulse_strength=30.0
    ),
    IdlePersonality.SHY: dict(
        spring=60.0, damper=15.0, impulse_chance=0.005, impulse_strength=5.0
    ),
    IdlePersonality.CONFIDENT: dict(
        spring=120.0, damper=10.0, impulse_chance=0.02, impulse_strength=20.0
    ),
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
    "dormant": dict(max_len=0.0, reach_speed=0.0, curl=0.0, jitter=0.0),
    "curious": dict(max_len=0.40, reach_speed=400.0, curl=0.1, jitter=0.05),
    "reaching": dict(max_len=1.0, reach_speed=900.0, curl=0.2, jitter=0.1),
    "grabbing": dict(max_len=1.0, reach_speed=600.0, curl=0.85, jitter=0.05),
    "spitting": dict(max_len=1.15, reach_speed=-800.0, curl=0.0, jitter=0.15),
    "frenzy": dict(max_len=1.2, reach_speed=2200.0, curl=0.4, jitter=0.35),
    "retracting": dict(max_len=0.0, reach_speed=-600.0, curl=0.0, jitter=0.0),
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
    curl: float = 0.0  # 0=reto, 1=enrolado
    sucker_phase: float = 0.0  # fase visual das ventosas

    # Para rendering: nó Panda3D correspondente (criado sob demanda)
    node: NodePath | None = None
    outline_node: NodePath | None = None


class TentacleState(StrEnum):
    """Estados do ciclo de vida de um tentáculo."""

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
    anchor: Vec3  # ponto de ancoragem (spawn point)
    target: Vec3 | None = None  # target no espaço mundial
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
    mesh_node: NodePath | None = None
    outline_mesh_node: NodePath | None = None
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
    contacts: TentacleContacts | None = None

    length_scale: float = 1.0
    girth_scale: float = 1.0
    speaker_throw: bool = False

    # Ondulação: tuning do temperamento atual, relógio próprio (sem salto ao
    # recolher) e parâmetros do estado anterior, usados enquanto recolhe.
    ondulacao: OndulacaoTuning = ONDULACAO_CALMA
    tempo_onda: float = 0.0
    params_antes_recolher: dict = field(default_factory=dict)

    # Saída pela porta (temperamento) e ajustes que a coreografia impõe a um
    # tentáculo específico; None = usa o padrão do estado.
    saida: coreo.SaidaTuning = coreo.SAIDA_CALMA
    duracao_revelacao_s: float | None = None
    duracao_recolher_s: float | None = None
    mola_forcada: tuple[float, float] | None = None

    # Buffers de render reaproveitados entre frames (evita recriar o
    # GeomVertexRewriter e recomputar a curva quando a pose não mudou).
    _vertex_rewriter: GeomVertexRewriter | None = None
    _normal_rewriter: GeomVertexRewriter | None = None
    _last_render_signature: tuple | None = None

    def visible_tip(self):
        """Devolve a ponta visível do tentáculo."""
        sample = max(0.0, min(1.0, self.reveal)) * (len(self.segments) - 1)
        index = min(len(self.segments) - 2, int(sample))
        blend = sample - index
        return (
            self.segments[index].pos * (1 - blend)
            + self.segments[index + 1].pos * blend
        )

    def __post_init__(self):
        """Inicia os segmentos e o estado derivado."""
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
        rng: random.Random | None = None,
        unit_scale: float = 1.0,
    ):
        """Monta o pool de tentáculos ancorados nos pontos dados."""
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
            t.duracao_revelacao_s = None
            t.duracao_recolher_s = None
            t.mola_forcada = None
        return selected

    def release(self, tentacle: Tentacle) -> None:
        """Devolve tentáculo ao pool (retract -> dormant)."""
        if tentacle.state in (TentacleState.DORMANT, TentacleState.RETRACTING):
            return
        tentacle.retract_from = [Vec3(segment.pos) for segment in tentacle.segments]
        tentacle.retract_reveal = tentacle.reveal
        # Mantém alvo e parâmetros: o corpo continua ondulando enquanto entra pela porta.
        tentacle.params_antes_recolher = dict(tentacle.params)
        tentacle.state = TentacleState.RETRACTING
        tentacle.state_time = 0.0
        tentacle.params = dict(STATE_PARAMS["retracting"])

    def release_all(self) -> None:
        """Recolhe todos os tentáculos ativos."""
        for t in self.tentacles:
            if t.state != TentacleState.DORMANT:
                self.release(t)

    def update_personality(self, personality: IdlePersonality) -> None:
        """Ajusta a ondulação dos tentáculos ao temperamento."""
        sp = SPRING_PARAMS[personality]
        for t in self.tentacles:
            t.spring = sp["spring"]
            t.damper = sp["damper"]
            t.impulse_chance = sp["impulse_chance"]
            t.impulse_strength = sp["impulse_strength"]
            t.ondulacao = ONDULACAO_POR_TEMPERAMENTO[personality]
            t.saida = coreo.SAIDA_POR_TEMPERAMENTO[personality]


# ============================================================
# Director — alto nível
# ============================================================


class TentacleDirector:
    """Comportamento de alto nível: decide o que os tentáculos fazem."""

    def __init__(  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        self,
        pool: TentaclePool,
        rig: Rig,
        model_np: NodePath,
        outline_np: NodePath,
        door_node: NodePath,
        rng: random.Random | None = None,
    ):
        """Monta o diretor que decide quando e como os tentáculos agem."""
        self.pool = pool
        self.rig = rig
        self.model_np = model_np
        self.outline_np = outline_np
        self.door_node = door_node
        self.rng = rng or random.Random()

        # Estado
        self.mouse_pos: Vec3 | None = None
        self.mouse_vel: Vec3 = Vec3(0, 0, 0)
        self.frenzy_mode = False
        self.frenzy_time = 0.0
        self.swallowing = False
        self.swallow_target: Vec3 | None = None
        self.swallow_time = 0.0

        # Door control
        self._door_requested = 0.0
        self._door_current = 0.0
        self.burst = False
        self.appearance_count = 1

        # Coreografia porta x tentáculos: empurrador/puxador, ângulo imposto à porta
        # e pedido de porta vindo do rig (outra animação dona da porta).
        self.coreografia = coreo.CoreografiaPorta()
        self._atuador: Tentacle | None = None
        self._alvo_atuador: Vec3 | None = None
        self._angulo_coreografado: float | None = None
        self._pedido_porta_externo = 0.0
        self._borda_porta_local: Vec3 | None = None
        self.speaker_throw_remaining = 0.0
        self.speaker_throw_limbs: list[Tentacle] = []

        # Cooldowns
        # Preserva a sequência das outras coreografias com as sementes existentes.
        self.rng.uniform(60.0, 100.0)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def set_mouse(self, pos: Vec3, vel: Vec3) -> None:
        """Atualiza a posição e a velocidade do mouse."""
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
        self._spawn_curious(
            count=self.rng.choices((1, 2, 3, 4, 6), weights=(16, 44, 25, 12, 3), k=1)[
                0
            ],
            coreografar=True,
        )

    def trigger_speaker_throw(self):
        """Dispara os tentáculos que arremessam a caixa de som."""
        self.speaker_throw_remaining = 1.5
        self.speaker_throw_limbs = self._spawn_curious(3)
        for index, limb in enumerate(self.speaker_throw_limbs):
            limb.speaker_throw = True
            limb.state_time = -0.08 * index
            limb.params["max_len"] = 1.1
            for segment in limb.segments:
                segment.length *= 1.2  # intencional: loop de 1 statement compacto

    def trigger_sneeze(self):
        """Dispara os tentáculos do espirro."""
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
        self._door_requested = coreo.SAIDA_ESPIRRO.angulo_empurrao_graus

    def update(self, dt: float, personality: IdlePersonality) -> None:  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        """Atualiza todos os tentáculos e decide transições."""
        dt = min(dt, 0.05)  # clamp para estabilidade
        if self.speaker_throw_remaining > 0:
            self.speaker_throw_remaining = max(0, self.speaker_throw_remaining - dt)
            if self.speaker_throw_remaining == 0:
                for limb in self.speaker_throw_limbs:
                    limb.speaker_throw = False
                    self.pool.release(limb)
                self.speaker_throw_limbs = []

        # Atualiza pool
        self.pool.update_personality(personality)
        if self._outro_dono_da_porta():
            self._cancelar_coreografia()

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

        # Atualiza cada tentáculo ativo
        for tentacle in self.pool.tentacles:
            if tentacle.state != TentacleState.DORMANT:
                self._update_tentacle(tentacle, dt)
        self._separate_tentacles()

        # Door sync
        self._avancar_coreografia(dt)
        self._update_door(dt)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _spawn_frenzy(self) -> None:
        active = self.pool.get_available(7)  # 6-8 tentáculos
        for t in active:
            t.state = TentacleState.FRENZY
            t.state_time = 0.0
            t.params = dict(STATE_PARAMS["frenzy"])
            t.target = self._random_target_near_mouse(radius=120.0)
        # Porta aberta total
        self._door_requested = 135.0

    def _spawn_swallow(self) -> None:
        active = self.pool.get_available(6)
        for t in active:
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

    def encerrar_espiada(self, *, interromper: bool) -> None:
        """Recolhe os curiosos, deixando o atuador concluir o ciclo da porta."""
        if interromper:
            self._retract_all()
            return
        for tentaculo in self.pool.tentacles:
            if tentaculo.state is TentacleState.CURIOUS and tentaculo is not self._atuador:
                self.pool.release(tentaculo)

    def _retract_all(self) -> None:
        self._cancelar_coreografia()
        for t in self.pool.tentacles:
            if t.state != TentacleState.DORMANT:
                self.pool.release(t)
        self._door_requested = 0.0

    def _update_tentacle(self, tentacle: Tentacle, dt: float) -> None:  # noqa: PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        # O atuador da coreografia (empurra/puxa a porta) não espera a porta abrir.
        if (
            tentacle.state == TentacleState.CURIOUS
            and tentacle is not self._atuador
            and self._door_current < coreo.LIMIAR_SAIDA_PORTA_GRAUS
        ):
            return
        tentacle.state_time += dt

        if tentacle.state == TentacleState.RETRACTING:
            duracao_recolher = 1.5
            if self.burst:
                duracao_recolher = 0.45
            elif tentacle.duracao_recolher_s is not None:
                duracao_recolher = tentacle.duracao_recolher_s
            progress = min(1.0, max(0.0, tentacle.state_time / duracao_recolher))
            eased = progress**3 * (10 - 15 * progress + 6 * progress * progress)
            tentacle.reveal = tentacle.retract_reveal * (1 - eased)
            if progress >= 1.0:
                tentacle.state = TentacleState.DORMANT
                tentacle.params = dict(STATE_PARAMS["dormant"])
                tentacle.retract_from.clear()
                tentacle.target = None
                tentacle.reveal = 0.0
                return
            if tentacle.params_antes_recolher:
                self._atualizar_segmentos(tentacle, dt, tentacle.params_antes_recolher)
            return

        # Transições de estado
        self._check_state_transition(tentacle)
        if tentacle.state in (TentacleState.RETRACTING, TentacleState.DORMANT):
            return

        # Parâmetros atuais
        p = tentacle.params
        duracao_revelacao = tentacle.duracao_revelacao_s
        if duracao_revelacao is None:
            duracao_revelacao = tentacle.saida.duracao_s
        reveal_time = max(
            0.0,
            min(
                1.0,
                tentacle.state_time
                / (
                    0.30
                    if getattr(tentacle, "speaker_throw", False)
                    else coreo.SAIDA_ESPIRRO.duracao_s
                    if self.burst
                    else duracao_revelacao
                ),
            ),
        )
        tentacle.reveal = reveal_time**3 * (10 - 15 * reveal_time + 6 * reveal_time**2)
        self._atualizar_segmentos(tentacle, dt, p)

    def _atualizar_segmentos(self, tentacle: Tentacle, dt: float, p: dict) -> None:  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        """Mola dos segmentos rumo à curva-alvo, com a onda da base à ponta."""
        max_len = p["max_len"]
        reach_speed = p["reach_speed"]
        target_curl = p["curl"]
        tentacle.tempo_onda += dt

        # Spring params
        spring = (
            190
            if getattr(tentacle, "speaker_throw", False)
            else 380
            if self.burst
            else tentacle.spring
        )
        damper = (
            24
            if getattr(tentacle, "speaker_throw", False)
            else 30
            if self.burst
            else tentacle.damper
        )
        if tentacle.mola_forcada is not None:
            spring, damper = tentacle.mola_forcada

        # Atualiza cada segmento
        for i, seg in enumerate(tentacle.segments):
            if i == 0:
                seg.pos = Vec3(tentacle.anchor)
                seg.vel = Vec3(0)
                continue
            t_param = (
                i / (len(tentacle.segments) - 1) if len(tentacle.segments) > 1 else 0.0
            )

            # Target position para este segmento
            if tentacle.target is not None and reach_speed != 0:
                # Interpola do anchor ao target baseado no progresso do tentáculo
                # Solve the complete curve; reveal samples a growing part of it.
                # The cross section keeps its volume instead of growing from zero.
                seg_progress = t_param
                delta = tentacle.target - tentacle.anchor
                lateral, forward, up = _base_frente(tentacle)
                a = tentacle.anchor + forward * 0.22 + Vec3(0, 0, 0.02)
                b = (
                    tentacle.anchor
                    + delta * 1.15
                    + forward * 0.08
                    + Vec3(0, 0, 0.06 + target_curl * 0.04)
                )
                u = seg_progress
                v = 1 - u
                target_pos = (
                    tentacle.anchor * (v**3)
                    + a * (3 * v * v * u)
                    + b * (3 * v * u * u)
                    + tentacle.target * (u**3)
                )
                arch = math.sin(math.pi * t_param)
                # Onda serpenteante da base à ponta, no plano da frente da cabeça.
                # O espirro usa a mesma onda com intensidade de rajada.
                onda_lateral, onda_cima = deslocamento_ondulante(
                    ONDULACAO_ESPIRRO if self.burst else tentacle.ondulacao,
                    t_param,
                    tentacle.tempo_onda,
                    tentacle.seed * FASE_POR_SEMENTE_RAD,
                )
                escala_onda = tentacle.unit_scale * tentacle.length_scale
                target_pos += lateral * (onda_lateral * escala_onda) + up * (
                    onda_cima * escala_onda
                )
                target_pos += forward * (8.0 * tentacle.unit_scale * arch) + up * (
                    12.0 * tentacle.unit_scale * arch
                )
            else:
                target_pos = tentacle.anchor

            # Jitter impulsivo (twitch aleatório)
            if (
                tentacle.state not in (TentacleState.CURIOUS, TentacleState.RETRACTING)
                and self.rng.random() < tentacle.impulse_chance * dt * 60
            ):
                impulse = Vec3(
                    self.rng.uniform(-1, 1)
                    * tentacle.impulse_strength
                    * tentacle.unit_scale,
                    self.rng.uniform(-1, 1)
                    * tentacle.impulse_strength
                    * tentacle.unit_scale,
                    self.rng.uniform(-1, 1)
                    * tentacle.impulse_strength
                    * tentacle.unit_scale
                    * 0.5,
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
            max_dist = (
                max_len
                * (i + 1)
                * tentacle.segments[i].length
                * (2.5 if self.burst else 1)
            )
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

    def _separate_tentacles(self):  # noqa: C901  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        # Preserve embedded roots; solve the visible bodies as tapered spheres.
        active = [
            t
            for t in self.pool.tentacles
            if t.state != TentacleState.DORMANT and t.reveal > 0.15
        ]
        # Spatial bins discard distant pairs before narrow-phase checks.
        cell = 0.18
        for _ in range(2):  # noqa: PLR1702  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
            bins = {}
            for owner, limb in enumerate(active):
                for i, segment in enumerate(limb.segments[2:], 2):
                    radius = (
                        0.072 * (1 - 0.88 * i / (len(limb.segments) - 1)) + 0.008
                    ) * limb.girth_scale
                    key = tuple(math.floor(segment.pos[k] / cell) for k in range(3))
                    for x in range(key[0] - 1, key[0] + 2):
                        for y in range(key[1] - 1, key[1] + 2):
                            for z in range(key[2] - 1, key[2] + 2):
                                for other_owner, other, other_radius in bins.get(
                                    (x, y, z), ()
                                ):
                                    if owner == other_owner:
                                        continue
                                    delta = segment.pos - other.pos
                                    squared = delta.lengthSquared()
                                    if squared >= (radius + other_radius) ** 2:
                                        continue
                                    distance = math.sqrt(squared)
                                    normal = (
                                        delta / distance
                                        if distance > 1e-7
                                        else Vec3(1, 0, 0)
                                    )
                                    correction = normal * min(
                                        0.012, (radius + other_radius - distance) * 0.5
                                    )
                                    segment.pos += correction
                                    other.pos -= correction
                                    closing = (segment.vel - other.vel).dot(normal)
                                    if closing < 0:
                                        segment.vel -= normal * closing * 0.5
                                        other.vel += normal * closing * 0.5
                    bins.setdefault(key, []).append((owner, segment, radius))
        for limb in self.pool.tentacles:
            if limb.state != TentacleState.DORMANT:
                self._solve_contacts(limb)

    def _solve_contacts(self, tentacle):
        if not tentacle.contacts:
            return
        # Alternate smoothing, link-length limits and swept-sphere projection.
        # Radii include the suction cups and the mantle, not only the centerline.
        nearby = tentacle.contacts.region(
            [segment.pos for segment in tentacle.segments], 0.13
        )
        for _ in range(3):  # noqa: PLR1702  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
            for index in range(1, len(tentacle.segments)):
                segment = tentacle.segments[index]
                u = index / (len(tentacle.segments) - 1)
                radius = (0.072 * (1 - 0.88 * u) + 0.008) * tentacle.girth_scale
                previous = tentacle.segments[index - 1]
                if index + 1 < len(tentacle.segments):
                    midpoint = (previous.pos + tentacle.segments[index + 1].pos) * 0.5
                    segment.pos += (midpoint - segment.pos) * 0.18
                delta = segment.pos - previous.pos
                limit = segment.length * 0.65
                if delta.lengthSquared() > limit * limit:
                    segment.pos = previous.pos + delta.normalized() * limit
                # Mid-link samples prevent a link cutting through a thin door.
                midpoint = (previous.pos + segment.pos) * 0.5
                projected_mid = tentacle.contacts.project(midpoint, radius, nearby)
                segment.pos += projected_mid - midpoint
                before = Vec3(segment.pos)
                segment.pos = tentacle.contacts.project(segment.pos, radius, nearby)
                correction = segment.pos - before
                if correction.lengthSquared() > 1e-12:
                    normal = correction.normalized()
                    incoming = segment.vel.dot(normal)
                    if incoming < 0:
                        segment.vel -= normal * incoming

    def _check_state_transition(self, tentacle: Tentacle) -> None:  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        st = tentacle.state

        if st == TentacleState.CURIOUS:
            # O atuador só é solto pela coreografia.
            if tentacle is not self._atuador and tentacle.state_time > (
                0.95 if self.burst else 4.8
            ):
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

        elif st == TentacleState.RETRACTING and tentacle.state_time > 1.2:
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
        if self._angulo_coreografado is not None:
            # Porta presa à coreografia (empurrão, esquecimento, puxão): sem suavização própria.
            self._door_current = self._angulo_coreografado
            if self.door_node:
                self.door_node.setH(self._door_current)
            return
        # Suaviza abertura/fechamento da porta
        diff = self._door_requested - self._door_current
        opening = diff > 0
        speed = 620 if self.burst else 38 + 14 * (self.appearance_count - 1)
        if getattr(self, "music_ejection", False) and opening:
            speed = max(speed, 180)
        delta = diff * (
            1.0
            - math.exp(
                -dt
                * (
                    14
                    if self.burst or getattr(self, "music_ejection", False)
                    else 3 + self.appearance_count * 0.5
                )
            )
        )
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

    def _spawn_curious(self, count: int, coreografar: bool = False) -> list[Tentacle]:
        self.appearance_count = count
        active = self.pool.get_available(count)
        for index, t in enumerate(active):
            t.length_scale = (
                self.rng.uniform(1.02, 1.22)
                if index % 2 == 0
                else self.rng.uniform(0.60, 0.78)
            )
            t.girth_scale = (
                self.rng.uniform(0.95, 1.10)
                if index % 2 == 0
                else self.rng.uniform(0.62, 0.78)
            )
            for segment in t.segments:
                segment.length = SEGMENT_LENGTH * self.pool.unit_scale * t.length_scale
            t.state = TentacleState.CURIOUS
            # Stagger the pair so the second tentacle follows the first.
            t.state_time = -t.saida.escalonamento_s * index
            t.params = dict(STATE_PARAMS["curious"])
            # Concept silhouette: crown, side curl, then lower tendrils.
            # Targets have independent depth so the limbs do not form a flat fan.
            offsets = (
                (-48, 55, 46),
                (58, 38, -32),
                (-64, 32, 8),
                (32, 68, -48),
                (42, 44, 50),
                (-30, 76, -40),
            )
            # Offsets autorais (x lateral, y frente, z cima) seguem a frente da cabeça,
            # não o espaço do modelo, que já vem com o giro assado no asset.
            lateral, frente, cima = _base_frente(t)
            x, y, z = offsets[index % len(offsets)]
            offset = (
                (lateral * x + frente * y + cima * z)
                * self.pool.unit_scale
                * t.length_scale
            )
            t.target = t.anchor + offset
        self._door_requested = max(self._door_requested, 85.0)
        if coreografar and active:
            self._iniciar_empurrao(active[0])
        return active

    # ------------------------------------------------------------------
    # Coreografia tentáculos x porta
    # ------------------------------------------------------------------

    def _outro_dono_da_porta(self) -> bool:
        """Rajada, caixa de som, fúria, engolir ou pedido do rig: a porta não é nossa."""
        return (
            self.burst
            or getattr(self, "music_ejection", False)
            or self.frenzy_mode
            or self.swallowing
            or self.speaker_throw_remaining > 0
            or self._pedido_porta_externo > coreo.LIMIAR_PEDIDO_EXTERNO_GRAUS
        )

    def _cancelar_coreografia(self) -> None:
        """Devolve a porta ao comportamento normal (pedido suavizado)."""
        self.coreografia.cancelar()
        self._angulo_coreografado = None
        if self._atuador is not None:
            self._atuador.mola_forcada = None
        self._atuador = None
        self._alvo_atuador = None

    def _iniciar_empurrao(self, empurrador: Tentacle) -> None:
        """O primeiro tentáculo sorteado empurra a porta, se ela estiver parada e fechada."""
        fase = self.coreografia.fase
        if fase is not coreo.FasePorta.FECHADA:
            # Aparição durante a coreografia (esquecida, puxando...): volta ao normal.
            if (
                fase is not coreo.FasePorta.ABERTA
                and fase is not coreo.FasePorta.EMPURRANDO
            ):
                self._cancelar_coreografia()
            return
        if (
            self._outro_dono_da_porta()
            or self._door_current >= coreo.LIMIAR_PORTA_FECHADA_GRAUS
        ):
            return
        borda = self._ponto_borda_porta()
        if borda is None:
            return
        self._atuador = empurrador
        self._alvo_atuador = empurrador.target
        self.coreografia.iniciar_empurrao()

    def _avancar_coreografia(self, dt: float) -> None:
        if self.coreografia.fase is coreo.FasePorta.FECHADA:
            return
        atuador = self._atuador
        fase = self.coreografia.fase
        if fase is coreo.FasePorta.EMPURRANDO and (
            atuador is None
            or atuador.state in (TentacleState.DORMANT, TentacleState.RETRACTING)
        ):
            self._cancelar_coreografia()
            return
        passo = self.coreografia.avancar(
            dt,
            revelacao_atuador=atuador.reveal if atuador is not None else 0.0,
            angulo_porta=self._door_current,
            ha_ativos=any(
                t.state != TentacleState.DORMANT for t in self.pool.tentacles
            ),
            angulo_empurrao=atuador.saida.angulo_empurrao_graus
            if atuador is not None
            else 0.0,
        )
        self._angulo_coreografado = passo.angulo_porta
        if passo.fim_empurrao and atuador is not None:
            # Empurrão feito: o tentáculo volta ao alvo comum de qualquer curioso.
            atuador.target = self._alvo_atuador
            self._atuador = None
            self._alvo_atuador = None
        if passo.chamar_puxador:
            self._chamar_puxador()
        if passo.soltar_puxador and atuador is not None:
            atuador.mola_forcada = None
            atuador.duracao_recolher_s = coreo.VOLTA_PUXADOR_S
            self.pool.release(atuador)
            self._atuador = None
        self._apontar_atuador()

    def _apontar_atuador(self) -> None:
        """Mira o atuador na borda livre da porta, que se move com ela."""
        atuador = self._atuador
        borda = self._ponto_borda_porta()
        if atuador is None or borda is None:
            return
        if self.coreografia.fase is coreo.FasePorta.EMPURRANDO:
            # A ponta visível está em `reveal` da curva: estende o alvo para que a
            # ponta chegue à borda ao fim do empurrão (aproximação linear).
            atuador.target = (
                atuador.anchor + (borda - atuador.anchor) / coreo.REVELACAO_FIM_EMPURRAO
            )
        else:
            atuador.target = borda

    def _chamar_puxador(self) -> None:
        disponiveis = self.pool.get_available(1)
        if not disponiveis:
            self._cancelar_coreografia()
            return
        puxador = disponiveis[0]
        puxador.length_scale = 1.0
        puxador.girth_scale = 1.0
        for segmento in puxador.segments:
            segmento.length = SEGMENT_LENGTH * self.pool.unit_scale
        puxador.state_time = 0.0
        puxador.params = dict(STATE_PARAMS["curious"])
        puxador.params["max_len"] = coreo.ALCANCE_PUXADOR
        puxador.duracao_revelacao_s = coreo.TEMPO_ALCANCE_PUXAO_S
        puxador.mola_forcada = (coreo.MOLA_PUXADOR, coreo.AMORTECEDOR_PUXADOR)
        self._atuador = puxador

    def _ponto_borda_porta(self) -> Vec3 | None:
        """Borda livre da porta (oposta à dobradiça, na altura do meio), no espaço do modelo."""
        if not self.door_node:
            return None
        if self._borda_porta_local is None:
            limites = self.door_node.getTightBounds(self.door_node)
            if not limites:
                return None
            baixo, alto = limites
            centro = (baixo + alto) * 0.5
            # A largura é o maior lado horizontal; a dobradiça fica na origem do nó.
            eixo = 0 if (alto.x - baixo.x) >= (alto.y - baixo.y) else 1
            extremo = alto[eixo] if abs(alto[eixo]) >= abs(baixo[eixo]) else baixo[eixo]
            borda = Vec3(centro)
            borda[eixo] = extremo
            self._borda_porta_local = borda
        return self.model_np.getRelativePoint(self.door_node, self._borda_porta_local)


def _base_frente(tentacle: Tentacle) -> tuple[Vec3, Vec3, Vec3]:
    """Base ortonormal (lateral, frente, cima) da cabeça no espaço do modelo.

    A frente vem do nó da cabeça e pode ter pitch; a lateral sai do eixo Z do
    modelo e o cima é recalculado para ficar perpendicular à frente.
    """
    frente = Vec3(tentacle.reference_front)
    if frente.lengthSquared() < EPSILON_BASE_FRENTE:
        frente = Vec3(0, 1, 0)
    frente.normalize()
    lateral = frente.cross(Vec3(0, 0, 1))
    if lateral.lengthSquared() < EPSILON_BASE_FRENTE:
        # Frente vertical: a lateral do modelo (+X) substitui o produto degenerado.
        lateral = Vec3(1, 0, 0)
    lateral.normalize()
    return lateral, frente, lateral.cross(frente)


# ============================================================
# Rendering helper
# ============================================================


def create_tentacle_geometry(  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
    tentacle: Tentacle,
    parent: NodePath,
    outline_parent: NodePath,
    color: tuple[float, float, float, float] = (0.2, 0.6, 1.0, 0.9),
) -> None:
    """Cria a malha grossa aprovada com poucos anéis e ventosas articuláveis."""
    from panda3d.core import (
        Geom,
        GeomNode,
        GeomTriangles,
        GeomVertexData,
        GeomVertexFormat,
        GeomVertexWriter,
        LineSegs,
        Texture,
    )

    vertices: list = []
    normals: list = []
    colors: list = []
    indices: list[int] = []

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

    profile = [
        (0, 0.044, 0),
        (0.075, 0.083, -0.007),
        (0.15, 0.071, -0.006),
        (0.23, 0.056, 0.005),
        (0.31, 0.041, 0.025),
        (0.39, 0.023, 0.056),
        (0.48, 0.001, 0.10),
    ]
    profile = [(z * 0.9, radius * 1.15, bend * 1.15) for z, radius, bend in profile]
    palette = [
        (0.78, 0.045, 0.23, 1),
        (0.94, 0.08, 0.32, 1),
        (1, 0.16, 0.42, 1),
        (0.86, 0.06, 0.28, 1),
        (0.60, 0.025, 0.15, 1),
        (0.42, 0.012, 0.085, 1),
        (0.49, 0.018, 0.11, 1),
        (0.66, 0.03, 0.18, 1),
    ]
    sides = 8
    rings = []
    for z, radius, bend in profile:
        ring = []
        for side in range(sides):
            angle = side * math.tau / sides - math.pi / 8
            ring.append(
                add_vertex(
                    (bend + radius * math.cos(angle), radius * math.sin(angle), z),
                    (math.cos(angle), math.sin(angle), 0),
                    palette[side],
                )
            )
        rings.append(ring)
    for row in range(len(rings) - 1):
        for side in range(sides):
            nxt = (side + 1) % sides
            add_quad(
                rings[row][side],
                rings[row][nxt],
                rings[row + 1][nxt],
                rings[row + 1][side],
            )
    center = add_vertex((0, 0, 0), (0, 0, -1), (0.42, 0.012, 0.085, 1))
    for side in range(sides):
        add_triangle(center, rings[0][(side + 1) % sides], rings[0][side])

    # Four raised hexagonal cups sit on the camera-facing side of the mantle.
    for z, body_radius, bend, radius in (
        (0.09, 0.080, -0.007, 0.026),
        (0.18, 0.065, 0, 0.024),
        (0.275, 0.047, 0.017, 0.020),
        (0.355, 0.030, 0.042, 0.015),
    ):
        z, body_radius, bend, radius = (
            z * 0.9,
            body_radius * 1.15,
            bend * 1.15,
            radius * 1.1,
        )
        base_y = body_radius * math.cos(math.pi / 8)
        cup_rings = []
        for ring_radius, depth, color in (
            (radius, 0.0, (0.90, 0.055, 0.28, 1)),
            (radius, 0.025, (1, 0.28, 0.52, 1)),
            (radius * 0.58, 0.026, (0.64, 0.02, 0.15, 1)),
            (radius * 0.45, 0.006, (0.25, 0.006, 0.045, 1)),
        ):
            cup = []
            for side in range(6):
                angle = side * math.tau / 6
                point = (
                    bend + ring_radius * math.cos(angle),
                    base_y + depth,
                    z + ring_radius * math.sin(angle),
                )
                cup.append(add_vertex(point, (0, 1, 0), color))
            cup_rings.append(cup)
        for row in range(3):
            for side in range(6):
                nxt = (side + 1) % 6
                add_quad(
                    cup_rings[row][side],
                    cup_rings[row + 1][side],
                    cup_rings[row + 1][nxt],
                    cup_rings[row][nxt],
                )
        cup_center = add_vertex(
            (bend, base_y + 0.006, z), (0, 1, 0), (0.25, 0.006, 0.045, 1)
        )
        for side in range(6):
            add_triangle(cup_center, cup_rings[3][(side + 1) % 6], cup_rings[3][side])

    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("procedural-tentacle", fmt, Geom.UHDynamic)
    vw, nw, cw = (
        GeomVertexWriter(vdata, name) for name in ("vertex", "normal", "color")
    )
    for vertex, normal, color in zip(vertices, normals, colors, strict=True):
        vw.addData3(*vertex)
        nw.addData3(*normal)
        cw.addData4f(*color)
    triangles = GeomTriangles(Geom.UHStatic)
    for i in range(0, len(indices), 3):
        triangles.addVertices(*indices[i : i + 3])
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
    profile_center = (
        (0, 0),
        (0.0675, -0.00805),
        (0.135, -0.0069),
        (0.207, 0.00575),
        (0.279, 0.02875),
        (0.351, 0.0644),
        (0.432, 0.115),
    )
    for x, y, z in vertices:
        bend = 0.115
        for (za, xa), (zb, xb) in pairwise(profile_center):
            if z <= zb:
                bend = xa + (xb - xa) * max(0, (z - za) / (zb - za))
                break
        tentacle.rest_vertices.append((z / 0.432, (x - bend) * 0.65, y * 0.65))
    lines = LineSegs("tentacle-joint-axes")
    lines.setThickness(1.5)
    for color, endpoint in (
        ((1, 0.15, 0.15, 1), (0.035, 0, 0)),
        ((0.15, 1, 0.2, 1), (0, 0.035, 0)),
        ((0.2, 0.4, 1, 1), (0, 0, 0.05)),
    ):
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


def update_tentacle_render(tentacle: Tentacle) -> None:  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
    """Deforma a malha low-poly na curva procedural dos pontos da mola."""
    if not tentacle.mesh_node or not tentacle.segments or not tentacle.mesh_vdata:
        return
    from panda3d.core import GeomVertexRewriter, Mat3, Quat, Vec3

    points = [Vec3(seg.pos) for seg in tentacle.segments]
    nearby = tentacle.contacts.region(points) if tentacle.contacts else []

    # Assinatura barata da entrada: sem obstáculos próximos, a malha depende
    # só da pose dos segmentos, do reveal, da espessura, do state_time e da
    # frente de referência. Se nada disso mudou, o recomputo daria o mesmo
    # resultado — pula o frame. Com obstáculos, nunca pula (a projeção pode
    # mudar sem os segmentos se moverem).
    if not nearby:
        signature = (
            round(tentacle.reveal, 5),
            round(tentacle.girth_scale, 5),
            round(tentacle.state_time, 4),
            tuple(round(c, 5) for c in tentacle.reference_front),
            tuple(round(c, 4) for point in points for c in point),
        )
        if signature == tentacle._last_render_signature:
            return
        tentacle._last_render_signature = signature
    else:
        tentacle._last_render_signature = None
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
        twist = (
            0.45 + math.sin(tentacle.state_time * 0.85 + tentacle.seed * 0.001) * 0.3
        ) * u
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
        center = (p1 * 2 + a * alpha + b * alpha**2 + c * alpha**3) * 0.5
        tangent = (a + b * (2 * alpha) + c * (3 * alpha**2)) * 0.5
        if tangent.lengthSquared() < 1e-10:
            tangent = frames[index][1]
        tangent.normalize()
        right = frames[index][2] * (1 - alpha) + frames[index + 1][2] * alpha
        right -= tangent * right.dot(tangent)
        right.normalize()
        front = tangent.cross(right).normalized()
        return center, tangent, right, front

    def deform(vdata) -> None:
        # Reaproveita os rewriters por tentáculo: eles ficam presos ao mesmo
        # GeomVertexData, que persiste entre frames. setRow(0) os reposiciona.
        vertex_writer = tentacle._vertex_rewriter
        normal_writer = tentacle._normal_rewriter
        if vertex_writer is None or normal_writer is None:
            vertex_writer = GeomVertexRewriter(vdata, "vertex")
            normal_writer = GeomVertexRewriter(vdata, "normal")
            tentacle._vertex_rewriter = vertex_writer
            tentacle._normal_rewriter = normal_writer
        vertex_writer.setRow(0)
        normal_writer.setRow(0)
        for (u, x, y), local_normal in zip(
            tentacle.rest_vertices, tentacle.template_normals, strict=True
        ):
            if u not in cache:
                frame = frame_at(u)
                center = frame[0]
                radius = 0.09 * tentacle.girth_scale
                ring_boxes = [
                    box
                    for box in nearby
                    if box.model_low.x - radius <= center.x <= box.model_high.x + radius
                    and box.model_low.y - radius
                    <= center.y
                    <= box.model_high.y + radius
                    and box.model_low.z - radius
                    <= center.z
                    <= box.model_high.z + radius
                ]
                cache[u] = (frame, ring_boxes)
            (center, tangent, right, front), ring_boxes = cache[u]
            position = center + (right * x + front * y) * tentacle.girth_scale
            for obstacle in ring_boxes:
                position = obstacle.project(position, 0.002)
            nx, ny, nz = local_normal
            normal = right * nx + front * ny + tangent * nz
            if normal.lengthSquared() > 1e-10:
                normal.normalize()
            vertex_writer.setData3(position)
            normal_writer.setData3(normal)

    deform(tentacle.mesh_vdata)

"""Sistema procedural de tentáculos — SeJogaDesktopCompanion.

Tentáculos como chains de segmentos rígidos (low-poly), sem skin.
Cada tentáculo = lista de TentacleSegment com mola-amortecedor + overshoot impulsivo.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import StrEnum

from panda3d.core import GeomVertexRewriter, Mat3, NodePath, Point3, Quat, Vec3

from sejoga.animacao.dados_autorais import tentaculos_ativos
from sejoga.nucleo.esqueleto import IdlePersonality, Rig
from sejoga.tentaculos import coreografia_porta as coreo
from sejoga.tentaculos.ondulacao import (
    FASE_POR_SEMENTE_RAD,
    ONDULACAO_CALMA,
    OndulacaoTuning,
    deslocamento_ondulante,
    ondulacao_do_temperamento,
    ondulacao_espirro,
)
from sejoga.tentaculos.restricoes_tentaculos import TentacleContacts

# Tolerância ao tratar a base da frente como degenerada (frente quase vertical).
EPSILON_BASE_FRENTE = 1e-6

# ============================================================
# Configuração visual / física
# ============================================================

TOTAL_ENXURRADA = 5
PERFIL_TENTACULO = (0.062, 0.080, 0.083, 0.076, 0.065, 0.051, 0.031, 0.006)
CURVATURAS = (0.28, -0.39, 0.48)

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
    (IdlePersonality.BRC_STANCE, IdlePersonality.CONFIDENT),
    (IdlePersonality.VIBING, IdlePersonality.CALM),
    (IdlePersonality.BRC_MALANDRO, IdlePersonality.CONFIDENT),
    (IdlePersonality.FRENETICO_GROOVE, IdlePersonality.PLAYFUL),
    (IdlePersonality.ESPREITA_ARMARIO, IdlePersonality.CURIOUS),
    (IdlePersonality.JOJO_EXIBIDO, IdlePersonality.CONFIDENT),
    (IdlePersonality.BOXEADOR_PRONTO, IdlePersonality.CONFIDENT),
    (IdlePersonality.DERRETIDO_SONO, IdlePersonality.SHY),
):
    SPRING_PARAMS[_style] = dict(SPRING_PARAMS[_base])

# Parâmetros por estado comportamental
STATE_PARAMS = {
    "dormant": dict(max_len=0.0, reach_speed=0.0, curl=0.0, jitter=0.0),
    "curious": dict(max_len=1.05, reach_speed=400.0, curl=0.14, jitter=0.05),
    "reaching": dict(max_len=1.05, reach_speed=900.0, curl=0.2, jitter=0.1),
    "grabbing": dict(max_len=1.05, reach_speed=600.0, curl=0.85, jitter=0.05),
    "spitting": dict(max_len=1.2, reach_speed=-800.0, curl=0.0, jitter=0.15),
    "frenzy": dict(max_len=1.25, reach_speed=2200.0, curl=0.4, jitter=0.35),
    "retracting": dict(max_len=0.0, reach_speed=-600.0, curl=0.0, jitter=0.0),
}

# Morfologias autorais: alterna base larga, chicotes segmentados de espirro,
# clavas sensoriais e cristas dorsais para eliminar tubos repetitivos e esticados.
TENTACLE_MORPHOLOGIES = (
    "musculoso",
    "chicote_longo",
    "clava_lula",
    "espinhoso_abissal",
)

# Paletas adaptadas aos 7 filtros visuais mantendo leitura low-poly clássica e distância do colorkey.
ESTILOS_TENTACULO: dict[str, dict[str, object]] = {
    "padrao": {
        "mantle": (
            (0.68, 0.080, 0.44, 1.0),
            (0.98, 0.190, 0.56, 1.0),
            (0.84, 0.125, 0.48, 1.0),
            (0.30, 0.048, 0.22, 1.0),
            (0.42, 0.062, 0.31, 1.0),
            (0.56, 0.074, 0.39, 1.0),
        ),
        "root": (0.28, 0.045, 0.21, 1.0),
        "tip": (0.98, 0.200, 0.54, 1.0),
        "sucker_0": (0.86, 0.125, 0.46, 1.0),
        "sucker_1": (1.00, 0.380, 0.64, 1.0),
        "sucker_2": (0.58, 0.080, 0.32, 1.0),
        "sucker_3": (0.26, 0.042, 0.18, 1.0),
        "sucker_c": (0.26, 0.042, 0.18, 1.0),
        "outline": (0.10, 0.02, 0.14, 1.0),
        "drips": (1.0, 1.0, 1.0, 1.0),
    },
    "pixel": {
        "mantle": (
            (0.66, 0.10, 0.44, 1.0),
            (0.90, 0.16, 0.50, 1.0),
            (0.76, 0.12, 0.46, 1.0),
            (0.34, 0.06, 0.28, 1.0),
            (0.46, 0.08, 0.36, 1.0),
            (0.56, 0.09, 0.40, 1.0),
        ),
        "root": (0.30, 0.05, 0.24, 1.0),
        "tip": (0.96, 0.22, 0.52, 1.0),
        "sucker_0": (0.12, 0.72, 0.78, 1.0),
        "sucker_1": (0.36, 0.96, 0.88, 1.0),
        "sucker_2": (0.08, 0.44, 0.56, 1.0),
        "sucker_3": (0.04, 0.20, 0.30, 1.0),
        "sucker_c": (0.04, 0.20, 0.30, 1.0),
        "outline": (0.06, 0.04, 0.12, 1.0),
        "drips": (0.55, 0.96, 0.92, 1.0),
    },
    "rascunho": {
        "mantle": (
            (0.48, 0.08, 0.22, 1.0),
            (0.76, 0.16, 0.32, 1.0),
            (0.62, 0.12, 0.26, 1.0),
            (0.22, 0.04, 0.12, 1.0),
            (0.32, 0.06, 0.16, 1.0),
            (0.40, 0.07, 0.19, 1.0),
        ),
        "root": (0.18, 0.03, 0.10, 1.0),
        "tip": (0.90, 0.22, 0.36, 1.0),
        "sucker_0": (0.76, 0.16, 0.28, 1.0),
        "sucker_1": (0.96, 0.88, 0.78, 1.0),
        "sucker_2": (0.38, 0.06, 0.14, 1.0),
        "sucker_3": (0.14, 0.02, 0.06, 1.0),
        "sucker_c": (0.14, 0.02, 0.06, 1.0),
        "outline": (0.05, 0.02, 0.04, 1.0),
        "drips": (0.86, 0.20, 0.30, 1.0),
    },
    "hifi_comic": {
        "mantle": (
            (0.82, 0.10, 0.24, 1.0),
            (0.98, 0.22, 0.34, 1.0),
            (0.90, 0.15, 0.28, 1.0),
            (0.46, 0.04, 0.16, 1.0),
            (0.58, 0.06, 0.19, 1.0),
            (0.70, 0.08, 0.21, 1.0),
        ),
        "root": (0.32, 0.02, 0.10, 1.0),
        "tip": (1.00, 0.44, 0.28, 1.0),
        "sucker_0": (0.96, 0.56, 0.12, 1.0),
        "sucker_1": (1.00, 0.82, 0.24, 1.0),
        "sucker_2": (0.72, 0.22, 0.08, 1.0),
        "sucker_3": (0.28, 0.06, 0.06, 1.0),
        "sucker_c": (0.28, 0.06, 0.06, 1.0),
        "outline": (0.04, 0.03, 0.08, 1.0),
        "drips": (1.00, 0.56, 0.22, 1.0),
    },
    "cyberfunk": {
        "mantle": (
            (0.36, 0.12, 0.78, 1.0),
            (0.62, 0.24, 0.96, 1.0),
            (0.48, 0.18, 0.88, 1.0),
            (0.14, 0.05, 0.44, 1.0),
            (0.22, 0.08, 0.58, 1.0),
            (0.28, 0.10, 0.68, 1.0),
        ),
        "root": (0.10, 0.04, 0.32, 1.0),
        "tip": (0.18, 0.92, 0.96, 1.0),
        "sucker_0": (0.12, 0.78, 0.92, 1.0),
        "sucker_1": (0.38, 1.00, 0.96, 1.0),
        "sucker_2": (0.08, 0.44, 0.68, 1.0),
        "sucker_3": (0.04, 0.16, 0.34, 1.0),
        "sucker_c": (0.04, 0.16, 0.34, 1.0),
        "outline": (0.04, 0.85, 0.95, 1.0),
        "drips": (0.22, 0.94, 0.98, 1.0),
    },
    "anime": {
        "mantle": (
            (0.84, 0.18, 0.42, 1.0),
            (1.00, 0.32, 0.56, 1.0),
            (0.92, 0.24, 0.48, 1.0),
            (0.46, 0.12, 0.38, 1.0),
            (0.60, 0.14, 0.42, 1.0),
            (0.72, 0.16, 0.45, 1.0),
        ),
        "root": (0.38, 0.10, 0.34, 1.0),
        "tip": (1.00, 0.52, 0.70, 1.0),
        "sucker_0": (0.98, 0.48, 0.66, 1.0),
        "sucker_1": (1.00, 0.84, 0.88, 1.0),
        "sucker_2": (0.72, 0.22, 0.44, 1.0),
        "sucker_3": (0.32, 0.10, 0.28, 1.0),
        "sucker_c": (0.32, 0.10, 0.28, 1.0),
        "outline": (0.11, 0.08, 0.17, 1.0),
        "drips": (1.00, 0.72, 0.84, 1.0),
    },
    "lowpoly_block": {
        "mantle": (
            (0.10, 0.64, 0.58, 1.0),
            (0.24, 0.90, 0.76, 1.0),
            (0.16, 0.78, 0.68, 1.0),
            (0.04, 0.34, 0.34, 1.0),
            (0.06, 0.46, 0.44, 1.0),
            (0.08, 0.54, 0.50, 1.0),
        ),
        "root": (0.03, 0.24, 0.26, 1.0),
        "tip": (1.00, 0.58, 0.16, 1.0),
        "sucker_0": (0.96, 0.46, 0.12, 1.0),
        "sucker_1": (1.00, 0.76, 0.26, 1.0),
        "sucker_2": (0.66, 0.24, 0.06, 1.0),
        "sucker_3": (0.28, 0.10, 0.04, 1.0),
        "sucker_c": (0.28, 0.10, 0.04, 1.0),
        "outline": (0.03, 0.12, 0.18, 1.0),
        "drips": (0.34, 0.96, 0.82, 1.0),
    },
    "holograma": {
        "mantle": (
            (0.08, 0.68, 0.92, 1.0),
            (0.22, 0.92, 1.00, 1.0),
            (0.12, 0.82, 0.98, 1.0),
            (0.03, 0.34, 0.64, 1.0),
            (0.05, 0.46, 0.76, 1.0),
            (0.06, 0.56, 0.84, 1.0),
        ),
        "root": (0.03, 0.28, 0.54, 1.0),
        "tip": (0.72, 0.98, 1.00, 1.0),
        "sucker_0": (0.24, 0.92, 1.00, 1.0),
        "sucker_1": (0.86, 1.00, 1.00, 1.0),
        "sucker_2": (0.10, 0.60, 0.86, 1.0),
        "sucker_3": (0.04, 0.24, 0.48, 1.0),
        "sucker_c": (0.04, 0.24, 0.48, 1.0),
        "outline": (0.65, 0.98, 1.00, 1.0),
        "drips": (0.26, 0.96, 1.00, 1.0),
    },
    "gameboy": {
        "mantle": (
            (0.32, 0.50, 0.12, 1.0),
            (0.55, 0.68, 0.06, 1.0),
            (0.44, 0.58, 0.10, 1.0),
            (0.12, 0.28, 0.12, 1.0),
            (0.19, 0.38, 0.19, 1.0),
            (0.25, 0.44, 0.15, 1.0),
        ),
        "root": (0.08, 0.22, 0.08, 1.0),
        "tip": (0.61, 0.74, 0.06, 1.0),
        "sucker_0": (0.55, 0.68, 0.06, 1.0),
        "sucker_1": (0.61, 0.74, 0.06, 1.0),
        "sucker_2": (0.19, 0.38, 0.19, 1.0),
        "sucker_3": (0.06, 0.22, 0.06, 1.0),
        "sucker_c": (0.06, 0.22, 0.06, 1.0),
        "outline": (0.06, 0.22, 0.06, 1.0),
        "drips": (0.55, 0.68, 0.06, 1.0),
    },
    "manga_papel": {
        "mantle": (
            (0.42, 0.42, 0.44, 1.0),
            (0.88, 0.87, 0.84, 1.0),
            (0.66, 0.65, 0.64, 1.0),
            (0.10, 0.10, 0.12, 1.0),
            (0.22, 0.22, 0.24, 1.0),
            (0.32, 0.32, 0.34, 1.0),
        ),
        "root": (0.08, 0.08, 0.10, 1.0),
        "tip": (0.96, 0.95, 0.91, 1.0),
        "sucker_0": (0.86, 0.85, 0.82, 1.0),
        "sucker_1": (0.96, 0.95, 0.91, 1.0),
        "sucker_2": (0.36, 0.36, 0.38, 1.0),
        "sucker_3": (0.08, 0.08, 0.10, 1.0),
        "sucker_c": (0.08, 0.08, 0.10, 1.0),
        "outline": (0.04, 0.04, 0.06, 1.0),
        "drips": (0.92, 0.91, 0.88, 1.0),
    },
}


def _resolver_cor_papel(
    estilo: dict[str, object], papel: str, colorkey_hex: str
) -> tuple[float, float, float, float]:
    """Devolve a cor RGBA de um papel semântico da malha, segura contra o colorkey."""
    from sejoga.render.chroma_tuning import seguro_contra_chroma_255

    if papel.startswith("mantle_"):
        idx = int(papel.split("_", 1)[1])
        manto = estilo["mantle"]  # type: ignore[index]
        rgba = manto[idx % len(manto)]  # type: ignore[index]
    else:
        rgba = estilo[papel]  # type: ignore[index]
    r, g, b, a = rgba
    rs, gs, bs = seguro_contra_chroma_255(
        int(round(max(0.0, min(1.0, float(r))) * 255.0)),
        int(round(max(0.0, min(1.0, float(g))) * 255.0)),
        int(round(max(0.0, min(1.0, float(b))) * 255.0)),
        colorkey_hex,
    )
    return (rs / 255.0, gs / 255.0, bs / 255.0, float(a))


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
    outline_rest_vertices: list = field(default_factory=list)
    outline_normals: list = field(default_factory=list)
    retract_from: list[Vec3] = field(default_factory=list)
    reveal: float = 0.0
    retract_reveal: float = 0.0
    frames: list = field(default_factory=list)
    axis_nodes: list = field(default_factory=list)
    reference_front: Vec3 = field(default_factory=lambda: Vec3(0, -1, 0))
    reference_up: Vec3 = field(default_factory=lambda: Vec3(0, 0, 1))
    color_roles: list[str] = field(default_factory=list)
    contacts: TentacleContacts | None = None

    perfil: int = 0
    morfologia: str = "musculoso"
    enxurrada: bool = False
    length_scale: float = 1.0
    girth_scale: float = 1.0
    speaker_throw: bool = False
    local_target: Vec3 | None = None

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
    _out_vertex_rewriter: GeomVertexRewriter | None = None
    _out_normal_rewriter: GeomVertexRewriter | None = None
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
            perfil=index % len(CURVATURAS),
            morfologia=TENTACLE_MORPHOLOGIES[(index + (index // 4)) % len(TENTACLE_MORPHOLOGIES)],
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
            t.enxurrada = False
            t.local_target = None
            t.length_scale = t.girth_scale = 1.0
            for segment in t.segments:
                segment.length = SEGMENT_LENGTH * self.unit_scale
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
            t.ondulacao = ondulacao_do_temperamento(personality)
            t.saida = coreo.saida_do_temperamento(personality)

    def aplicar_estilo(
        self,
        filtro: str,
        outline_enabled: bool = True,
        outline_rgba: tuple[float, float, float, float] | None = None,
        colorkey_hex: str = "#FF00FF",
    ) -> None:
        """Adapta paleta e contorno de todos os tentáculos ao estilo visual ativo."""
        filtro_norm = "anime" if filtro == "anime_impact" else filtro
        nome_estilo = filtro_norm if filtro_norm in ESTILOS_TENTACULO else "padrao"
        estilo = ESTILOS_TENTACULO[nome_estilo]
        mapa_cores: dict[str, tuple[float, float, float, float]] = {}
        usar_cor_usuario = (
            outline_rgba is not None
            and nome_estilo == "padrao"
        )
        cor_borda = (
            outline_rgba
            if usar_cor_usuario
            else _resolver_cor_papel(estilo, "outline", colorkey_hex)
        )
        for t in self.tentacles:
            if t.mesh_vdata is not None and t.color_roles:
                cw = GeomVertexRewriter(t.mesh_vdata, "color")
                cw.setRow(0)
                set_col = cw.setData4f
                for papel in t.color_roles:
                    cor = mapa_cores.get(papel)
                    if cor is None:
                        cor = _resolver_cor_papel(estilo, papel, colorkey_hex)
                        mapa_cores[papel] = cor
                    set_col(*cor)
                t._vertex_rewriter = None
                t._normal_rewriter = None
                t._out_vertex_rewriter = None
                t._out_normal_rewriter = None
                t._last_render_signature = None
            if t.outline_mesh_node is not None:
                if not outline_enabled:
                    t.outline_mesh_node.hide()
                else:
                    t.outline_mesh_node.setShaderInput("outline_color", cor_borda)


# ============================================================
# Director — alto nível
# ============================================================


class TentacleDirector:
    """Comportamento de alto nível: decide o que os tentáculos fazem."""

    def __init__(  # noqa: PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
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
        self.aviso_antena_tempo: float = 0.0
        self._atraso_abertura_porta: float = 0.0
        self._pedido_porta_externo = 0.0
        self._fechar_apos_ejecao = False
        self._borda_porta_local: Vec3 | None = None
        self.speaker_throw_remaining = 0.0
        self.speaker_throw_limbs: list[Tentacle] = []
        self.music_ejection = False

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
        self.aviso_antena_tempo = max(self.aviso_antena_tempo, 0.45)
        if self.door_node is not None and self._door_current < coreo.LIMIAR_SAIDA_PORTA_GRAUS:
            self._atraso_abertura_porta = max(self._atraso_abertura_porta, 0.22)
        self._spawn_frenzy()

    def trigger_swallow(self, target_pos: Vec3, duration: float = 2.0) -> None:
        """Inicia sequência de engolir: target é engolido e cuspido depois."""
        self.swallowing = True
        self.swallow_target = target_pos
        self.swallow_time = duration
        self.aviso_antena_tempo = max(self.aviso_antena_tempo, 0.45)
        if self.door_node is not None and self._door_current < coreo.LIMIAR_SAIDA_PORTA_GRAUS:
            self._atraso_abertura_porta = max(self._atraso_abertura_porta, 0.20)
        self._spawn_swallow()

    def trigger_curious(self, count: int | None = None) -> None:
        """Força um momento curious (espiada) com 2-4 tentáculos saindo em leque."""
        if count is None and any(
            t.state == TentacleState.CURIOUS and not t.speaker_throw
            for t in self.pool.tentacles
        ):
            return
        self._spawn_curious(
            count=count if count is not None else self.rng.choices(
                (2, 3, 4), weights=(20, 45, 35), k=1
            )[0],
            coreografar=True,
        )

    def trigger_speaker_throw(self):
        """Dispara os tentáculos que arremessam a caixa de som."""
        for limb in self.speaker_throw_limbs:
            limb.speaker_throw = False
            limb.duracao_recolher_s = 0.5
            self.pool.release(limb)
        self.speaker_throw_remaining = 1.04
        self.speaker_throw_limbs = self._spawn_curious(1)
        for limb in self.speaker_throw_limbs:
            limb.speaker_throw = True
            limb.params["max_len"] = 1.1
            limb.length_scale = 3.4
            limb.girth_scale = 1.65
            for segment in limb.segments:
                segment.length = SEGMENT_LENGTH * limb.unit_scale * limb.length_scale

    def cobrir_roupa(self):
        """Estende duas curvas pela frente do tronco enquanto a roupa muda."""
        limbs = self._spawn_curious(2)
        head = self.door_node.getParent() if self.door_node is not None else None
        for index, limb in enumerate(limbs):
            lado = -1 if index == 0 else 1
            if head is not None and not head.isEmpty() and self.model_np is not None:
                alvo = self.model_np.getRelativePoint(
                    head, Point3(lado * 0.35, 0.44, -0.51)
                )
            else:
                lateral, forward, cima = _base_frente(limb)
                alvo = limb.anchor + lateral * (lado * 0.35) + forward * 0.36 - cima * 0.42
            limb.target = Vec3(alvo)
            limb.state_time = 0
            limb.duracao_revelacao_s = 0.65
            limb.girth_scale = 3.4
            for segment in limb.segments:
                segment.length = SEGMENT_LENGTH * limb.unit_scale * 2.8
        return limbs

    def trigger_sneeze(self):
        """Dispara os tentáculos do espirro."""
        self.burst = True
        self.aviso_antena_tempo = max(self.aviso_antena_tempo, 0.36)
        self._spawn_curious(TOTAL_ENXURRADA, enxurrada=True)
        self._door_requested = coreo.SAIDA_ESPIRRO.angulo_empurrao_graus

    def update(self, dt: float, personality: IdlePersonality) -> None:  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        """Atualiza todos os tentáculos e decide transições."""
        dt = min(dt, 0.05)  # clamp para estabilidade
        if self.aviso_antena_tempo > 0.0:
            self.aviso_antena_tempo = max(0.0, self.aviso_antena_tempo - dt)
        if self._atraso_abertura_porta > 0.0:
            self._atraso_abertura_porta = max(0.0, self._atraso_abertura_porta - dt)
        if self.speaker_throw_remaining > 0:
            self.speaker_throw_remaining = max(0, self.speaker_throw_remaining - dt)
            if self.speaker_throw_remaining == 0:
                for limb in self.speaker_throw_limbs:
                    limb.speaker_throw = False
                    limb.duracao_recolher_s = 0.5
                    self.pool.release(limb)
                self.speaker_throw_limbs = []

        # Atualiza pool
        self.pool.update_personality(personality)
        if self._outro_dono_da_porta():
            self._fechar_apos_ejecao |= self.burst or getattr(
                self, "music_ejection", False
            )
            self._cancelar_coreografia()
        elif self._fechar_apos_ejecao:
            self._fechar_apos_ejecao = False
            if self._door_current >= coreo.LIMIAR_SAIDA_PORTA_GRAUS:
                self.coreografia.assumir_aberta()

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
        any_active = False
        for tentacle in self.pool.tentacles:
            if tentacle.state != TentacleState.DORMANT:
                any_active = True
                self._update_tentacle(tentacle, dt)
        if not any_active and self.burst and not self.frenzy_mode and not self.swallowing:
            self.burst = False
        if any_active:
            self._separate_tentacles()

        # Door sync: atualiza o ângulo da porta antes de apontar o atuador para
        # que ``door_node`` reflita a abertura atual (em vez de ficar em 0° do rig).
        self._avancar_coreografia(dt)
        self._update_door(dt)
        self._apontar_atuador()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _spawn_frenzy(self) -> None:
        active = self.pool.get_available(7)  # 6-8 tentáculos
        for idx, t in enumerate(active):
            t.state = TentacleState.FRENZY
            t.state_time = -0.03 * idx
            t.duracao_revelacao_s = 0.48
            t.length_scale = 1.05 + 0.08 * (idx % 3)
            t.girth_scale = 0.88 + 0.06 * (idx % 3)
            t.params = dict(STATE_PARAMS["frenzy"])
            for segment in t.segments:
                segment.length = SEGMENT_LENGTH * self.pool.unit_scale * t.length_scale
            lateral, frente, cima = _base_frente(t)
            ang = idx * math.tau / max(1, len(active)) + self.rng.uniform(-0.25, 0.25)
            d = (
                lateral * (math.cos(ang) * 0.78)
                + frente * self.rng.uniform(0.85, 1.15)
                + cima * (math.sin(ang) * 0.62)
            ).normalized()
            alcance = self.rng.uniform(118.0, 152.0) * self.pool.unit_scale * t.length_scale
            t.target = self._projetar_alvo_frontal_cabeca(t.anchor + d * alcance, min_y=0.38)
        # Porta aberta total
        self._door_requested = 135.0

    def _spawn_swallow(self) -> None:
        active = self.pool.get_available(6)
        for t in active:
            t.state = TentacleState.REACHING
            t.state_time = 0.0
            t.params = dict(STATE_PARAMS["reaching"])
            scale = self.pool.unit_scale
            offset = Vec3(
                self.rng.uniform(-30, 30) * scale,
                self.rng.uniform(-30, 30) * scale,
                self.rng.uniform(-16, 16) * scale,
            )
            base_sw = self.swallow_target if self.swallow_target is not None else (
                t.anchor + _base_frente(t)[1] * (160.0 * scale)
            )
            t.target = self._projetar_alvo_frontal_cabeca(base_sw + offset, min_y=0.24)
        self._door_requested = 135.0

    def encerrar_espiada(self, *, interromper: bool) -> None:
        """Recolhe os curiosos, deixando o atuador concluir o ciclo da porta."""
        if interromper:
            self._retract_all()
            return
        for tentaculo in self.pool.tentacles:
            if (
                tentaculo.state is TentacleState.CURIOUS
                and tentaculo is not self._atuador
                and not tentaculo.speaker_throw
            ):
                self.pool.release(tentaculo)

    def _retract_all(self) -> None:
        self._fechar_apos_ejecao = False
        self._atraso_abertura_porta = 0.0
        self.burst = False
        self.frenzy_mode = False
        self.swallowing = False
        self.music_ejection = False
        self.speaker_throw_remaining = 0.0
        for limb in self.speaker_throw_limbs:
            limb.speaker_throw = False
        self.speaker_throw_limbs = []
        self._cancelar_coreografia()
        for t in self.pool.tentacles:
            if t.state != TentacleState.DORMANT:
                t.duracao_recolher_s = 0.28
                self.pool.release(t)
        self._door_requested = 0.0

    def _atualizar_tentaculo_recolhendo(self, tentacle: Tentacle, dt: float) -> None:
        """Avança o recolhimento suave do tentáculo até voltar ao estado dormente."""
        duracao_recolher = (
            0.45
            if self.burst
            else tentacle.duracao_recolher_s
            if tentacle.duracao_recolher_s is not None
            else 1.1
        )
        progress = min(1.0, max(0.0, tentacle.state_time / duracao_recolher))
        eased = progress**3 * (10 - 15 * progress + 6 * progress * progress)
        tentacle.reveal = tentacle.retract_reveal * max(0.0, 1 - eased)
        if progress >= 1.0:
            tentacle.state = TentacleState.DORMANT
            tentacle.params = dict(STATE_PARAMS["dormant"])
            tentacle.retract_from.clear()
            tentacle.target = None
            tentacle.local_target = None
            tentacle.reveal = 0.0
            self._resetar_segmentos_ancora(tentacle)
            return
        if tentacle.target is not None:
            _, front_dir, _ = _base_frente(tentacle)
            inside_target = tentacle.anchor + front_dir * 0.03
            pull = 1.0 - math.exp(-dt * 8.0)
            tentacle.target = tentacle.target + (inside_target - tentacle.target) * pull
        if tentacle.params_antes_recolher:
            self._atualizar_segmentos(tentacle, dt, tentacle.params_antes_recolher)

    def _update_tentacle(self, tentacle: Tentacle, dt: float) -> None:
        if (
            self._atraso_abertura_porta > 0.0
            and self._door_current < coreo.LIMIAR_SAIDA_PORTA_GRAUS
        ):
            return
        # O atuador da coreografia (empurra/puxa a porta) não espera a porta abrir.
        if (
            tentacle.state == TentacleState.CURIOUS
            and tentacle is not self._atuador
            and self._door_current < coreo.LIMIAR_SAIDA_PORTA_GRAUS
        ):
            return
        tentacle.state_time += dt

        if tentacle.state == TentacleState.RETRACTING:
            self._atualizar_tentaculo_recolhendo(tentacle, dt)
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
        reveal_divisor = (
            0.30
            if getattr(tentacle, "speaker_throw", False)
            else coreo.saida_espirro().duracao_s
            if self.burst
            else duracao_revelacao
        )
        reveal_time = max(0.0, min(1.0, tentacle.state_time / reveal_divisor))
        tentacle.reveal = reveal_time**3 * (10 - 15 * reveal_time + 6 * reveal_time**2)
        self._atualizar_segmentos(tentacle, dt, p)

    def _pontos_bezier_curva(
        self,
        tentacle: Tentacle,
        lateral: Vec3,
        forward: Vec3,
        up: Vec3,
        curve: float,
        target_curl: float,
    ) -> tuple[Vec3, Vec3, Vec3]:
        delta = tentacle.target - tentacle.anchor
        a = tentacle.anchor + forward * (0.28 * tentacle.length_scale) + up * 0.015
        b = (
            tentacle.anchor
            + delta * 1.15
            + forward * 0.08
            + Vec3(0, 0, 0.06 + target_curl * 0.04)
        )
        if tentacle is self._atuador or tentacle.speaker_throw:
            return a, b, delta
        delta_lat = delta.dot(lateral)
        delta_up = delta.dot(up)
        lat_sign = 1.0 if delta_lat >= 0.0 else -1.0
        passagem = max(0.24, 0.30 * tentacle.length_scale)
        espalhamento = (
            lateral * (lat_sign * abs(curve) * 0.42)
            + up * ((0.22 if delta_up >= -0.05 else -0.14) * abs(curve))
        ) * delta.length()
        corredor = self._corredor_porta_aberta()
        if corredor is not None:
            meio_vao, saida_livre = corredor
            # Espalha suavemente dentro da abertura útil do gabinete antes de abrir em leque fora.
            lat_a = max(-0.042, min(0.042, delta_lat * 0.14))
            up_a = max(-0.085, min(0.065, delta_up * 0.28))
            a = meio_vao + forward * 0.055 + lateral * lat_a + up * up_a
            b = (
                saida_livre
                + forward * (0.10 * tentacle.length_scale)
                + lateral * (delta_lat * 0.32)
                + up * (delta_up * 0.40)
                + espalhamento * 0.28
            )
        else:
            a = (
                tentacle.anchor
                + forward * (0.22 * tentacle.length_scale)
                + lateral * (delta_lat * 0.12)
                + up * (delta_up * 0.12 + 0.022)
            )
            b = tentacle.anchor + forward * passagem + delta * 0.56 + espalhamento
        return a, b, delta

    def _aplicar_ondulacao_e_arco(
        self,
        tentacle: Tentacle,
        target_pos: Vec3,
        t_param: float,
        lateral: Vec3,
        forward: Vec3,
        up: Vec3,
        curl_tip: bool,
        traj: dict | None = None,
    ) -> Vec3:
        arch = math.sin(math.pi * t_param) ** 2
        fator_boca = 1.0
        if self.door_node is not None and self.model_np is not None:
            head = self.door_node.getParent()
            if not head.isEmpty():
                local_y = float(head.getRelativePoint(self.model_np, target_pos).y)
                t_b = max(0.0, min(1.0, (local_y - 0.145) / (0.275 - 0.145)))
                fator_boca = t_b * t_b * (3.0 - 2.0 * t_b)
        if traj is None:
            traj = tentaculos_ativos().get("trajetoria_ponta", {})
        delta_atraso = float(traj.get("atraso_segmento_s", 0.045)) - 0.045
        tempo_onda = tentacle.tempo_onda - t_param * delta_atraso
        onda_lateral, onda_cima = deslocamento_ondulante(
            ondulacao_espirro() if self.burst else tentacle.ondulacao,
            t_param,
            tempo_onda,
            tentacle.seed * FASE_POR_SEMENTE_RAD,
        )
        escala_onda = tentacle.unit_scale * math.sqrt(tentacle.length_scale)
        if self.burst:
            escala_onda *= 1.35 * (0.45 + 0.55 * t_param)
        if curl_tip:
            escala_onda *= 1 - 0.55 * t_param**4
        target_pos += (
            lateral * (onda_lateral * escala_onda * fator_boca)
            + up * (onda_cima * escala_onda * fator_boca)
        )
        arco_extra = float(traj.get("elevacao_arco", 0.0))
        avanco_extra = float(traj.get("avanco_frontal", 0.0))
        escala_alc = float(traj.get("escala_alcance", 1.0))
        if abs(escala_alc - 1.0) > 1e-6:
            target_pos = tentacle.anchor + (target_pos - tentacle.anchor) * escala_alc
        return (
            target_pos
            + forward * ((8.0 + avanco_extra * 100.0 * fator_boca) * tentacle.unit_scale * arch)
            + up * ((12.0 + arco_extra * 100.0) * tentacle.unit_scale * arch * fator_boca)
        )

    def _alvo_segmento_curva(
        self,
        tentacle: Tentacle,
        t_param: float,
        p: dict,
        lateral: Vec3,
        forward: Vec3,
        up: Vec3,
        curve: float,
        curl_tip: bool,
        *,
        bezier: tuple[Vec3, Vec3, Vec3] | None = None,
        traj: dict | None = None,
    ) -> Vec3:
        """Calcula a posição-alvo ao longo da Bézier com espiral na ponta e ondulação."""
        if tentacle.target is None or p["reach_speed"] == 0:
            return tentacle.anchor
        a, b, delta = (
            bezier
            if bezier is not None
            else self._pontos_bezier_curva(tentacle, lateral, forward, up, curve, p["curl"])
        )
        u = t_param
        v = 1 - u
        target_pos = (
            tentacle.anchor * (v**3)
            + a * (3 * v * v * u)
            + b * (3 * v * u * u)
            + tentacle.target * (u**3)
        )
        start_curl = 0.88 if self.burst else 0.80
        if curl_tip and u > start_curl:
            start = start_curl
            remaining = 1 - start
            base = (
                tentacle.anchor * remaining**3
                + a * (3 * remaining**2 * start)
                + b * (3 * remaining * start**2)
                + tentacle.target * start**3
            )
            tangent = (
                (a - tentacle.anchor) * remaining**2
                + (b - a) * (2 * remaining * start)
                + (tentacle.target - b) * start**2
            ) * 3
            along = tangent.normalized()
            bend = (
                up * (0.85 if delta.dot(up) >= -0.05 else -0.55)
                + lateral * ((1.0 if delta.dot(lateral) >= 0.0 else -1.0) * abs(curve))
            )
            bend = (bend - along * bend.dot(along)).normalized()
            turn = (0.35 + curve * 0.15) if self.burst else (1.20 + curve * 0.35)
            angle = ((u - start) / remaining) * turn
            target_pos = base + (
                along * math.sin(angle) + bend * (1 - math.cos(angle))
            ) * (remaining * tangent.length() / turn)
        return self._aplicar_ondulacao_e_arco(
            tentacle, target_pos, t_param, lateral, forward, up, curl_tip, traj=traj
        )

    @staticmethod
    def _orientar_segmento(seg, tentacle: Tentacle) -> None:
        if seg.vel.length() <= 0.5 * tentacle.unit_scale:
            return
        seg_vel_dir = seg.vel.normalized()
        world_up = Vec3(0, 0, 1)
        axis = world_up.cross(seg_vel_dir)
        dot = max(-1.0, min(1.0, world_up.dot(seg_vel_dir)))
        if axis.lengthSquared() > 1e-10:
            axis.normalize()
            seg.rot = Quat()
            seg.rot.setFromAxisAngle(math.degrees(math.acos(dot)), axis)
        elif dot < 0:
            seg.rot = Quat()
            seg.rot.setFromAxisAngle(180, Vec3(1, 0, 0))

    def _aplicar_jitter_segmento(self, tentacle: Tentacle, seg, dt: float) -> None:
        if (
            tentacle.state not in (TentacleState.CURIOUS, TentacleState.RETRACTING)
            and self.rng.random() < tentacle.impulse_chance * dt * 60
        ):
            amp = tentacle.impulse_strength * tentacle.unit_scale
            seg.vel += Vec3(
                self.rng.uniform(-1, 1) * amp,
                self.rng.uniform(-1, 1) * amp,
                self.rng.uniform(-1, 1) * amp * 0.5,
            )

    @staticmethod
    def _integrar_segmento_pos(
        tentacle: Tentacle,
        is_attuador: bool,
        seg,
        target_pos: Vec3,
        t_param: float,
        spring: float,
        damper: float,
        dt: float,
    ) -> None:
        if tentacle.enxurrada and not is_attuador:
            sub_dt = dt * 0.5
            k_burst = spring * 1.25
            d_burst = damper * 0.80
            for _ in range(2):
                force = (target_pos - seg.pos) * k_burst
                seg.vel += (force - seg.vel * d_burst) * sub_dt
                seg.pos += seg.vel * sub_dt
            return
        force = (target_pos - seg.pos) * spring
        seg.vel += (force - seg.vel * damper) * dt
        seg.pos += seg.vel * dt

    def _passo_segmento(
        self,
        tentacle: Tentacle,
        i: int,
        n_seg: int,
        seg,
        max_len: float,
        p: dict,
        spring: float,
        damper: float,
        lateral: Vec3,
        forward: Vec3,
        up: Vec3,
        curve: float,
        curl_tip: bool,
        dt: float,
        *,
        bezier: tuple[Vec3, Vec3, Vec3] | None = None,
        traj: dict | None = None,
    ) -> None:
        if i == 0:
            seg.pos = Vec3(tentacle.anchor)
            seg.vel = Vec3(0)
            return
        t_param = i / (n_seg - 1) if n_seg > 1 else 0.0
        target_pos = self._alvo_segmento_curva(
            tentacle,
            t_param,
            p,
            lateral,
            forward,
            up,
            curve,
            curl_tip,
            bezier=bezier,
            traj=traj,
        )
        self._aplicar_jitter_segmento(tentacle, seg, dt)
        self._integrar_segmento_pos(
            tentacle, tentacle is self._atuador, seg, target_pos, t_param, spring, damper, dt
        )
        from_anchor = seg.pos - tentacle.anchor
        max_dist = max_len * (i + 1) * seg.length * (2.5 if self.burst else 1)
        if from_anchor.length() > max_dist:
            seg.pos = tentacle.anchor + from_anchor.normalized() * max_dist
            seg.vel = Vec3(0, 0, 0)
        self._orientar_segmento(seg, tentacle)
        curl_amount = p["curl"] * (1.0 - t_param * 0.3)
        if curl_amount > 0.01:
            curl_rot = Quat()
            curl_rot.setHpr(Vec3(curl_amount * 45.0, 0, 0))
            seg.rot = seg.rot * curl_rot
        seg.sucker_phase += dt * 3.0

    def _atualizar_segmentos(self, tentacle: Tentacle, dt: float, p: dict) -> None:
        """Mola dos segmentos rumo à curva-alvo, com a onda da base à ponta."""
        max_len = p["max_len"]
        lateral, forward, up = _base_frente(tentacle)
        curve = CURVATURAS[tentacle.perfil]
        curl_tip = (
            tentacle.target is not None
            and tentacle is not self._atuador
            and not tentacle.speaker_throw
            and tentacle.state in (TentacleState.CURIOUS, TentacleState.RETRACTING)
        )
        tentacle.tempo_onda += dt
        if tentacle.mola_forcada is not None:
            spring, damper = tentacle.mola_forcada
        elif getattr(tentacle, "speaker_throw", False):
            spring, damper = 190, 24
        elif self.burst:
            spring, damper = 380, 30
        else:
            spring, damper = tentacle.spring, tentacle.damper

        bezier = (
            self._pontos_bezier_curva(tentacle, lateral, forward, up, curve, p["curl"])
            if tentacle.target is not None and p["reach_speed"] != 0
            else None
        )
        traj = tentaculos_ativos().get("trajetoria_ponta", {})
        n_seg = len(tentacle.segments)
        for i, seg in enumerate(tentacle.segments):
            self._passo_segmento(
                tentacle,
                i,
                n_seg,
                seg,
                max_len,
                p,
                spring,
                damper,
                lateral,
                forward,
                up,
                curve,
                curl_tip,
                dt,
                bezier=bezier,
                traj=traj,
            )

    @staticmethod
    def _coletar_esferas_tentaculo(
        limb: Tentacle,
    ) -> tuple[tuple[float, float, float, float, float, float], list[list]]:
        """Coleta esferas de colisão e AABB com margem dos elos expostos do tentáculo."""
        segments = limb.segments
        n = len(segments)
        inv_span = 1.0 / max(1, n - 1)
        girth = limb.girth_scale
        segs: list[list] = []
        min_x = min_y = min_z = 1e9
        max_x = max_y = max_z = -1e9
        # As raízes compartilham espaço dentro do armário.
        first = 5 if limb.enxurrada else 2
        last = min(n, 1 + math.ceil(limb.reveal * (n - 1)))
        for i in range(first, last, 2 if limb.enxurrada else 1):
            seg = segments[i]
            sp = seg.pos
            px, py, pz = float(sp.x), float(sp.y), float(sp.z)
            min_x, max_x = min(min_x, px), max(max_x, px)
            min_y, max_y = min(min_y, py), max(max_y, py)
            min_z, max_z = min(min_z, pz), max(max_z, pz)
            r = raio_tentaculo(i * inv_span / limb.reveal) * girth * 0.56 * compressao_saida(limb, sp)
            segs.append([seg, px, py, pz, r])
        margin = 0.12 * girth
        aabb = (min_x - margin, max_x + margin, min_y - margin, max_y + margin, min_z - margin, max_z + margin)
        return aabb, segs

    @staticmethod
    def _resolver_par_esferas(entry_a: list, entry_b: list) -> None:
        """Empurra dois segmentos sobrepostos e amortece a velocidade de aproximação."""
        seg_a, px, py, pz, ra = entry_a
        seg_b, ox, oy, oz, rb = entry_b
        dx, dy, dz = px - ox, py - oy, pz - oz
        min_dist = ra + rb
        squared = dx * dx + dy * dy + dz * dz
        if squared >= min_dist * min_dist:
            return
        distance = math.sqrt(squared)
        if distance > 1e-7:
            inv_d = 1.0 / distance
            nx, ny, nz = dx * inv_d, dy * inv_d, dz * inv_d
        else:
            nx, ny, nz = 1.0, 0.0, 0.0
        mag = min(0.022, (min_dist - distance) * 0.65)
        px, py, pz = px + nx * mag, py + ny * mag, pz + nz * mag
        ox, oy, oz = ox - nx * mag, oy - ny * mag, oz - nz * mag
        entry_a[1], entry_a[2], entry_a[3] = px, py, pz
        entry_b[1], entry_b[2], entry_b[3] = ox, oy, oz
        seg_a.pos = Vec3(px, py, pz)
        seg_b.pos = Vec3(ox, oy, oz)
        va, vb = seg_a.vel, seg_b.vel
        closing = (va.x - vb.x) * nx + (va.y - vb.y) * ny + (va.z - vb.z) * nz
        if closing < 0.0:
            c2 = closing * 0.5
            seg_a.vel = Vec3(va.x - nx * c2, va.y - ny * c2, va.z - nz * c2)
            seg_b.vel = Vec3(vb.x + nx * c2, vb.y + ny * c2, vb.z + nz * c2)

    @classmethod
    def _separar_par_tentaculos(cls, segs_a: list[list], segs_b: list[list]) -> None:
        """Resolve colisões esfera-a-esfera entre todos os pares de elos de dois tentáculos."""
        for entry_a in segs_a:
            for entry_b in segs_b:
                cls._resolver_par_esferas(entry_a, entry_b)

    @classmethod
    def _resolver_pares_ativos(cls, active: list[Tentacle]) -> None:
        """Executa separação par-a-par entre tentáculos cujas AABBs se sobrepõem."""
        coletados = [cls._coletar_esferas_tentaculo(limb) for limb in active]
        count = len(coletados)
        for a in range(count):
            ax0, ax1, ay0, ay1, az0, az1 = coletados[a][0]
            segs_a = coletados[a][1]
            for b in range(a + 1, count):
                bx0, bx1, by0, by1, bz0, bz1 = coletados[b][0]
                if ax1 < bx0 or ax0 > bx1 or ay1 < by0 or ay0 > by1 or az1 < bz0 or az0 > bz1:
                    continue
                cls._separar_par_tentaculos(segs_a, coletados[b][1])

    def _separate_tentacles(self):
        """Separa tentáculos ativos entre si e resolve contatos contra o corpo."""
        # Preserve embedded roots; solve the visible bodies as tapered spheres.
        active = [
            t
            for t in self.pool.tentacles
            if t.state != TentacleState.DORMANT and t.reveal > 0.15
        ]
        if len(active) > 1:
            self._resolver_pares_ativos(active)
        for limb in self.pool.tentacles:
            if limb.state != TentacleState.DORMANT:
                self._solve_contacts(limb)

    @staticmethod
    def _relaxar_corrente_tentaculo(segments: list[TentacleSegment], *, dividir_elos: bool) -> None:
        n = len(segments)
        for index in range(1, n):
            segment = segments[index]
            previous = segments[index - 1]
            if not dividir_elos and index + 1 < n:
                midpoint = (previous.pos + segments[index + 1].pos) * 0.5
                segment.pos += (midpoint - segment.pos) * 0.18
            delta = segment.pos - previous.pos
            limit = segment.length * 1.06
            dist_sq = delta.lengthSquared()
            if dist_sq <= limit * limit:
                continue
            dist = math.sqrt(dist_sq)
            excess = delta * ((dist - limit) / dist)
            if not dividir_elos or index <= 4:
                segment.pos -= excess
            else:
                previous.pos += excess * 0.32
                segment.pos -= excess * 0.68

    @staticmethod
    def _projetar_sem_recuo(
        tentacle: Tentacle,
        point: Vec3,
        radius: float,
        nearby: list,
        front_dir: Vec3,
    ) -> Vec3:
        projected = tentacle.contacts.project(point, radius, nearby)
        correction = projected - point
        if (
            (point - tentacle.anchor).dot(front_dir) < 0.36
            and correction.dot(front_dir) < 0.0
        ):
            # Impede que quina de porta ou gabinete trave ou empurre o trecho emergente para trás.
            correction -= front_dir * correction.dot(front_dir)
        return correction

    @staticmethod
    def _amortecer_velocidade_normal(segment, correction: Vec3) -> None:
        """Zera a componente da velocidade de entrada após projeção em obstáculo."""
        if correction.lengthSquared() <= 1e-12:
            return
        normal = correction.normalized()
        incoming = segment.vel.dot(normal)
        if incoming < 0:
            segment.vel -= normal * incoming

    @classmethod
    def _projetar_segmento_porta(cls, segment, previous, box, radius: float) -> None:
        ref_prev = (float(previous.pos.x), float(previous.pos.y), float(previous.pos.z))
        for frac in (0.35, 0.70):
            sample = previous.pos + (segment.pos - previous.pos) * frac
            res_mid = box.project_door_xyz(
                float(sample.x),
                float(sample.y),
                float(sample.z),
                radius * 0.92,
                ref_prev=ref_prev,
            )
            if res_mid is not None:
                segment.pos += Vec3(*res_mid) - sample
        res = box.project_door_xyz(
            float(segment.pos.x),
            float(segment.pos.y),
            float(segment.pos.z),
            radius,
            ref_prev=ref_prev,
        )
        if res is None:
            return
        new_pos = Vec3(*res)
        correction = new_pos - segment.pos
        segment.pos = new_pos
        cls._amortecer_velocidade_normal(segment, correction)

    @classmethod
    def _passo_porta_firme(
        cls,
        tentacle: Tentacle,
        door_boxes: list,
        radii_door: list[float],
    ) -> None:
        if not door_boxes:
            return
        segments = tentacle.segments
        for index in range(1, len(segments)):
            segment = segments[index]
            previous = segments[index - 1]
            radius = radii_door[index]
            for box in door_boxes:
                cls._projetar_segmento_porta(segment, previous, box, radius)

    def _colidir_segmento_corpo(
        self,
        tentacle: Tentacle,
        index: int,
        previous,
        segment,
        non_cab: list,
        cab_boxes: list,
        radius: float,
        radius_door: float,
        front_dir: Vec3,
        passo: int,
    ) -> None:
        limiar_frente = 0.04 if tentacle.state == TentacleState.RETRACTING else 0.09
        avanco = (segment.pos - tentacle.anchor).dot(front_dir)
        if non_cab and index >= 3 and avanco > limiar_frente:
            if passo == 0:
                midpoint = (previous.pos + segment.pos) * 0.5
                segment.pos += self._projetar_sem_recuo(
                    tentacle, midpoint, radius * 0.85, non_cab, front_dir
                )
            correction = self._projetar_sem_recuo(
                tentacle, segment.pos, radius, non_cab, front_dir
            )
            segment.pos += correction
            self._amortecer_velocidade_normal(segment, correction)
        if cab_boxes and index >= 1:
            corr_cab = self._projetar_sem_recuo(
                tentacle,
                segment.pos,
                max(radius, radius_door * 0.78),
                cab_boxes,
                front_dir,
            )
            segment.pos += corr_cab
            self._amortecer_velocidade_normal(segment, corr_cab)

    def _passo_colisao_tentaculo(
        self,
        tentacle: Tentacle,
        body_boxes: list,
        door_boxes: list,
        radii: list[float],
        radii_door: list[float],
        front_dir: Vec3,
        passo: int,
    ) -> None:
        segments = tentacle.segments
        n = len(segments)
        non_cab = [b for b in body_boxes if not b.name.startswith("cabinet-wall-")] if body_boxes else []
        cab_boxes = [b for b in body_boxes if b.name.startswith("cabinet-wall-")] if body_boxes else []
        for index in range(1, n):
            segment = segments[index]
            previous = segments[index - 1]
            if index + 1 < n:
                midpoint = (previous.pos + segments[index + 1].pos) * 0.5
                segment.pos += (midpoint - segment.pos) * 0.16
            self._colidir_segmento_corpo(
                tentacle,
                index,
                previous,
                segment,
                non_cab,
                cab_boxes,
                radii[index],
                radii_door[index],
                front_dir,
                passo,
            )
        self._passo_porta_firme(tentacle, door_boxes, radii_door)

    def _radii_tentaculo(
        self, tentacle: Tentacle
    ) -> tuple[list[float], list[float]]:
        segments = tentacle.segments
        span = max(1.0, (len(segments) - 1) * tentacle.reveal)
        radii = []
        radii_door = []
        for idx, segment in enumerate(segments):
            base = (
                raio_tentaculo(idx / span)
                * tentacle.girth_scale
                * compressao_saida(tentacle, segment.pos)
            )
            radii.append(base * (0.40 if idx < 7 else 0.52))
            radii_door.append(max(0.018, base * 0.98))
        return radii, radii_door

    def _restringir_funil_frontal(self, tentacle: Tentacle) -> None:
        """Garante que todo tentáculo saia estritamente pela abertura frontal do gabinete."""
        if self.door_node is None or self.model_np is None:
            return
        head = self.door_node.getParent()
        if head.isEmpty():
            return
        segments = tentacle.segments
        anchor_h = head.getRelativePoint(self.model_np, tentacle.anchor)
        min_root_y = min(0.045, float(anchor_h.y) - 0.005)
        for index in range(1, len(segments)):
            seg = segments[index]
            p = head.getRelativePoint(self.model_np, seg.pos)
            px, py, pz = float(p.x), float(p.y), float(p.z)
            viol = Vec3(0.0, 0.0, 0.0)
            if py < min_root_y:
                viol.y = 1.0
                py = min_root_y
            # Vão real do Armario em `head`: x=[-0.096, 0.096], z=[-0.042, 0.295], frente em y=0.156.
            if py <= 0.255:
                f = max(0.0, (py - 0.162) / (0.255 - 0.162))
                lim_x = 0.096 + f * 0.24
                lim_z_lo = -0.042 - f * 0.22
                lim_z_hi = 0.295 + f * 0.22
                if px < -lim_x:
                    viol.x = 1.0
                    px = -lim_x
                elif px > lim_x:
                    viol.x = -1.0
                    px = lim_x
                if pz < lim_z_lo:
                    viol.z = 1.0
                    pz = lim_z_lo
                elif pz > lim_z_hi:
                    viol.z = -1.0
                    pz = lim_z_hi
            elif (abs(px) > 0.102 or pz < -0.046 or pz > 0.305) and py < 0.168:
                viol.y = 1.0
                py = 0.168
            p_corr = Point3(px, py, pz)
            seg.pos = Vec3(self.model_np.getRelativePoint(head, p_corr))
            if viol.lengthSquared() > 0.0:
                vn = self.model_np.getRelativeVector(head, viol).normalized()
                inward = seg.vel.dot(vn)
                if inward < 0.0:
                    seg.vel -= vn * inward

    def _solve_contacts(self, tentacle):
        if not tentacle.contacts:
            self._restringir_funil_frontal(tentacle)
            return
        segments = tentacle.segments
        if len(segments) < 2:
            return
        nearby = tentacle.contacts.region(
            [seg.pos for seg in segments], 0.09 * tentacle.girth_scale
        )
        body_boxes = [b for b in nearby if b.name != "door"]
        door_boxes = [b for b in tentacle.contacts.boxes if b.name == "door"]
        if not body_boxes and not door_boxes:
            for _ in range(2):
                self._relaxar_corrente_tentaculo(segments, dividir_elos=False)
            self._restringir_funil_frontal(tentacle)
            return
        radii, radii_door = self._radii_tentaculo(tentacle)
        _, front_dir, _ = _base_frente(tentacle)
        for passo in range(2):
            self._passo_colisao_tentaculo(
                tentacle, body_boxes, door_boxes, radii, radii_door, front_dir, passo
            )
            self._relaxar_corrente_tentaculo(segments, dividir_elos=True)
        # Reprojeção final após relaxamento impede que a tensão dos elos puxe um nó
        # de volta para dentro da folha fina da porta.
        if door_boxes:
            self._passo_porta_firme(tentacle, door_boxes, radii_door)
        self._restringir_funil_frontal(tentacle)

    def reprojetar_portas(self) -> None:
        """Sincroniza segmentos contra as caixas da porta após giro final no quadro."""
        for limb in self.pool.tentacles:
            if limb.state == TentacleState.DORMANT or not limb.contacts:
                continue
            door_boxes = [b for b in limb.contacts.boxes if b.name == "door"]
            if door_boxes:
                _, radii_door = self._radii_tentaculo(limb)
                self._passo_porta_firme(limb, door_boxes, radii_door)
                self._relaxar_corrente_tentaculo(limb.segments, dividir_elos=False)
                self._passo_porta_firme(limb, door_boxes, radii_door)
            self._restringir_funil_frontal(limb)

    def _check_state_transition(self, tentacle: Tentacle) -> None:  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
        st = tentacle.state

        if st == TentacleState.CURIOUS:
            # O atuador só é solto pela coreografia.
            if tentacle is not self._atuador and tentacle.state_time > (
                1.75 if self.burst else 4.8
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
                    lateral, forward, up = _base_frente(tentacle)
                    eject_dir = (
                        lateral * self.rng.uniform(-0.65, 0.65)
                        + forward
                        + up * self.rng.uniform(-0.45, 0.45)
                    ).normalized()
                    tentacle.target = tentacle.anchor + eject_dir * (220.0 * tentacle.unit_scale)
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

    def _projetar_alvo_frontal_cabeca(
        self, ponto: Vec3, *, min_y: float = 0.24
    ) -> Vec3:
        """Mantém alvos livres no hemisfério frontal da cabeça para não virar para trás."""
        if self.door_node is None or self.model_np is None:
            return ponto
        head = self.door_node.getParent()
        if head.isEmpty():
            return ponto
        p = head.getRelativePoint(self.model_np, ponto)
        px = max(-0.48, min(0.48, float(p.x)))
        py = max(min_y, abs(float(p.y)) if float(p.y) < min_y else float(p.y))
        pz = max(-0.18, min(0.55, float(p.z)))
        return Vec3(self.model_np.getRelativePoint(head, Point3(px, py, pz)))

    def _update_frenzy(self, dt: float) -> None:
        # Targets caóticos sempre à frente da cabeça
        for t in self.pool.tentacles:
            if t.state == TentacleState.FRENZY and self.rng.random() < 0.02:
                t.target = self._projetar_alvo_frontal_cabeca(
                    self._random_target_near_mouse(radius=200.0, tentacle=t), min_y=0.28
                )

    def _update_swallow(self, dt: float) -> None:
        # Fase 1: REACHING -> GRABBING (puxa mouse pra dentro)
        # Fase 2: SPITTING (cuspe pra fora)
        # O director controla o timing via swallow_time
        pass  # Lógica está em _check_state_transition

    def _angulo_minimo_passagem(self) -> float:
        """Mantém o vão livre enquanto alguma ponta ainda está recolhendo."""
        maior_reveal = max(
            (
                t.reveal
                for t in self.pool.tentacles
                if t.state != TentacleState.DORMANT and t.reveal > 0.03
            ),
            default=0.0,
        )
        if maior_reveal <= 0.03:
            return 0.0
        fator = min(1.0, (maior_reveal - 0.03) / 0.12)
        return 22.0 * fator

    def _update_door(self, dt: float) -> None:
        if (
            self._atraso_abertura_porta > 0.0
            and self._door_current < coreo.LIMIAR_SAIDA_PORTA_GRAUS
        ):
            return
        min_passagem = self._angulo_minimo_passagem()
        if self._angulo_coreografado is not None:
            # Porta presa à coreografia (empurrão, esquecimento, puxão): sem suavização própria,
            # mas respeitando o vão mínimo se alguma ponta ainda estiver voltando.
            self._door_current = max(self._angulo_coreografado, min_passagem)
            if self.door_node:
                self.door_node.setH(self._door_current)
            return
        # Suaviza abertura/fechamento da porta
        alvo_porta = max(self._door_requested, min_passagem)
        diff = alvo_porta - self._door_current
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

    def _random_target_near_mouse(
        self, radius: float, tentacle: Tentacle | None = None
    ) -> Vec3:
        scale = tentacle.unit_scale if tentacle is not None else self.pool.unit_scale
        if self.mouse_pos is not None:
            angle = self.rng.uniform(0, 2 * math.pi)
            dist = self.rng.uniform(0, radius * scale)
            return self.mouse_pos + Vec3(
                math.cos(angle) * dist,
                math.sin(angle) * dist,
                0,
            )
        ref = tentacle or (self.pool.tentacles[0] if self.pool.tentacles else None)
        if ref is not None:
            lateral, forward, up = _base_frente(ref)
            d = (
                lateral * self.rng.uniform(-0.7, 0.7)
                + forward * self.rng.uniform(0.65, 1.05)
                + up * self.rng.uniform(-0.5, 0.5)
            ).normalized()
            return ref.anchor + d * max(0.24, radius * scale)
        return Vec3(0, 0, 0)

    # Targets em leque frontal amplo para separar cada silhueta inclusive de frente.
    _OFFSETS_CURIOUS: tuple[tuple[int, int, int], ...] = (
        (0, 144, 28),
        (-46, 134, 48),
        (52, 132, -34),
        (-36, 138, -42),
        (32, 128, 72),
        (-22, 130, -60),
    )

    _OFFSETS_SNEEZE: tuple[tuple[float, float, float], ...] = (
        (0.0, 152.0, -12.0),
        (-36.0, 140.0, -24.0),
        (38.0, 138.0, -22.0),
        (-46.0, 132.0, 12.0),
        (46.0, 134.0, 14.0),
    )

    @classmethod
    def _offset_curioso_enxurrada(cls, index: int) -> tuple[float, float, float]:
        """Concentra o jato de espirro em um leque frontal-inferior coeso de 5 tentáculos."""
        return cls._OFFSETS_SNEEZE[index % len(cls._OFFSETS_SNEEZE)]

    def _configurar_tentaculo_curioso(
        self,
        t: Tentacle,
        index: int,
        enxurrada: bool,
    ) -> None:
        if enxurrada:
            t.length_scale = 1.18
            t.girth_scale = 1.18
            t.duracao_revelacao_s = 0.44 + 0.04 * t.perfil
            t.duracao_recolher_s = 0.42
        else:
            t.length_scale = 1.08
            t.girth_scale = 1.05
        t.enxurrada = enxurrada
        for segment in t.segments:
            segment.length = SEGMENT_LENGTH * self.pool.unit_scale * t.length_scale
        t.state = TentacleState.CURIOUS
        # Cascata viva e ágil para todos os 3-5 tentáculos saírem juntos antes de recolher.
        t.state_time = -min(0.22, t.saida.escalonamento_s * 0.45) * index
        t.params = dict(STATE_PARAMS["curious"])
        if enxurrada:
            t.state_time = -0.040 * index
            t.params["max_len"] = 1.05
        # Offsets autorais (x lateral, y frente, z cima) seguem a frente da cabeça,
        # não o espaço do modelo, que já vem com o giro assado no asset.
        lateral, frente, cima = _base_frente(t)
        x, y, z = (
            self._offset_curioso_enxurrada(index)
            if enxurrada
            else self._OFFSETS_CURIOUS[index % len(self._OFFSETS_CURIOUS)]
        )
        if not enxurrada and self.appearance_count == 2:
            # Duas pontas em alturas distintas enquadram o centro da boca.
            x, z = ((-23, 34), (23, -16))[index]

        local_dir = Vec3(x, y, z).normalized()
        alvo_escala = (132.0 if enxurrada else 128.0) * self.pool.unit_scale * t.length_scale
        t.local_target = local_dir * alvo_escala
        offset = (
            lateral * t.local_target.x + frente * t.local_target.y + cima * t.local_target.z
        )
        t.target = t.anchor + offset

    def _spawn_curious(
        self, count: int, coreografar: bool = False, *, enxurrada: bool | None = None
    ) -> list[Tentacle]:
        active = self.pool.get_available(count)
        if active:
            self.appearance_count = len(active)
        if enxurrada is None:
            enxurrada = count >= TOTAL_ENXURRADA
        for index, t in enumerate(active):
            self._configurar_tentaculo_curioso(t, index, enxurrada)
        self._door_requested = max(self._door_requested, 105.0)
        if coreografar and active:
            self._iniciar_empurrao(active[0])
        return active

    # ------------------------------------------------------------------
    # Coreografia tentáculos x porta
    # ------------------------------------------------------------------

    @property
    def coreografia_ativa(self) -> bool:
        """Indica se a coreografia de abertura/fechamento da porta está ativa."""
        return self.coreografia.fase is not coreo.FasePorta.FECHADA

    def _resetar_segmentos_ancora(self, tentacle: Tentacle) -> None:
        """Reposiciona todos os segmentos na âncora para evitar salto ao reutilizar."""
        seg_len = SEGMENT_LENGTH * self.pool.unit_scale * tentacle.length_scale
        for segment in tentacle.segments:
            segment.pos = Vec3(tentacle.anchor)
            segment.vel = Vec3(0)
            segment.length = seg_len

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
        self._atraso_abertura_porta = 0.0
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
        if self._outro_dono_da_porta():
            return
        if self._door_current >= coreo.porta_tuning()["limiar_fechada_graus"]:
            self.coreografia.assumir_aberta()
            return
        borda = self._ponto_borda_porta()
        if borda is None:
            return
        self._atuador = empurrador
        self._alvo_atuador = empurrador.target
        self.aviso_antena_tempo = 0.54
        if not self.burst:
            self._atraso_abertura_porta = max(self._atraso_abertura_porta, 0.28)
        self.coreografia.iniciar_empurrao()

    def _avancar_coreografia(self, dt: float) -> None:
        if self.coreografia.fase is coreo.FasePorta.FECHADA:
            return
        atuador = self._atuador
        fase = self.coreografia.fase
        if (
            fase is coreo.FasePorta.EMPURRANDO
            and self._atraso_abertura_porta > 0.0
            and self._door_current < coreo.porta_tuning()["limiar_saida_graus"]
        ):
            self._angulo_coreografado = 0.0
            return
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
            atuador.duracao_recolher_s = coreo.porta_tuning()["volta_puxador_s"]
            self.pool.release(atuador)
            self._atuador = None

    def _apontar_atuador(self) -> None:
        """Mira o atuador na borda livre da porta (ou envolve a borda ao puxar)."""
        atuador = self._atuador
        borda = self._ponto_borda_porta()
        if atuador is None or borda is None:
            return
        if self.coreografia.fase is coreo.FasePorta.EMPURRANDO:
            # A ponta visível está em `reveal` da curva: estende o alvo para que a
            # ponta chegue à borda ao fim do empurrão, sem atravessar a parede lateral do gabinete.
            fim_emp = max(1e-4, coreo.porta_tuning()["revelacao_fim_empurrao"])
            alvo = atuador.anchor + (borda - atuador.anchor) / fim_emp
            if (
                self._door_current < 22.0
                and self.door_node is not None
                and self.model_np is not None
                and not self.door_node.getParent().isEmpty()
            ):
                head = self.door_node.getParent()
                p = head.getRelativePoint(self.model_np, alvo)
                alvo = self.model_np.getRelativePoint(
                    head,
                    Point3(
                        max(-0.090, min(0.095, float(p.x))),
                        min(0.175, float(p.y)),
                        max(0.075, min(0.285, float(p.z))),
                    ),
                )
            atuador.target = Vec3(alvo)
        elif self.coreografia.fase in (
            coreo.FasePorta.ALCANCANDO,
            coreo.FasePorta.PUXANDO,
        ):
            atuador.target = self._ponto_pegada_externa_porta() or borda
        else:
            atuador.target = borda

    def _chamar_puxador(self) -> None:
        disponiveis = self.pool.get_available(1)
        if not disponiveis:
            self._cancelar_coreografia()
            return
        # Prefere o tentáculo mais à esquerda do armário para sair pela fresta aberta.
        puxador = min(disponiveis, key=lambda t: float(t.anchor.x))
        puxador.state_time = 0.0
        puxador.reveal = 0.0
        puxador.local_target = None
        puxador.enxurrada = False
        # Comprimento proporcional à distância até a porta para formar arco limpo, sem embolar.
        puxador.length_scale = 0.45
        puxador.girth_scale = 0.72
        puxador.duracao_recolher_s = None
        puxador.params = dict(STATE_PARAMS["curious"])
        pt = coreo.porta_tuning()
        puxador.params["max_len"] = max(pt["alcance_puxador"], 0.55)
        puxador.params["wiggle_amp"] = min(float(puxador.params.get("wiggle_amp", 0.04)), 0.04)
        puxador.duracao_revelacao_s = pt["tempo_alcance_puxao_s"]
        puxador.mola_forcada = (pt["mola_puxador"], pt["amortecedor_puxador"])
        self._resetar_segmentos_ancora(puxador)
        self._atuador = puxador

    def _ponto_pegada_externa_porta(self) -> Vec3 | None:
        """Contorna a borda livre pela fresta e engancha a ponta na frente da porta."""
        if not self.door_node:
            return None
        if self._borda_porta_local is None and self._ponto_borda_porta() is None:
            return None
        borda_local = self._borda_porta_local
        assert borda_local is not None
        sinal_x = 1.0 if borda_local.x >= 0.0 else -1.0
        # Durante ALCANCANDO, primeiro sai pela fresta aberta e depois dobra sobre a borda frontal.
        if self.coreografia.fase is coreo.FasePorta.ALCANCANDO and self._atuador is not None:
            t_curva = max(0.0, min(1.0, (self._atuador.reveal - 0.55) / 0.40))
        else:
            t_curva = 1.0
        extra_x = (0.068 + (0.044 - 0.068) * t_curva) * sinal_x
        extra_y = -0.015 + (0.022 - (-0.015)) * t_curva
        pegada_local = Vec3(borda_local.x + extra_x, borda_local.y + extra_y, borda_local.z)
        return self.model_np.getRelativePoint(self.door_node, pegada_local)

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

    def _corredor_porta_aberta(self) -> tuple[Vec3, Vec3] | None:
        """Retorna a boca do gabinete e um ponto livre à frente dela."""
        if (
            self.door_node is None
            or self.model_np is None
            or self._door_current < coreo.LIMIAR_SAIDA_PORTA_GRAUS
        ):
            return None
        parent = self.door_node.getParent()
        if parent.isEmpty():
            return None
        # Centro real da abertura frontal do Armario no espaço local de ``head``.
        boca = Point3(0.0, 0.1465, 0.1812)
        return (
            self.model_np.getRelativePoint(parent, boca),
            self.model_np.getRelativePoint(parent, boca + Vec3(0.0, 0.28, 0.0)),
        )

    def sincronizar_ancora_e_frente(
        self, tentacle: Tentacle, anchor: Vec3, front: Vec3, up: Vec3 | None = None
    ) -> None:
        """Atualiza âncora, segmentos e alvo local conforme o giro atual da cabeça."""
        old_anchor = Vec3(tentacle.anchor)
        old_front = Vec3(tentacle.reference_front)
        new_front = Vec3(front)
        rot_q = Quat()
        if old_front.lengthSquared() > EPSILON_BASE_FRENTE and new_front.lengthSquared() > EPSILON_BASE_FRENTE:
            of = old_front.normalized()
            nf = new_front.normalized()
            cross = of.cross(nf)
            dot = max(-1.0, min(1.0, of.dot(nf)))
            if cross.lengthSquared() > 1e-10:
                rot_q.setFromAxisAngle(math.degrees(math.acos(dot)), cross.normalized())
            elif dot < -0.999:
                rot_q.setFromAxisAngle(180.0, Vec3(0, 0, 1))
        tentacle.anchor = Vec3(anchor)
        for segment in tentacle.segments:
            segment.pos = Vec3(anchor) + rot_q.xform(segment.pos - old_anchor)
            segment.vel = rot_q.xform(segment.vel)
        tentacle.reference_front = new_front
        if up is not None and up.lengthSquared() > EPSILON_BASE_FRENTE:
            tentacle.reference_up = Vec3(up).normalized()
        else:
            tentacle.reference_up = rot_q.xform(tentacle.reference_up)
        empurrando_porta = tentacle is self._atuador and self.coreografia.fase in (
            coreo.FasePorta.EMPURRANDO,
            coreo.FasePorta.ALCANCANDO,
            coreo.FasePorta.PUXANDO,
        )
        if not empurrando_porta and tentacle.local_target is not None:
            lateral, frente, cima = _base_frente(tentacle)
            offset = (
                lateral * tentacle.local_target.x
                + frente * tentacle.local_target.y
                + cima * tentacle.local_target.z
            )
            tentacle.target = tentacle.anchor + offset
        elif tentacle.target is not None:
            tentacle.target = Vec3(anchor) + rot_q.xform(tentacle.target - old_anchor)


def _base_frente(tentacle: Tentacle) -> tuple[Vec3, Vec3, Vec3]:
    """Base ortonormal (lateral, frente, cima) da cabeça no espaço do modelo."""
    frente = Vec3(tentacle.reference_front)
    if frente.lengthSquared() < EPSILON_BASE_FRENTE:
        frente = Vec3(0, 1, 0)
    frente.normalize()
    ref_up = Vec3(tentacle.reference_up)
    if ref_up.lengthSquared() < EPSILON_BASE_FRENTE:
        ref_up = Vec3(0, 0, 1)
    lateral = frente.cross(ref_up)
    if lateral.lengthSquared() < EPSILON_BASE_FRENTE:
        lateral = frente.cross(Vec3(0, 0, 1))
    if lateral.lengthSquared() < EPSILON_BASE_FRENTE:
        lateral = Vec3(1, 0, 0)
    lateral.normalize()
    return lateral, frente, lateral.cross(frente)


# ============================================================
# Rendering helper
# ============================================================


def raio_tentaculo(u: float) -> float:
    """Interpola as seções contínuas da base até a ponta."""
    raios = PERFIL_TENTACULO
    amostra = max(0.0, min(1.0, u)) * (len(raios) - 1)
    i = min(int(amostra), len(raios) - 2)
    return (raios[i] + (raios[i + 1] - raios[i]) * (amostra - i)) * 1.15


def compressao_saida(tentacle: Tentacle, center: Vec3) -> float:
    """Mantém base firme na saída sem achatar o corpo alongado na boca do armário."""
    distance = (center - tentacle.anchor).dot(tentacle.reference_front)
    base_min = 0.50 if tentacle.enxurrada else 0.75
    topo_max = 0.78 if tentacle.enxurrada else 1.0
    t = max(0.0, min(1.0, (distance - 0.02) / 0.20))
    return base_min + (topo_max - base_min) * t * t * (3.0 - 2.0 * t)


def _modulado_morfologia(
    morfologia: str, u: float, angle: float
) -> tuple[float, float, float, float]:
    """Retorna proporções limpas do primeiro modelo low-poly (sem caroços ou espinhos)."""
    del angle
    fator_tipo = {
        "chicote_longo": 0.94,
        "clava_lula": 1.04,
        "espinhoso_abissal": 1.00,
    }.get(morfologia, 1.02)
    base_firme = 1.0 + 0.05 * math.sin(min(1.0, max(0.0, u)) * math.pi)
    return base_firme * fator_tipo, 1.0, 0.82, 1.0


def create_tentacle_geometry(  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
    tentacle: Tentacle,
    parent: NodePath,
    outline_parent: NodePath,
    color: tuple[float, float, float, float] = (0.2, 0.6, 1.0, 0.9),
) -> None:
    """Cria a malha low-poly facetada original (6 lados, Blockbench) com ventosas hexagonais."""
    from itertools import pairwise

    from panda3d.core import (
        Geom,
        GeomNode,
        GeomTriangles,
        GeomVertexData,
        GeomVertexFormat,
        GeomVertexWriter,
        LineSegs,
        Material,
        Texture,
    )

    vertices: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    colors: list[tuple[float, float, float, float]] = []
    color_roles: list[str] = []
    indices: list[int] = []

    def add_vertex(point, normal, v_color, role: str) -> int:
        index = len(vertices)
        vertices.append(point)
        normals.append(normal)
        colors.append(v_color)
        color_roles.append(role)
        return index

    def _calc_norm(a, b, c) -> tuple[float, float, float]:
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        return (nx / ln, ny / ln, nz / ln)

    def add_flat_tri(a, b, c, v_color, role: str) -> None:
        n = _calc_norm(a, b, c)
        ia = add_vertex(a, n, v_color, role)
        ib = add_vertex(b, n, v_color, role)
        ic = add_vertex(c, n, v_color, role)
        indices.extend((ia, ib, ic))

    def add_flat_quad(a, b, c, d, v_color, role: str) -> None:
        n = _calc_norm(a, b, c)
        ia = add_vertex(a, n, v_color, role)
        ib = add_vertex(b, n, v_color, role)
        ic = add_vertex(c, n, v_color, role)
        id_ = add_vertex(d, n, v_color, role)
        indices.extend((ia, ib, ic, ia, ic, id_))

    # Perfil cônico encorpado fiel ao primeiro modelo (`bbefe06:tentacle_model.py`).
    base_profile = [
        (0.0, 0.072, 0.0),
        (0.075, 0.083, -0.007),
        (0.15, 0.071, -0.006),
        (0.23, 0.056, 0.005),
        (0.31, 0.041, 0.025),
        (0.39, 0.024, 0.056),
        (0.48, 0.006, 0.10),
    ]
    # Subdivisão em 2 passos preserva o ar low-poly facetado curvando suave na spline.
    profile = [
        tuple(a + (b - a) * step / 2 for a, b in zip(start, end, strict=True))
        for start, end in pairwise(base_profile)
        for step in range(2)
    ] + [base_profile[-1]]
    profile = [(z * 0.9, radius * 1.15, bend * 1.15) for z, radius, bend in profile]
    z_max = max(1e-6, profile[-1][0])
    estilo_padrao = ESTILOS_TENTACULO["padrao"]
    palette = estilo_padrao["mantle"]  # type: ignore[assignment]
    sides = 6
    rings_pos: list[list[tuple[float, float, float]]] = []
    for z, radius, bend in profile:
        u_ring = z / z_max
        ring_p = []
        for side in range(sides):
            angle = side * math.tau / sides
            ca, sa = math.cos(angle), math.sin(angle)
            mod_s, oval_x, oval_y, _ = _modulado_morfologia(
                tentacle.morfologia, u_ring, angle
            )
            ring_p.append(
                (
                    bend + radius * mod_s * oval_x * ca,
                    radius * mod_s * oval_y * sa,
                    z,
                )
            )
        rings_pos.append(ring_p)

    for row in range(len(rings_pos) - 1):
        for side in range(sides):
            nxt = (side + 1) % sides
            add_flat_quad(
                rings_pos[row][side],
                rings_pos[row][nxt],
                rings_pos[row + 1][nxt],
                rings_pos[row + 1][side],
                palette[side],
                f"mantle_{side}",
            )
    for side in range(sides):
        nxt = (side + 1) % sides
        add_flat_tri(
            (0.0, 0.0, 0.0),
            rings_pos[0][nxt],
            rings_pos[0][side],
            estilo_padrao["root"],  # type: ignore[arg-type]
            "root",
        )
    z_tip, _rad_tip, bend_tip = profile[-1]
    for side in range(sides):
        nxt = (side + 1) % sides
        add_flat_tri(
            (bend_tip, 0.0, z_tip),
            rings_pos[-1][side],
            rings_pos[-1][nxt],
            estilo_padrao["tip"],  # type: ignore[arg-type]
            "tip",
        )

    # Cinco ventosas hexagonais salientes (estilo Blockbench do 1º modelo) ao longo do lado frontal.
    for z_raw, body_rad_raw, bend_raw, rad_raw in (
        (0.09, 0.080, -0.007, 0.027),
        (0.175, 0.066, 0.0, 0.025),
        (0.255, 0.051, 0.012, 0.021),
        (0.33, 0.036, 0.032, 0.017),
        (0.395, 0.023, 0.056, 0.013),
    ):
        z = z_raw * 0.9
        body_radius = body_rad_raw * 1.15
        bend = bend_raw * 1.15
        radius = rad_raw * 1.12
        for lower, upper in pairwise(profile):
            if lower[0] <= z <= upper[0]:
                fraction = (z - lower[0]) / max(1e-6, upper[0] - lower[0])
                body_radius = lower[1] + (upper[1] - lower[1]) * fraction
                bend = lower[2] + (upper[2] - lower[2]) * fraction
                break
        mod_suck, _ox_s, oval_sy, _ = _modulado_morfologia(
            tentacle.morfologia, z / z_max, math.pi * 0.5
        )
        base_y = body_radius * mod_suck * oval_sy * math.cos(math.pi / 6) - 0.004
        back = [
            (bend + radius * math.cos(s * math.tau / 6), base_y, z + radius * math.sin(s * math.tau / 6))
            for s in range(6)
        ]
        lip = [
            (bend + radius * math.cos(s * math.tau / 6), base_y + 0.022, z + radius * math.sin(s * math.tau / 6))
            for s in range(6)
        ]
        inner = [
            (bend + radius * 0.58 * math.cos(s * math.tau / 6), base_y + 0.023, z + radius * 0.58 * math.sin(s * math.tau / 6))
            for s in range(6)
        ]
        hole = [
            (bend + radius * 0.44 * math.cos(s * math.tau / 6), base_y + 0.003, z + radius * 0.44 * math.sin(s * math.tau / 6))
            for s in range(6)
        ]
        for side in range(6):
            nxt = (side + 1) % 6
            add_flat_quad(back[side], lip[side], lip[nxt], back[nxt], estilo_padrao["sucker_0"], "sucker_0")  # type: ignore[arg-type]
            add_flat_quad(lip[side], inner[side], inner[nxt], lip[nxt], estilo_padrao["sucker_1"], "sucker_1")  # type: ignore[arg-type]
            add_flat_quad(inner[side], hole[side], hole[nxt], inner[nxt], estilo_padrao["sucker_2"], "sucker_2")  # type: ignore[arg-type]
            add_flat_tri((bend, base_y + 0.002, z), hole[nxt], hole[side], estilo_padrao["sucker_3"], "sucker_3")  # type: ignore[arg-type]

    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("procedural-tentacle", GeomVertexFormat.getV3n3c4t2(), Geom.UHDynamic)
    vw, nw, cw = (
        GeomVertexWriter(vdata, name) for name in ("vertex", "normal", "color")
    )
    uv = GeomVertexWriter(vdata, "texcoord")
    for vertex, normal, v_col in zip(vertices, normals, colors, strict=True):
        # UV de repouso: a pele acompanha a dobra sem deslizar entre os anéis.
        x, y, z = vertex
        lateral = y if abs(normal[0]) > abs(normal[1]) else x
        uv.addData2(.5 + lateral*4., z/z_max)
        vw.addData3(*vertex)
        nw.addData3(*normal)
        cw.addData4f(*v_col)
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
    mat_tentaculo = Material()
    mat_tentaculo.setBaseColor((1.0, 1.0, 1.0, 1.0))
    mat_tentaculo.setRoughness(0.76)
    mat_tentaculo.setMetallic(0.0)
    mesh_node.setMaterial(mat_tentaculo, 1)
    # Textura branca opaca mantém o shader de contorno/alpha independente da porta do CRT.
    white = Texture("tentacle-opaque")
    white.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRgba)
    white.setRamImage(bytes((255, 255, 255, 255)))
    from sejoga.render.sprites_efeitos import textura_acabamento

    mesh_node.setTexture(textura_acabamento("pele"), 1)

    # Malha estanque de contorno com anéis compartilhados (não abre frestas nas quinas flat!).
    out_vdata = GeomVertexData("procedural-tentacle-outline", fmt, Geom.UHDynamic)
    ovw, onw, ocw = (
        GeomVertexWriter(out_vdata, name) for name in ("vertex", "normal", "color")
    )
    out_rest: list[tuple[float, float, float]] = []
    out_norms: list[tuple[float, float, float]] = []
    out_rings: list[list[int]] = []
    for (z, _r, bend), ring_pts in zip(profile, rings_pos, strict=True):
        ring_idx: list[int] = []
        for side, pt in enumerate(ring_pts):
            angle = side * math.tau / sides
            idx_v = len(out_rest)
            ovw.addData3(*pt)
            n_rad = (math.cos(angle), math.sin(angle), 0.0)
            onw.addData3(*n_rad)
            ocw.addData4f(1.0, 1.0, 1.0, 1.0)
            out_rest.append((z / 0.432, (pt[0] - bend) * 0.65, pt[1] * 0.65))
            out_norms.append(n_rad)
            ring_idx.append(idx_v)
        out_rings.append(ring_idx)
    out_c_base = len(out_rest)
    ovw.addData3(0.0, 0.0, 0.0)
    onw.addData3(0.0, 0.0, -1.0)
    ocw.addData4f(1.0, 1.0, 1.0, 1.0)
    out_rest.append((0.0, 0.0, 0.0))
    out_norms.append((0.0, 0.0, -1.0))
    out_c_tip = len(out_rest)
    ovw.addData3(bend_tip, 0.0, z_tip)
    onw.addData3(0.0, 0.0, 1.0)
    ocw.addData4f(1.0, 1.0, 1.0, 1.0)
    out_rest.append((z_tip / 0.432, 0.0, 0.0))
    out_norms.append((0.0, 0.0, 1.0))

    outline_faces = GeomTriangles(Geom.UHStatic)
    for row in range(len(out_rings) - 1):
        for side in range(sides):
            nxt = (side + 1) % sides
            a, b = out_rings[row][side], out_rings[row][nxt]
            c, d = out_rings[row + 1][nxt], out_rings[row + 1][side]
            outline_faces.addVertices(a, b, c)
            outline_faces.addVertices(a, c, d)
    for side in range(sides):
        nxt = (side + 1) % sides
        outline_faces.addVertices(out_c_base, out_rings[0][nxt], out_rings[0][side])
        outline_faces.addVertices(out_c_tip, out_rings[-1][side], out_rings[-1][nxt])
    outline_faces.closePrimitive()
    outline_geom = Geom(out_vdata)
    outline_geom.addPrimitive(outline_faces)
    outline = GeomNode("procedural-tentacle-outline")
    outline.addGeom(outline_geom)
    outline_node = outline_parent.attachNewNode(outline)
    outline_node.setTexture(white, 1)
    outline_node.setShaderInput("outline_color", (0.10, 0.02, 0.14, 1.0), 1)
    mesh_node.hide()
    outline_node.hide()
    tentacle.mesh_node = mesh_node
    tentacle.outline_mesh_node = outline_node
    tentacle.mesh_vdata = vdata
    tentacle.color_roles = color_roles
    tentacle.outline_vdata = out_vdata
    tentacle.outline_rest_vertices = out_rest
    tentacle.outline_normals = out_norms
    tentacle.template_vertices = vertices
    tentacle.template_normals = normals
    tentacle.rest_vertices = []
    for x, y, z in vertices:
        bend_v = profile[-1][2]
        for (za, _ra, ba), (zb, _rb, bb) in pairwise(profile):
            if z <= zb:
                bend_v = ba + (bb - ba) * max(0.0, (z - za) / max(1e-6, zb - za))
                break
        tentacle.rest_vertices.append((z / 0.432, (x - bend_v) * 0.65, y * 0.65))
    lines = LineSegs("tentacle-joint-axes")
    lines.setThickness(1.5)
    for line_color, endpoint in (
        ((1, 0.15, 0.15, 1), (0.035, 0, 0)),
        ((0.15, 1, 0.2, 1), (0, 0.035, 0)),
        ((0.2, 0.4, 1, 1), (0, 0, 0.05)),
    ):
        lines.setColor(*line_color)
        lines.moveTo(0, 0, 0)
        lines.drawTo(*endpoint)
    axes = lines.create()
    tentacle.axis_nodes = []
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

    points = [Vec3(seg.pos) for seg in tentacle.segments]

    # Assinatura barata da entrada: a malha depende só da pose dos segmentos,
    # do reveal, da espessura, da fase de torção (quantizada a 20 Hz) e da frente.
    signature = (
        round(tentacle.reveal, 5),
        round(tentacle.girth_scale, 5),
        tentacle.enxurrada,
        int(tentacle.state_time * 20.0),
        tuple(round(c, 5) for c in tentacle.reference_front),
        tuple(round(c, 4) for point in points for c in point),
    )
    if signature == tentacle._last_render_signature:
        return
    tentacle._last_render_signature = signature

    # Parallel transport (Bishop frames): transporta o eixo transversal por
    # rotação mínima ao longo da curva sem acumular projeções que pinçam ou giram.
    n_pts = len(points)
    tangents = []
    for index in range(n_pts):
        tangent = points[min(index + 1, n_pts - 1)] - points[max(0, index - 1)]
        if tangent.lengthSquared() < 1e-10:
            tangent = Vec3(tentacle.reference_front)
        if tangent.lengthSquared() < 1e-10:
            tangent = Vec3(0, 1, 0)
        tangent.normalize()
        tangents.append(tangent)

    lateral, frente, cima = _base_frente(tentacle)
    # Orientação oposta à curvatura faz o transporte paralelo girar a fileira de
    # ventosas (+Y local) naturalmente para o lado frontal visível ao observador.
    desvio = points[-1] - points[0]
    curva = desvio - tangents[0] * desvio.dot(tangents[0])
    bias_lateral = (0.35, -0.35, 0.25)[tentacle.perfil % 3]
    front = frente * 0.35 + lateral * bias_lateral - cima * 0.15
    if curva.lengthSquared() > 1e-6:
        curva.normalize()
        front = -curva * 0.88 + frente * 0.35 + lateral * bias_lateral
    front -= tangents[0] * front.dot(tangents[0])
    if front.lengthSquared() < 1e-4:
        front = Vec3(0, 0, 1) - tangents[0] * tangents[0].z
    if front.lengthSquared() < 1e-4:
        front = Vec3(1, 0, 0) - tangents[0] * tangents[0].x
    front.normalize()
    right = front.cross(tangents[0]).normalized()

    twist_rate = (
        0.22 + math.sin(tentacle.state_time * 0.85 + tentacle.seed * 0.001) * 0.14
    )
    frames = []
    bishop_axes = []
    for index, center in enumerate(points):
        tangent = tangents[index]
        if index > 0:
            prev_t = tangents[index - 1]
            rot_axis = prev_t.cross(tangent)
            if rot_axis.lengthSquared() > 1e-10:
                dot = max(-1.0, min(1.0, prev_t.dot(tangent)))
                rot_q = Quat()
                rot_q.setFromAxisAngle(math.degrees(math.acos(dot)), rot_axis.normalized())
                front = rot_q.xform(front)
                right = rot_q.xform(right)
            elif prev_t.dot(tangent) < -0.999:
                front = -front
                right = -right
            front -= tangent * front.dot(tangent)
            front.normalize()
            right = front.cross(tangent).normalized()
        bishop_axes.append((Vec3(right), Vec3(front)))
        u = index / max(1, n_pts - 1)
        twist = twist_rate * u
        cos_t, sin_t = math.cos(twist), math.sin(twist)
        transverse_x = right * cos_t + front * sin_t
        transverse_y = front * cos_t - right * sin_t
        frames.append((center, tangent, transverse_x, transverse_y))
        orientation = Mat3(*transverse_x, *transverse_y, *tangent)
        rotation = Quat()
        rotation.setFromMatrix(orientation)
        tentacle.segments[index].rot = rotation
        if index < len(tentacle.axis_nodes) and not tentacle.axis_nodes[index].isHidden():
            tentacle.axis_nodes[index].setPos(center)
            tentacle.axis_nodes[index].setQuat(rotation)
    tentacle.frames = frames
    unique_us = getattr(tentacle, "_unique_us", None)
    vertex_table = getattr(tentacle, "_vertex_table", None)
    outline_table = getattr(tentacle, "_outline_table", None)
    if unique_us is None or vertex_table is None:
        u_map: dict[float, int] = {}
        u_list: list[float] = []

        def _index_u(u_val: float) -> int:
            idx = u_map.get(u_val)
            if idx is None:
                idx = len(u_list)
                u_map[u_val] = idx
                u_list.append(u_val)
            return idx

        vertex_table = tuple(
            (_index_u(u), float(x), float(y), float(lnx), float(lny), float(lnz))
            for (u, x, y), (lnx, lny, lnz) in zip(
                tentacle.rest_vertices, tentacle.template_normals, strict=True
            )
        )
        out_rv = getattr(tentacle, "outline_rest_vertices", [])
        out_nm = getattr(tentacle, "outline_normals", [])
        if out_rv and out_nm and len(out_rv) == len(out_nm):
            outline_table = tuple(
                (_index_u(u), float(x), float(y), float(lnx), float(lny), float(lnz))
                for (u, x, y), (lnx, lny, lnz) in zip(out_rv, out_nm, strict=True)
            )
        else:
            outline_table = None
        unique_us = tuple(u_list)
        tentacle._unique_us = unique_us
        tentacle._vertex_table = vertex_table
        tentacle._outline_table = outline_table

    ring_table = []
    max_seg_idx = n_pts - 2
    reveal_span = tentacle.reveal * (n_pts - 1)
    girth_reveal = tentacle.girth_scale * (0.72 + 0.28 * tentacle.reveal)
    for u in unique_us:
        t_clamped = 0.0 if u < 0.0 else (1.0 if u > 1.0 else u)
        sample = t_clamped * reveal_span
        index = int(sample)
        if index > max_seg_idx:
            index = max_seg_idx
        alpha = sample - index
        p0, p1 = points[0 if index == 0 else index - 1], points[index]
        p2, p3 = points[index + 1], points[n_pts - 1 if index + 2 >= n_pts else index + 2]
        a = -p0 + p2
        b = p0 * 2 - p1 * 5 + p2 * 4 - p3
        c = -p0 + p1 * 3 - p2 * 3 + p3
        center = (p1 * 2 + a * alpha + b * (alpha * alpha) + c * (alpha * alpha * alpha)) * 0.5
        tangent = (a + b * (2 * alpha) + c * (3 * alpha * alpha)) * 0.5
        if tangent.lengthSquared() < 1e-10:
            tangent = frames[index][1]
        tangent.normalize()
        _, f0 = bishop_axes[index]
        _, f1 = bishop_axes[index + 1]
        if f0.dot(f1) < 0.0:
            f1 = -f1
        base_front = f0 * (1.0 - alpha) + f1 * alpha
        base_front -= tangent * base_front.dot(tangent)
        if base_front.lengthSquared() < 1e-6:
            base_front = f0
        base_front.normalize()
        base_right = base_front.cross(tangent).normalized()
        twist = twist_rate * (sample / max(1, n_pts - 1))
        cos_t, sin_t = math.cos(twist), math.sin(twist)
        right = base_right * cos_t + base_front * sin_t
        front_f = base_front * cos_t - base_right * sin_t
        ring_table.append(
            (
                float(center.x),
                float(center.y),
                float(center.z),
                float(right.x),
                float(right.y),
                float(right.z),
                float(front_f.x),
                float(front_f.y),
                float(front_f.z),
                float(tangent.x),
                float(tangent.y),
                float(tangent.z),
                girth_reveal * compressao_saida(tentacle, center),
            )
        )

    def deform(vdata, table, rw_v_attr: str, rw_n_attr: str) -> None:
        vertex_writer = getattr(tentacle, rw_v_attr, None)
        normal_writer = getattr(tentacle, rw_n_attr, None)
        if vertex_writer is None or normal_writer is None:
            vertex_writer = GeomVertexRewriter(vdata, "vertex")
            normal_writer = GeomVertexRewriter(vdata, "normal")
            setattr(tentacle, rw_v_attr, vertex_writer)
            setattr(tentacle, rw_n_attr, normal_writer)
        vertex_writer.setRow(0)
        normal_writer.setRow(0)
        sqrt = math.sqrt
        set_pos = vertex_writer.setData3
        set_norm = normal_writer.setData3
        for u_idx, x, y, nx, ny, nz in table:
            cx, cy, cz, rx, ry, rz, fx, fy, fz, tx, ty, tz, girth = ring_table[u_idx]
            xg, yg = x * girth, y * girth
            vx_n = rx * nx + fx * ny + tx * nz
            vy_n = ry * nx + fy * ny + ty * nz
            vz_n = rz * nx + fz * ny + tz * nz
            n2 = vx_n * vx_n + vy_n * vy_n + vz_n * vz_n
            if n2 > 1e-10:
                inv_n = 1.0 / sqrt(n2)
                vx_n, vy_n, vz_n = vx_n * inv_n, vy_n * inv_n, vz_n * inv_n
            set_pos(
                cx + rx * xg + fx * yg,
                cy + ry * xg + fy * yg,
                cz + rz * xg + fz * yg,
            )
            set_norm(vx_n, vy_n, vz_n)

    deform(tentacle.mesh_vdata, vertex_table, "_vertex_rewriter", "_normal_rewriter")
    tentacle.mesh_node.node().markInternalBoundsStale()
    if (
        tentacle.outline_vdata is not None
        and tentacle.outline_vdata is not tentacle.mesh_vdata
        and outline_table is not None
    ):
        deform(
            tentacle.outline_vdata,
            outline_table,
            "_out_vertex_rewriter",
            "_out_normal_rewriter",
        )
    if tentacle.outline_mesh_node:
        tentacle.outline_mesh_node.node().markInternalBoundsStale()

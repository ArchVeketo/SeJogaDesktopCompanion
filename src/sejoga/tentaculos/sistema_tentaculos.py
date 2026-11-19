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
PERFIL_TENTACULO = (0.062, 0.076, 0.074, 0.065, 0.052, 0.038, 0.023, 0.001)
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
    reference_front: Vec3 = field(default_factory=lambda: Vec3(0, -1, 0))
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
        """Força um momento curious (espiada)."""
        self._spawn_curious(
            count=count if count is not None else self.rng.choices(
                (1, 2, 3), weights=(30, 58, 12), k=1
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
        for index, limb in enumerate(limbs):
            limb.target = Vec3((-1 if index == 0 else 1) * 0.35, -0.44, 0.24)
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
        self._spawn_curious(TOTAL_ENXURRADA)
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
            a = meio_vao + lateral * (delta_lat * 0.28) + up * (delta_up * 0.24)
            b = (
                saida_livre
                + forward * (0.16 * tentacle.length_scale)
                + lateral * (delta_lat * 0.62)
                + up * (delta_up * 0.48)
                + espalhamento * 0.55
            )
        else:
            a = (
                tentacle.anchor
                + forward * (0.22 * tentacle.length_scale)
                + lateral * (delta_lat * 0.16 - 0.015 * tentacle.length_scale)
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
    ) -> Vec3:
        arch = math.sin(math.pi * t_param)
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
        target_pos += lateral * (onda_lateral * escala_onda) + up * (
            onda_cima * escala_onda
        )
        arco_extra = float(traj.get("elevacao_arco", 0.0))
        avanco_extra = float(traj.get("avanco_frontal", 0.0))
        escala_alc = float(traj.get("escala_alcance", 1.0))
        if abs(escala_alc - 1.0) > 1e-6:
            target_pos = tentacle.anchor + (target_pos - tentacle.anchor) * escala_alc
        return (
            target_pos
            + forward * ((8.0 + avanco_extra * 100.0) * tentacle.unit_scale * arch)
            + up * ((12.0 + arco_extra * 100.0) * tentacle.unit_scale * arch)
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
    ) -> Vec3:
        """Calcula a posição-alvo ao longo da Bézier com espiral na ponta e ondulação."""
        if tentacle.target is None or p["reach_speed"] == 0:
            return tentacle.anchor
        a, b, delta = self._pontos_bezier_curva(
            tentacle, lateral, forward, up, curve, p["curl"]
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
            angle = (u - start) * turn
            target_pos = base + (
                along * math.sin(angle) + bend * (1 - math.cos(angle))
            ) * (tangent.length() / max(0.35, turn))
        return self._aplicar_ondulacao_e_arco(
            tentacle, target_pos, t_param, lateral, forward, up, curl_tip
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
    ) -> None:
        if i == 0:
            seg.pos = Vec3(tentacle.anchor)
            seg.vel = Vec3(0)
            return
        t_param = i / (n_seg - 1) if n_seg > 1 else 0.0
        target_pos = self._alvo_segmento_curva(
            tentacle, t_param, p, lateral, forward, up, curve, curl_tip
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
        if cab_boxes and index >= 2 and avanco > 0.02:
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

    def _solve_contacts(self, tentacle):
        if not tentacle.contacts:
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

    def reprojetar_portas(self) -> None:
        """Sincroniza segmentos contra as caixas da porta após giro final no quadro."""
        for limb in self.pool.tentacles:
            if limb.state == TentacleState.DORMANT or not limb.contacts:
                continue
            door_boxes = [b for b in limb.contacts.boxes if b.name == "door"]
            if not door_boxes:
                continue
            _, radii_door = self._radii_tentaculo(limb)
            self._passo_porta_firme(limb, door_boxes, radii_door)
            self._relaxar_corrente_tentaculo(limb.segments, dividir_elos=False)
            self._passo_porta_firme(limb, door_boxes, radii_door)

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

    # Targets projetados claramente para fora da boca do armário sem emaranhar na porta.
    _OFFSETS_CURIOUS: tuple[tuple[int, int, int], ...] = (
        (-68, 148, 34),
        (72, 152, 24),
        (-46, 158, -28),
        (54, 144, -34),
    )

    _OFFSETS_SNEEZE: tuple[tuple[float, float, float], ...] = (
        (0.0, 172.0, -14.0),
        (-36.0, 158.0, -26.0),
        (38.0, 156.0, -24.0),
        (-48.0, 148.0, 6.0),
        (48.0, 150.0, 8.0),
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
            t.length_scale = 1.26
            t.girth_scale = 0.84
            t.duracao_revelacao_s = 0.48 + 0.04 * t.perfil
            t.duracao_recolher_s = 0.42
        else:
            t.length_scale = 1.20
            t.girth_scale = 0.88
        t.enxurrada = enxurrada
        for segment in t.segments:
            segment.length = SEGMENT_LENGTH * self.pool.unit_scale * t.length_scale
        t.state = TentacleState.CURIOUS
        # Stagger the pair so the second tentacle follows the first.
        t.state_time = -t.saida.escalonamento_s * index
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

        local_dir = Vec3(x, y, z).normalized()
        alvo_escala = (168.0 if enxurrada else 178.0) * self.pool.unit_scale * t.length_scale
        t.local_target = local_dir * alvo_escala
        offset = (
            lateral * t.local_target.x + frente * t.local_target.y + cima * t.local_target.z
        )
        t.target = t.anchor + offset

    def _spawn_curious(self, count: int, coreografar: bool = False) -> list[Tentacle]:
        active = self.pool.get_available(count)
        if active:
            self.appearance_count = len(active)
        enxurrada = count >= TOTAL_ENXURRADA
        for index, t in enumerate(active):
            self._configurar_tentaculo_curioso(t, index, enxurrada)
        self._door_requested = max(self._door_requested, 85.0)
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
            # ponta chegue à borda ao fim do empurrão (aproximação linear).
            fim_emp = max(1e-4, coreo.porta_tuning()["revelacao_fim_empurrao"])
            atuador.target = (
                atuador.anchor + (borda - atuador.anchor) / fim_emp
            )
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
        hp = self.door_node.getPos()
        # A boca pertence à cabeça. A borda da folha sai desse plano ao girar.
        boca = Point3(0, hp.y, hp.z - 0.065)
        return (
            self.model_np.getRelativePoint(parent, boca),
            self.model_np.getRelativePoint(parent, boca + Vec3(0, 0.28, 0.01)),
        )

    def sincronizar_ancora_e_frente(
        self, tentacle: Tentacle, anchor: Vec3, front: Vec3
    ) -> None:
        """Atualiza âncora, segmentos e alvo local conforme o giro atual da cabeça."""
        delta = anchor - tentacle.anchor
        tentacle.anchor = Vec3(anchor)
        for segment in tentacle.segments:
            segment.pos += delta
        tentacle.reference_front = Vec3(front)
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
            tentacle.target += delta


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
    """Retorna ``(escala_radial, oval_x, oval_y, realce_junta)`` para a variação."""
    # Colarinho muscular na raiz (u <= 0.16): base anatômica espessa saindo do gabinete.
    base_collar = 1.0
    if u < 0.16:
        collar_phase = math.sin((u / 0.16) * math.pi)
        base_collar = 1.0 + 0.26 * collar_phase
    groove = 1.0
    oval_x, oval_y = 1.0, 1.0
    if morfologia == "chicote_longo":
        # Nós musculares intermediários que preservam volume mesmo bem estendidos.
        wave = math.sin(u * math.tau * 3.5)
        body_boost = 1.0 + (0.28 * max(0.0, 1.0 - abs(u - 0.55) / 0.45))
        ring_swell = 1.0 + 0.16 * wave
        groove = 0.88 if wave < -0.55 else (1.12 if wave > 0.55 else 1.0)
        return base_collar * body_boost * ring_swell, 1.04, 0.96, groove
    if morfologia == "clava_lula":
        # Haste esguia intermediária abrindo numa clava achatada cheia de ventosas.
        club = math.exp(-((u - 0.68) / 0.14) ** 2)
        stalk = 0.86 if 0.18 < u < 0.48 else 1.0
        scale = base_collar * (stalk + 0.52 * club)
        oval_x = 1.0 + 0.28 * club
        oval_y = 1.0 - 0.14 * club
        groove = 1.14 if club > 0.45 else 0.94
        return scale, oval_x, oval_y, groove
    if morfologia == "espinhoso_abissal":
        # Anéis serrilhados com crista dorsal pronunciada (lado -Y local = costas).
        crest = 1.0 + 0.14 * math.sin(u * math.tau * 5.0)
        dorsal = max(0.0, -math.sin(angle))
        spine_flare = 1.0 + 0.34 * (dorsal**3) * (0.5 + 0.5 * math.cos(u * math.tau * 5.0))
        groove = 0.86 + 0.22 * (1.0 - dorsal)
        return base_collar * crest * spine_flare, 0.96, 1.08, groove
    # musculoso (padrão robusto)
    swell = 1.0 + 0.12 * math.sin(u * math.tau * 2.5)
    return base_collar * swell, 1.02, 0.98, 1.0


def create_tentacle_geometry(  # noqa: C901, PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
    tentacle: Tentacle,
    parent: NodePath,
    outline_parent: NodePath,
    color: tuple[float, float, float, float] = (0.2, 0.6, 1.0, 0.9),
) -> None:
    """Cria a malha clássica esculpida em 8 lados, paleta carmesim rica e ventosas 3D."""
    from itertools import pairwise

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

    def add_vertex(point, normal, v_color):
        index = len(vertices)
        vertices.append(point)
        normals.append(normal)
        colors.append(v_color)
        return index

    def add_triangle(a, b, c):
        indices.extend((a, b, c))

    def add_quad(a, b, c, d):
        add_triangle(a, b, c)
        add_triangle(a, c, d)

    base_profile = [
        (0.0, 0.052, 0.0),
        (0.075, 0.083, -0.007),
        (0.15, 0.072, -0.006),
        (0.23, 0.058, 0.005),
        (0.31, 0.044, 0.025),
        (0.39, 0.030, 0.056),
        (0.45, 0.017, 0.084),
        (0.48, 0.007, 0.10),
    ]
    # Subdivide os anéis para curvar suavemente na spline sem degraus triangulares.
    profile = [
        tuple(a + (b - a) * step / 4 for a, b in zip(start, end, strict=True))
        for start, end in pairwise(base_profile)
        for step in range(4)
    ] + [base_profile[-1]]
    profile = [(z * 0.9, radius * 1.15, bend * 1.15) for z, radius, bend in profile]
    palette = [
        (0.82, 0.055, 0.26, 1),
        (0.94, 0.085, 0.33, 1),
        (1.00, 0.160, 0.42, 1),
        (0.90, 0.070, 0.30, 1),
        (0.74, 0.042, 0.22, 1),
        (0.62, 0.030, 0.17, 1),
        (0.66, 0.034, 0.19, 1),
        (0.76, 0.045, 0.23, 1),
    ]
    sides = 8
    rings = []
    for z, radius, bend in profile:
        ring = []
        for side in range(sides):
            angle = side * math.tau / sides - math.pi / 8
            ca, sa = math.cos(angle), math.sin(angle)
            ring.append(
                add_vertex(
                    (bend + radius * ca, radius * sa, z),
                    (ca, sa, 0),
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
    z_tip, _rad_tip, bend_tip = profile[-1]
    tip_center = add_vertex((bend_tip, 0, z_tip), (0, 0, 1), (0.94, 0.08, 0.32, 1))
    for side in range(sides):
        add_triangle(tip_center, rings[-1][side], rings[-1][(side + 1) % sides])

    mantle = tuple(indices)

    # Quatro ventosas hexagonais salientes soldadas ao manto (u por vértice).
    for z_raw, body_rad_raw, bend_raw, rad_raw in (
        (0.09, 0.080, -0.007, 0.026),
        (0.18, 0.065, 0.0, 0.024),
        (0.275, 0.047, 0.017, 0.020),
        (0.355, 0.030, 0.042, 0.015),
    ):
        z = z_raw * 0.9
        body_radius = body_rad_raw * 1.15
        bend = bend_raw * 1.15
        radius = rad_raw * 1.1
        for lower, upper in pairwise(profile):
            if lower[0] <= z <= upper[0]:
                fraction = (z - lower[0]) / max(1e-6, upper[0] - lower[0])
                body_radius = lower[1] + (upper[1] - lower[1]) * fraction
                bend = lower[2] + (upper[2] - lower[2]) * fraction
                break
        base_y = body_radius * math.cos(math.pi / 8) - 0.005

        r0, r1, r2, r3 = [], [], [], []
        for side in range(6):
            angle = side * math.tau / 6
            ca, sa = math.cos(angle), math.sin(angle)

            pt0 = (bend + radius * ca, base_y, z + radius * sa)
            norm_wall = (ca, 0.0, sa)
            r0.append(
                add_vertex(
                    pt0,
                    norm_wall,
                    (0.90, 0.055, 0.28, 1),
                )
            )

            pt1 = (bend + radius * ca, base_y + 0.025, z + radius * sa)
            r1.append(
                add_vertex(
                    pt1,
                    norm_wall,
                    (1.0, 0.28, 0.52, 1),
                )
            )

            pt2 = (bend + radius * 0.58 * ca, base_y + 0.026, z + radius * 0.58 * sa)
            r2.append(
                add_vertex(
                    pt2,
                    (0.0, 1.0, 0.0),
                    (0.64, 0.02, 0.15, 1),
                )
            )

            pt3 = (bend + radius * 0.45 * ca, base_y + 0.006, z + radius * 0.45 * sa)
            inv_n = 1.0 / math.sqrt(0.64 + 0.36)
            norm_in = (-ca * 0.8 * inv_n, 0.6 * inv_n, -sa * 0.8 * inv_n)
            r3.append(
                add_vertex(
                    pt3,
                    norm_in,
                    (0.27, 0.008, 0.055, 1),
                )
            )

        for side in range(6):
            nxt = (side + 1) % 6
            add_quad(r0[side], r1[side], r1[nxt], r0[nxt])
            add_quad(r1[side], r2[side], r2[nxt], r1[nxt])
            add_quad(r2[side], r3[side], r3[nxt], r2[nxt])

        pt_c = (bend, base_y + 0.006, z)
        c_idx = add_vertex(
            pt_c,
            (0.0, 1.0, 0.0),
            (0.27, 0.008, 0.055, 1),
        )
        for side in range(6):
            nxt = (side + 1) % 6
            add_triangle(c_idx, r3[nxt], r3[side])

    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("procedural-tentacle", fmt, Geom.UHDynamic)
    vw, nw, cw = (
        GeomVertexWriter(vdata, name) for name in ("vertex", "normal", "color")
    )
    for vertex, normal, v_col in zip(vertices, normals, colors, strict=True):
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
    # Textura branca opaca mantém o shader de contorno/alpha independente da porta do CRT.
    white = Texture("tentacle-opaque")
    white.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRgba)
    white.setRamImage(bytes((255, 255, 255, 255)))
    mesh_node.setTexture(white, 1)

    outline_faces = GeomTriangles(Geom.UHStatic)
    for i in range(0, len(mantle), 3):
        outline_faces.addVertices(*mantle[i : i + 3])
    outline_faces.closePrimitive()
    outline_geom = Geom(vdata)
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
    # Both shells share the same deforming vertex data. Rewriting a duplicate
    # would double the skinning and collision work without changing the pose.
    tentacle.outline_vdata = vdata
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
    # do reveal, da espessura, do state_time e da frente de referência.
    signature = (
        round(tentacle.reveal, 5),
        round(tentacle.girth_scale, 5),
        tentacle.enxurrada,
        round(tentacle.state_time, 4),
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

    front = Vec3(tentacle.reference_front) + Vec3(0, 0, -0.38)
    front -= tangents[0] * front.dot(tangents[0])
    if front.lengthSquared() < 1e-4:
        front = Vec3(0, 0, -1) - tangents[0] * tangents[0].z
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
    if unique_us is None or vertex_table is None:
        u_map: dict[float, int] = {}
        u_list: list[float] = []
        v_list = []
        for (u, x, y), (lnx, lny, lnz) in zip(
            tentacle.rest_vertices, tentacle.template_normals, strict=True
        ):
            idx = u_map.get(u)
            if idx is None:
                idx = len(u_list)
                u_map[u] = idx
                u_list.append(u)
            v_list.append((idx, float(x), float(y), float(lnx), float(lny), float(lnz)))
        unique_us = tuple(u_list)
        vertex_table = tuple(v_list)
        tentacle._unique_us = unique_us
        tentacle._vertex_table = vertex_table

    ring_table = []
    max_seg_idx = n_pts - 2
    reveal_span = tentacle.reveal * (n_pts - 1)
    girth_reveal = tentacle.girth_scale * min(1.0, max(0.35, tentacle.reveal**0.5))
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
        r0, f0 = bishop_axes[index]
        r1, f1 = bishop_axes[index + 1]
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
        sqrt = math.sqrt
        set_pos = vertex_writer.setData3
        set_norm = normal_writer.setData3
        for u_idx, x, y, nx, ny, nz in vertex_table:
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

    deform(tentacle.mesh_vdata)
    tentacle.mesh_node.node().markInternalBoundsStale()
    if tentacle.outline_mesh_node:
        tentacle.outline_mesh_node.node().markInternalBoundsStale()

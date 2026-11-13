"""Controlador procedural de animação do mascote.

As poses são produzidas pelo rig sem depender de clipes exportados. O
controlador escolhe um estado a partir da interação/física e faz crossfade
entre poses para evitar saltos bruscos.
"""

from __future__ import annotations

import random
from enum import StrEnum
from math import degrees
from typing import ClassVar

from sejoga.animacao import movimento_corpo_tuning as tune
from sejoga.animacao.agencia import Agencia
from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.animacao.camadas_animacao import (
    MASCARA_MUSICA,
    CamadaAnim,
    CamadaDelta,
    LayerStack,
    MixerCamadas,
    Prioridade,
)
from sejoga.animacao.estados_delta import (
    delta_drag,
    delta_fall,
    delta_fisica,
    delta_idle,
    delta_secundario,
    delta_sleep,
    delta_soltura,
    delta_walk,
    somar_deltas,
)
from sejoga.animacao.gestos_tuning import (
    ACENO_DURACAO_S,
    ALONGAR_DURACAO_S,
    CUTUCAR_DURACAO_S,
)
from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.molas_juntas import (
    CADEIA_COLUNA,
    CADEIA_DIREITA,
    CADEIA_ESQUERDA,
    CADEIA_FONE_DIREITO,
    CADEIA_FONE_ESQUERDO,
    LagChain,
)
from sejoga.animacao.movimento_corpo import BodyMotion
from sejoga.animacao.movimento_danca import DanceMotion
from sejoga.animacao.movimento_maos import HandMotion
from sejoga.animacao.movimento_pernas import LegMotion
from sejoga.animacao.pacotes_animacao import (
    ANGULO_POR_ORIENTACAO,
    AgendadorPacotes,
    EstadoProfundidade,
    ItemPacote,
    NivelProfundidade,
    OrientacaoCorpo,
    PacoteOlharTela,
)
from sejoga.animacao.pose_repouso import REPOUSO
from sejoga.animacao.poses_base import (
    pose_blue_balls,
    pose_drag,
    pose_flourish,
    pose_idle,
    pose_interaction,
    pose_secondary,
    pose_sleep,
    pose_sneeze,
    pose_throw_release,
    pose_thrown,
    pose_virtual_insanity,
    pose_walk,
)
from sejoga.animacao.resolvedor_poses import PoseResolver
from sejoga.animacao.respiracao import Respiracao, amostrar_respiracao_repouso
from sejoga.animacao.sono_tuning import SONO_TRANSICAO_S
from sejoga.animacao.teimosia_pose import (
    aplicar_fase as aplicar_pose_teimosia,
)
from sejoga.animacao.teimosia_pose import (
    fase_do_tempo as fase_teimosia_do_tempo,
)
from sejoga.nucleo.esqueleto import IdlePersonality, Rig, Rotation3
from sejoga.nucleo.modelo import Model

#: Braço no arraste: o z=62 original era REPOUSO.BRACO_Z - 6 (afasta um pouco).
_ARRASTE_BRACO_Z = REPOUSO.BRACO_Z - 6
#: Braço na pega pelo corpo: o z=65 original era REPOUSO.BRACO_Z - 3 (mais solto).
_PEGA_CORPO_BRACO_Z = REPOUSO.BRACO_Z - 3


class AnimationState(StrEnum):
    """Estados de animação; o valor é o nome usado nas poses e nas reações."""

    IDLE = "idle"
    WALK = "walk"
    RUN = "run"
    DRAG = "drag"
    FALL = "fall"
    DANCE = "dance"
    SLEEP = "sleep"
    HOVER = "hover"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    PET = "pet"
    POKE = "poke"
    WAKE = "wake"
    LAND = "land"
    WAVE = "wave"
    STRETCH = "stretch"
    PEEK = "peek"
    HIT = "hit"
    SNEEZE = "sneeze"
    HANG_LOOSE = "hang_loose"
    THUMBS_UP = "thumbs_up"
    ROCK = "rock"
    FINGER_GUN = "finger_gun"
    PEACE = "peace"
    OPEN_HANDS = "open_hands"
    CLOSE_FISTS = "close_fists"
    BLUE_BALLS = "blue_balls"
    VIRTUAL_INSANITY = "virtual_insanity"
    SURPRISE = "surprise"
    # Teimosia: manifesto §1.4 — resistência → repreensão → bote → roubo do mouse
    TEIMOSIA = "teimosia"


class AnimationController:
    """Gera poses a cada frame e interpola mudanças de estado."""

    def __init__(  # noqa: PLR0915  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
        self,
        rig: Rig,
        transition_seconds: float = 0.55,
        model: Model | None = None,
    ) -> None:
        """Monta o controlador com a pose idle composta como ponto de partida."""
        self.rig = rig
        self.transition_seconds = max(0.0, transition_seconds)
        self._active_transition_seconds = self.transition_seconds
        self.state: AnimationState | None = None
        self.state_time = 0.0
        self.idle_time = 0.0
        self._idle_clock = 0.0
        self.clock = 0.0
        self.idle_personality = IdlePersonality.CALM
        self.respiracao = Respiracao(frequencia=0.0)
        self._peso_repouso = 0.0
        self.respiracao_valor = 0.0
        self._personality_rng = random.Random()
        # Start in a composed idle pose. Starting every joint at zero exposes
        # the asset's T-pose during the first state crossfade.
        rig.reset()
        pose_idle(rig, 0.0, self.idle_personality)
        pose_secondary(rig, 0.0, AnimationState.IDLE.value, self.idle_personality)
        self._pose = rig.pose()
        rig.reset()
        self._reaction: AnimationState | None = None
        self._reaction_time = 0.0
        self._reaction_direction = 1.0
        self._pending_intent: tuple[str, float | None, float] | None = None
        self._cooldowns: dict[str, float] = {}
        self._look_direction = 0.0
        self._look_vertical = 0.0
        self._idle_torso_look_dir = 0.0
        self._idle_torso_look_vert = 0.0
        self._hover_enter_timer = 0.0
        self._hover_exit_timer = 0.0
        self.appendage_remaining = 0.0
        self._cursor_anterior: tuple[float, float] | None = None
        self._quietude = 0.0
        self.modo_sono: str = "em_pe"
        self._sleep_locked: bool = False
        self._dance_remaining = 0.0
        self._music_grace = 0.0
        self._dance_decision_in = 0.0
        self._previous_beat = False
        self._dance_rng = random.Random()
        self.drag_intensity = 0.0
        self._release_time = 1.0
        self._release_grip = 0.0
        self._was_grounded: bool | None = None
        self._peak_fall_vy: float = 0.0
        self.body_motion = BodyMotion()
        self.leg_motion = LegMotion()
        self.hand_motion = HandMotion()
        self.dance_motion = DanceMotion()
        self._dance_preview_remaining = 0.0
        self._dance_preview_style = "head_bob"
        # Camada 'interacao': atraso efetivo da cadeia dos braços (braço ->
        # antebraço -> mão -> dedos). Cada cadeia persegue o alvo autoral com
        # molas, e a diferença (saída - alvo) vira um follow-through aditivo
        # somado sobre o follow-through das mãos (hand_motion).
        self.cadeia_direita = LagChain(CADEIA_DIREITA)
        self.cadeia_esquerda = LagChain(CADEIA_ESQUERDA)
        self.cadeia_fone_direito = LagChain(CADEIA_FONE_DIREITO)
        self.cadeia_fone_esquerdo = LagChain(CADEIA_FONE_ESQUERDO)
        self.cadeia_coluna = LagChain(CADEIA_COLUNA)
        for _c in (
            self.cadeia_direita,
            self.cadeia_esquerda,
            self.cadeia_fone_direito,
            self.cadeia_fone_esquerdo,
            self.cadeia_coluna,
        ):
            _c.definir(dict(self._pose))
        self._collision_model = model
        self.pose_resolver = PoseResolver()
        self.pose_resolver.iniciar_transicao(
            dict(self._pose), transition_seconds=self.transition_seconds
        )
        # LayerStack para composição aditiva de deltas (Fase 3).
        self.layer_stack = LayerStack()
        # Pacotes de animação, profundidade visual e orientação manual (Fases 3-4).
        self.profundidade = EstadoProfundidade()
        self.pacote_olhar_tela = PacoteOlharTela()
        self.agendador_pacotes = AgendadorPacotes(
            (
                ItemPacote("olhar_tela", peso=0.75, resfriamento_s=180.0),
                ItemPacote("caminhar_fundo", peso=0.45, resfriamento_s=210.0),
            ),
            intervalo_base_s=95.0,
        )
        self._curiosidade_fundo_restante: float = 0.0
        self.orientacao_manual: OrientacaoCorpo | None = None
        self.angulo_giro_pedido: float | None = None
        self.permitir_giro_costas: bool = False
        self._fonte_atencao: str | None = None

        # ── Sistema de agência (manifesto §4.1 — Camada 1) ──────────────
        self.agencia = Agencia()
        self._teimosia_fase: str = "resistencia"  # resistencia → repreensao → bote → roubo → cospe
        self._teimosia_tempo = 0.0
        self._cursor_oculto = False  # Track if we hid the cursor via Win32

    def iniciar_pacote_olhar_tela(self, lado: float | None = None) -> None:
        """Dispara o pacote 'Olhar a tela' (olhar por cima do ombro -> costas -> frente)."""
        self.idle_time = 0.0
        escolhido = (
            (1.0 if self._personality_rng.random() < 0.5 else -1.0)
            if lado is None
            else lado
        )
        self.pacote_olhar_tela.iniciar(lado=escolhido)

    def definir_profundidade(self, nivel: NivelProfundidade | str) -> None:
        """Define o nível de profundidade visual (`perto`, `medio` ou `longe`)."""
        self._curiosidade_fundo_restante = 0.0
        self.profundidade.definir_nivel(nivel)

    def caminhar_para_fundo(self) -> NivelProfundidade:
        """Avança um nível de profundidade para dentro da tela (`perto -> medio -> longe`)."""
        return self.profundidade.avancar_fundo()

    def caminhar_para_frente(self) -> NivelProfundidade:
        """Avança um nível de profundidade para a frente da tela (`longe -> medio -> perto`)."""
        return self.profundidade.avancar_frente()

    def definir_orientacao(self, orientacao: OrientacaoCorpo | str | None) -> None:
        """Define a orientação manual do corpo (`frente`, `perfil`, `costas`) ou limpa."""
        if orientacao is None:
            self.orientacao_manual = None
            return
        self.orientacao_manual = OrientacaoCorpo(orientacao)
        if self.orientacao_manual != OrientacaoCorpo.COSTAS:
            self.pacote_olhar_tela.interromper()

    def voltar_ao_plano(self) -> None:
        """Retorna imediatamente ao plano frontal (`perto` e `frente`)."""
        self._curiosidade_fundo_restante = 0.0
        self.pacote_olhar_tela.interromper()
        self.orientacao_manual = None
        self.angulo_giro_pedido = 0.0
        self.permitir_giro_costas = False
        self.profundidade.definir_nivel(NivelProfundidade.PERTO)

    def preview_dance(self, style):
        """Força a prévia de um estilo de dança por alguns segundos."""
        if style not in (
            "head_bob", "hip_hop", "rock", "breakdance",
            "street_groove", "graffiti_dance", "cyber_bounce",
        ):
            return
        self._dance_preview_remaining = 15.0
        self._dance_preview_style = style
        self.dance_motion.style = style
        self.dance_motion.style_beats = 0
        self.dance_motion.pose.clear()

    def colocar_para_dormir(self, modo: str = "em_pe") -> None:
        """Coloca o mascote para dormir em um dos 3 estados: em_pe, sentado ou deitado."""
        if modo not in ("em_pe", "sentado", "deitado"):
            modo = "em_pe"
        self.modo_sono = modo
        self._sleep_locked = True
        self.state = AnimationState.SLEEP
        self.state_time = 0.0
        self.appendage_remaining = 0.0
        self.pose_resolver.iniciar_transicao(
            dict(self._pose), transition_seconds=SONO_TRANSICAO_S
        )

    def acordar(self) -> None:
        """Acorda o mascote e retorna ao idle."""
        self._sleep_locked = False
        if self.state == AnimationState.SLEEP:
            self.state = AnimationState.IDLE
            self.state_time = 0.0
            self.idle_time = 0.0
            self.pose_resolver.iniciar_transicao(
                dict(self._pose), transition_seconds=self.transition_seconds
            )

    def empurrar_respiracao(self, quantidade: float) -> None:
        """Soma uma inspiração breve ao movimento em curso."""
        self.respiracao.empurrar(quantidade)

    def set_idle_personality(self, personality: IdlePersonality | str | None) -> None:
        """Seleciona uma variação ou retorna ao repouso padrão."""
        selected = (
            IdlePersonality.CALM
            if personality is None or personality == "auto"
            else IdlePersonality(personality)
        )
        if selected == self.idle_personality:
            return
        self.idle_personality = selected
        self._idle_clock = 0.0
        self.pose_resolver.iniciar_transicao(
            dict(self._pose), transition_seconds=max(self.transition_seconds, 1.0)
        )
        self._active_transition_seconds = max(self.transition_seconds, 1.0)
        self.state_time = 0.0

    REACTION_SECONDS: ClassVar[dict[AnimationState, float]] = {
        **{
            AnimationState(k): 3.2
            for k in ("hang_loose", "thumbs_up", "rock", "finger_gun", "peace")
        },
        AnimationState.OPEN_HANDS: 2.5,
        AnimationState.CLOSE_FISTS: 2.5,
        AnimationState.BLUE_BALLS: 2.4,
        AnimationState.VIRTUAL_INSANITY: 2.4,
        AnimationState.SNEEZE: 9.0,
        AnimationState.CLICK: 0.5,
        AnimationState.DOUBLE_CLICK: 1.4,
        AnimationState.PET: 1.5,
        AnimationState.POKE: CUTUCAR_DURACAO_S,
        AnimationState.WAKE: 1.2,
        AnimationState.LAND: 0.50,
        AnimationState.WAVE: ACENO_DURACAO_S,
        AnimationState.STRETCH: ALONGAR_DURACAO_S,
        AnimationState.PEEK: 9.0,
        AnimationState.HIT: 0.65,
        # SURPRESA: recuo rápido + retorno no mesmo padrão das outras reações.
        # Duração CALIBRÁVEL (validar na GPU): curta o bastante para parecer um
        # susto, longa o bastante para o retorno ser visível.
        AnimationState.SURPRISE: 0.7,
        # TEIMOSIA: manifesto §1.4 — sequência completa (bote → roubo → cospe)
        AnimationState.TEIMOSIA: 6.0,
    }

    def _registrar_humor_interacao(self, kind: str, strength: float) -> None:
        if kind in ("pet", "double_click"):
            self.agencia.registrar_interacao_positiva()
        elif kind in ("hit", "poke"):
            self.agencia.registrar_interacao_negativa(strength)

    def interact(
        self, kind: str, *, direction: float | None = None, strength: float = 1.0
    ) -> None:
        """Interação acorda o mascote e dispara uma reação com cooldown."""
        self.idle_time = 0.0
        if kind == "peek":
            self.appendage_remaining = 9.0
            return
        if kind == "drag_start":
            self._reaction = None
            if self.agencia.tem_meta_ativa or self.agencia.teimosia_ativa:
                self.agencia.registrar_interrupcao()
            return
        if self.state == AnimationState.SLEEP:
            kind = "wake"
        sem_cooldown = ("blue_balls", "virtual_insanity", "peace", "open_hands", "hit")
        if kind not in self.REACTION_SECONDS or (
            kind not in sem_cooldown and self.clock < self._cooldowns.get(kind, 0.0)
        ):
            return
        # Continuidade pós-queda (Rain World): guarda intenções não-emergenciais
        # recebidas durante FALL/DRAG/LAND para retomá-las após amortecer o pouso.
        em_queda = (
            self.state in (AnimationState.FALL, AnimationState.DRAG)
            or self._reaction == AnimationState.LAND
        )
        if kind not in ("hit", "land", "wake") and em_queda:
            self._pending_intent = (kind, direction, strength)
            return
        self.body_motion.impulse(
            kind, self._look_direction if direction is None else direction, strength
        )
        if kind == "wake":
            self._sleep_locked = False
        self._registrar_humor_interacao(kind, strength)
        self._reaction = AnimationState(kind)
        self._reaction_time = 0.0
        dir_ref = self._look_direction if direction is None else direction
        self._reaction_direction = 1.0 if dir_ref >= 0.0 else -1.0
        recuo_min = 6.0 if kind == "surprise" else 0.5
        self._cooldowns[kind] = self.clock + max(
            self.REACTION_SECONDS[self._reaction], recuo_min
        )

    @staticmethod
    def _choose_state(
        *,
        speed: float,
        grounded: bool,
        gravity_active: bool,
        dragging: bool,
        music_playing: bool,
        music_intensity: float,
        current_state: AnimationState | None = None,
    ) -> AnimationState:
        if dragging:
            return AnimationState.DRAG
        if gravity_active or (not grounded and speed > 120.0):
            return AnimationState.FALL
        if music_playing and music_intensity > 0.01:
            return AnimationState.DANCE
        limiar_run = 560.0 if current_state == AnimationState.RUN else 700.0
        if grounded and speed > limiar_run:
            return AnimationState.RUN
        limiar_walk = 75.0 if current_state == AnimationState.WALK else 120.0
        if grounded and speed > limiar_walk:
            return AnimationState.WALK
        return AnimationState.IDLE

    def update(  # noqa: C901, PLR0915  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
        self,
        dt: float,
        *,
        velocity: tuple[float, float] = (0.0, 0.0),
        grounded: bool = True,
        gravity_active: bool = False,
        dragging: bool = False,
        drag_direction: float = 0.0,
        drag_intensity: float = 0.0,
        music_playing: bool = False,
        music_intensity: float = 0.0,
        music_bass: float = 0.0,
        music_bpm: float | None = None,
        dance_chance: float = 1.0,
        react_to_beat: bool = True,
        beat_detected: bool = False,
        idle_enabled: bool = True,
        sleep_after_idle_seconds: int = 0,
        hovered: bool = False,
        look_direction: float = 0.0,
        look_vertical: float = 0.0,
        fonte_atencao: str | None = None,
        pointer_position: tuple[float, float] | None = None,
        grab_part: str = "body",
    ) -> dict[str, Rotation3]:
        """Atualiza o estado e devolve um snapshot de rotações em radianos."""
        dt = min(0.1, max(0.0, dt))
        if self._dance_preview_remaining > 0:
            self._dance_preview_remaining = max(0, self._dance_preview_remaining - dt)
            music_playing = react_to_beat = True
            dance_chance = 1.0
            music_intensity, music_bass, music_bpm = {
                "head_bob": (0.2, 0.03, 80),
                "hip_hop": (0.5, 0.3, 95),
                "rock": (0.6, 0.15, 135),
                "breakdance": (0.9, 0.6, 145),
                "street_groove": (0.65, 0.4, 108),
                "graffiti_dance": (0.55, 0.25, 100),
                "cyber_bounce": (0.75, 0.5, 124),
            }.get(self._dance_preview_style, (0.5, 0.25, 100))
            self.dance_motion.override = self._dance_preview_style
            self._dance_remaining = 1.0
        self.clock += dt
        self.delta_time = dt
        self._music_grace = 0.65 if music_playing else max(0.0, self._music_grace - dt)
        music_playing = self._music_grace > 0
        self.music_active = music_playing
        if self.orientacao_manual == OrientacaoCorpo.COSTAS or (
            self.permitir_giro_costas and abs(self.angulo_giro_pedido or 0) > 90
        ):
            look_direction = -look_direction
        self.appendage_remaining = max(0, self.appendage_remaining - dt)

        # ── Sistema de agência: atualizar cérebro do Mário ──────────────
        cursor_parado = False
        if pointer_position is not None:
            if self._cursor_anterior is None:
                self._cursor_anterior = pointer_position
                self.agencia.registrar_cursor_movimento()
            else:
                dx = pointer_position[0] - self._cursor_anterior[0]
                dy = pointer_position[1] - self._cursor_anterior[1]
                if dx * dx + dy * dy <= 16.0:
                    cursor_parado = True
                else:
                    self._cursor_anterior = pointer_position
                    self.agencia.registrar_cursor_movimento()
        else:
            self._cursor_anterior = None
        self.agencia.atualizar(dt)

        # Direção da meta ativa para resistência durante arraste
        meta_dir = self.agencia.direcao_meta
        resistencia = self.agencia.resistencia_ao_arraste

        self.body_motion.update(
            dt,
            pointer=pointer_position,
            dragging=dragging,
            hovered=hovered,
            look=(look_direction, look_vertical),
            grounded=grounded,
            velocity=velocity,
            grab_part=grab_part,
            meta_direcao=meta_dir,
            resistencia_nivel=resistencia,
        )
        if self.state == AnimationState.DRAG and not dragging:
            self._release_time = 0.0
            self._release_grip = self.drag_intensity
        else:
            self._release_time += dt
        self.drag_intensity += (
            max(0, min(1, drag_intensity)) - self.drag_intensity
        ) * min(1, dt * 8)
        self._dance_remaining = max(0.0, self._dance_remaining - dt)
        self._dance_decision_in = max(0.0, self._dance_decision_in - dt)
        if not music_playing or not react_to_beat or dance_chance <= 0:
            self._dance_remaining = 0.0
            self._dance_decision_in = 0.0
        elif self._dance_decision_in == 0:
            # One decision per phrase, never one random draw per rendered frame.
            self._dance_decision_in = 8.0
            if self._dance_rng.random() < min(1.0, dance_chance):
                self._dance_remaining = 8.0
        beat_edge = beat_detected and not self._previous_beat
        self._previous_beat = beat_detected
        # Onsets corrigem a cadência; não classificam áudio baixo como alto.
        self.dance_motion.update(dt, music_intensity, music_bass, music_bpm, beat_edge)
        self._look_direction += (
            max(-1.0, min(1.0, look_direction)) - self._look_direction
        ) * min(1.0, dt * 10.0)
        self._look_vertical += (
            max(-1.0, min(1.0, look_vertical)) - self._look_vertical
        ) * min(1.0, dt * 10.0)
        # Tronco acompanha o olhar com atraso suave (ação sobreposta).
        self._idle_torso_look_dir += (
            self._look_direction - self._idle_torso_look_dir
        ) * min(1.0, dt * 3.5)
        self._idle_torso_look_vert += (
            self._look_vertical - self._idle_torso_look_vert
        ) * min(1.0, dt * 3.5)
        if self._reaction is not None:
            self._reaction_time += dt
            if self._reaction_time >= self.REACTION_SECONDS[self._reaction]:
                if self._reaction == AnimationState.TEIMOSIA:
                    self.agencia.interrupcoes.resetar()
                    self.agencia._teimosia_ativa = False
                    self.agencia._teimosia_nivel = 0.0
                    self._teimosia_fase = "resistencia"
                self._reaction = None
                if (
                    grounded
                    and not dragging
                    and self._pending_intent is not None
                ):
                    pending = self._pending_intent
                    self._pending_intent = None
                    self.interact(
                        pending[0], direction=pending[1], strength=pending[2]
                    )

        if not grounded and not dragging:
            self._peak_fall_vy = max(self._peak_fall_vy, abs(velocity[1]))
        if (
            self._was_grounded is False
            and grounded
            and not dragging
            and (self.state == AnimationState.FALL or self._peak_fall_vy > 100.0)
        ):
            forca = max(0.75, min(1.8, self._peak_fall_vy / 480.0))
            self.interact(
                "land",
                direction=max(-1.0, min(1.0, velocity[0] / 400.0)),
                strength=forca,
            )
        self._was_grounded = grounded
        if grounded:
            self._peak_fall_vy = 0.0

        speed = (velocity[0] ** 2 + velocity[1] ** 2) ** 0.5
        next_state = self._choose_state(
            speed=speed,
            grounded=grounded,
            gravity_active=gravity_active,
            dragging=dragging,
            music_playing=music_playing and self._dance_remaining > 0,
            music_intensity=music_intensity,
            current_state=self.state,
        )
        condicao_quietude = (
            cursor_parado
            and grounded
            and idle_enabled
            and not hovered
            and not music_playing
            and not dragging
            and self._reaction is None
        )
        if (
            condicao_quietude
            and next_state == AnimationState.IDLE
            and self.state == AnimationState.IDLE
        ):
            if self.appendage_remaining <= 0.0:
                anterior = self._quietude
                self._quietude += dt
                # Tentáculos saem quando Mário acha que ninguém está olhando (Manifesto §1.3 C)
                if anterior < 14.0 <= self._quietude:
                    self.appendage_remaining = 5.5
                    self._quietude = 0.0
        elif not (
            condicao_quietude
            and (
                next_state == AnimationState.WALK
                or (
                    self.state == AnimationState.WALK
                    and next_state == AnimationState.IDLE
                )
            )
        ):
            self._quietude = 0.0
            if next_state in (AnimationState.SLEEP, AnimationState.DRAG, AnimationState.FALL):
                self.appendage_remaining = 0.0
        if hovered:
            self._hover_enter_timer += dt
            self._hover_exit_timer = 0.0
        else:
            self._hover_exit_timer += dt
            self._hover_enter_timer = 0.0

        if next_state != AnimationState.DRAG and (
            next_state != AnimationState.FALL or self._reaction == AnimationState.HIT
        ):
            if self._reaction is not None and (
                next_state != AnimationState.DANCE
                or self._reaction in (
                    AnimationState.HIT,
                    AnimationState.LAND,
                    AnimationState.SNEEZE,
                    AnimationState.OPEN_HANDS,
                    AnimationState.CLOSE_FISTS,
                    AnimationState.BLUE_BALLS,
                    AnimationState.VIRTUAL_INSANITY,
                )
            ):
                next_state = self._reaction
            elif next_state == AnimationState.IDLE and (
                (
                    hovered
                    and (
                        self.state == AnimationState.HOVER
                        or self._hover_enter_timer >= 0.05
                    )
                )
                or (
                    not hovered
                    and self.state == AnimationState.HOVER
                    and self._hover_exit_timer < 0.16
                )
            ):
                next_state = AnimationState.HOVER
        if self._sleep_locked:
            if next_state in (AnimationState.DRAG, AnimationState.FALL):
                self._sleep_locked = False
            else:
                next_state = AnimationState.SLEEP
        elif next_state in (
            AnimationState.IDLE,
            AnimationState.WAVE,
            AnimationState.STRETCH,
            AnimationState.PEEK,
        ):
            self.idle_time += dt
            if (
                sleep_after_idle_seconds > 0
                and self.idle_time >= sleep_after_idle_seconds
            ):
                next_state = AnimationState.SLEEP
        else:
            self.idle_time = 0.0

        # ── Teimosia: se agência detectou 3+ interrupções, acionar TEIMOSIA ─
        if (
            self.agencia.teimosia_ativa
            and self.state
            not in (
                AnimationState.TEIMOSIA,
                AnimationState.DRAG,
                AnimationState.FALL,
                AnimationState.LAND,
            )
            and self._reaction not in (AnimationState.TEIMOSIA, AnimationState.LAND)
        ):
            self._reaction = AnimationState.TEIMOSIA
            self._reaction_time = 0.0
            self._cooldowns["teimosia"] = self.clock + 6.0
            next_state = AnimationState.TEIMOSIA

        if (
            self._reaction == AnimationState.TEIMOSIA
            and 2.0 <= self._reaction_time <= 5.2
        ):
            self.appendage_remaining = max(
                self.appendage_remaining, 5.2 - self._reaction_time
            )

        if next_state != self.state:
            if next_state == AnimationState.FALL:
                self._active_transition_seconds = min(self.transition_seconds, 0.11)
            elif next_state in (
                AnimationState.DRAG,
                AnimationState.HIT,
                AnimationState.BLUE_BALLS,
                AnimationState.VIRTUAL_INSANITY,
            ):
                self._active_transition_seconds = min(self.transition_seconds, 0.14)
            else:
                self._active_transition_seconds = self.transition_seconds

            if next_state == AnimationState.SLEEP:
                # Adormecer é lento: crossfade longo para o corpo não cair de uma vez.
                self._active_transition_seconds = max(
                    self.transition_seconds, SONO_TRANSICAO_S
                )

            self.pose_resolver.iniciar_transicao(
                dict(self._pose), transition_seconds=self._active_transition_seconds
            )
            self.state = next_state
            self.state_time = 0.0
        else:
            self.state_time += dt

        self.rig.reset()
        em_repouso = idle_enabled and self.state in (AnimationState.IDLE, AnimationState.HOVER)
        passo = dt / 0.55
        self._peso_repouso = (
            min(1.0, self._peso_repouso + passo)
            if em_repouso
            else max(0.0, self._peso_repouso - passo)
        )
        peso_repouso = suavizar_quintico(self._peso_repouso)
        ciclo = amostrar_respiracao_repouso(self.clock)
        impulso = self.respiracao.atualizar(dt)
        self.respiracao_valor = max(
            -1.0, min(1.0, ciclo * peso_repouso + impulso)
        )
        if self.state in (AnimationState.IDLE, AnimationState.HOVER):
            if idle_enabled:
                self._idle_clock += dt
                pose_idle(
                    self.rig,
                    self._idle_clock,
                    self.idle_personality,
                    self.respiracao_valor,
                )
            if self.state == AnimationState.HOVER:
                pose_interaction(
                    self.rig,
                    "hover",
                    self.state_time,
                    self._look_direction,
                    self._look_vertical,
                )
        elif self.state == AnimationState.WALK:
            pose_walk(self.rig, self.clock)
        elif self.state == AnimationState.RUN:
            pose_walk(self.rig, self.clock, run=True)
        elif self.state == AnimationState.DRAG:
            pose_drag(self.rig, self.clock, drag_direction, self.drag_intensity)
        elif self.state == AnimationState.FALL:
            pose_thrown(self.rig, self.state_time, velocity)
        elif self.state == AnimationState.DANCE:
            contribuicao_danca = self.dance_motion.contribuicao(self.rig)
            self.rig.current = dict(contribuicao_danca)
        elif self.state == AnimationState.SLEEP:
            pose_sleep(self.rig, self.clock, self.modo_sono, self.state_time)
        elif self.state in (AnimationState.OPEN_HANDS, AnimationState.CLOSE_FISTS):
            palma_aberta = self.state == AnimationState.OPEN_HANDS
            for lado, mao, dedos, sinal in (
                ("right", "hand", "fingers", 1),
                ("left", "hand2", "fingers2", -1),
            ):
                for grupo, (x, y, z) in braco_hpr_graus(lado, "interaction").items():
                    self.rig.set_rotation(grupo, x=x, y=y, z=z)
                self.rig.set_rotation(mao, x=36 if palma_aberta else -16, z=sinal * 6)
                self.rig.set_rotation(dedos)
        elif self.state.value in ("hang_loose", "thumbs_up", "rock", "finger_gun", "peace"):
            pose_idle(self.rig, self.clock, self.idle_personality)
            # Cada gesto posiciona o braço e o antebraço para exibir a silhueta correta.
            if self.state.value == "rock":
                self.rig.set_rotation("right-arm", x=90.0, y=-15.0, z=25.0)
                self.rig.set_rotation("ant-arm", x=0.0, z=70.0)
                self.rig.set_rotation("hand", x=0.0, y=0.0, z=0.0)
            elif self.state.value == "hang_loose":
                self.rig.set_rotation("right-arm", x=90.0, y=-15.0, z=25.0)
                self.rig.set_rotation("ant-arm", x=0.0, z=46.0)
                self.rig.set_rotation("hand", x=0.0, y=0.0, z=0.0)
            elif self.state.value == "peace":
                self.rig.set_rotation("right-arm", x=86.0, y=-14.0, z=24.0)
                self.rig.set_rotation("ant-arm", x=0.0, z=62.0)
                self.rig.set_rotation("hand", x=0.0, y=0.0, z=0.0)
            elif self.state.value == "thumbs_up":
                self.rig.set_rotation("right-arm", x=62.0, y=-22.0, z=25.0)
                self.rig.set_rotation("ant-arm", x=0.0, z=62.0)
                self.rig.set_rotation("hand", x=0.0, y=0.0, z=0.0)
            else:
                # finger_gun
                self.rig.set_rotation("right-arm", x=38.0, y=-28.0, z=30.0)
                self.rig.set_rotation("ant-arm", x=0.0, z=52.0)
                self.rig.set_rotation("hand", x=0.0, y=0.0, z=0.0)
            self.rig.set_rotation("fingers", z=0)
        elif self.state == AnimationState.BLUE_BALLS:
            pose_blue_balls(self.rig, self._reaction_time)
        elif self.state == AnimationState.VIRTUAL_INSANITY:
            pose_virtual_insanity(
                self.rig, self._reaction_time, self._reaction_direction
            )
        elif self.state == AnimationState.SNEEZE:
            pose_sneeze(self.rig, self._reaction_time)
        elif self.state == AnimationState.TEIMOSIA:
            # Manifesto §1.4: teimosia com fases (bote → roubo → cospe)
            self._aplicar_pose_teimosia()
        elif self.state in (
            AnimationState.WAVE,
            AnimationState.STRETCH,
            AnimationState.PEEK,
            AnimationState.HIT,
        ):
            pose_flourish(self.rig, self.state.value, self._reaction_time)
        elif self.state == AnimationState.HOVER or self.state in self.REACTION_SECONDS:
            pose_interaction(
                self.rig,
                self.state.value,
                self._reaction_time,
                self._look_direction,
                self._look_vertical,
            )

        pose_secondary(
            self.rig,
            self._idle_clock
            if self.state in (AnimationState.IDLE, AnimationState.HOVER)
            else self.clock,
            self.state.value,
            self.idle_personality,
        )
        if not dragging and self._release_time < 0.9:
            pose_throw_release(self.rig, self._release_time, self._release_grip)

        if dragging:
            motion = self.body_motion.snapshot
            # Hanging limbs counter-rotate the torso and trail pointer motion.
            # O z=62 original era REPOUSO.BRACO_Z - 6 (arraste afasta um pouco os braços).
            # Base completa do repouso (torção/azimute do IK); a física soma por
            # cima. Cotovelo no repouso (os -8/+8 antigos eram hiperextensão).
            _bx, _by, _az = REPOUSO.BRACO_X, REPOUSO.BRACO_Y, REPOUSO.ANTEBRACO_Z
            self.rig.set_rotation(
                "right-arm",
                x=_bx - motion.pitch * 0.55,
                y=_by,
                z=_ARRASTE_BRACO_Z - motion.roll * 0.55 + motion.limb_swing * 0.45,
            )
            self.rig.set_rotation(
                "left-arm",
                x=_bx - motion.pitch * 0.55,
                y=-_by,
                z=-_ARRASTE_BRACO_Z - motion.roll * 0.55 + motion.limb_swing * 0.4,
            )
            self.rig.set_rotation("ant-arm", x=motion.limb_swing * 0.3, z=_az)
            self.rig.set_rotation("ant-arm2", x=motion.limb_swing * 0.25, z=-_az)
            if grab_part == "right-arm":
                self.rig.set_rotation("right-arm", x=_bx - 8, y=_by, z=-55)
                self.rig.set_rotation("ant-arm", x=0, z=_az)
            elif grab_part == "left-arm":
                self.rig.set_rotation("left-arm", x=_bx - 8, y=-_by, z=55)
                self.rig.set_rotation("ant-arm2", x=0, z=-_az)
            elif grab_part == "body":
                # Loose arms and a drooping neck when lifted by the back.
                # O z=65 original era REPOUSO.BRACO_Z - 3 (braços um pouco mais soltos).
                self.rig.set_rotation("head", x=-12, z=motion.limb_swing * 0.08)
                self.rig.set_rotation(
                    "right-arm",
                    x=_bx - motion.pitch * 0.9,
                    y=_by,
                    z=_PEGA_CORPO_BRACO_Z + motion.limb_swing * 0.25,
                )
                self.rig.set_rotation(
                    "left-arm",
                    x=_bx - motion.pitch * 0.9,
                    y=-_by,
                    z=-_PEGA_CORPO_BRACO_Z + motion.limb_swing * 0.25,
                )
                self.rig.set_rotation("ant-arm", x=3 + motion.limb_swing * 0.2, z=_az)
                self.rig.set_rotation(
                    "ant-arm2", x=3 + motion.limb_swing * 0.18, z=-_az
                )
            elif grab_part in ("legs", "left-feet", "right-feet"):
                # Pego pela perna/pé: o tronco está rolado ~155° (quase de
                # cabeça para baixo). Os braços e a cabeça devem PENDER a favor
                # da gravidade — ou seja, no espaço do mundo caem AFASTANDO-SE
                # do ponto de pega (o pé, que está por cima). Com o tronco
                # invertido, isso significa recolher os braços para perto do
                # corpo (sair dos ±62° "abertos" do caso genérico) e deixá-los
                # cair ao longo do tronco, com a cabeça pendendo para baixo.
                #
                # Ângulos CALIBRÁVEIS (a validar na GPU — ver relatorio Q4):
                self.rig.set_rotation(
                    "head",
                    x=tune.ARRASTE_PENDENTE_CABECA_X,
                    z=motion.limb_swing * tune.ARRASTE_PENDENTE_OSCILACAO * 0.4,
                )
                self.rig.set_rotation(
                    "right-arm",
                    x=_bx + tune.ARRASTE_PENDENTE_BRACO_X,
                    y=_by,
                    z=tune.ARRASTE_PENDENTE_BRACO_Z
                    + motion.limb_swing * tune.ARRASTE_PENDENTE_OSCILACAO,
                )
                self.rig.set_rotation(
                    "left-arm",
                    x=_bx + tune.ARRASTE_PENDENTE_BRACO_X,
                    y=-_by,
                    z=-tune.ARRASTE_PENDENTE_BRACO_Z
                    + motion.limb_swing * tune.ARRASTE_PENDENTE_OSCILACAO,
                )
                self.rig.set_rotation(
                    "ant-arm", x=tune.ARRASTE_PENDENTE_BRACO_X * 0.4, z=_az
                )
                self.rig.set_rotation(
                    "ant-arm2", x=tune.ARRASTE_PENDENTE_BRACO_X * 0.4, z=-_az
                )
        target = self.rig.pose()

        # ═══════════════════════════════════════════════════════════════════════
        # Pacotes de animação, profundidade visual e giro de corpo (Fases 3-4)
        # ═══════════════════════════════════════════════════════════════════════
        self.profundidade.atualizar(dt, arrastando=dragging)
        interromper_pacote = (
            dragging
            or not grounded
            or self.state
            not in (
                AnimationState.IDLE,
                AnimationState.HOVER,
                AnimationState.WALK,
                AnimationState.RUN,
            )
        )
        amostra_olhar = self.pacote_olhar_tela.atualizar(
            dt, interromper=interromper_pacote
        )
        self._fonte_atencao = fonte_atencao
        if self._curiosidade_fundo_restante > 0.0:
            self._curiosidade_fundo_restante = max(0.0, self._curiosidade_fundo_restante - dt)
            if self._curiosidade_fundo_restante <= 0.0 or dragging:
                self._curiosidade_fundo_restante = 0.0
                self.profundidade.definir_nivel(NivelProfundidade.PERTO)

        elegivel_curiosidade = (
            self.state == AnimationState.IDLE
            and grounded
            and idle_enabled
            and not dragging
            and not amostra_olhar.ativo
            and self.orientacao_manual is None
            and self._curiosidade_fundo_restante <= 0.0
        )
        pacote_sorteado = self.agendador_pacotes.atualizar(
            dt, elegivel=elegivel_curiosidade
        )
        if pacote_sorteado in ("olhar_tela", "caminhar_fundo"):
            lado_olhar = 1.0 if look_direction >= 0 else -1.0
            if pacote_sorteado == "caminhar_fundo":
                self.caminhar_para_fundo()
                self._curiosidade_fundo_restante = 16.0
            self.iniciar_pacote_olhar_tela(lado=lado_olhar)
            amostra_olhar = self.pacote_olhar_tela.atualizar(0.0)

        if dragging:
            self.angulo_giro_pedido = None
            self.permitir_giro_costas = False
        elif amostra_olhar.ativo:
            self.angulo_giro_pedido = amostra_olhar.angulo_giro_corpo
            self.permitir_giro_costas = True
        elif self.orientacao_manual is not None:
            self.angulo_giro_pedido = ANGULO_POR_ORIENTACAO[self.orientacao_manual]
            self.permitir_giro_costas = (
                self.orientacao_manual == OrientacaoCorpo.COSTAS
            )
        elif self.state in (AnimationState.WALK, AnimationState.RUN) and abs(velocity[0]) > 40.0:
            self.angulo_giro_pedido = 90.0 if velocity[0] > 0.0 else -90.0
            self.permitir_giro_costas = False
        else:
            self.angulo_giro_pedido = None
            self.permitir_giro_costas = False

        # ═══════════════════════════════════════════════════════════════════════
        # Composição via LayerStack (Fase 3): produz delta do estado atual
        # e usa layer_stack.compor() para obter pose composta.
        # ═══════════════════════════════════════════════════════════════════════
        motion = self.body_motion.snapshot

        # Produz delta do estado atual
        delta_estado = self._delta_do_estado(
            self.state,
            self._idle_clock
            if self.state in (AnimationState.IDLE, AnimationState.HOVER)
            else self.clock,
            velocity,
            grab_part,
        )
        # Soltura: os dedos abrem além do ponto ao largar (aditivo, fecha em 0).
        if delta_estado and not dragging and self.state != AnimationState.DRAG:
            delta_estado = somar_deltas(
                delta_estado, delta_soltura(self._release_time, self._release_grip)
            )
        if amostra_olhar.ativo and amostra_olhar.delta_pose:
            delta_estado = somar_deltas(delta_estado, amostra_olhar.delta_pose)

        # Determina se o estado atual está totalmente migrado para deltas
        # Estados não migrados usam a pose legada diretamente
        estados_migrados = {
            AnimationState.IDLE,
            AnimationState.WALK,
            AnimationState.RUN,
            AnimationState.DRAG,
            AnimationState.FALL,
            AnimationState.SLEEP,
        }
        estado_migrado = self.state in estados_migrados and delta_estado

        if estado_migrado:
            relogio_sec = (
                self._idle_clock
                if self.state in (AnimationState.IDLE, AnimationState.HOVER)
                else self.clock
            )
            # Set camadas no LayerStack
            self.layer_stack.set_camada(
                CamadaDelta(
                    nome="estado",
                    prioridade=Prioridade.ESTADO,
                    delta=delta_estado,
                )
            )

            # Camada de física (roll, pitch, yaw do body_motion)
            self.layer_stack.set_camada(
                CamadaDelta(
                    nome="fisica",
                    prioridade=Prioridade.FISICA,
                    delta=delta_fisica(
                        motion,
                        pendurado=dragging and motion.hanging > tune.PENDURADO_LIMIAR,
                    ),
                )
            )

            # Camada secundária (follow-through de coluna, fones, antenas, ombros e mãos)
            self.layer_stack.set_camada(
                CamadaDelta(
                    nome="secundario",
                    prioridade=Prioridade.FOLLOW_THROUGH,
                    delta=delta_secundario(
                        relogio_sec,
                        self.state.value,
                        self.idle_personality,
                        delta_estado,
                    ),
                )
            )

            # Compõe camadas sobre a base de repouso
            composed = self.layer_stack.compor()

            # Garante que grupos não cobertos pelo delta usem valores da pose legada
            for grupo, rotacao in target.items():
                if grupo not in composed:
                    composed[grupo] = rotacao
        else:
            # Estados não migrados: usa sistema legado com MixerCamadas
            camadas = [CamadaAnim("base", dict(target))]
            if self.state == AnimationState.DANCE:
                base = camadas[0].contribuicao
                contribuicao_musica = {
                    grupo: base[grupo] for grupo in MASCARA_MUSICA if grupo in base
                }
                for grupo in contribuicao_musica:
                    base[grupo] = Rotation3()
                camadas.append(
                    CamadaAnim("musica", contribuicao_musica, mascara=MASCARA_MUSICA)
                )
            composed = MixerCamadas.compor(camadas)

        # Crossfade, colisão e clamps delegados ao PoseResolver.
        self._pose = self.pose_resolver.resolver(
            dt, composed, model=self._collision_model, state_time=self.state_time,
        )
        displayed_pose = self.hand_motion.apply(self._pose, dt, self.state.value)
        peso_tatil = 1.0 if self.state in (AnimationState.DRAG, AnimationState.FALL) else 0.0
        displayed_pose = self._aplicar_interacao(displayed_pose, dt, peso_tatil)
        self.rig.current = dict(displayed_pose)
        roubo_ativo = self.state == AnimationState.TEIMOSIA and self._teimosia_fase == "roubo"
        estado_pernas = (
            AnimationState.RUN.value
            if roubo_ativo
            else AnimationState.WALK.value
            if amostra_olhar.ativo and amostra_olhar.em_passo
            else self.state.value
        )
        vel_pernas = (
            (240.0, 0.0)
            if roubo_ativo
            else (160.0 * self.pacote_olhar_tela.lado, 0.0)
            if amostra_olhar.ativo and amostra_olhar.em_passo
            else velocity
        )
        tempo_pernas = (
            self._idle_clock
            if self.state in (AnimationState.IDLE, AnimationState.HOVER)
            else self.state_time
            if self.state in (AnimationState.DRAG, AnimationState.SLEEP, AnimationState.FALL, AnimationState.LAND)
            else self._reaction_time
        )
        self.leg_motion.update(
            dt,
            estado_pernas,
            vel_pernas,
            tempo_pernas,
            self.body_motion.snapshot.limb_swing
            if dragging
            else self.body_motion.snapshot.roll
            + degrees(displayed_pose.get("body", Rotation3()).z) * 0.85,
            dance_phase=(
                self.dance_motion.style_beats * 6.28318530718
                if self.dance_motion.style == "breakdance"
                else self.dance_motion.phase
            ),
            dance_strength=self.dance_motion.strength,
            dance_style=self.dance_motion.style,
            modo_sono=self.modo_sono,
        )
        return displayed_pose

    def _aplicar_interacao(
        self, pose: dict[str, Rotation3], dt: float, peso: float
    ) -> dict[str, Rotation3]:
        """Camada 'interacao': soma o atraso das cadeias dos braços à pose.

        Cada cadeia persegue, por mola, os alvos autorais da pose composta
        (``self._pose``, em radianos). O follow-through aditivo por junta é a
        diferença entre a saída atrasada da cadeia e o alvo, deixando a ponta
        (antebraço/mão/dedos) arrastar atrás da base do braço. Isso soma sobre
        o follow-through já aplicado por hand_motion.
        """
        resultado = dict(pose)
        for cadeia in (
            self.cadeia_direita,
            self.cadeia_esquerda,
            self.cadeia_fone_direito,
            self.cadeia_fone_esquerdo,
            self.cadeia_coluna,
        ):
            alvos = {
                grupo: self._pose[grupo]
                for grupo in cadeia.cadeia
                if grupo in self._pose
            }
            if not alvos:
                continue
            saida = cadeia.atualizar(dt, alvos)
            for grupo, atrasada in saida.items():
                if grupo not in resultado:
                    continue
                alvo = alvos[grupo]
                base = resultado[grupo]
                resultado[grupo] = Rotation3(
                    base.x + (atrasada.x - alvo.x) * peso,
                    base.y + (atrasada.y - alvo.y) * peso,
                    base.z + (atrasada.z - alvo.z) * peso,
                )
        return resultado

    def _aplicar_pose_teimosia(self) -> None:
        """Aplica a pose de teimosia conforme manifesto §1.4 (delegado a teimosia_pose.py)."""
        t = self._reaction_time
        self._teimosia_fase = fase_teimosia_do_tempo(t)
        aplicar_pose_teimosia(self.rig, t, self._look_direction)

    @staticmethod
    def _blend(start: Rotation3, end: Rotation3, amount: float) -> Rotation3:
        inverse = 1.0 - amount
        return Rotation3(
            x=start.x * inverse + end.x * amount,
            y=start.y * inverse + end.y * amount,
            z=start.z * inverse + end.z * amount,
        )

    def _delta_do_estado(
        self,
        state: AnimationState,
        t: float,
        velocity: tuple[float, float],
        grab_part: str,
    ) -> dict[str, Rotation3]:
        """Produz o delta do estado atual via funções delta_*.

        Cada delta retorna apenas a diferença sobre a pose base, não a pose
        absoluta. Estados não migrados retornam delta vazio.
        """
        motion = self.body_motion.snapshot

        if state in (AnimationState.IDLE, AnimationState.HOVER):
            return delta_idle(
                t,
                self.idle_personality,
                self.respiracao_valor,
                look_direction=self._look_direction,
                look_vertical=self._look_vertical,
                torso_look_direction=self._idle_torso_look_dir,
                torso_look_vertical=self._idle_torso_look_vert,
            )
        if state == AnimationState.DRAG:
            return delta_drag(motion, grab_part, self.drag_intensity)
        if state in (AnimationState.WALK, AnimationState.RUN):
            return delta_walk(self.leg_motion.phase, run=state == AnimationState.RUN)
        if state == AnimationState.FALL:
            return delta_fall(self.state_time, velocity)
        if state == AnimationState.SLEEP and self.modo_sono == "em_pe":
            return delta_sleep(t, self.modo_sono)
        # Estados não migrados: delta vazio (usa pose legada)
        return {}

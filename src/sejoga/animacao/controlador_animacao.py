"""Controlador procedural de animação do mascote.

As poses são produzidas pelo rig sem depender de clipes exportados. O
controlador escolhe um estado a partir da interação/física e faz crossfade
entre poses para evitar saltos bruscos.
"""

from __future__ import annotations

import random
from enum import StrEnum
from math import degrees, radians
from typing import ClassVar

from sejoga.animacao import movimento_corpo_tuning as tune
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
from sejoga.animacao.mola_tuning import amortecimento_de, frequencia_de
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
    NivelProfundidade,
    OrientacaoCorpo,
    PacoteOlharTela,
)
from sejoga.animacao.pose_repouso import REPOUSO
from sejoga.animacao.poses_base import (
    pose_drag,
    pose_flourish,
    pose_idle,
    pose_interaction,
    pose_secondary,
    pose_sleep,
    pose_sneeze,
    pose_throw_release,
    pose_thrown,
    pose_walk,
)
from sejoga.animacao.resolvedor_poses import PoseResolver
from sejoga.animacao.respiracao import Respiracao
from sejoga.animacao.respiracao_tuning import parametros_de
from sejoga.animacao.sono_tuning import SONO_TRANSICAO_S
from sejoga.nucleo.esqueleto import ALL_GROUPS, IdlePersonality, Rig, Rotation3
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
    SURPRISE = "surprise"


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
        # Respiração sob demanda (engine-agnóstica): o oscilador lento e a
        # mola seguem avançando a cada frame, mas o valor exposto só sai de
        # zero enquanto houver impulso de empurrar_respiracao ativo. No idle
        # normal o tórax fica parado; o renderer lê 0.0 até alguém empurrar.
        self.respiracao = self._criar_respiracao(self.idle_personality)
        self.respiracao_valor = 0.0
        self._personality_rng = random.Random()
        self._personality_elapsed = 0.0
        self._personality_interval = self._personality_rng.uniform(24.0, 36.0)
        # Start in a composed idle pose. Starting every joint at zero exposes
        # the asset's T-pose during the first state crossfade.
        rig.reset()
        pose_idle(rig, 0.0, self.idle_personality)
        pose_secondary(rig, 0.0, AnimationState.IDLE.value, self.idle_personality)
        self._pose = rig.pose()
        rig.reset()
        self._reaction: AnimationState | None = None
        self._reaction_time = 0.0
        self._cooldowns: dict[str, float] = {}
        self._look_direction = 0.0
        self._look_vertical = 0.0
        self._ambient_in = 28.0
        self.appendage_remaining = 0.0
        self._peek_in = self._personality_rng.uniform(180, 360)
        self.modo_sono: str = "em_pe"
        self._sleep_locked: bool = False
        self._dance_remaining = 0.0
        self._dance_decision_in = 0.0
        self._previous_beat = False
        self._dance_rng = random.Random()
        self.drag_intensity = 0.0
        self._release_time = 1.0
        self._release_grip = 0.0
        self._personality_locked = False
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
        # Crossfade, colisão e clamps delegados ao PoseResolver.
        # As tensões de crossfade vêm de spring_tuning: âncora firme, ponta
        # solta. EXCEÇÃO: legs, left-feet e right-feet recebem a tensão FIRME
        # do corpo, porque o movimento real vem do IK de lower_body via
        # leg_motion (fora do mixer): não se duplica amortecimento aqui.
        firme = (frequencia_de("body"), amortecimento_de("body"))
        tensoes_crossfade = {
            grupo: (
                firme
                if grupo in ("legs", "left-feet", "right-feet")
                else (frequencia_de(grupo), amortecimento_de(grupo))
            )
            for grupo in ALL_GROUPS
        }
        self._collision_model = model
        self.pose_resolver = PoseResolver(tensoes_crossfade=tensoes_crossfade)
        self.pose_resolver.iniciar_transicao(
            dict(self._pose), transition_seconds=self.transition_seconds
        )
        # LayerStack para composição aditiva de deltas (Fase 3).
        self.layer_stack = LayerStack()
        # Pacotes de animação, profundidade visual e orientação manual (Fases 3-4).
        self.profundidade = EstadoProfundidade()
        self.pacote_olhar_tela = PacoteOlharTela()
        self.agendador_pacotes = AgendadorPacotes()
        self.orientacao_manual: OrientacaoCorpo | None = None
        self.angulo_giro_pedido: float | None = None
        self.permitir_giro_costas: bool = False
        self.pedido_caminhada_autonoma: str | None = None

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
        self.pacote_olhar_tela.interromper()
        self.orientacao_manual = None
        self.angulo_giro_pedido = 0.0
        self.permitir_giro_costas = False
        self.profundidade.definir_nivel(NivelProfundidade.PERTO)

    def preview_dance(self, style):
        """Força a prévia de um estilo de dança por alguns segundos."""
        if style not in ("head_bob", "hip_hop", "rock", "breakdance"):
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

    @staticmethod
    def _criar_respiracao(personality: IdlePersonality) -> Respiracao:
        """Cria a respiração calibrada pelos parâmetros da personalidade."""
        parametros = parametros_de(personality)
        return Respiracao(
            frequencia=parametros.frequencia,
            amplitude=parametros.amplitude,
            amortecimento=1.0 - parametros.bounce,
        )

    def _recalibrar_respiracao(self, personality: IdlePersonality) -> None:
        """Recria a respiração para a nova personalidade, começando no repouso."""
        self.respiracao = self._criar_respiracao(personality)
        self.respiracao_valor = 0.0

    def empurrar_respiracao(self, quantidade: float) -> None:
        """Ativa a respiração sob demanda, inflando o tórax por evento.

        A respiração não ocorre mais no idle; este é o único gancho que a
        liga. Chamar ``empurrar_respiracao(quantidade)`` a partir de um estado
        ou evento (ex.: inspiração antes do espirro) faz ``respiracao_valor``
        subir por alguns frames e decair sozinho de volta a 0.0, sem precisar
        desligar nada. Delega a ``Respiracao.empurrar``. TODO: ligar ao estado
        SNEEZE quando a FEAT do espirro existir. NÃO implementar o sneeze aqui.
        """
        self.respiracao.empurrar(quantidade)

    def set_idle_personality(self, personality: IdlePersonality | str | None) -> None:
        """Escolhe uma personalidade ou devolve o idle à rotação automática."""
        if personality is None or personality == "auto":
            self._personality_locked = False
            self._personality_elapsed = 0.0
            self._personality_interval = self._personality_rng.uniform(24.0, 36.0)
            return
        selected = IdlePersonality(personality)
        if selected == self.idle_personality and self._personality_locked:
            return
        self.idle_personality = selected
        self._recalibrar_respiracao(selected)
        self._idle_clock = 0.0
        self._personality_locked = True
        self._personality_elapsed = 0.0
        self.pose_resolver.iniciar_transicao(
            dict(self._pose), transition_seconds=max(self.transition_seconds, 1.0)
        )
        self._active_transition_seconds = max(self.transition_seconds, 1.0)
        self.state_time = 0.0

    REACTION_SECONDS: ClassVar[dict[AnimationState, float]] = {
        **{
            AnimationState(k): 3.2
            for k in ("hang_loose", "thumbs_up", "rock", "finger_gun")
        },
        AnimationState.SNEEZE: 9.0,
        AnimationState.CLICK: 0.5,
        AnimationState.DOUBLE_CLICK: 1.4,
        AnimationState.PET: 1.5,
        AnimationState.POKE: CUTUCAR_DURACAO_S,
        AnimationState.WAKE: 1.2,
        AnimationState.LAND: 0.45,
        AnimationState.WAVE: ACENO_DURACAO_S,
        AnimationState.STRETCH: ALONGAR_DURACAO_S,
        AnimationState.PEEK: 9.0,
        AnimationState.HIT: 0.65,
        # SURPRESA: recuo rápido + retorno no mesmo padrão das outras reações.
        # Duração CALIBRÁVEL (validar na GPU): curta o bastante para parecer um
        # susto, longa o bastante para o retorno ser visível.
        AnimationState.SURPRISE: 0.7,
    }

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
            return
        if self.state == AnimationState.SLEEP:
            kind = "wake"
        if kind not in self.REACTION_SECONDS or self.clock < self._cooldowns.get(
            kind, 0.0
        ):
            return
        self.body_motion.impulse(
            kind, self._look_direction if direction is None else direction, strength
        )
        self._reaction = AnimationState(kind)
        self._reaction_time = 0.0
        self._cooldowns[kind] = self.clock + max(
            self.REACTION_SECONDS[self._reaction], 0.5
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
    ) -> AnimationState:
        if dragging:
            return AnimationState.DRAG
        if gravity_active or (not grounded and speed > 120.0):
            return AnimationState.FALL
        if music_playing and music_intensity > 0.01:
            return AnimationState.DANCE
        if grounded and speed > 700.0:
            return AnimationState.RUN
        if grounded and speed > 120.0:
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
            }[self._dance_preview_style]
            self.dance_motion.override = self._dance_preview_style
            self._dance_remaining = 1.0
        self.clock += dt
        self.delta_time = dt
        # Avança a respiração com o dt já saturado (o oscilador e o impulso de
        # empurrar precisam evoluir todo frame), mas só expõe o valor centrado
        # ENQUANTO houver impulso ativo. Sem empurrar, fica 0.0: o idle não
        # respira sozinho (respiração sob demanda).
        self.respiracao.atualizar(dt)
        self.respiracao_valor = (
            self.respiracao.centrada if self.respiracao.impulso_ativo else 0.0
        )
        self.music_active = music_playing
        self.appendage_remaining = max(0, self.appendage_remaining - dt)
        self.body_motion.update(
            dt,
            pointer=pointer_position,
            dragging=dragging,
            hovered=hovered,
            look=(look_direction, look_vertical),
            grounded=grounded,
            velocity=velocity,
            grab_part=grab_part,
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
        if (
            music_playing
            and react_to_beat
            and dance_chance > 0
            and self.state == AnimationState.DANCE
        ):
            self._dance_remaining = max(self._dance_remaining, 1.0)
        beat_edge = beat_detected and not self._previous_beat
        self._previous_beat = beat_detected
        if react_to_beat and beat_edge and self._dance_remaining > 0:
            pass  # Onsets correct cadence; do not classify quiet audio as loud.
        self.dance_motion.update(dt, music_intensity, music_bass, music_bpm, beat_edge)
        self._look_direction += (
            max(-1.0, min(1.0, look_direction)) - self._look_direction
        ) * min(1.0, dt * 10.0)
        self._look_vertical += (
            max(-1.0, min(1.0, look_vertical)) - self._look_vertical
        ) * min(1.0, dt * 10.0)
        if self._reaction is not None:
            self._reaction_time += dt
            if self._reaction_time >= self.REACTION_SECONDS[self._reaction]:
                self._reaction = None

        speed = (velocity[0] ** 2 + velocity[1] ** 2) ** 0.5
        next_state = self._choose_state(
            speed=speed,
            grounded=grounded,
            gravity_active=gravity_active,
            dragging=dragging,
            music_playing=music_playing and self._dance_remaining > 0,
            music_intensity=music_intensity,
        )
        if (
            next_state == AnimationState.IDLE
            and self.state == AnimationState.IDLE
            and grounded
            and idle_enabled
            and not hovered
            and not music_playing
            and not dragging
        ):
            self._peek_in -= dt
            if self._peek_in <= 0 and self._reaction is None:
                self.appendage_remaining = 5.5
                self._peek_in = self._personality_rng.uniform(180, 360)
        elif next_state in (AnimationState.SLEEP, AnimationState.DRAG, AnimationState.FALL):
            self.appendage_remaining = 0.0
        if (
            next_state == AnimationState.IDLE
            and grounded
            and idle_enabled
            and not hovered
        ):
            self._ambient_in -= dt
            if self._ambient_in <= 0 and self._reaction is None:
                self._reaction = self._personality_rng.choice(
                    [AnimationState.WAVE, AnimationState.STRETCH]
                )
                self._reaction_time = 0.0
                self._ambient_in = self._personality_rng.uniform(32.0, 48.0)
        if next_state != AnimationState.DRAG and (
            next_state != AnimationState.FALL or self._reaction == AnimationState.HIT
        ):
            if self._reaction is not None and (
                next_state != AnimationState.DANCE
                or self._reaction in (AnimationState.HIT, AnimationState.SNEEZE)
            ):
                next_state = self._reaction
            elif hovered and next_state == AnimationState.IDLE:
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

        if (
            next_state in (AnimationState.IDLE, AnimationState.HOVER)
            and idle_enabled
            and not self._personality_locked
        ):
            self._personality_elapsed += dt
            if self._personality_elapsed >= self._personality_interval:
                choices = [
                    personality
                    for personality in IdlePersonality
                    if personality != self.idle_personality
                ]
                self.idle_personality = self._personality_rng.choice(choices)
                self._recalibrar_respiracao(self.idle_personality)
                self._idle_clock = 0.0
                self._personality_elapsed = 0.0
                self._personality_interval = self._personality_rng.uniform(24.0, 36.0)
                self._active_transition_seconds = max(self.transition_seconds, 1.4)
                self.pose_resolver.iniciar_transicao(
                    dict(self._pose), transition_seconds=self._active_transition_seconds
                )
                self.state_time = 0.0
        elif next_state != AnimationState.IDLE:
            self._personality_elapsed = 0.0

        if next_state != self.state:
            self._active_transition_seconds = (
                min(self.transition_seconds, 0.22)
                if next_state
                in (AnimationState.DRAG, AnimationState.FALL, AnimationState.HIT)
                else self.transition_seconds
            )

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
        if self.state in (AnimationState.IDLE, AnimationState.HOVER):
            if idle_enabled:
                self._idle_clock += dt
                # A respiração é sob demanda: respiracao_valor fica 0.0 no idle
                # normal, então pose_idle recebe 0.0 e NÃO infla o tórax. Só
                # quando empurrar_respiracao é chamado o valor sobe por alguns
                # frames. Walk/run/drag/fall/dance/sleep seguem sem respiração.
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
            # A dança não autora mais a base: avança as molas e obtém a
            # contribuição, que vira a camada aditiva 'musica' adiante. O rig
            # recebe a pose crua suavizada para que pose_secondary leia os
            # mesmos valores de antes (continuidade de mãos/ombros).
            contribuicao_danca = self.dance_motion.contribuicao(self.rig)
            self.rig.current = dict(contribuicao_danca)
        elif self.state == AnimationState.SLEEP:
            pose_sleep(self.rig, self.clock, self.modo_sono)
        elif self.state.value in ("hang_loose", "thumbs_up", "rock", "finger_gun"):
            pose_idle(self.rig, self.clock, self.idle_personality)
            # Gesto de mão (hang loose/joinha/rock/finger gun): ergue o braço à
            # frente a partir do alvo de interação (IK) para a mão ficar visível.
            _ik = braco_hpr_graus("right", "interaction")
            _g, _ge = _ik["right-arm"], _ik["ant-arm"]
            self.rig.set_rotation("right-arm", x=_g[0] - 20, y=_g[1], z=_g[2])
            # Cotovelo do IK (o -60 antigo era hiperextensão na FK real).
            self.rig.set_rotation("ant-arm", x=_ge[0] - 8, z=_ge[2])
            self.rig.set_rotation("hand", x=180, y=0, z=0)
            self.rig.set_rotation("fingers", z=0)
        elif self.state == AnimationState.SNEEZE:
            pose_sneeze(self.rig, self._reaction_time)
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
        if self.appendage_remaining > 0:
            self.rig.set_rotation("door", y=85)
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
        elegivel_pacote = (
            self.state == AnimationState.IDLE
            and grounded
            and idle_enabled
            and not hovered
            and not dragging
            and not amostra_olhar.ativo
            and self._reaction is None
            and self.orientacao_manual is None
        )
        pacote_sorteado = self.agendador_pacotes.atualizar(dt, elegivel=elegivel_pacote)
        if pacote_sorteado == "olhar_tela":
            self.iniciar_pacote_olhar_tela()
            amostra_olhar = self.pacote_olhar_tela.atualizar(0.0)
        elif pacote_sorteado == "caminhar_fundo":
            if self.profundidade.nivel_alvo == NivelProfundidade.LONGE:
                self.caminhar_para_frente()
            else:
                self.caminhar_para_fundo()
        elif pacote_sorteado == "caminhar_lado":
            self.pedido_caminhada_autonoma = "aleatorio"

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
        if self.appendage_remaining > 0 and delta_estado:
            delta_estado = somar_deltas(
                delta_estado, {"door": Rotation3(0.0, radians(85.0), 0.0)}
            )

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
                    delta=delta_fisica(motion),
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
        # O resolver aplica crossfade com molas (continuidade de velocidade),
        # correção de colisão (se model injetado) e clamps finais.
        self._pose = self.pose_resolver.resolver(
            dt, composed, model=self._collision_model, state_time=self.state_time
        )
        displayed_pose = self.hand_motion.apply(self._pose, dt, self.state.value)
        displayed_pose = self._aplicar_interacao(displayed_pose, dt)
        self.rig.current = dict(displayed_pose)
        estado_pernas = (
            AnimationState.WALK.value
            if amostra_olhar.ativo and amostra_olhar.em_passo
            else self.state.value
        )
        vel_pernas = (
            (160.0 * self.pacote_olhar_tela.lado, 0.0)
            if amostra_olhar.ativo and amostra_olhar.em_passo
            else velocity
        )
        self.leg_motion.update(
            dt,
            estado_pernas,
            vel_pernas,
            self._reaction_time,
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
            personality=self.idle_personality.value,
        )
        return displayed_pose

    def _aplicar_interacao(
        self, pose: dict[str, Rotation3], dt: float
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
                    base.x + (atrasada.x - alvo.x),
                    base.y + (atrasada.y - alvo.y),
                    base.z + (atrasada.z - alvo.z),
                )
        return resultado

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
            return delta_idle(t, self.idle_personality, self.respiracao_valor)
        if state == AnimationState.DRAG:
            return delta_drag(motion, grab_part, self.drag_intensity)
        if state == AnimationState.WALK:
            return delta_walk(
                self.leg_motion.phase,
                run=False,
                personalidade=self.idle_personality.value,
            )
        if state == AnimationState.RUN:
            return delta_walk(
                self.leg_motion.phase,
                run=True,
                personalidade=self.idle_personality.value,
            )
        if state == AnimationState.FALL:
            return delta_fall(self.state_time, velocity)
        if state == AnimationState.SLEEP:
            return delta_sleep(t, self.modo_sono)
        # Estados não migrados: delta vazio (usa pose legada)
        return {}

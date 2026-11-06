"""Controlador procedural de animação do mascote.

As poses são produzidas pelo rig sem depender de clipes exportados. O
controlador escolhe um estado a partir da interação/física e faz crossfade
entre poses para evitar saltos bruscos.
"""

from __future__ import annotations

import random
from enum import StrEnum
from typing import ClassVar

from .anim_layers import MASCARA_MUSICA, CamadaAnim, MixerCamadas
from .body_motion import BodyMotion
from .dance_motion import DanceMotion
from .hand_motion import HandMotion
from .joint_springs import (
    CADEIA_DIREITA,
    CADEIA_ESQUERDA,
    LagChain,
    SpringPose,
)
from .leg_motion import LegMotion
from .respiracao import Respiracao
from .respiracao_tuning import parametros_de
from .rig import (
    ALL_GROUPS,
    IdlePersonality,
    Rig,
    Rotation3,
    pose_drag,
    pose_flourish,
    pose_idle,
    pose_interaction,
    pose_secondary,
    pose_sleep,
    pose_throw_release,
    pose_thrown,
    pose_walk,
)
from .spring_tuning import amortecimento_de, frequencia_de


class AnimationState(StrEnum):
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


class AnimationController:
    """Gera poses a cada frame e interpola mudanças de estado."""

    def __init__(self, rig: Rig, transition_seconds: float = 0.55) -> None:
        self.rig = rig
        self.transition_seconds = max(0.0, transition_seconds)
        self._active_transition_seconds = self.transition_seconds
        self.state: AnimationState | None = None
        self.state_time = 0.0
        self.idle_time = 0.0
        self._idle_clock = 0.0
        self.clock = 0.0
        self.idle_personality = IdlePersonality.CALM
        # Respiração contínua (engine-agnóstica): oscilador lento suavizado por
        # mola, calibrado pela personalidade atual. O renderer lê o valor
        # centrado para inflar o tórax no idle.
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
        self._transition_from = dict(self._pose)
        rig.reset()
        self._reaction: AnimationState | None = None
        self._reaction_time = 0.0
        self._cooldowns: dict[str, float] = {}
        self._look_direction = 0.0
        self._look_vertical = 0.0
        self._ambient_in = 28.0
        self.appendage_remaining = 0.0
        self._peek_in = self._personality_rng.uniform(60, 100)
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
        self._dance_preview_style = 'head_bob'
        # Crossfade por junta com continuidade de velocidade: a pose exibida
        # persegue o alvo autoral com molas, em vez de um blend linear que
        # zera a velocidade a cada troca de estado. Cada junta recebe a sua
        # tensão de spring_tuning (âncora firme, ponta solta). EXCEÇÃO: legs,
        # left-feet e right-feet recebem a tensão FIRME do corpo, porque o
        # movimento real das pernas/pés vem do IK de lower_body via leg_motion
        # (fora do mixer): não se duplica amortecimento aqui.
        firme = (frequencia_de("body"), amortecimento_de("body"))
        tensoes_crossfade = {
            grupo: (firme if grupo in ("legs", "left-feet", "right-feet")
                    else (frequencia_de(grupo), amortecimento_de(grupo)))
            for grupo in ALL_GROUPS
        }
        self._crossfade = SpringPose(tensoes=tensoes_crossfade)
        # Frequência-base de cada junta (regime estável): usada para devolver a
        # tensão da tabela depois que a aceleração da troca termina.
        self._frequencia_base = {grupo: tensao[0]
                                 for grupo, tensao in tensoes_crossfade.items()}
        self._crossfade.definir(dict(self._pose))
        self._just_transitioned = True
        # Camada 'interacao': atraso efetivo da cadeia dos braços (braço ->
        # antebraço -> mão -> dedos). Cada cadeia persegue o alvo autoral com
        # molas, e a diferença (saída - alvo) vira um follow-through aditivo
        # somado sobre o follow-through das mãos (hand_motion).
        self.cadeia_direita = LagChain(CADEIA_DIREITA)
        self.cadeia_esquerda = LagChain(CADEIA_ESQUERDA)
        self.cadeia_direita.definir(dict(self._pose))
        self.cadeia_esquerda.definir(dict(self._pose))

    def preview_dance(self, style):
        if style not in ('head_bob', 'hip_hop', 'rock', 'breakdance'):
            return
        self._dance_preview_remaining = 15.0
        self._dance_preview_style = style
        self.dance_motion.style = style
        self.dance_motion.style_beats = 0
        self.dance_motion.pose.clear()

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
        """Soma um impulso à respiração para inflar o tórax por evento.

        Delega a ``Respiracao.empurrar``. TODO: ligar este gancho ao estado
        SNEEZE (inspiração antes do espirro) quando a FEAT do espirro existir.
        NÃO implementar o sneeze aqui.
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
        self._transition_from = dict(self._pose)
        self._crossfade.definir(dict(self._pose))
        self._just_transitioned = True
        self._active_transition_seconds = max(self.transition_seconds, 1.0)
        self.state_time = 0.0

    REACTION_SECONDS: ClassVar[dict[AnimationState, float]] = {
        **{AnimationState(k): 3.2 for k in ("hang_loose", "thumbs_up", "rock", "finger_gun")},
        AnimationState.SNEEZE: 9.0,
        AnimationState.CLICK: 0.5,
        AnimationState.DOUBLE_CLICK: 1.4,
        AnimationState.PET: 1.5,
        AnimationState.POKE: 0.4,
        AnimationState.WAKE: 1.2,
        AnimationState.LAND: 0.45,
        AnimationState.WAVE: 2.2,
        AnimationState.STRETCH: 2.8,
        AnimationState.PEEK: 9.0,
        AnimationState.HIT: 0.65,
    }

    def interact(self, kind: str, *, direction: float | None = None, strength: float = 1.0) -> None:
        """Interação acorda o mascote e dispara uma reação com cooldown."""
        self.idle_time = 0.0
        if kind == 'peek':
            self.appendage_remaining = 9.0
            return
        if kind == "drag_start":
            self._reaction = None
            return
        if self.state == AnimationState.SLEEP:
            kind = "wake"
        if kind not in self.REACTION_SECONDS or self.clock < self._cooldowns.get(kind, 0.0):
            return
        self.body_motion.impulse(kind, self._look_direction if direction is None else direction, strength)
        self._reaction = AnimationState(kind)
        self._reaction_time = 0.0
        self._cooldowns[kind] = self.clock + max(self.REACTION_SECONDS[self._reaction], 0.5)

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

    def update(
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
        grab_part: str = 'body',
    ) -> dict[str, Rotation3]:
        """Atualiza o estado e devolve um snapshot de rotações em radianos."""
        dt = min(0.1, max(0.0, dt))
        if self._dance_preview_remaining > 0:
            self._dance_preview_remaining = max(0, self._dance_preview_remaining-dt)
            music_playing = react_to_beat = True
            dance_chance = 1.0
            music_intensity, music_bass, music_bpm = {
                'head_bob': (.2,.03,80), 'hip_hop': (.5,.3,95),
                'rock': (.6,.15,135), 'breakdance': (.9,.6,145),
            }[self._dance_preview_style]
            self.dance_motion.override = self._dance_preview_style
            self._dance_remaining = 1.0
        self.clock += dt
        self.delta_time = dt
        # Avança a respiração com o dt já saturado e expõe o valor centrado do
        # frame (-1..1) para o renderer inflar o tórax.
        self.respiracao.atualizar(dt)
        self.respiracao_valor = self.respiracao.centrada
        self.music_active = music_playing
        self.appendage_remaining = max(0, self.appendage_remaining-dt)
        self.body_motion.update(dt, pointer=pointer_position, dragging=dragging,
                                hovered=hovered, look=(look_direction, look_vertical),
                                grounded=grounded, velocity=velocity, grab_part=grab_part)
        if self.state == AnimationState.DRAG and not dragging:
            self._release_time = 0.0
            self._release_grip = self.drag_intensity
        else:
            self._release_time += dt
        self.drag_intensity += (max(0, min(1, drag_intensity))-self.drag_intensity)*min(1, dt*8)
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
        if music_playing and react_to_beat and dance_chance > 0 and self.state == AnimationState.DANCE:
            self._dance_remaining = max(self._dance_remaining, 1.0)
        beat_edge = beat_detected and not self._previous_beat
        self._previous_beat = beat_detected
        if react_to_beat and beat_edge and self._dance_remaining > 0:
            pass  # Onsets correct cadence; do not classify quiet audio as loud.
        self.dance_motion.update(dt, music_intensity, music_bass, music_bpm, beat_edge)
        self._look_direction += (max(-1.0, min(1.0, look_direction)) - self._look_direction) * min(1.0, dt * 10.0)
        self._look_vertical += (max(-1.0, min(1.0, look_vertical)) - self._look_vertical) * min(1.0, dt * 10.0)
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
        if next_state in (AnimationState.IDLE, AnimationState.DANCE) and grounded and idle_enabled and not hovered:
            self._peek_in -= dt
            if self._peek_in <= 0 and self._reaction is None:
                self.appendage_remaining = 9.0
                self._peek_in = self._personality_rng.uniform(60, 100)
        if next_state == AnimationState.IDLE and grounded and idle_enabled and not hovered:
            self._ambient_in -= dt
            if self._ambient_in <= 0 and self._reaction is None:
                self._reaction = self._personality_rng.choice(
                    [AnimationState.WAVE, AnimationState.STRETCH]
                )
                self._reaction_time = 0.0
                self._ambient_in = self._personality_rng.uniform(32.0, 48.0)
        if next_state != AnimationState.DRAG and (next_state != AnimationState.FALL or self._reaction == AnimationState.HIT):
            if self._reaction is not None and (next_state != AnimationState.DANCE or
                    self._reaction in (AnimationState.HIT, AnimationState.SNEEZE)):
                next_state = self._reaction
            elif hovered and next_state == AnimationState.IDLE:
                next_state = AnimationState.HOVER
        if next_state in (AnimationState.IDLE, AnimationState.WAVE, AnimationState.STRETCH, AnimationState.PEEK):
            self.idle_time += dt
            if sleep_after_idle_seconds > 0 and self.idle_time >= sleep_after_idle_seconds:
                next_state = AnimationState.SLEEP
        else:
            self.idle_time = 0.0

        if next_state in (AnimationState.IDLE, AnimationState.HOVER) and idle_enabled and not self._personality_locked:
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
                self._transition_from = dict(self._pose)
                self._crossfade.definir(dict(self._pose))
                self._just_transitioned = True
                self._active_transition_seconds = max(self.transition_seconds, 1.4)
                self.state_time = 0.0
        elif next_state != AnimationState.IDLE:
            self._personality_elapsed = 0.0

        if next_state != self.state:
            self._transition_from = dict(self._pose)
            self._crossfade.definir(dict(self._pose))
            self._just_transitioned = True
            self.state = next_state
            self.state_time = 0.0
            self._active_transition_seconds = (min(self.transition_seconds, .22)
                if next_state in (AnimationState.DRAG, AnimationState.FALL, AnimationState.HIT)
                else self.transition_seconds)
        else:
            self.state_time += dt

        self.rig.reset()
        if self.state in (AnimationState.IDLE, AnimationState.HOVER):
            if idle_enabled:
                self._idle_clock += dt
                pose_idle(self.rig, self._idle_clock, self.idle_personality)
            if self.state == AnimationState.HOVER:
                pose_interaction(self.rig, "hover", self.state_time,
                                 self._look_direction, self._look_vertical)
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
            pose_sleep(self.rig, self.clock)
        elif self.state.value in ('hang_loose', 'thumbs_up', 'rock', 'finger_gun'):
            pose_idle(self.rig, self.clock, self.idle_personality)
            self.rig.set_rotation('right-arm', x=-20, z=0)
            self.rig.set_rotation('ant-arm', x=-8, z=-60)
            self.rig.set_rotation('hand', x=180, y=0, z=0)
            self.rig.set_rotation('fingers', z=0)
        elif self.state == AnimationState.SNEEZE:
            from .rig import pose_sneeze
            pose_sneeze(self.rig, self._reaction_time)
        elif self.state in (AnimationState.WAVE, AnimationState.STRETCH, AnimationState.PEEK, AnimationState.HIT):
            pose_flourish(self.rig, self.state.value, self._reaction_time)
        elif self.state == AnimationState.HOVER or self.state in self.REACTION_SECONDS:
            pose_interaction(self.rig, self.state.value, self._reaction_time, self._look_direction, self._look_vertical)

        pose_secondary(self.rig, self._idle_clock if self.state in (AnimationState.IDLE, AnimationState.HOVER) else self.clock,
                       self.state.value, self.idle_personality)
        if not dragging and self._release_time < .9:
            pose_throw_release(self.rig, self._release_time, self._release_grip)

        if dragging:
            motion = self.body_motion.snapshot
            # Hanging limbs counter-rotate the torso and trail pointer motion.
            self.rig.set_rotation('right-arm', x=-motion.pitch*.55,
                                  z=62-motion.roll*.55+motion.limb_swing*.45)
            self.rig.set_rotation('left-arm', x=-motion.pitch*.55,
                                  z=-62-motion.roll*.55+motion.limb_swing*.4)
            self.rig.set_rotation('ant-arm', x=motion.limb_swing*.3, z=-8)
            self.rig.set_rotation('ant-arm2', x=motion.limb_swing*.25, z=8)
            if grab_part == 'right-arm':
                self.rig.set_rotation('right-arm', x=-8, z=-55)
                self.rig.set_rotation('ant-arm', x=0, z=-8)
            elif grab_part == 'left-arm':
                self.rig.set_rotation('left-arm', x=-8, z=55)
                self.rig.set_rotation('ant-arm2', x=0, z=8)
            elif grab_part == 'body':
                # Loose arms and a drooping neck when lifted by the back.
                self.rig.set_rotation('head', x=-12, z=motion.limb_swing*.08)
                self.rig.set_rotation('right-arm', x=-motion.pitch*.9, z=65+motion.limb_swing*.25)
                self.rig.set_rotation('left-arm', x=-motion.pitch*.9, z=-65+motion.limb_swing*.25)
                self.rig.set_rotation('ant-arm', x=3+motion.limb_swing*.2, z=-4)
                self.rig.set_rotation('ant-arm2', x=3+motion.limb_swing*.18, z=4)
        if self.appendage_remaining > 0:
            self.rig.set_rotation('door', y=85)
        target = self.rig.pose()
        # A saída por junta passa pelo mixer de camadas aditivas. A pose
        # autoral vira a camada 'base'; na dança, as juntas de música saem da
        # base (zeradas) e entram como camada aditiva 'musica', de modo que
        # base + musica reproduz a dança de hoje sem dupla aplicação. Pernas e
        # pés permanecem na base (fora da máscara) e no IK de lower_body.
        camadas = [CamadaAnim("base", dict(target))]
        if self.state == AnimationState.DANCE:
            base = camadas[0].contribuicao
            contribuicao_musica = {
                grupo: base[grupo] for grupo in MASCARA_MUSICA if grupo in base
            }
            for grupo in contribuicao_musica:
                base[grupo] = Rotation3()
            camadas.append(CamadaAnim("musica", contribuicao_musica,
                                      mascara=MASCARA_MUSICA))
        composed = MixerCamadas.compor(camadas)

        if self._active_transition_seconds == 0.0:
            # Sem crossfade: a pose exibida acompanha o alvo diretamente.
            self._crossfade.definir(composed)
            self._pose = {group: composed.get(group, Rotation3()) for group in composed}
            self._just_transitioned = False
        elif self._just_transitioned:
            # Primeiro frame após a troca: segura a pose anterior (continuidade
            # de posição e velocidade) antes de a mola começar a perseguir. As
            # cadeias de atraso NÃO são reposicionadas: a pose segurada mantém
            # os alvos dos braços estáveis na borda, então o follow-through
            # evolui por um único passo de mola, sem salto perceptível.
            self._crossfade.definir({group: self._transition_from.get(group, Rotation3())
                                     for group in composed})
            self._pose = {group: self._transition_from.get(group, Rotation3())
                          for group in composed}
            self._just_transitioned = False
        else:
            # Molas por junta com continuidade de velocidade. Durante a janela
            # de transição acelera-se o retargeting (sensação de troca rápida
            # de estado), sem uniformizar todas as juntas: usa-se o MAIOR entre
            # a tensão própria da junta e a frequência da troca, preservando a
            # hierarquia âncora-firme / ponta-solta. No regime estável cada
            # junta volta à sua tensão da tabela (não se reescreve frequency).
            em_transicao = self.state_time < self._active_transition_seconds
            freq_troca = max(0.6, 1.0 / self._active_transition_seconds)
            for grupo, mola in self._crossfade.molas.items():
                freq_junta = self._frequencia_base.get(grupo, freq_troca)
                frequencia = max(freq_junta, freq_troca) if em_transicao else freq_junta
                mola.x.frequency = mola.y.frequency = mola.z.frequency = frequencia
            self._pose = self._crossfade.atualizar(dt, composed)
        displayed_pose = self.hand_motion.apply(self._pose, dt, self.state.value)
        displayed_pose = self._aplicar_interacao(displayed_pose, dt)
        self.rig.current = dict(displayed_pose)
        self.leg_motion.update(dt, self.state.value, velocity, self._reaction_time,
                               self.body_motion.snapshot.limb_swing if dragging else self.body_motion.snapshot.roll,
                               dance_phase=(self.dance_motion.style_beats*6.28318530718
                                            if self.dance_motion.style == 'breakdance' else self.dance_motion.phase),
                               dance_strength=self.dance_motion.strength,
                               dance_style=self.dance_motion.style)
        return displayed_pose

    def _aplicar_interacao(self, pose: dict[str, Rotation3], dt: float) -> dict[str, Rotation3]:
        """Camada 'interacao': soma o atraso das cadeias dos braços à pose.

        Cada cadeia persegue, por mola, os alvos autorais da pose composta
        (``self._pose``, em radianos). O follow-through aditivo por junta é a
        diferença entre a saída atrasada da cadeia e o alvo, deixando a ponta
        (antebraço/mão/dedos) arrastar atrás da base do braço. Isso soma sobre
        o follow-through já aplicado por hand_motion.
        """
        resultado = dict(pose)
        for cadeia in (self.cadeia_direita, self.cadeia_esquerda):
            alvos = {grupo: self._pose[grupo] for grupo in cadeia.cadeia
                     if grupo in self._pose}
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

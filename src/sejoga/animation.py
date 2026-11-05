"""Controlador procedural de animação do mascote.

As poses são produzidas pelo rig sem depender de clipes exportados. O
controlador escolhe um estado a partir da interação/física e faz crossfade
entre poses para evitar saltos bruscos.
"""

from __future__ import annotations

import random
from enum import StrEnum
from .body_motion import BodyMotion
from .leg_motion import LegMotion
from .hand_motion import HandMotion

from .rig import (
    IdlePersonality,
    Rig,
    Rotation3,
    pose_dance,
    pose_drag,
    pose_idle,
    pose_interaction,
    pose_sleep,
    pose_thrown,
    pose_walk,
    pose_flourish,
    pose_secondary,
    pose_throw_release,
)


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
        self._idle_clock = 0.0
        self._personality_locked = True
        self._personality_elapsed = 0.0
        self._transition_from = dict(self._pose)
        self._active_transition_seconds = max(self.transition_seconds, 1.0)
        self.state_time = 0.0

    REACTION_SECONDS = {
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
        if music_playing and music_intensity > 0.12:
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
        dance_chance: float = 1.0,
        react_to_beat: bool = True,
        beat_detected: bool = False,
        idle_enabled: bool = True,
        sleep_after_idle_seconds: int = 0,
        hovered: bool = False,
        look_direction: float = 0.0,
        look_vertical: float = 0.0,
        pointer_position: tuple[float, float] | None = None,
    ) -> dict[str, Rotation3]:
        """Atualiza o estado e devolve um snapshot de rotações em radianos."""
        dt = min(0.1, max(0.0, dt))
        self.clock += dt
        self.body_motion.update(dt, pointer=pointer_position, dragging=dragging,
                                hovered=hovered, look=(look_direction, look_vertical),
                                grounded=grounded, velocity=velocity)
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
        beat_edge = beat_detected and not self._previous_beat
        self._previous_beat = beat_detected
        if react_to_beat and beat_edge and self._dance_remaining > 0:
            music_intensity = max(music_intensity, 0.75)
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
        if next_state == AnimationState.IDLE and grounded and idle_enabled and not hovered:
            self._ambient_in -= dt
            self._peek_in -= dt
            if self._peek_in <= 0 and self._reaction is None:
                self._reaction = AnimationState.PEEK
                self._reaction_time = 0.0
                self._peek_in = self._personality_rng.uniform(60, 100)
            if self._ambient_in <= 0 and self._reaction is None:
                self._reaction = self._personality_rng.choice(
                    [AnimationState.WAVE, AnimationState.STRETCH]
                )
                self._reaction_time = 0.0
                self._ambient_in = self._personality_rng.uniform(32.0, 48.0)
        if next_state != AnimationState.DRAG and (next_state != AnimationState.FALL or self._reaction == AnimationState.HIT):
            if self._reaction is not None:
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
                self._idle_clock = 0.0
                self._personality_elapsed = 0.0
                self._personality_interval = self._personality_rng.uniform(24.0, 36.0)
                self._transition_from = dict(self._pose)
                self._active_transition_seconds = max(self.transition_seconds, 1.4)
                self.state_time = 0.0
        elif next_state != AnimationState.IDLE:
            self._personality_elapsed = 0.0

        if next_state != self.state:
            self._transition_from = dict(self._pose)
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
            pose_dance(self.rig, self.clock, music_intensity)
        elif self.state == AnimationState.SLEEP:
            pose_sleep(self.rig, self.clock)
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

        target = self.rig.pose()
        if self._active_transition_seconds == 0.0:
            alpha = 1.0
        else:
            linear = min(1.0, self.state_time / self._active_transition_seconds)
            alpha = linear ** 3 * (linear * (linear * 6.0 - 15.0) + 10.0)

        self._pose = {
            group: self._blend(self._transition_from.get(group, Rotation3()), rotation, alpha)
            for group, rotation in target.items()
        }
        displayed_pose = self.hand_motion.apply(self._pose, dt, self.state.value)
        self.rig.current = dict(displayed_pose)
        self.leg_motion.update(dt, self.state.value, velocity, self._reaction_time,
                               self.body_motion.snapshot.roll)
        return displayed_pose

    @staticmethod
    def _blend(start: Rotation3, end: Rotation3, amount: float) -> Rotation3:
        inverse = 1.0 - amount
        return Rotation3(
            x=start.x * inverse + end.x * amount,
            y=start.y * inverse + end.y * amount,
            z=start.z * inverse + end.z * amount,
        )

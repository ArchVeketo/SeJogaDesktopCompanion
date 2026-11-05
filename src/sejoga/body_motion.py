"""Inertial body motion driven by mouse gestures, independent of the engine.

Springs use their analytic underdamped solution so a 30/60/120 Hz renderer
does not change the weight or stability of the character.
"""
from dataclasses import dataclass
from math import cos, exp, isfinite, pi, sin, sqrt


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class Spring:
    frequency: float
    damping: float
    value: float = 0.0
    velocity: float = 0.0

    def update(self, dt, target):
        if dt <= 0:
            return self.value
        omega = 2 * pi * self.frequency
        decay = self.damping * omega
        oscillation = omega * sqrt(1 - self.damping * self.damping)
        offset = self.value - target
        coefficient = (self.velocity + decay * offset) / oscillation
        phase = oscillation * dt
        attenuation = exp(-decay * dt)
        displacement = offset * cos(phase) + coefficient * sin(phase)
        self.value = target + attenuation * displacement
        self.velocity = attenuation * (
            -decay * displacement + oscillation * (-offset * sin(phase) + coefficient * cos(phase))
        )
        return self.value


@dataclass(frozen=True)
class BodyPose:
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    head_roll: float = 0.0
    head_pitch: float = 0.0
    arm_lag: float = 0.0
    compression: float = 0.0
    hanging: float = 0.0
    limb_swing: float = 0.0
    stretch: float = 0.0


class BodyMotion:
    def __init__(self):
        self.roll = Spring(1.15, .58)
        self.pitch = Spring(1.25, .60)
        self.yaw = Spring(1.2, .78)
        self.neck_roll = Spring(1.65, .58)
        self.neck_pitch = Spring(1.75, .60)
        self.compression = Spring(1.6, .52)
        self.suspension = Spring(2.1, .9)
        self.limbs = Spring(1.1, .30)
        self.snapshot = BodyPose()
        self.pointer_velocity = (0.0, 0.0)
        self._pointer = None
        self._engaged = False

    def impulse(self, kind, direction=0.0, strength=1.0):
        direction = clamp(direction, -1, 1)
        strength = clamp(strength, 0, 2)
        if kind in ("click", "poke", "double_click"):
            self.roll.velocity += (direction or .35) * 38 * strength
            self.pitch.velocity -= 25 * strength
        elif kind == "pet":
            self.roll.velocity += direction * 16 * strength
        elif kind in ("hit", "land"):
            self.roll.velocity += direction * 48 * strength
            self.pitch.velocity += 28 * strength
            self.compression.velocity += 4.5 * strength

    def update(self, dt, *, pointer=None, dragging=False, hovered=False,
               look=(0.0, 0.0), grounded=True, velocity=(0.0, 0.0), grab_part='body'):
        dt = clamp(dt, 0.0, .1) if isfinite(dt) else 0.0
        if dt == 0:
            return self.snapshot
        engaged = dragging or hovered
        raw = (0.0, 0.0)
        valid_pointer = pointer is not None and all(isfinite(v) for v in pointer)
        if valid_pointer and self._pointer is not None and engaged and self._engaged:
            raw = tuple(clamp((pointer[k] - self._pointer[k]) / dt, -2500, 2500) for k in range(2))
        self._pointer = tuple(pointer) if valid_pointer else None
        self._engaged = engaged
        response = 1 - exp(-18 * dt)
        self.pointer_velocity = tuple(old + (new - old) * response
                                      for old, new in zip(self.pointer_velocity, raw, strict=True))
        vx, vy = self.pointer_velocity
        if dragging:
            roll_target = clamp(vx * .012, -23, 23)
            if grab_part in ('left-feet', 'right-feet', 'legs'):
                roll_target += 155 if grab_part != 'left-feet' else -155
            elif grab_part in ('right-arm', 'left-arm'):
                roll_target += 45 if grab_part == 'right-arm' else -45
            pitch_target = clamp((-26 if grab_part == 'body' else -9)-vy * .009, -36, 4)
            yaw_target = clamp(-vx * .003, -5, 5)
        elif hovered:
            roll_target = clamp(vx * .003 - look[0] * 3.8, -8, 8)
            pitch_target = clamp(-vy * .002 - look[1] * 3.2, -6, 6)
            yaw_target = -look[0] * 3.0
        elif not grounded:
            roll_target = clamp(velocity[0] * .004, -9, 9)
            pitch_target = clamp(-velocity[1] * .002, -4, 4)
            yaw_target = 0
        else:
            roll_target = pitch_target = yaw_target = 0
        self.roll.update(dt, roll_target)
        self.pitch.update(dt, pitch_target)
        self.yaw.update(dt, yaw_target)
        self.neck_roll.update(dt, self.roll.value)
        self.neck_pitch.update(dt, self.pitch.value)
        self.compression.update(dt, 0)
        self.suspension.update(dt, 1.0 if dragging or not grounded else 0.0)
        self.limbs.update(dt, clamp(-vx*.021, -30, 30) if dragging else 0)
        # Bound the visual response without modifying desktop physics or cursor.
        self.snapshot = BodyPose(
            roll=clamp(self.roll.value, -178, 178),
            pitch=clamp(self.pitch.value, -38, 16),
            yaw=clamp(self.yaw.value, -7, 7),
            head_roll=clamp((self.neck_roll.value - self.roll.value) * .65, -8, 8),
            head_pitch=clamp((self.neck_pitch.value - self.pitch.value) * .6 - 5*self.suspension.value, -12, 6),
            arm_lag=clamp(-self.roll.velocity * .035, -6, 6),
            compression=clamp(self.compression.value, -.12, .20),
            hanging=clamp(self.suspension.value, 0, 1),
            limb_swing=clamp(self.limbs.value, -30, 30),
            stretch=(.08 if grab_part != 'body' else .025)*clamp(self.suspension.value,0,1) if dragging else 0,
        )
        return self.snapshot

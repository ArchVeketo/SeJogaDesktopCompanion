"""Engine independent arm follow-through layered over authored gestures."""

from math import exp, radians, sin

from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.nucleo.esqueleto import Rotation3

_HAND_ENERGY = {
    "idle": 1.20,
    "hover": 1.05,
    "sit": 0.90,
    "walk": 1.15,
    "run": 1.35,
    "jump": 0.85,
    "dance": 1.35,
    "drag": 0.75,
    "fall": 0.80,
    "land": 0.55,
    "celebrate": 0.75,
    "pet": 0.50,
    "poke": 0.40,
    "hit": 0.45,
    "surprise": 0.45,
    "click": 0.40,
    "double_click": 0.50,
    "wake": 0.45,
    "stretch": 0.35,
    "peek": 0.45,
    "teimosia": 0.55,
    "wave": 0.25,
    "sneeze": 0.25,
    "sleep": 0.12,
    "blue_balls": 0.20,
    "virtual_insanity": 0.30,
    "goku_teleport": 0.0,
    "hang_loose": 0.15,
    "thumbs_up": 0.15,
    "rock": 0.15,
    "finger_gun": 0.15,
    "peace": 0.15,
    "point": 0.15,
    "open_hands": 0.0,
    "close_fists": 0.0,
}

_PARES_BRACOS = (
    ("right-arm", "shoulder", "ant-arm", "hand", "fingers", 1),
    ("left-arm", "shoulder2", "ant-arm2", "hand2", "fingers2", -1),
)


class HandMotion:
    """Keep authored rotations and add bounded, delayed joint offsets."""

    def __init__(self):
        """Inicia os filtros das mãos em repouso."""
        self.clock = 0.0
        self.offsets = {}
        self.previous = {}
        self._vel_filtrada: dict[str, tuple[float, float]] = {}
        self._peso_ativo = 1.0

    def _alvos_lado(
        self, pose, dt: float, state: str, energy: float, peso_suave: float,
        upper_arm: str, shoulder: str, arm: str, wrist: str, fingers: str, side: int,
    ) -> tuple[dict[str, tuple[float, float, float]], dict[str, int]]:
        """Calcula alvos e taxas de suavização para um braço."""
        authored = pose[arm]
        upper_authored = pose.get(upper_arm, authored)
        previous = self.previous.get(arm, authored)
        raw_x = (authored.x - previous.x) / dt if dt > 1e-4 else 0.0
        raw_z = (authored.z - previous.z) / dt if dt > 1e-4 else 0.0
        self.previous[arm] = authored
        # Filtro passa-baixa na derivada elimina jitter de 1 quadro em cortes de estado
        alpha_v = 1.0 - exp(-dt * 18.0) if dt > 0.0 else 1.0
        prev_vx, prev_vz = self._vel_filtrada.get(arm, (0.0, 0.0))
        speed_x = prev_vx + (raw_x - prev_vx) * alpha_v
        speed_z = prev_vz + (raw_z - prev_vz) * alpha_v
        self._vel_filtrada[arm] = (speed_x, speed_z)
        lag_x = max(-radians(10), min(radians(10), -speed_x * 0.055)) * energy
        lag_z = max(-radians(12), min(radians(12), -speed_z * 0.06)) * energy
        phase = self.clock * 1.35 - side * 0.75
        relaxado = state in ("idle", "hover", "sit")
        variacao = sin(self.clock * 0.54 + side * 1.6) if relaxado else 0.0
        elevacao_braco = max(-0.8, min(1.4, (-upper_authored.z * side) + 1.0))
        escala_clavicula = min(1.0, max(0.0, energy)) * peso_suave
        clavicula_z = radians(5.5 * elevacao_braco * escala_clavicula) * (-side)
        targets = {
            upper_arm: (
                radians(1.8) * sin(phase + 0.3) * energy,
                radians(2.5 + 3.8 * relaxado) * sin(phase * 0.85 - side * 0.4) * side * energy,
                radians(2.6 + 1.8 * relaxado) * sin(phase - 0.2) * side * energy,
            ),
            shoulder: (
                radians(1.8) * sin(phase + 0.45) * energy,
                radians(1.6 * elevacao_braco * escala_clavicula) * side,
                clavicula_z + radians(2.4) * sin(phase + 0.1) * side * energy,
            ),
            arm: (
                radians(2.8) * sin(phase) * energy,
                0.0,
                (radians(3.6) * (0.5 + 0.5 * sin(phase - 0.35)) * side * energy) + lag_z * 0.52,
            ),
            wrist: (
                lag_x * 0.85 + radians(5.0 + 5.5 * relaxado) * sin(phase - 0.65 + variacao) * energy,
                radians(6.5) * sin(phase - 0.5) * side * energy,
                lag_z + radians(6.0) * sin(phase - 0.8) * side * energy,
            ),
            fingers: (
                radians(1.8) * sin(phase - 1.0) * energy,
                0.0,
                radians(7.2) * sin(phase - 1.1) * side * energy + lag_z * 0.42,
            ),
        }
        rates = {upper_arm: 11, shoulder: 11, arm: 9, wrist: 7, fingers: 5}
        return targets, rates

    def apply(self, pose, dt, state, *, ativo: bool = True):
        """Aplica o follow-through das mãos sobre a pose com rampa quíntica de entrada/saída."""
        dt = max(0.0, min(0.05, dt))
        self.clock += dt
        alvo_peso = 1.0 if ativo else 0.0
        passo_peso = dt / 0.18 if dt > 0.0 else 1.0
        self._peso_ativo += max(-passo_peso, min(passo_peso, alvo_peso - self._peso_ativo))
        peso_suave = suavizar_quintico(self._peso_ativo)
        result = dict(pose)
        energy = _HAND_ENERGY.get(state, 0.35) * peso_suave
        for upper_arm, shoulder, arm, wrist, fingers, side in _PARES_BRACOS:
            if arm not in pose:
                continue
            targets, rates = self._alvos_lado(
                pose, dt, state, energy, peso_suave, upper_arm, shoulder, arm, wrist, fingers, side
            )
            for joint, target in targets.items():
                if joint not in pose:
                    continue
                old = self.offsets.get(joint, (0.0, 0.0, 0.0))
                taxa = rates[joint] if ativo else max(rates[joint], 14)
                blend = 1 - exp(-dt * taxa)
                offset = tuple(a + (b - a) * blend for a, b in zip(old, target, strict=True))
                if not ativo and self._peso_ativo <= 1e-4 and max(abs(v) for v in offset) < 1e-4:
                    offset = (0.0, 0.0, 0.0)
                self.offsets[joint] = offset
                base = result[joint]
                result[joint] = Rotation3(
                    base.x + offset[0], base.y + offset[1], base.z + offset[2]
                )
        return result

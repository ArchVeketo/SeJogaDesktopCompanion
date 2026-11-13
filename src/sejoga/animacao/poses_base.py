"""Presets de pose procedurais do companion.

Saíram de ``nucleo/esqueleto.py``: usam gestos e clipes de ``animacao``, e
``nucleo`` não importa ``animacao``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from math import cos, degrees, exp, pi, sin, tanh

from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.animacao.clipes_animacao import amostrar_clipe
from sejoga.animacao.clipes_ocioso import sample_idle
from sejoga.animacao.gestos_reacao import (
    aplicar_aceno,
    aplicar_alongar,
    aplicar_cutucar,
)
from sejoga.animacao.gestos_tuning import (
    SURPRESA_BRACO,
    SURPRESA_CABECA,
    SURPRESA_GIRO,
    SURPRESA_RECUO,
    WAKE_BRACO_ELEVACAO,
)
from sejoga.animacao.interpolacao import amostrar_pista
from sejoga.animacao.pose_repouso import pose_repouso
from sejoga.animacao.respiracao_tuning import parametros_de
from sejoga.animacao.ruido_procedural import delta_micro_ruido_idle
from sejoga.nucleo.esqueleto import IdlePersonality, Rig


def _idle_pulse(
    t: float,
    period: float,
    attack: float,
    hold: float,
    release: float,
    offset: float = 0.0,
) -> float:
    """Devolve um gesto suavizado seguido de pausa legível dentro do loop idle."""
    phase = (t + offset) % period

    def ease(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

    if phase < attack:
        return ease(phase / attack)
    phase -= attack
    if phase < hold:
        return 1.0
    phase -= hold
    if phase < release:
        return 1.0 - ease(phase / release)
    return 0.0


# --------------------------------------------------------------------------- #
# Presets de pose — ponto de partida para as animações do companion
# --------------------------------------------------------------------------- #
def pose_idle(
    rig: Rig,
    t: float,
    personality: IdlePersonality = IdlePersonality.CALM,
    respiracao: float = 0.0,
) -> None:
    """Aplica o idle com personalidade própria, sem deixar de respeitar a dobradiça.

    ``respiracao`` é o valor centrado (-1..1) vindo de ``Respiracao`` (0 no
    repouso); default 0.0 preserva o comportamento de quem não passa respiração.
    A amplitude/bounce por personalidade vêm de ``respiracao_tuning``: o peito
    (``body`` eixo x) infla e ombros/cabeça acompanham de leve, garantindo que
    NENHUM idle fique totalmente estático (sempre respiração + micro-movimento).
    """
    parametros = parametros_de(personality)
    # Fonte única: os 9 idles vivem em ``idle_clips.CLIPS``.
    pose = sample_idle(personality.value, t, respiracao, parametros.amplitude)
    for group, (x, y, z) in pose.items():
        rig.set_rotation(group, x=x, y=y, z=z)


def pose_walk(rig: Rig, t: float, *, run: bool = False) -> None:
    """Aplica a passada alternada: delta do clipe (ver anim_clips) sobre o repouso."""
    frequency = 2.5 if run else 1.5
    # Um ciclo do clipe = uma passada completa; a frequência controla o ritmo.
    delta = amostrar_clipe("run" if run else "walk", t * frequency)
    repouso = pose_repouso()
    rig.set_rotation("legs", x=0)
    rig.set_rotation("left-feet", x=0)
    rig.set_rotation("right-feet", x=0)
    for group, (dx, dy, dz) in delta.items():
        base = repouso[group]
        rig.set_rotation(
            group,
            x=degrees(base.x) + dx,
            y=degrees(base.y) + dy,
            z=degrees(base.z) + dz,
        )


def pose_drag(
    rig: Rig, t: float, direction: float = 0.0, drag_intensity: float = 0.0
) -> None:
    """Inclina na direção do arraste e estende os braços para se equilibrar."""
    grip = max(0, min(1, drag_intensity))
    rig.set_rotation("fingers", z=8 + 24 * grip)
    rig.set_rotation("fingers2", z=-8 - 24 * grip)

    direction = max(-1.0, min(1.0, direction))
    rig.set_rotation("body", y=-direction * 3.0)
    rig.set_rotation("head", y=direction * 3.0)
    right_reach = max(0.0, -direction)
    left_reach = max(0.0, direction)

    # IK: a mão vai para o ALVO de arraste (à frente, equilibrando). O "reach"
    # por direção estende o braço mais para a frente (PROFUNDIDADE = heading Y),
    # em vez de chutar ângulos diretos. Os termos secundários seguem por cima.
    drag_r = braco_hpr_graus("right", "drag")
    drag_l = braco_hpr_graus("left", "drag")
    rb, re = drag_r["right-arm"], drag_r["ant-arm"]
    lb, le = drag_l["left-arm"], drag_l["ant-arm2"]
    # Reach: leva o braço MAIS para a frente = H positivo no direito (medido no
    # grafo de cena), espelhado (negativo) no esquerdo.
    rig.set_rotation("right-arm", x=rb[0], y=rb[1] + 24.0 * right_reach, z=rb[2])
    rig.set_rotation("left-arm", x=lb[0], y=lb[1] - 24.0 * left_reach, z=lb[2])
    rig.set_rotation("ant-arm", x=re[0], y=re[1], z=re[2] + 20.0 * right_reach)
    rig.set_rotation("ant-arm2", x=le[0], y=le[1], z=le[2] - 20.0 * left_reach)
    rig.set_rotation("hand", z=direction * 10.0)
    rig.set_rotation("hand2", z=direction * 10.0)

    # Shoulder compensation: shoulder follows ~15% of ant-arm x rotation
    shoulder_comp = re[0] * 0.15
    rig.set_rotation("shoulder", x=shoulder_comp)
    rig.set_rotation("shoulder2", x=-shoulder_comp)


def _sono_sentado(rig: Rig, breath: float, entrada: float) -> None:
    # Sentado no chão com as pernas abertas ("pernas abertas", torso relaxado)
    tronco, cabeca, virada = amostrar_pista(
        ((0.0, (0, 0, 0)), (0.45, (-9, -4, 1)), (1.35, (5, 5, 2)),
         (2.7, (6, 19, 3))),
        entrada,
    )
    rig.set_rotation("body", x=tronco + breath * 0.6)
    rig.set_rotation("cintura", x=2.0)
    rig.set_rotation("abdomen", x=2.0)
    rig.set_rotation("peitoral", x=2.0)
    rig.set_rotation("head", x=cabeca + breath * 0.8, y=virada)
    # Pernas splayadas para fora (abertas no chão)
    rig.set_rotation("coxa-direita", y=10.0)
    rig.set_rotation("coxa-esquerda", y=-10.0)
    for lado in ("right", "left"):
        for grupo, (x, y, z) in braco_hpr_graus(lado, "colo").items():
            rig.set_rotation(grupo, x=x, y=y, z=z)
    rig.set_rotation("hand", x=8.0, z=-12.0)
    rig.set_rotation("hand2", x=8.0, z=12.0)
    rig.set_rotation("fingers", z=6.0 + breath * 1.5)
    rig.set_rotation("fingers2", z=-6.0 - breath * 1.5)


def _sono_deitado(rig: Rig, breath: float) -> None:
    # Deitado no chão de lado: corpo unificado e relaxado
    rig.set_rotation("body", x=2.0 + breath * 0.5)
    rig.set_rotation("cintura", x=1.0)
    rig.set_rotation("abdomen", x=1.0)
    rig.set_rotation("peitoral", x=1.0)
    rig.set_rotation("head", x=6.0 + breath * 0.6, y=-5.0)
    # Pernas encolhidas suavemente em repouso
    rig.set_rotation("coxa-direita", y=10.0)
    rig.set_rotation("coxa-esquerda", y=8.0)
    # Braços aconchegados na frente do peito/rosto como travesseiro
    rig.set_rotation("right-arm", x=-20.0, y=-10.0, z=50.0)
    rig.set_rotation("left-arm", x=-25.0, y=10.0, z=-45.0)
    rig.set_rotation("ant-arm", z=45.0)
    rig.set_rotation("ant-arm2", z=-45.0)
    rig.set_rotation("hand", z=8.0)
    rig.set_rotation("hand2", z=-8.0)
    rig.set_rotation("fingers", z=8.0)
    rig.set_rotation("fingers2", z=-8.0)


def pose_sleep(rig: Rig, t: float, modo: str = "em_pe", entrada: float = 3.0) -> None:
    """Aplica a pose de sono com respiração lenta nos 3 modos."""
    breath = sin(t * 0.75)

    if modo == "sentado":
        _sono_sentado(rig, breath, entrada)
        return

    if modo == "deitado":
        _sono_deitado(rig, breath)
        return

    rig.set_rotation("body", x=1.5 + breath * 0.6, z=-2.0)
    rig.set_rotation("head", x=12.0 + breath * 0.8, y=4.0)

    # IK: braços relaxados, mãos recolhidas junto ao corpo (alvo de sono).
    sleep_r = braco_hpr_graus("right", "sleep")
    sleep_l = braco_hpr_graus("left", "sleep")
    rb, re = sleep_r["right-arm"], sleep_r["ant-arm"]
    lb, le = sleep_l["left-arm"], sleep_l["ant-arm2"]
    rig.set_rotation("right-arm", x=rb[0] + 10.0, y=rb[1], z=rb[2])
    rig.set_rotation("left-arm", x=lb[0] + 10.0, y=lb[1], z=lb[2])
    rig.set_rotation("ant-arm", x=re[0] + 8.0, y=re[1], z=re[2])
    rig.set_rotation("ant-arm2", x=le[0] + 8.0, y=le[1], z=le[2])

    # Shoulder compensation (minimal since ant-arms are static)
    rig.set_rotation("shoulder", x=1.2)
    rig.set_rotation("shoulder2", x=-1.2)

    # Fingers: relaxed curl
    rig.set_rotation("fingers", z=15.0 + breath * 2.0)
    rig.set_rotation("fingers2", z=-15.0 - breath * 2.0)


def _pose_aereo_bracos(
    rig: Rig, t: float, settle: float, descent: float, drift: float, air_sway: float, air_flutter: float
) -> None:
    thr_r = braco_hpr_graus("right", "thrown")
    thr_l = braco_hpr_graus("left", "thrown")
    rb, re = thr_r["right-arm"], thr_r["ant-arm"]
    lb, le = thr_l["left-arm"], thr_l["ant-arm2"]
    rig.set_rotation("right-arm", x=rb[0] - 12.0 + 9.0 * descent, y=rb[1], z=rb[2] + 12.0 * descent + drift * 9.0 + air_sway * 8.0)
    rig.set_rotation("left-arm", x=lb[0] - 9.0 + 7.0 * descent, y=lb[1], z=lb[2] - 12.0 * descent + drift * 5.0 - air_sway * 9.0)
    rig.set_rotation("ant-arm", x=re[0] - 20.0 + 9.0 * descent, y=re[1], z=re[2] + 14.0 * descent - air_flutter * 7.0)
    rig.set_rotation("ant-arm2", x=le[0] - 15.0 + 6.0 * descent, y=le[1], z=le[2] - 14.0 * descent + air_flutter * 6.0)
    rig.set_rotation("hand", x=9.0 * settle - 5.0 * descent, y=drift * 3.0, z=-18.0 + drift * 5.0 - air_sway * 5.0)
    rig.set_rotation("hand2", x=6.0 * settle - 3.0 * descent, y=-drift * 2.0, z=14.0 - drift * 3.0 + air_sway * 4.0)
    rig.set_rotation("fingers", z=-10.0 + sin(t * 4.5) * 3.0)
    rig.set_rotation("fingers2", z=10.0 - sin(t * 4.5 + 0.6) * 3.0)


def pose_thrown(rig: Rig, t: float = 0.0, velocity=(0.0, 450.0)) -> None:
    """Aplica silhueta aérea responsiva (subida/queda) com balanço de membros."""
    descent = 0.5 + 0.5 * tanh(velocity[1] / 280.0)
    drift = tanh(velocity[0] / 580.0)
    settle = 1.0 - exp(-max(0, t) * 7.5)
    air_sway = sin(t * 3.8) * (0.60 + 0.40 * descent) * settle
    air_flutter = sin(t * 6.4 + 0.9) * (0.40 + 0.60 * descent) * settle
    # Coluna e cintura arqueiam na subida e compensam na descida sem esmagar o tronco.
    rig.set_rotation("body", x=-7.0 + 13.0 * descent, z=-drift * 10.0 + air_sway * 2.4)
    rig.set_rotation("cintura", x=-2.5 + 4.5 * descent, z=air_sway * 1.8)
    rig.set_rotation("abdomen", x=-2.0 + 3.8 * descent, z=-air_sway * 1.4)
    rig.set_rotation("peitoral", x=-2.0 + 3.0 * descent, z=-air_sway * 2.0)
    rig.set_rotation("head", x=-8.0 + 14.0 * descent, y=-drift * 10.0, z=drift * 5.0 - air_sway * 2.6)
    rig.set_rotation("fones", z=-air_sway * 3.0)
    rig.set_rotation("antena-direita", x=10.0 * descent, z=6.0 * air_flutter)
    rig.set_rotation("antena-esquerda", x=10.0 * descent, z=-6.0 * air_flutter)
    _pose_aereo_bracos(rig, t, settle, descent, drift, air_sway, air_flutter)
    rig.set_rotation("legs", x=-8.0 + 12.0 * descent + air_flutter * 3.5, z=drift * 5.0)
    rig.set_rotation("left-feet", x=-8.0 - 13.0 * descent + 4.0 * drift + air_flutter * 6.0)
    rig.set_rotation("right-feet", x=5.0 - 9.0 * descent - 4.0 * drift - air_flutter * 6.0)


@dataclass(frozen=True, slots=True)
class _BaseBracos:
    """Base (P, H, R) do ombro e do cotovelo dos dois braços, em graus."""

    rbx: float
    rby: float
    right_base: float
    rex: float
    right_elbow: float
    lbx: float
    lby: float
    left_base: float
    lex: float
    left_elbow: float


def _ler_base_atual(rig: Rig) -> _BaseBracos:
    """Lê a base dos braços da pose atual do rig (usada pelo hover)."""

    def _graus(grupo: str) -> tuple[float, float, float]:
        rot = rig.current[grupo]
        return degrees(rot.x), degrees(rot.y), degrees(rot.z)

    rbx, rby, right_base = _graus("right-arm")
    lbx, lby, left_base = _graus("left-arm")
    rex, _rey, right_elbow = _graus("ant-arm")
    lex, _ley, left_elbow = _graus("ant-arm2")
    return _BaseBracos(
        rbx, rby, right_base, rex, right_elbow, lbx, lby, left_base, lex, left_elbow
    )


def _ler_base_alvo(inter_r: dict, inter_l: dict) -> _BaseBracos:
    """Lê a base dos braços do ALVO de interação resolvido por IK."""
    rbx, rby, right_base = inter_r["right-arm"]
    lbx, lby, left_base = inter_l["left-arm"]
    rex, _rey, right_elbow = inter_r["ant-arm"]
    lex, _ley, left_elbow = inter_l["ant-arm2"]
    return _BaseBracos(
        rbx, rby, right_base, rex, right_elbow, lbx, lby, left_base, lex, left_elbow
    )


def _interacao_hover(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Estende um braço, de leve, na direção do cursor."""
    right_reach = max(0.0, -direction) ** 1.3
    left_reach = max(0.0, direction) ** 1.3
    down = max(0.0, vertical)
    up = max(0.0, -vertical)
    rig.set_rotation(
        "right-arm",
        x=b.rbx - 3.0 - up * 10.0,
        y=b.rby,
        z=b.right_base - 40.0 * right_reach - 18.0 * up + 10.0 * down,
    )
    rig.set_rotation(
        "left-arm",
        x=b.lbx - 3.0 - up * 10.0,
        y=b.lby,
        z=b.left_base + 40.0 * left_reach + 18.0 * up - 10.0 * down,
    )
    rig.set_rotation(
        "ant-arm",
        x=b.rex - 5.0 - up * 12.0,
        z=b.right_elbow + 54.0 * right_reach + 14.0 * up,
    )
    rig.set_rotation(
        "ant-arm2",
        x=b.lex - 5.0 - up * 12.0,
        z=b.left_elbow - 54.0 * left_reach - 14.0 * up,
    )
    rig.set_rotation("hand", z=-5.0 * right_reach)
    rig.set_rotation("hand2", z=5.0 * left_reach)
    rig.set_rotation("fingers", z=-5.0 * right_reach)
    rig.set_rotation("fingers2", z=5.0 * left_reach)
    rig.set_rotation("door", y=20.0)


def _amostrar_escalar(chaves: list[tuple[float, float]] | tuple[tuple[float, float], ...], tempo: float) -> float:
    """Amostra uma pista escalar quíntica delegando para ``amostrar_pista``."""
    return amostrar_pista(tuple((at, (valor, 0.0, 0.0)) for at, valor in chaves), tempo)[0]


def _interacao_click(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Reação de clique com antecipação, estalo e follow-through na coluna e antenas."""
    u = min(1.0, max(0.0, t / 0.55))
    # Antecipação curta (afunda antes de virar) + ataque rápido + retorno macio
    carga = _amostrar_escalar([(0.0, 0.0), (0.14, 1.0), (0.34, -0.25), (1.0, 0.0)], u)
    ataque = _amostrar_escalar([(0.0, 0.0), (0.12, 0.0), (0.32, 1.05), (0.58, 0.92), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.20, 0.0), (0.45, 1.0), (1.0, 0.0)], u)
    porta = _amostrar_escalar([(0.0, 0.0), (0.14, 28.0), (0.38, 12.0), (0.62, 20.0), (1.0, 0.0)], u)

    rig.set_rotation("cintura", x=4.0 * carga - 3.0 * ataque, y=direction * 6.0 * ataque)
    rig.set_rotation("abdomen", x=3.5 * carga - 2.5 * ataque, y=direction * 5.0 * ataque)
    rig.set_rotation("peitoral", x=-4.0 * ataque, z=direction * 4.5 * ataque)
    rig.set_rotation("head", x=6.0 * carga - 5.0 * ataque, y=direction * 35.0 * (0.3 + 0.7 * ataque), z=8.0 * ataque)
    rig.set_rotation("door", y=porta)
    rig.set_rotation("fones", x=-6.0 * atraso, z=direction * 5.0 * atraso)
    rig.set_rotation("antena-direita", x=-10.0 * atraso, z=6.0 * atraso)
    rig.set_rotation("antena-esquerda", x=-10.0 * atraso, z=-6.0 * atraso)
    rig.set_rotation("hand", x=-12.0 * atraso, y=8.0 * atraso)
    rig.set_rotation("hand2", x=-12.0 * atraso, y=-8.0 * atraso)


def _interacao_double_click(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Recua e estica o braço direito no clique duplo."""

    def track(*keys):
        return amostrar_pista(tuple((at, (value, 0, 0)) for at, value in keys), t)[0]

    recoil = track((0, 0), (0.18, 5), (0.42, -7), (0.75, 2), (1.4, 0))
    reach = track((0, 0), (0.18, -4), (0.44, 1), (0.65, 1), (1.4, 0))
    extension = track((0, 0), (0.20, -6), (0.48, -48), (0.72, -42), (1.4, 0))
    rig.set_rotation("body", x=recoil, y=-direction * reach)
    rig.set_rotation("head", x=-recoil * 0.65, y=direction * 15, z=-recoil * 0.4)
    rig.set_rotation(
        "right-arm",
        x=b.rbx - abs(extension) * 0.2,
        y=b.rby,
        z=b.right_base + extension,
    )
    rig.set_rotation(
        "ant-arm", x=b.rex + extension * 0.4, z=b.right_elbow + extension * 0.3
    )
    rig.set_rotation("hand", x=-recoil, z=-extension * 0.2)
    curl = track((0, 0), (0.18, 20), (0.43, -10), (0.8, 4), (1.4, 0))
    rig.set_rotation("fingers", z=curl)
    rig.set_rotation("door", y=max(0, -recoil) * 3)


def _interacao_pet(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Inclina coluna e cabeça no carinho com balanço orgânico e follow-through."""
    u = min(1.0, max(0.0, t / 1.55))
    env = _amostrar_escalar([(0.0, 0.0), (0.20, 1.0), (0.74, 0.96), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.28, 1.0), (0.82, 0.95), (1.0, 0.0)], u)
    embalo = sin(t * 7.5) * env

    rig.set_rotation("cintura", x=-4.0 * env, z=direction * 4.0 * env + 2.0 * embalo)
    rig.set_rotation("abdomen", x=-4.5 * env, z=direction * 3.5 * env + 1.8 * embalo)
    rig.set_rotation("peitoral", x=-3.5 * env, z=direction * 3.0 * env)
    rig.set_rotation("head", x=-12.0 * env, y=direction * 25.0 * (0.4 + 0.6 * env), z=9.0 * env + 3.0 * embalo)
    rig.set_rotation("body", z=direction * 5.0 * env)
    rig.set_rotation("door", y=env * (18.0 + 3.5 * sin(t * 14.0)))
    rig.set_rotation("fones", z=direction * 4.5 * atraso + 2.5 * embalo)
    rig.set_rotation("antena-direita", x=5.0 * atraso, z=4.0 * embalo)
    rig.set_rotation("antena-esquerda", x=5.0 * atraso, z=4.0 * embalo)


def _interacao_poke(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Delega a cutucada ao gesto de reação."""
    aplicar_cutucar(rig, t, (b.rbx, b.rby, b.right_base), (b.rex, b.right_elbow))


def _interacao_land(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Amortece a aterrissagem com impacto profundo, braços em contrapeso e rebote."""
    u = min(1.0, max(0.0, t / 0.50))
    # Ataque rápido ao tocar o chão (~18% = 90ms) seguido de rebote elástico.
    impacto = _amostrar_escalar([(0.0, 0.28), (0.18, 1.0), (0.50, -0.22), (0.78, 0.08), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.28, 1.0), (0.64, -0.26), (1.0, 0.0)], u)

    rep_r = braco_hpr_graus("right", "idle")
    rep_l = braco_hpr_graus("left", "idle")
    rb, re = rep_r["right-arm"], rep_r["ant-arm"]
    lb, le = rep_l["left-arm"], rep_l["ant-arm2"]

    rig.set_rotation("body", x=9.0 * impacto, y=direction * 5.0 * impacto)
    rig.set_rotation("cintura", x=6.0 * impacto)
    rig.set_rotation("abdomen", x=5.0 * impacto)
    rig.set_rotation("peitoral", x=4.0 * impacto)
    rig.set_rotation("legs", x=-10.0 * impacto)
    rig.set_rotation("head", x=14.0 * atraso, y=direction * 10.0 * atraso)
    rig.set_rotation("door", y=max(0.0, 26.0 * impacto))
    rig.set_rotation("fones", x=10.0 * atraso)
    rig.set_rotation("antena-direita", x=18.0 * atraso, z=6.0 * atraso)
    rig.set_rotation("antena-esquerda", x=18.0 * atraso, z=-6.0 * atraso)
    # Braços abrem para equilibrar o impacto e descem para repouso no rebote.
    rig.set_rotation("right-arm", x=rb[0] + 8.0 * impacto, y=rb[1] - 18.0 * impacto, z=rb[2] - 24.0 * impacto)
    rig.set_rotation("left-arm", x=lb[0] + 8.0 * impacto, y=lb[1] + 18.0 * impacto, z=lb[2] + 24.0 * impacto)
    rig.set_rotation("ant-arm", x=re[0], y=re[1], z=re[2] + 16.0 * impacto)
    rig.set_rotation("ant-arm2", x=le[0], y=le[1], z=le[2] - 16.0 * impacto)
    rig.set_rotation("hand", x=18.0 * atraso, z=-8.0 * impacto)
    rig.set_rotation("hand2", x=18.0 * atraso, z=8.0 * impacto)


def _interacao_wake(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Acorda: encolhimento inicial, espreguiçar profundo com coluna em onda e retorno macio."""
    u = min(1.0, max(0.0, t / 1.25))
    encolhe = _amostrar_escalar([(0.0, 0.0), (0.14, 1.0), (0.30, 0.0), (1.0, 0.0)], u)
    estica = _amostrar_escalar([(0.0, 0.0), (0.16, 0.0), (0.48, 1.0), (0.72, 0.90), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.24, 0.0), (0.58, 1.0), (1.0, 0.0)], u)
    tremor = sin(t * 11.0) * 4.0 * estica

    rig.set_rotation("cintura", x=4.0 * encolhe - 5.0 * estica)
    rig.set_rotation("abdomen", x=4.0 * encolhe - 5.5 * estica)
    rig.set_rotation("peitoral", x=3.5 * encolhe - 6.0 * estica)
    rig.set_rotation("body", x=3.0 * encolhe - 6.0 * estica)
    rig.set_rotation("head", x=6.0 * encolhe - 11.0 * estica, y=tremor)
    rig.set_rotation("door", y=45.0 * estica)
    rig.set_rotation("fones", x=-6.0 * atraso, z=tremor * 0.6)
    rig.set_rotation("antena-direita", x=-10.0 * atraso)
    rig.set_rotation("antena-esquerda", x=-10.0 * atraso)
    # Parte dos braços baixados (idle) e os ergue ao espreguiçar.
    # Medido no grafo de cena: elevação = eixo do nó ROLL (Z); z NEGATIVO ergue.
    wake_r = braco_hpr_graus("right", "idle")["right-arm"]
    wake_l = braco_hpr_graus("left", "idle")["left-arm"]
    rig.set_rotation(
        "right-arm",
        x=wake_r[0],
        y=wake_r[1],
        z=wake_r[2] - WAKE_BRACO_ELEVACAO * estica,
    )
    rig.set_rotation(
        "left-arm",
        x=wake_l[0],
        y=wake_l[1],
        z=wake_l[2] + WAKE_BRACO_ELEVACAO * estica,
    )
    # Compensação do ombro enquanto os braços sobem.
    shoulder_comp = -45.0 * estica * 0.15
    rig.set_rotation("shoulder", x=shoulder_comp)
    rig.set_rotation("shoulder2", x=-shoulder_comp)


def _interacao_surprise(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Susto: micro-encolhimento, recuo instantâneo com guarda e follow-through."""
    u = min(1.0, max(0.0, t / 0.72))
    encolhe = _amostrar_escalar([(0.0, 0.0), (0.07, 1.0), (0.18, 0.0), (1.0, 0.0)], u)
    susto = _amostrar_escalar([(0.0, 0.0), (0.06, 0.0), (0.22, 1.05), (0.55, 0.72), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.12, 0.0), (0.34, 1.0), (1.0, 0.0)], u)

    rig.set_rotation("cintura", x=4.0 * encolhe - 5.0 * susto, y=direction * 5.0 * susto)
    rig.set_rotation("abdomen", x=3.5 * encolhe - 5.0 * susto)
    rig.set_rotation("peitoral", x=-6.0 * susto, y=direction * 4.0 * susto)
    rig.set_rotation(
        "body",
        x=3.0 * encolhe - SURPRESA_RECUO * susto,
        y=direction * SURPRESA_GIRO * susto,
    )
    rig.set_rotation(
        "head",
        x=-max(-1.0, min(1.0, vertical)) * 26.0 - SURPRESA_CABECA * susto,
        y=direction * 40.0,
    )
    rig.set_rotation("door", y=34.0 * susto)
    rig.set_rotation("fones", x=-8.0 * atraso)
    rig.set_rotation("antena-direita", x=-14.0 * atraso, z=-6.0 * atraso)
    rig.set_rotation("antena-esquerda", x=-14.0 * atraso, z=6.0 * atraso)
    surp_r = braco_hpr_graus("right", "idle")["right-arm"]
    surp_l = braco_hpr_graus("left", "idle")["left-arm"]
    rig.set_rotation(
        "right-arm",
        x=surp_r[0],
        y=surp_r[1],
        z=surp_r[2] - SURPRESA_BRACO * susto,
    )
    rig.set_rotation(
        "left-arm",
        x=surp_l[0],
        y=surp_l[1],
        z=surp_l[2] + SURPRESA_BRACO * susto,
    )


_REACOES_INTERACAO = {
    "hover": _interacao_hover,
    "click": _interacao_click,
    "double_click": _interacao_double_click,
    "pet": _interacao_pet,
    "poke": _interacao_poke,
    "land": _interacao_land,
    "wake": _interacao_wake,
    "surprise": _interacao_surprise,
}


def pose_interaction(
    rig: Rig, kind: str, t: float, direction: float = 0.0, vertical: float = 0.0
) -> None:
    """Aplica as reações procedurais: porta gira na dobradiça, sem escala da malha.

    Um ``kind`` desconhecido aplica só a base dos braços e o olhar da cabeça.
    """
    direction = max(-1.0, min(1.0, direction))
    # Braços junto ao corpo nas reações. O hover parte da pose idle atual para
    # um alcance pequeno e direcional; as demais partem do ALVO de interação
    # (mãos à frente) resolvido por IK. A torção do IK escolhe o plano do
    # cotovelo, então a base (P, H, R) completa não pode ser descartada.
    inter_r = braco_hpr_graus("right", "idle" if kind == "land" else "interaction")
    inter_l = braco_hpr_graus("left", "idle" if kind == "land" else "interaction")
    b = _ler_base_atual(rig) if kind == "hover" else _ler_base_alvo(inter_r, inter_l)
    rig.set_rotation("right-arm", x=b.rbx, y=b.rby, z=b.right_base)
    rig.set_rotation("left-arm", x=b.lbx, y=b.lby, z=b.left_base)
    rig.set_rotation("ant-arm", x=b.rex, z=b.right_elbow)
    rig.set_rotation("ant-arm2", x=b.lex, z=b.left_elbow)
    rig.set_rotation(
        "head", x=-max(-1.0, min(1.0, vertical)) * 26.0, y=direction * 40.0
    )
    reacao = _REACOES_INTERACAO.get(kind)
    if reacao is not None:
        reacao(rig, t, direction, vertical, b)


def pose_flourish(rig: Rig, kind: str, t: float) -> None:
    """Aplica aceno, alongamento, espiada e recuperação de impacto."""
    if kind in ("wave", "stretch"):
        (aplicar_aceno if kind == "wave" else aplicar_alongar)(rig, t)
        return
    durations = {"peek": 9.0, "hit": 0.65}
    phase = min(1.0, max(0.0, t / durations[kind]))
    envelope = sin(phase * pi)
    # Default dos braços: repouso baixado (IK do alvo idle).
    repouso_fl = {
        **braco_hpr_graus("right", "idle"),
        **braco_hpr_graus("left", "idle"),
    }
    fl_r, fl_l = repouso_fl["right-arm"], repouso_fl["left-arm"]
    rig.set_rotation("right-arm", x=fl_r[0], y=fl_r[1], z=fl_r[2])
    rig.set_rotation("left-arm", x=fl_l[0], y=fl_l[1], z=fl_l[2])
    if kind == "peek":
        rig.set_rotation("head", y=sin(t * 2) * 12 * envelope, z=5 * envelope)
        rig.set_rotation("ant-arm", x=-12 * envelope)
        rig.set_rotation("ant-arm2", x=-12 * envelope)
        # Compensação do ombro na espiada.
        shoulder_comp = -12 * envelope * 0.15
        rig.set_rotation("shoulder", x=shoulder_comp)
        rig.set_rotation("shoulder2", x=-shoulder_comp)
    else:
        recoil = sin(t * 18) * (1 - phase) ** 2
        rig.set_rotation("body", x=-15 * envelope, z=recoil * 10)
        rig.set_rotation("head", x=-18 * envelope, z=-recoil * 12)
        rig.set_rotation("door", y=40 * envelope)


def _espirro_bracos(rig: Rig, inhale: float, hit: float) -> None:
    """Ergue os braços à frente a partir do repouso baixado (IK).

    Medido no grafo de cena: elevação = eixo do nó ROLL (Z); z NEGATIVO ergue.
    """
    sz_r = braco_hpr_graus("right", "idle")["right-arm"]
    sz_l = braco_hpr_graus("left", "idle")["left-arm"]
    sze = {**braco_hpr_graus("right", "idle"), **braco_hpr_graus("left", "idle")}
    sze_r, sze_l = sze["ant-arm"][2], sze["ant-arm2"][2]
    rig.set_rotation(
        "right-arm",
        x=sz_r[0] - 12 * inhale - 48 * hit,
        y=sz_r[1],
        z=sz_r[2] - 40 - 12 * inhale,
    )
    rig.set_rotation(
        "left-arm",
        x=sz_l[0] - 10 * inhale - 44 * hit,
        y=sz_l[1],
        z=sz_l[2] + 40 + 10 * inhale,
    )
    # Cotovelos DOBRAM (o sinal antigo pedia hiperextensão).
    rig.set_rotation("ant-arm", x=-12 * inhale - 18 * hit, z=sze_r + 20 + 20 * inhale)
    rig.set_rotation("ant-arm2", x=-10 * inhale - 16 * hit, z=sze_l - 20 - 18 * inhale)


def _espirro_esfregar(rig: Rig, t: float) -> None:
    """Esfrega a frente do armário fechado e baixa a mão devagar."""
    rub = max(0.0, min(1.0, (t - 7.7) / 0.3, (8.8 - t) / 0.5))
    stroke = sin(t * 12) * rub
    if not rub:
        return
    alvo = braco_hpr_graus("right", "limpar_porta")
    for nome, (x, y, z) in alvo.items():
        base = rig.current[nome]
        rig.set_rotation(
            nome,
            x=degrees(base.x) * (1 - rub) + x * rub,
            y=degrees(base.y) * (1 - rub) + y * rub,
            z=degrees(base.z) * (1 - rub) + z * rub + 3 * stroke,
        )
    rig.set_rotation("hand", x=17 * rub + 8 * stroke, y=3 * stroke, z=5 * stroke)
    rig.set_rotation("fingers", z=-8 * rub)
    rig.set_rotation("head", x=3 * rub, z=-2 * rub)


def pose_sneeze(rig: Rig, t: float) -> None:
    """Aplica três inspirações, contração para baixo e recuperação amortecida."""
    # Inspiração lenta, antecipação segurada e um espirro seco para a frente.
    inhale = min(1.0, max(0.0, t / 3.3))
    inhale = inhale * inhale * (3 - 2 * inhale)
    if t >= 3.6:
        inhale *= exp(-(t - 3.6) * 12)
    inhale += sum(
        amp * exp(-(((t - at) / width) ** 2))
        for at, width, amp in (
            (0.65, 0.24, 0.25),
            (1.65, 0.32, 0.35),
            (2.85, 0.4, 0.45),
        )
    )
    hit = exp(-(((t - 3.68) / 0.105) ** 2))
    settle = sin(max(0, t - 3.8) * 8) * exp(-max(0, t - 3.8) * 4) if t > 3.8 else 0
    rig.set_rotation("head", x=-10 * inhale - 42 * hit - 5 * settle, z=-3 * inhale)
    rig.set_rotation("body", x=-5 * inhale - 22 * hit - 3 * settle)
    _espirro_bracos(rig, inhale, hit)
    rig.set_rotation("hand", x=15 * hit, z=-8 * inhale)
    rig.set_rotation("hand2", x=12 * hit, z=8 * inhale)
    rig.set_rotation("fingers", z=18 * inhale - 10 * hit)
    rig.set_rotation("fingers2", z=-18 * inhale + 10 * hit)
    rig.set_rotation("door", y=120 * hit)
    _espirro_esfregar(rig, t)


def _aplicar_braco_hpr(
    rig: Rig, lado: str, nome_alvo: str, *, dx: float = 0.0, dz: float = 0.0
) -> None:
    """Aplica ``braco_hpr_graus`` num braço com ajuste fino opcional de pitch/roll."""
    hpr = braco_hpr_graus(lado, nome_alvo)
    arm_key = "right-arm" if lado == "right" else "left-arm"
    for grupo, (x, y, z) in hpr.items():
        if grupo == arm_key:
            rig.set_rotation(grupo, x=x + dx, y=y, z=z + dz)
        else:
            rig.set_rotation(grupo, x=x, y=y, z=z)


def pose_virtual_insanity(rig: Rig, t: float, direction: float = 1.0) -> None:
    """Pose Jamiroquai (Virtual Insanity): deslize plantado e mão aberta para a câmera."""
    dir_sinal = 1.0 if direction >= 0.0 else -1.0
    balanco = sin(t * 2.2)
    groove = cos(t * 4.4)
    # Tronco angulado em 3/4 mantendo ombro dianteiro voltado à lente.
    rig.set_rotation("cintura", x=3.0, y=-6.0 * dir_sinal, z=-2.0 * dir_sinal)
    rig.set_rotation("abdomen", x=-4.0)
    rig.set_rotation("peitoral", x=-6.0, y=6.0 * dir_sinal)
    rig.set_rotation("body", x=-7.0 + groove * 1.2, y=24.0 * dir_sinal)
    # Queixo levemente abaixado encarando a câmera apesar da guinada do corpo.
    rig.set_rotation(
        "head",
        x=-11.0 + balanco * 1.5,
        y=-20.0 * dir_sinal,
        z=-3.5 * dir_sinal,
    )
    frente_right = dir_sinal >= 0.0
    lado_frente = "right" if frente_right else "left"
    lado_atras = "left" if frente_right else "right"
    sinal_frente = 1.0 if frente_right else -1.0
    _aplicar_braco_hpr(rig, lado_frente, "virtual_alcance", dx=balanco * 2.2)
    _aplicar_braco_hpr(rig, lado_atras, "virtual_apoio", dz=sinal_frente * balanco * 3.0)
    mao_frente = "hand" if frente_right else "hand2"
    mao_atras = "hand2" if frente_right else "hand"
    dedos_frente = "fingers" if frente_right else "fingers2"
    dedos_atras = "fingers2" if frente_right else "fingers"
    # Palma espalmada apontada direto para a câmera; mão de trás solta no quadril.
    rig.set_rotation(mao_frente, x=32.0 + balanco * 3.0, z=sinal_frente * 12.0)
    rig.set_rotation(mao_atras, x=-10.0, z=-sinal_frente * 8.0)
    rig.set_rotation(dedos_frente, z=-sinal_frente * 14.0)
    rig.set_rotation(dedos_atras, z=sinal_frente * 4.0)


def pose_blue_balls(rig: Rig, t: float) -> None:
    """FNF Blue Balls: choque elétrico breve seguido de dobra agarrando o quadril."""
    shock = max(0.0, 1.0 - max(0.0, t - 0.22) / 0.14)
    u = max(0.0, min(1.0, (t - 0.16) / 0.20))
    clutch = u * u * (3.0 - 2.0 * u)
    tremor = sin(t * 56.0) * shock
    pulse = sin(max(0.0, t - 0.40) * 9.0) * exp(-max(0.0, t - 0.40) * 0.55)

    # Sem deitar para trás: choque arqueia, depois dobra violentamente em pé sem esconder o rosto.
    rig.set_rotation("cintura", x=6.0 * clutch - 4.0 * shock)
    rig.set_rotation("abdomen", x=-8.0 * clutch + 4.0 * shock)
    rig.set_rotation("peitoral", x=-9.0 * clutch + 5.0 * shock)
    rig.set_rotation(
        "body",
        x=16.0 * shock - 22.0 * clutch - 4.0 * pulse + tremor * 4.5,
        z=tremor * 3.5,
    )
    rig.set_rotation(
        "head",
        x=24.0 * shock - 14.0 * clutch + 3.0 * pulse - tremor * 5.0,
        z=sin(t * 16.0) * 4.0 * clutch * exp(-max(0.0, t - 0.42) * 1.3) + tremor * 6.0,
    )
    for lado, mao, dedos, sinal in (
        ("right", "hand", "fingers", 1.0),
        ("left", "hand2", "fingers2", -1.0),
    ):
        fall_hpr = braco_hpr_graus(lado, "fall")
        clutch_hpr = braco_hpr_graus(lado, "blue_balls_clutch")
        for grupo, (fx, fy, fz) in fall_hpr.items():
            cx, cy, cz = clutch_hpr[grupo]
            rig.set_rotation(
                grupo,
                x=fx * (1.0 - clutch) + cx * clutch,
                y=fy * (1.0 - clutch) + cy * clutch,
                z=fz * (1.0 - clutch) + cz * clutch,
            )
        rig.set_rotation(
            mao,
            x=-22.0 * clutch + 12.0 * shock + sin(t * 24.0) * 2.5 * clutch,
            z=sinal * (6.0 * shock - 8.0 * clutch),
        )
        rig.set_rotation(dedos, z=sinal * (14.0 * clutch - 8.0 * shock))


#: Escala do balanço da mão por estado (``pose_secondary``); 1.5 nos demais.
_BALANCO_MAO_POR_ESTADO = {
    "idle": 2.2,
    "hover": 1.8,
    "walk": 5.0,
    "run": 6.5,
    "drag": 1.0,
    "fall": 5.5,
    "dance": 7.0,
    "wave": 0.7,
    "stretch": 1.0,
    "peek": 1.5,
    "hit": 0.4,
    "click": 1.0,
    "double_click": 1.2,
    "virtual_insanity": 0.8,
    "blue_balls": 0.4,
    "pet": 1.0,
    "poke": 0.8,
    "wake": 1.0,
    "land": 0.8,
}
_LADOS_SECUNDARIO = (
    ("ant-arm", "shoulder", "hand", "fingers", 1),
    ("ant-arm2", "shoulder2", "hand2", "fingers2", -1),
)


def _gesto_idle_mao(
    t: float, state: str, personality: IdlePersonality, side: int, curl: float
) -> tuple[float, float]:
    """Devolve ``(curl, idle_wrist)`` com o gesto de mão do temperamento idle."""
    idle_wrist = 0.0
    if state != "idle":
        return curl, idle_wrist
    if personality == IdlePersonality.CURIOUS and side == 1:
        reach = _idle_pulse(t, 7.8, 0.65, 0.55, 0.9, offset=1.0)
        idle_wrist += 15.0 * reach
        curl -= 5.0 * reach
    elif personality == IdlePersonality.PLAYFUL and side == 1:
        flick = _idle_pulse(t, 4.8, 0.18, 0.08, 0.35, offset=0.7)
        idle_wrist += 10.0 * flick
        curl -= 8.0 * flick
    elif personality == IdlePersonality.SHY:
        fidget = _idle_pulse(t, 6.2, 0.5, 0.2, 0.6, offset=side * 0.8)
        idle_wrist += side * 4.0 * fidget
    return curl, idle_wrist


def _curl_por_estado(t: float, state: str, side: int, curl: float) -> float:
    """Substitui o curl dos dedos nos estados com dedos próprios."""
    if state in ("open_hands", "close_fists", "blue_balls", "virtual_insanity"):
        return 0.0
    if state == "sleep":
        return 8 + sin(t * 0.6) * 0.7
    if state == "fall":
        # Dedos um pouco abertos na queda.
        return -5 + sin(t * 4.0) * 3.0
    if state in ("wave", "stretch", "peek", "hit"):
        # Dedos reativos durante os floreios.
        return 5 + sin(t * 1.3 + side) * 4.0
    return curl


def _secundario_lado(
    rig: Rig,
    t: float,
    state: str,
    personality: IdlePersonality,
    lado: tuple[str, str, str, str, int],
) -> None:
    """Aplica o follow-through de ombro, pulso e dedos de um lado."""
    forearm, shoulder, hand, fingers, side = lado
    arm = rig.current[forearm]
    authored_hand = rig.current[hand]
    authored_fingers = rig.current[fingers]
    rig.set_rotation(shoulder, x=max(-3, min(3, degrees(arm.x) * 0.12)))
    arm_roll = degrees(arm.z)
    if state in ("idle", "hover"):
        # Contrapesa o tronco com cotovelos atrasados, sem balanço rígido.
        rig.set_rotation(
            forearm,
            x=degrees(arm.x) + sin(t * 0.8 - side * 0.45) * 1.6,
            y=degrees(arm.y),
            z=arm_roll + side * sin(t * 0.8 - side * 0.6) * 2.4,
        )
    wrist_follow = max(-10.0, min(10.0, -arm_roll * 0.22))
    sway_scale = _BALANCO_MAO_POR_ESTADO.get(state, 1.5)
    hand_sway = sin(t * 0.58 - side * 0.35) * sway_scale
    wrist_pitch = -degrees(arm.x) * 0.24 + sin(t * 0.52 - side * 0.3) * 2.0
    rig.set_rotation(
        hand,
        x=degrees(authored_hand.x) + wrist_pitch,
        y=degrees(authored_hand.y),
        z=degrees(authored_hand.z) + wrist_follow + side * hand_sway,
    )
    if state == "drag":
        return
    amplitude = (
        7.0
        if personality in (IdlePersonality.CURIOUS, IdlePersonality.PLAYFUL)
        else 4.5
    )
    curl = 3 + sin(t * 0.62 - side * 0.3) * amplitude + wrist_follow * 0.3
    curl, idle_wrist = _gesto_idle_mao(t, state, personality, side, curl)
    curl = _curl_por_estado(t, state, side, curl)
    rig.set_rotation(
        hand,
        x=degrees(authored_hand.x) + wrist_pitch,
        y=degrees(authored_hand.y),
        z=degrees(authored_hand.z) + wrist_follow + side * hand_sway + idle_wrist,
    )
    rig.set_rotation(fingers, z=degrees(authored_fingers.z) + side * curl)


def pose_secondary(
    rig: Rig, t: float, state: str, personality=IdlePersonality.CALM
) -> None:
    """Aplica follow-through de ombro/pulso, micro-ruído e coluna distribuída."""
    for lado in _LADOS_SECUNDARIO:
        _secundario_lado(rig, t, state, personality, lado)
    _secundario_coluna_e_fones(rig, t, state)


def _secundario_fones(rig, t, micro, head_x, head_y, head_z):
    # Fones e antenas reagem com atraso/balanço secundário ao movimento da cabeça
    if "fones" in rig.current:
        r_fones = micro.get("fones")
        fx = degrees(r_fones.x) if r_fones else 0.0
        fy = degrees(r_fones.y) if r_fones else 0.0
        fz = degrees(r_fones.z) if r_fones else 0.0
        rig.set_rotation(
            "fones",
            x=-head_x * 0.08 + fx,
            y=-head_y * 0.05 + fy,
            z=-head_z * 0.10 + fz,
        )
    for lado_sinal, nome_fone, nome_antena in (
        (1.0, "fone-direito", "antena-direita"),
        (-1.0, "fone-esquerdo", "antena-esquerda"),
    ):
        if nome_fone in rig.current:
            rig.set_rotation(
                nome_fone,
                x=-head_x * 0.06,
                y=-head_y * 0.04,
                z=-head_z * 0.12 + lado_sinal * sin(t * 1.1) * 0.4,
            )
        if nome_antena in rig.current:
            r_ant = micro.get(nome_antena)
            ax = degrees(r_ant.x) if r_ant else 0.0
            ay = degrees(r_ant.y) if r_ant else 0.0
            az = degrees(r_ant.z) if r_ant else 0.0
            rig.set_rotation(
                nome_antena,
                x=-head_x * 0.22 + ax,
                y=-head_y * 0.15 + ay,
                z=-head_z * 0.28 + az,
            )


def _secundario_coluna_e_fones(rig: Rig, t: float, state: str) -> None:
    """Aplica micro-ruído orgânico e follow-through nos nós da coluna, fones e antenas."""
    escala_ruido = 1.0 if state in ("idle", "hover") else 0.45
    micro = delta_micro_ruido_idle(t, escala=escala_ruido)
    cabeca = rig.current.get("head")
    head_x = degrees(cabeca.x) if cabeca else 0.0
    head_y = degrees(cabeca.y) if cabeca else 0.0
    head_z = degrees(cabeca.z) if cabeca else 0.0

    # Micro-ruído orgânico na coluna sem multiplicar ``body`` em dobro.
    for nome in ("cintura", "abdomen", "peitoral"):
        atual = rig.current.get(nome)
        r_micro = micro.get(nome)
        if atual is not None and r_micro is not None:
            rig.set_rotation(
                nome,
                x=degrees(atual.x) + degrees(r_micro.x),
                y=degrees(atual.y) + degrees(r_micro.y),
                z=degrees(atual.z) + degrees(r_micro.z),
            )

    _secundario_fones(rig, t, micro, head_x, head_y, head_z)


def pose_throw_release(rig: Rig, t: float, grip: float = 0.5) -> None:
    """Solta a pegada, abre além do ponto e assenta em 0,9 s."""
    keys = [(0, 8 + 32 * max(0, min(1, grip))), (0.22, -22), (0.6, 7), (0.9, 3)]
    curl = keys[-1][1]
    for (a, x), (b, y) in pairwise(keys):
        if t <= b:
            u = max(0, (t - a) / (b - a))
            u = u * u * (3 - 2 * u)
            curl = x + (y - x) * u
            break
    rig.set_rotation("fingers", z=curl)
    rig.set_rotation("fingers2", z=-curl)

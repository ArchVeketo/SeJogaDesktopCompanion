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
from sejoga.animacao.interpolacao import amostrar_pista, amostrar_pista_continua, suavizar_quintico
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

    # Shoulder compensation: shoulder follows ~15% of ant-arm x rotation (sinal X idêntico nos dois lados)
    shoulder_comp = re[0] * 0.15
    rig.set_rotation("shoulder", x=shoulder_comp)
    rig.set_rotation("shoulder2", x=shoulder_comp)


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

    # Shoulder compensation (minimal since ant-arms are static; sinal X idêntico nos dois lados)
    rig.set_rotation("shoulder", x=1.2)
    rig.set_rotation("shoulder2", x=1.2)

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
    rig: Rig,
    t: float,
    direction: float,
    vertical: float,
    b: _BaseBracos,
    part: str = "body",
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
    """Amostra pista escalar de reação com spline C1 (sem parar em cada chave intermediária).

    Extremos (antecipação, pico de overshoot, assento) mantêm tangente zero para o
    contraste de timing ficar crisp; chaves intermediárias passam com velocidade
    contínua em vez de frear e reacelerar como na interpolação quíntica por trecho.
    """
    return amostrar_pista_continua(
        tuple((at, (valor, 0.0, 0.0)) for at, valor in chaves), tempo, padrao="catmull"
    )[0]


def _aplicar_bracos_click(
    rig: Rig,
    b: _BaseBracos,
    direction: float,
    carga: float,
    ataque: float,
    atraso: float,
) -> None:
    """Aplica reação assimétrica de clique nos ombros, braços, antebraços e mãos."""
    peso_r = 1.0 if direction <= 0.0 else 0.45
    peso_l = 1.0 if direction > 0.0 else 0.45
    lados = (
        ("shoulder", "right-arm", "ant-arm", "hand", "fingers", b.rbx, b.rby, b.right_base, b.rex, b.right_elbow, peso_r, 1.0),
        ("shoulder2", "left-arm", "ant-arm2", "hand2", "fingers2", b.lbx, b.lby, b.left_base, b.lex, b.left_elbow, peso_l, -1.0),
    )
    for sh, arm, ant, hand, fing, bx, by, bz, ex, ez, peso, sinal in lados:
        rig.set_rotation(sh, x=-3.0 * peso * ataque + 2.0 * carga, z=sinal * (4.5 * peso * ataque - 2.0 * carga))
        rig.set_rotation(arm, x=bx - 4.0 * peso * ataque, y=by + sinal * (12.0 * peso * ataque - 4.0 * carga), z=bz + sinal * (-14.0 * peso * ataque + 4.0 * carga))
        cotov = ez + sinal * (16.0 * peso * atraso - 3.0 * carga)
        rig.set_rotation(ant, x=ex, z=max(0.0, cotov) if sinal > 0 else min(0.0, cotov))
        rig.set_rotation(hand, x=-12.0 * atraso * peso, y=sinal * 8.0 * atraso * peso, z=-sinal * 8.0 * atraso * peso)
        rig.set_rotation(fing, z=sinal * (-10.0 * atraso * peso + 6.0 * carga))


def _interacao_click(
    rig: Rig,
    t: float,
    direction: float,
    vertical: float,
    b: _BaseBracos,
    part: str = "body",
) -> None:
    """Reação de clique com antecipação, estalo assimétrico nos braços e follow-through."""
    del part
    u = min(1.0, max(0.0, t / 0.50))
    # Antecipação curta + ataque rápido com micro-overshoot + assentamento suave (0 em u=0 e u=1).
    carga = _amostrar_escalar([(0.0, 0.0), (0.14, 1.0), (0.36, -0.22), (0.72, 0.06), (1.0, 0.0)], u)
    ataque = _amostrar_escalar([(0.0, 0.0), (0.12, 0.0), (0.34, 1.06), (0.60, 0.90), (0.84, -0.06), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.18, 0.0), (0.46, 1.05), (0.78, -0.08), (1.0, 0.0)], u)
    olhar = _amostrar_escalar([(0.0, 0.0), (0.16, 1.0), (0.70, 0.88), (1.0, 0.0)], u)
    porta = _amostrar_escalar([(0.0, 0.0), (0.16, 26.0), (0.40, 10.0), (0.66, 18.0), (1.0, 0.0)], u)

    rig.set_rotation("cintura", x=4.0 * carga - 3.0 * ataque, y=direction * 6.0 * ataque, z=-direction * 2.0 * carga)
    rig.set_rotation("abdomen", x=3.5 * carga - 2.5 * ataque, y=direction * 5.0 * ataque)
    rig.set_rotation("peitoral", x=-4.0 * ataque, y=direction * 4.0 * ataque, z=direction * 4.5 * ataque)
    rig.set_rotation("body", x=3.0 * carga - 2.5 * ataque, y=direction * 4.0 * ataque, z=direction * 2.5 * ataque)
    rig.set_rotation(
        "head",
        x=6.0 * carga - 5.0 * ataque - max(-1.0, min(1.0, vertical)) * 14.0 * olhar,
        y=direction * 34.0 * olhar,
        z=7.0 * direction * ataque,
    )
    rig.set_rotation("door", y=max(0.0, porta))
    rig.set_rotation("fones", x=-6.0 * atraso, z=direction * 5.0 * atraso)
    rig.set_rotation("antena-direita", x=-10.0 * atraso, z=6.0 * atraso)
    rig.set_rotation("antena-esquerda", x=-10.0 * atraso, z=-6.0 * atraso)
    _aplicar_bracos_click(rig, b, direction, carga, ataque, atraso)


def _zona_corpo(part: str | None) -> str:
    """Normaliza o identificador do picking para uma zona anatômica canônica."""
    nome = (part or "body").lower()
    if any(k in nome for k in ("head", "door", "fone", "antena")):
        return "head"
    if any(k in nome for k in ("arm", "hand", "shoulder", "finger")):
        return "arm"
    if "feet" in nome:
        return "feet"
    if "leg" in nome:
        return "legs"
    return "body"


def _lado_parte(part: str | None, fallback: float = 1.0) -> float:
    """Retorna +1 para lado esquerdo, -1 para direito ou ``fallback``."""
    nome = (part or "").lower()
    if "left" in nome or nome.endswith("2"):
        return 1.0
    if "right" in nome:
        return -1.0
    return fallback or 1.0


def _aplicar_bracos_tronco_dc(
    rig: Rig, b: _BaseBracos, recoil: float, extension: float, curl: float, atraso: float
) -> None:
    """Estocada do braço direito e contrapeso esquerdo no duplo clique no tronco."""
    rig.set_rotation("shoulder", x=-abs(extension) * 0.08, z=-extension * 0.08)
    rig.set_rotation("shoulder2", x=recoil * 0.25, z=recoil * 0.35)
    rig.set_rotation("right-arm", x=b.rbx - abs(extension) * 0.18, y=b.rby - extension * 0.35, z=b.right_base + extension)
    rig.set_rotation("left-arm", x=b.lbx, y=b.lby + 8.0 * atraso, z=b.left_base + 8.0 * atraso)
    rig.set_rotation("ant-arm", x=b.rex + extension * 0.25, z=max(0.0, b.right_elbow - extension * 0.25))
    rig.set_rotation("ant-arm2", x=b.lex, z=min(0.0, b.left_elbow - 6.0 * atraso))
    rig.set_rotation("hand", x=-recoil, z=-extension * 0.2)
    rig.set_rotation("hand2", x=-recoil * 0.6 * atraso, z=6.0 * atraso)
    rig.set_rotation("fingers", z=curl)
    rig.set_rotation("fingers2", z=-6.0 * atraso)


def _double_click_tronco(
    rig: Rig, t: float, direction: float, b: _BaseBracos
) -> None:
    """Reação clássica de duplo clique no tronco: cascata na coluna e estocada com o braço direito."""
    u = min(1.0, max(0.0, t / 1.4))

    def track(*keys):
        return amostrar_pista(tuple((at, (value, 0, 0)) for at, value in keys), t)[0]

    recoil = track((0.0, 0.0), (0.18, 5.0), (0.42, -7.0), (0.75, 2.0), (1.15, -0.8), (1.4, 0.0))
    reach = track((0.0, 0.0), (0.18, -4.0), (0.44, 1.0), (0.65, 1.0), (1.4, 0.0))
    extension = track((0.0, 0.0), (0.20, -6.0), (0.48, -44.0), (0.72, -38.0), (1.16, 3.0), (1.4, 0.0))
    curl = track((0.0, 0.0), (0.18, 20.0), (0.43, -10.0), (0.8, 4.0), (1.4, 0.0))
    olhar = _amostrar_escalar([(0.0, 0.0), (0.14, 1.0), (0.78, 0.85), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.22, 0.0), (0.48, 1.05), (0.82, -0.08), (1.0, 0.0)], u)

    rig.set_rotation("cintura", x=recoil * 0.35, y=-direction * reach * 0.4)
    rig.set_rotation("abdomen", x=recoil * 0.40, y=-direction * reach * 0.35)
    rig.set_rotation("peitoral", x=recoil * 0.50, y=-direction * reach * 0.5, z=-recoil * 0.25)
    rig.set_rotation("body", x=recoil * 0.65, y=-direction * reach)
    rig.set_rotation("head", x=-recoil * 0.65, y=direction * 16.0 * olhar, z=-recoil * 0.4)
    rig.set_rotation("fones", x=recoil * 0.45 * atraso, z=-recoil * 0.25)
    rig.set_rotation("antena-direita", x=recoil * 0.70 * atraso, z=-recoil * 0.35)
    rig.set_rotation("antena-esquerda", x=recoil * 0.70 * atraso, z=recoil * 0.35)
    rig.set_rotation("door", y=max(0.0, -recoil) * 3.0)
    _aplicar_bracos_tronco_dc(rig, b, recoil, extension, curl, atraso)


def _double_click_cabeca(
    rig: Rig, t: float, direction: float, b: _BaseBracos
) -> None:
    """Duplo clique na cabeça: chacoalha a TV, cascata de coluna e fones com retorno suave."""
    u = min(1.0, max(0.0, t / 1.4))
    env = _amostrar_escalar([(0.0, 0.0), (0.12, 1.05), (0.65, 0.85), (0.86, -0.07), (1.0, 0.0)], u)
    atraso_env = _amostrar_escalar([(0.0, 0.0), (0.18, 0.0), (0.46, 1.04), (0.86, -0.06), (1.0, 0.0)], u)
    olhar = _amostrar_escalar([(0.0, 0.0), (0.12, 1.0), (0.76, 0.85), (1.0, 0.0)], u)
    chacoalho = sin(t * 28.0) * env
    atraso = sin(max(0.0, t - 0.08) * 24.0) * env
    porta = _amostrar_escalar(
        [(0.0, 0.0), (0.16, 40.0), (0.36, 12.0), (0.58, 30.0), (1.0, 0.0)], u
    )
    rig.set_rotation("cintura", x=-3.5 * env, z=4.0 * chacoalho)
    rig.set_rotation("abdomen", x=-4.5 * env, z=-3.0 * chacoalho)
    rig.set_rotation("peitoral", x=-6.0 * env, z=-5.0 * chacoalho)
    rig.set_rotation("head", x=-14.0 * env, y=direction * 16.0 * olhar + 26.0 * chacoalho, z=10.0 * atraso)
    rig.set_rotation("door", y=max(0.0, porta))
    rig.set_rotation("fones", x=-12.0 * atraso_env, z=-14.0 * atraso)
    rig.set_rotation("antena-direita", x=-20.0 * atraso_env, z=16.0 * atraso)
    rig.set_rotation("antena-esquerda", x=-20.0 * atraso_env, z=-16.0 * atraso)
    rig.set_rotation("shoulder", x=-3.5 * env, z=5.0 * env)
    rig.set_rotation("shoulder2", x=-3.5 * env, z=-5.0 * env)
    rig.set_rotation("right-arm", x=b.rbx - 10.0 * env, y=b.rby + 8.0 * env, z=b.right_base - 18.0 * env)
    rig.set_rotation("left-arm", x=b.lbx - 10.0 * env, y=b.lby - 8.0 * env, z=b.left_base + 18.0 * env)
    rig.set_rotation("ant-arm", x=b.rex, z=max(0.0, b.right_elbow + 22.0 * env))
    rig.set_rotation("ant-arm2", x=b.lex, z=min(0.0, b.left_elbow - 22.0 * env))
    rig.set_rotation("hand", x=16.0 * atraso_env, z=14.0 * atraso_env)
    rig.set_rotation("hand2", x=16.0 * atraso_env, z=-14.0 * atraso_env)
    rig.set_rotation("fingers", z=-12.0 * env)
    rig.set_rotation("fingers2", z=12.0 * env)


def _aplicar_braco_dc_lado(
    rig: Rig,
    lado: str,
    b: _BaseBracos,
    puxao: float,
    atraso: float,
    sacode: float,
    *,
    tocado: bool,
) -> None:
    """Recolhe o braço tocado ou abre o braço oposto em contrapeso a partir do idle."""
    eh_esq = lado == "left"
    sinal = -1.0 if eh_esq else 1.0
    arm, ant, hand, fing = (
        ("left-arm", "ant-arm2", "hand2", "fingers2")
        if eh_esq
        else ("right-arm", "ant-arm", "hand", "fingers")
    )
    bx, by, bz, ex, ez = (
        (b.lbx, b.lby, b.left_base, b.lex, b.left_elbow)
        if eh_esq
        else (b.rbx, b.rby, b.right_base, b.rex, b.right_elbow)
    )
    if tocado:
        rig.set_rotation(arm, x=bx - 10.0 * puxao, y=by + sinal * 14.0 * puxao, z=bz - sinal * 28.0 * puxao)
        cot = ez + sinal * (38.0 * max(0.0, puxao) + 10.0 * sacode)
        rig.set_rotation(ant, x=ex, z=min(0.0, cot) if eh_esq else max(0.0, cot))
        rig.set_rotation(hand, x=-20.0 * atraso, z=-sinal * 16.0 * sacode)
        rig.set_rotation(fing, z=sinal * 14.0 * puxao)
        return
    rig.set_rotation(arm, x=bx, y=by, z=bz - sinal * 16.0 * puxao)
    cot = ez + sinal * 10.0 * atraso
    rig.set_rotation(ant, x=ex, z=min(0.0, cot) if eh_esq else max(0.0, cot))
    rig.set_rotation(hand, x=8.0 * atraso, z=-sinal * 6.0 * atraso)
    rig.set_rotation(fing, z=sinal * 8.0 * atraso)


def _double_click_braco(
    rig: Rig, t: float, b: _BaseBracos, lado_arm: float
) -> None:
    """Duplo clique no braço: recolhe o braço tocado a partir do idle e compensa com o oposto."""
    u = min(1.0, max(0.0, t / 1.4))
    puxao = _amostrar_escalar([(0.0, 0.0), (0.15, 1.06), (0.48, 0.65), (0.85, -0.07), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.20, 0.0), (0.45, 1.04), (0.86, -0.06), (1.0, 0.0)], u)
    sacode = sin(t * 22.0) * puxao
    eh_esq = lado_arm > 0
    rig.set_rotation("cintura", y=-lado_arm * 8.0 * puxao, z=-lado_arm * 5.0 * puxao)
    rig.set_rotation("abdomen", y=-lado_arm * 10.0 * puxao, z=-lado_arm * 6.0 * puxao)
    rig.set_rotation("peitoral", y=-lado_arm * 14.0 * puxao, z=-lado_arm * 8.0 * puxao)
    rig.set_rotation("head", y=lado_arm * 28.0 * puxao, z=-lado_arm * 8.0 * puxao)
    rig.set_rotation("door", y=max(0.0, 16.0 * puxao))
    rig.set_rotation("fones", x=-6.0 * atraso, z=-lado_arm * 6.0 * atraso)
    rig.set_rotation("antena-direita", x=-12.0 * atraso, z=lado_arm * 8.0 * atraso)
    rig.set_rotation("antena-esquerda", x=-12.0 * atraso, z=-lado_arm * 8.0 * atraso)
    rig.set_rotation("shoulder", x=-3.5 * puxao, z=4.5 * puxao)
    rig.set_rotation("shoulder2", x=-3.5 * puxao, z=-4.5 * puxao)
    _aplicar_braco_dc_lado(rig, "left", b, puxao, atraso, sacode, tocado=eh_esq)
    _aplicar_braco_dc_lado(rig, "right", b, puxao, atraso, sacode, tocado=not eh_esq)


def _double_click_membro_inferior(
    rig: Rig, t: float, b: _BaseBracos, zona: str, lado: float
) -> None:
    """Duplo clique em pernas ou pés: susto para baixo com cascata e contrapeso nos braços."""
    u = min(1.0, max(0.0, t / 1.4))
    env = _amostrar_escalar([(0.0, 0.0), (0.14, 1.05), (0.55, 0.78), (0.85, -0.07), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.20, 0.0), (0.46, 1.04), (0.86, -0.06), (1.0, 0.0)], u)
    tremor = sin(t * 20.0) * env
    inclinacao = 14.0 if zona == "feet" else 9.0
    # Convenção canônica: -X inclina tronco à frente e baixa a cabeça para olhar os pés.
    rig.set_rotation("body", x=-7.5 * env, z=-lado * inclinacao * env + 3.0 * tremor)
    rig.set_rotation("cintura", x=-5.0 * env, z=-lado * 6.0 * env)
    rig.set_rotation("abdomen", x=-4.5 * env, z=-lado * 4.5 * env)
    rig.set_rotation("peitoral", x=-4.0 * env, z=-lado * 3.5 * env)
    rig.set_rotation("head", x=-14.0 * env, y=lado * 22.0 * env, z=lado * 10.0 * env)
    rig.set_rotation("door", y=max(0.0, 24.0 * env))
    rig.set_rotation("fones", x=8.0 * atraso, z=8.0 * tremor)
    rig.set_rotation("antena-direita", x=14.0 * atraso, z=10.0 * tremor)
    rig.set_rotation("antena-esquerda", x=14.0 * atraso, z=-10.0 * tremor)
    rig.set_rotation("shoulder", x=3.5 * env, z=5.0 * env)
    rig.set_rotation("shoulder2", x=3.5 * env, z=-5.0 * env)
    rig.set_rotation("right-arm", x=b.rbx - 8.0 * env, y=b.rby - 8.0 * env, z=b.right_base - 28.0 * env)
    rig.set_rotation("left-arm", x=b.lbx - 8.0 * env, y=b.lby + 8.0 * env, z=b.left_base + 28.0 * env)
    rig.set_rotation("ant-arm", x=b.rex, z=max(0.0, b.right_elbow + 16.0 * env))
    rig.set_rotation("ant-arm2", x=b.lex, z=min(0.0, b.left_elbow - 16.0 * env))
    rig.set_rotation("hand", x=-14.0 * atraso, z=-12.0 * atraso)
    rig.set_rotation("hand2", x=-14.0 * atraso, z=12.0 * atraso)
    rig.set_rotation("fingers", z=-12.0 * atraso)
    rig.set_rotation("fingers2", z=12.0 * atraso)


def _interacao_double_click(
    rig: Rig,
    t: float,
    direction: float,
    vertical: float,
    b: _BaseBracos,
    part: str = "body",
) -> None:
    """Reage ao clique duplo de forma diferenciada por parte tocada."""
    zona = _zona_corpo(part)
    if zona == "head":
        _double_click_cabeca(rig, t, direction, b)
    elif zona == "arm":
        _double_click_braco(rig, t, b, _lado_parte(part, direction))
    elif zona in ("legs", "feet"):
        _double_click_membro_inferior(rig, t, b, zona, _lado_parte(part, direction))
    else:
        _double_click_tronco(rig, t, direction, b)


def _interacao_pet(
    rig: Rig,
    t: float,
    direction: float,
    vertical: float,
    b: _BaseBracos,
    part: str = "body",
) -> None:
    """Inclina coluna e cabeça no carinho com ombros macios, braços soltos e punhos aconchegantes."""
    del vertical, part
    u = min(1.0, max(0.0, t / 1.50))
    antecip = _amostrar_escalar([(0.0, 0.0), (0.07, 1.0), (0.17, 0.0), (1.0, 0.0)], u)
    env = _amostrar_escalar([(0.0, 0.0), (0.06, -0.06), (0.22, 1.02), (0.74, 0.96), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.28, 1.0), (0.82, 0.95), (1.0, 0.0)], u)
    olhar = _amostrar_escalar([(0.0, 0.0), (0.18, 1.0), (0.78, 0.90), (1.0, 0.0)], u)
    embalo = sin(t * 7.5) * max(0.0, env)

    rig.set_rotation("cintura", x=-4.0 * env + 2.0 * antecip, z=direction * 4.0 * env + 2.0 * embalo)
    rig.set_rotation("abdomen", x=-4.5 * env + 1.8 * antecip, z=direction * 3.5 * env + 1.8 * embalo)
    rig.set_rotation("peitoral", x=-3.5 * env + 1.5 * antecip, z=direction * 3.0 * env)
    rig.set_rotation("head", x=-12.0 * env + 3.5 * antecip, y=direction * 25.0 * olhar, z=9.0 * env + 3.0 * embalo)
    rig.set_rotation("body", z=direction * 5.0 * env)
    rig.set_rotation("door", y=max(0.0, env * (18.0 + 3.5 * sin(t * 14.0))))
    rig.set_rotation("fones", z=direction * 4.5 * atraso + 2.5 * embalo)
    rig.set_rotation("antena-direita", x=5.0 * atraso, z=4.0 * embalo)
    rig.set_rotation("antena-esquerda", x=5.0 * atraso, z=4.0 * embalo)
    rig.set_rotation("shoulder", x=3.5 * atraso, z=5.0 * env)
    rig.set_rotation("shoulder2", x=3.5 * atraso, z=-5.0 * env)
    rig.set_rotation(
        "right-arm",
        x=b.rbx + 4.0 * env,
        y=b.rby + 4.0 * env + 5.0 * embalo,
        z=b.right_base - 3.0 * env - 3.0 * embalo,
    )
    rig.set_rotation(
        "left-arm",
        x=b.lbx + 4.0 * env,
        y=b.lby - 4.0 * env + 5.0 * embalo,
        z=b.left_base + 3.0 * env - 3.0 * embalo,
    )
    rig.set_rotation("ant-arm", x=b.rex, z=max(0.0, b.right_elbow + 8.0 * atraso - 2.5 * embalo))
    rig.set_rotation("ant-arm2", x=b.lex, z=min(0.0, b.left_elbow - 8.0 * atraso - 2.5 * embalo))
    rig.set_rotation("hand", x=9.0 * atraso, z=-6.0 * env + 4.0 * embalo)
    rig.set_rotation("hand2", x=9.0 * atraso, z=6.0 * env + 4.0 * embalo)
    rig.set_rotation("fingers", z=11.0 * atraso + 3.0 * embalo)
    rig.set_rotation("fingers2", z=-11.0 * atraso + 3.0 * embalo)


def _interacao_poke(
    rig: Rig,
    t: float,
    direction: float,
    vertical: float,
    b: _BaseBracos,
    part: str = "body",
) -> None:
    """Cutucada expressiva por região (head, body, arm, legs/feet) com os 12 princípios."""
    del vertical
    zona = _zona_corpo(part)
    lado = _lado_parte(part, direction if abs(direction) > 0.05 else 1.0)
    u = min(1.0, max(0.0, t / 0.90))
    antecip = _amostrar_escalar([(0.0, 0.0), (0.07, 1.0), (0.16, 0.0), (1.0, 0.0)], u)
    snap = _amostrar_escalar([(0.0, 0.0), (0.07, -0.25), (0.20, 1.08), (0.48, 0.72), (0.78, -0.10), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.12, 0.0), (0.28, 1.12), (0.62, 0.55), (0.86, -0.12), (1.0, 0.0)], u)
    vib = sin(t * 24.0) * max(0.0, snap)

    if zona == "head":
        # Recuo ágil da cabeça + mão direita subindo em reflexo protetor ao lado do gabinete.
        rig.set_rotation("cintura", x=3.5 * snap - 2.0 * antecip, y=-lado * 6.0 * snap, z=lado * 3.0 * snap)
        rig.set_rotation("abdomen", x=4.5 * snap - 2.5 * antecip, y=-lado * 8.0 * snap, z=lado * 4.0 * snap)
        rig.set_rotation("peitoral", x=6.0 * snap - 3.0 * antecip, y=-lado * 10.0 * snap, z=lado * 5.0 * snap)
        rig.set_rotation("body", x=5.0 * snap - 2.5 * antecip, y=-lado * 8.0 * snap)
        rig.set_rotation("head", x=14.0 * snap - 6.0 * antecip, y=-lado * 26.0 * snap + 8.0 * vib, z=lado * 12.0 * atraso)
        rig.set_rotation("door", y=max(0.0, 26.0 * snap))
        rig.set_rotation("fones", x=-12.0 * atraso, z=-lado * 10.0 * atraso)
        rig.set_rotation("antena-direita", x=-18.0 * atraso, z=14.0 * atraso + 6.0 * vib)
        rig.set_rotation("antena-esquerda", x=-18.0 * atraso, z=-14.0 * atraso - 6.0 * vib)
        rig.set_rotation("shoulder", x=-4.0 * snap, z=-6.0 * snap)
        rig.set_rotation("shoulder2", x=-3.0 * snap, z=4.0 * snap)
        rig.set_rotation("right-arm", x=b.rbx + 18.0 * snap, y=b.rby - 28.0 * snap, z=b.right_base - 48.0 * max(0.0, snap))
        rig.set_rotation("ant-arm", x=b.rex - 12.0 * snap, z=max(0.0, b.right_elbow + 46.0 * max(0.0, snap)))
        rig.set_rotation("hand", x=-18.0 * atraso, z=-10.0 * atraso)
        rig.set_rotation("fingers", z=-16.0 * max(0.0, snap))
        rig.set_rotation("left-arm", x=b.lbx - 8.0 * snap, y=b.lby + 12.0 * snap, z=b.left_base + 22.0 * max(0.0, snap))
        rig.set_rotation("ant-arm2", x=b.lex, z=min(0.0, b.left_elbow - 18.0 * max(0.0, snap)))
        return

    if zona == "arm":
        eh_esq = _lado_parte(part, -1.0) > 0
        s = 1.0 if eh_esq else -1.0
        rig.set_rotation("cintura", x=-3.0 * snap, y=-s * 10.0 * snap, z=-s * 5.0 * snap)
        rig.set_rotation("abdomen", x=-3.5 * snap, y=-s * 12.0 * snap, z=-s * 6.0 * snap)
        rig.set_rotation("peitoral", x=-4.0 * snap, y=-s * 16.0 * snap, z=-s * 7.0 * snap)
        rig.set_rotation("body", y=-s * 12.0 * snap, z=-s * 4.0 * snap)
        rig.set_rotation("head", x=-8.0 * snap, y=s * 28.0 * snap, z=-s * 9.0 * atraso)
        rig.set_rotation("fones", x=-7.0 * atraso, z=-s * 8.0 * atraso)
        rig.set_rotation("antena-direita", x=-14.0 * atraso, z=s * 12.0 * atraso)
        rig.set_rotation("antena-esquerda", x=-14.0 * atraso, z=-s * 12.0 * atraso)
        if eh_esq:
            rig.set_rotation("shoulder2", x=-5.0 * snap, z=8.0 * snap)
            rig.set_rotation("left-arm", x=b.lbx - 18.0 * snap, y=b.lby - 20.0 * snap, z=b.left_base + 38.0 * max(0.0, snap))
            rig.set_rotation("ant-arm2", x=b.lex - 14.0 * snap, z=min(0.0, b.left_elbow - 46.0 * max(0.0, snap)))
            rig.set_rotation("hand2", x=-22.0 * atraso, z=14.0 * vib)
            rig.set_rotation("fingers2", z=-18.0 * max(0.0, snap))
            rig.set_rotation("right-arm", x=b.rbx + 6.0 * snap, y=b.rby - 10.0 * snap, z=b.right_base - 14.0 * max(0.0, snap))
        else:
            rig.set_rotation("shoulder", x=-5.0 * snap, z=-8.0 * snap)
            rig.set_rotation("right-arm", x=b.rbx - 18.0 * snap, y=b.rby + 20.0 * snap, z=b.right_base - 38.0 * max(0.0, snap))
            rig.set_rotation("ant-arm", x=b.rex - 14.0 * snap, z=max(0.0, b.right_elbow + 46.0 * max(0.0, snap)))
            rig.set_rotation("hand", x=-22.0 * atraso, z=-14.0 * vib)
            rig.set_rotation("fingers", z=18.0 * max(0.0, snap))
            rig.set_rotation("left-arm", x=b.lbx + 6.0 * snap, y=b.lby + 10.0 * snap, z=b.left_base + 14.0 * max(0.0, snap))
        return

    if zona in ("legs", "feet"):
        s = _lado_parte(part, 1.0)
        # Pulo em um pé só: inclina o tronco para o lado de apoio e abre os dois braços em equilíbrio!
        rig.set_rotation("body", x=-8.5 * snap, z=-s * 12.0 * snap + 3.0 * vib)
        rig.set_rotation("cintura", x=-6.0 * snap, z=-s * 7.0 * snap)
        rig.set_rotation("abdomen", x=-5.0 * snap, z=-s * 5.5 * snap)
        rig.set_rotation("peitoral", x=-4.5 * snap, z=-s * 4.5 * snap)
        rig.set_rotation("head", x=-18.0 * snap, y=s * 22.0 * snap, z=s * 11.0 * atraso)
        rig.set_rotation("fones", x=10.0 * atraso, z=8.0 * vib)
        rig.set_rotation("antena-direita", x=16.0 * atraso, z=12.0 * vib)
        rig.set_rotation("antena-esquerda", x=16.0 * atraso, z=-12.0 * vib)
        rig.set_rotation("shoulder", x=3.5 * snap, z=-6.0 * snap)
        rig.set_rotation("shoulder2", x=3.5 * snap, z=6.0 * snap)
        rig.set_rotation("right-arm", x=b.rbx - 10.0 * snap, y=b.rby - 14.0 * snap, z=b.right_base - 36.0 * max(0.0, snap))
        rig.set_rotation("left-arm", x=b.lbx - 10.0 * snap, y=b.lby + 14.0 * snap, z=b.left_base + 36.0 * max(0.0, snap))
        rig.set_rotation("ant-arm", x=b.rex, z=max(0.0, b.right_elbow + 22.0 * max(0.0, snap)))
        rig.set_rotation("ant-arm2", x=b.lex, z=min(0.0, b.left_elbow - 22.0 * max(0.0, snap)))
        rig.set_rotation("hand", x=-16.0 * atraso, z=-12.0 * atraso)
        rig.set_rotation("hand2", x=-16.0 * atraso, z=12.0 * atraso)
        rig.set_rotation("fingers", z=-14.0 * max(0.0, snap))
        rig.set_rotation("fingers2", z=14.0 * max(0.0, snap))
        return

    # Tronco / barriga: cócega/estocada viva com torção e contra-ataque expressivo!
    aplicar_cutucar(rig, t, (b.rbx, b.rby, b.right_base), (b.rex, b.right_elbow))
    rig.set_rotation("left-arm", x=b.lbx - 12.0 * snap, y=b.lby + 14.0 * snap, z=b.left_base + 24.0 * max(0.0, snap))
    rig.set_rotation("ant-arm2", x=b.lex, z=min(0.0, b.left_elbow - 28.0 * max(0.0, snap)))
    rig.set_rotation("hand2", x=-14.0 * atraso, z=10.0 * atraso)


def _celebrate_bracos(rig: Rig, carga: float, salto_v: float, bombeio: float, aberto: float) -> None:
    """Comemoração 'YEAH!': V heróico aberto longe da cabeça + punho-bomba largo no peito."""
    del aberto
    v = max(0.0, salto_v)
    p = max(0.0, bombeio)
    suave = max(0.0, min(1.0, v + p))
    pulso_v = 4.0 * sin(v * pi * 2.0) * v
    # Fase 1: carga baixa ao lado do quadril -> Fase 2: V aberto claro dos fones -> Fase 3: bombeio largo à frente.
    # Cada junta respeita o eixo validado por FK (nunca dobra ant-arm no nariz/fones!).
    rig.set_rotation(
        "shoulder",
        x=-5.0 * v + 3.0 * carga + 2.0 * p,
        z=-11.0 * v + 4.0 * carga + 3.0 * p,
    )
    rig.set_rotation(
        "right-arm",
        x=15.0 + 5.0 * v - 6.0 * carga,
        y=-28.0 + 40.0 * v + 38.0 * p + 6.0 * carga,
        z=62.0 - 88.0 * v - 42.0 * p + 12.0 * carga - pulso_v,
    )
    rig.set_rotation(
        "ant-arm",
        x=3.0 + 2.0 * v + 12.0 * p,
        z=max(0.0, 12.0 * (1.0 - v) + 5.0 * v + 40.0 * p + 22.0 * carga),
    )
    rig.set_rotation(
        "hand",
        x=-4.0 * v + 10.0 * p,
        y=6.0 * v,
        z=-4.0 * v + 8.0 * p,
    )
    rig.set_rotation("fingers", z=10.0 * suave)

    # Braço esquerdo em contraponto simétrico-orgânico com leve variação de altura (visual vivo!).
    v_esq = v * 0.95
    rig.set_rotation(
        "shoulder2",
        x=-5.0 * v_esq + 3.0 * carga + 2.0 * p,
        z=11.0 * v_esq - 4.0 * carga - 3.0 * p,
    )
    rig.set_rotation(
        "left-arm",
        x=15.0 + 4.0 * v_esq - 6.0 * carga,
        y=28.0 - 40.0 * v_esq - 38.0 * p - 6.0 * carga,
        z=-62.0 + 86.0 * v_esq + 42.0 * p - 12.0 * carga + pulso_v * 0.85,
    )
    rig.set_rotation(
        "ant-arm2",
        x=3.0 + 2.0 * v_esq + 12.0 * p,
        z=min(0.0, -12.0 * (1.0 - v_esq) - 7.0 * v_esq - 40.0 * p - 22.0 * carga),
    )
    rig.set_rotation(
        "hand2",
        x=-4.0 * v_esq + 10.0 * p,
        y=-6.0 * v_esq,
        z=4.0 * v_esq - 8.0 * p,
    )
    rig.set_rotation("fingers2", z=-10.0 * suave)


def _interacao_celebrate(
    rig: Rig,
    t: float,
    direction: float,
    vertical: float,
    b: _BaseBracos,
    part: str = "body",
) -> None:
    """Comemoração 'YEAH!' (~2s): antecipação limpa -> salto em V heróico -> pump largo no peito -> assento."""
    del vertical, b, part
    u = min(1.0, max(0.0, t / 2.0))
    carga = _amostrar_escalar(
        [(0.0, 0.0), (0.10, 1.0), (0.19, 0.0), (0.56, 0.0), (0.64, 0.25), (0.76, 0.0), (1.0, 0.0)],
        u,
    )
    salto_v = _amostrar_escalar(
        [(0.0, 0.0), (0.15, 0.0), (0.28, 1.0), (0.50, 0.96), (0.60, 0.10), (0.72, 0.0), (1.0, 0.0)],
        u,
    )
    bombeio = _amostrar_escalar(
        [(0.0, 0.0), (0.52, 0.0), (0.62, 1.0), (0.72, 0.55), (0.80, 0.88), (0.94, 0.0), (1.0, 0.0)],
        u,
    )
    atraso = _amostrar_escalar(
        [(0.0, 0.0), (0.18, 0.0), (0.34, 1.0), (0.64, 0.72), (0.88, -0.12), (1.0, 0.0)],
        u,
    )

    # Coluna limpa e heróica: agacha sem torcer -> abre peito orgulhoso -> bomba elástica no pouso.
    pico = max(salto_v, bombeio * 0.5)
    yaw_olhar = direction * 2.5 * pico
    rig.set_rotation(
        "body",
        x=-5.0 * carga + 3.0 * salto_v - 3.0 * bombeio,
        y=yaw_olhar * 0.5,
        z=1.5 * salto_v,
    )
    rig.set_rotation(
        "cintura",
        x=-4.0 * carga + 2.0 * salto_v - 2.0 * bombeio,
        y=0.0,
        z=1.0 * salto_v,
    )
    rig.set_rotation(
        "abdomen",
        x=-4.0 * carga + 2.5 * salto_v - 2.0 * bombeio,
        y=0.0,
        z=1.0 * salto_v,
    )
    rig.set_rotation(
        "peitoral",
        x=-3.0 * carga + 3.5 * salto_v + 1.5 * bombeio,
        y=yaw_olhar * 0.4,
        z=1.0 * salto_v,
    )
    rig.set_rotation(
        "head",
        x=-5.0 * carga + 8.5 * salto_v + 4.0 * bombeio,
        y=yaw_olhar * 0.6,
        z=3.0 * salto_v - 1.5 * bombeio,
    )
    rig.set_rotation("door", x=0.0, y=0.0, z=0.0)
    rig.set_rotation("fones", x=-8.0 * atraso + 3.0 * carga, z=4.5 * salto_v)
    rig.set_rotation("antena-direita", x=-14.0 * atraso + 6.0 * carga, z=10.0 * salto_v)
    rig.set_rotation("antena-esquerda", x=-14.0 * atraso + 6.0 * carga, z=-10.0 * salto_v)
    _celebrate_bracos(rig, carga, salto_v, bombeio, 0.0)


def _aplicar_bracos_land(
    rig: Rig, b: _BaseBracos, impacto: float, atraso: float, heavy: bool
) -> None:
    """Abre braços em contrapeso no pouso com atraso de punhos e dedos."""
    elev = 30.0 if heavy else 24.0
    cotov_delta = 20.0 if heavy else 16.0
    elev_u = max(-0.05, impacto)
    for sh, arm, ant, hand, fing, bx, by, bz, ex, ez, sinal in (
        ("shoulder", "right-arm", "ant-arm", "hand", "fingers", b.rbx, b.rby, b.right_base, b.rex, b.right_elbow, 1.0),
        ("shoulder2", "left-arm", "ant-arm2", "hand2", "fingers2", b.lbx, b.lby, b.left_base, b.lex, b.left_elbow, -1.0),
    ):
        rig.set_rotation(sh, x=3.5 * impacto, z=sinal * 5.5 * impacto)
        rig.set_rotation(arm, x=bx + 8.0 * impacto, y=by - sinal * 20.0 * impacto, z=bz - sinal * elev * elev_u)
        cot = ez + sinal * cotov_delta * impacto
        rig.set_rotation(ant, x=ex, z=max(0.0, cot) if sinal > 0 else min(0.0, cot))
        rig.set_rotation(hand, x=19.0 * atraso, z=-sinal * 9.0 * atraso)
        rig.set_rotation(fing, z=-sinal * 12.0 * atraso)


def _interacao_land(
    rig: Rig,
    t: float,
    direction: float,
    vertical: float,
    b: _BaseBracos,
    part: str = "body",
    *,
    heavy: bool = False,
) -> None:
    """Amortece a aterrissagem com antecipação, impacto de gabinete sólido, contrapeso e rebote ZZZ."""
    del vertical, part
    dur = 1.45 if heavy else 0.50
    u = min(1.0, max(0.0, t / dur))
    if heavy:
        antecip = _amostrar_escalar([(0.0, 0.0), (0.06, 1.0), (0.15, 0.0), (1.0, 0.0)], u)
        impacto = _amostrar_escalar(
            [(0.0, 0.0), (0.15, 1.14), (0.44, 0.94), (0.68, 0.72), (0.86, -0.14), (1.0, 0.0)],
            u,
        )
        atraso = _amostrar_escalar(
            [(0.0, 0.0), (0.05, 0.0), (0.24, 1.12), (0.56, 0.68), (0.83, -0.18), (1.0, 0.0)],
            u,
        )
        olhar = _amostrar_escalar([(0.0, 0.0), (0.16, 1.0), (0.76, 0.85), (1.0, 0.0)], u)
    else:
        antecip = _amostrar_escalar([(0.0, 0.0), (0.07, 1.0), (0.17, 0.0), (1.0, 0.0)], u)
        impacto = _amostrar_escalar([(0.0, 0.0), (0.18, 1.04), (0.52, -0.22), (0.80, 0.08), (1.0, 0.0)], u)
        atraso = _amostrar_escalar([(0.0, 0.0), (0.06, 0.0), (0.28, 1.05), (0.66, -0.24), (1.0, 0.0)], u)
        olhar = _amostrar_escalar([(0.0, 0.0), (0.18, 1.0), (0.68, 0.65), (1.0, 0.0)], u)

    escala_h = 1.35 if heavy else 1.0
    # Convenção canônica: -X absorve o impacto curvando à frente, +X antecipa.
    rig.set_rotation("body", x=-8.0 * escala_h * impacto + 2.0 * antecip, y=direction * 5.0 * impacto, z=-direction * 3.0 * impacto)
    rig.set_rotation("cintura", x=-5.5 * escala_h * impacto + 2.0 * antecip)
    rig.set_rotation("abdomen", x=-4.5 * escala_h * impacto + 1.5 * antecip)
    rig.set_rotation("peitoral", x=-4.0 * escala_h * impacto + 1.5 * antecip)
    rig.set_rotation("legs", x=-10.0 * escala_h * impacto)
    rig.set_rotation("head", x=-10.0 * escala_h * atraso + 3.5 * antecip, y=direction * 12.0 * olhar)
    rig.set_rotation("door", y=max(0.0, (32.0 if heavy else 26.0) * impacto))
    rig.set_rotation("fones", x=11.0 * escala_h * atraso)
    rig.set_rotation("antena-direita", x=19.0 * escala_h * atraso, z=6.5 * atraso)
    rig.set_rotation("antena-esquerda", x=19.0 * escala_h * atraso, z=-6.5 * atraso)
    _aplicar_bracos_land(rig, b, impacto, atraso, heavy)


def _interacao_wake(
    rig: Rig,
    t: float,
    direction: float,
    vertical: float,
    b: _BaseBracos,
    part: str = "body",
) -> None:
    """Acorda: encolhimento inicial, espreguiçar profundo com coluna em onda e retorno macio."""
    del direction, vertical, part
    u = min(1.0, max(0.0, t / 1.20))
    encolhe = _amostrar_escalar([(0.0, 0.0), (0.14, 1.0), (0.30, 0.0), (1.0, 0.0)], u)
    estica = _amostrar_escalar([(0.0, 0.0), (0.16, 0.0), (0.48, 1.04), (0.68, 0.84), (0.90, -0.03), (1.0, 0.0)], u)
    porta_env = _amostrar_escalar([(0.0, 0.0), (0.16, 0.0), (0.48, 1.0), (0.72, 0.88), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.24, 0.0), (0.58, 1.05), (0.92, -0.06), (1.0, 0.0)], u)
    tremor = sin(t * 11.0) * 4.0 * porta_env

    # Convenção canônica: -X encolhe à frente, +X arqueia para trás/cima ao espreguiçar.
    rig.set_rotation("cintura", x=-3.5 * encolhe + 4.0 * estica)
    rig.set_rotation("abdomen", x=-3.5 * encolhe + 4.5 * estica)
    rig.set_rotation("peitoral", x=-3.0 * encolhe + 5.0 * estica)
    rig.set_rotation("body", x=-2.5 * encolhe + 4.5 * estica)
    rig.set_rotation("head", x=-5.0 * encolhe + 9.0 * estica, y=tremor)
    rig.set_rotation("door", y=45.0 * porta_env)
    rig.set_rotation("fones", x=-6.0 * atraso, z=tremor * 0.6)
    rig.set_rotation("antena-direita", x=-10.0 * atraso, z=4.0 * atraso)
    rig.set_rotation("antena-esquerda", x=-10.0 * atraso, z=-4.0 * atraso)
    rig.set_rotation("right-arm", x=b.rbx, y=b.rby, z=b.right_base - WAKE_BRACO_ELEVACAO * estica)
    rig.set_rotation("left-arm", x=b.lbx, y=b.lby, z=b.left_base + WAKE_BRACO_ELEVACAO * estica)
    rig.set_rotation("ant-arm", x=b.rex - 8.0 * estica, z=max(0.0, b.right_elbow + 8.0 * encolhe - 8.0 * estica))
    rig.set_rotation("ant-arm2", x=b.lex - 8.0 * estica, z=min(0.0, b.left_elbow - 8.0 * encolhe + 8.0 * estica))
    rig.set_rotation("hand", x=-14.0 * atraso, z=-10.0 * atraso)
    rig.set_rotation("hand2", x=-14.0 * atraso, z=10.0 * atraso)
    rig.set_rotation("fingers", z=-12.0 * atraso + 8.0 * encolhe)
    rig.set_rotation("fingers2", z=12.0 * atraso - 8.0 * encolhe)
    shoulder_comp = -45.0 * estica * 0.15
    rig.set_rotation("shoulder", x=shoulder_comp, z=-5.0 * estica)
    rig.set_rotation("shoulder2", x=shoulder_comp, z=5.0 * estica)


def _interacao_surprise(
    rig: Rig,
    t: float,
    direction: float,
    vertical: float,
    b: _BaseBracos,
    part: str = "body",
) -> None:
    """Susto: micro-encolhimento, recuo instantâneo com guarda em idle e follow-through."""
    del part
    u = min(1.0, max(0.0, t / 0.70))
    encolhe = _amostrar_escalar([(0.0, 0.0), (0.08, 1.0), (0.20, 0.0), (1.0, 0.0)], u)
    susto = _amostrar_escalar([(0.0, 0.0), (0.06, 0.0), (0.24, 1.06), (0.54, 0.72), (0.85, -0.07), (1.0, 0.0)], u)
    atraso = _amostrar_escalar([(0.0, 0.0), (0.12, 0.0), (0.36, 1.05), (0.84, -0.08), (1.0, 0.0)], u)
    olhar = _amostrar_escalar([(0.0, 0.0), (0.14, 1.0), (0.74, 0.85), (1.0, 0.0)], u)

    # Convenção canônica: -X encolhe, +X recua para trás assustado!
    rig.set_rotation("cintura", x=-3.5 * encolhe + 4.0 * susto, y=direction * 5.0 * susto, z=-direction * 2.5 * susto)
    rig.set_rotation("abdomen", x=-3.0 * encolhe + 4.0 * susto, y=direction * 4.0 * susto)
    rig.set_rotation("peitoral", x=5.0 * susto, y=direction * 5.0 * susto)
    rig.set_rotation(
        "body",
        x=-2.5 * encolhe + SURPRESA_RECUO * 0.75 * susto,
        y=direction * SURPRESA_GIRO * susto,
    )
    rig.set_rotation(
        "head",
        x=-max(-1.0, min(1.0, vertical)) * 18.0 * olhar + SURPRESA_CABECA * 0.65 * susto,
        y=direction * 36.0 * olhar,
        z=-direction * 4.0 * atraso,
    )
    rig.set_rotation("door", y=max(0.0, 34.0 * susto))
    rig.set_rotation("fones", x=-8.0 * atraso, z=direction * 5.0 * atraso)
    rig.set_rotation("antena-direita", x=-14.0 * atraso, z=-6.0 * atraso)
    rig.set_rotation("antena-esquerda", x=-14.0 * atraso, z=6.0 * atraso)
    rig.set_rotation("shoulder", x=-3.5 * susto + 2.5 * encolhe, z=5.0 * susto)
    rig.set_rotation("shoulder2", x=-3.5 * susto + 2.5 * encolhe, z=-5.0 * susto)
    rig.set_rotation(
        "right-arm",
        x=b.rbx - 12.0 * susto,
        y=b.rby + 16.0 * susto,
        z=b.right_base - SURPRESA_BRACO * susto,
    )
    rig.set_rotation(
        "left-arm",
        x=b.lbx - 12.0 * susto,
        y=b.lby - 16.0 * susto,
        z=b.left_base + SURPRESA_BRACO * susto,
    )
    rig.set_rotation("ant-arm", x=b.rex, z=max(0.0, b.right_elbow + 26.0 * susto - 6.0 * atraso))
    rig.set_rotation("ant-arm2", x=b.lex, z=min(0.0, b.left_elbow - 26.0 * susto + 6.0 * atraso))
    rig.set_rotation("hand", x=-14.0 * atraso, z=-10.0 * atraso)
    rig.set_rotation("hand2", x=-14.0 * atraso, z=10.0 * atraso)
    rig.set_rotation("fingers", z=-18.0 * susto)
    rig.set_rotation("fingers2", z=18.0 * susto)


_REACOES_INTERACAO = {
    "hover": _interacao_hover,
    "click": _interacao_click,
    "double_click": _interacao_double_click,
    "pet": _interacao_pet,
    "poke": _interacao_poke,
    "celebrate": _interacao_celebrate,
    "land": _interacao_land,
    "wake": _interacao_wake,
    "surprise": _interacao_surprise,
}


def pose_interaction(
    rig: Rig,
    kind: str,
    t: float,
    direction: float = 0.0,
    vertical: float = 0.0,
    part: str = "body",
    *,
    heavy: bool = False,
) -> None:
    """Aplica as reações procedurais a partir da base ``idle`` sem salto nos braços.

    Um ``kind`` desconhecido aplica só a base dos braços e o olhar da cabeça.
    """
    direction = max(-1.0, min(1.0, direction))
    inter_r = braco_hpr_graus("right", "idle")
    inter_l = braco_hpr_graus("left", "idle")
    b = _ler_base_atual(rig) if kind == "hover" else _ler_base_alvo(inter_r, inter_l)
    rig.set_rotation("right-arm", x=b.rbx, y=b.rby, z=b.right_base)
    rig.set_rotation("left-arm", x=b.lbx, y=b.lby, z=b.left_base)
    rig.set_rotation("ant-arm", x=b.rex, z=b.right_elbow)
    rig.set_rotation("ant-arm2", x=b.lex, z=b.left_elbow)
    if kind == "hover" or kind not in _REACOES_INTERACAO:
        rig.set_rotation(
            "head", x=-max(-1.0, min(1.0, vertical)) * 26.0, y=direction * 40.0
        )
    else:
        rig.set_rotation("head", x=0.0, y=0.0, z=0.0)
    if kind == "land":
        _interacao_land(rig, t, direction, vertical, b, part, heavy=heavy)
        return
    reacao = _REACOES_INTERACAO.get(kind)
    if reacao is not None:
        reacao(rig, t, direction, vertical, b, part)


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
    ant_r, ant_l = repouso_fl["ant-arm"], repouso_fl["ant-arm2"]
    rig.set_rotation("right-arm", x=fl_r[0], y=fl_r[1], z=fl_r[2])
    rig.set_rotation("left-arm", x=fl_l[0], y=fl_l[1], z=fl_l[2])
    rig.set_rotation("ant-arm", x=ant_r[0], y=ant_r[1], z=ant_r[2])
    rig.set_rotation("ant-arm2", x=ant_l[0], y=ant_l[1], z=ant_l[2])
    if kind == "peek":
        # Espiada viva: antecipação do tronco, olhares assimétricos em arco e contrapeso
        olhar = sin(t * 2.2) * 0.75 + sin(t * 1.1 + 0.8) * 0.35
        atraso = sin((t - 0.14) * 2.2) * 0.75 + sin((t - 0.14) * 1.1 + 0.8) * 0.35
        rig.set_rotation("cintura", x=-2.5 * envelope, y=olhar * 4.5 * envelope, z=-olhar * 2.5 * envelope)
        rig.set_rotation("abdomen", x=-2.0 * envelope, y=olhar * 5.0 * envelope, z=-olhar * 2.0 * envelope)
        rig.set_rotation("peitoral", x=-2.0 * envelope, y=olhar * 6.5 * envelope, z=olhar * 2.5 * envelope)
        rig.set_rotation("head", x=-4.5 * envelope + 2.5 * abs(olhar) * envelope, y=olhar * 16.0 * envelope, z=5.5 * envelope - atraso * 4.0 * envelope)
        rig.set_rotation("fones", z=-atraso * 4.0 * envelope)
        rig.set_rotation("antena-direita", x=8.0 * envelope, z=atraso * 5.5 * envelope)
        rig.set_rotation("antena-esquerda", x=8.0 * envelope, z=-atraso * 5.5 * envelope)
        rig.set_rotation("right-arm", x=fl_r[0] + 4.0 * envelope, y=fl_r[1] - 6.0 * envelope, z=fl_r[2] - 7.0 * envelope)
        rig.set_rotation("left-arm", x=fl_l[0] + 4.0 * envelope, y=fl_l[1] + 6.0 * envelope, z=fl_l[2] + 7.0 * envelope)
        rig.set_rotation("ant-arm", x=ant_r[0] - 8.0 * envelope, y=ant_r[1], z=ant_r[2] + 10.0 * envelope)
        rig.set_rotation("ant-arm2", x=ant_l[0] - 8.0 * envelope, y=ant_l[1], z=ant_l[2] - 10.0 * envelope)
        rig.set_rotation("shoulder", x=-2.0 * envelope, z=-2.5 * envelope)
        rig.set_rotation("shoulder2", x=-2.0 * envelope, z=2.5 * envelope)
    else:
        recoil = sin(t * 18) * (1 - phase) ** 2
        rig.set_rotation("body", x=12 * envelope, z=recoil * 10)
        rig.set_rotation("head", x=14 * envelope, z=-recoil * 12)
        rig.set_rotation("door", y=40 * envelope)


def _espirro_bracos(
    rig: Rig, inhale: float, hit: float, relaxa: float = 0.0, prepara: float = 1.0
) -> None:
    """Ergue os braços à frente e relaxa gradualmente antes de limpar a porta.

    Medido no grafo de cena: elevação = eixo do nó ROLL (Z); z NEGATIVO ergue.
    """
    sz_r = braco_hpr_graus("right", "idle")["right-arm"]
    sz_l = braco_hpr_graus("left", "idle")["left-arm"]
    sze = {**braco_hpr_graus("right", "idle"), **braco_hpr_graus("left", "idle")}
    sze_r, sze_l = sze["ant-arm"][2], sze["ant-arm2"][2]
    guarda = prepara * (1.0 - relaxa)
    rig.set_rotation(
        "right-arm",
        x=sz_r[0] - 12 * inhale - 48 * hit,
        y=sz_r[1],
        z=sz_r[2] - (40 + 12 * inhale) * guarda,
    )
    rig.set_rotation(
        "left-arm",
        x=sz_l[0] - 10 * inhale - 44 * hit,
        y=sz_l[1],
        z=sz_l[2] + (40 + 10 * inhale) * guarda,
    )
    # Cotovelos DOBRAM (o sinal antigo pedia hiperextensão).
    rig.set_rotation(
        "ant-arm",
        x=(-12 * inhale - 18 * hit) * guarda,
        z=sze_r + (20 + 20 * inhale) * guarda,
    )
    rig.set_rotation(
        "ant-arm2",
        x=(-10 * inhale - 16 * hit) * guarda,
        z=sze_l - (20 + 18 * inhale) * guarda,
    )
    rig.set_rotation("shoulder", x=-2.5 * inhale + 5.0 * hit, z=4.0 * guarda)
    rig.set_rotation("shoulder2", x=-2.5 * inhale + 5.0 * hit, z=-4.0 * guarda)


def _espirro_esfregar(rig: Rig, t: float) -> None:
    """Esfrega a frente do armário fechado e baixa a mão devagar com curva quíntica."""
    rub_in = suavizar_quintico((t - 7.7) / 0.30)
    rub_out = 1.0 - suavizar_quintico((t - 8.3) / 0.50)
    rub = rub_in * rub_out
    stroke = sin(t * 12) * rub
    if rub <= 1e-4:
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


def _aplicar_sneeze_tronco_maos(
    rig: Rig, inhale: float, hit: float, settle: float, tontura_env: float, ofego: float, shake: float
) -> None:
    """Aplica tronco, cabeça, fones, antenas, mãos e porta no espirro.

    Convenção canônica: +X joga cabeça/peito para trás na inspiração, -X dispara
    tudo à frente na explosão do espirro.
    """
    rig.set_rotation("head", x=12 * inhale - 26 * hit - 4 * settle - 4.0 * tontura_env + 2.5 * ofego, y=shake * 14.0, z=-3 * inhale + shake * 5.0)
    rig.set_rotation("body", x=4.5 * inhale - 14 * hit - 2.5 * settle - 2.5 * tontura_env + 1.8 * ofego, z=shake * 2.5)
    for grupo, c_in, c_hit, c_of in (("cintura", 3.0, -4.5, 1.4), ("abdomen", 4.0, -5.5, 1.8), ("peitoral", 5.0, -6.5, 2.2)):
        rig.set_rotation(grupo, x=c_in * inhale + c_hit * hit + c_of * ofego)
    rig.set_rotation("fones", x=6 * inhale - 14 * hit - 4 * tontura_env, z=shake * 5.0)
    rig.set_rotation("antena-direita", x=10 * inhale - 24 * hit + 12 * tontura_env, z=4 * inhale + shake * 6.0)
    rig.set_rotation("antena-esquerda", x=10 * inhale - 24 * hit + 12 * tontura_env, z=-4 * inhale - shake * 6.0)
    rig.set_rotation("hand", x=15 * hit - 6 * tontura_env, z=-8 * inhale)
    rig.set_rotation("hand2", x=12 * hit - 6 * tontura_env, z=8 * inhale)
    rig.set_rotation("fingers", z=18 * inhale - 10 * hit + 6 * ofego)
    rig.set_rotation("fingers2", z=-18 * inhale + 10 * hit - 6 * ofego)
    rig.set_rotation("door", y=min(48.0, 46.0 * hit + max(0.0, ofego) * 3.0))


def pose_sneeze(rig: Rig, t: float) -> None:
    """Aplica três inspirações, explosão, tontura viva (4.2..7.7 s) e limpeza."""
    # Inspiração lenta, antecipação segurada e um espirro seco para a frente (C1 contínuo em t=3.6s).
    prepara = suavizar_quintico(t / 0.45)
    inhale = suavizar_quintico(t / 3.3) * (1.0 - suavizar_quintico((t - 3.48) / 0.24))
    inhale += sum(
        amp * exp(-(((t - at) / width) ** 2))
        for at, width, amp in ((0.65, 0.24, 0.25), (1.65, 0.32, 0.35), (2.85, 0.4, 0.45))
    )
    hit = exp(-(((t - 3.68) / 0.105) ** 2))
    hit_lag = exp(-(((t - 3.74) / 0.125) ** 2))
    settle = sin(max(0, t - 3.8) * 8) * exp(-max(0, t - 3.8) * 4) if t > 3.8 else 0.0
    tontura_env = suavizar_quintico((t - 4.0) / 0.6) * (1.0 - suavizar_quintico((t - 7.2) / 0.6))
    ofego = sin(max(0.0, t - 3.8) * 4.2) * tontura_env
    shake = sin(max(0.0, t - 4.3) * 11.5) * exp(-max(0.0, t - 4.3) * 0.65) * tontura_env
    relaxa = suavizar_quintico((t - 4.1) / 1.4)

    _aplicar_sneeze_tronco_maos(rig, inhale, hit, settle, tontura_env, ofego, shake)
    # Atraso de chicote nas antenas e fones pós-explosão (Princípio 5)
    rig.set_rotation("fones", x=6 * inhale - 14 * hit_lag - 4 * tontura_env, z=shake * 5.0)
    rig.set_rotation("antena-direita", x=10 * inhale - 24 * hit_lag + 12 * tontura_env, z=4 * inhale + shake * 6.0)
    rig.set_rotation("antena-esquerda", x=10 * inhale - 24 * hit_lag + 12 * tontura_env, z=-4 * inhale - shake * 6.0)
    _espirro_bracos(rig, inhale, hit, relaxa=relaxa, prepara=prepara)
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
    env = suavizar_quintico(t / 0.20)
    balanco = sin(t * 2.2) * env
    groove = cos(t * 4.4) * env
    # Tronco angulado em 3/4 mantendo ombro dianteiro voltado à lente.
    rig.set_rotation("cintura", x=3.0 * env, y=-6.0 * dir_sinal * env, z=-2.0 * dir_sinal * env)
    rig.set_rotation("abdomen", x=-4.0 * env)
    rig.set_rotation("peitoral", x=-6.0 * env, y=6.0 * dir_sinal * env)
    rig.set_rotation("body", x=-7.0 * env + groove * 1.2, y=24.0 * dir_sinal * env)
    # Queixo levemente abaixado encarando a câmera apesar da guinada do corpo.
    rig.set_rotation(
        "head",
        x=-11.0 * env + balanco * 1.5,
        y=-20.0 * dir_sinal * env,
        z=-3.5 * dir_sinal * env,
    )
    rig.set_rotation("fones", x=4.0 * env, z=2.5 * dir_sinal * balanco)
    rig.set_rotation("antena-direita", x=-6.0 * env + groove * 2.0, z=4.5 * env)
    rig.set_rotation("antena-esquerda", x=-6.0 * env + groove * 2.0, z=-4.5 * env)
    frente_right = dir_sinal >= 0.0
    lado_frente = "right" if frente_right else "left"
    lado_atras = "left" if frente_right else "right"
    sinal_frente = 1.0 if frente_right else -1.0
    rig.set_rotation("shoulder" if frente_right else "shoulder2", x=-4.0 * env, z=-sinal_frente * 5.0 * env)
    rig.set_rotation("shoulder2" if frente_right else "shoulder", x=2.5 * env, z=sinal_frente * 3.0 * env)
    _aplicar_braco_hpr(rig, lado_frente, "virtual_alcance", dx=balanco * 2.2)
    _aplicar_braco_hpr(rig, lado_atras, "virtual_apoio", dz=sinal_frente * balanco * 3.0)
    mao_frente = "hand" if frente_right else "hand2"
    mao_atras = "hand2" if frente_right else "hand"
    dedos_frente = "fingers" if frente_right else "fingers2"
    dedos_atras = "fingers2" if frente_right else "fingers"
    # Palma espalmada apontada direto para a câmera; mão de trás solta no quadril.
    rig.set_rotation(mao_frente, x=32.0 * env + balanco * 3.0, z=sinal_frente * 12.0 * env)
    rig.set_rotation(mao_atras, x=-10.0 * env, z=-sinal_frente * 8.0 * env)
    rig.set_rotation(dedos_frente, z=-sinal_frente * 14.0 * env)
    rig.set_rotation(dedos_atras, z=sinal_frente * 4.0 * env)


def pose_blue_balls(rig: Rig, t: float) -> None:
    """FNF Blue Balls: choque elétrico breve seguido de dobra agarrando o quadril."""
    shock = 1.0 - suavizar_quintico((t - 0.18) / 0.18)
    clutch = suavizar_quintico((t - 0.16) / 0.22)
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
    rig.set_rotation("fones", x=-8.0 * shock + 6.0 * clutch, z=tremor * 5.0)
    rig.set_rotation("antena-direita", x=-14.0 * shock + 10.0 * clutch, z=10.0 * shock - 6.0 * clutch + tremor * 5.0)
    rig.set_rotation("antena-esquerda", x=-14.0 * shock + 10.0 * clutch, z=-10.0 * shock + 6.0 * clutch - tremor * 5.0)
    rig.set_rotation("shoulder", x=4.0 * clutch - 5.0 * shock, z=7.0 * clutch - 6.0 * shock)
    rig.set_rotation("shoulder2", x=4.0 * clutch - 5.0 * shock, z=-7.0 * clutch + 6.0 * shock)
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
            y=sinal * 24.0 * clutch,
            z=sinal * (6.0 * shock - 10.0 * clutch),
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
    "celebrate": 3.5,
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
    if state in ("open_hands", "close_fists", "blue_balls", "virtual_insanity", "goku_teleport"):
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
    if state == "goku_teleport":
        return
    forearm, shoulder, hand, fingers, side = lado
    arm = rig.current[forearm]
    authored_shoulder = rig.current[shoulder]
    authored_hand = rig.current[hand]
    authored_fingers = rig.current[fingers]
    rig.set_rotation(
        shoulder,
        x=degrees(authored_shoulder.x) + max(-3, min(3, degrees(arm.x) * 0.12)),
        y=degrees(authored_shoulder.y),
        z=degrees(authored_shoulder.z),
    )
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
    # Fones e antenas reagem com atraso/balanço secundário preservando a pose autoral da reação.
    if "fones" in rig.current:
        atual_f = rig.current["fones"]
        r_fones = micro.get("fones")
        fx = degrees(r_fones.x) if r_fones else 0.0
        fy = degrees(r_fones.y) if r_fones else 0.0
        fz = degrees(r_fones.z) if r_fones else 0.0
        rig.set_rotation(
            "fones",
            x=degrees(atual_f.x) - head_x * 0.08 + fx,
            y=degrees(atual_f.y) - head_y * 0.05 + fy,
            z=degrees(atual_f.z) - head_z * 0.10 + fz,
        )
    for lado_sinal, nome_fone, nome_antena in (
        (1.0, "fone-direito", "antena-direita"),
        (-1.0, "fone-esquerdo", "antena-esquerda"),
    ):
        if nome_fone in rig.current:
            atual_fn = rig.current[nome_fone]
            rig.set_rotation(
                nome_fone,
                x=degrees(atual_fn.x) - head_x * 0.06,
                y=degrees(atual_fn.y) - head_y * 0.04,
                z=degrees(atual_fn.z) - head_z * 0.12 + lado_sinal * sin(t * 1.1) * 0.4,
            )
        if nome_antena in rig.current:
            atual_a = rig.current[nome_antena]
            r_ant = micro.get(nome_antena)
            ax = degrees(r_ant.x) if r_ant else 0.0
            ay = degrees(r_ant.y) if r_ant else 0.0
            az = degrees(r_ant.z) if r_ant else 0.0
            rig.set_rotation(
                nome_antena,
                x=degrees(atual_a.x) - head_x * 0.22 + ax,
                y=degrees(atual_a.y) - head_y * 0.15 + ay,
                z=degrees(atual_a.z) - head_z * 0.28 + az,
            )


def _secundario_coluna_e_fones(rig: Rig, t: float, state: str) -> None:
    """Aplica micro-ruído orgânico e follow-through nos nós da coluna, fones e antenas."""
    if state == "goku_teleport":
        return
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


def pose_goku_teleport(rig: Rig, t: float = 0.0) -> None:
    """Pose do Teleporte do Goku (Shunkan Idō): dois dedos da mão direita na testa e guarda marcial na esquerda."""
    from sejoga.animacao.pose_repouso import REPOUSO

    foco = suavizar_quintico(t / 0.14)
    inv = 1.0 - foco
    pulso_ki = sin(t * 9.0) * 0.8
    rig.set_rotation("body", x=-3.5 * foco, y=-4.0 * foco, z=1.5 * foco)
    rig.set_rotation("cintura", x=-1.5 * foco, y=5.5 * foco, z=-1.0 * foco)
    rig.set_rotation("abdomen", x=-2.0 * foco, y=-3.0 * foco, z=1.0 * foco)
    rig.set_rotation("peitoral", x=-2.5 * foco, y=-5.0 * foco, z=1.5 * foco)
    rig.set_rotation("head", x=(-4.0 + pulso_ki * 0.5) * foco, y=2.0 * foco, z=-1.5 * foco)
    rig.set_rotation("fones", x=3.5 * foco, z=-1.5 * foco + pulso_ki * 0.6)
    rig.set_rotation("door", y=0.0)
    rig.set_rotation("shoulder", x=4.0 * foco, y=4.0 * foco, z=-8.0 * foco)
    # Alvos medidos na malha: indicador e médio chegam à frente da testa,
    # com a palma voltada para o gabinete e o cotovelo abaixo do punho.
    rig.set_rotation(
        "right-arm",
        x=REPOUSO.BRACO_X * inv + 25.5 * foco,
        y=REPOUSO.BRACO_Y * inv + 39.0 * foco,
        z=REPOUSO.BRACO_Z * inv + 27.5 * foco,
    )
    rig.set_rotation("ant-arm", x=24.0 * foco, y=-4.0 * foco, z=REPOUSO.ANTEBRACO_Z * inv + 75.0 * foco)
    rig.set_rotation("hand", x=83.0 * foco, y=44.0 * foco, z=REPOUSO.MAO_Z * inv + 64.5 * foco)
    rig.set_rotation("fingers", z=REPOUSO.DEDOS_Z * inv)
    rig.set_rotation("shoulder2", x=2.0 * foco, y=-3.0 * foco, z=5.0 * foco)
    rig.set_rotation(
        "left-arm",
        x=REPOUSO.BRACO_X * inv - 5.0 * foco,
        y=-REPOUSO.BRACO_Y * inv - 17.5 * foco,
        z=-REPOUSO.BRACO_Z * inv - 40.5 * foco,
    )
    rig.set_rotation("ant-arm2", x=12.0 * foco, y=10.5 * foco, z=-REPOUSO.ANTEBRACO_Z * inv - 67.5 * foco)
    rig.set_rotation("hand2", x=103.0 * foco, y=-38.0 * foco, z=-REPOUSO.MAO_Z * inv - 60.0 * foco)
    rig.set_rotation("fingers2", z=-REPOUSO.DEDOS_Z * inv)
    rig.set_rotation("antena-direita", x=-8.0 * foco + pulso_ki, z=6.0 * foco)
    rig.set_rotation("antena-esquerda", x=-8.0 * foco + pulso_ki, z=-6.0 * foco)


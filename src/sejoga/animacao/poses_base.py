"""Presets de pose procedurais do companion.

Saíram de ``nucleo/esqueleto.py``: usam gestos e clipes de ``animacao``, e
``nucleo`` não importa ``animacao``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from math import degrees, exp, pi, sin, tanh

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


def pose_sleep(rig: Rig, t: float, modo: str = "em_pe") -> None:
    """Aplica a pose de sono com respiração lenta nos 3 modos."""
    breath = sin(t * 0.75)

    if modo == "sentado":
        rig.set_rotation("body", x=8.0 + breath * 0.6, z=-3.0)
        rig.set_rotation("cintura", x=4.0)
        rig.set_rotation("abdomen", x=6.0)
        rig.set_rotation("peitoral", x=8.0)
        rig.set_rotation("head", x=-18.0 + breath * 0.8, y=4.0, z=-5.0)
        rig.set_rotation("coxa-direita", x=68.0)
        rig.set_rotation("coxa-esquerda", x=68.0)
        rig.set_rotation("canela-direita", x=-72.0)
        rig.set_rotation("canela-esquerda", x=-72.0)
        rig.set_rotation("joelho-direito", x=-36.0)
        rig.set_rotation("joelho-esquerdo", x=-36.0)
        rig.set_rotation("right-arm", x=-12.0, y=6.0, z=25.0)
        rig.set_rotation("left-arm", x=-12.0, y=-6.0, z=-25.0)
        rig.set_rotation("ant-arm", x=-8.0, z=42.0)
        rig.set_rotation("ant-arm2", x=-8.0, z=-42.0)
        rig.set_rotation("fingers", z=8.0 + breath * 1.5)
        rig.set_rotation("fingers2", z=-8.0 - breath * 1.5)
        return

    if modo == "deitado":
        rig.set_rotation("body", x=breath * 0.5, z=-82.0)
        rig.set_rotation("head", x=-6.0 + breath * 0.6, z=-10.0)
        rig.set_rotation("coxa-direita", x=24.0, z=8.0)
        rig.set_rotation("coxa-esquerda", x=16.0, z=-6.0)
        rig.set_rotation("canela-direita", x=-32.0)
        rig.set_rotation("canela-esquerda", x=-24.0)
        rig.set_rotation("joelho-direito", x=-16.0)
        rig.set_rotation("joelho-esquerdo", x=-12.0)
        rig.set_rotation("right-arm", x=-10.0, z=45.0)
        rig.set_rotation("left-arm", x=-16.0, z=-50.0)
        rig.set_rotation("ant-arm", z=36.0)
        rig.set_rotation("ant-arm2", z=-36.0)
        rig.set_rotation("fingers", z=8.0)
        rig.set_rotation("fingers2", z=-8.0)
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


def pose_thrown(rig: Rig, t: float = 0.0, velocity=(0.0, 450.0)) -> None:
    """Aplica a silhueta aérea guiada por subida/descida, sem debater."""
    descent = 0.5 + 0.5 * tanh(velocity[1] / 320.0)
    drift = tanh(velocity[0] / 650.0)
    settle = 1.0 - exp(-max(0, t) * 5)
    air_sway = sin(t * 2.7) * (0.55 + 0.45 * descent)
    # One shoulder catches the air while the other trails; symmetrical arms
    # made the fall read as a rigid T-pose. The body turns into the drift and
    # the wrists lag behind the elbows.
    rig.set_rotation("body", x=-6 + 13 * descent, z=-drift * 10 + air_sway * 2)
    rig.set_rotation(
        "head", x=-6 + 14 * descent, y=-drift * 9, z=drift * 5 - air_sway * 2
    )
    # IK: silhueta aérea com as mãos abertas para fora (alvo de queda). O
    # descent/drift/air_sway modulam o braço por cima (inércia do voo).
    thr_r = braco_hpr_graus("right", "thrown")
    thr_l = braco_hpr_graus("left", "thrown")
    rb, re = thr_r["right-arm"], thr_r["ant-arm"]
    lb, le = thr_l["left-arm"], thr_l["ant-arm2"]
    rig.set_rotation(
        "right-arm",
        x=rb[0] - 11 + 8 * descent,
        y=rb[1],
        z=rb[2] + 10 * descent + drift * 8 + air_sway * 6,
    )
    rig.set_rotation(
        "left-arm",
        x=lb[0] - 8 + 6 * descent,
        y=lb[1],
        z=lb[2] - 10 * descent + drift * 4 - air_sway * 7,
    )
    rig.set_rotation(
        "ant-arm",
        x=re[0] - 20 + 8 * descent,
        y=re[1],
        z=re[2] + 12 * descent - air_sway * 5,
    )
    rig.set_rotation(
        "ant-arm2",
        x=le[0] - 14 + 4 * descent,
        y=le[1],
        z=le[2] - 12 * descent + air_sway * 4,
    )
    rig.set_rotation(
        "hand",
        x=8 * settle - 5 * descent,
        y=drift * 3,
        z=-18 + drift * 5 - air_sway * 4,
    )
    rig.set_rotation(
        "hand2",
        x=5 * settle - 3 * descent,
        y=-drift * 2,
        z=14 - drift * 3 + air_sway * 3,
    )
    # Fingers spread slightly during fall
    rig.set_rotation("fingers", z=-8 + sin(t * 3.5) * 2)
    rig.set_rotation("fingers2", z=8 - sin(t * 3.5 + 0.5) * 2)
    # Legs move during fall for more natural motion
    rig.set_rotation("left-feet", x=-8 - 12 * descent + 4 * drift)
    rig.set_rotation("right-feet", x=5 - 8 * descent - 4 * drift)


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


def _interacao_click(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Inclina a cabeça e bate a porta no clique simples."""
    pulse = sin(pi * min(1.0, t / 0.5))
    rig.set_rotation("head", y=direction * 35.0, z=pulse * 8.0)
    rig.set_rotation("door", y=45.0 * sin(t * 4.0 * pi) ** 2)


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
    """Inclina cabeça e tronco no carinho, com a porta vibrando."""
    pulse = sin(pi * min(1.0, t / 1.5))
    rig.set_rotation("head", x=-12.0 * pulse, y=direction * 25.0, z=8.0 * pulse)
    rig.set_rotation("body", z=direction * 5.0 * pulse)
    rig.set_rotation("door", y=pulse * (20.0 + 4.0 * sin(t * 20.0)))


def _interacao_poke(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Delega a cutucada ao gesto de reação."""
    aplicar_cutucar(rig, t, (b.rbx, b.rby, b.right_base), (b.rex, b.right_elbow))


def _interacao_land(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Amortece a aterrissagem no tronco e nas pernas."""
    pulse = sin(pi * min(1.0, t / 0.45))
    rig.set_rotation("body", x=10.0 * pulse)
    rig.set_rotation("legs", x=-12.0 * pulse)
    rig.set_rotation("head", x=8.0 * pulse)
    rig.set_rotation("door", y=15.0 * pulse)


def _interacao_wake(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Acorda: tronco recua, porta abre e os braços sobem ao espreguiçar."""
    pulse = sin(pi * min(1.0, t / 1.2))
    rig.set_rotation("body", x=-6.0 * pulse)
    rig.set_rotation("head", x=-10.0 * pulse, y=sin(t * 12.0) * 5.0 * pulse)
    rig.set_rotation("door", y=75.0 * pulse)
    # Parte dos braços baixados (idle) e os ergue ao espreguiçar.
    # Medido no grafo de cena: elevação = eixo do nó ROLL (Z); z NEGATIVO ergue.
    wake_r = braco_hpr_graus("right", "idle")["right-arm"]
    wake_l = braco_hpr_graus("left", "idle")["left-arm"]
    rig.set_rotation(
        "right-arm",
        x=wake_r[0],
        y=wake_r[1],
        z=wake_r[2] - WAKE_BRACO_ELEVACAO * pulse,
    )
    rig.set_rotation(
        "left-arm",
        x=wake_l[0],
        y=wake_l[1],
        z=wake_l[2] + WAKE_BRACO_ELEVACAO * pulse,
    )
    # Compensação do ombro enquanto os braços sobem.
    shoulder_comp = -45.0 * pulse * 0.15  # approx half of 90
    rig.set_rotation("shoulder", x=shoulder_comp)
    rig.set_rotation("shoulder2", x=-shoulder_comp)


def _interacao_surprise(
    rig: Rig, t: float, direction: float, vertical: float, b: _BaseBracos
) -> None:
    """Susto: recuo rápido do tronco e volta, reagindo na direção do estímulo.

    Fica na camada de olhar da cabeça/tronco/braço, sem giro amplo de corpo.
    Ganhos em ``gestos_tuning`` (SURPRESA_*), calibráveis na GPU.
    """
    pulse = sin(pi * min(1.0, t / 0.7))
    rig.set_rotation(
        "body",
        x=-SURPRESA_RECUO * pulse,
        y=direction * SURPRESA_GIRO * pulse,
    )
    rig.set_rotation(
        "head",
        x=-max(-1.0, min(1.0, vertical)) * 26.0 - SURPRESA_CABECA * pulse,
        y=direction * 40.0,
    )
    # Guarda: os braços sobem um pouco a partir do repouso baixado (IK).
    # elevação = eixo do nó ROLL (Z); z NEGATIVO ergue.
    surp_r = braco_hpr_graus("right", "idle")["right-arm"]
    surp_l = braco_hpr_graus("left", "idle")["left-arm"]
    rig.set_rotation(
        "right-arm",
        x=surp_r[0],
        y=surp_r[1],
        z=surp_r[2] - SURPRESA_BRACO * pulse,
    )
    rig.set_rotation(
        "left-arm",
        x=surp_l[0],
        y=surp_l[1],
        z=surp_l[2] + SURPRESA_BRACO * pulse,
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
    inter_r = braco_hpr_graus("right", "interaction")
    inter_l = braco_hpr_graus("left", "interaction")
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
        opening = min(1.0, t / 2.5, max(0.0, (9.0 - t) / 2.5))
        opening = opening * opening * (3 - 2 * opening)
        rig.set_rotation("door", y=85 * opening)
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
    sz_r = braco_hpr_graus("right", "idle")["right-arm"]
    sze_r = braco_hpr_graus("right", "idle")["ant-arm"][2]
    rig.set_rotation(
        "right-arm", x=sz_r[0] - 35 * rub, y=sz_r[1], z=sz_r[2] - 40 + 55 * rub
    )
    rig.set_rotation("ant-arm", x=-28 * rub, z=sze_r + 20 + 48 * rub)
    rig.set_rotation("hand", x=20 * rub, y=8 * stroke, z=10 * stroke)
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
    curl = 12 + sin(t * 0.62 - side * 0.3) * amplitude + wrist_follow * 0.3
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


def _secundario_coluna_e_fones(rig: Rig, t: float, state: str) -> None:
    """Aplica micro-ruído orgânico e follow-through nos nós da coluna, fones e antenas."""
    escala_ruido = 1.0 if state in ("idle", "hover") else 0.45
    micro = delta_micro_ruido_idle(t, escala=escala_ruido)
    cabeca = rig.current.get("head")
    corpo = rig.current.get("body")
    head_x = degrees(cabeca.x) if cabeca else 0.0
    head_y = degrees(cabeca.y) if cabeca else 0.0
    head_z = degrees(cabeca.z) if cabeca else 0.0
    body_x = degrees(corpo.x) if corpo else 0.0
    body_y = degrees(corpo.y) if corpo else 0.0
    body_z = degrees(corpo.z) if corpo else 0.0

    # Distribui uma fração suave da inclinação/torção nos 3 elos da coluna
    for nome, fracao in (
        ("cintura", 0.12),
        ("abdomen", 0.18),
        ("peitoral", 0.25),
    ):
        if nome in rig.current:
            r_micro = micro.get(nome)
            mx = degrees(r_micro.x) if r_micro else 0.0
            my = degrees(r_micro.y) if r_micro else 0.0
            mz = degrees(r_micro.z) if r_micro else 0.0
            rig.set_rotation(
                nome,
                x=body_x * fracao + mx,
                y=body_y * fracao + my,
                z=body_z * fracao + mz,
            )

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

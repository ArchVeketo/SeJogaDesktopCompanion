"""Novas cenas narrativas de idle v2.0 (SPEC_ROTEIROS_IDLES_E_ACOES).

Princípios de atuação humana (inspiração ZZZ / Persona / Hi-Fi Rush):
- Nenhuma parte se move isolada: toda batida de pé ou gesto propaga em cascata
  ``pelvis -> cintura -> abdomen -> peitoral -> body -> ombros -> cabeça -> fones/antenas``
  com atraso de fase real (0.06-0.14 s).
- Fraseado humano assimétrico (antecipação -> ataque snappy -> assento -> respiro),
  evitando senóides uniformes robóticas.
- Braços sempre resolvidos pelo IK 3D analítico (``ik_bracos.braco_para``) cacheado.

Módulo puro: sem dependências de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

from functools import cache
from math import cos, degrees, exp, radians, sin, tau

from sejoga.animacao import ik_bracos
from sejoga.animacao.braco_hpr import _modelo_ik
from sejoga.animacao.braco_tuning import POLO_COTOVELO_ANATOMICO
from sejoga.animacao.cenas_interativas import (
    AMOSTRADORES_INTERATIVOS,
    DURACOES_CENAS_INTERATIVAS,
)
from sejoga.animacao.estados_delta import delta_absoluto_para_repouso
from sejoga.animacao.gestos_dedos import CURL_NEUTRO
from sejoga.animacao.interpolacao import suavizar_curva
from sejoga.nucleo.esqueleto import Rotation3

Vec3 = tuple[float, float, float]
Dedos5 = tuple[float, float, float, float, float]
DedosCena = tuple[Dedos5, Dedos5]
Pernas6 = tuple[float, ...]
AmostraNova = tuple[dict[str, Rotation3], float, Pernas6, DedosCena]

DURACOES_CENAS_NOVAS: dict[str, float] = {
    "finger_guns_camera": 3.60,
    "bater_pe_impaciente": 5.20,
    "bater_pe_ritmo": 5.60,
    "solo_guitarra_ar": 6.20,
    **DURACOES_CENAS_INTERATIVAS,
}

_DEDOS_NEUTROS: Dedos5 = (CURL_NEUTRO,) * 5
_DEDOS_ARMINHA: Dedos5 = (0.02, 0.02, 0.98, 1.0, 1.0)
_DEDOS_CINTURA: Dedos5 = (0.62, 0.74, 0.84, 0.88, 0.92)
_DEDOS_PALHETA: Dedos5 = (0.78, 0.82, 0.92, 0.95, 0.96)
_DEDOS_ROCK: Dedos5 = (0.04, 0.02, 0.98, 0.98, 0.02)


@cache
def _ik_braco(
    lado: str,
    alvo: Vec3,
    polo: Vec3 = POLO_COTOVELO_ANATOMICO,
) -> tuple[Vec3, Vec3]:
    res = ik_bracos.braco_para(_modelo_ik(), lado, alvo, polo)
    arm_key = "right-arm" if lado == "right" else "left-arm"
    ant_key = "ant-arm" if lado == "right" else "ant-arm2"
    ra, rf = res[arm_key], res[ant_key]
    return (
        (degrees(ra.x), degrees(ra.y), degrees(ra.z)),
        (degrees(rf.x), degrees(rf.y), degrees(rf.z)),
    )


def _quintic(u: float) -> float:
    x = max(0.0, min(1.0, u))
    return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)


def _pulso(t: float, centro: float, largura: float) -> float:
    return exp(-(((t - centro) / largura) ** 2))


def _envelope(t: float, t_ini: float, t_sub: float, t_desce: float, t_fim: float) -> float:
    if t < t_ini or t >= t_fim:
        return 0.0
    if t < t_sub:
        return suavizar_curva((t - t_ini) / max(1e-6, t_sub - t_ini), "overshoot")
    if t <= t_desce:
        return 1.0 + 0.03 * sin((t - t_sub) * 4.2)
    return 1.0 - suavizar_curva((t - t_desce) / max(1e-6, t_fim - t_desce), "ease_in_out")


def _peso_bordas(t: float, dur: float, entrada: float = 0.22, saida: float = 0.34) -> float:
    if t < entrada:
        return suavizar_curva(t / entrada, "snap_out")
    if t > dur - saida:
        return 1.0 - _quintic((t - (dur - saida)) / saida)
    return 1.0


def _lerp3(a: Vec3, b: Vec3, f: float) -> Vec3:
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f)


def _lerp5(a: Dedos5, b: Dedos5, f: float) -> Dedos5:
    return tuple(x + (y - x) * f for x, y in zip(a, b, strict=True))  # type: ignore[return-value]


def _aplicar_deltas_rel(delta: dict[str, Rotation3], rel: dict[str, Vec3]) -> None:
    for grp, (gx, gy, gz) in rel.items():
        delta[grp] = Rotation3(radians(gx), radians(gy), radians(gz))


# --------------------------------------------------------------------------- #
# 1. finger_guns_camera (Arminha dupla pra câmera — 'Ayyy!')
# --------------------------------------------------------------------------- #
def _bracos_finger_guns(f_pose: float, antecip: float, clique: float) -> dict[str, Rotation3]:
    r_arm_b, r_ant_b = _ik_braco("right", (0.155, -0.215, 0.055), (0.15, -0.82, -0.48))
    l_arm_b, l_ant_b = _ik_braco("left", (-0.155, -0.215, 0.055), (-0.15, -0.82, -0.48))
    r_arm_a, r_ant_a = _ik_braco("right", (0.145, 0.030, 0.240), (0.28, -0.70, -0.58))
    l_arm_a, l_ant_a = _ik_braco("left", (-0.145, 0.030, 0.240), (-0.28, -0.70, -0.58))
    r_arm = _lerp3(r_arm_b, r_arm_a, f_pose)
    r_ant = _lerp3(r_ant_b, r_ant_a, f_pose)
    l_arm = _lerp3(l_arm_b, l_arm_a, f_pose)
    l_ant = _lerp3(l_ant_b, l_ant_a, f_pose)
    graus_abs = {
        "right-arm": (r_arm[0], r_arm[1] - antecip * 10.0, r_arm[2] - clique * 11.0),
        "left-arm": (l_arm[0], l_arm[1] + antecip * 10.0, l_arm[2] + clique * 11.0),
        "ant-arm": (r_ant[0], r_ant[1], r_ant[2] + antecip * 14.0 - clique * 6.0),
        "ant-arm2": (l_ant[0], l_ant[1], l_ant[2] - antecip * 14.0 + clique * 6.0),
    }
    return {g: delta_absoluto_para_repouso(g, *v) for g, v in graus_abs.items()}


def amostrar_finger_guns_camera(t: float) -> AmostraNova:
    """Arminha dupla pra câmera com duplo clique de gatilho ('Ayyy!')."""
    dur = DURACOES_CENAS_NOVAS["finger_guns_camera"]
    f_pose = _envelope(t, 0.12, 0.62, 2.55, 3.45)
    antecip = _pulso(t, 0.22, 0.12)
    clique = min(1.15, _pulso(t, 0.92, 0.095) * 0.90 + _pulso(t, 1.32, 0.105) * 1.10)
    delta = _bracos_finger_guns(f_pose, antecip, clique)
    _aplicar_deltas_rel(
        delta,
        {
            "pelvis": (f_pose * 3.5 - clique * 2.5, f_pose * 3.0, -f_pose * 4.0),
            "body": (f_pose * 5.0 - antecip * 4.0 + clique * 3.5, -f_pose * 4.0, f_pose * 5.0),
            "head": (-f_pose * 3.0 + clique * 5.5, f_pose * 4.0, -f_pose * 10.5 - clique * 3.5),
            "fones": (clique * 3.0, 0.0, -f_pose * 3.0 - clique * 4.0),
            "antena-direita": (f_pose * 5.0 + clique * 12.0, 0.0, -f_pose * 8.0 - clique * 6.0),
            "antena-esquerda": (f_pose * 5.0 + clique * 12.0, 0.0, f_pose * 8.0 + clique * 6.0),
            "shoulder": (-f_pose * 5.0 - clique * 4.0, f_pose * 4.0, -f_pose * 4.0),
            "shoulder2": (-f_pose * 5.0 - clique * 4.0, -f_pose * 4.0, f_pose * 4.0),
            "hand": (-f_pose * 8.0 - clique * 14.0, -f_pose * 6.0, f_pose * 8.0),
            "hand2": (-f_pose * 8.0 - clique * 14.0, f_pose * 6.0, -f_pose * 8.0),
            "door": (0.0, f_pose * 2.0 + clique * 4.0, 0.0),
        },
    )
    sq = clique * 10.0 + antecip * 4.0
    pernas: Pernas6 = (
        -4.0 * f_pose - sq * 0.45,
        -7.0 * f_pose - sq * 0.45,
        6.0 + f_pose * 6.0 + sq,
        6.0 + f_pose * 10.0 + sq,
        5.0 + f_pose * 5.0,
        -5.0 - f_pose * 7.0,
    )
    dedos_mao = _lerp5(_DEDOS_NEUTROS, _DEDOS_ARMINHA, _quintic(min(1.0, f_pose * 1.35)))
    return delta, _peso_bordas(t, dur, 0.30, 0.45), pernas, (dedos_mao, dedos_mao)


# --------------------------------------------------------------------------- #
# 2. bater_pe_impaciente (Corpo vivo + indicador batucando + olhar + suspiro)
# --------------------------------------------------------------------------- #
def _batida_impaciente(t: float) -> float:
    return sum(_pulso(t, c, 0.11) for c in (1.00, 1.58, 2.16, 2.74, 3.32))


def amostrar_bater_pe_impaciente(t: float) -> AmostraNova:
    """Impaciência humana: corpo reage ao pé, indicador batuca igual, olhar desvia e suspira."""
    dur = DURACOES_CENAS_NOVAS["bater_pe_impaciente"]
    f_pose = _envelope(t, 0.10, 0.68, 4.35, 5.10)
    bat = _batida_impaciente(t)
    bat_atraso = _batida_impaciente(t - 0.09)
    bat_cab = _batida_impaciente(t - 0.14)
    # Suspiro humano em 2 tempos: inspira estufando em 3.85 s -> desaba expirando em 4.22 s
    inspira = _pulso(t, 3.82, 0.22)
    expira = _pulso(t, 4.22, 0.30)
    # Olhar vivo: encara usuário -> desvia impaciente pro lado em 1.8..2.7 s -> volta encarando
    desvia = _envelope(t, 1.55, 1.90, 2.55, 2.95)
    respiro_vivo = sin(t * 2.1) * f_pose

    r_arm_b, r_ant_b = _ik_braco("right", (0.155, -0.215, 0.055), (0.15, -0.82, -0.48))
    l_arm_b, l_ant_b = _ik_braco("left", (-0.155, -0.215, 0.055), (-0.15, -0.82, -0.48))
    r_arm_c, r_ant_c = _ik_braco("right", (0.175, -0.155, 0.095), (0.72, -0.40, -0.52))
    l_arm_c, l_ant_c = _ik_braco("left", (-0.175, -0.155, 0.095), (-0.72, -0.40, -0.52))
    r_arm = _lerp3(r_arm_b, r_arm_c, f_pose)
    l_arm = _lerp3(l_arm_b, l_arm_c, f_pose)
    graus_abs = {
        "right-arm": (r_arm[0], r_arm[1] + bat_atraso * 3.5, r_arm[2] - inspira * 6.0 + expira * 5.0),
        "left-arm": (l_arm[0], l_arm[1] - bat_atraso * 3.0, l_arm[2] + inspira * 6.0 - expira * 5.0),
        "ant-arm": _lerp3(r_ant_b, r_ant_c, f_pose),
        "ant-arm2": _lerp3(l_ant_b, l_ant_c, f_pose),
    }
    delta = {g: delta_absoluto_para_repouso(g, *v) for g, v in graus_abs.items()}
    _aplicar_deltas_rel(
        delta,
        {
            "pelvis": (f_pose * 3.5 - bat * 2.8 + inspira * 3.0 - expira * 4.0, f_pose * 8.0 + respiro_vivo * 3.5, -f_pose * 8.5 - bat * 3.0),
            "cintura": (f_pose * 2.5 - bat_atraso * 2.0 + inspira * 3.5 - expira * 5.0, respiro_vivo * 2.5, f_pose * 3.0),
            "abdomen": (inspira * 3.0 - expira * 4.0, -respiro_vivo * 2.0, f_pose * 2.0),
            "peitoral": (inspira * 4.0 - expira * 5.0, f_pose * 3.0, bat_atraso * 2.2),
            "body": (f_pose * 4.0 - bat_atraso * 2.5 + inspira * 5.0 - expira * 9.0, f_pose * 10.0 + respiro_vivo * 4.0, f_pose * 5.5 + bat_atraso * 3.0),
            "head": (-f_pose * 3.5 + bat_cab * 3.8 + inspira * 6.0 - expira * 12.0, -f_pose * 16.0 + desvia * 30.0, f_pose * 8.0 - desvia * 12.0 + bat_cab * 2.5),
            "fones": (bat_cab * 3.0 - expira * 4.0, 0.0, f_pose * 3.0 + bat_cab * 3.5),
            "antena-direita": (-f_pose * 6.0 + bat_cab * 11.0 + inspira * 7.0 - expira * 12.0, 0.0, -f_pose * 8.0 - expira * 8.0),
            "antena-esquerda": (-f_pose * 6.0 + bat_cab * 11.0 + inspira * 7.0 - expira * 12.0, 0.0, f_pose * 8.0 + expira * 8.0),
            "shoulder": (-inspira * 8.0 + expira * 10.0 + bat_atraso * 2.5, 0.0, -f_pose * 6.0),
            "shoulder2": (-inspira * 8.0 + expira * 10.0 + bat_atraso * 2.5, 0.0, f_pose * 6.0),
            "hand": (-bat * 10.0, 0.0, 0.0),
            "door": (0.0, f_pose * 1.5 + inspira * 2.0 + expira * 6.0, 0.0),
        },
    )
    pernas: Pernas6 = (
        -3.5 * f_pose - bat * 2.5 - expira * 3.0,
        -13.0 * f_pose - bat * 4.5,
        8.0 + f_pose * 5.0 + bat * 4.5 + expira * 6.0,
        8.0 + f_pose * 12.0 + bat * 6.0,
        5.0 + f_pose * 4.0,
        -5.0 - f_pose * 12.0,
        -3.5 * f_pose - bat * 1.5,
        6.0 * f_pose,
        -5.0,
        -28.0 * bat,
        0.0,
        0.0,
    )
    # Dedo indicador direito batuca no mesmo ritmo do pé! (0.08 estendido -> 0.85 batendo)
    ind = 0.78 - bat * 0.72
    dir_d: Dedos5 = (0.62, ind, 0.86, 0.90, 0.94)
    return (
        delta,
        _peso_bordas(t, dur, 0.32, 0.48),
        pernas,
        (_lerp5(_DEDOS_NEUTROS, dir_d, f_pose), _lerp5(_DEDOS_NEUTROS, _DEDOS_CINTURA, f_pose)),
    )


# --------------------------------------------------------------------------- #
# 3. bater_pe_ritmo (Corpo inteiro no groove + cascata + indicador no beat)
# --------------------------------------------------------------------------- #
def _groove_pulso(t: float, atraso: float = 0.0) -> tuple[float, float, float]:
    """Devolve ``(pulso_snappy, contra_tempo, sway_lateral)`` em ~112 BPM com atraso."""
    beat = tau * ((t - atraso) / 0.535)
    p = ((1.0 - cos(beat)) * 0.5) ** 2.4
    c = ((1.0 - cos(beat - 3.14159)) * 0.5) ** 2.4
    s = sin(beat * 0.5)
    return p, c, s


def amostrar_bater_pe_ritmo(t: float) -> AmostraNova:
    """Groove de corpo inteiro: quadril lidera, coluna/ombros/cabeça em cascata, indicador no beat."""
    dur = DURACOES_CENAS_NOVAS["bater_pe_ritmo"]
    f_pose = _envelope(t, 0.12, 0.65, 4.70, 5.50)
    p0, c0, s0 = _groove_pulso(t, 0.0)
    p1, c1, s1 = _groove_pulso(t, 0.07)
    p2, _, s2 = _groove_pulso(t, 0.13)
    p0, c0, s0 = p0 * f_pose, c0 * f_pose, s0 * f_pose
    p1, c1, s1 = p1 * f_pose, c1 * f_pose, s1 * f_pose
    p2, s2 = p2 * f_pose, s2 * f_pose

    r_arm_b, r_ant_b = _ik_braco("right", (0.155, -0.215, 0.055), (0.15, -0.82, -0.48))
    l_arm_b, l_ant_b = _ik_braco("left", (-0.155, -0.215, 0.055), (-0.15, -0.82, -0.48))
    r_arm_g, r_ant_g = _ik_braco("right", (0.195, -0.015, 0.175), (0.30, -0.72, -0.52))
    l_arm_g, l_ant_g = _ik_braco("left", (-0.185, -0.130, 0.115), (-0.25, -0.78, -0.50))
    r_arm = _lerp3(r_arm_b, r_arm_g, f_pose)
    r_ant = _lerp3(r_ant_b, r_ant_g, f_pose)
    l_arm = _lerp3(l_arm_b, l_arm_g, f_pose)
    l_ant = _lerp3(l_ant_b, l_ant_g, f_pose)
    graus_abs = {
        "right-arm": (r_arm[0], r_arm[1] + s1 * 10.0, r_arm[2] - p1 * 12.0 - c1 * 8.0),
        "left-arm": (l_arm[0], l_arm[1] - s1 * 12.0, l_arm[2] + p1 * 10.0),
        "ant-arm": (r_ant[0], r_ant[1], r_ant[2] + p1 * 14.0 + c1 * 10.0),
        "ant-arm2": (l_ant[0], l_ant[1], l_ant[2] - p1 * 10.0 - s1 * 8.0),
    }
    delta = {g: delta_absoluto_para_repouso(g, *v) for g, v in graus_abs.items()}
    _aplicar_deltas_rel(
        delta,
        {
            "pelvis": (-p0 * 5.5, s0 * 11.0, s0 * 7.5),
            "cintura": (-p1 * 4.0, s1 * 7.0, -s1 * 4.0),
            "abdomen": (-p1 * 3.0, -s1 * 5.0, s1 * 3.5),
            "peitoral": (p1 * 2.5, s1 * 6.0, -s1 * 3.0),
            "body": (-p1 * 6.5, -f_pose * 7.0 + s1 * 9.0, s1 * 6.0),
            "head": (-p2 * 9.5, f_pose * 8.0 - s2 * 8.5, s2 * 8.0),
            "fones": (-p2 * 5.0, 0.0, s2 * 7.5),
            "antena-direita": (-p2 * 11.0, 0.0, -6.0 * f_pose + s2 * 9.0),
            "antena-esquerda": (-p2 * 11.0, 0.0, 6.0 * f_pose + s2 * 9.0),
            "shoulder": (-p1 * 6.0 + s1 * 5.0, 0.0, -5.0 * f_pose),
            "shoulder2": (-p1 * 6.0 - s1 * 5.0, 0.0, 5.0 * f_pose),
            "hand": (-p1 * 16.0 - c1 * 10.0, -6.0 * f_pose, 8.0 * f_pose),
            "hand2": (-p1 * 10.0, 6.0 * f_pose, -8.0 * f_pose),
            "door": (0.0, f_pose * 1.5 + p1 * 3.5, 0.0),
        },
    )
    pernas: Pernas6 = (
        -5.0 * f_pose - p0 * 8.0,
        -12.0 * f_pose - p0 * 8.0,
        10.0 + p0 * 18.0 + max(0.0, s0) * 6.0,
        12.0 + p0 * 18.0 + max(0.0, -s0) * 6.0,
        6.0 + f_pose * 4.0,
        -12.0 * f_pose - 5.0,
        -4.0 + s0 * 3.5,
        5.0 + s0 * 3.5,
        -6.0 - p0 * 6.0,
        -26.0 * p0,
        0.0,
        0.0,
    )
    # Indicador direito marca exatamente o mesmo ritmo do pé (apontando e batendo no beat)!
    dir_d: Dedos5 = (0.30, 0.06 + p0 * 0.62, 0.78, 0.84, 0.88)
    esq_d: Dedos5 = (0.28 + c0 * 0.25, 0.20 + p0 * 0.45, 0.28 + p0 * 0.40, 0.36, 0.44)
    return (
        delta,
        _peso_bordas(t, dur, 0.35, 0.45),
        pernas,
        (_lerp5(_DEDOS_NEUTROS, dir_d, f_pose), _lerp5(_DEDOS_NEUTROS, esq_d, f_pose)),
    )


# --------------------------------------------------------------------------- #
# 4. solo_guitarra_ar (Air Guitar Rockstar — 3 frases humanas + power chord)
# --------------------------------------------------------------------------- #
def _bracos_guitarra(
    t: float, f_pose: float, palhetada: float, frase_aguda: float, climax: float
) -> dict[str, Rotation3]:
    r_arm_b, r_ant_b = _ik_braco("right", (0.155, -0.215, 0.055), (0.15, -0.82, -0.48))
    l_arm_b, l_ant_b = _ik_braco("left", (-0.155, -0.215, 0.055), (-0.15, -0.82, -0.48))
    # Mão esquerda estendida pro lado na altura do peito segurando o braço da guitarra
    l_arm_m, l_ant_m = _ik_braco("left", (-0.235, 0.010, 0.165), (-0.35, -0.75, -0.45))
    l_arm_a, l_ant_a = _ik_braco("left", (-0.255, 0.055, 0.145), (-0.38, -0.72, -0.42))
    l_arm_g = _lerp3(l_arm_m, l_arm_a, frase_aguda)
    l_ant_g = _lerp3(l_ant_m, l_ant_a, frase_aguda)

    # Mão direita à frente do peito (z=0.235, y=-0.09..+0.01 -> 100% fora da colisão da bermuda!)
    # Cotovelo aberto pra fora/trás deixa o antebraço cruzando diagonal nas cordas!
    r_arm_up, r_ant_up = _ik_braco("right", (0.110, 0.015, 0.235), (0.60, -0.45, -0.55))
    r_arm_dn, r_ant_dn = _ik_braco("right", (0.095, -0.085, 0.235), (0.58, -0.55, -0.52))
    r_arm_hi, r_ant_hi = _ik_braco("right", (0.215, 0.160, 0.125), (0.35, -0.60, -0.58))

    strum_u = 0.5 + 0.5 * palhetada
    r_arm_t = _lerp3(_lerp3(r_arm_dn, r_arm_up, strum_u), r_arm_hi, climax)
    r_ant_t = _lerp3(_lerp3(r_ant_dn, r_ant_up, strum_u), r_ant_hi, climax)
    graus_abs = {
        "right-arm": _lerp3(r_arm_b, r_arm_t, f_pose),
        "left-arm": _lerp3(l_arm_b, l_arm_g, f_pose),
        "ant-arm": _lerp3(r_ant_b, r_ant_t, f_pose),
        "ant-arm2": _lerp3(l_ant_b, l_ant_g, f_pose),
    }
    return {g: delta_absoluto_para_repouso(g, *v) for g, v in graus_abs.items()}


def amostrar_solo_guitarra_ar(t: float) -> AmostraNova:
    """Air Guitar em 3 frases humanas: riff firme, solo agudo inclinado e power chord."""
    dur = DURACOES_CENAS_NOVAS["solo_guitarra_ar"]
    f_pose = _envelope(t, 0.12, 0.70, 5.20, 6.08)
    rajada = _envelope(t, 0.72, 0.92, 3.20, 3.48)
    frase_aguda = _envelope(t, 1.85, 2.25, 2.95, 3.35)
    antecip_climax = _pulso(t, 3.22, 0.20)
    climax = _envelope(t, 3.38, 3.68, 4.45, 5.05)

    palhetada = sin(tau * t * 3.8) * rajada
    groove_0 = ((1.0 - cos(tau * t * 1.9)) * 0.5) ** 2 * rajada
    groove_1 = ((1.0 - cos(tau * (t - 0.08) * 1.9)) * 0.5) ** 2 * rajada
    balanco = sin(tau * t * 0.95) * rajada

    delta = _bracos_guitarra(t, f_pose, palhetada, frase_aguda, climax)
    _aplicar_deltas_rel(
        delta,
        {
            # Peito aberto / leve lean back rockstar (nada curvado pra frente!)
            "pelvis": (f_pose * 3.0 - groove_0 * 4.0 - antecip_climax * 6.0 + climax * 10.0, f_pose * 14.0 + balanco * 7.0, -f_pose * 4.0 - frase_aguda * 5.0),
            "cintura": (f_pose * 2.5 - groove_1 * 3.0 - antecip_climax * 5.0 + climax * 7.0, balanco * 5.0, frase_aguda * 4.0),
            "abdomen": (f_pose * 2.0 - groove_1 * 2.0 + climax * 5.0, -balanco * 4.0, frase_aguda * 3.0),
            "peitoral": (f_pose * 2.0 + climax * 5.0, balanco * 4.0, -balanco * 3.0),
            "body": (
                f_pose * 5.0 - groove_1 * 5.0 - antecip_climax * 8.0 + climax * 16.0,
                f_pose * 16.0 + balanco * 8.0,
                f_pose * 4.0 + frase_aguda * 6.0 + climax * 4.0,
            ),
            "head": (
                -groove_1 * 10.0 - antecip_climax * 8.0 + climax * 14.0,
                -f_pose * 10.0 + frase_aguda * 14.0,
                f_pose * 6.0 + balanco * 6.0,
            ),
            "fones": (-groove_1 * 5.0 + climax * 4.0, 0.0, balanco * 6.0),
            "antena-direita": (-groove_1 * 12.0 + climax * 14.0, 0.0, -10.0 * f_pose + balanco * 6.0),
            "antena-esquerda": (-groove_1 * 12.0 + climax * 14.0, 0.0, 10.0 * f_pose + balanco * 6.0),
            "shoulder": (-f_pose * 4.0 - climax * 8.0, 6.0 * f_pose, -6.0 * f_pose),
            "shoulder2": (-f_pose * 6.0 - frase_aguda * 4.0, -6.0 * f_pose, 8.0 * f_pose),
            "hand": (palhetada * 26.0, -8.0 * f_pose, 10.0 * f_pose),
            "hand2": (-16.0 * f_pose, 14.0 * f_pose, -20.0 * f_pose),
            "door": (0.0, f_pose * 2.0 + climax * 6.0, 0.0),
        },
    )
    jo = 16.0 * f_pose + groove_0 * 14.0 + antecip_climax * 16.0 + climax * 8.0
    pernas: Pernas6 = (
        -12.0 * f_pose - groove_0 * 5.0 - antecip_climax * 6.0,
        -10.0 * f_pose - groove_0 * 5.0 - antecip_climax * 6.0,
        6.0 + jo,
        6.0 + jo,
        14.0 * f_pose + 5.0,
        -14.0 * f_pose - 5.0,
        -7.0 * f_pose + balanco * 3.0,
        7.0 * f_pose + balanco * 3.0,
        -10.0 * f_pose - groove_0 * 5.0,
        -10.0 * f_pose - groove_0 * 5.0,
        0.0,
        0.0,
    )
    dedilha = (
        0.35,
        0.20 + 0.60 * (0.5 + 0.5 * sin(t * 20.0)),
        0.20 + 0.60 * (0.5 + 0.5 * sin(t * 20.0 + 1.4)),
        0.20 + 0.60 * (0.5 + 0.5 * sin(t * 20.0 + 2.8)),
        0.20 + 0.60 * (0.5 + 0.5 * sin(t * 20.0 + 4.2)),
    )
    dir_d = _lerp5(_DEDOS_PALHETA, _DEDOS_ROCK, climax)
    esq_d = _lerp5(dedilha, _DEDOS_ROCK, climax)
    return (
        delta,
        _peso_bordas(t, dur, 0.35, 0.50),
        pernas,
        (_lerp5(_DEDOS_NEUTROS, dir_d, f_pose), _lerp5(_DEDOS_NEUTROS, esq_d, f_pose)),
    )


_AMOSTRADORES_NOVOS = {
    "finger_guns_camera": amostrar_finger_guns_camera,
    "bater_pe_impaciente": amostrar_bater_pe_impaciente,
    "bater_pe_ritmo": amostrar_bater_pe_ritmo,
    "solo_guitarra_ar": amostrar_solo_guitarra_ar,
    **AMOSTRADORES_INTERATIVOS,
}


def amostrar_cena_nova(nome: str, tempo: float) -> AmostraNova | None:
    """Despacha uma das novas cenas narrativas v2.0 (ou None se não registrada)."""
    fn = _AMOSTRADORES_NOVOS.get(nome)
    if fn is None:
        return None
    dur = DURACOES_CENAS_NOVAS[nome]
    if tempo < 0.0 or tempo >= dur:
        return None
    return fn(tempo)

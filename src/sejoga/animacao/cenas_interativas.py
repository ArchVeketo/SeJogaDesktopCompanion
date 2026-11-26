"""Cenas interativas de armário vivo, cursor e ejeção de itens (v4 — encenação clara).

Regras centrais desta versão:
- Staging cristalino em 3 atos: o olhar SEMPRE mostra primeiro o que o Mário viu
  (rastreando o cursor até o chão antes do bote; olhando pro próprio peito quando
  o tentáculo sai; acompanhando o item quicar no chão depois de cuspir).
- Zero T-pose residual: poses encadeadas interpolam por waypoints 3D completos
  com cotovelos anatômicos para baixo, sem estacionar em parábolas laterais.
- Assimetria humana real (atraso direita/esquerda, 12 canais de pernas com passos
  e transferência de peso, coluna vertebral inteira e dedos em cascata).

Módulo puro: sem dependências de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

from functools import cache
from math import cos, degrees, exp, pi, radians, sin

from sejoga.animacao import ik_bracos
from sejoga.animacao.braco_hpr import _modelo_ik
from sejoga.animacao.estados_delta import delta_absoluto_para_repouso
from sejoga.animacao.gestos_dedos import CURL_NEUTRO
from sejoga.nucleo.esqueleto import Rotation3

Vec3 = tuple[float, float, float]
Dedos5 = tuple[float, float, float, float, float]
DedosCena = tuple[Dedos5, Dedos5]
Pernas12 = tuple[float, ...]
AmostraNova = tuple[dict[str, Rotation3], float, Pernas12, DedosCena]

DURACOES_CENAS_INTERATIVAS: dict[str, float] = {
    "tentaculo_fujao": 5.40,
    "cacar_cursor_sucesso": 5.60,
    "cacar_cursor_falha": 5.20,
    "roubo_cursor_tentaculo": 5.00,
    "cuspir_item": 2.70,
}

_DEDOS_NEUTROS: Dedos5 = (CURL_NEUTRO,) * 5
_DEDOS_ABERTOS: Dedos5 = (0.04, 0.02, 0.04, 0.06, 0.08)
_DEDOS_EMPURRAR: Dedos5 = (0.20, 0.16, 0.18, 0.22, 0.26)
_DEDOS_GARRA: Dedos5 = (0.36, 0.42, 0.48, 0.54, 0.60)
_DEDOS_CONCHA: Dedos5 = (0.48, 0.58, 0.64, 0.70, 0.74)
_DEDOS_BANDEJA: Dedos5 = (0.22, 0.28, 0.32, 0.36, 0.40)
_DEDOS_CUTUCAR: Dedos5 = (0.76, 0.03, 0.94, 0.96, 0.98)
_DEDOS_MURCHOS: Dedos5 = (0.50, 0.58, 0.65, 0.72, 0.78)

_REPOUSO_DIR: Vec3 = (0.155, -0.215, 0.055)
_REPOUSO_ESQ: Vec3 = (-0.155, -0.215, 0.055)
_POLO_DIR: Vec3 = (0.22, -0.82, -0.48)
_POLO_ESQ: Vec3 = (-0.22, -0.82, -0.48)


@cache
def _ik_q(
    lado: str,
    ax: float,
    ay: float,
    az: float,
    px: float,
    py: float,
    pz: float,
) -> tuple[Vec3, Vec3]:
    res = ik_bracos.braco_para(_modelo_ik(), lado, (ax, ay, az), (px, py, pz))
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


def _ataque_assento(
    t: float,
    t0: float,
    t_pico: float,
    t_desce: float,
    t_fim: float,
    *,
    antecip: float = 0.08,
    over: float = 0.12,
) -> float:
    """Curva humana: antecipação curta -> ataque rápido -> overshoot elástico -> settle."""
    dur_ant = max(0.07, (t_pico - t0) * 0.45)
    if t < t0 - dur_ant or t >= t_fim:
        return 0.0
    if t < t0:
        u = (t - (t0 - dur_ant)) / dur_ant
        return -antecip * sin(u * pi)
    if t < t_pico:
        u = (t - t0) / max(1e-5, t_pico - t0)
        s = 1.0 - (1.0 - u) ** 3.5
        return s * (1.0 + over * sin(u * pi * 0.5))
    if t <= t_desce:
        dt_h = t - t_pico
        return 1.0 + over * exp(-dt_h * 5.2) * cos(dt_h * 9.5)
    return 1.0 - _quintic((t - t_desce) / max(1e-5, t_fim - t_desce))


def _peso_bordas(t: float, dur: float, entrada: float = 0.22, saida: float = 0.36) -> float:
    if t < entrada:
        return 1.0 - (1.0 - max(0.0, min(1.0, t / entrada))) ** 3
    if t > dur - saida:
        return 1.0 - _quintic((t - (dur - saida)) / saida)
    return 1.0


def _lerp3(a: Vec3, b: Vec3, w: float) -> Vec3:
    wc = max(-0.12, min(1.18, w))
    return (a[0] + (b[0] - a[0]) * wc, a[1] + (b[1] - a[1]) * wc, a[2] + (b[2] - a[2]) * wc)


def _braco_alvo_3d(lado: str, alvo: Vec3, polo: Vec3 | None = None) -> dict[str, Rotation3]:
    """Resolve IK 3D exato para o ponto ``alvo`` sem abdução artificial de T-pose."""
    p = polo or (_POLO_DIR if lado == "right" else _POLO_ESQ)
    arm_g, ant_g = _ik_q(
        lado,
        round(alvo[0], 3),
        round(alvo[1], 3),
        round(alvo[2], 3),
        round(p[0], 2),
        round(p[1], 2),
        round(p[2], 2),
    )
    arm_k = "right-arm" if lado == "right" else "left-arm"
    ant_k = "ant-arm" if lado == "right" else "ant-arm2"
    return {
        arm_k: delta_absoluto_para_repouso(arm_k, *arm_g),
        ant_k: delta_absoluto_para_repouso(ant_k, *ant_g),
    }


def _caminho_mao(base: Vec3, etapas: tuple[tuple[Vec3, float], ...]) -> Vec3:
    pos = base
    for alvo, peso in etapas:
        if abs(peso) > 1e-4:
            pos = _lerp3(pos, alvo, peso)
    return pos


def _dedos_cascata(a: Dedos5, b: Dedos5, f: float, spread: float = 0.14) -> Dedos5:
    fc = max(0.0, min(1.0, f))
    pesos = (
        max(0.0, min(1.0, fc * (1.0 + spread) - spread * 0.8)),
        max(0.0, min(1.0, fc * (1.0 + spread) - spread * 0.5)),
        fc,
        max(0.0, min(1.0, fc * (1.0 + spread) - spread * 0.2)),
        min(1.0, fc * (1.0 + spread)),
    )
    return tuple(x + (y - x) * p for x, y, p in zip(a, b, pesos, strict=True))  # type: ignore[return-value]


def _aplicar_rel(delta: dict[str, Rotation3], rel: dict[str, Vec3]) -> None:
    for grp, (gx, gy, gz) in rel.items():
        delta[grp] = Rotation3(radians(gx), radians(gy), radians(gz))


def _vida(t: float) -> tuple[float, float]:
    resp = sin(t * 2.35) * 0.68 + sin(t * 3.85 + 0.9) * 0.32
    deriva = sin(t * 1.45 + 0.4) * 0.65 + sin(t * 2.75 + 1.8) * 0.35
    return resp, deriva


# --------------------------------------------------------------------------- #
# 1. tentaculo_fujao (1 tentáculo espia -> olha pro peito -> susto -> empurra -> disfarça)
# --------------------------------------------------------------------------- #
def _bracos_fujao(susto: float, emp_r: float, emp_l: float, esforco: float, disf: float) -> dict[str, Rotation3]:
    p_r = _caminho_mao(
        _REPOUSO_DIR,
        (
            ((0.195, 0.035, 0.155), susto),
            ((0.088, 0.065 - esforco * 0.012, 0.205 - esforco * 0.018), emp_r),
            ((0.162, -0.175, 0.095), disf),  # mão apoia casual perto do quadril/bolso, ZERO T-pose!
        ),
    )
    p_l = _caminho_mao(
        _REPOUSO_ESQ,
        (
            ((-0.185, 0.010, 0.165), susto * 0.92),
            ((-0.092, 0.035 - esforco * 0.010, 0.205 - esforco * 0.016), emp_l),
            ((-0.158, -0.205, 0.068), disf),
        ),
    )
    polo_r = _lerp3(_POLO_DIR, (0.44, -0.58, -0.50), max(0.0, min(1.0, max(susto, emp_r))))
    polo_l = _lerp3(_POLO_ESQ, (-0.42, -0.60, -0.50), max(0.0, min(1.0, max(susto, emp_l))))
    delta = _braco_alvo_3d("right", p_r, polo_r)
    delta.update(_braco_alvo_3d("left", p_l, polo_l))
    return delta


def amostrar_tentaculo_fujao(t: float) -> AmostraNova:
    """1 tentáculo espia -> Mário olha pra baixo -> mini-susto -> empurra em 3 trancos -> disfarça."""
    dur = DURACOES_CENAS_INTERATIVAS["tentaculo_fujao"]
    resp, deriva = _vida(t)
    olha_baixo = _ataque_assento(t, 0.72, 1.05, 1.38, 1.70, antecip=0.0, over=0.06)
    susto = _ataque_assento(t, 1.32, 1.50, 1.72, 2.02, antecip=0.08, over=0.18)
    emp_r = _ataque_assento(t, 1.76, 2.02, 3.08, 3.52, antecip=0.06, over=0.12)
    emp_l = _ataque_assento(t - 0.08, 1.76, 2.05, 3.12, 3.58, antecip=0.06, over=0.12)
    esforco = _pulso(t, 2.12, 0.12) * 0.75 + _pulso(t, 2.55, 0.13) * 0.90 + _pulso(t, 2.98, 0.11) * 1.20
    slam = _pulso(t, 3.06, 0.10)
    disf = _ataque_assento(t, 3.35, 3.78, 4.70, 5.30, antecip=0.04, over=0.06)
    espia_lados = sin((t - 3.45) * 4.4) * max(0.0, disf)

    delta = _bracos_fujao(susto, emp_r, emp_l, esforco, disf)
    porta_y = max(0.0, _ataque_assento(t, 0.35, 0.88, 2.85, 3.10, antecip=0.0, over=0.08) * 28.0 - esforco * 12.0 - slam * 22.0)
    _aplicar_rel(
        delta,
        {
            "pelvis": (susto * 4.5 - emp_r * 5.0 + disf * 2.5, deriva * 3.5 - susto * 5.0 + disf * 5.0, deriva * 2.5),
            "cintura": (susto * 3.5 - emp_r * 4.0 + resp * 1.4, espia_lados * 3.0, 0.0),
            "abdomen": (susto * 4.0 - emp_r * 4.5 - esforco * 3.0 + disf * 2.5, 0.0, -susto * 2.5),
            "peitoral": (susto * 5.0 - emp_r * 5.0 - esforco * 3.5 + resp * 2.0, espia_lados * 4.0, susto * 3.0),
            "body": (susto * 6.0 - emp_r * 5.5 - esforco * 4.0 + slam * 4.0, deriva * 3.0 + espia_lados * 5.0, -susto * 3.5 + disf * 3.0),
            "head": (-olha_baixo * 15.0 + susto * 13.0 - emp_r * 9.0 + slam * 6.0 + disf * 3.0, espia_lados * 18.0, -olha_baixo * 6.0 - susto * 7.0 + disf * 5.0),
            "fones": (susto * 6.0 - slam * 4.0, 0.0, -susto * 4.0 + espia_lados * 3.0),
            "antena-direita": (susto * 18.0 - esforco * 8.0 - disf * 5.0, 0.0, -susto * 12.0 + espia_lados * 7.0),
            "antena-esquerda": (susto * 16.0 - esforco * 8.0 - disf * 5.0, 0.0, susto * 12.0 + espia_lados * 7.0),
            "shoulder": (-susto * 11.0 - esforco * 5.0 + disf * 5.0, 0.0, -susto * 5.0),
            "shoulder2": (-susto * 10.0 - esforco * 5.0 + disf * 5.0, 0.0, susto * 5.0),
            "hand": (susto * 16.0 - emp_r * 22.0, -emp_r * 8.0, 0.0),
            "hand2": (susto * 14.0 - emp_l * 20.0, emp_l * 8.0, 0.0),
            "door": (0.0, porta_y if t < 3.10 else 0.0, 0.0),
        },
    )
    passo = _pulso(t, 1.44, 0.10)
    rec = max(0.0, susto * 0.7 + emp_r * 0.8)
    hl, hr = -4.0 - rec * 9.0, -4.0 + rec * 9.0 + max(0.0, disf) * 3.0
    kl, kr = 8.0 + rec * 16.0 + slam * 8.0, 8.0 + rec * 12.0 + slam * 6.0
    pernas: Pernas12 = (hl, hr, kl, kr, 6.0, -7.0 - rec * 4.0, -2.5, 3.0, -0.48 * (hl + kl), -0.46 * (hr + kr) + passo * 12.0, 0.0, passo * 0.020)
    f_m = max(0.0, max(susto, emp_r))
    d_r = _dedos_cascata(_DEDOS_NEUTROS, _DEDOS_ABERTOS if susto > emp_r else _DEDOS_EMPURRAR, f_m)
    d_l = _dedos_cascata(_DEDOS_NEUTROS, _DEDOS_ABERTOS if susto > emp_l else _DEDOS_EMPURRAR, max(0.0, max(susto, emp_l)))
    return delta, _peso_bordas(t, dur, 0.30, 0.46), pernas, (d_r, d_l)


# --------------------------------------------------------------------------- #
# 2 & 3. cacar_cursor (Rastreia esq->dir->chão -> agacha -> bote NO CHÃO -> 2 finais)
# --------------------------------------------------------------------------- #
def _rastreio_cursor(t: float) -> tuple[float, float, float, float]:
    """Fase 1 compartilhada: acompanha o cursor cruzando e pousando no chão à frente."""
    rastreia = _ataque_assento(t, 0.08, 0.38, 1.35, 1.68, antecip=0.0, over=0.04)
    # Olhar cruza da esquerda (+18°) pra direita (-16°) e depois crava no centro-chão (0°)
    olhar_yaw = (sin((t - 0.15) * 4.8) * exp(-max(0.0, t - 0.85) * 3.2)) * 20.0 * max(0.0, rastreia)
    agacha = _ataque_assento(t, 0.68, 1.15, 1.55, 1.85, antecip=0.04, over=0.08)
    bote_chao = _ataque_assento(t, 1.52, 1.72, 1.96, 2.25, antecip=0.14, over=0.18)
    return rastreia, olhar_yaw, agacha, bote_chao


def _bracos_cacar_sucesso(agacha: float, bote: float, traz: float, cutuca: float, solta: float, tranco: float) -> dict[str, Rotation3]:
    wiggle = sin(agacha * 9.0) * 0.010
    p_r = _caminho_mao(
        _REPOUSO_DIR,
        (
            ((0.175, -0.045 + wiggle, 0.155), agacha),          # garras prontas
            ((0.058, -0.255, 0.215), bote),                     # BOTE NO CHÃO!
            ((0.088 - cutuca * 0.048, -0.015 + tranco * 0.015 + cutuca * 0.012, 0.215), traz),
            ((0.155, 0.115, 0.185), solta),                     # solta pro alto!
        ),
    )
    p_l = _caminho_mao(
        _REPOUSO_ESQ,
        (
            ((-0.168, -0.055 - wiggle, 0.150), agacha * 0.94),
            ((-0.062, -0.255, 0.212), bote * 0.96),             # BOTE NO CHÃO!
            ((-0.055, -0.035 + tranco * 0.015, 0.210), traz),   # mão esquerda vira "bandeja"
            ((-0.148, 0.105, 0.180), solta * 0.92),
        ),
    )
    polo_r = _lerp3(_POLO_DIR, (0.38, -0.62, -0.52), max(0.0, min(1.0, max(agacha, traz, solta))))
    polo_l = _lerp3(_POLO_ESQ, (-0.36, -0.64, -0.52), max(0.0, min(1.0, max(agacha, traz, solta))))
    delta = _braco_alvo_3d("right", p_r, polo_r)
    delta.update(_braco_alvo_3d("left", p_l, polo_l))
    return delta


def amostrar_cacar_cursor_sucesso(t: float) -> AmostraNova:
    """Segue cursor com o olhar -> agacha -> bate as mãos no chão -> traz na bandeja, cutuca 3x e solta pro alto."""
    dur = DURACOES_CENAS_INTERATIVAS["cacar_cursor_sucesso"]
    resp, deriva = _vida(t)
    rastreia, olhar_yaw, agacha, bote = _rastreio_cursor(t)
    traz = _ataque_assento(t, 1.92, 2.28, 4.18, 4.88, antecip=0.0, over=0.10)
    # Cursor se debatendo dentro das mãos em concha antes dele abrir a bandejinha!
    tranco = sin(t * 24.0) * _pulso(t, 2.15, 0.18)
    cutuca = _pulso(t, 2.68, 0.095) + _pulso(t, 3.06, 0.095) * 0.90 + _pulso(t, 3.68, 0.11) * 1.05
    solta = _ataque_assento(t, 4.22, 4.55, 4.92, 5.46, antecip=0.08, over=0.14)

    delta = _bracos_cacar_sucesso(agacha, bote, traz, cutuca, solta, tranco)
    inclina = sin((t - 2.3) * 2.2) * max(0.0, traz)
    _aplicar_rel(
        delta,
        {
            "pelvis": (-agacha * 10.0 - bote * 14.0 - traz * 3.0 + solta * 3.5, olhar_yaw * 0.25 + traz * 5.0 + deriva * 2.5, inclina * 2.5),
            "cintura": (-agacha * 6.0 - bote * 9.0 - traz * 2.5 + solta * 2.5, -traz * 3.0, 0.0),
            "abdomen": (-agacha * 7.0 - bote * 11.0 - traz * 3.0 + resp * 1.6 + solta * 3.0, cutuca * 2.5, 0.0),
            "peitoral": (-agacha * 8.0 - bote * 12.0 - traz * 4.0 + solta * 5.0, olhar_yaw * 0.3 - traz * 4.0, traz * 3.0),
            "body": (-agacha * 9.0 - bote * 14.0 - traz * 4.5 + solta * 5.5, olhar_yaw * 0.35 - traz * 4.0 + deriva * 2.5, inclina * 3.0),
            "head": (-rastreia * 12.0 - agacha * 8.0 - bote * 8.0 - traz * 14.0 + solta * 18.0, olhar_yaw - traz * 6.0 + solta * 10.0, olhar_yaw * 0.35 + inclina * 11.0 + cutuca * 4.0),
            "fones": (-bote * 5.0 + solta * 4.0, 0.0, inclina * 4.5),
            "antena-direita": (-agacha * 12.0 + bote * 16.0 + cutuca * 13.0 + solta * 14.0, 0.0, -5.0 + inclina * 7.0),
            "antena-esquerda": (-agacha * 10.0 + bote * 14.0 + cutuca * 11.0 + solta * 14.0, 0.0, 5.0 + inclina * 7.0),
            "shoulder": (-agacha * 6.0 - solta * 6.0, 0.0, -agacha * 4.0),
            "shoulder2": (-agacha * 6.0 - solta * 5.0, 0.0, agacha * 4.0),
            "hand": (-bote * 18.0 - cutuca * 20.0 + solta * 18.0, -traz * 10.0, 0.0),
            "hand2": (-bote * 18.0 + traz * 22.0 + solta * 16.0, traz * 14.0, 0.0),
            "door": (0.0, max(0.0, traz * 2.5 + solta * 4.5), 0.0),
        },
    )
    passo = _pulso(t, 1.62, 0.10)
    avan = max(0.0, agacha * 0.7 + bote * 1.1)
    hl = -14.0 * avan - 5.0 * max(0.0, traz)
    hr = -12.0 * avan + 5.0 * max(0.0, traz)
    kl = 8.0 + avan * 32.0 + max(0.0, traz) * 8.0
    kr = 8.0 + avan * 28.0 + max(0.0, traz) * 6.0
    pernas: Pernas12 = (hl, hr, kl, kr, 8.0 + avan * 4.0, -8.0 - avan * 4.0, -3.0, 3.0, -0.48 * (hl + kl), -0.48 * (hr + kr), passo * 0.022, 0.0)

    d_base_r = _dedos_cascata(_DEDOS_NEUTROS, _DEDOS_GARRA if agacha > traz else _DEDOS_CONCHA, max(0.0, max(agacha, bote, traz)))
    d_r = _dedos_cascata(_dedos_cascata(d_base_r, _DEDOS_CUTUCAR, min(1.0, cutuca * 1.15)), _DEDOS_ABERTOS, max(0.0, solta))
    d_l = _dedos_cascata(_dedos_cascata(_DEDOS_NEUTROS, _DEDOS_GARRA if agacha > traz else _DEDOS_BANDEJA, max(0.0, max(agacha, bote, traz))), _DEDOS_ABERTOS, max(0.0, solta))
    return delta, _peso_bordas(t, dur, 0.30, 0.48), pernas, (d_r, d_l)


def _bracos_cacar_falha(agacha: float, bote: float, espia_chao: float, procura: float, triste: float, pend: float) -> dict[str, Rotation3]:
    p_r = _caminho_mao(
        _REPOUSO_DIR,
        (
            ((0.175, -0.045, 0.155), agacha),
            ((0.055, -0.265, 0.220), bote),                     # BATE NO CHÃO!
            ((0.095, -0.185, 0.215), espia_chao),               # levanta mão direita espiando embaixo!
            ((0.150, -0.055, 0.195), procura),                  # abre as palmas: "ué, cadê?!"
            ((0.142, -0.242, 0.068 + pend * 0.042), triste),    # braços caem pesados murchos
        ),
    )
    p_l = _caminho_mao(
        _REPOUSO_ESQ,
        (
            ((-0.168, -0.055, 0.150), agacha * 0.94),
            ((-0.060, -0.265, 0.218), bote * 0.96),
            ((-0.065, -0.245, 0.212), espia_chao),              # esquerda ainda no chão enquanto a dir espia!
            ((-0.145, -0.065, 0.190), procura * 0.94),
            ((-0.142, -0.244, 0.066 - pend * 0.038), triste),
        ),
    )
    polo_r = _lerp3(_POLO_DIR, (0.36, -0.64, -0.52), max(0.0, min(1.0, max(agacha, procura))))
    polo_l = _lerp3(_POLO_ESQ, (-0.36, -0.64, -0.52), max(0.0, min(1.0, max(agacha, procura))))
    delta = _braco_alvo_3d("right", p_r, polo_r)
    delta.update(_braco_alvo_3d("left", p_l, polo_l))
    return delta


def amostrar_cacar_cursor_falha(t: float) -> AmostraNova:
    """Segue cursor -> bate as mãos no chão -> levanta uma mão pra espiar -> procura pros lados -> murcha triste."""
    dur = DURACOES_CENAS_INTERATIVAS["cacar_cursor_falha"]
    resp, deriva = _vida(t)
    rastreia, olhar_yaw, agacha, bote = _rastreio_cursor(t)
    espia_chao = _ataque_assento(t, 1.88, 2.12, 2.38, 2.65, antecip=0.0, over=0.06)
    procura = _ataque_assento(t, 2.35, 2.62, 3.12, 3.48, antecip=0.0, over=0.08)
    triste = _ataque_assento(t, 3.15, 3.55, 4.45, 5.08, antecip=0.06, over=0.10)
    vasculha_yaw = sin((t - 2.38) * 6.8) * 22.0 * max(0.0, procura)
    nega_triste = sin((t - 3.50) * 4.6) * exp(-max(0.0, t - 3.50) * 1.5) * 12.0 * max(0.0, triste)
    pend = exp(-max(0.0, t - 3.30) * 2.3) * sin(max(0.0, t - 3.30) * 5.8) * max(0.0, triste)

    delta = _bracos_cacar_falha(agacha, bote, espia_chao, procura, triste, pend)
    baixa = max(0.0, agacha * 0.7 + bote * 1.1 + espia_chao * 0.85)
    _aplicar_rel(
        delta,
        {
            "pelvis": (-baixa * 11.0 - triste * 5.0, olhar_yaw * 0.25 + vasculha_yaw * 0.20 + deriva * 2.5, -triste * 3.0),
            "cintura": (-baixa * 7.0 - triste * 6.0, 0.0, triste * 2.0),
            "abdomen": (-baixa * 8.0 - triste * 7.5 + resp * 1.5, vasculha_yaw * 0.15, 0.0),
            "peitoral": (-baixa * 9.0 - triste * 9.0 + resp * 2.0, vasculha_yaw * 0.25, triste * 3.0),
            "body": (-baixa * 10.0 - procura * 4.0 - triste * 10.5, olhar_yaw * 0.3 + vasculha_yaw * 0.3, triste * 3.5),
            "head": (-rastreia * 12.0 - baixa * 10.0 - procura * 12.0 - triste * 20.0, olhar_yaw + vasculha_yaw + nega_triste, espia_chao * 10.0 - triste * 8.0),
            "fones": (-bote * 5.0 - triste * 4.0, 0.0, -triste * 3.5),
            "antena-direita": (-agacha * 10.0 + bote * 12.0 - triste * 22.0, 0.0, -triste * 25.0),
            "antena-esquerda": (-agacha * 10.0 + bote * 12.0 - triste * 22.0, 0.0, triste * 25.0),
            "shoulder": (-bote * 6.0 + triste * 14.0, 0.0, triste * 6.5),
            "shoulder2": (-bote * 6.0 + triste * 13.0, 0.0, -triste * 6.5),
            "hand": (-bote * 20.0 + procura * 26.0 + pend * 14.0, -procura * 16.0, 0.0),
            "hand2": (-bote * 20.0 + procura * 24.0 - pend * 14.0, procura * 16.0, 0.0),
            "door": (0.0, max(0.0, bote * 3.5 + triste * 3.0), 0.0),
        },
    )
    passo = _pulso(t, 1.62, 0.10)
    hl = -14.0 * baixa - 6.0 * max(0.0, triste)
    hr = -13.0 * baixa - 7.0 * max(0.0, triste)
    kl = 8.0 + baixa * 32.0 + max(0.0, procura) * 10.0 + max(0.0, triste) * 14.0
    kr = 8.0 + baixa * 30.0 + max(0.0, procura) * 12.0 + max(0.0, triste) * 16.0
    pernas: Pernas12 = (hl, hr, kl, kr, 8.0, -8.0, -2.5, 2.5, -0.48 * (hl + kl), -0.48 * (hr + kr), 0.0, passo * 0.022)
    d_alvo = _DEDOS_CONCHA if (bote + espia_chao) > procura and (bote + espia_chao) > triste else (_DEDOS_ABERTOS if procura >= triste else _DEDOS_MURCHOS)
    f_d = max(0.0, max(agacha, bote, procura, triste))
    return delta, _peso_bordas(t, dur, 0.30, 0.48), pernas, (_dedos_cascata(_DEDOS_NEUTROS, d_alvo, f_d), _dedos_cascata(_DEDOS_NEUTROS, d_alvo, f_d * 0.95))


# --------------------------------------------------------------------------- #
# 4. roubo_cursor_tentaculo (Espia fresta -> puxa -> MASTIGA FECHADO -> cospe + limpa!)
# --------------------------------------------------------------------------- #
def _bracos_roubo(tranco: float, mastiga: float, estufa: float, cuspe: float, limpa: float, nhac: float) -> dict[str, Rotation3]:
    p_r = _caminho_mao(
        _REPOUSO_DIR,
        (
            ((0.185, -0.025, 0.135), tranco),                       # recuo curto de surpresa (sem T-pose!)
            ((0.188, 0.115 + nhac * 0.010, 0.115), mastiga),        # segura fone direito tremendo
            ((0.175, -0.095, 0.115), max(estufa, cuspe)),           # apoia firme no cuspe (sem abrir T-pose!)
            ((0.182, 0.120, 0.118), limpa),                         # ajeita o fone com a mão dobrada natural
        ),
    )
    p_l = _caminho_mao(
        _REPOUSO_ESQ,
        (
            ((-0.180, -0.040, 0.140), tranco * 0.92),
            ((-0.190, 0.100 - nhac * 0.010, 0.118), mastiga * 0.95),
            ((-0.170, -0.110, 0.110), max(estufa, cuspe) * 0.92),
        ),
    )
    polo_r = _lerp3(_POLO_DIR, (0.50, -0.50, -0.48), max(0.0, min(1.0, max(mastiga, limpa))))
    polo_l = _lerp3(_POLO_ESQ, (-0.48, -0.52, -0.48), max(0.0, min(1.0, mastiga)))
    delta = _braco_alvo_3d("right", p_r, polo_r)
    delta.update(_braco_alvo_3d("left", p_l, polo_l))
    return delta


def amostrar_roubo_cursor_tentaculo(t: float) -> AmostraNova:
    """Porta entreabre -> bote puxa cursor -> PORTA BATE FECHADA mastigando -> estufa e cospe."""
    dur = DURACOES_CENAS_INTERATIVAS["roubo_cursor_tentaculo"]
    resp, deriva = _vida(t)
    emboscada = _ataque_assento(t, 0.08, 0.35, 0.58, 0.72, antecip=0.0, over=0.05)
    tranco = _ataque_assento(t, 0.65, 0.82, 1.12, 1.38, antecip=0.06, over=0.20)
    mastiga = _ataque_assento(t, 1.32, 1.58, 2.82, 3.12, antecip=0.0, over=0.08)
    # 4 mastigadas nítidas ("nhac, nhac, nhac, nhac") com a porta FECHADA!
    nhac = sin((t - 1.35) * 14.5) * max(0.0, mastiga)
    estufa = _ataque_assento(t, 2.92, 3.18, 3.28, 3.44, antecip=0.0, over=0.10)
    cuspe = _ataque_assento(t, 3.28, 3.44, 3.72, 4.10, antecip=0.08, over=0.22)
    limpa = _ataque_assento(t, 3.98, 4.26, 4.56, 4.92, antecip=0.04, over=0.06)

    delta = _bracos_roubo(tranco, mastiga, estufa, cuspe, limpa, nhac)
    porta_ang = (
        emboscada * 12.0
        + tranco * 46.0
        + abs(nhac) * 3.5
        + estufa * 14.0
        + cuspe * 48.0
    )
    if 1.38 <= t <= 2.90:
        porta_ang = abs(nhac) * 4.0  # PORTA TRANCADA mastigando lá dentro!
    _aplicar_rel(
        delta,
        {
            "pelvis": (tranco * 4.0 + estufa * 4.5 - cuspe * 6.5, deriva * 3.0 + nhac * 3.5, nhac * 3.0),
            "cintura": (tranco * 3.0 + estufa * 3.5 - cuspe * 4.5, nhac * 3.5, -nhac * 2.0),
            "abdomen": (tranco * 3.5 + estufa * 4.0 - cuspe * 5.0 + resp * 1.5, -nhac * 3.0, nhac * 2.5),
            "peitoral": (tranco * 4.5 + estufa * 5.0 - cuspe * 6.5, nhac * 4.0 - limpa * 4.0, nhac * 3.0),
            "body": (tranco * 5.0 + estufa * 5.5 - cuspe * 7.5, deriva * 2.5 + nhac * 4.5, emboscada * 4.0 + nhac * 3.5),
            "head": (-emboscada * 6.0 + tranco * 8.0 + abs(nhac) * 6.0 + estufa * 7.0 - cuspe * 10.0, emboscada * 10.0 - nhac * 7.5 - limpa * 7.0, emboscada * 8.0 + nhac * 7.0 + limpa * 6.0),
            "fones": (tranco * 6.0 - cuspe * 5.0, 0.0, nhac * 5.5),
            "antena-direita": (tranco * 16.0 + cuspe * 18.0, 0.0, -nhac * 12.0),
            "antena-esquerda": (tranco * 15.0 + cuspe * 16.0, 0.0, nhac * 12.0),
            "shoulder": (-tranco * 10.0 - mastiga * 7.0 - estufa * 8.0, 0.0, -mastiga * 5.0),
            "shoulder2": (-tranco * 9.0 - mastiga * 7.0 - estufa * 8.0, 0.0, mastiga * 5.0),
            "hand": (tranco * 14.0 - mastiga * 12.0, 0.0, 0.0),
            "hand2": (tranco * 12.0 - mastiga * 12.0, 0.0, 0.0),
            "door": (0.0, min(48.0, max(0.0, porta_ang)), 0.0),
        },
    )
    passo = _pulso(t, 0.80, 0.11)
    hl = -5.0 - max(0.0, tranco) * 8.0 + max(0.0, estufa) * 5.0 - max(0.0, cuspe) * 12.0
    hr = -5.0 + max(0.0, tranco) * 8.0 + max(0.0, estufa) * 5.0 - max(0.0, cuspe) * 9.0
    kl = 8.0 + max(0.0, tranco) * 16.0 + abs(nhac) * 6.0 + max(0.0, estufa) * 14.0 + max(0.0, cuspe) * 18.0
    kr = 8.0 + max(0.0, tranco) * 12.0 + abs(nhac) * 6.0 + max(0.0, estufa) * 14.0 + max(0.0, cuspe) * 14.0
    pernas: Pernas12 = (hl, hr, kl, kr, 7.0, -8.0, -2.5, 2.5, -0.46 * (hl + kl), -0.46 * (hr + kr) + passo * 10.0, 0.0, passo * 0.018)
    f_m = max(0.0, max(tranco, mastiga, cuspe, limpa))
    d_r = _dedos_cascata(_DEDOS_NEUTROS, _DEDOS_EMPURRAR if (mastiga > tranco or limpa > 0.2) else _DEDOS_ABERTOS, f_m)
    d_l = _dedos_cascata(_DEDOS_NEUTROS, _DEDOS_EMPURRAR if mastiga > tranco else _DEDOS_ABERTOS, max(0.0, max(tranco, mastiga, cuspe)))
    return delta, _peso_bordas(t, dur, 0.26, 0.45), pernas, (d_r, d_l)


# --------------------------------------------------------------------------- #
# 5. cuspir_item (Inspira -> TENTÁCULOS arremessam item pra fora -> olha quicar e fecha!)
# --------------------------------------------------------------------------- #
def amostrar_cuspir_item(t: float) -> AmostraNova:
    """Engasga/inspira -> porta abre largo pros tentáculos cuspirem o item -> acompanha no chão e fecha."""
    dur = DURACOES_CENAS_INTERATIVAS["cuspir_item"]
    resp, deriva = _vida(t)
    inspira = _ataque_assento(t, 0.08, 0.46, 0.58, 0.76, antecip=0.04, over=0.10)
    cuspe_p = _ataque_assento(t, 0.56, 0.76, 1.10, 1.52, antecip=0.0, over=0.18)
    cuspe_c = _ataque_assento(t - 0.06, 0.56, 0.78, 1.14, 1.58, antecip=0.0, over=0.22)
    olha_item = _ataque_assento(t, 1.05, 1.38, 2.05, 2.55, antecip=0.0, over=0.08)
    fecha_porta = _ataque_assento(t, 1.58, 1.88, 2.15, 2.55, antecip=0.06, over=0.10)
    tapinha = _pulso(t, 1.92, 0.09)

    p_r = _caminho_mao(
        _REPOUSO_DIR,
        (
            ((0.165, -0.085, 0.115), inspira),              # mãos puxam pro peito tomando impulso
            ((0.185, -0.115, 0.085), cuspe_p),              # contrabalança pra trás (cotovelo dobrado, sem T-pose!)
            ((0.095, 0.045, 0.215), fecha_porta),           # mão direita encosta na frente da porta pra fechar!
        ),
    )
    p_l = _caminho_mao(
        _REPOUSO_ESQ,
        (
            ((-0.162, -0.095, 0.110), inspira * 0.92),
            ((-0.180, -0.125, 0.085), cuspe_p * 0.90),
        ),
    )
    polo_r = _lerp3(_POLO_DIR, (0.42, -0.60, -0.50), max(0.0, min(1.0, fecha_porta)))
    delta = _braco_alvo_3d("right", p_r, polo_r)
    delta.update(_braco_alvo_3d("left", p_l, _POLO_ESQ))

    porta_ang = max(0.0, inspira * 22.0 + cuspe_c * 48.0 + olha_item * 24.0 * (1.0 - min(1.0, max(0.0, fecha_porta) * 1.3)))
    _aplicar_rel(
        delta,
        {
            "pelvis": (inspira * 4.5 - cuspe_p * 6.5, deriva * 2.5 - fecha_porta * 3.5, 0.0),
            "cintura": (inspira * 3.5 - cuspe_p * 4.5, 0.0, olha_item * 2.0),
            "abdomen": (inspira * 4.0 - cuspe_p * 5.0 + resp * 1.4, -fecha_porta * 2.5, 0.0),
            "peitoral": (inspira * 5.0 - cuspe_c * 6.5 + tapinha * 2.5, -fecha_porta * 4.0, olha_item * 2.5),
            "body": (inspira * 5.5 - cuspe_c * 7.5 - olha_item * 3.5, -fecha_porta * 3.5, olha_item * 3.0),
            "head": (inspira * 6.5 - cuspe_c * 9.0 - olha_item * 11.0 + tapinha * 4.0, olha_item * 6.0, olha_item * 6.0),
            "fones": (inspira * 4.5 - cuspe_c * 7.0, 0.0, olha_item * 3.0),
            "antena-direita": (-inspira * 12.0 + cuspe_c * 20.0, 0.0, -cuspe_c * 11.0),
            "antena-esquerda": (-inspira * 10.0 + cuspe_c * 18.0, 0.0, cuspe_c * 11.0),
            "shoulder": (-inspira * 10.0 + cuspe_c * 7.0, 0.0, -inspira * 5.0),
            "shoulder2": (-inspira * 9.0 + cuspe_c * 6.0, 0.0, inspira * 5.0),
            "hand": (cuspe_c * 14.0 - fecha_porta * 18.0 - tapinha * 10.0, -fecha_porta * 8.0, 0.0),
            "hand2": (cuspe_c * 12.0, 0.0, 0.0),
            "door": (0.0, min(48.0, porta_ang if t < 1.96 else 0.0), 0.0),
        },
    )
    elev = max(0.0, inspira) * 0.018
    hl = -8.0 * inspira - 13.0 * cuspe_p - 4.0 * olha_item
    hr = -6.0 * inspira + 7.0 * cuspe_p - 3.0 * olha_item
    kl = 8.0 + inspira * 16.0 + cuspe_p * 24.0 + olha_item * 8.0
    kr = 8.0 + inspira * 14.0 + cuspe_p * 14.0 + olha_item * 6.0
    pernas: Pernas12 = (hl, hr, kl, kr, 7.0, -8.0 - cuspe_p * 4.0, -2.5, 2.5, -0.46 * (hl + kl) + inspira * 10.0, -0.46 * (hr + kr), elev, 0.0)
    d_r = _dedos_cascata(_DEDOS_NEUTROS, _DEDOS_EMPURRAR if fecha_porta > cuspe_p else _DEDOS_ABERTOS, max(0.0, max(inspira, cuspe_p, fecha_porta)))
    d_l = _dedos_cascata(_DEDOS_NEUTROS, _DEDOS_ABERTOS, max(0.0, max(inspira, cuspe_p)))
    return delta, _peso_bordas(t, dur, 0.20, 0.40), pernas, (d_r, d_l)


AMOSTRADORES_INTERATIVOS = {
    "tentaculo_fujao": amostrar_tentaculo_fujao,
    "cacar_cursor_sucesso": amostrar_cacar_cursor_sucesso,
    "cacar_cursor_falha": amostrar_cacar_cursor_falha,
    "roubo_cursor_tentaculo": amostrar_roubo_cursor_tentaculo,
    "cuspir_item": amostrar_cuspir_item,
}

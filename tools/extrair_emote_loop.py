"""Extrai e faz retargeting 1:1 em 3D dos emotes do Fortnite (.blend) para o rig do Mário.

Uso:
  blender -b --python tools/extrair_emote_loop.py -- --lote-padrao
  blender -b "assets/animation/emotes/Electro Swing.blend" --python tools/extrair_emote_loop.py -- --saida assets/animation/loops/electro_swing.json

Como funciona o retargeting 1:1:
  1. Amostra as faixas NLA nativas do Unreal/Fortnite a 30.0 fps reais (sem desacelerar em 24fps)
     e aplica ``bpm_nativo`` + ``velocidade`` próprios por emote.
  2. Constrói referenciais anatômicos 3D sem viés de roll de ossos no espaço de autoria
     (``+X`` direita, ``+Y`` frente, ``+Z`` cima):
     - Pelve (``thigh_r - thigh_l``, ``spine_02 - pelvis``) + heading contínuo sem salto em ±180°.
     - Coluna (``cintura``, ``abdomen``, ``peitoral``), clavículas (``shoulder``, ``shoulder2``) e ``head``.
  3. Braços e antebraços 1:1 com ramo de Euler duplo (``(h,p,r)`` vs ``(h+pi, pi-p, r+pi)``) para manter
     ângulos dentro da zona linear de ``braco_tuning`` (braços esticados retos até acima da cabeça),
     eixo de dobradiça anatômico contínua e anti-atravessamento real contra tronco e cabeça.
  4. IK analítico 3D exato das pernas casando a ordem matricial de ``LowerBody.apply`` (``Rx(P)·Ry(R)·Rz(Y)``):
     preserva pernas esticadas (~0° joelho), joelhos dobrados (até 145°) e pernas cruzadas/de índio, com
     alívio posado de colisão perna-tronco/cabeça e pé-pé.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sejoga.animacao import braco_tuning as bt  # noqa: E402
from sejoga.animacao.colisao_bracos import penetracao_do_lado  # noqa: E402
from sejoga.animacao.primitivas_colisao import (  # noqa: E402
    CaixaOrientada,
    Capsula,
    penetracao_capsula_caixa,
    penetracao_capsula_capsula,
)
from sejoga.nucleo import cinematica as cin  # noqa: E402
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rotation3  # noqa: E402
from sejoga.nucleo.modelo import Model, load_model  # noqa: E402
from sejoga.nucleo.recursos import resolve_model  # noqa: E402

try:
    import bpy  # type: ignore[import-not-found]
except ImportError:
    bpy = None

#: Taxa nativa dos clipes do Fortnite / Unreal Engine.
FPS_UE_NATIVO = 30.0

MAPA_EMOTES_PADRAO: dict[str, str] = {
    "electro_swing": "Electro Swing.blend",
    "passinho": "Fancy Feet.blend",
    "master_of_mystery": "Void Redemption.blend",
    "she_bugging": "Shimmy.blend",
    "miku": "Chew.blend",
    "dont_start_now": "Farewell.blend",
    "popular": "Fiesta Flame.blend",
    "griddy": "Griddle.blend",
    "boogie_down": "Boogie Down.blend",
    "jabba_switchway": "Downward.blend",
    "go_mufasa": "Sandwich Bop.blend",
    "breakdance": "Breakdance.blend",
    "aloa": "Aloa.blend",
    "bbd": "BBD.blend",
    "celebration_dance": "Celebration Dance.blend",
    "criss_cross": "Criss Cross.blend",
    "cyclone_headbang": "Cyclone Headbang.blend",
    "january_bop": "January Bop.blend",
    "jazz_dance": "Jazz Dance.blend",
    "jiggle": "Jiggle.blend",
    "kpop_dance_03": "KPOP Dance 03.blend",
    "lets_begin": "Let's Begin.blend",
    "macaroons": "Macaroons.blend",
    "speed_dial": "Speed Dial.blend",
}

#: (bpm_nativo, multiplicador_velocidade) calibrados por dança (FPS UE nativo = 30.0).
MAPA_TEMPO_EMOTES: dict[str, tuple[float, float]] = {
    "aloa": (92.0, 0.94),
    "bbd": (96.0, 0.96),
    "boogie_down": (109.0, 1.00),
    "breakdance": (124.0, 0.94),
    "celebration_dance": (122.0, 1.02),
    "criss_cross": (100.0, 1.00),
    "cyclone_headbang": (140.0, 1.06),
    "dont_start_now": (124.0, 1.00),
    "electro_swing": (120.0, 1.02),
    "go_mufasa": (126.0, 1.02),
    "griddy": (138.0, 1.04),
    "jabba_switchway": (102.0, 0.96),
    "january_bop": (116.0, 1.00),
    "jazz_dance": (112.0, 0.96),
    "jiggle": (106.0, 0.98),
    "kpop_dance_03": (125.0, 1.02),
    "lets_begin": (114.0, 0.96),
    "macaroons": (118.0, 0.98),
    "master_of_mystery": (120.0, 0.96),
    "miku": (132.0, 1.02),
    "passinho": (115.0, 1.04),
    "popular": (99.0, 0.96),
    "she_bugging": (104.0, 0.98),
    "speed_dial": (95.0, 0.94),
}

#: Clipes Mixamo (.fbx) suportados em lote via ``--mixamo-dir``.
MAPA_MIXAMO: dict[str, dict[str, Any]] = {
    "arm_stretching": {
        "arquivo": "Arm Stretching.fbx",
        "pasta": "acoes",
        "bpm": 92.0,
        "vel": 1.00,
        "loop": True,
    },
    "baseball_hit": {
        "arquivo": "Baseball Hit.fbx",
        "pasta": "acoes",
        "bpm": 120.0,
        "vel": 1.15,
        "loop": False,
    },
    "boxing": {
        "arquivo": "Boxing.fbx",
        "pasta": "acoes",
        "bpm": 130.0,
        "vel": 1.08,
        "loop": True,
    },
    "breakdance_1990": {
        "arquivo": "Breakdance 1990.fbx",
        "pasta": "loops",
        "bpm": 128.0,
        "vel": 1.00,
        "loop": True,
        "fechar_retorno": True,
    },
    "breakdance_freeze": {
        "arquivo": "Breakdance Freeze Var 2.fbx",
        "pasta": "loops",
        "bpm": 118.0,
        "vel": 1.00,
        "loop": True,
    },
    "breakdance_uprock": {
        "arquivo": "Breakdance Uprock Var 2.fbx",
        "pasta": "loops",
        "bpm": 122.0,
        "vel": 1.02,
        "loop": True,
    },
    "cover_to_stand": {
        "arquivo": "Cover To Stand.fbx",
        "pasta": "acoes",
        "bpm": 110.0,
        "vel": 1.00,
        "loop": False,
    },
    "dancing_twerk": {
        "arquivo": "Dancing Twerk.fbx",
        "pasta": "loops",
        "bpm": 112.0,
        "vel": 1.00,
        "loop": True,
    },
    "dodging_right": {
        "arquivo": "Dodging Right.fbx",
        "pasta": "acoes",
        "bpm": 120.0,
        "vel": 1.10,
        "loop": False,
    },
    "flair": {
        "arquivo": "Flair.fbx",
        "pasta": "loops",
        "bpm": 126.0,
        "vel": 0.92,
        "loop": True,
        "repetir": 2,
    },
    "drop_kick": {
        "arquivo": "Goalkeeper Drop Kick.fbx",
        "pasta": "acoes",
        "bpm": 120.0,
        "vel": 1.12,
        "loop": False,
    },
    "walk_strafe_left": {
        "arquivo": "Left Strafe Walking.fbx",
        "pasta": "acoes",
        "bpm": 116.0,
        "vel": 1.05,
        "loop": True,
        "centralizar_yaw": True,
    },
    "walk_strafe_right": {
        "arquivo": "Right Strafe Walk.fbx",
        "pasta": "acoes",
        "bpm": 116.0,
        "vel": 1.05,
        "loop": True,
        "centralizar_yaw": True,
    },
    "run_mixamo": {
        "arquivo": "Running.fbx",
        "pasta": "acoes",
        "bpm": 152.0,
        "vel": 1.05,
        "loop": True,
        "inicio": 31,
        "fim": 47,
        "centralizar_yaw": True,
    },
    "walk_standard": {
        "arquivo": "Standard Walk.fbx",
        "pasta": "acoes",
        "bpm": 110.0,
        "vel": 1.05,
        "loop": True,
        "centralizar_yaw": True,
    },
    "swimming": {
        "arquivo": "Swimming.fbx",
        "pasta": "acoes",
        "bpm": 108.0,
        "vel": 1.05,
        "loop": True,
    },
    "walk_strafe_slow": {
        "arquivo": "Walk Strafe Left.fbx",
        "pasta": "acoes",
        "bpm": 100.0,
        "vel": 1.00,
        "loop": True,
        "centralizar_yaw": True,
    },
}

MODEL_FLOOR_Z = 0.0977

# Geometria medida do repouso das pernas do Mário em coordenadas de MODELO (+X esq, -Y frente, +Z cima)
_HIP_REST = {"left": (0.0956, 0.0008, 0.4562), "right": (-0.0956, 0.0008, 0.4562)}
_KNEE_REST = {"left": (0.1187, 0.0008, 0.3500), "right": (-0.1187, 0.0008, 0.3500)}
_ANKLE_REST = {"left": (0.1250, 0.0000, 0.2500), "right": (-0.1250, 0.0000, 0.2500)}
_TOE_OFFSET_MODEL = (0.0, -0.185, -0.095)
_PIVO_CINTURA_AUT = (0.0, 0.0, 0.4375)

# Caixas no espaço local do TRONCO / CABEÇA em autoria (+X dir, +Y frente, +Z cima).
# Camiseta/peitoral começa em z=0.455 para não gerar colisão falsa no joelho/coxa em pé (z=0.35..0.42),
# bloqueando entradas reais de joelho, canela ou bota dentro do abdômen, peito e TV.
_CAIXA_TORSO_PERNA = CaixaOrientada(
    centro=(0.0, 0.000, 0.595),
    eixos=(cin.EIXO_DIREITA, cin.EIXO_FRENTE, cin.EIXO_CIMA),
    meias_dim=(0.168, 0.138, 0.140),  # Z cobre 0.455..0.735 sem falso positivo em pé
)
_CAIXA_CABECA_PERNA = CaixaOrientada(
    centro=(0.0, 0.0, 0.90),
    eixos=(cin.EIXO_DIREITA, cin.EIXO_FRENTE, cin.EIXO_CIMA),
    meias_dim=(0.175, 0.145, 0.205),
)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _wrap_pi(ang: float) -> float:
    return ((ang + math.pi) % math.tau) - math.pi


def _pt_autoria(v: Any) -> cin.Vec3:
    """Converte ponto/vetor do mundo Blender (+X esq, -Y frente, +Z cima) para autoria (+X dir, +Y frente, +Z cima)."""
    return (-float(v[0]), -float(v[1]), float(v[2]))


def _conj_autoria(m: Any) -> cin.Mat3:
    """Conjuga matriz 3x3 do mundo Blender por S = diag(-1, -1, 1) para o espaço de autoria."""
    return (
        float(m[0][0]),
        float(m[0][1]),
        -float(m[0][2]),
        float(m[1][0]),
        float(m[1][1]),
        -float(m[1][2]),
        -float(m[2][0]),
        -float(m[2][1]),
        float(m[2][2]),
    )


def _frame_ortonormal(eixo_x_bruto: cin.Vec3, eixo_z_bruto: cin.Vec3) -> cin.Mat3:
    """Constrói matriz 3x3 ortonormal (colunas X=direita, Y=frente, Z=cima) a partir de marcos anatômicos."""
    x = cin.normalizar(eixo_x_bruto)
    if cin.norma(x) < 1e-6:
        x = cin.EIXO_DIREITA
    proj = cin.produto_escalar(eixo_z_bruto, x)
    z = cin.normalizar(cin.subtrair(eixo_z_bruto, cin.escalar(x, proj)))
    if cin.norma(z) < 1e-6:
        z = cin.EIXO_CIMA
    y = cin.normalizar(cin.produto_vetorial(z, x))
    z = cin.normalizar(cin.produto_vetorial(x, y))
    return (
        x[0], y[0], z[0],
        x[1], y[1], z[1],
        x[2], y[2], z[2],
    )


def _rot_mat_model(rx_deg: float, ry_deg: float, rz_deg: float) -> cin.Mat3:
    """Matriz de rotação 3x3 equivalente a ``Mat4.rotateMat(rx, X) * rotateMat(ry, Y) * rotateMat(rz, Z)``."""
    px, py, pz = math.radians(rx_deg), math.radians(ry_deg), math.radians(rz_deg)
    cx, sx = math.cos(px), math.sin(px)
    cy, sy = math.cos(py), math.sin(py)
    cz, sz = math.cos(pz), math.sin(pz)
    rx = (1.0, 0.0, 0.0, 0.0, cx, -sx, 0.0, sx, cx)
    ry = (cy, 0.0, sy, 0.0, 1.0, 0.0, -sy, 0.0, cy)
    rz = (cz, -sz, 0.0, sz, cz, 0.0, 0.0, 0.0, 1.0)
    return cin.mul(rz, cin.mul(ry, rx))


def _rot_entre_vetores(ua: cin.Vec3, ub: cin.Vec3) -> cin.Mat3:
    """Matriz mínima 3x3 de transporte paralelo alinhando ``ua`` a ``ub``."""
    d = _clamp(cin.produto_escalar(ua, ub), -1.0, 1.0)
    if d > 0.9998:
        return cin.IDENTIDADE
    v = cin.produto_vetorial(ua, ub)
    nv = cin.norma(v)
    if nv < 1e-5:
        ref = cin.EIXO_FRENTE if abs(ua[1]) < 0.9 else cin.EIXO_CIMA
        eixo = cin.normalizar(cin.produto_vetorial(ua, ref))
        return cin.rot_eixo(eixo, math.pi)
    return cin.rot_eixo(cin.escalar(v, 1.0 / nv), math.acos(d))


def _projetar_perp(v: cin.Vec3, u: cin.Vec3) -> cin.Vec3:
    """Projeta ``v`` ortogonalmente a ``u`` unitário com fallback seguro."""
    perp = cin.subtrair(v, cin.escalar(u, cin.produto_escalar(v, u)))
    if cin.norma(perp) < 1e-4:
        ref = cin.EIXO_FRENTE if abs(u[1]) < 0.9 else cin.EIXO_CIMA
        perp = cin.subtrair(ref, cin.escalar(u, cin.produto_escalar(ref, u)))
    if cin.norma(perp) < 1e-4:
        perp = cin.subtrair(cin.EIXO_DIREITA, cin.escalar(u, u[0]))
    return cin.normalizar(perp)


def _ang_no_plano(a: cin.Vec3, b: cin.Vec3, eixo: cin.Vec3) -> float:
    """Ângulo com sinal de ``a`` até ``b`` em torno de ``eixo`` unitário."""
    c = cin.produto_vetorial(a, b)
    return math.atan2(
        cin.produto_escalar(eixo, c), _clamp(cin.produto_escalar(a, b), -1.0, 1.0)
    )


def _ancoras_dobradica(
    geom: list[cin.Vec3],
    sin_a: list[float],
    sin_limiar: float = 0.22,
) -> list[bool]:
    """Identifica âncoras confiáveis descartando inversões isoladas com pouca dobra."""
    n = len(geom)
    ok = [sin_a[t] >= sin_limiar for t in range(n)]
    for t in range(n):
        if not ok[t] or sin_a[t] >= 0.58:
            continue
        p = next((j for j in range(t - 1, max(-1, t - 5), -1) if ok[j]), -1)
        q = next((j for j in range(t + 1, min(n, t + 5)) if ok[j]), -1)
        if p < 0 or q < 0:
            continue
        if (
            cin.produto_escalar(geom[p], geom[q]) > 0.25
            and cin.produto_escalar(geom[t], geom[p]) < -0.32
            and cin.produto_escalar(geom[t], geom[q]) < -0.32
        ):
            ok[t] = False
    return ok


def _propagar_eixo_dobradica(
    u1_seq: list[cin.Vec3],
    geom: list[cin.Vec3],
    ancora_ok: list[bool],
    indices: range,
    passo_ant: int,
) -> tuple[list[cin.Vec3 | None], list[int]]:
    """Propaga eixos confiáveis de dobra via transporte paralelo em um sentido."""
    n = len(u1_seq)
    transp: list[cin.Vec3 | None] = [None] * n
    ancora = [-1] * n
    atual: cin.Vec3 | None = None
    ult = -1
    for t in indices:
        if ancora_ok[t]:
            atual = geom[t]
            ult = t
        elif atual is not None:
            rot = _rot_entre_vetores(u1_seq[t + passo_ant], u1_seq[t])
            atual = _projetar_perp(cin.aplicar(rot, atual), u1_seq[t])
        transp[t] = atual
        ancora[t] = ult
    return transp, ancora


def _suavizar_eixos_dobradica(
    u1_seq: list[cin.Vec3],
    u2_seq: list[cin.Vec3],
    osso_seq: list[cin.Vec3],
    sin_limiar: float = 0.22,
) -> list[cin.Vec3]:
    """Transporta e interpola o eixo normal de dobra em segmentos esticados."""
    n = len(u1_seq)
    if n == 0:
        return []
    sin_a = [cin.norma(cin.produto_vetorial(u1_seq[t], u2_seq[t])) for t in range(n)]
    geom = [
        cin.escalar(cin.produto_vetorial(u1_seq[t], u2_seq[t]), 1.0 / sin_a[t])
        if sin_a[t] > 0.08
        else _projetar_perp(osso_seq[t], u1_seq[t])
        for t in range(n)
    ]
    ancora_ok = _ancoras_dobradica(geom, sin_a, sin_limiar=sin_limiar)
    fwd, prev_anc = _propagar_eixo_dobradica(u1_seq, geom, ancora_ok, range(n), -1)
    bwd, next_anc = _propagar_eixo_dobradica(
        u1_seq, geom, ancora_ok, range(n - 1, -1, -1), 1
    )
    if all(x is None for x in fwd):
        out = [geom[0]]
        for t in range(1, n):
            rot = _rot_entre_vetores(u1_seq[t - 1], u1_seq[t])
            out.append(_projetar_perp(cin.aplicar(rot, out[-1]), u1_seq[t]))
        return out

    res: list[cin.Vec3] = []
    for t in range(n):
        ft, btv = fwd[t], bwd[t]
        if ft is not None and btv is not None:
            pa, na = prev_anc[t], next_anc[t]
            frac = (t - pa) / (na - pa) if na > pa else 0.0
            ang = _ang_no_plano(ft, btv, u1_seq[t])
            est = _projetar_perp(
                cin.aplicar(cin.rot_eixo(u1_seq[t], ang * frac), ft), u1_seq[t]
            )
        else:
            est = ft if ft is not None else (btv if btv is not None else geom[t])
        conf = _smoothstep((sin_a[t] - 0.14) / 0.32)
        if conf > 1e-4 and sin_a[t] > 0.08:
            ang_g = _ang_no_plano(est, geom[t], u1_seq[t])
            if not (sin_a[t] < 0.58 and abs(ang_g) > 2.0):
                est = _projetar_perp(
                    cin.aplicar(cin.rot_eixo(u1_seq[t], ang_g * conf), est), u1_seq[t]
                )
        res.append(est)
    return res


def _avaliar_ombro_candidato(
    base: cin.Mat3,
    p_raw: float,
    h_raw: float,
    r_raw: float,
    ant: tuple[float, float, float] | None,
) -> tuple[float, tuple[float, float, float]]:
    """Calcula custo contínuo (sem degraus) e tupla ``(p, h, r)`` clampeada."""
    h_lim = math.radians(bt.OMBRO_AZIMUTE_MAX_GRAUS - 3.0)
    r_min = math.radians(bt.OMBRO_ELEVACAO_MIN_GRAUS + 3.0)
    r_max = math.radians(bt.OMBRO_ELEVACAO_MAX_GRAUS - 3.0)

    h = _wrap_pi(h_raw)
    r = _wrap_pi(r_raw)
    p = _desembrulhar_angulo(p_raw, ant[0]) if ant is not None else _wrap_pi(p_raw)
    h_c = _clamp(h, -h_lim, h_lim)
    r_c = _clamp(r, r_min, r_max)

    m_c = cin.rot_hpr(h_c, p, r_c)
    err_3d = max(0.0, 3.0 - sum(m_c[i] * base[i] for i in range(9)))
    over2 = (h - h_c) ** 2 + (r - r_c) ** 2
    custo = 45.0 * err_3d + 4.0 * over2
    if ant is None:
        custo += 0.08 * (p * p + h_c * h_c + r_c * r_c)
    else:
        custo += (p - ant[0]) ** 2 + (h_c - ant[1]) ** 2 + (r_c - ant[2]) ** 2
    return custo, (p, h_c, r_c)


def _eixo_dobra_braco(
    dobra_geom: cin.Vec3,
    dobra_osso: cin.Vec3,
) -> cin.Vec3:
    """Seleciona eixo de dobra do cotovelo sem inverter o plano suavizado por ruído."""
    n_dg = cin.norma(dobra_geom)
    if n_dg >= 0.58:
        return cin.normalizar(dobra_geom)
    if n_dg > 0.22:
        dg = cin.normalizar(dobra_geom)
        if cin.produto_escalar(dg, dobra_osso) >= -0.25:
            w = _smoothstep((n_dg - 0.22) / 0.36)
            return cin.normalizar(
                (
                    dobra_osso[0] + (dg[0] - dobra_osso[0]) * w,
                    dobra_osso[1] + (dg[1] - dobra_osso[1]) * w,
                    dobra_osso[2] + (dg[2] - dobra_osso[2]) * w,
                )
            )
    return dobra_osso


def _base_braco_quadro(
    lado: str,
    u_braco: cin.Vec3,
    u_antebraco: cin.Vec3,
    u_dobra_osso: cin.Vec3,
) -> tuple[float, cin.Mat3]:
    """Constrói flexão do cotovelo e matriz-alvo ortonormal ``base`` do ombro direito equivalente."""
    u1 = cin.normalizar(cin.espelhar_ponto(u_braco) if lado == "left" else u_braco)
    u2 = cin.normalizar(cin.espelhar_ponto(u_antebraco) if lado == "left" else u_antebraco)
    ub_osso = cin.espelhar_ponto(u_dobra_osso) if lado == "left" else u_dobra_osso

    cos_c = _clamp(cin.produto_escalar(u1, u2), -1.0, 1.0)
    flexao = _clamp(math.acos(cos_c), 0.0, math.radians(bt.COTOVELO_MAX_GRAUS - 4.0))
    dobra_geom = cin.subtrair(u2, cin.escalar(u1, cos_c))
    u_bend = _eixo_dobra_braco(dobra_geom, _projetar_perp(ub_osso, u1))

    terceiro = cin.normalizar(cin.produto_vetorial(u1, u_bend))
    u_bend = cin.normalizar(cin.produto_vetorial(terceiro, u1))
    base: cin.Mat3 = (
        u1[0], u_bend[0], terceiro[0],
        u1[1], u_bend[1], terceiro[1],
        u1[2], u_bend[2], terceiro[2],
    )
    return flexao, base


def _candidatos_gimbal_ombro(
    base: cin.Mat3,
    ant_ombro: tuple[float, float, float] | None,
) -> list[tuple[float, float, float]]:
    """Gera candidatos equivalentes em ``(p, h, r)`` ao atravessar gimbal do ombro."""
    if abs(base[7]) <= 0.62:
        return []
    r_min = math.radians(bt.OMBRO_ELEVACAO_MIN_GRAUS + 3.0)
    r_max = math.radians(bt.OMBRO_ELEVACAO_MAX_GRAUS - 3.0)
    if ant_ombro is None:
        alvos_r = [math.radians(g) for g in (-150.0, -125.0, -100.0, -75.0, -50.0, -25.0, 0.0, 25.0, 50.0, 75.0, 100.0, 125.0)]
    else:
        r_ant = _clamp(ant_ombro[2], r_min, r_max)
        offsets = (0.0, 0.16, -0.16, 0.36, -0.36, 0.60, -0.60, 0.95, -0.95)
        alvos_r = [_clamp(r_ant + d, r_min, r_max) for d in offsets] + [_clamp(r_ant * 0.5, r_min, r_max), 0.0]
    out: list[tuple[float, float, float]] = []
    vistos: set[int] = set()
    for r_raw in alvos_r:
        r_g = _clamp(r_raw, r_min, r_max)
        chave = round(r_g * 1000)
        if chave in vistos:
            continue
        vistos.add(chave)
        m_no_r = cin.mul(base, cin.rot_y(-r_g))
        h_g = math.atan2(m_no_r[3], m_no_r[0])
        m_p = cin.mul(cin.rot_z(-h_g), m_no_r)
        out.append((math.atan2(m_p[7], m_p[4]), h_g, r_g))
    return out


def _cands_ombro_viterbi(base: cin.Mat3) -> list[tuple[float, tuple[float, float, float]]]:
    """Lista nós candidatos em um quadro com custo local (fidelidade 3D + margem de limite)."""
    h0, p0, r0 = cin.hpr_de_matriz(base)
    brutos = [(p0, h0, r0), (math.pi - p0, h0 + math.pi, r0 + math.pi), *_candidatos_gimbal_ombro(base, None)]
    h_lim = math.radians(bt.OMBRO_AZIMUTE_MAX_GRAUS - 3.0)
    r_min = math.radians(bt.OMBRO_ELEVACAO_MIN_GRAUS + 3.0)
    r_max = math.radians(bt.OMBRO_ELEVACAO_MAX_GRAUS - 3.0)
    res: list[tuple[float, tuple[float, float, float]]] = []
    for p_raw, h_raw, r_raw in brutos:
        h, r = _wrap_pi(h_raw), _wrap_pi(r_raw)
        h_c, r_c = _clamp(h, -h_lim, h_lim), _clamp(r, r_min, r_max)
        p_c = _wrap_pi(p_raw)
        m_c = cin.rot_hpr(h_c, p_c, r_c)
        err_3d = max(0.0, 3.0 - sum(m_c[i] * base[i] for i in range(9)))
        over2 = (h - h_c) ** 2 + (r - r_c) ** 2
        custo = 45.0 * err_3d + 6.0 * over2 + 0.004 * (h_c * h_c + r_c * r_c)
        res.append((custo, (p_c, h_c, r_c)))
    return res


def _passo_viterbi_ombro(
    dp_ant: list[float],
    est_ant: list[tuple[float, float, float]],
    cands_cur: list[tuple[float, tuple[float, float, float]]],
) -> tuple[list[float], list[int]]:
    """Avança um passo da programação dinâmica minimizando salto entre ramos."""
    dp_novo: list[float] = []
    ptrs: list[int] = []
    for custo_no, (pc, hc, rc) in cands_cur:
        melhor_i = 0
        melhor_v = float("inf")
        for i_prev, ((pa, ha, ra), base_c) in enumerate(zip(est_ant, dp_ant, strict=True)):
            dp_ang = _wrap_pi(pc - pa)
            trans = dp_ang * dp_ang + (hc - ha) ** 2 + (rc - ra) ** 2
            tot = base_c + custo_no + 1.15 * trans
            if tot < melhor_v:
                melhor_v = tot
                melhor_i = i_prev
        dp_novo.append(melhor_v)
        ptrs.append(melhor_i)
    return dp_novo, ptrs


def _resolver_trilha_ombro(bases: list[cin.Mat3]) -> list[tuple[float, float, float]]:
    """Encontra a trajetória globalmente contínua de ``(p, h, r)`` evitando becos de clamp."""
    if not bases:
        return []
    camadas = [_cands_ombro_viterbi(b) for b in bases]
    dp = [c + 0.04 * (s[0] * s[0] + s[1] * s[1] + s[2] * s[2]) for c, s in camadas[0]]
    backs: list[list[int]] = []
    for t in range(1, len(camadas)):
        est_ant = [s for _, s in camadas[t - 1]]
        dp, ptrs = _passo_viterbi_ombro(dp, est_ant, camadas[t])
        backs.append(ptrs)
    idx = min(range(len(dp)), key=dp.__getitem__)
    rev = [camadas[-1][idx][1]]
    for t in range(len(backs) - 1, -1, -1):
        idx = backs[t][idx]
        rev.append(camadas[t][idx][1])
    seq = list(reversed(rev))
    out = [seq[0]]
    for t in range(1, len(seq)):
        p_u = _desembrulhar_angulo(seq[t][0], out[-1][0])
        out.append((p_u, seq[t][1], seq[t][2]))
    return out


def _resolver_braco_1para1(
    lado: str,
    u_braco: cin.Vec3,
    u_antebraco: cin.Vec3,
    u_dobra_osso: cin.Vec3,
    ant_ombro: tuple[float, float, float] | None,
) -> tuple[Rotation3, Rotation3, tuple[float, float, float]]:
    """Resolve ombro e cotovelo em 3D exato com ramo contínuo e estabilidade de gimbal."""
    flexao, base = _base_braco_quadro(lado, u_braco, u_antebraco, u_dobra_osso)
    h0, p0, r0 = cin.hpr_de_matriz(base)
    cands: list[tuple[float, float, float]] = [
        (p0, h0, r0),
        (math.pi - p0, h0 + math.pi, r0 + math.pi),
        *_candidatos_gimbal_ombro(base, ant_ombro),
    ]
    _custo, (p, h, r) = min(
        (_avaliar_ombro_candidato(base, cp, ch, cr, ant_ombro) for cp, ch, cr in cands),
        key=lambda item: item[0],
    )
    rot_ombro = Rotation3(p, h, r)
    rot_cotovelo = Rotation3(0.0, 0.0, flexao)
    if lado == "left":
        return cin.espelhar_rotacao(rot_ombro), cin.espelhar_rotacao(rot_cotovelo), (p, h, r)
    return rot_ombro, rot_cotovelo, (p, h, r)


def _penetracao_braco_posed(
    model: Model,
    lado: str,
    pose: dict[str, Rotation3],
) -> float:
    """Mede penetração do braço contra tronco/cabeça (idêntico a ``penetracao_do_lado``)."""
    return penetracao_do_lado(model, lado, pose)


def _melhor_ajuste_braco(
    model: Model,
    pose: dict[str, Rotation3],
    lado: str,
    g_om: str,
    g_co: str,
    pen_atual: float,
    passo_deg: float,
    limites: tuple[float, float, float, float],
) -> tuple[float, Rotation3, Rotation3] | None:
    """Testa um passo pequeno em ombro/cotovelo para aliviar penetração."""
    h_min, h_max, r_min, r_max = limites
    sinal_lado = 1.0 if lado == "right" else -1.0
    passo = math.radians(passo_deg)
    ro_atual = pose[g_om]
    rc_atual = pose[g_co]
    flex_max = math.radians(bt.COTOVELO_MAX_GRAUS - 4.0)
    flex_menor = max(0.0, abs(rc_atual.z) - passo) * sinal_lado
    flex_maior = min(flex_max, abs(rc_atual.z) + passo) * sinal_lado
    candidatos = (
        (Rotation3(ro_atual.x, _clamp(ro_atual.y + sinal_lado * passo, h_min, h_max), ro_atual.z), rc_atual),
        (Rotation3(ro_atual.x, _clamp(ro_atual.y - sinal_lado * passo, h_min, h_max), ro_atual.z), rc_atual),
        (Rotation3(ro_atual.x, ro_atual.y, _clamp(ro_atual.z - sinal_lado * passo, r_min, r_max)), rc_atual),
        (Rotation3(ro_atual.x, ro_atual.y, _clamp(ro_atual.z + sinal_lado * passo, r_min, r_max)), rc_atual),
        (ro_atual, Rotation3(0.0, 0.0, flex_menor)),
        (ro_atual, Rotation3(0.0, 0.0, flex_maior)),
    )
    melhor: tuple[float, Rotation3, Rotation3] | None = None
    melhor_pen = pen_atual
    for ro_cand, rc_cand in candidatos:
        pose[g_om] = ro_cand
        pose[g_co] = rc_cand
        p_cand = _penetracao_braco_posed(model, lado, pose)
        if p_cand < melhor_pen - 1e-4:
            melhor_pen = p_cand
            melhor = (p_cand, ro_cand, rc_cand)
    pose[g_om] = ro_atual
    pose[g_co] = rc_atual
    return melhor


def _aliviar_lado_braco(
    model: Model,
    pose: dict[str, Rotation3],
    lado: str,
    g_om: str,
    g_co: str,
    max_iter: int,
    limites: tuple[float, float, float, float],
) -> None:
    """Afasta um braço suavemente apenas quando há penetração relevante."""
    pen = _penetracao_braco_posed(model, lado, pose)
    if pen <= 0.014:
        return
    for _ in range(max_iter):
        if pen <= 0.014:
            break
        melhor = None
        for passo_deg in (2.0, 4.5):
            melhor = _melhor_ajuste_braco(model, pose, lado, g_om, g_co, pen, passo_deg, limites)
            if melhor is not None:
                break
        if melhor is None:
            break
        pen, pose[g_om], pose[g_co] = melhor


def _aliviar_colisao_pose(
    model: Model,
    pose: dict[str, Rotation3],
    max_iter: int = 5,
) -> None:
    """Afasta minimamente os braços caso atravessem tronco ou cabeça."""
    limites = (
        math.radians(bt.OMBRO_AZIMUTE_MIN_GRAUS + 2.0),
        math.radians(bt.OMBRO_AZIMUTE_MAX_GRAUS - 2.0),
        math.radians(bt.OMBRO_ELEVACAO_MIN_GRAUS + 2.0),
        math.radians(bt.OMBRO_ELEVACAO_MAX_GRAUS - 2.0),
    )
    for lado, g_om, g_co in (
        ("right", "right-arm", "ant-arm"),
        ("left", "left-arm", "ant-arm2"),
    ):
        _aliviar_lado_braco(model, pose, lado, g_om, g_co, max_iter, limites)


def _rot3_para_mat(r: Rotation3) -> cin.Mat3:
    return cin.rot_hpr(r.y, r.x, r.z)


def _rot_pose_tronco(pose: dict[str, Rotation3]) -> cin.Mat3:
    m_c = _rot3_para_mat(pose.get("cintura", Rotation3()))
    m_a = _rot3_para_mat(pose.get("abdomen", Rotation3()))
    m_p = _rot3_para_mat(pose.get("peitoral", Rotation3()))
    return cin.mul(m_c, cin.mul(m_a, m_p))


def _somar_rot_pivo(p: cin.Vec3, m: cin.Mat3, pivo: cin.Vec3) -> cin.Vec3:
    rel = cin.subtrair(p, pivo)
    rot = cin.aplicar(m, rel)
    return (rot[0] + pivo[0], rot[1] + pivo[1], rot[2] + pivo[2])


def _transformar_caixa(caixa: CaixaOrientada, m: cin.Mat3, pivo: cin.Vec3) -> CaixaOrientada:
    return CaixaOrientada(
        centro=_somar_rot_pivo(caixa.centro, m, pivo),
        eixos=(
            cin.aplicar(m, caixa.eixos[0]),
            cin.aplicar(m, caixa.eixos[1]),
            cin.aplicar(m, caixa.eixos[2]),
        ),
        meias_dim=caixa.meias_dim,
    )


def _wrap180_deg(ang: float) -> float:
    return ((ang + 180.0) % 360.0) - 180.0


def _solve_leg_from_ek(
    u_th: cin.Vec3,
    ek: cin.Vec3,
) -> tuple[float, float, float]:
    """Calcula ``(p_deg, r_deg, y_deg)`` a partir de ``u_th`` e eixo de joelho ``ek``."""
    r_deg = math.degrees(-math.asin(_clamp(ek[2], -1.0, 1.0)))
    y_deg = math.degrees(math.atan2(ek[1], ek[0])) if math.hypot(ek[0], ek[1]) > 1e-4 else 0.0
    cy, sy = math.cos(math.radians(-y_deg)), math.sin(math.radians(-y_deg))
    cr, sr = math.cos(math.radians(-r_deg)), math.sin(math.radians(-r_deg))
    ub_x = u_th[0] * cy - u_th[1] * sy
    ub_y = u_th[0] * sy + u_th[1] * cy
    ub_z = u_th[2]
    ub_y2 = ub_y
    ub_z2 = -ub_x * sr + ub_z * cr
    p_deg = math.degrees(math.atan2(ub_y2, -ub_z2))
    return _wrap180_deg(p_deg), _wrap180_deg(r_deg), _wrap180_deg(y_deg)


def _eval_leg_cand(
    p_raw: float,
    r_raw: float,
    y_raw: float,
    u_th: cin.Vec3,
    ek_alvo: cin.Vec3,
    ant_pry: tuple[float, float, float] | None,
    peso_ek: float = 1.5,
) -> tuple[float, tuple[float, float, float]]:
    """Pontua candidato de perna por fidelidade 3D pós-clamp e continuidade."""
    p_c = _clamp(_wrap180_deg(p_raw), -132.0, 92.0)
    r_c = _clamp(_wrap180_deg(r_raw), -84.0, 84.0)
    y_c = _clamp(_wrap180_deg(y_raw), -112.0, 112.0)
    m_q = _rot_mat_model(p_c, r_c, y_c)
    th_got = cin.aplicar(m_q, (0.0, 0.0, -1.0))
    ek_got = cin.aplicar(m_q, (1.0, 0.0, 0.0))
    dot_th = _clamp(cin.produto_escalar(th_got, u_th), -1.0, 1.0)
    dot_ek = _clamp(cin.produto_escalar(ek_got, ek_alvo), -1.0, 1.0)
    err_3d = 40.0 * (1.0 - dot_th) + peso_ek * (1.0 - dot_ek)
    if ant_pry is None:
        cont = 0.0005 * (p_c * p_c + r_c * r_c + y_c * y_c)
    else:
        dp = _wrap180_deg(p_c - ant_pry[0])
        dr = r_c - ant_pry[1]
        dy = y_c - ant_pry[2]
        cont = 0.0012 * (dp * dp + dr * dr + dy * dy)
    return err_3d + cont, (p_c, r_c, y_c)


def _eixo_joelho_frame(
    u_th: cin.Vec3,
    u_sh: cin.Vec3,
    ek_bone: cin.Vec3,
) -> tuple[float, cin.Vec3]:
    """Calcula ângulo e eixo normal contínuo do joelho evitando inversões ruidosas."""
    ek_perp = _projetar_perp(ek_bone, u_th)
    dot_knee = _clamp(cin.produto_escalar(u_th, u_sh), -1.0, 1.0)
    ang_joelho = math.degrees(math.acos(dot_knee))
    cross_g = cin.produto_vetorial(u_th, u_sh)
    n_cg = cin.norma(cross_g)
    if n_cg >= 0.45:
        ek = cin.normalizar(cross_g)
    elif n_cg > 0.14:
        ek_g = cin.normalizar(cross_g)
        if cin.produto_escalar(ek_g, ek_perp) >= -0.25:
            w = _smoothstep((n_cg - 0.14) / 0.31)
            ek = cin.normalizar(
                (
                    ek_perp[0] + (ek_g[0] - ek_perp[0]) * w,
                    ek_perp[1] + (ek_g[1] - ek_perp[1]) * w,
                    ek_perp[2] + (ek_g[2] - ek_perp[2]) * w,
                )
            )
        else:
            ek = ek_perp
    else:
        ek = ek_perp
    return ang_joelho, _projetar_perp(ek, u_th)


def _candidatos_perna_ik(
    u_th: cin.Vec3,
    ek: cin.Vec3,
    ant_perna: tuple[float, float, float] | None,
) -> list[tuple[float, float, float]]:
    """Lista ramos analíticos, sagitais e de gimbal para a articulação do quadril."""
    p0, r0, y0 = _solve_leg_from_ek(u_th, ek)
    cands: list[tuple[float, float, float]] = [
        (p0, r0, y0),
        (p0 + 180.0, 180.0 - r0, y0 + 180.0),
    ]
    if math.hypot(u_th[0], u_th[1]) > 0.15:
        for base_y in (
            math.degrees(math.atan2(-u_th[0], -u_th[1])),
            math.degrees(math.atan2(u_th[0], u_th[1])),
        ):
            cy_s = math.cos(math.radians(-base_y))
            sy_s = math.sin(math.radians(-base_y))
            uy_s = u_th[0] * sy_s + u_th[1] * cy_s
            p_s = math.degrees(math.atan2(uy_s, -u_th[2]))
            cands.append((p_s, 0.0, base_y))
            cands.append((p_s + 180.0, 180.0, base_y + 180.0))
    if abs(ek[2]) > 0.65 and ant_perna is not None:
        y_ant = ant_perna[2]
        for y_g in (y_ant, 0.0, y_ant - 18.0, y_ant + 18.0, y_ant - 36.0, y_ant + 36.0):
            cy_g = math.cos(math.radians(-y_g))
            sy_g = math.sin(math.radians(-y_g))
            ux1 = u_th[0] * cy_g - u_th[1] * sy_g
            uy1 = u_th[0] * sy_g + u_th[1] * cy_g
            uz1 = u_th[2]
            p_g = math.degrees(math.asin(_clamp(uy1, -1.0, 1.0)))
            r_g = math.degrees(math.atan2(-ux1, -uz1))
            cands.append((p_g, r_g, y_g))
            cands.append((180.0 - p_g, math.degrees(math.atan2(ux1, uz1)), y_g))
    return cands


def _resolver_perna_ik_3d(
    lado: str,
    u_th_aut: cin.Vec3,
    u_sh_aut: cin.Vec3,
    ek_bone_aut: cin.Vec3,
    ant_perna: tuple[float, float, float] | None = None,
) -> tuple[float, float, float, float]:
    """IK analítico 3D exato casando ``LowerBody.apply`` com ramo contínuo e fallback sagital."""
    _ = lado
    u_th = cin.normalizar((-u_th_aut[0], -u_th_aut[1], u_th_aut[2]))
    u_sh = cin.normalizar((-u_sh_aut[0], -u_sh_aut[1], u_sh_aut[2]))
    ek_bone = (-ek_bone_aut[0], -ek_bone_aut[1], ek_bone_aut[2])

    ang_joelho, ek = _eixo_joelho_frame(u_th, u_sh, ek_bone)
    cands = _candidatos_perna_ik(u_th, ek, ant_perna)
    peso_ek = 1.5 * _clamp(ang_joelho / 24.0, 0.05, 1.0)
    _custo, (p_deg, r_deg, y_deg) = min(
        (_eval_leg_cand(cp, cr, cy_c, u_th, ek, ant_perna, peso_ek=peso_ek) for cp, cr, cy_c in cands),
        key=lambda item: item[0],
    )
    k_deg = _clamp(ang_joelho, 0.0, 145.0)
    return p_deg, r_deg, y_deg, k_deg


def _pontos_perna_autoria(
    lado: str,
    p_deg: float,
    r_deg: float,
    y_deg: float,
    k_deg: float,
) -> tuple[cin.Vec3, cin.Vec3, cin.Vec3, cin.Vec3, cin.Vec3]:
    """FK exato da perna em autoria (hip, thigh_distal, knee, ankle, toe) replicando ``LowerBody.apply``."""
    ph = _HIP_REST[lado]
    pk = _KNEE_REST[lado]
    pa = _ANKLE_REST[lado]

    m_quadril = _rot_mat_model(p_deg, r_deg, y_deg)
    m_canela = _rot_mat_model(p_deg + k_deg, r_deg, y_deg)

    v_pk = cin.subtrair(pk, ph)
    v_ka = cin.subtrair(pa, pk)
    k_mod = tuple(ph[i] + cin.aplicar(m_quadril, v_pk)[i] for i in range(3))
    a_mod = tuple(k_mod[i] + cin.aplicar(m_canela, v_ka)[i] for i in range(3))
    t_off = cin.aplicar(m_canela, _TOE_OFFSET_MODEL)
    t_mod = (a_mod[0] + t_off[0], a_mod[1] + t_off[1], a_mod[2] + t_off[2])
    td_mod = (
        ph[0] + (k_mod[0] - ph[0]) * 0.65,
        ph[1] + (k_mod[1] - ph[1]) * 0.65,
        ph[2] + (k_mod[2] - ph[2]) * 0.65,
    )

    def to_aut(v: tuple[float, ...]) -> cin.Vec3:
        return (-v[0], -v[1], v[2])

    return to_aut(ph), to_aut(td_mod), to_aut(k_mod), to_aut(a_mod), to_aut(t_mod)


def _caixas_perna_posed(
    pose_tronco: dict[str, Rotation3],
) -> tuple[CaixaOrientada, ...]:
    r_tr = _rot_pose_tronco(pose_tronco)
    r_hd = cin.mul(r_tr, _rot3_para_mat(pose_tronco.get("head", Rotation3())))
    return (
        _transformar_caixa(_CAIXA_TORSO_PERNA, r_tr, _PIVO_CINTURA_AUT),
        _transformar_caixa(_CAIXA_CABECA_PERNA, r_hd, _PIVO_CINTURA_AUT),
    )


def _penetracao_pernas(
    perna_frame: dict[str, float],
    pose_tronco: dict[str, Rotation3],
    caixas: tuple[CaixaOrientada, ...] | None = None,
) -> float:
    """Mede penetração de joelho, canela e bota no tronco/TV e entre as duas pernas."""
    if caixas is None:
        caixas = _caixas_perna_posed(pose_tronco)

    maior = 0.0
    caps_lado: dict[str, tuple[Capsula, Capsula]] = {}
    for lado in ("left", "right"):
        _h, td, kn, ak, to = _pontos_perna_autoria(
            lado,
            perna_frame[lado],
            perna_frame[f"{lado}_roll"],
            perna_frame[f"{lado}_yaw"],
            perna_frame[f"{lado}_knee"],
        )
        c_coxa = Capsula(a=td, b=kn, raio=0.042)
        c_canela = Capsula(a=kn, b=ak, raio=0.042)
        c_bota = Capsula(a=ak, b=to, raio=0.064)
        caps_lado[lado] = (c_canela, c_bota)

        for cx in caixas:
            maior = max(
                maior,
                penetracao_capsula_caixa(c_coxa, cx),
                penetracao_capsula_caixa(c_canela, cx),
                penetracao_capsula_caixa(c_bota, cx),
            )

    for ca in caps_lado["left"]:
        for cb in caps_lado["right"]:
            maior = max(maior, penetracao_capsula_capsula(ca, cb) - 0.012)

    return maior


def _melhor_ajuste_perna(
    perna_frame: dict[str, float],
    pose_tronco: dict[str, Rotation3],
    caixas: tuple[CaixaOrientada, ...],
    passo: float,
    pen_atual: float,
) -> tuple[float, dict[str, float]] | None:
    """Busca ajuste pequeno em uma perna para reduzir penetração relevante."""
    melhor: tuple[float, dict[str, float]] | None = None
    melhor_pen = pen_atual
    for lado, sinal in (("left", 1.0), ("right", -1.0)):
        p_cur = perna_frame[lado]
        r_cur = perna_frame[f"{lado}_roll"]
        k_cur = perna_frame[f"{lado}_knee"]
        alteracoes = (
            (lado, _clamp(p_cur + passo, -132.0, 92.0)),
            (lado, _clamp(p_cur - passo, -132.0, 92.0)),
            (f"{lado}_roll", _clamp(r_cur - sinal * passo, -84.0, 84.0)),
            (f"{lado}_roll", _clamp(r_cur + sinal * passo, -84.0, 84.0)),
            (f"{lado}_knee", _clamp(k_cur - passo, 0.0, 145.0)),
            (f"{lado}_knee", _clamp(k_cur + passo, 0.0, 145.0)),
        )
        for ch, val in alteracoes:
            if val == perna_frame[ch]:
                continue
            cand = dict(perna_frame)
            cand[ch] = val
            pc = _penetracao_pernas(cand, pose_tronco, caixas=caixas)
            if pc < melhor_pen - 1e-4:
                melhor_pen = pc
                melhor = (pc, cand)
    return melhor


def _aliviar_colisao_pernas(
    perna_frame: dict[str, float],
    pose_tronco: dict[str, Rotation3],
    max_iter: int = 6,
) -> None:
    """Empurra pernas suavemente para fora quando penetram fundo tronco/cabeça ou entre si."""
    caixas = _caixas_perna_posed(pose_tronco)
    pen = _penetracao_pernas(perna_frame, pose_tronco, caixas=caixas)
    if pen <= 0.022:
        return
    for _ in range(max_iter):
        if pen <= 0.022:
            break
        melhor = None
        for passo in (2.5, 5.0):
            melhor = _melhor_ajuste_perna(perna_frame, pose_tronco, caixas, passo, pen)
            if melhor is not None:
                break
        if melhor is None:
            break
        pen, cand = melhor
        perna_frame.update(cand)


def _desembrulhar_angulo(atual: float, anterior: float) -> float:
    return anterior + _wrap_pi(atual - anterior)


def _desembrulhar_graus(atual: float, anterior: float) -> float:
    return anterior + (((atual - anterior + 180.0) % 360.0) - 180.0)


def _armadura_principal() -> Any:
    armaduras = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armaduras:
        raise RuntimeError("Nenhuma armadura encontrada no .blend")
    return max(armaduras, key=lambda obj: len(obj.data.bones))


def _intervalo_nla(arm: Any, scene: Any) -> tuple[int, int, int]:
    """Retorna (quadro_inicio, quadro_inicio_loop, quadro_fim) a partir da NLA ou Action."""
    strips: list[Any] = []
    if arm.animation_data and arm.animation_data.nla_tracks:
        for tr in arm.animation_data.nla_tracks:
            for s in tr.strips:
                strips.append(s)
    strips.sort(key=lambda s: float(s.frame_start))
    if strips:
        s0 = strips[0]
        dur0 = round(float(s0.action_frame_end) - float(s0.action_frame_start))
        if len(strips) >= 2 and float(s0.frame_end) <= 45.0:
            s1 = strips[1]
            inicio_loop = round(float(s1.frame_start))
            dur_loop = round(float(s1.action_frame_end) - float(s1.action_frame_start))
            return round(float(s0.frame_start)), inicio_loop, inicio_loop + dur_loop

        inicio = round(float(s0.frame_start))
        fim = inicio + max(24, dur0)
        return inicio, inicio, fim

    if arm.animation_data and arm.animation_data.action:
        r0, r1 = arm.animation_data.action.frame_range
        inicio = round(float(r0))
        fim = max(inicio + 1, round(float(r1)))
        return inicio, inicio, fim

    return int(scene.frame_start), int(scene.frame_start), int(scene.frame_end)


def _custo_transicao(
    q_a: dict[str, list[float]],
    p_a: dict[str, float],
    q_b: dict[str, list[float]],
    p_b: dict[str, float],
) -> float:
    total = 0.0
    for k, va in q_a.items():
        vb = q_b.get(k, [0.0, 0.0, 0.0])
        for a, b in zip(va, vb, strict=True):
            d = _wrap_pi(a - b)
            total += d * d
    for k, va in p_a.items():
        vb = p_b.get(ch := k, 0.0)
        _ = ch
        d = (va - vb) * 0.025
        total += d * d
    return total


def _alinhar_quat(
    q: tuple[float, float, float, float],
    q_ref: tuple[float, float, float, float] | None,
) -> tuple[float, float, float, float]:
    if q_ref is None:
        return q
    dot = q[0] * q_ref[0] + q[1] * q_ref[1] + q[2] * q_ref[2] + q[3] * q_ref[3]
    return (-q[0], -q[1], -q[2], -q[3]) if dot < 0.0 else q


def _blendar_raiz_emenda(
    r_idx: list[float],
    r0: list[float],
    r_prev: list[float],
    peso: float,
) -> list[float]:
    """Combina altura, guinada e orientação 3D de raiz na janela de emenda do loop."""
    g_delta = ((r0[1] - r_idx[1] + 180.0) % 360.0) - 180.0
    dz_n = round(r_idx[0] + (r0[0] - r_idx[0]) * peso, 4)
    g_n = round(r_idx[1] + g_delta * peso, 2)
    if len(r_idx) < 6 or len(r0) < 6:
        return [dz_n, g_n]
    q_v = (float(r_idx[2]), float(r_idx[3]), float(r_idx[4]), float(r_idx[5]))
    q_0 = (float(r0[2]), float(r0[3]), float(r0[4]), float(r0[5]))
    q_prev = (float(r_prev[2]), float(r_prev[3]), float(r_prev[4]), float(r_prev[5]))
    q_n = _alinhar_quat(_slerp_quat(q_v, q_0, peso), q_prev)
    return [dz_n, g_n, *(round(c, 5) for c in q_n)]


def _suavizar_emenda_loop(
    quadros: list[dict[str, list[float]]],
    pernas: list[dict[str, float]],
    raiz: list[list[float]],
    janela: int = 8,
) -> None:
    """Blend quíntico no fim do loop pelo menor arco angular (preserva giros completos)."""
    n = len(quadros)
    w = min(janela, n // 6)
    if n < 16 or w <= 1:
        return
    q0, p0, r0 = quadros[0], pernas[0], raiz[0]
    for i in range(w):
        idx = n - w + i
        u = (i + 1) / (w + 1)
        peso = u * u * u * (10.0 + u * (-15.0 + 6.0 * u))
        q_idx = quadros[idx]
        for grupo, vals in q_idx.items():
            alvo = q0.get(grupo, vals)
            q_idx[grupo] = [round(v + _wrap_pi(t - v) * peso, 4) for v, t in zip(vals, alvo, strict=True)]
        p_idx = pernas[idx]
        for ch, val in p_idx.items():
            p_idx[ch] = round(val + (p0.get(ch, val) - val) * peso, 3 if ch.endswith("_lift") else 2)
        raiz[idx] = _blendar_raiz_emenda(raiz[idx], r0, raiz[idx - 1], peso)


def _filtrar_passo(
    quadros: list[dict[str, list[float]]],
    pernas: list[dict[str, float]],
    raiz: list[list[float]],
    peso_viz: float,
) -> None:
    n = len(quadros)
    copia_q = [{k: list(v) for k, v in q.items()} for q in quadros]
    copia_p = [dict(p) for p in pernas]
    copia_r = [list(r) for r in raiz]

    peso_cen = 1.0 - 2.0 * peso_viz
    for i in range(1, n - 1):
        for k, v in copia_q[i].items():
            v_prev = copia_q[i - 1][k]
            v_next = copia_q[i + 1][k]
            quadros[i][k] = [
                round(
                    v[j]
                    + peso_viz
                    * (
                        (_wrap_pi(v_prev[j] - v[j]) + _wrap_pi(v_next[j] - v[j]))
                        if j == 0
                        else ((v_prev[j] - v[j]) + (v_next[j] - v[j]))
                    ),
                    4,
                )
                for j in range(3)
            ]
        for k, v in copia_p[i].items():
            if k.endswith("_lift"):
                continue
            pernas[i][k] = round(
                peso_viz * copia_p[i - 1][k] + peso_cen * v + peso_viz * copia_p[i + 1][k],
                2,
            )

        dz_s = round(
            peso_viz * copia_r[i - 1][0]
            + peso_cen * copia_r[i][0]
            + peso_viz * copia_r[i + 1][0],
            4,
        )
        if len(copia_r[i]) >= 6 and len(copia_r[i - 1]) >= 6 and len(copia_r[i + 1]) >= 6:
            qm = (float(copia_r[i][2]), float(copia_r[i][3]), float(copia_r[i][4]), float(copia_r[i][5]))
            qp = _alinhar_quat(
                (float(copia_r[i - 1][2]), float(copia_r[i - 1][3]), float(copia_r[i - 1][4]), float(copia_r[i - 1][5])),
                qm,
            )
            qn = _alinhar_quat(
                (float(copia_r[i + 1][2]), float(copia_r[i + 1][3]), float(copia_r[i + 1][4]), float(copia_r[i + 1][5])),
                qm,
            )
            qw = peso_viz * qp[0] + peso_cen * qm[0] + peso_viz * qn[0]
            qx = peso_viz * qp[1] + peso_cen * qm[1] + peso_viz * qn[1]
            qy = peso_viz * qp[2] + peso_cen * qm[2] + peso_viz * qn[2]
            qz = peso_viz * qp[3] + peso_cen * qm[3] + peso_viz * qn[3]
            nn = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz) or 1.0
            q_prev = (float(raiz[i - 1][2]), float(raiz[i - 1][3]), float(raiz[i - 1][4]), float(raiz[i - 1][5]))
            q_ok = _alinhar_quat((qw / nn, qx / nn, qy / nn, qz / nn), q_prev)
            raiz[i] = [
                dz_s,
                round(copia_r[i][1], 2),
                round(q_ok[0], 5),
                round(q_ok[1], 5),
                round(q_ok[2], 5),
                round(q_ok[3], 5),
            ]
        else:
            raiz[i] = [dz_s, round(copia_r[i][1], 2), *copia_r[i][2:]]


def _filtrar_trajetoria(
    quadros: list[dict[str, list[float]]],
    pernas: list[dict[str, float]],
    raiz: list[list[float]],
    model: Model,
) -> None:
    """Suaviza micro-vibração preservando amplitude total sem reinjetar degraus pós-filtro."""
    _ = model
    n = len(quadros)
    if n < 3:
        return
    # Garante sinal consistente dos quatérnios antes de filtrar
    for i in range(1, n):
        if len(raiz[i]) >= 6 and len(raiz[i - 1]) >= 6:
            q_prev = (float(raiz[i - 1][2]), float(raiz[i - 1][3]), float(raiz[i - 1][4]), float(raiz[i - 1][5]))
            q_cur = _alinhar_quat((float(raiz[i][2]), float(raiz[i][3]), float(raiz[i][4]), float(raiz[i][5])), q_prev)
            raiz[i] = [
                raiz[i][0],
                raiz[i][1],
                round(q_cur[0], 5),
                round(q_cur[1], 5),
                round(q_cur[2], 5),
                round(q_cur[3], 5),
            ]

    _filtrar_passo(quadros, pernas, raiz, 0.16)
    _filtrar_passo(quadros, pernas, raiz, 0.12)

    for i in range(1, n):
        for k, vals in quadros[i].items():
            ant_x = quadros[i - 1][k][0]
            quadros[i][k] = [
                round(_desembrulhar_angulo(vals[0], ant_x), 4),
                round(vals[1], 4),
                round(vals[2], 4),
            ]


def _smoothstep(u: float) -> float:
    x = _clamp(u, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _mat_para_quat(m: cin.Mat3) -> tuple[float, float, float, float]:
    """Converte matriz 3x3 (vetores coluna em ``cinematica``) em ``(w, x, y, z)``."""
    m00, m01, m02, m10, m11, m12, m20, m21, m22 = m
    tr = m00 + m11 + m22
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        q = (0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s)
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        q = ((m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s)
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        q = ((m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s)
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        q = ((m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s)
    n = math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]) or 1.0
    return (q[0] / n, q[1] / n, q[2] / n, q[3] / n)


def _quat_para_mat(q: tuple[float, float, float, float]) -> cin.Mat3:
    """Converte ``(w, x, y, z)`` em matriz 3x3 coluna-ativa de ``cinematica``."""
    w, x, y, z = q
    return (
        1.0 - 2.0 * (y * y + z * z),
        2.0 * (x * y - z * w),
        2.0 * (x * z + y * w),
        2.0 * (x * y + z * w),
        1.0 - 2.0 * (x * x + z * z),
        2.0 * (y * z - x * w),
        2.0 * (x * z - y * w),
        2.0 * (y * z + x * w),
        1.0 - 2.0 * (x * x + y * y),
    )


def _slerp_quat(
    qa: tuple[float, float, float, float],
    qb: tuple[float, float, float, float],
    t: float,
) -> tuple[float, float, float, float]:
    """Interpolação esférica pelo menor arco entre dois quatérnios unitários."""
    u = _clamp(t, 0.0, 1.0)
    dot = qa[0] * qb[0] + qa[1] * qb[1] + qa[2] * qb[2] + qa[3] * qb[3]
    if dot < 0.0:
        qb = (-qb[0], -qb[1], -qb[2], -qb[3])
        dot = -dot
    if dot > 0.9995:
        w = qa[0] + (qb[0] - qa[0]) * u
        x = qa[1] + (qb[1] - qa[1]) * u
        y = qa[2] + (qb[2] - qa[2]) * u
        z = qa[3] + (qb[3] - qa[3]) * u
        n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
        return (w / n, x / n, y / n, z / n)
    theta_0 = math.acos(_clamp(dot, -1.0, 1.0))
    sin_theta_0 = math.sin(theta_0)
    theta = theta_0 * u
    s0 = math.cos(theta) - dot * math.sin(theta) / sin_theta_0
    s1 = math.sin(theta) / sin_theta_0
    return (
        s0 * qa[0] + s1 * qb[0],
        s0 * qa[1] + s1 * qb[1],
        s0 * qa[2] + s1 * qb[2],
        s0 * qa[3] + s1 * qb[3],
    )


def _pontos_cabeca_mundo(rot_h: cin.Mat3, pos_h: cin.Vec3) -> list[tuple[cin.Vec3, float]]:
    """Retorna os 8 vértices aproximados da cabeça com raio de contato."""
    ex_h = (rot_h[0], rot_h[3], rot_h[6])
    ey_h = (rot_h[1], rot_h[4], rot_h[7])
    ez_h = (rot_h[2], rot_h[5], rot_h[8])
    cantos = [(hx, hy, hz) for hx in (-0.39, 0.39) for hy in (-0.16, 0.27) for hz in (0.0, 0.485)]
    return [
        (
            cin.somar(
                pos_h,
                cin.somar(
                    cin.escalar(ex_h, hx),
                    cin.somar(cin.escalar(ey_h, hy), cin.escalar(ez_h, hz)),
                ),
            ),
            0.015,
        )
        for hx, hy, hz in cantos
    ]


def _altura_minima_corpo_mundo(
    model: Model,
    pose_tronco_bracos: dict[str, Rotation3],
    perna_frame: dict[str, float],
    r_root_mundo: cin.Mat3,
) -> float:
    """Estima o ponto mais baixo do corpo rotacionado em torno do pivô ``z=0.44``."""
    fks: dict[str, tuple[cin.Mat3, cin.Vec3]] = {}
    for ponta in ("head", "hand", "hand2"):
        fks.update(cin.cadeia(model, ponta, pose_tronco_bracos))
    pivo_z = 0.44
    raios_grupo = {
        "cintura": 0.13,
        "abdomen": 0.14,
        "peitoral": 0.15,
        "head": 0.19,
        "right-arm": 0.075,
        "left-arm": 0.075,
        "ant-arm": 0.070,
        "ant-arm2": 0.070,
        "hand": 0.125,
        "hand2": 0.125,
    }
    pontos_raios: list[tuple[cin.Vec3, float]] = [
        (fks[grupo][1], raio) for grupo, raio in raios_grupo.items() if grupo in fks
    ]
    if "head" in fks:
        pontos_raios.extend(_pontos_cabeca_mundo(fks["head"][0], fks["head"][1]))
    for lado in ("left", "right"):
        _h, _td, k_aut, a_aut, t_aut = _pontos_perna_autoria(
            lado,
            perna_frame.get(lado, 0.0),
            perna_frame.get(f"{lado}_roll", 0.0),
            perna_frame.get(f"{lado}_yaw", 0.0),
            perna_frame.get(f"{lado}_knee", 0.0),
        )
        pontos_raios.extend(((k_aut, 0.10), (a_aut, 0.11), (t_aut, 0.11)))

    min_z = min(
        (
            pivo_z + cin.aplicar(r_root_mundo, (pt[0], pt[1], pt[2] - pivo_z))[2] - raio
            for pt, raio in pontos_raios
        ),
        default=float("inf"),
    )
    return min_z if min_z < float("inf") else 0.0


_CACHE_CANTOS_GLB: dict[str, list[cin.Vec3]] | None = None
_GRUPOS_SUPERIORES_PEITORAL = frozenset(
    {
        "head",
        "door",
        "fones",
        "fone-direito",
        "antena-direita",
        "fone-esquerdo",
        "antena-esquerda",
        "right-arm",
        "shoulder",
        "ant-arm",
        "hand",
        "fingers",
        "left-arm",
        "shoulder2",
        "ant-arm2",
        "hand2",
        "fingers2",
    }
)
_GRUPOS_PERNA_ESTATICOS = frozenset(
    {
        "pants",
        "pants2",
        "right-feet",
        "left-feet",
        "legs",
        "coxa-direita",
        "canela-direita",
        "joelho-direito",
        "coxa-esquerda",
        "canela-esquerda",
        "joelho-esquerdo",
    }
)


def _mat4_gltf_local(no: dict[str, Any]) -> list[list[float]]:
    t = no.get("translation", (0.0, 0.0, 0.0))
    x, y, z, w = no.get("rotation", (0.0, 0.0, 0.0, 1.0))
    s = no.get("scale", (1.0, 1.0, 1.0))
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return [
        [(1.0 - 2.0 * (yy + zz)) * s[0], 2.0 * (xy - wz) * s[1], 2.0 * (xz + wy) * s[2], t[0]],
        [2.0 * (xy + wz) * s[0], (1.0 - 2.0 * (xx + zz)) * s[1], 2.0 * (yz - wx) * s[2], t[1]],
        [2.0 * (xz - wy) * s[0], 2.0 * (yz + wx) * s[1], (1.0 - 2.0 * (xx + yy)) * s[2], t[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _grupo_e_cadeia_no(
    nodes: list[dict[str, Any]],
    pai_de: dict[int, int],
    idx: int,
) -> tuple[str | None, list[int]]:
    """Sobe na árvore glTF até o grupo semântico de ``ALL_GROUPS``."""
    cur: int | None = idx
    cadeia: list[int] = []
    while cur is not None:
        nome = nodes[cur].get("name", "")
        if nome in ALL_GROUPS:
            return nome, cadeia
        cadeia.append(cur)
        cur = pai_de.get(cur)
    return None, cadeia


def _cantos_malha_gltf(
    malha: dict[str, Any],
    nodes: list[dict[str, Any]],
    cadeia: list[int],
    accessors: list[dict[str, Any]],
    pad: float,
) -> list[cin.Vec3]:
    """Calcula os 8 cantos da AABB local no referencial de autoria."""
    mat = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    for c_idx in reversed(cadeia):
        loc = _mat4_gltf_local(nodes[c_idx])
        mat = [[sum(mat[r][k] * loc[k][c] for k in range(4)) for c in range(4)] for r in range(4)]
    mn = [min(float(accessors[p["attributes"]["POSITION"]]["min"][k]) for p in malha["primitives"]) for k in range(3)]
    mx = [max(float(accessors[p["attributes"]["POSITION"]]["max"][k]) for p in malha["primitives"]) for k in range(3)]
    return [
        (
            mat[0][0] * cx + mat[0][1] * cy + mat[0][2] * cz + mat[0][3],
            -(mat[2][0] * cx + mat[2][1] * cy + mat[2][2] * cz + mat[2][3]),
            mat[1][0] * cx + mat[1][1] * cy + mat[1][2] * cz + mat[1][3],
        )
        for cx in (mn[0] - pad, mx[0] + pad)
        for cy in (mn[1] - pad, mx[1] + pad)
        for cz in (mn[2] - pad, mx[2] + pad)
    ]


def _cantos_glb_por_grupo() -> dict[str, list[cin.Vec3]]:
    """Extrai os 8 vértices da AABB local real de cada malha superior no glTF."""
    global _CACHE_CANTOS_GLB
    if _CACHE_CANTOS_GLB is not None:
        return _CACHE_CANTOS_GLB

    caminho = resolve_model()
    if caminho.suffix.lower() != ".gltf" and caminho.with_suffix(".gltf").exists():
        caminho = caminho.with_suffix(".gltf")
    if caminho.suffix.lower() != ".gltf" or not caminho.exists():
        _CACHE_CANTOS_GLB = {}
        return _CACHE_CANTOS_GLB

    dados = json.loads(caminho.read_text(encoding="utf-8"))
    nodes, meshes, accessors = dados["nodes"], dados["meshes"], dados["accessors"]
    pai_de = {filho: idx for idx, no in enumerate(nodes) for filho in no.get("children", ())}
    por_grupo: dict[str, list[cin.Vec3]] = {}
    for idx, no in enumerate(nodes):
        if "mesh" not in no:
            continue
        grupo, cadeia = _grupo_e_cadeia_no(nodes, pai_de, idx)
        if grupo is None or grupo in _GRUPOS_PERNA_ESTATICOS:
            continue
        # Margem modesta nos dedos/luvas sem exagerar a caixa de contato (evita levitação em flexão).
        pad = 0.015 if grupo in ("fingers", "fingers2") else (0.01 if grupo in ("hand", "hand2") else 0.0)
        por_grupo.setdefault(grupo, []).extend(
            _cantos_malha_gltf(meshes[no["mesh"]], nodes, cadeia, accessors, pad)
        )
    _CACHE_CANTOS_GLB = por_grupo
    return por_grupo


def _altura_minima_rig_mundo(
    model: Model,
    pose: dict[str, Rotation3],
    perna: dict[str, float],
    r_root_mundo: cin.Mat3,
    pivo_z: float = 0.44,
) -> float:
    """Altura mínima real em autoria alinhada ao ``FlexibleRig`` (tronco/braços/TV + botas)."""
    cantos_glb = _cantos_glb_por_grupo()
    if not cantos_glb:
        return _altura_minima_corpo_mundo(model, pose, perna, r_root_mundo, pivo_z)

    r_peit_rest, o_peit_rest = cin.transformacao_no(model, "peitoral", {})
    r_peit_posed, o_peit_posed = cin.transformacao_no(model, "peitoral", pose)
    dr_peit = cin.mul(r_peit_posed, cin.transposta(r_peit_rest))

    min_z = float("inf")
    for grupo, cantos in cantos_glb.items():
        r_g, o_g = cin.transformacao_no(model, grupo, pose)
        if grupo in _GRUPOS_SUPERIORES_PEITORAL:
            o_g = cin.somar(o_peit_posed, cin.aplicar(dr_peit, cin.subtrair(o_g, o_peit_rest)))
            r_g = cin.mul(dr_peit, r_g)
        for pt in cantos:
            pg = cin.somar(o_g, cin.aplicar(r_g, pt))
            z_world = pivo_z + cin.aplicar(r_root_mundo, (pg[0], pg[1], pg[2] - pivo_z))[2]
            if z_world < min_z:
                min_z = z_world

    for lado in ("left", "right"):
        _h, _td, k_aut, a_aut, t_aut = _pontos_perna_autoria(
            lado,
            perna.get(lado, 0.0),
            perna.get(f"{lado}_roll", 0.0),
            perna.get(f"{lado}_yaw", 0.0),
            perna.get(f"{lado}_knee", 0.0),
        )
        for pt_aut, raio in ((k_aut, 0.065), (a_aut, 0.080), (t_aut, 0.080)):
            z_world = pivo_z + cin.aplicar(r_root_mundo, (pt_aut[0], pt_aut[1], pt_aut[2] - pivo_z))[2] - raio
            if z_world < min_z:
                min_z = z_world
    return min_z if min_z < float("inf") else 0.0


def _resolver_bracos_quadro(
    bruto: dict[str, Any],
    hinge_r: cin.Vec3,
    hinge_l: cin.Vec3,
    ant_ombro: dict[str, tuple[float, float, float] | None],
    trilha_t: dict[str, tuple[float, tuple[float, float, float]]] | None = None,
) -> dict[str, Rotation3]:
    """Resolve ombros, cotovelos, punhos e dedos para um quadro bruto."""
    poses_bracos: dict[str, Rotation3] = {}
    hinges = {"right": hinge_r, "left": hinge_l}
    dedos_brutos = bruto.get("dedos", {})
    for lado, g_om, g_co, g_ma, g_de, s_el in (
        ("right", "right-arm", "ant-arm", "hand", "fingers", 1.0),
        ("left", "left-arm", "ant-arm2", "hand2", "fingers2", -1.0),
    ):
        u1_p, u2_p, _ch, rot_punho = bruto["bracos"][lado]
        if trilha_t is not None and lado in trilha_t:
            flexao, (p, h, r) = trilha_t[lado]
            ro, rc_arm = Rotation3(p, h, r), Rotation3(0.0, 0.0, flexao)
            if lado == "left":
                ro, rc_arm = cin.espelhar_rotacao(ro), cin.espelhar_rotacao(rc_arm)
            ant_ombro[lado] = (p, h, r)
        else:
            u_dobra = cin.produto_vetorial(hinges[lado], u1_p)
            ro, rc_arm, ant_ombro[lado] = _resolver_braco_1para1(
                lado, u1_p, u2_p, u_dobra, ant_ombro[lado]
            )
        poses_bracos[g_om] = ro
        poses_bracos[g_co] = rc_arm
        poses_bracos[g_ma] = rot_punho
        curls = dedos_brutos.get(lado)
        if curls and len(curls) >= 5:
            curl_med = 0.28 * curls[1] + 0.32 * curls[2] + 0.24 * curls[3] + 0.16 * curls[4]
            poses_bracos[g_de] = Rotation3(0.0, 0.0, s_el * _clamp(curl_med * 0.92, 0.02, 0.92))
        else:
            flex_ratio = _clamp(abs(rc_arm.z) / math.radians(130.0), 0.0, 1.0)
            poses_bracos[g_de] = Rotation3(0.0, 0.0, s_el * (0.14 + 0.24 * flex_ratio))
    return poses_bracos


def _resolver_pernas_quadro(
    bruto: dict[str, Any],
    ek_l: cin.Vec3,
    ek_r: cin.Vec3,
    pose_tb: dict[str, Rotation3],
    ant_perna: dict[str, tuple[float, float, float] | None],
) -> dict[str, float]:
    """Resolve IK e alívio leve de colisão para as duas pernas no quadro."""
    perna_frame: dict[str, float] = {}
    eks = {"left": ek_l, "right": ek_r}
    for pref in ("left", "right"):
        dados_p = bruto["pernas"][pref]
        u_th, u_sh, _ek_raw, lift = dados_p[:4]
        ankle_deg = dados_p[4] if len(dados_p) >= 5 else None
        p_d, r_d, y_d, k_d = _resolver_perna_ik_3d(
            pref, u_th, u_sh, eks[pref], ant_perna[pref]
        )
        ant_perna[pref] = (p_d, r_d, y_d)
        perna_frame[pref] = round(p_d, 2)
        perna_frame[f"{pref}_roll"] = round(r_d, 2)
        perna_frame[f"{pref}_yaw"] = round(y_d, 2)
        perna_frame[f"{pref}_knee"] = round(k_d, 2)
        perna_frame[f"{pref}_lift"] = round(min(0.16, lift), 4)
        if ankle_deg is not None:
            perna_frame[f"{pref}_ankle"] = round(ankle_deg, 2)

    _aliviar_colisao_pernas(perna_frame, pose_tb)
    for k_p in list(perna_frame.keys()):
        if not k_p.endswith("_lift"):
            perna_frame[k_p] = round(perna_frame[k_p], 2)
    return perna_frame


def _calcular_dz_pelvis(
    bruto: dict[str, Any],
    model: Model,
    pose_tb: dict[str, Rotation3],
    perna_frame: dict[str, float],
) -> float:
    """Eleva a raiz em poses inclinadas/invertidas para impedir invasão do piso."""
    dz_contato = 0.0
    r_root_mundo = bruto["r_root_mundo"]
    if bruto["alpha_tilt"] > 0.02:
        min_z = _altura_minima_rig_mundo(model, pose_tb, perna_frame, r_root_mundo)
        tilt_rad = math.acos(_clamp(r_root_mundo[8], -1.0, 1.0))
        w_tilt = 1.0 if tilt_rad > 0.25 else _clamp((tilt_rad - 0.04) / 0.21, 0.0, 1.0)
        dz_contato = _clamp(max(0.0, MODEL_FLOOR_Z - min_z) * w_tilt, 0.0, 0.72)
    return round(max(bruto["dz_pulo"], dz_contato), 4)


def _resolver_quadro_bruto(
    bruto: dict[str, Any],
    hinge_r: cin.Vec3,
    hinge_l: cin.Vec3,
    ek_l: cin.Vec3,
    ek_r: cin.Vec3,
    model: Model,
    ant_ombro: dict[str, tuple[float, float, float] | None],
    ant_perna: dict[str, tuple[float, float, float] | None],
    trilha_t: dict[str, tuple[float, tuple[float, float, float]]] | None = None,
) -> tuple[dict[str, list[float]], dict[str, float], list[float]]:
    """Converte uma amostra bruta do Blender em pose do rig, pernas e raiz do Mário."""
    poses_bracos = _resolver_bracos_quadro(bruto, hinge_r, hinge_l, ant_ombro, trilha_t=trilha_t)
    pose_tb: dict[str, Rotation3] = {
        "cintura": bruto["cintura"],
        "abdomen": bruto["abdomen"],
        "peitoral": bruto["peitoral"],
        "head": bruto["head"],
        **bruto["claviculas"],
        **poses_bracos,
    }
    _aliviar_colisao_pose(model, pose_tb, max_iter=4)
    perna_frame = _resolver_pernas_quadro(bruto, ek_l, ek_r, pose_tb, ant_perna)
    quadro_ser = {
        grupo: [round(rot.x, 4), round(rot.y, 4), round(rot.z, 4)]
        for grupo, rot in pose_tb.items()
    }
    dz_pelvis = _calcular_dz_pelvis(bruto, model, pose_tb, perna_frame)
    q_root = bruto["q_root"]
    raiz_row = [
        dz_pelvis,
        round(math.degrees(bruto["psi_pelvis"]), 2),
        *(round(c, 5) for c in q_root),
    ]
    return quadro_ser, perna_frame, raiz_row


def _pos_bone(mw: Any, pb: Any, nome: str) -> cin.Vec3:
    """Retorna posição mundial da cabeça de um bone no referencial de autoria."""
    return _pt_autoria(mw @ pb[nome].head)


def _rot_bone(mw: Any, pb: Any, rest_rot: dict[str, Any], nome: str) -> cin.Mat3:
    """Retorna rotação relativa do pose bone no referencial de autoria."""
    return _conj_autoria((mw @ pb[nome].matrix).to_3x3() @ rest_rot[nome].inverted())


def _vec_aut(v_mundo: Any) -> cin.Vec3:
    """Converte vetor livre do mundo Blender (Y-up/Z-up ajustado) para autoria."""
    return (-float(v_mundo[0]), -float(v_mundo[1]), float(v_mundo[2]))


def _achar_osso(db: Any, *candidatos: str) -> str:
    """Encontra o primeiro bone presente na armadura (com ou sem namespace ``mixamorig:``)."""
    for nome in candidatos:
        if nome in db:
            return nome
        m = f"mixamorig:{nome}"
        if m in db:
            return m
    return ""


def _perfil_armadura(arm: Any) -> dict[str, Any]:
    """Detecta perfil de nomenclatura e eixos locais de dobra (Fortnite vs Mixamo)."""
    db = arm.data.bones
    eh_mixamo = bool(_achar_osso(db, "Hips")) and not ("pelvis" in db)
    if eh_mixamo:
        return {
            "tipo": "mixamo",
            "pelvis": _achar_osso(db, "Hips"),
            "spine": _achar_osso(db, "Spine"),
            "spine1": _achar_osso(db, "Spine1"),
            "chest": _achar_osso(db, "Spine2"),
            "neck": _achar_osso(db, "Neck"),
            "head": _achar_osso(db, "Head"),
            "clav_r": _achar_osso(db, "RightShoulder"),
            "clav_l": _achar_osso(db, "LeftShoulder"),
            "up_r": _achar_osso(db, "RightArm"),
            "up_l": _achar_osso(db, "LeftArm"),
            "lo_r": _achar_osso(db, "RightForeArm"),
            "lo_l": _achar_osso(db, "LeftForeArm"),
            "hand_r": _achar_osso(db, "RightHand"),
            "hand_l": _achar_osso(db, "LeftHand"),
            "thigh_r": _achar_osso(db, "RightUpLeg"),
            "thigh_l": _achar_osso(db, "LeftUpLeg"),
            "calf_r": _achar_osso(db, "RightLeg"),
            "calf_l": _achar_osso(db, "LeftLeg"),
            "foot_r": _achar_osso(db, "RightFoot"),
            "foot_l": _achar_osso(db, "LeftFoot"),
            "toe_r": _achar_osso(db, "RightToe_End", "RightToeBase"),
            "toe_l": _achar_osso(db, "LeftToe_End", "LeftToeBase"),
            "arm_col": 2,
            "arm_s_r": -1.0,
            "arm_s_l": 1.0,
            "leg_col": 0,
            "leg_s": -1.0,
        }
    return {
        "tipo": "fortnite",
        "pelvis": "pelvis",
        "spine": "spine_01" if "spine_01" in db else "pelvis",
        "spine1": "spine_02" if "spine_02" in db else "pelvis",
        "chest": "spine_03" if "spine_03" in db else "spine_02",
        "neck": "neck_01" if "neck_01" in db else "head",
        "head": "head",
        "clav_r": "clavicle_r",
        "clav_l": "clavicle_l",
        "up_r": "upperarm_r",
        "up_l": "upperarm_l",
        "lo_r": "lowerarm_r",
        "lo_l": "lowerarm_l",
        "hand_r": "hand_r",
        "hand_l": "hand_l",
        "thigh_r": "thigh_r",
        "thigh_l": "thigh_l",
        "calf_r": "calf_r",
        "calf_l": "calf_l",
        "foot_r": "foot_r",
        "foot_l": "foot_l",
        "toe_r": "",
        "toe_l": "",
        "arm_col": 2,
        "arm_s_r": 1.0,
        "arm_s_l": -1.0,
        "leg_col": 2,
        "leg_s": -1.0,
    }


def _preparar_contexto_armadura(arm: Any) -> dict[str, Any]:
    """Pré-calcula ossos de referência e alturas em repouso da armadura (Fortnite ou Mixamo)."""
    mw = arm.matrix_world
    db = arm.data.bones
    perfil = _perfil_armadura(arm)
    rest_rot = {b.name: (mw @ b.matrix_local).to_3x3() for b in db}
    rest_clav_vec: dict[str, cin.Vec3] = {}
    for lado, k_cl, k_up in (("right", "clav_r", "up_r"), ("left", "clav_l", "up_l")):
        b_cl, b_up = perfil[k_cl], perfil[k_up]
        if b_cl in db and b_up in db:
            rest_clav_vec[lado] = cin.normalizar(
                _pt_autoria((mw @ db[b_up].head_local) - (mw @ db[b_cl].head_local))
            )
    rest_ankle_rad: dict[str, float] = {}
    for pref, k_ca, k_fo, k_to in (
        ("left", "calf_l", "foot_l", "toe_l"),
        ("right", "calf_r", "foot_r", "toe_r"),
    ):
        b_to = perfil[k_to]
        if b_to and b_to in db:
            v_sh = _pt_autoria((mw @ db[perfil[k_fo]].head_local) - (mw @ db[perfil[k_ca]].head_local))
            v_ft = _pt_autoria((mw @ db[b_to].head_local) - (mw @ db[perfil[k_fo]].head_local))
            rest_ankle_rad[pref] = math.acos(
                _clamp(cin.produto_escalar(cin.normalizar(v_sh), cin.normalizar(v_ft)), -1.0, 1.0)
            )
    return {
        "mw": mw,
        "rest_rot": rest_rot,
        "perfil": perfil,
        "pelvis_z_rest": float((mw @ db[perfil["pelvis"]].head_local).z),
        "foot_z_rest": min(
            float((mw @ db[perfil["foot_l"]].head_local).z),
            float((mw @ db[perfil["foot_r"]].head_local).z),
        ),
        "rest_clav_vec": rest_clav_vec,
        "rest_ankle_rad": rest_ankle_rad,
    }


def _orientacao_pelve_e_raiz(
    r_pelv_mundo: cin.Mat3,
    estado: dict[str, Any],
) -> tuple[float, float, tuple[float, float, float, float], cin.Mat3]:
    """Atualiza rastreio contínuo de yaw e quatérnio raiz entre quadros adjacentes."""
    q_pelv_mundo = _alinhar_quat(_mat_para_quat(r_pelv_mundo), estado["q_pelv_ant"])
    estado["q_pelv_ant"] = q_pelv_mundo
    tilt_pelv = math.acos(_clamp(r_pelv_mundo[8], -1.0, 1.0))
    alpha_tilt = _smoothstep((tilt_pelv - math.radians(18.0)) / math.radians(26.0))
    if tilt_pelv > math.radians(28.0):
        estado["tem_tilt_3d"] = True

    rx_p, ry_p = r_pelv_mundo[0], r_pelv_mundo[3]
    if tilt_pelv < math.radians(52.0) and math.hypot(rx_p, ry_p) >= 0.45:
        yaw_bruto = math.atan2(ry_p, rx_p)
        psi_pelvis = yaw_bruto if not estado["psi_init"] else _desembrulhar_angulo(yaw_bruto, estado["psi_ant"])
    elif not estado["psi_init"]:
        psi_pelvis = math.atan2(ry_p, rx_p) if math.hypot(rx_p, ry_p) >= 1e-4 else 0.0
    else:
        psi_pelvis = estado["psi_ant"]
    estado["psi_init"] = True
    estado["psi_ant"] = psi_pelvis

    q_yaw = (math.cos(psi_pelvis * 0.5), 0.0, 0.0, math.sin(psi_pelvis * 0.5))
    q_root = q_pelv_mundo if alpha_tilt >= 0.9999 else _slerp_quat(q_yaw, q_pelv_mundo, alpha_tilt)
    q_root = _alinhar_quat(q_root, estado["q_root_ant"])
    estado["q_root_ant"] = q_root
    return alpha_tilt, psi_pelvis, q_root, _quat_para_mat(q_root)


def _claviculas_quadro(
    mw: Any,
    pb: Any,
    perfil: dict[str, Any],
    r_chest_inv: cin.Mat3,
    rest_clav_vec: dict[str, cin.Vec3],
) -> dict[str, Rotation3]:
    """Extrai encolhimento e protração das clavículas relativas ao tórax."""
    poses: dict[str, Rotation3] = {}
    for lado, k_cl, k_up, g_sh, sgn in (
        ("right", "clav_r", "up_r", "shoulder", 1.0),
        ("left", "clav_l", "up_l", "shoulder2", -1.0),
    ):
        n_cl, n_up = perfil[k_cl], perfil[k_up]
        if not n_cl or n_cl not in pb or lado not in rest_clav_vec:
            continue
        vc = cin.normalizar(cin.aplicar(r_chest_inv, cin.subtrair(_pos_bone(mw, pb, n_up), _pos_bone(mw, pb, n_cl))))
        v_ref = rest_clav_vec[lado]
        shrug = _clamp((vc[2] - v_ref[2]) * 1.15, -0.26, 0.26)
        protract = _clamp((vc[1] - v_ref[1]) * 0.95, -0.22, 0.22)
        poses[g_sh] = Rotation3(0.0, sgn * protract, -sgn * shrug)
    return poses


def _amostrar_dedos_mixamo(mw: Any, pb: Any, lado: str) -> list[float] | None:
    """Mede flexão normalizada [0..1] para (polegar, indicador, médio, anelar, mínimo)."""
    pref = "RightHand" if lado == "right" else "LeftHand"
    b_hand = _achar_osso(pb, pref)
    if not b_hand:
        return None
    curls: list[float] = []
    for nome_dedo, esc_rad in (
        ("Thumb", 1.15),
        ("Index", 1.85),
        ("Middle", 1.90),
        ("Ring", 1.90),
        ("Pinky", 1.90),
    ):
        b1 = _achar_osso(pb, f"{pref}{nome_dedo}1")
        b2 = _achar_osso(pb, f"{pref}{nome_dedo}2")
        b3 = _achar_osso(pb, f"{pref}{nome_dedo}3")
        b4 = _achar_osso(pb, f"{pref}{nome_dedo}4") or b3
        if not (b1 and b2 and b3):
            curls.append(0.15)
            continue
        v1 = cin.normalizar(cin.subtrair(_pos_bone(mw, pb, b2), _pos_bone(mw, pb, b1)))
        v2 = cin.normalizar(cin.subtrair(_pos_bone(mw, pb, b3), _pos_bone(mw, pb, b2)))
        a1 = math.acos(_clamp(cin.produto_escalar(v1, v2), -1.0, 1.0))
        a2 = 0.0
        if b4 and b4 != b3:
            v3 = cin.normalizar(cin.subtrair(_pos_bone(mw, pb, b4), _pos_bone(mw, pb, b3)))
            a2 = math.acos(_clamp(cin.produto_escalar(v2, v3), -1.0, 1.0))
        curls.append(round(_clamp((a1 + 0.7 * a2) / esc_rad, 0.0, 1.0), 2))
    return curls


def _bracos_e_pernas_brutos(
    mw: Any,
    pb: Any,
    rest_rot: dict[str, Any],
    perfil: dict[str, Any],
    r_chest_inv: cin.Mat3,
    r_root_inv: cin.Mat3,
    foot_z_rest: float,
    rest_ankle_rad: dict[str, float],
) -> tuple[
    dict[str, tuple[cin.Vec3, cin.Vec3, cin.Vec3, Rotation3]],
    dict[str, tuple[cin.Vec3, cin.Vec3, cin.Vec3, float, float | None]],
    dict[str, list[float]],
]:
    """Amostra vetores locais de braços (no tórax), pernas (na raiz) e dedos."""
    bracos_f: dict[str, tuple[cin.Vec3, cin.Vec3, cin.Vec3, Rotation3]] = {}
    dedos_f: dict[str, list[float]] = {}
    a_col = int(perfil["arm_col"])
    for lado, k_up, k_lo, k_ha, s_arm in (
        ("right", "up_r", "lo_r", "hand_r", float(perfil["arm_s_r"])),
        ("left", "up_l", "lo_l", "hand_l", float(perfil["arm_s_l"])),
    ):
        n_up, n_lo, n_ha = perfil[k_up], perfil[k_lo], perfil[k_ha]
        s_pt, e_pt, w_pt = _pos_bone(mw, pb, n_up), _pos_bone(mw, pb, n_lo), _pos_bone(mw, pb, n_ha)
        z_up = (mw @ pb[n_up].matrix).to_3x3()
        z_col = (s_arm * float(z_up[0][a_col]), s_arm * float(z_up[1][a_col]), s_arm * float(z_up[2][a_col]))
        hw, pw, rw = cin.hpr_de_matriz(
            cin.mul(cin.transposta(_rot_bone(mw, pb, rest_rot, n_lo)), _rot_bone(mw, pb, rest_rot, n_ha))
        )
        rot_punho = Rotation3(_clamp(pw * 0.85, -0.95, 0.95), _clamp(hw * 0.85, -0.95, 0.95), _clamp(rw * 0.85, -0.95, 0.95))
        bracos_f[lado] = (
            cin.aplicar(r_chest_inv, cin.normalizar(cin.subtrair(e_pt, s_pt))),
            cin.aplicar(r_chest_inv, cin.normalizar(cin.subtrair(w_pt, e_pt))),
            cin.aplicar(r_chest_inv, _vec_aut(z_col)),
            rot_punho,
        )
        if perfil["tipo"] == "mixamo":
            curls = _amostrar_dedos_mixamo(mw, pb, lado)
            if curls is not None:
                dedos_f[lado] = curls

    pernas_f: dict[str, tuple[cin.Vec3, cin.Vec3, cin.Vec3, float, float | None]] = {}
    l_col = int(perfil["leg_col"])
    l_s = float(perfil["leg_s"])
    for pref, k_th, k_ca, k_fo, k_to in (
        ("left", "thigh_l", "calf_l", "foot_l", "toe_l"),
        ("right", "thigh_r", "calf_r", "foot_r", "toe_r"),
    ):
        n_th, n_ca, n_fo, n_to = perfil[k_th], perfil[k_ca], perfil[k_fo], perfil[k_to]
        th_pt, ca_pt, fo_pt = _pos_bone(mw, pb, n_th), _pos_bone(mw, pb, n_ca), _pos_bone(mw, pb, n_fo)
        z_th = (mw @ pb[n_th].matrix).to_3x3()
        z_th_w = (l_s * float(z_th[0][l_col]), l_s * float(z_th[1][l_col]), l_s * float(z_th[2][l_col]))
        ankle_deg: float | None = None
        if n_to and n_to in pb and pref in rest_ankle_rad:
            to_pt = _pos_bone(mw, pb, n_to)
            v_sh = cin.normalizar(cin.subtrair(fo_pt, ca_pt))
            v_ft = cin.normalizar(cin.subtrair(to_pt, fo_pt))
            ang_cur = math.acos(_clamp(cin.produto_escalar(v_sh, v_ft), -1.0, 1.0))
            ankle_deg = _clamp(math.degrees(rest_ankle_rad[pref] - ang_cur), -26.0, 26.0)
        pernas_f[pref] = (
            cin.aplicar(r_root_inv, cin.normalizar(cin.subtrair(ca_pt, th_pt))),
            cin.aplicar(r_root_inv, cin.normalizar(cin.subtrair(fo_pt, ca_pt))),
            cin.aplicar(r_root_inv, _vec_aut(z_th_w)),
            max(0.0, (fo_pt[2] - foot_z_rest) * 0.36),
            ankle_deg,
        )
    return bracos_f, pernas_f, dedos_f


def _amostrar_quadro_blender(
    arm: Any,
    ctx: dict[str, Any],
    estado: dict[str, Any],
) -> dict[str, Any]:
    """Extrai dados brutos espaciais de um quadro da armadura avaliada no Blender."""
    mw, pb, rest_rot, perfil = ctx["mw"], arm.pose.bones, ctx["rest_rot"], ctx["perfil"]
    p_pelv = _pos_bone(mw, pb, perfil["pelvis"])
    sp_top = _pos_bone(mw, pb, perfil["spine1"] or perfil["chest"])
    r_pelv_mundo = _frame_ortonormal(
        cin.subtrair(_pos_bone(mw, pb, perfil["thigh_r"]), _pos_bone(mw, pb, perfil["thigh_l"])),
        cin.subtrair(sp_top, p_pelv),
    )
    neck = _pos_bone(mw, pb, perfil["neck"] or perfil["head"])
    chest_base = _pos_bone(mw, pb, perfil["spine1"] or perfil["spine"])
    r_chest_mundo = _frame_ortonormal(
        cin.subtrair(_pos_bone(mw, pb, perfil["up_r"]), _pos_bone(mw, pb, perfil["up_l"])),
        cin.subtrair(neck, chest_base),
    )
    r_chest_inv = cin.transposta(r_chest_mundo)
    alpha_tilt, psi_pelvis, q_root, r_root_mundo = _orientacao_pelve_e_raiz(r_pelv_mundo, estado)
    r_root_inv = cin.transposta(r_root_mundo)

    _hp, pp, rp = cin.hpr_de_matriz(cin.mul(r_root_inv, r_pelv_mundo))
    escala_sp = 1.0 - alpha_tilt
    pp_mod = _clamp(pp * 0.85 * escala_sp, math.radians(-38.0), math.radians(38.0))
    rp_mod = _clamp(rp * 0.85 * escala_sp, math.radians(-40.0), math.radians(40.0))

    hc, pc, rc = cin.hpr_de_matriz(cin.mul(cin.transposta(r_pelv_mundo), r_chest_mundo))
    pc_mod = _clamp(pc * 0.90, math.radians(-34.0), math.radians(32.0))
    rc_mod = _clamp(rc * 0.90, math.radians(-34.0), math.radians(34.0))
    hc_mod = _clamp(hc * 0.92, math.radians(-46.0), math.radians(46.0))

    hh, ph, rh = cin.hpr_de_matriz(cin.mul(r_chest_inv, _rot_bone(mw, pb, rest_rot, perfil["head"])))
    rot_head = Rotation3(
        _clamp(ph * 0.90, math.radians(-38.0), math.radians(36.0)),
        _clamp(hh * 0.92, math.radians(-58.0), math.radians(58.0)),
        _clamp(rh * 0.90, math.radians(-36.0), math.radians(36.0)),
    )
    bracos_f, pernas_f, dedos_f = _bracos_e_pernas_brutos(
        mw, pb, rest_rot, perfil, r_chest_inv, r_root_inv, ctx["foot_z_rest"], ctx["rest_ankle_rad"]
    )
    air_foot = max(
        0.0,
        min(_pos_bone(mw, pb, perfil["foot_l"])[2], _pos_bone(mw, pb, perfil["foot_r"])[2]) - ctx["foot_z_rest"] - 0.04,
    )
    air_pelvis = max(0.0, p_pelv[2] - ctx["pelvis_z_rest"] + 0.08)
    return {
        "cintura": Rotation3(pc_mod * 0.36 + pp_mod * 0.55, hc_mod * 0.34, rc_mod * 0.36 + rp_mod * 0.55),
        "abdomen": Rotation3(pc_mod * 0.34 + pp_mod * 0.25, hc_mod * 0.34, rc_mod * 0.34 + rp_mod * 0.25),
        "peitoral": Rotation3(pc_mod * 0.30 + pp_mod * 0.20, hc_mod * 0.32, rc_mod * 0.30 + rp_mod * 0.20),
        "claviculas": _claviculas_quadro(mw, pb, perfil, r_chest_inv, ctx["rest_clav_vec"]),
        "head": rot_head,
        "bracos": bracos_f,
        "pernas": pernas_f,
        "dedos": dedos_f,
        "alpha_tilt": alpha_tilt,
        "psi_pelvis": psi_pelvis,
        "q_root": q_root,
        "r_root_mundo": r_root_mundo,
        "pos_pelve": p_pelv,
        "dz_pulo": _clamp(min(air_foot, air_pelvis) * 0.34, 0.0, 0.18),
    }


def _suavizar_eixos_brutos(brutos: list[dict[str, Any]]) -> dict[str, list[cin.Vec3]]:
    """Suaviza eixos de dobra de cotovelos e joelhos ao longo de todo o clipe."""
    out: dict[str, list[cin.Vec3]] = {}
    for lado in ("right", "left"):
        out[f"arm_{lado}"] = _suavizar_eixos_dobradica(
            [b["bracos"][lado][0] for b in brutos],
            [b["bracos"][lado][1] for b in brutos],
            [b["bracos"][lado][2] for b in brutos],
        )
        out[f"leg_{lado}"] = _suavizar_eixos_dobradica(
            [b["pernas"][lado][0] for b in brutos],
            [b["pernas"][lado][1] for b in brutos],
            [b["pernas"][lado][2] for b in brutos],
        )
    return out


def _pre_trilhas_ombros(
    brutos: list[dict[str, Any]],
    eixos: dict[str, list[cin.Vec3]],
) -> dict[str, list[tuple[float, tuple[float, float, float]]]]:
    """Resolve trilhas contínuas globais de ombro para os dois braços."""
    out: dict[str, list[tuple[float, tuple[float, float, float]]]] = {}
    for lado in ("right", "left"):
        flexoes: list[float] = []
        bases: list[cin.Mat3] = []
        for idx_b, bruto in enumerate(brutos):
            u1_p, u2_p, _ch, _rp = bruto["bracos"][lado]
            u_dobra = cin.produto_vetorial(eixos[f"arm_{lado}"][idx_b], u1_p)
            fl, bs = _base_braco_quadro(lado, u1_p, u2_p, u_dobra)
            flexoes.append(fl)
            bases.append(bs)
        out[lado] = list(zip(flexoes, _resolver_trilha_ombro(bases), strict=True))
    return out


def _resolver_todos_quadros(
    brutos: list[dict[str, Any]],
    eixos: dict[str, list[cin.Vec3]],
    model: Model,
    tem_tilt_3d: bool,
) -> tuple[list[dict[str, list[float]]], list[dict[str, float]], list[list[float]]]:
    """Converte todos os quadros brutos em curvas finais e enxuga raízes sem tilt 3D."""
    trilhas = _pre_trilhas_ombros(brutos, eixos)
    todos_quadros: list[dict[str, list[float]]] = []
    todas_pernas: list[dict[str, float]] = []
    todas_raizes: list[list[float]] = []
    ant_ombro: dict[str, tuple[float, float, float] | None] = {"right": None, "left": None}
    ant_perna: dict[str, tuple[float, float, float] | None] = {"right": None, "left": None}
    for idx_b, bruto in enumerate(brutos):
        trilha_t = {"right": trilhas["right"][idx_b], "left": trilhas["left"][idx_b]}
        q_s, p_f, r_row = _resolver_quadro_bruto(
            bruto,
            eixos["arm_right"][idx_b],
            eixos["arm_left"][idx_b],
            eixos["leg_left"][idx_b],
            eixos["leg_right"][idx_b],
            model,
            ant_ombro,
            ant_perna,
            trilha_t=trilha_t,
        )
        todos_quadros.append(q_s)
        todas_pernas.append(p_f)
        todas_raizes.append(r_row if tem_tilt_3d else r_row[:2])
    return todos_quadros, todas_pernas, todas_raizes


def _encontrar_inicio_loop(
    inicio: int,
    inicio_loop_nla: int,
    todos_quadros: list[dict[str, list[float]]],
    todas_pernas: list[dict[str, float]],
) -> int:
    """Separa introdução real do trecho cíclico quando há NLA multi-strip ou pickup claro."""
    idx_loop = max(0, inicio_loop_nla - inicio)
    total = len(todos_quadros)
    if idx_loop != 0 or total < 160:
        return idx_loop
    custo_direto = _custo_transicao(todos_quadros[0], todas_pernas[0], todos_quadros[-1], todas_pernas[-1])
    if custo_direto <= 0.35:
        return 0
    melhor_k = 0
    melhor_custo = custo_direto
    limite_busca = min(total - 72, int(total * 0.38))
    for k in range(16, limite_busca):
        c = _custo_transicao(todos_quadros[k], todas_pernas[k], todos_quadros[-1], todas_pernas[-1])
        if c < melhor_custo * 0.45:
            melhor_custo = c
            melhor_k = k
    return melhor_k


def _fechar_retorno_loop(
    todos_quadros: list[dict[str, list[float]]],
    todas_pernas: list[dict[str, float]],
    todas_raizes: list[list[float]],
    n_passos: int = 24,
) -> None:
    """Anexa rampa quíntica suave do último quadro de volta ao início para acrobatas."""
    if len(todos_quadros) < 8 or n_passos <= 1:
        return
    q_ult, p_ult, r_ult = todos_quadros[-1], todas_pernas[-1], todas_raizes[-1]
    q_ini, p_ini, r_ini = todos_quadros[0], todas_pernas[0], todas_raizes[0]
    for i in range(n_passos):
        u = (i + 1) / (n_passos + 1)
        w = u * u * u * (10.0 + u * (-15.0 + 6.0 * u))
        q_row = {
            g: [round(v + _wrap_pi(t - v) * w, 4) for v, t in zip(q_ult[g], q_ini.get(g, q_ult[g]), strict=True)]
            for g in q_ult
        }
        p_row = {
            c: round(v + (p_ini.get(c, v) - v) * w, 3 if c.endswith("_lift") else 2)
            for c, v in p_ult.items()
        }
        r_prev = todas_raizes[-1]
        todos_quadros.append(q_row)
        todas_pernas.append(p_row)
        todas_raizes.append(_blendar_raiz_emenda(r_ult, r_ini, r_prev, w))


def _centralizar_yaw_se_preciso(todas_raizes: list[list[float]], apenas_reverso: bool = True) -> None:
    """Remove offset de guinada >95° (ex.: corrida de costas após meia-volta) preservando swing natural."""
    if not todas_raizes:
        return
    media_yaw = sum(r[1] for r in todas_raizes) / len(todas_raizes)
    if apenas_reverso and abs(media_yaw) <= 95.0:
        return
    q_corr = None
    if len(todas_raizes[0]) >= 6:
        half = math.radians(-media_yaw) * 0.5
        q_corr = (math.cos(half), 0.0, 0.0, math.sin(half))
    for r in todas_raizes:
        r[1] = round(((r[1] - media_yaw + 180.0) % 360.0) - 180.0, 2)
        if len(r) >= 6 and q_corr is not None:
            cw, cx, cy, cz = q_corr
            rw, rx, ry, rz = r[2], r[3], r[4], r[5]
            qw = cw * rw - cx * rx - cy * ry - cz * rz
            qx = cw * rx + cx * rw + cy * rz - cz * ry
            qy = cw * ry - cx * rz + cy * rw + cz * rx
            qz = cw * rz + cx * ry - cy * rx + cz * rw
            for idx_q, comp in enumerate((qw, qx, qy, qz), start=2):
                r[idx_q] = round(comp, 5)


def extrair_clipe_atual(
    estilo: str = "",
    *,
    frame_inicio: int | None = None,
    frame_fim: int | None = None,
    eh_loop: bool = True,
    bpm_override: float | None = None,
    vel_override: float | None = None,
    centralizar_yaw: bool = False,
    fechar_retorno: bool = False,
) -> dict[str, Any]:
    """Amostra a armadura em todos os quadros a 30fps e resolve o retargeting 3D 1:1 completo."""
    if bpy is None:
        raise RuntimeError("Este script deve ser executado dentro do Blender.")
    scene = bpy.context.scene
    arm = _armadura_principal()
    inicio_nla, inicio_loop_nla, fim_nla = _intervalo_nla(arm, scene)
    inicio = inicio_nla if frame_inicio is None else max(inicio_nla, int(frame_inicio))
    fim = fim_nla if frame_fim is None else min(fim_nla, int(frame_fim))
    if not eh_loop or frame_inicio is not None:
        inicio_loop_nla = inicio
    scene.frame_start = inicio
    scene.frame_end = max(int(scene.frame_end), fim + 2)

    model = load_model(resolve_model())
    ctx = _preparar_contexto_armadura(arm)
    estado: dict[str, Any] = {
        "tem_tilt_3d": False,
        "psi_ant": 0.0,
        "psi_init": False,
        "q_pelv_ant": None,
        "q_root_ant": None,
    }
    brutos: list[dict[str, Any]] = []
    for f in range(inicio, fim + 1):
        scene.frame_set(f)
        brutos.append(_amostrar_quadro_blender(arm, ctx, estado))

    eixos = _suavizar_eixos_brutos(brutos)
    todos_quadros, todas_pernas, todas_raizes = _resolver_todos_quadros(
        brutos, eixos, model, bool(estado["tem_tilt_3d"])
    )
    _filtrar_trajetoria(todos_quadros, todas_pernas, todas_raizes, model)
    if centralizar_yaw:
        _centralizar_yaw_se_preciso(todas_raizes, apenas_reverso=True)

    idx_loop = (
        _encontrar_inicio_loop(inicio, inicio_loop_nla, todos_quadros, todas_pernas)
        if eh_loop
        else 0
    )
    quadros_loop = todos_quadros[idx_loop:]
    pernas_loop = todas_pernas[idx_loop:]
    raiz_loop = todas_raizes[idx_loop:]
    if fechar_retorno:
        _fechar_retorno_loop(quadros_loop, pernas_loop, raiz_loop, n_passos=24)
    if eh_loop:
        _suavizar_emenda_loop(quadros_loop, pernas_loop, raiz_loop, janela=8)

    bpm_pad, vel_pad = MAPA_TEMPO_EMOTES.get(estilo, (112.0, 1.0))
    bpm_nativo = bpm_override if bpm_override is not None else bpm_pad
    velocidade = vel_override if vel_override is not None else vel_pad
    dados: dict[str, Any] = {
        "fps": round(FPS_UE_NATIVO, 2),
        "bpm_nativo": round(bpm_nativo, 1),
        "velocidade": round(velocidade, 3),
        "loop": bool(eh_loop),
        "inicio_loop": idx_loop,
        "quadros_intro": todos_quadros[:idx_loop],
        "quadros_pernas_intro": todas_pernas[:idx_loop],
        "raiz_intro": todas_raizes[:idx_loop],
        "quadros": quadros_loop,
        "quadros_pernas": pernas_loop,
        "raiz": raiz_loop,
    }
    deslocamentos = _deslocamentos_horizontais([b["pos_pelve"] for b in brutos])
    dados["deslocamento_intro"] = deslocamentos[:idx_loop]
    dados["deslocamento"] = deslocamentos[idx_loop:]
    while len(dados["deslocamento"]) < len(quadros_loop):
        resto = len(quadros_loop) - len(dados["deslocamento"])
        ultimo = dados["deslocamento"][-1]
        primeiro = dados["deslocamento"][0]
        dados["deslocamento"].append([
            round(a + (b - a) / (resto + 1), 4)
            for a, b in zip(ultimo, primeiro, strict=True)
        ])
    if any(b.get("dedos") for b in brutos):
        todos_dedos = [b.get("dedos", {}) for b in brutos]
        dados["dedos_intro"] = todos_dedos[:idx_loop]
        dedos_loop = todos_dedos[idx_loop:]
        while len(dedos_loop) < len(quadros_loop):
            dedos_loop.append(dedos_loop[0] if dedos_loop else {})
        dados["dedos"] = dedos_loop
    return dados


def _deslocamentos_horizontais(pontos: list[cin.Vec3]) -> list[list[float]]:
    """Converte o trajeto do quadril para unidades do mascote a partir do primeiro quadro."""
    x0, y0, _ = pontos[0]
    return [[round((x - x0) * 0.7, 4), round((y - y0) * 0.7, 4)] for x, y, _ in pontos]


def _imprimir_resumo_clipe(estilo: str, arquivo: str, dados: dict[str, Any]) -> None:
    """Imprime estatísticas resumidas de extração para conferência do lote."""
    giros = [r[1] for r in dados["raiz"]]
    k_max = max((max(p.get("left_knee", 0.0), p.get("right_knee", 0.0)) for p in dados["quadros_pernas"]), default=0.0)
    k_min = min((min(p.get("left_knee", 99.0), p.get("right_knee", 99.0)) for p in dados["quadros_pernas"]), default=0.0)
    e_min = math.degrees(
        min((min(abs(q.get("ant-arm", [0, 0, 9])[2]), abs(q.get("ant-arm2", [0, 0, 9])[2])) for q in dados["quadros"]), default=0.0)
    )
    print(
        f"[OK] {estilo:20s} <- {arquivo:26s} "
        f"(in={len(dados['quadros_intro']):2d}, lp={len(dados['quadros']):3d} loop={int(dados.get('loop', True))} @ {dados['fps']}fps "
        f"v={dados['velocidade']:.2f}x bpm={dados['bpm_nativo']:.0f} "
        f"knee=[{k_min:.0f},{k_max:.0f}] elbMin={e_min:.0f} yaw=[{min(giros):+.0f},{max(giros):+.0f}])",
        flush=True,
    )


def _executar_lote_padrao(pasta_emotes: Path, pasta_loops: Path) -> None:
    """Reexporta todos os emotes configurados em ``MAPA_EMOTES_PADRAO``."""
    for estilo, arquivo in MAPA_EMOTES_PADRAO.items():
        caminho_blend = pasta_emotes / arquivo
        if not caminho_blend.exists():
            continue
        bpy.ops.wm.open_mainfile(filepath=str(caminho_blend))
        dados = extrair_clipe_atual(estilo=estilo)
        dados["estilo"] = estilo
        dados["origem"] = arquivo
        destino = pasta_loops / f"{estilo}.json"
        destino.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        _imprimir_resumo_clipe(estilo, arquivo, dados)


def _executar_lote_mixamo(pasta_mixamo: Path, pasta_loops: Path) -> None:
    """Importa e exporta todos os arquivos Mixamo (.fbx) de ``MAPA_MIXAMO``."""
    pasta_acoes = pasta_loops.parent / "acoes"
    pasta_acoes.mkdir(parents=True, exist_ok=True)
    for estilo, cfg in MAPA_MIXAMO.items():
        caminho_fbx = pasta_mixamo / cfg["arquivo"]
        if not caminho_fbx.exists():
            print(f"[SKIP] {estilo}: nao encontrado {caminho_fbx}", flush=True)
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(caminho_fbx))
        dados = extrair_clipe_atual(
            estilo=estilo,
            frame_inicio=cfg.get("inicio"),
            frame_fim=cfg.get("fim"),
            eh_loop=bool(cfg.get("loop", True)),
            bpm_override=float(cfg["bpm"]),
            vel_override=float(cfg["vel"]),
            centralizar_yaw=bool(cfg.get("centralizar_yaw", False)),
            fechar_retorno=bool(cfg.get("fechar_retorno", False)),
        )
        repetir = int(cfg.get("repetir", 1))
        if repetir > 1:
            for ch in ("quadros", "quadros_pernas", "raiz", "dedos", "deslocamento"):
                if ch in dados and isinstance(dados[ch], list):
                    dados[ch] = dados[ch] * repetir
        dados["estilo"] = estilo
        dados["origem"] = cfg["arquivo"]
        sub = pasta_loops if cfg.get("pasta") == "loops" else pasta_acoes
        destino = sub / f"{estilo}.json"
        destino.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        _imprimir_resumo_clipe(estilo, cfg["arquivo"], dados)


def main() -> None:
    """Executa extração unitária ou em lote (Fortnite / Mixamo) dentro do Blender."""
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--saida", type=str, default="")
    parser.add_argument("--estilo", type=str, default="")
    parser.add_argument("--lote-padrao", action="store_true")
    parser.add_argument("--mixamo-dir", type=str, default="")
    args = parser.parse_args(argv)

    pasta_emotes = ROOT_DIR / "assets" / "animation" / "emotes"
    pasta_loops = ROOT_DIR / "assets" / "animation" / "loops"
    pasta_loops.mkdir(parents=True, exist_ok=True)
    if args.lote_padrao:
        _executar_lote_padrao(pasta_emotes, pasta_loops)
        return
    if args.mixamo_dir:
        _executar_lote_mixamo(Path(args.mixamo_dir), pasta_loops)
        return

    estilo = args.estilo or (Path(args.saida).stem if args.saida else "")
    dados = extrair_clipe_atual(estilo=estilo)
    if args.saida:
        destino = Path(args.saida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()

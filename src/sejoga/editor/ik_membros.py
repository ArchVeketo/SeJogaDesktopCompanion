"""Cinemática inversa e composição de membros em Python puro para o editor.

FRONTEIRA: nunca importa ``panda3d``, ``PySide6`` nem ``win32*``.

Cobre:
- Classificação uniforme dos grupos do rig para o manipulador ``Mover (G)``.
- IK analítica de 2 ossos para as pernas sobre a convenção ``Rx(q) · Ry(roll) · Rz(yaw)``
  do ``LowerBody`` (sem iteração numérica).
- Mira analítica de 1 osso para coxa e composição de ``LegPose`` sobre ``quadro.pose``.
- Conversão sem saltos entre pose total desejada e chave interpolável das pistas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sejoga.animacao.interpolacao import amostrar_pista
from sejoga.animacao.movimento_pernas import LegPose
from sejoga.nucleo.esqueleto import Rotation3

Vec3 = tuple[float, float, float]

GRUPOS_CORPO_INTEIRO = frozenset({"body", "cintura", "legs"})

_ESPEC_IK_FIXA: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "hand": ("ik_braco_dir", "Mão direita (IK braço)", ("right-arm", "ant-arm")),
    "fingers": ("ik_braco_dir", "Dedos direitos (IK braço)", ("right-arm", "ant-arm")),
    "hand2": ("ik_braco_esq", "Mão esquerda (IK braço)", ("left-arm", "ant-arm2")),
    "fingers2": ("ik_braco_esq", "Dedos esquerdos (IK braço)", ("left-arm", "ant-arm2")),
    "right-feet": ("ik_perna_dir", "Pé direito (IK perna)", ("coxa-direita", "canela-direita")),
    "canela-direita": ("ik_perna_dir", "Canela direita (IK perna)", ("coxa-direita", "canela-direita")),
    "left-feet": ("ik_perna_esq", "Pé esquerdo (IK perna)", ("coxa-esquerda", "canela-esquerda")),
    "canela-esquerda": ("ik_perna_esq", "Canela esquerda (IK perna)", ("coxa-esquerda", "canela-esquerda")),
    "coxa-direita": ("coxa_dir", "Coxa direita (mira)", ("coxa-direita",)),
    "joelho-direito": ("coxa_dir", "Joelho direito (mira)", ("coxa-direita",)),
    "coxa-esquerda": ("coxa_esq", "Coxa esquerda (mira)", ("coxa-esquerda",)),
    "joelho-esquerdo": ("coxa_esq", "Joelho esquerdo (mira)", ("coxa-esquerda",)),
}

_NOMES_MIRA: dict[str, str] = {
    "right-arm": "Braço direito (mira)",
    "ant-arm": "Antebraço direito (mira)",
    "left-arm": "Braço esquerdo (mira)",
    "ant-arm2": "Antebraço esquerdo (mira)",
    "abdomen": "Abdômen (mira)",
    "peitoral": "Peitoral (mira)",
    "head": "Cabeça (mira)",
    "door": "Porta da cabeça (mira)",
    "fones": "Fones (mira)",
    "fone-direito": "Fone direito (mira)",
    "fone-esquerdo": "Fone esquerdo (mira)",
    "antena-direita": "Antena direita (mira)",
    "antena-esquerda": "Antena esquerda (mira)",
}

_LADOS_PERNA: tuple[tuple[str, str, str, str, str], ...] = (
    ("left", "coxa-esquerda", "joelho-esquerdo", "canela-esquerda", "left-feet"),
    ("right", "coxa-direita", "joelho-direito", "canela-direita", "right-feet"),
)


@dataclass(frozen=True, slots=True)
class EspecMoverMembro:
    """Descreve o modo cinemático e as juntas gravadas ao mover um membro em 3D."""

    modo: str
    rotulo: str
    juntas: tuple[str, ...]


def resolver_espec_mover_membro(grupo: str) -> EspecMoverMembro | None:
    """Retorna a especificação IK/mira de ``grupo``, ou ``None`` se mover o corpo."""
    if grupo in GRUPOS_CORPO_INTEIRO:
        return None
    fixo = _ESPEC_IK_FIXA.get(grupo)
    if fixo is not None:
        return EspecMoverMembro(modo=fixo[0], rotulo=fixo[1], juntas=fixo[2])
    rot_mira = _NOMES_MIRA.get(grupo)
    if rot_mira is not None:
        return EspecMoverMembro(modo="mira", rotulo=rot_mira, juntas=(grupo,))
    return None


def _clamp(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def _embrulhar_180(ang_graus: float) -> float:
    return (ang_graus + 180.0) % 360.0 - 180.0


def _rot_y(v: Vec3, graus: float) -> Vec3:
    rad = math.radians(graus)
    c, s = math.cos(rad), math.sin(rad)
    return (v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c)


def _rot_z(v: Vec3, graus: float) -> Vec3:
    rad = math.radians(graus)
    c, s = math.cos(rad), math.sin(rad)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])


def _desfazer_yaw_e_calcular_roll(
    d: Vec3,
    x_rest: float,
    yaw_graus: float,
) -> tuple[Vec3, float]:
    d1 = _rot_z(d, -yaw_graus)
    r_xz = math.hypot(d1[0], d1[2])
    if r_xz < 1e-6:
        roll_deg = 0.0
    else:
        ratio = _clamp(x_rest / r_xz, -1.0, 1.0)
        phi = math.atan2(-d1[2], d1[0])
        roll_deg = _embrulhar_180(math.degrees(phi - math.acos(ratio)))
    roll_deg = _clamp(roll_deg, -80.0, 80.0)
    return _rot_y(d1, -roll_deg), roll_deg


def resolver_ik_perna(
    quadril: Vec3,
    joelho: Vec3,
    tornozelo: Vec3,
    alvo_tornozelo: Vec3,
    *,
    yaw_graus: float = 0.0,
) -> tuple[float, float, float]:
    """Resolve ``(ang_quadril, ang_joelho, ang_roll)`` em graus para ``LowerBody``.

    Usa exatamente a ordem de matrizes de ``LowerBody.apply`` (``Rx · Ry · Rz``),
    mantendo o ``yaw_graus`` atual e dobrando o joelho anatomicamente para trás.
    """
    t0 = (joelho[0] - quadril[0], joelho[1] - quadril[1], joelho[2] - quadril[2])
    s0 = (tornozelo[0] - joelho[0], tornozelo[1] - joelho[1], tornozelo[2] - joelho[2])
    d = (
        alvo_tornozelo[0] - quadril[0],
        alvo_tornozelo[1] - quadril[1],
        alvo_tornozelo[2] - quadril[2],
    )
    d2, roll_deg = _desfazer_yaw_e_calcular_roll(d, t0[0] + s0[0], yaw_graus)

    l1 = math.hypot(t0[1], t0[2])
    l2 = math.hypot(s0[1], s0[2])
    if l1 < 1e-6 or l2 < 1e-6:
        return (0.0, 0.0, roll_deg)
    r_yz = _clamp(math.hypot(d2[1], d2[2]), abs(l1 - l2) + 1e-4, l1 + l2 - 1e-4)

    ang_base_t = math.atan2(t0[1], -t0[2])
    ang_base_s = math.atan2(s0[1], -s0[2])
    cos_a = _clamp((l1 * l1 + r_yz * r_yz - l2 * l2) / (2.0 * l1 * r_yz), -1.0, 1.0)
    cos_k = _clamp((l1 * l1 + l2 * l2 - r_yz * r_yz) / (2.0 * l1 * l2), -1.0, 1.0)

    ang_dir = math.atan2(d2[1], -d2[2])
    q_deg = _embrulhar_180(math.degrees(ang_dir - math.acos(cos_a) - ang_base_t))
    k_deg = math.degrees((math.pi - math.acos(cos_k)) - (ang_base_s - ang_base_t))
    return (_clamp(q_deg, -135.0, 135.0), _clamp(k_deg, 0.0, 145.0), roll_deg)


def resolver_mira_coxa(
    quadril: Vec3,
    joelho: Vec3,
    alvo_joelho: Vec3,
    *,
    yaw_graus: float = 0.0,
) -> tuple[float, float]:
    """Resolve ``(ang_quadril, ang_roll)`` em graus para apontar o joelho ao alvo."""
    t0 = (joelho[0] - quadril[0], joelho[1] - quadril[1], joelho[2] - quadril[2])
    d = (
        alvo_joelho[0] - quadril[0],
        alvo_joelho[1] - quadril[1],
        alvo_joelho[2] - quadril[2],
    )
    d2, roll_deg = _desfazer_yaw_e_calcular_roll(d, t0[0], yaw_graus)
    ang_base_t = math.atan2(t0[1], -t0[2])
    ang_dir = math.atan2(d2[1], -d2[2])
    q_deg = _embrulhar_180(math.degrees(ang_dir - ang_base_t))
    return (_clamp(q_deg, -135.0, 135.0), roll_deg)


def extrair_estado_pernas(pose: LegPose | None, lado: str) -> tuple[float, float, float, float]:
    """Lê ``(quadril, joelho, roll, yaw)`` em graus do lado ``'left'`` ou ``'right'``."""
    p = pose or LegPose()
    return (
        float(getattr(p, lado)),
        float(getattr(p, f"{lado}_knee")),
        float(getattr(p, f"{lado}_roll", 0.0)),
        float(getattr(p, f"{lado}_yaw", 0.0)),
    )


def _delta_graus(
    pose: dict[str, Rotation3],
    repouso: dict[str, Rotation3],
    grupo: str,
) -> Vec3:
    r = pose.get(grupo)
    if r is None:
        return (0.0, 0.0, 0.0)
    b = repouso.get(grupo, Rotation3())
    return (
        math.degrees(r.x - b.x),
        math.degrees(r.y - b.y),
        math.degrees(r.z - b.z),
    )


def compor_pose_pernas(
    base: LegPose | None,
    pose: dict[str, Rotation3],
    *,
    repouso: dict[str, Rotation3] | None = None,
) -> LegPose | None:
    """Soma rotações autorais dos grupos de perna sobre a ``LegPose`` base."""
    ref = repouso or {}
    deltas: dict[str, Vec3] = {}
    alterado = False
    for _, coxa, joelho, canela, bota in _LADOS_PERNA:
        for grp in (coxa, joelho, canela, bota):
            d = _delta_graus(pose, ref, grp)
            deltas[grp] = d
            if abs(d[0]) > 1e-5 or abs(d[1]) > 1e-5 or abs(d[2]) > 1e-5:
                alterado = True
    if not alterado:
        return base

    ref_leg = base or LegPose()
    campos: dict[str, float] = {}
    for lado, coxa, joelho, canela, bota in _LADOS_PERNA:
        dc = deltas[coxa]
        dj = deltas[joelho]
        dn = deltas[canela]
        db = deltas[bota]
        campos[lado] = float(getattr(ref_leg, lado)) + dc[0]
        campos[f"{lado}_yaw"] = float(getattr(ref_leg, f"{lado}_yaw", 0.0)) + dc[1]
        campos[f"{lado}_roll"] = float(getattr(ref_leg, f"{lado}_roll", 0.0)) + dc[2]
        campos[f"{lado}_knee"] = float(getattr(ref_leg, f"{lado}_knee")) + dn[0] + dj[0]
        campos[f"{lado}_ankle"] = float(getattr(ref_leg, f"{lado}_ankle", 0.0)) + db[0]
        campos[f"{lado}_ankle_roll"] = float(getattr(ref_leg, f"{lado}_ankle_roll", 0.0)) + db[2]

    return LegPose(
        left=campos["left"],
        right=campos["right"],
        left_knee=campos["left_knee"],
        right_knee=campos["right_knee"],
        left_lift=ref_leg.left_lift,
        right_lift=ref_leg.right_lift,
        left_yaw=campos["left_yaw"],
        right_yaw=campos["right_yaw"],
        left_roll=campos["left_roll"],
        right_roll=campos["right_roll"],
        left_ankle=campos["left_ankle"],
        right_ankle=campos["right_ankle"],
        left_ankle_roll=campos["left_ankle_roll"],
        right_ankle_roll=campos["right_ankle_roll"],
        left_foot_squash=ref_leg.left_foot_squash,
        right_foot_squash=ref_leg.right_foot_squash,
    )


def delta_euler_curto(desejado: Vec3, base: Vec3) -> Vec3:
    """Diferença componente-a-componente em graus embrulhada em ``[-180, 180]``."""
    return (
        _embrulhar_180(desejado[0] - base[0]),
        _embrulhar_180(desejado[1] - base[1]),
        _embrulhar_180(desejado[2] - base[2]),
    )


def amostrar_pista_bloco_no_tempo(
    bloco: dict[str, Any] | None,
    grupo: str,
    tempo_s: float,
    *,
    secao_dados: str = "",
    duracao_acao_s: float | None = None,
) -> Vec3:
    """Retorna o valor atual interpolado de ``tracks[grupo]`` no tempo da ação."""
    if not bloco:
        return (0.0, 0.0, 0.0)
    tracks = bloco.get("tracks", {})
    pista = tracks.get(grupo) if isinstance(tracks, dict) else None
    if not pista:
        return (0.0, 0.0, 0.0)
    dur_bloco = max(1e-6, float(bloco.get("duration", duracao_acao_s or 1.0)))
    t_eff = float(tempo_s)
    if secao_dados == "LOCOMOCAO_CLIPS" and duracao_acao_s:
        u = t_eff / max(0.2, float(duracao_acao_s))
        t_eff = u % dur_bloco if bloco.get("loop", True) else _clamp(u, 0.0, dur_bloco)
    elif bloco.get("loop", False):
        t_eff = t_eff % dur_bloco
    else:
        t_eff = _clamp(t_eff, 0.0, dur_bloco)
    curvas_map = bloco.get("curvas", {})
    curvas = curvas_map.get(grupo) if isinstance(curvas_map, dict) else None
    vx, vy, vz = amostrar_pista(pista, t_eff, curvas=curvas)
    return (float(vx), float(vy), float(vz))


def valor_chave_membro(
    track_inicial: Vec3,
    pose_inicial_deg: Vec3,
    pose_desejada_deg: Vec3,
) -> Vec3:
    """Converte pose desejada total em valor gravável na pista sem salto aditivo."""
    dx, dy, dz = delta_euler_curto(pose_desejada_deg, pose_inicial_deg)
    return (
        round(track_inicial[0] + dx, 4),
        round(track_inicial[1] + dy, 4),
        round(track_inicial[2] + dz, 4),
    )

"""Pose de teimosia: sequência completa do manifesto §1.4.

Extraído de `controlador_animacao.py` para manter o módulo < 200 linhas.
Implementa as 5 fases da teimosia: resistência → repreensão → bote →
roubo do cursor → cospe.

Manifesto: §1.4 — Cena canônica do roubo do mouse.
"""

from __future__ import annotations

import math

from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.pose_repouso import REPOUSO

Trio = tuple[float, float, float]

#: Duração de cada fase da teimosia em segundos.
FASES_TEIMOSIA = {
    "resistencia": (0.0, 1.0),
    "repreensao": (1.0, 2.0),
    "bote": (2.0, 3.0),
    "roubo": (3.0, 5.0),
    "cospe": (5.0, 6.0),
}

_JANELA_BLEND_FASE_S = 0.16

_BASE_TEIMOSIA: dict[str, Trio] = {
    "cintura": (0.0, 0.0, 0.0),
    "abdomen": (0.0, 0.0, 0.0),
    "peitoral": (0.0, 0.0, 0.0),
    "body": (0.0, 0.0, 0.0),
    "head": (0.0, 0.0, 0.0),
    "door": (0.0, 0.0, 0.0),
    "fones": (0.0, 0.0, 0.0),
    "antena-direita": (0.0, 0.0, 0.0),
    "antena-esquerda": (0.0, 0.0, 0.0),
    "shoulder": (0.0, 0.0, 0.0),
    "shoulder2": (0.0, 0.0, 0.0),
    "right-arm": (REPOUSO.BRACO_X, REPOUSO.BRACO_Y, REPOUSO.BRACO_Z),
    "left-arm": (REPOUSO.BRACO_X, -REPOUSO.BRACO_Y, -REPOUSO.BRACO_Z),
    "ant-arm": (REPOUSO.ANTEBRACO_X, 0.0, REPOUSO.ANTEBRACO_Z),
    "ant-arm2": (REPOUSO.ANTEBRACO_X, 0.0, -REPOUSO.ANTEBRACO_Z),
    "hand": (0.0, 0.0, 0.0),
    "hand2": (0.0, 0.0, 0.0),
    "fingers": (0.0, 0.0, 0.0),
    "fingers2": (0.0, 0.0, 0.0),
}


def fase_do_tempo(tempo: float) -> str:
    """Retorna o nome da fase ativa no ``tempo`` dado."""
    for nome, (inicio, fim) in FASES_TEIMOSIA.items():
        if inicio <= tempo < fim:
            return nome
    return "cospe"  # fallback para o final


def _aplicar_dict(rig, pose: dict[str, Trio]) -> None:
    for grupo, (x, y, z) in pose.items():
        rig.set_rotation(grupo, x=x, y=y, z=z)


def _misturar_poses(a: dict[str, Trio], b: dict[str, Trio], peso: float) -> dict[str, Trio]:
    u = max(0.0, min(1.0, peso))
    saida: dict[str, Trio] = {}
    for grupo in _BASE_TEIMOSIA:
        ax, ay, az = a[grupo]
        bx, by, bz = b[grupo]
        saida[grupo] = (
            ax + (bx - ax) * u,
            ay + (by - ay) * u,
            az + (bz - az) * u,
        )
    return saida


def aplicar_fase(
    rig,
    tempo: float,
    direcao_olhar: float = 0.0,
) -> None:
    """Aplica a pose da fase de teimosia no ``rig`` com costura contínua entre fases."""
    t = max(0.0, tempo)
    fase = fase_do_tempo(t)

    construtores = {
        "resistencia": _pose_resistencia,
        "repreensao": _pose_repreensao,
        "bote": _pose_bote,
        "roubo": _pose_roubo,
        "cospe": _pose_cospe,
    }
    anteriores = {
        "repreensao": (1.0, _pose_resistencia),
        "bote": (2.0, _pose_repreensao),
        "roubo": (3.0, _pose_bote),
        "cospe": (5.0, _pose_roubo),
    }

    pose = construtores[fase](t, direcao_olhar)
    if fase in anteriores:
        t_corte, prev_fn = anteriores[fase]
        dt_fase = t - t_corte
        if dt_fase < _JANELA_BLEND_FASE_S:
            peso = suavizar_quintico(dt_fase / _JANELA_BLEND_FASE_S)
            pose_ant = prev_fn(t_corte, direcao_olhar)
            pose = _misturar_poses(pose_ant, pose, peso)

    _aplicar_dict(rig, pose)


def _pose_resistencia(tempo: float, direcao_olhar: float) -> dict[str, Trio]:
    """Fase 1: Mário tensiona o corpo em cascata da cintura às antenas."""
    tensao = suavizar_quintico(min(1.0, tempo / 0.30))
    balanco = math.sin(tempo * 10.0) * tensao
    pose = dict(_BASE_TEIMOSIA)
    pose.update({
        "cintura": (-4.0 * tensao, direcao_olhar * 4.0 * tensao, balanco * 2.5),
        "abdomen": (-4.0 * tensao, direcao_olhar * 4.0 * tensao, balanco * 3.0),
        "peitoral": (-4.0 * tensao, direcao_olhar * 5.0 * tensao, balanco * 3.5),
        "body": (-10.0 * tensao, direcao_olhar * 12.0 * tensao, balanco * 6.0),
        "head": (-15.0 * tensao, direcao_olhar * 30.0 * tensao, 5.0 * tensao - balanco * 2.0),
        "fones": (4.0 * tensao, 0.0, -balanco * 3.0),
        "antena-direita": (9.0 * tensao, 0.0, -5.0 * tensao + balanco * 4.0),
        "antena-esquerda": (9.0 * tensao, 0.0, 5.0 * tensao - balanco * 4.0),
        "shoulder": (-3.0 * tensao, 0.0, 4.0 * tensao),
        "shoulder2": (-3.0 * tensao, 0.0, -4.0 * tensao),
        "right-arm": (REPOUSO.BRACO_X - 20.0 * tensao, REPOUSO.BRACO_Y, REPOUSO.BRACO_Z + 15.0 * tensao),
        "left-arm": (REPOUSO.BRACO_X - 20.0 * tensao, -REPOUSO.BRACO_Y, -REPOUSO.BRACO_Z - 15.0 * tensao),
        "ant-arm": (REPOUSO.ANTEBRACO_X, 0.0, REPOUSO.ANTEBRACO_Z + 18.0 * tensao),
        "ant-arm2": (REPOUSO.ANTEBRACO_X, 0.0, -REPOUSO.ANTEBRACO_Z - 18.0 * tensao),
        "hand": (10.0 * tensao, 0.0, -8.0 * tensao),
        "hand2": (10.0 * tensao, 0.0, 8.0 * tensao),
        "fingers": (0.0, 0.0, 14.0 * tensao),
        "fingers2": (0.0, 0.0, -14.0 * tensao),
    })
    return pose


def _pose_repreensao(tempo: float, direcao_olhar: float) -> dict[str, Trio]:
    """Fase 2: Olhar de desafio para o cursor (pose forte + ombros e dedos vivos)."""
    u = min(1.0, max(0.0, tempo - 1.0))
    batida = 0.5 - 0.5 * math.cos((tempo - 1.0) * 8.0)
    pose = dict(_BASE_TEIMOSIA)
    pose.update({
        "cintura": (2.0 * math.sin(u * math.pi), direcao_olhar * 5.0, 0.0),
        "abdomen": (2.5 * math.sin(u * math.pi), direcao_olhar * 6.0, 0.0),
        "peitoral": (3.0 * math.sin(u * math.pi), direcao_olhar * 8.0, -3.0),
        "body": (4.0 * math.sin(u * math.pi), direcao_olhar * 15.0, -4.0),
        "head": (-8.0, direcao_olhar * 45.0, -6.0 + batida * 2.0),
        "door": (0.0, 4.0 * batida, 0.0),
        "fones": (4.0, 0.0, -4.0),
        "antena-direita": (-6.0 + batida * 4.0, 0.0, -4.0),
        "antena-esquerda": (-6.0 + batida * 4.0, 0.0, 4.0),
        "shoulder": (2.0, 0.0, -5.0),
        "shoulder2": (2.0, 0.0, 5.0),
        "right-arm": (REPOUSO.BRACO_X - 8.0, REPOUSO.BRACO_Y - 10.0, REPOUSO.BRACO_Z - 16.0),
        "left-arm": (REPOUSO.BRACO_X - 8.0, -REPOUSO.BRACO_Y + 10.0, -REPOUSO.BRACO_Z + 16.0),
        "ant-arm": (0.0, 0.0, REPOUSO.ANTEBRACO_Z + 32.0 + batida * 8.0),
        "ant-arm2": (0.0, 0.0, -REPOUSO.ANTEBRACO_Z - 32.0 - batida * 6.0),
        "hand": (12.0 + batida * 6.0, 0.0, -10.0),
        "hand2": (12.0, 0.0, 10.0),
        "fingers": (0.0, 0.0, 10.0),
        "fingers2": (0.0, 0.0, -10.0),
    })
    return pose


def _pose_bote(tempo: float, direcao_olhar: float) -> dict[str, Trio]:
    """Fase 3: Antecipação + agachar e escancarar porta até 48° (manifesto §3.3)."""
    agachar = min(1.0, max(0.0, tempo - 2.0))
    suave = suavizar_quintico(agachar)
    pose = dict(_BASE_TEIMOSIA)
    pose.update({
        # Convenção canônica: -X inclina tronco à frente para o bote.
        "cintura": (-5.0 * suave, direcao_olhar * 4.0, 0.0),
        "abdomen": (-5.5 * suave, direcao_olhar * 4.0, 0.0),
        "peitoral": (-6.5 * suave, direcao_olhar * 5.0, 0.0),
        "body": (-10.0 * suave, direcao_olhar * 10.0, 0.0),
        "head": (12.0 * suave, direcao_olhar * 20.0, 0.0),
        "fones": (10.0 * suave, 0.0, 0.0),
        "antena-direita": (16.0 * suave, 0.0, -6.0 * suave),
        "antena-esquerda": (16.0 * suave, 0.0, 6.0 * suave),
        "shoulder": (-5.0 * suave, 0.0, 6.0 * suave),
        "shoulder2": (-5.0 * suave, 0.0, -6.0 * suave),
        "door": (0.0, 48.0 * suave, 0.0),
        "right-arm": (REPOUSO.BRACO_X - 42.0 * suave, REPOUSO.BRACO_Y, REPOUSO.BRACO_Z - 14.0 * suave),
        "left-arm": (REPOUSO.BRACO_X - 42.0 * suave, -REPOUSO.BRACO_Y, -REPOUSO.BRACO_Z + 14.0 * suave),
        "ant-arm": (-14.0 * suave, 0.0, REPOUSO.ANTEBRACO_Z + 24.0 * suave),
        "ant-arm2": (-14.0 * suave, 0.0, -REPOUSO.ANTEBRACO_Z - 24.0 * suave),
        "hand": (18.0 * suave, 0.0, -12.0 * suave),
        "hand2": (18.0 * suave, 0.0, 12.0 * suave),
        "fingers": (0.0, 0.0, -18.0 * suave),
        "fingers2": (0.0, 0.0, 18.0 * suave),
    })
    return pose


def _pose_roubo(tempo: float, direcao_olhar: float) -> dict[str, Trio]:
    """Fase 4: Roubo do mouse — tronco dinâmico com braços em corrida."""
    del direcao_olhar
    dt_roubo = max(0.0, tempo - 3.0)
    correr = math.sin(dt_roubo * 10.0) * 10.0
    osc = math.cos(dt_roubo * 10.0)
    pose = dict(_BASE_TEIMOSIA)
    pose.update({
        "cintura": (3.0, -correr * 0.4, osc * 2.5),
        "abdomen": (4.0, correr * 0.25, 0.0),
        "peitoral": (5.0, correr * 0.5, 0.0),
        "body": (8.0, correr * 0.5, osc * 4.0),
        "head": (-10.0, correr, -osc * 2.0),
        "door": (0.0, 18.0 + math.sin(dt_roubo * 12.0) * 4.0, 0.0),
        "fones": (6.0, 0.0, osc * 4.0),
        "antena-direita": (14.0 - osc * 6.0, 0.0, osc * 5.0),
        "antena-esquerda": (14.0 + osc * 6.0, 0.0, -osc * 5.0),
        "shoulder": (correr * 0.4, 0.0, -3.0),
        "shoulder2": (-correr * 0.4, 0.0, 3.0),
        "right-arm": (REPOUSO.BRACO_X - 28.0 + correr * 1.6, REPOUSO.BRACO_Y, REPOUSO.BRACO_Z),
        "left-arm": (REPOUSO.BRACO_X - 28.0 - correr * 1.6, -REPOUSO.BRACO_Y, -REPOUSO.BRACO_Z),
        "ant-arm": (0.0, 0.0, REPOUSO.ANTEBRACO_Z + 28.0 + 0.6 * (math.sqrt(correr * correr + 1.0) - correr)),
        "ant-arm2": (0.0, 0.0, -REPOUSO.ANTEBRACO_Z - 28.0 - 0.6 * (math.sqrt(correr * correr + 1.0) + correr)),
        "hand": (10.0 + correr * 0.8, 0.0, 0.0),
        "hand2": (10.0 - correr * 0.8, 0.0, 0.0),
        "fingers": (0.0, 0.0, 14.0),
        "fingers2": (0.0, 0.0, -14.0),
    })
    return pose


def _pose_cospe(tempo: float, direcao_olhar: float) -> dict[str, Trio]:
    """Fase 5: Cospe o cursor de volta com quique elástico e assentamento limpo em REPOUSO."""
    cospe_t = min(1.0, max(0.0, tempo - 5.0))
    quique = math.sin(cospe_t * math.pi * 3.0) * (1.0 - cospe_t) * 20.0
    porta = 48.0 * math.sin(min(1.0, cospe_t * 2.0) * math.pi)
    decai = 1.0 - suavizar_quintico(cospe_t)
    pose = dict(_BASE_TEIMOSIA)
    pose.update({
        "cintura": (-5.0 * decai, direcao_olhar * 6.0 * decai, 0.0),
        "abdomen": (-6.0 * decai, direcao_olhar * 8.0 * decai, 0.0),
        "peitoral": (-8.0 * decai, direcao_olhar * 10.0 * decai, 0.0),
        "body": (-12.0 * decai, direcao_olhar * 15.0 * decai, 0.0),
        "head": (quique, direcao_olhar * 30.0 * decai, 0.0),
        "door": (0.0, max(0.0, porta), 0.0),
        "fones": (-quique * 0.3, 0.0, 0.0),
        "antena-direita": (-quique * 0.5, 0.0, -6.0 * decai),
        "antena-esquerda": (-quique * 0.5, 0.0, 6.0 * decai),
        "shoulder": (3.0 * decai, 0.0, -4.0 * decai),
        "shoulder2": (3.0 * decai, 0.0, 4.0 * decai),
        "right-arm": (REPOUSO.BRACO_X - 10.0 * decai, REPOUSO.BRACO_Y, REPOUSO.BRACO_Z - 18.0 * decai),
        "left-arm": (REPOUSO.BRACO_X - 10.0 * decai, -REPOUSO.BRACO_Y, -REPOUSO.BRACO_Z + 18.0 * decai),
        "ant-arm": (REPOUSO.ANTEBRACO_X, 0.0, REPOUSO.ANTEBRACO_Z + 18.0 * decai),
        "ant-arm2": (REPOUSO.ANTEBRACO_X, 0.0, -REPOUSO.ANTEBRACO_Z - 18.0 * decai),
        "hand": (12.0 * decai, 0.0, -8.0 * decai),
        "hand2": (12.0 * decai, 0.0, 8.0 * decai),
        "fingers": (0.0, 0.0, -16.0 * decai),
        "fingers2": (0.0, 0.0, 16.0 * decai),
    })
    return pose

"""Mede a continuidade da pose na entrada de uma transição autoral."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from math import degrees, sin, sqrt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sejoga.animacao.resolvedor_poses import PoseResolver
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rotation3


@dataclass(frozen=True, slots=True)
class MedicaoSaltoJunta:
    """Salto de pose e velocidade de uma junta na troca de estado."""

    grupo: str
    salto_pose_graus: float
    salto_vel_graus_s: float
    vel_antes_graus_s: float
    vel_depois_graus_s: float
    vel_rel_antes_graus_s: float = 0.0
    vel_rel_depois_graus_s: float = 0.0


def _norma_rot(a: Rotation3, b: Rotation3) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    dz = a.z - b.z
    return sqrt(dx * dx + dy * dy + dz * dz)


def _velocidade(atual: Rotation3, anterior: Rotation3, dt: float) -> Rotation3:
    return Rotation3(
        (atual.x - anterior.x) / dt,
        (atual.y - anterior.y) / dt,
        (atual.z - anterior.z) / dt,
    )


def _alvo_destino(t_local: float, alvo_movel: bool) -> dict[str, Rotation3]:
    if not alvo_movel:
        return {g: Rotation3(x=-0.15, y=0.10, z=-0.20) for g in ALL_GROUPS}
    onda = sin(t_local * 5.0 + 0.4)
    return {
        g: Rotation3(
            x=-0.15 + 0.18 * onda,
            y=0.10 - 0.14 * onda,
            z=-0.20 + 0.24 * onda,
        )
        for g in ALL_GROUPS
    }


def _registrar_medicao(
    grupo: str,
    dt: float,
    pose_antes: dict[str, Rotation3],
    pose_anterior: dict[str, Rotation3],
    pose_transicao: dict[str, Rotation3],
    proximo: dict[str, Rotation3],
    alvo_0: dict[str, Rotation3],
    alvo_1: dict[str, Rotation3],
    alvo_anterior: dict[str, Rotation3],
) -> MedicaoSaltoJunta:
    v_antes = _velocidade(pose_antes[grupo], pose_anterior[grupo], dt)
    v_depois = _velocidade(proximo[grupo], pose_transicao[grupo], dt)
    v_alvo_antes = _velocidade(alvo_0[grupo], alvo_anterior[grupo], dt)
    v_alvo_depois = _velocidade(alvo_1[grupo], alvo_0[grupo], dt)
    return MedicaoSaltoJunta(
        grupo=grupo,
        salto_pose_graus=degrees(_norma_rot(pose_transicao[grupo], pose_antes[grupo])),
        salto_vel_graus_s=degrees(_norma_rot(v_depois, v_antes)),
        vel_antes_graus_s=degrees(_norma_rot(v_antes, Rotation3())),
        vel_depois_graus_s=degrees(_norma_rot(v_depois, Rotation3())),
        vel_rel_antes_graus_s=degrees(_norma_rot(v_antes, v_alvo_antes)),
        vel_rel_depois_graus_s=degrees(_norma_rot(v_depois, v_alvo_depois)),
    )


def medir_transicao(
    *,
    dt: float = 1.0 / 60.0,
    quadros_antes: int = 25,
    transition_seconds: float = 0.55,
    alvo_movel: bool = False,
) -> list[MedicaoSaltoJunta]:
    """Simula troca de estado no meio do movimento para destino fixo ou em movimento."""
    resolver = PoseResolver()
    pose_anterior = {g: Rotation3() for g in ALL_GROUPS}
    pose_atual = dict(pose_anterior)
    alvo_anterior = dict(pose_anterior)
    for quadro in range(quadros_antes):
        t = (quadro + 1) * dt
        fase = sin(t * 6.0)
        alvo_movimento = {
            g: Rotation3(x=0.35 * fase, y=0.25 * fase, z=0.55 * fase) for g in ALL_GROUPS
        }
        pose_anterior, alvo_anterior = pose_atual, alvo_movimento
        pose_atual = resolver.resolver(dt, alvo_movimento, state_time=t)

    pose_antes = dict(pose_atual)
    resolver.iniciar_transicao(pose_antes, transition_seconds=transition_seconds)
    alvo_0, alvo_1 = _alvo_destino(0.0, alvo_movel), _alvo_destino(dt, alvo_movel)
    pose_transicao = resolver.resolver(dt, alvo_0, state_time=0.0)
    proximo = resolver.resolver(dt, alvo_1, state_time=dt)

    medicoes = [
        _registrar_medicao(
            grupo, dt, pose_antes, pose_anterior, pose_transicao, proximo, alvo_0, alvo_1, alvo_anterior
        )
        for grupo in ALL_GROUPS
    ]
    medicoes.sort(key=lambda m: m.salto_vel_graus_s, reverse=True)
    return medicoes


def main() -> None:
    """Imprime a tabela de saltos por junta ordenada pelas piores (fixo e alvo móvel)."""
    for titulo, movel in (("Destino estatico", False), ("Destino em movimento", True)):
        print(f"=== {titulo} ===")
        medicoes = medir_transicao(alvo_movel=movel)
        print(
            f"{'Junta':<14} | {'|Δpose| (°)':>12} | {'|v_antes| (°/s)':>15} | "
            f"{'|v_depois| (°/s)':>16} | {'|Δvel| (°/s)':>13} | {'|v_rel_dep| (°/s)':>17}"
        )
        print("-" * 100)
        for m in medicoes[:8]:
            print(
                f"{m.grupo:<14} | {m.salto_pose_graus:12.4f} | "
                f"{m.vel_antes_graus_s:15.2f} | {m.vel_depois_graus_s:16.2f} | "
                f"{m.salto_vel_graus_s:13.2f} | {m.vel_rel_depois_graus_s:17.2f}"
            )


if __name__ == "__main__":
    main()

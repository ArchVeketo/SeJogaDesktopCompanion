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


def medir_transicao(
    *,
    dt: float = 1.0 / 60.0,
    quadros_antes: int = 25,
    transition_seconds: float = 0.55,
) -> list[MedicaoSaltoJunta]:
    """Simula um membro em balanço que sofre troca de estado no meio do movimento."""
    resolver = PoseResolver()
    pose_inicial = {g: Rotation3() for g in ALL_GROUPS}
    pose_anterior = pose_inicial
    pose_atual = pose_inicial
    for quadro in range(quadros_antes):
        t = (quadro + 1) * dt
        fase = sin(t * 6.0)
        alvo_movimento = {
            g: Rotation3(
                x=0.35 * fase,
                y=0.25 * fase,
                z=0.55 * fase,
            )
            for g in ALL_GROUPS
        }
        pose_anterior = pose_atual
        pose_atual = resolver.resolver(dt, alvo_movimento, state_time=t)

    pose_antes = dict(pose_atual)

    # Dispara transição para um novo estado (ex.: retorno ao repouso neutro)
    resolver.iniciar_transicao(pose_antes, transition_seconds=transition_seconds)
    alvo_novo = {g: Rotation3(x=-0.15, y=0.10, z=-0.20) for g in ALL_GROUPS}
    pose_transicao = resolver.resolver(dt, alvo_novo, state_time=0.0)
    proximo = resolver.resolver(dt, alvo_novo, state_time=dt)

    medicoes: list[MedicaoSaltoJunta] = []
    for grupo in ALL_GROUPS:
        salto_pose = degrees(_norma_rot(pose_transicao[grupo], pose_antes[grupo]))
        v_antes = _velocidade(pose_antes[grupo], pose_anterior[grupo], dt)
        v_depois = _velocidade(proximo[grupo], pose_transicao[grupo], dt)
        salto_vel = degrees(_norma_rot(v_depois, v_antes))
        medicoes.append(
            MedicaoSaltoJunta(
                grupo=grupo,
                salto_pose_graus=salto_pose,
                salto_vel_graus_s=salto_vel,
                vel_antes_graus_s=degrees(_norma_rot(v_antes, Rotation3())),
                vel_depois_graus_s=degrees(_norma_rot(v_depois, Rotation3())),
            )
        )

    medicoes.sort(key=lambda m: m.salto_vel_graus_s, reverse=True)
    return medicoes


def main() -> None:
    """Imprime a tabela de saltos por junta ordenada pelas piores."""
    medicoes = medir_transicao()
    print(
        f"{'Junta':<14} | {'|Δpose| (°)':>12} | {'|v_antes| (°/s)':>15} | "
        f"{'|v_depois| (°/s)':>16} | {'|Δvel| (°/s)':>13}"
    )
    print("-" * 80)
    for m in medicoes:
        print(
            f"{m.grupo:<14} | {m.salto_pose_graus:12.4f} | "
            f"{m.vel_antes_graus_s:15.2f} | {m.vel_depois_graus_s:16.2f} | "
            f"{m.salto_vel_graus_s:13.2f}"
        )


if __name__ == "__main__":
    main()

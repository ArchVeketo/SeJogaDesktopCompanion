"""Mede saltos de pose e de velocidade em transições de estado do PoseResolver.

Verifica na prática o achado 3.2 de ``docs/ESTUDO_ANIMACAO_PROCEDURAL.md``:
quando um membro está em movimento e o estado muda, ``iniciar_transicao``
pode descartar a velocidade das molas, causando um salto de velocidade (jerk).

FRONTEIRA: Python puro, sem Panda3D/Qt/Win32.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from math import degrees, sin, sqrt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sejoga.animacao.mola_tuning import amortecimento_de, frequencia_de
from sejoga.animacao.resolvedor_poses import PoseResolver
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rotation3


@dataclass(frozen=True, slots=True)
class MedicaoSaltoJunta:
    """Salto de pose e velocidade de uma junta na troca de estado."""

    grupo: str
    salto_pose_graus: float
    salto_vel_mola_graus_s: float
    vel_antes_graus_s: float
    vel_depois_graus_s: float


def _norma_rot(a: Rotation3, b: Rotation3) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    dz = a.z - b.z
    return sqrt(dx * dx + dy * dy + dz * dz)


def _velocidade_mola(resolver: PoseResolver, grupo: str) -> Rotation3:
    mola = resolver.molas.get(grupo)
    if mola is None:
        return Rotation3()
    return Rotation3(mola.x.velocity, mola.y.velocity, mola.z.velocity)


def medir_transicao(
    *,
    dt: float = 1.0 / 60.0,
    quadros_antes: int = 25,
    transition_seconds: float = 0.55,
) -> list[MedicaoSaltoJunta]:
    """Simula um membro em balanço que sofre troca de estado no meio do movimento."""
    firme = (frequencia_de("body"), amortecimento_de("body"))
    tensoes = {
        grupo: (
            firme
            if grupo in ("legs", "left-feet", "right-feet")
            else (frequencia_de(grupo), amortecimento_de(grupo))
        )
        for grupo in ALL_GROUPS
    }
    resolver = PoseResolver(tensoes_crossfade=tensoes)
    pose_inicial = {g: Rotation3() for g in ALL_GROUPS}
    resolver.definir_pose(pose_inicial)

    # Alimenta uma pose oscilante por ``quadros_antes`` quadros para que todas
    # as juntas estejam com velocidade não nula no instante da troca.
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
        pose_atual = resolver.resolver(dt, alvo_movimento, state_time=t)

    vel_mola_antes = {g: _velocidade_mola(resolver, g) for g in ALL_GROUPS}
    pose_antes = dict(pose_atual)

    # Dispara transição para um novo estado (ex.: retorno ao repouso neutro)
    resolver.iniciar_transicao(pose_antes, transition_seconds=transition_seconds)
    alvo_novo = {g: Rotation3(x=-0.15, y=0.10, z=-0.20) for g in ALL_GROUPS}
    pose_transicao = resolver.resolver(dt, alvo_novo, state_time=0.0)
    vel_mola_depois = {g: _velocidade_mola(resolver, g) for g in ALL_GROUPS}

    medicoes: list[MedicaoSaltoJunta] = []
    for grupo in ALL_GROUPS:
        salto_pose = degrees(_norma_rot(pose_transicao[grupo], pose_antes[grupo]))
        v_antes = vel_mola_antes[grupo]
        v_depois = vel_mola_depois[grupo]
        salto_vel = degrees(_norma_rot(v_depois, v_antes))
        medicoes.append(
            MedicaoSaltoJunta(
                grupo=grupo,
                salto_pose_graus=salto_pose,
                salto_vel_mola_graus_s=salto_vel,
                vel_antes_graus_s=degrees(_norma_rot(v_antes, Rotation3())),
                vel_depois_graus_s=degrees(_norma_rot(v_depois, Rotation3())),
            )
        )

    medicoes.sort(key=lambda m: m.salto_vel_mola_graus_s, reverse=True)
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
            f"{m.salto_vel_mola_graus_s:13.2f}"
        )


if __name__ == "__main__":
    main()

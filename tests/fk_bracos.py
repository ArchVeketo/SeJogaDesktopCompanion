"""Apoio dos testes: punho relativo ao ombro pela FK do grafo de cena.

Os testes de pose deixam de afirmar ângulos (a convenção antiga de "z>50 =
braço baixado" não vale na FK real) e passam a afirmar POSIÇÃO: punho acima ou
abaixo do ombro, à frente ou atrás, espelhado ou não. Eixos de ``arm_targets``:
``(direita, cima, frente)``.
"""

from __future__ import annotations

from functools import lru_cache

from sejoga.animacao import arm_ik
from sejoga.nucleo.recursos import resolve_model
from sejoga.nucleo.modelo import Model, load_model


@lru_cache(maxsize=1)
def modelo() -> Model:
    return load_model(resolve_model())


def punho(pose, lado: str = "right") -> tuple[float, float, float]:
    """Punho relativo ao ombro ``(direita, cima, frente)`` para a pose."""
    braco, antebraco = ("right-arm", "ant-arm") if lado == "right" else ("left-arm", "ant-arm2")

    return arm_ik.posicao_mao_para_hpr(modelo(), lado, pose[braco], pose[antebraco], pose)

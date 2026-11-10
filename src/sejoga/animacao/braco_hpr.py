"""HPR do braço por alvo de mão, resolvido por IK e cacheado.

Saiu de ``nucleo/esqueleto.py``: depende do solver de ``animacao``, e
``nucleo`` não importa ``animacao``.
"""

from __future__ import annotations

from math import degrees

from sejoga.animacao import ik_bracos
from sejoga.animacao.alvos_bracos import ALVOS
from sejoga.nucleo.esqueleto import Rotation3
from sejoga.nucleo.modelo import Model, load_model
from sejoga.nucleo.recursos import resolve_model

# --------------------------------------------------------------------------- #
# IK de braço: resolução preguiçosa do Model + cache dos HPR por alvo de mão
# --------------------------------------------------------------------------- #
# Os gestos de braço declaram ALVOS DE MÃO (ver sejoga.animacao.alvos_bracos) e o
# solver 3D (sejoga.animacao.ik_bracos) os converte nos HPR reais dos bones. Como
# resolver a IK a cada frame custaria caro, cacheamos o HPR por (alvo, lado): os
# alvos dos gestos são fixos, então a cadeia FK roda uma vez por alvo.
_MODELO_IK_CACHE: Model | None = None
_HPR_ALVO_CACHE: dict[tuple, dict[str, Rotation3]] = {}


def _modelo_ik() -> Model:
    """Carrega o Model de produção uma vez (resolução preguiçosa, cacheada)."""
    global _MODELO_IK_CACHE

    if _MODELO_IK_CACHE is None:
        _MODELO_IK_CACHE = load_model(resolve_model())

    return _MODELO_IK_CACHE


def definir_modelo_ik(model: Model | None) -> None:
    """Injeta o Model usado pela IK de braço (ex.: o renderer passa o seu).

    Limpa o cache de HPR para recomputar os alvos com a nova geometria.
    """
    global _MODELO_IK_CACHE

    _MODELO_IK_CACHE = model
    _HPR_ALVO_CACHE.clear()


def braco_hpr_graus(
    lado: str, nome_alvo: str, model: Model | None = None
) -> dict[str, tuple[float, float, float]]:
    """Devolve o HPR (graus) do braço do ``lado`` para o alvo de mão nomeado em arm_targets.

    Devolve ``{grupo: (x_pitch, y_heading, z_roll)}`` em GRAUS, pronto para
    ``rig.set_rotation``. Cacheado por (lado, nome_alvo). O eixo X (torção) fica
    em 0: o IK posiciona a mão; o giro do pulso é termo aditivo do gesto.
    """
    chave = (lado, nome_alvo)
    cache = _HPR_ALVO_CACHE.get(chave)

    if cache is None:
        alvo = ALVOS[nome_alvo]
        m = model if model is not None else _modelo_ik()
        alvo_lado = alvo.alvo if lado == "right" else alvo.alvo_espelhado()
        cache = ik_bracos.braco_para(m, lado, alvo_lado, alvo.polo)
        _HPR_ALVO_CACHE[chave] = cache

    return {
        grupo: (degrees(rot.x), degrees(rot.y), degrees(rot.z))
        for grupo, rot in cache.items()
    }

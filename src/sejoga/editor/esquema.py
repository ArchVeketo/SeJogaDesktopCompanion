"""Esquema puro, limites numéricos e validação estrutural de ``animation.py``.

Sem dependências de Panda3D, Qt ou Win32.
"""

from __future__ import annotations

from dataclasses import dataclass

from sejoga.animacao.interpolacao import CURVAS_SUPORTADAS
from sejoga.nucleo.esqueleto import ALL_GROUPS

TOP_LEVEL_KEYS: tuple[str, ...] = (
    "VERSAO_ESQUEMA",
    "IDLE_CLIPS",
    "CENAS_IDLE",
    "LOCOMOCAO_CLIPS",
    "RESPIRACAO",
    "DANCA",
    "TENTACULOS",
    "REACOES",
    "VFX",
    "CLIPES_GLTF",
)

EXTRAS_RIG_GLTF: frozenset[str] = frozenset(
    {
        "root",
        "pelvis",
        "Armario",
        "Porta",
        "fio do fone",
        "circ",
        "circ2",
        "circ_antena",
        "circ2_antena",
        "argola_sup_dir",
        "argola_inf_dir",
        "argola_sup_esq",
        "argola_inf_esq",
    }
)
GRUPOS_RIG_VALIDOS: frozenset[str] = frozenset(ALL_GROUPS) | EXTRAS_RIG_GLTF

ANCORAS_VFX_VALIDAS: frozenset[str] = (
    frozenset(
        {
            "cabeca",
            "antenas",
            "fone_dir",
            "fone_esq",
            "suor",
            "raiva",
            "boca",
            "pes",
            "ombro_l",
            "ombro_r",
            "tronco",
            "antena_d",
            "antena_e",
            "caixa_som",
        }
    )
    | GRUPOS_RIG_VALIDOS
)

CURVAS_VALIDAS: frozenset[str] = frozenset(CURVAS_SUPORTADAS)


@dataclass(frozen=True, slots=True)
class LimiteCampo:
    """Faixa válida e unidade exibida pelo inspetor e pelos validadores."""

    minimo: float
    maximo: float
    unidade: str
    passo: float = 0.5
    casas: int = 2


LIMITES_JUNTA = LimiteCampo(-360.0, 360.0, "°", passo=1.0, casas=2)
LIMITES_DURACAO = LimiteCampo(0.05, 120.0, "s", passo=0.05, casas=3)
LIMITES_BLENDS = LimiteCampo(0.0, 10.0, "s", passo=0.02, casas=3)
LIMITES_PESO = LimiteCampo(0.0, 2.0, "", passo=0.05, casas=2)
LIMITES_FREQUENCIA = LimiteCampo(0.01, 5.0, "Hz", passo=0.02, casas=3)
LIMITES_ESCALA_VFX = LimiteCampo(0.05, 32.0, "x", passo=0.1, casas=2)
LIMITES_BPM = LimiteCampo(30.0, 260.0, "BPM", passo=1.0, casas=1)
LIMITES_COR_CANAL = LimiteCampo(0.0, 1.0, "", passo=0.05, casas=3)

GRUPOS_PRINCIPAIS_EDITOR: tuple[str, ...] = ALL_GROUPS


def grupo_rig_valido(nome: str) -> bool:
    """Indica se ``nome`` (ou sua raiz antes de ``:``) é um nó válido do rig."""
    base = nome.split(":", 1)[0]
    return base in GRUPOS_RIG_VALIDOS


def ancora_vfx_valida(nome: str) -> bool:
    """Indica se ``nome`` é uma âncora conhecida para disparo de VFX."""
    return nome in ANCORAS_VFX_VALIDAS

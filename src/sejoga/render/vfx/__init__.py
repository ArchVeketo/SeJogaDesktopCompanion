"""Registro modular de emissores VFX autorais por estilo (SPEC_PRODUCAO_VFX_E_MODELOS_3D).

Cada estilo canônico (`blockbench`, `street`, `anime`, `spiderverse`, `holograma`)
mantém seu próprio módulo nesta pasta e registra aqui os eventos já migrados.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from panda3d.core import Vec3

from sejoga.render.vfx.anime import EMISSORES_ANIME
from sejoga.render.vfx.blockbench import EMISSORES_BLOCKBENCH
from sejoga.render.vfx.holograma import EMISSORES_HOLOGRAMA
from sejoga.render.vfx.spiderverse import EMISSORES_SPIDERVERSE
from sejoga.render.vfx.street import EMISSORES_STREET

if TYPE_CHECKING:
    from sejoga.render.efeitos_street import GerenciadorEfeitosStreet

EmissorVfx = Callable[..., None]

EMISSORES_POR_ESTILO: dict[str, dict[str, EmissorVfx]] = {
    "blockbench": EMISSORES_BLOCKBENCH,
    "street": EMISSORES_STREET,
    "anime": EMISSORES_ANIME,
    "spiderverse": EMISSORES_SPIDERVERSE,
    "holograma": EMISSORES_HOLOGRAMA,
}


def emitir_vfx_registrado(
    mgr: GerenciadorEfeitosStreet,
    filtro: str,
    evento: str,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> bool:
    """Despacha para o emissor autoral registrado, retornando True se tratado."""
    emissor = EMISSORES_POR_ESTILO.get(filtro, {}).get(evento)
    if emissor is None:
        return False
    emissor(mgr, anc, pos=pos, vel=vel, dir_x=dir_x, forca=forca)
    return True

"""Origem, direção e duração dos grafismos de cada ação do Mário."""

from __future__ import annotations

from math import atan2, degrees
from typing import TYPE_CHECKING

from panda3d.core import Vec3

from sejoga.render.vfx import emitir_vfx_registrado
from sejoga.render.vfx_volume import emitir_blocos, emitir_street

if TYPE_CHECKING:
    from sejoga.render.efeitos_street import GerenciadorEfeitosStreet

# Índices usados pelos desenhos GLSL. Duração em segundos e tamanho no espaço do rig.
_EVENTOS = {
    "impacto_chao": (0, 0.52, 1.25),
    "acento_danca": (1, 0.39, 1.10),
    "musica": (1, 0.39, 1.00),
    "choque": (2, 0.34, 0.93),
    "rastro": (3, 0.36, 1.0),
    "poeira_passo": (0, 0.34, 0.65),
    "carinho": (4, 0.86, 0.92),
    "sono": (5, 1.08, 0.78),
    "calor": (6, 0.70, 0.88),
    "irritado": (6, 0.74, 0.92),
    "sobressalto": (7, 0.30, 0.80),
    "impacto_parede": (8, 0.44, 1.15),
    "tontura": (5, 1.05, 0.88),
    "sinal_radio": (1, 0.58, 0.88),
    "curiosidade": (7, 0.68, 0.85),
    "brilho_estilo": (4, 0.72, 0.88),
}

_ANCORAS_EMOCAO = {
    "carinho": ("cabeca_topo", 53.0),
    "sono": ("visor_lado", 22.0),
    "calor": ("templo", 73.0),
    "irritado": ("templo", 73.0),
    "tontura": ("cabeca_topo", 0.0),
    "curiosidade": ("visor_lado", 18.0),
    "brilho_estilo": ("cabeca_topo", 0.0),
}


def _emitir_marca(
    mgr: GerenciadorEfeitosStreet,
    evento: str,
    codigo: int,
    ponto: Vec3,
    *,
    lado: float = 1.0,
    angulo: float = 0.0,
    tamanho: float = 1.0,
    vida: float = 0.4,
    ancora: str | None = None,
) -> None:
    volumes = {"padrao": emitir_street, "blockbench": emitir_blocos}
    if mgr._filtro in volumes:
        volumes[mgr._filtro](mgr, evento, ponto, lado, angulo, tamanho, vida, ancora)
        return
    mgr.emitir_grafismo(evento, codigo, ponto, lado, angulo, tamanho, vida)


def _despachar_legado(
    mgr: GerenciadorEfeitosStreet,
    evento: str,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None,
    vel: Vec3 | None,
    dir_x: float,
    forca: float,
) -> None:
    codigo, vida, escala = _EVENTOS[evento]
    tamanho = escala * forca
    if vel is not None:
        tamanho *= max(0.72, min(1.55, 0.72 + vel.length() * 0.22))

    if evento == "impacto_chao" and forca >= 0.9:
        for lado, sola in ((-1.0, "sola_esq"), (1.0, "sola_dir")):
            ponto = anc.get(sola, anc["pes"] + Vec3(lado * 0.78, 0, 0))
            _emitir_marca(mgr, evento, codigo, ponto, lado=lado, tamanho=tamanho, vida=vida)
    elif evento == "sobressalto":
        for chave, lado in (("fone_dir", -1.0), ("fone_esq", 1.0)):
            _emitir_marca(mgr, evento, codigo, anc[chave], lado=lado, angulo=8.0, tamanho=tamanho, vida=vida)
    elif evento in _ANCORAS_EMOCAO:
        ancora, angulo = _ANCORAS_EMOCAO[evento]
        _emitir_marca(
            mgr, evento, codigo, anc[ancora], lado=1.0, angulo=angulo, tamanho=tamanho, vida=vida, ancora=ancora
        )
    elif evento == "choque":
        for chave, lado in (("antena_d", -1.0), ("antena_e", 1.0)):
            _emitir_marca(mgr, evento, codigo, anc[chave], lado=lado, angulo=34.0, tamanho=tamanho, vida=vida)
    elif pos is not None:
        lado = dir_x if vel is None else (-1.0 if vel.x < 0 else 1.0)
        angulo = 0.0 if vel is None else degrees(atan2(vel.z, abs(vel.x)))
        _emitir_marca(mgr, evento, codigo, pos, lado=lado, angulo=angulo, tamanho=tamanho, vida=vida)


def emitir_evento_estilo(
    mgr: GerenciadorEfeitosStreet,
    paleta: str,
    evento: str,
    anc: dict[str, Vec3],
    *,
    pos: Vec3 | None = None,
    vel: Vec3 | None = None,
    dir_x: float = 1.0,
    forca: float = 1.0,
) -> None:
    """Emite no ponto de contato, orientando o desenho no sentido do impulso."""
    if emitir_vfx_registrado(
        mgr, mgr._filtro, evento, anc, pos=pos, vel=vel, dir_x=dir_x, forca=forca
    ):
        return
    _despachar_legado(mgr, evento, anc, pos=pos, vel=vel, dir_x=dir_x, forca=forca)
    _ilustrar_evento(mgr, paleta, evento, anc, pos, dir_x, forca)


def _ilustrar_evento(mgr, paleta, evento, anc, pos, lado, forca):
    if paleta == "auto":
        return
    # Reservar as ilustrações para os acentos evita sobrepor selos no rastro contínuo.
    if evento == "impacto_chao" and forca >= 1.15:
        ponto = anc["pes"] + Vec3(0, -0.10, 0.16)
        nome = "queda_chao"
    elif evento == "acento_danca" and pos is not None:
        ponto = pos + Vec3(0.52 * lado, 0, 0.36)
        nome = "musica"
    elif evento in ("carinho", "sono", "calor", "sobressalto", "choque"):
        nome = {"calor": "raiva", "sobressalto": "susto"}.get(evento, evento)
        ponto = anc["cabeca_topo"] + Vec3(-0.36, 0, 0.30)
    else:
        return
    mgr.emitir_cartao(
        nome, ponto, plane_y=ponto.y, vel=Vec3(-0.26, 0, 0.50), scale_x=0.88, ttl=0.54
    )

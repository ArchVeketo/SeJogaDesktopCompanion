"""Prop 3D ejetado pelo armário do Mário na cena ``cuspir_item``.

Carrega ``radio-compacto.glb`` sob demanda, guia as pontas dos tentáculos
empurrando o item para fora da boca do gabinete em arco balístico, aplica
quique elástico no chão com VFX ``impacto_chao`` e recolhe de forma limpa.
"""

from __future__ import annotations

import math

import gltf
from panda3d.core import NodePath, Point3, SamplerState, Vec3

from sejoga.nucleo.recursos import model_dir
from sejoga.render.vfx_coreografias import emitir_evento_estilo


class PropCuspidoCena:
    """Gerencia o ciclo de vida visual do item cuspido no desktop."""

    PERMANENCIA_NO_CHAO_S: float = 4.50

    def __init__(self, renderer) -> None:
        """Prepara referências preguiçosas sem carregar GLB antes do primeiro uso."""
        self._renderer = renderer
        self._node: NodePath | None = None
        self._escala_base: float = 1.0
        self._ativo: bool = False
        self._tempo_pos_cena: float = 0.0
        self._impacto_emitido: bool = False
        self._pos_pousada = Point3(0.0, 0.0, 0.0)

    def _garantir_modelo(self) -> NodePath | None:
        if self._node is not None:
            return self._node
        if self._renderer.model_np is None:
            return None
        caminho = model_dir() / "radio-compacto.glb"
        if not caminho.exists():
            return None
        prop = NodePath(gltf.load_model(str(caminho)))
        for tex in prop.findAllTextures():
            tex.setMagfilter(SamplerState.FTNearest)
            tex.setMinfilter(SamplerState.FTNearest)
        prop.setCollideMask(0)
        prop.reparentTo(self._renderer.model_np)
        bounds = prop.getTightBounds(prop)
        altura = max(1e-4, float(bounds[1].z - bounds[0].z)) if bounds else 1.0
        self._escala_base = (float(self._renderer._model_dimensions.z) * 0.24) / altura
        prop.setScale(self._escala_base)
        prop.hide()
        self._node = prop
        return prop

    def ocultar(self) -> None:
        """Esconde imediatamente o prop."""
        self._ativo = False
        self._tempo_pos_cena = 0.0
        self._impacto_emitido = False
        if self._node is not None and not self._node.isEmpty():
            self._node.hide()

    def atualizar(self, dt: float, controller, *, interromper: bool = False) -> None:
        """Atualiza voo balístico, quique, VFX de impacto e recolhimento."""
        if interromper or controller is None:
            self.ocultar()
            return
        amostra = getattr(controller, "cena_idle_amostra", None)
        em_cuspe = bool(amostra is not None and amostra.ativa and amostra.nome == "cuspir_item")
        if em_cuspe:
            self._atualizar_durante_cena(float(getattr(controller, "_cena_idle_tempo", 0.0)))
            return
        if not self._ativo or self._node is None or self._node.isEmpty():
            return
        st = getattr(controller.state, "value", "idle") if controller.state else "idle"
        if st not in ("idle", "hover"):
            self.ocultar()
            return
        self._tempo_pos_cena += max(0.0, dt)
        restante = self.PERMANENCIA_NO_CHAO_S - self._tempo_pos_cena
        if restante <= 0.0:
            self.ocultar()
        elif restante < 0.32:
            self._node.setScale(self._escala_base * max(0.05, restante / 0.32))

    def _guiar_tentaculos_no_prop(self, pos: Point3, lat: Vec3) -> None:
        pool = getattr(self._renderer, "tentacle_pool", None)
        if pool is None:
            return
        for idx_t, limb in enumerate(pool.tentacles):
            if limb.state.value != "dormant":
                off_l = -0.06 if idx_t % 2 == 0 else 0.06
                limb.target = Point3(pos.x + lat.x * off_l, pos.y + lat.y * off_l, pos.z + 0.06)

    def _aplicar_voo_inicial(
        self, prop: NodePath, boca: Point3, alvo_final: Point3, lat: Vec3, u: float
    ) -> None:
        x = boca.x + (alvo_final.x - boca.x) * u
        y = boca.y + (alvo_final.y - boca.y) * (u**0.82)
        z = boca.z + (alvo_final.z - boca.z) * (u**1.35) + math.sin(u * math.pi) * 0.055
        prop.setPos(x, y, z)
        prop.setHpr(180.0 + u * 25.0, -22.0 * (1.0 - u), math.sin(u * math.pi) * 14.0)
        prop.setScale(self._escala_base * min(1.0, 0.55 + u * 0.75))
        if u < 0.68:
            self._guiar_tentaculos_no_prop(Point3(x, y, z), lat)

    def _aplicar_quique_chao(
        self, prop: NodePath, alvo_final: Point3, z_chao: float, t: float
    ) -> None:
        if not self._impacto_emitido:
            self._impacto_emitido = True
            self._emitir_poeira_quique(alvo_final)
        self._pos_pousada = Point3(alvo_final.x + 0.03, alvo_final.y - 0.03, z_chao)
        if t >= 1.68:
            prop.setPos(self._pos_pousada)
            prop.setHpr(205.0, 0.0, 0.0)
            prop.setScale(self._escala_base)
            return
        u = (t - 1.24) / 0.44
        quique = abs(math.sin(u * math.pi * 1.5)) * 0.048 * (1.0 - u)
        squash = 1.0 - 0.14 * math.exp(-u * 5.0) * abs(math.cos(u * math.pi * 1.5))
        prop.setPos(alvo_final.x + 0.03, alvo_final.y - u * 0.03, z_chao + quique)
        prop.setHpr(205.0, 0.0, math.sin(u * math.pi * 2.0) * 9.0 * (1.0 - u))
        xy_s = self._escala_base / math.sqrt(max(0.7, squash))
        prop.setScale(xy_s, xy_s, self._escala_base * squash)

    def _atualizar_durante_cena(self, t: float) -> None:
        if t < 0.64:
            self._impacto_emitido = False
            if self._node is not None:
                self._node.hide()
            return
        prop = self._garantir_modelo()
        r = self._renderer
        head = r._rig_nodes.get("head") if prop is not None else None
        if prop is None or head is None or head.isEmpty():
            return
        self._ativo = True
        self._tempo_pos_cena = 0.0
        prop.show()
        z_chao = float(r._model_min_z) + 0.015
        boca = r.model_np.getRelativePoint(head, Point3(0.0, 0.14, 0.04))
        frente = r.model_np.getRelativeVector(head, Vec3(0.0, 1.0, 0.0)).normalized()
        lat = r.model_np.getRelativeVector(head, Vec3(1.0, 0.0, 0.0)).normalized()
        alvo_xy = boca + frente * 0.36 + lat * 0.08
        alvo_final = Point3(float(alvo_xy.x), float(alvo_xy.y), z_chao)
        if t < 1.24:
            self._aplicar_voo_inicial(prop, boca, alvo_final, lat, (t - 0.64) / 0.60)
        else:
            self._aplicar_quique_chao(prop, alvo_final, z_chao, t)

    def _emitir_poeira_quique(self, ponto_modelo: Point3) -> None:
        efeitos = getattr(self._renderer, "efeitos_street", None)
        if efeitos is None or not getattr(self._renderer, "_vfx_enabled", True):
            return
        ponto_fx = efeitos.root.getRelativePoint(self._renderer.model_np, ponto_modelo)
        anc = efeitos._ancoras_atuais() if hasattr(efeitos, "_ancoras_atuais") else {"pes": Vec3(ponto_fx)}
        anc = dict(anc)
        anc["pes"] = Vec3(ponto_fx)
        anc["sola_esq"] = Vec3(ponto_fx) + Vec3(-0.08, 0.0, 0.0)
        anc["sola_dir"] = Vec3(ponto_fx) + Vec3(0.08, 0.0, 0.0)
        paleta = str(getattr(efeitos, "_paleta", "auto") or "auto")
        emitir_evento_estilo(
            efeitos, paleta, "impacto_chao", anc, pos=Vec3(ponto_fx), forca=0.92
        )

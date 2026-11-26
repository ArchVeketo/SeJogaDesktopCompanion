"""Orquestrador multi-estilo de VFX 3D e cinéticos ancorados ao rig do Mário."""

from __future__ import annotations

import logging
import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from panda3d.core import (
    AlphaTestAttrib,
    AntialiasAttrib,
    CardMaker,
    NodePath,
    Texture,
    TransparencyAttrib,
    Vec3,
)

from sejoga.render import vfx_geometria_3d as geo
from sejoga.render.chroma_tuning import CHROMA_HEX_PADRAO, derivar_chroma
from sejoga.render.estilos_vfx import PERFIS_MOVIMENTO_VFX, construir_banco_estilo_vfx
from sejoga.render.sprites_efeitos import shader_sprite_bayer
from sejoga.render.vfx_coreografias import emitir_evento_estilo
from sejoga.render.vfx_filtros import shader_grafismo

logger = logging.getLogger(__name__)

_FX_FRONT_Y = -2.25
_FX_CHAO_Y = 0.0
_FX_BACK_Y = 1.95
_MAX_INSTANCIAS = 72

_PALETAS_VFX_VALIDAS = (
    "auto",
    "pb_escuro",
    "pb_claro",
    "colorido",
    "hifi_rush",
    "spider_verse",
    "anime_sakuga",
    "lowpoly_3d",
)

_ZERO_VEC3 = Vec3(0.0, 0.0, 0.0)


@dataclass
class _InstanciaVFX:
    nome: str
    node: NodePath
    frames: tuple[Texture, ...]
    pos: Vec3
    vel: Vec3
    age: float
    ttl: float
    scale_x: float
    scale_z: float
    rot_base: float
    rot_vel: float
    drag: float
    gravity: float
    anchor_key: str | None = None
    anchor_offset: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, 0.0))
    plane_y: float = _FX_FRONT_Y
    frame_atual: int = -1
    seed: float = 0.0
    spawned_flecks: bool = False
    allow_flecks: bool = True
    single_frame_idx: int | None = None
    eh_malha_3d: bool = False
    rot3d_vel: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, 0.0))
    modo_mov: str = "padrao"
    fps_step: float = 0.0
    orbita_r: tuple[float, float, float] = (0.0, 0.0, 0.0)
    orbita_vel: float = 0.0
    exp_final: float = 1.0
    tilt_p: float = 0.0
    heading_h: float = 0.0
    tipo_mesh: str = ""
    referencial_fixo: NodePath | None = None
    atualizar_fase: Callable[[float], None] | None = None

    def remover(self):
        """Solta a malha e seu espaço de emissão, inclusive ao trocar de filtro."""
        self.node.removeNode()
        if self.referencial_fixo is not None:
            self.referencial_fixo.removeNode()


def construir_malha_vfx_3d(
    nome: str,
    colorkey_hex: str = CHROMA_HEX_PADRAO,
) -> NodePath:
    """Constrói malha procedural 3D estilizada para um nome semântico de VFX."""
    mapa = {
        "musica": ("nota_3d", (0.38, 0.94, 0.24), (1.00, 0.82, 0.14)),
        "choque": ("raio_3d", (0.18, 0.88, 1.00), (1.00, 0.82, 0.14)),
        "carinho": ("coracao_3d", (1.00, 0.30, 0.52), (1.00, 0.82, 0.24)),
        "susto": ("exclamacao_3d", (1.00, 0.84, 0.14), (1.00, 0.42, 0.10)),
        "sono": ("z_bloco_3d", (0.46, 0.64, 1.00), (0.24, 0.84, 0.98)),
    }
    if nome in mapa:
        tipo, ca, cb = mapa[nome]
        return geo.construir_objeto_tematico_3d(tipo, ca, cb, colorkey_hex=colorkey_hex)
    if nome == "queda_chao":
        return geo.construir_cubo_cel_3d((0.82, 0.88, 0.96), (0.28, 0.74, 0.96), colorkey_hex=colorkey_hex)
    return geo.construir_objeto_tematico_3d("cristal_3d", (1.00, 0.78, 0.16), (0.18, 0.86, 1.00), colorkey_hex=colorkey_hex)


class _AncorasLazy:
    """Proxy de dicionário que só consulta os nós do Panda3D quando algum VFX dispara."""

    def __init__(self, resolver) -> None:
        self._resolver = resolver
        self._cache: dict[str, Vec3] | None = None

    def _garantir(self) -> dict[str, Vec3]:
        if self._cache is None:
            self._cache = self._resolver()
        return self._cache

    def __getitem__(self, chave: str) -> Vec3:
        return self._garantir()[chave]

    def __contains__(self, chave: object) -> bool:
        return chave in self._garantir()

    def get(self, chave: str, padrao: Vec3 | None = None) -> Vec3 | None:
        return self._garantir().get(chave, padrao)


class GerenciadorEfeitosStreet:
    """Orquestra os efeitos do filtro e as ilustrações opcionais no rig do Mário."""

    def __init__(
        self,
        parent_node: NodePath,
        *,
        head_node: NodePath | None = None,
        model_node: NodePath | None = None,
        paleta: str = "auto",
        escala_global: float = 1.0,
        habilitado: bool = True,
        colorkey_hex: str = CHROMA_HEX_PADRAO,
    ) -> None:
        """Inicializa o gerenciador multi-estilo de VFX."""
        self.root = parent_node.attachNewNode("efeitos-street-v2")
        self.root.setAntialias(AntialiasAttrib.MNone, 1)
        self.head_node = head_node
        self.model_node = model_node
        self._pes = tuple(model_node.find(f"**/{nome}") for nome in ("left-feet", "right-feet")) if model_node else ()
        self._antena_dir_node = self._buscar_antena(head_node, "antena-direita")
        self._antena_esq_node = self._buscar_antena(head_node, "antena-esquerda")
        self._enabled = bool(habilitado)
        self._paleta = paleta if paleta in _PALETAS_VFX_VALIDAS else "pb_escuro"
        self._escala_global = max(0.5, min(1.6, float(escala_global)))
        self._colorkey_hex = colorkey_hex
        self._rng = random.Random()
        molde = CardMaker("grafismo")
        molde.setFrame(-0.28, 1.72, -1.0, 1.0)
        self._molde = NodePath(molde.generate())
        self._filtro = "padrao"
        self._chave = Vec3(*derivar_chroma(colorkey_hex).rgb)
        self._tempo = 0.0
        self._instancias: list[_InstanciaVFX] = []
        self._banco_cache: dict[str, dict[str, tuple[Texture, ...]]] = {}
        self._resetar_estados()

    def _resetar_estados(self) -> None:
        self._cd_musica = 0.0
        self._cd_choque = 0.0
        self._cd_raiva = 0.0
        self._cd_carinho = 0.0
        self._cd_susto = 0.0
        self._cd_tontura = 0.0
        self._cd_sono = 0.0
        self._cd_linhas_queda = 0.0
        self._cd_comemorando = 0.0
        self._cd_assinatura = 0.0
        self._cd_passos = 0.0
        self._cd_rastro_arraste = 0.0
        self._cd_humor_vfx = 0.0
        self._xray_flash_restante = 0.0
        self._xray_flash_duracao = 0.11
        self._prev_susto = False
        self._prev_raiva = False
        self._prev_choque = False
        self._prev_acento = False
        self._prev_comemorando = False
        self._lado_alternado = 1
        self._cena_vfx_nome = ""
        self._cena_vfx_disparados: set[int] = set()

    @staticmethod
    def _buscar_antena(head_node: NodePath | None, nome: str) -> NodePath | None:
        if head_node is None or head_node.isEmpty():
            return None
        ant = head_node.find(f"**/{nome}")
        if ant.isEmpty():
            return None
        esf = ant.find("**/sphere")
        return esf if not esf.isEmpty() else ant

    def _quadros_ilustracao(self, nome):
        banco = self._banco_cache.setdefault(self._paleta, {})
        if nome not in banco:
            try:
                banco.update(construir_banco_estilo_vfx(
                    self._paleta, nomes=(nome,), colorkey_hex=self._colorkey_hex
                ))
            except Exception as exc:
                logger.warning("Falha ao construir ilustração %s/%s: %s", self._paleta, nome, exc)
                banco[nome] = ()
        return banco.get(nome, ())

    def configurar(
        self,
        *,
        habilitado: bool | None = None,
        paleta: str | None = None,
        filtro: str | None = None,
        escala_global: float | None = None,
        colorkey_hex: str | None = None,
    ) -> None:
        """Atualiza estado/preset/escala ao vivo, reiniciando instâncias ao trocar estilo."""
        if colorkey_hex is not None and colorkey_hex != self._colorkey_hex:
            self._colorkey_hex = colorkey_hex
            self._chave = Vec3(*derivar_chroma(colorkey_hex).rgb)
            self.limpar()
            self._banco_cache.clear()
        if filtro is not None and filtro != self._filtro:
            self._filtro = filtro
            self.limpar()
            self._resetar_estados()
        if habilitado is not None:
            self._enabled = bool(habilitado)
            if not self._enabled:
                self.limpar()
        if escala_global is not None:
            self._escala_global = max(0.5, min(1.6, float(escala_global)))
        if paleta is not None and paleta in _PALETAS_VFX_VALIDAS and paleta != self._paleta:
            self._paleta = paleta
            self.limpar()

    def limpar(self) -> None:
        """Remove todos os efeitos ativos imediatamente."""
        for inst in self._instancias:
            inst.remover()
        self._instancias.clear()

    def _descartar_excedentes(self) -> None:
        while len(self._instancias) >= _MAX_INSTANCIAS:
            antigo = self._instancias.pop(0)
            antigo.remover()

    def emitir_grafismo(self, nome, codigo, pos, lado, angulo, escala, vida):
        """Instancia o desenho do filtro. O shader anima a partir da origem do cartão."""
        if not self._enabled:
            return
        self._descartar_excedentes()
        node = self._molde.copyTo(self.root)
        node.setName(nome)
        node.setTwoSided(True)
        node.setCollideMask(0)
        node.setDepthWrite(False)
        node.setBin("fixed", 43)
        node.setShader(shader_grafismo(self._filtro), 2)
        node.setShaderInput("fase", 0.)
        node.setShaderInput("evento", codigo)
        node.setShaderInput("chave", self._chave)
        node.setPos(pos)
        tamanho = escala * self._escala_global
        node.setScale(lado * tamanho, 1.0, tamanho)
        node.setR(-lado * angulo)
        self._instancias.append(_InstanciaVFX(
            nome=nome, node=node, frames=(), pos=Vec3(pos), vel=Vec3(0),
            age=0.0, ttl=vida, scale_x=tamanho, scale_z=tamanho, rot_base=0.0,
            rot_vel=0.0, drag=0.0, gravity=0.0, tipo_mesh=f"{self._filtro}_{nome}",
            modo_mov="grafismo",
        ))

    def emitir_3d(
        self,
        node: NodePath,
        pos: Vec3,
        *,
        tipo_mesh: str = "",
        vel: Vec3 = _ZERO_VEC3,
        ttl: float = 0.85,
        scale_x: float = 0.85,
        scale_z: float | None = None,
        rot_base: float = 0.0,
        rot_vel: float = 0.0,
        drag: float = 1.6,
        gravity: float = 0.0,
        anchor_key: str | None = None,
        anchor_offset: Vec3 = _ZERO_VEC3,
        plane_y: float | None = None,
        rot3d_vel: Vec3 = _ZERO_VEC3,
        modo_mov: str = "padrao",
        fps_step: float = 0.0,
        orbita_r: tuple[float, float, float] = (0.0, 0.0, 0.0),
        orbita_vel: float = 0.0,
        exp_final: float = 1.0,
        tilt_p: float = 0.0,
        heading_h: float = 0.0,
        seed: float | None = None,
        atualizar_fase: Callable[[float], None] | None = None,
    ) -> None:
        """Registra um nó 3D procedural na fila ativa com seu modo de movimento."""
        if not self._enabled:
            if not node.isEmpty():
                node.removeNode()
            return
        self._descartar_excedentes()
        py = float(pos.y) if plane_y is None else float(plane_y)
        fixo = None
        if anchor_key is None:
            fixo = self.root.attachNewNode("espaco-do-impacto")
            fixo.wrtReparentTo(self.root.getTop())
        node.reparentTo(fixo if fixo is not None else self.root)
        node.setTwoSided(node.getTwoSided())
        node.setLightOff(1)
        node.setShaderOff(1)
        node.setDepthTest(True)
        node.setDepthWrite(True)
        node.setTransparency(TransparencyAttrib.MNone)
        node.setCollideMask(0)
        node.setBin("fixed", 41 if (py >= -0.05 or modo_mov in ("onda_expansao", "pilar_pulso")) else 43)

        sx = scale_x * self._escala_global
        sz = (scale_x if scale_z is None else scale_z) * self._escala_global
        p = Vec3(pos.x, py, pos.z)
        node.setPos(p)
        node.setHpr(heading_h, tilt_p, rot_base)
        node.setScale(sx, sx, sz)
        self._instancias.append(
            _InstanciaVFX(
                nome=tipo_mesh or "vfx_3d",
                node=node,
                frames=(),
                pos=p,
                vel=Vec3(vel),
                age=0.0,
                ttl=max(0.22, ttl),
                scale_x=sx,
                scale_z=sz,
                rot_base=rot_base,
                rot_vel=rot_vel,
                drag=drag,
                gravity=gravity,
                anchor_key=anchor_key,
                anchor_offset=Vec3(anchor_offset),
                plane_y=py,
                frame_atual=-1,
                seed=float(seed if seed is not None else self._rng.uniform(0.0, 100.0)),
                allow_flecks=False,
                referencial_fixo=fixo,
                eh_malha_3d=True,
                rot3d_vel=Vec3(rot3d_vel),
                modo_mov=modo_mov,
                fps_step=fps_step,
                orbita_r=orbita_r,
                orbita_vel=orbita_vel,
                exp_final=exp_final,
                tilt_p=tilt_p,
                heading_h=heading_h,
                tipo_mesh=tipo_mesh,
                atualizar_fase=atualizar_fase,
            )
        )

    def _criar_no_cartao(self, nome: str, tex: Texture) -> NodePath:
        cm = CardMaker(f"vfx-street-{nome}")
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)
        node = self.root.attachNewNode(cm.generate())
        node.setTexture(tex, 1)
        node.setTwoSided(True)
        node.setLightOff(1)
        node.setTransparency(TransparencyAttrib.MNone)
        node.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreater, 0.5))
        node.setShader(shader_sprite_bayer(), 2)
        node.setShaderInput("u_fade", 1.0)
        node.setDepthTest(True)
        node.setDepthWrite(False)
        node.setCollideMask(0)
        node.setBin("fixed", 42)
        return node

    def emitir_cartao(
        self,
        nome: str,
        pos: Vec3,
        *,
        vel: Vec3 = _ZERO_VEC3,
        ttl: float = 0.85,
        scale_x: float = 1.0,
        scale_z: float | None = None,
        rot_base: float = 0.0,
        rot_vel: float = 0.0,
        drag: float = 1.6,
        gravity: float = 0.0,
        anchor_key: str | None = None,
        anchor_offset: Vec3 = _ZERO_VEC3,
        plane_y: float = _FX_FRONT_Y,
        allow_flecks: bool = False,
        single_frame_idx: int | None = None,
    ) -> None:
        """Emite cartão tipográfico híbrido (Spider-Verse HQ) usando a folha 2x2."""
        del allow_flecks
        if not self._enabled:
            return
        if not (frames := self._quadros_ilustracao(nome)):
            return
        self._descartar_excedentes()
        node = self._criar_no_cartao(nome, frames[single_frame_idx or 0])
        sx = scale_x * self._escala_global
        sz = (scale_x if scale_z is None else scale_z) * self._escala_global
        p = Vec3(pos.x, plane_y, pos.z)
        node.setPos(p)
        node.setR(rot_base)
        node.setScale(sx * 0.65, 1.0, sz * 0.65)
        self._instancias.append(
            _InstanciaVFX(
                nome=nome,
                node=node,
                frames=frames,
                pos=p,
                vel=Vec3(vel),
                age=0.0,
                ttl=max(0.25, ttl),
                scale_x=sx,
                scale_z=sz,
                rot_base=rot_base,
                rot_vel=rot_vel,
                drag=drag,
                gravity=gravity,
                anchor_key=anchor_key,
                anchor_offset=Vec3(anchor_offset),
                plane_y=plane_y,
                frame_atual=single_frame_idx or 0,
                seed=self._rng.uniform(0.0, 100.0),
                allow_flecks=False,
                single_frame_idx=single_frame_idx,
                eh_malha_3d=False,
                tipo_mesh=f"{self._paleta}_card_{nome}",
            )
        )

    def _ancora_ponto(
        self,
        node: NodePath | None,
        local: tuple[float, float, float],
        fallback: tuple[float, float, float],
        plane_y: float = _FX_FRONT_Y,
    ) -> Vec3:
        if node is not None and not node.isEmpty():
            p = self.root.getRelativePoint(node, Vec3(*local))
            return Vec3(p) if self._filtro in ("padrao", "blockbench") else Vec3(p.x, plane_y, p.z)
        return Vec3(fallback[0], plane_y, fallback[2])

    def _ancora_centro(
        self,
        node: NodePath | None,
        fallback: tuple[float, float, float],
        plane_y: float = _FX_FRONT_Y,
    ) -> Vec3:
        if node is not None and not node.isEmpty():
            bounds = node.getTightBounds(self.root)
            if bounds:
                c = (bounds[0] + bounds[1]) * 0.5
                return Vec3(c) if self._filtro in ("padrao", "blockbench") else Vec3(c.x, plane_y, c.z)
            p = self.root.getRelativePoint(node, Vec3(0.0, 0.0, 0.0))
            return Vec3(p) if self._filtro in ("padrao", "blockbench") else Vec3(p.x, plane_y, p.z)
        return Vec3(fallback[0], plane_y, fallback[2])

    def _calcular_ancoras(self) -> dict[str, Vec3]:
        """Calcula pontos anatômicos exatos no espaço do modelo atual."""
        return {
            "cabeca_topo": self._ancora_ponto(self.head_node, (0.0, 0.14, 0.44), (0.0, _FX_FRONT_Y, 4.75)),
            "cabeca_centro": self._ancora_ponto(self.head_node, (0.0, 0.0, 0.22), (0.0, 0.0, 3.65), plane_y=0.0),
            "templo": self._ancora_ponto(self.head_node, (-0.12, 0.18, 0.24), (0.68, _FX_FRONT_Y, 3.85)),
            "fone_dir": self._ancora_ponto(self.head_node, (0.32, 0.10, 0.16), (-1.75, _FX_FRONT_Y, 3.45)),
            "fone_esq": self._ancora_ponto(self.head_node, (-0.32, 0.10, 0.16), (1.75, _FX_FRONT_Y, 3.45)),
            "visor_lado": self._ancora_ponto(self.head_node, (-0.26, 0.16, 0.14), (1.42, _FX_FRONT_Y, 3.35)),
            "antenas_meio": self._ancora_ponto(self.head_node, (0.0, 0.10, 0.48), (0.0, _FX_FRONT_Y, 4.95)),
            "antena_d": self._ancora_centro(self._antena_dir_node, (-1.85, _FX_FRONT_Y, 4.85)),
            "antena_e": self._ancora_centro(self._antena_esq_node, (1.85, _FX_FRONT_Y, 4.85)),
            "pes": self._ancora_ponto(self.model_node, (0.0, 0.0, 0.02), (0.0, _FX_CHAO_Y, -1.48), plane_y=_FX_CHAO_Y),
            "tronco": self._ancora_ponto(self.model_node, (0.0, 0.0, 0.50), (0.0, _FX_FRONT_Y, 1.35)),
            "porta": self._ancora_ponto(self.model_node, (0.0, 0.24, 0.42), (0.0, _FX_FRONT_Y, 1.35)),
            "lado_esq": self._ancora_ponto(self.model_node, (-0.56, 0.0, 0.52), (-2.85, _FX_FRONT_Y, 1.65)),
            "lado_dir": self._ancora_ponto(self.model_node, (0.56, 0.0, 0.52), (2.85, _FX_FRONT_Y, 1.65)),
        }

    def solicitar_flash_xray(self, duracao: float = 0.11) -> None:
        """Agenda um flash rápido de Raio-X (esqueleto FNF) nos impactos fortes."""
        dur = max(0.04, min(0.24, float(duracao)))
        self._xray_flash_duracao = dur
        self._xray_flash_restante = max(self._xray_flash_restante, dur)

    def xray_flash_intensidade(self) -> float:
        """Retorna intensidade ``[0..1]`` do flash Raio-X ativo no frame atual."""
        if self._xray_flash_restante <= 0.0 or self._xray_flash_duracao <= 0.0:
            return 0.0
        return max(0.0, min(1.0, self._xray_flash_restante / self._xray_flash_duracao))

    def disparar_pouso_entrada(self) -> None:
        """Poeira dos dois apoios na queda heroica."""
        self.disparar_impacto_chao(1.25)

    def disparar_impacto_chao(self, forca: float = 1.0) -> None:
        """Dispara coreografia de impacto no chão para o preset ativo."""
        if not self._enabled:
            return
        anc = self._calcular_ancoras()
        solas = []
        for pe in self._pes:
            bounds = pe.getTightBounds(self.root) if not pe.isEmpty() else None
            if bounds:
                baixo, alto = bounds
                solas.append((baixo, alto))
        if len(solas) == 2:
            esq, direita = sorted(solas, key=lambda par: par[0].x + par[1].x)
            anc["sola_esq"] = Vec3(esq[0].x, esq[0].y, esq[0].z)
            anc["sola_dir"] = Vec3(direita[1].x, direita[0].y, direita[0].z)
        emitir_evento_estilo(
            self,
            self._paleta,
            "impacto_chao",
            anc,
            pos=anc["pes"],
            forca=max(0.75, min(1.6, float(forca))),
        )

    def disparar_impacto_parede(
        self,
        kind: str,
        velocity: tuple[float, float],
        forca: float = 1.0,
    ) -> None:
        """Dispara impacto direcional no ponto real de batida (chão, teto ou laterais)."""
        if not self._enabled:
            return
        anc = self._calcular_ancoras()
        vx, vy = float(velocity[0]), float(velocity[1])
        f = max(0.75, min(1.5, float(forca)))
        kind_l = str(kind).lower()
        if "floor" in kind_l or "shelf" in kind_l or (
            "wall" not in kind_l and "ceil" not in kind_l and "top" not in kind_l and vy > 0.0 and abs(vy) >= abs(vx) * 1.15
        ):
            self.disparar_impacto_chao(f)
            return
        if "ceil" in kind_l or "top" in kind_l or (abs(vy) > abs(vx) * 1.4 and vy < 0.0):
            pos = Vec3(anc["cabeca_topo"].x, anc["cabeca_topo"].y, anc["cabeca_topo"].z + 0.15)
        elif "left" in kind_l or (kind_l == "impact" and vx < -25.0):
            pos = Vec3(anc["lado_esq"].x - 0.15, anc["lado_esq"].y, anc["lado_esq"].z)
        elif "right" in kind_l or (kind_l == "impact" and vx > 25.0):
            pos = Vec3(anc["lado_dir"].x + 0.15, anc["lado_dir"].y, anc["lado_dir"].z)
        else:
            self.disparar_impacto_chao(f)
            return
        emitir_evento_estilo(self, self._paleta, "impacto_parede", anc, pos=pos, forca=f, vel=Vec3(-vx * 0.002, 0, vy * 0.002))

    def disparar_carinho(self) -> None:
        """Emite carinho no topo da cabeça para o estilo ativo."""
        if not self._enabled or self._cd_carinho > 0.0:
            return
        self._cd_carinho = 0.90
        anc = self._calcular_ancoras()
        emitir_evento_estilo(self, self._paleta, "carinho", anc, pos=anc["cabeca_topo"])

    def atualizar(self, dt: float, params: dict[str, Any]) -> None:
        """Atualiza cooldowns, emite eventos de estado e avança todas as instâncias."""
        dt = max(0.0, min(0.05, float(dt)))
        self._tempo += dt
        if not self._enabled:
            if self._instancias:
                self.limpar()
            return
        for attr in (
            "_cd_musica", "_cd_choque", "_cd_raiva", "_cd_carinho", "_cd_susto",
            "_cd_tontura", "_cd_sono", "_cd_linhas_queda", "_cd_comemorando",
            "_cd_assinatura", "_cd_passos", "_cd_rastro_arraste", "_cd_humor_vfx",
        ):
            setattr(self, attr, max(0.0, getattr(self, attr) - dt))
        self._xray_flash_restante = max(0.0, self._xray_flash_restante - dt)
        anc: Any = (
            self._calcular_ancoras()
            if any(inst.anchor_key for inst in self._instancias)
            else _AncorasLazy(self._calcular_ancoras)
        )
        self._emitir_choque_ou_musica(anc, params)
        self._gatilhos_cabeca_emocoes(anc, params)
        self._gatilhos_cenas_narrativas(anc, params)
        self._gatilhos_ritmo_e_movimento(anc, params)
        self._gatilhos_deslocamento_e_queda(anc, params)
        if self._instancias:
            self._atualizar_instancias(dt, anc)

    def _emitir_choque_ou_musica(self, anc: dict[str, Vec3], params: dict[str, Any]) -> None:
        estouro_f = bool(params.get("estouro_fone"))
        aviso_ant = float(params.get("aviso_antena", 0.0) or 0.0)
        choque_on = bool(params.get("choque_argolas") or estouro_f or aviso_ant > 0.04)
        if choque_on and (not self._prev_choque or self._cd_choque <= 0.0) and self._cd_choque <= 0.0:
            self._cd_choque = 0.36
            emitir_evento_estilo(self, self._paleta, "choque", anc, pos=anc["antena_d"])
        self._prev_choque = choque_on

    def _gatilhos_humor_micro_vfx(self, anc: dict[str, Vec3], params: dict[str, Any], susto: bool, raiva: bool) -> None:
        if susto and not self._prev_susto and self._cd_humor_vfx <= 0.0:
            self._cd_humor_vfx = 2.2
            emitir_evento_estilo(self, self._paleta, "suor", anc, pos=anc.get("templo"), forca=0.92)
        if self._cd_humor_vfx > 0.0 or susto or raiva:
            return
        humor = str(params.get("humor", "") or "").upper()
        if humor in ("TEDIOSO", "DESCONFIADO"):
            self._cd_humor_vfx = 5.2
            emitir_evento_estilo(self, self._paleta, "tristeza", anc, pos=anc["cabeca_topo"], forca=0.92)
        elif humor == "CANSADO" and not params.get("sono"):
            self._cd_humor_vfx = 4.6
            emitir_evento_estilo(self, self._paleta, "suspiro", anc, pos=anc["visor_lado"], forca=0.90)

    def _gatilhos_cabeca_emocoes(self, anc: dict[str, Vec3], params: dict[str, Any]) -> None:
        susto = bool(params.get("susto"))
        raiva = bool(params.get("raiva"))
        if susto and not self._prev_susto and self._cd_susto == 0:
            emitir_evento_estilo(self, self._paleta, "sobressalto", anc)
            self._cd_susto = 0.55
        if raiva and not self._prev_raiva and self._cd_raiva == 0:
            emitir_evento_estilo(self, self._paleta, "irritado", anc)
            self._cd_raiva = 0.75
        self._gatilhos_humor_micro_vfx(anc, params, susto, raiva)
        self._prev_susto = susto
        self._prev_raiva = raiva
        if params.get("tontura") and self._cd_tontura <= 0.0:
            self._cd_tontura = 1.15
            emitir_evento_estilo(self, self._paleta, "tontura", anc, pos=anc["cabeca_topo"])
        if params.get("sono") and self._cd_sono <= 0.0:
            self._cd_sono = 1.65
            emitir_evento_estilo(self, self._paleta, "sono", anc, pos=anc["visor_lado"])
        if params.get("carinho"):
            self.disparar_carinho()
        comem = bool(params.get("comemorando"))
        if comem and not self._prev_comemorando and self._cd_comemorando <= 0.0:
            self._cd_comemorando = 1.10
            emitir_evento_estilo(self, self._paleta, "brilho_estilo", anc, pos=anc["cabeca_topo"], forca=1.10)
        self._prev_comemorando = comem

    # (tempo_s, evento_vfx, ancora, dir_x, forca) — dispara uma vez por cue em cada execução da cena
    _GATILHOS_CENAS_VFX: ClassVar[dict[str, tuple[tuple[float, str, str, float, float], ...]]] = {
        "finger_guns_camera": (
            (0.90, "brilho_estilo", "cabeca_topo", 1.0, 1.00),
            (2.05, "brilho_estilo", "cabeca_topo", 1.0, 1.12),
        ),
        "conferir_luva": ((1.15, "brilho_estilo", "cabeca_topo", 1.0, 0.92),),
        "bater_pe_impaciente": ((1.75, "irritado", "cabeca_topo", 1.0, 0.92),),
        "bater_pe_ritmo": (
            (1.15, "musica", "fone_esq", 1.0, 0.86),
            (3.15, "musica", "fone_dir", -1.0, 0.86),
        ),
        "solo_guitarra_ar": (
            (1.05, "musica", "fone_esq", 1.0, 1.05),
            (2.60, "musica", "fone_dir", -1.0, 1.10),
            (4.15, "brilho_estilo", "cabeca_topo", 1.0, 1.15),
        ),
        "escutar_fone": (
            (1.30, "musica", "fone_esq", 1.0, 0.82),
            (3.60, "musica", "fone_dir", -1.0, 0.82),
        ),
        "checar_walkman": (
            (1.55, "sinal_radio", "antena_d", 1.0, 0.92),
            (3.25, "musica", "fone_esq", 1.0, 0.88),
        ),
        "groove_um_pe": (
            (1.45, "musica", "fone_esq", 1.0, 0.90),
            (3.45, "musica", "fone_dir", -1.0, 0.90),
        ),
        "pensar_gabinete": ((1.10, "curiosidade", "visor_lado", 1.0, 0.95),),
        "olhar_curioso_chao": ((0.85, "curiosidade", "visor_lado", 1.0, 0.95),),
        "tentaculo_fujao": (
            (0.90, "curiosidade", "visor_lado", 1.0, 0.95),
            (2.35, "sobressalto", "cabeca_topo", 1.0, 1.00),
        ),
        "cacar_cursor_sucesso": (
            (0.65, "curiosidade", "visor_lado", 1.0, 0.95),
            (3.65, "brilho_estilo", "cabeca_topo", 1.0, 1.15),
        ),
        "cacar_cursor_falha": (
            (0.65, "curiosidade", "visor_lado", 1.0, 0.95),
            (2.85, "irritado", "cabeca_topo", 1.0, 0.98),
        ),
        "roubo_cursor_tentaculo": (
            (0.55, "curiosidade", "visor_lado", 1.0, 0.95),
            (3.45, "brilho_estilo", "cabeca_topo", 1.0, 1.08),
        ),
        "cuspir_item": ((0.60, "sobressalto", "cabeca_topo", 1.0, 0.96),),
        "argolas_antena": ((0.55, "sinal_radio", "antena_d", 1.0, 1.00),),
        "espreguicar": ((1.85, "suspiro", "visor_lado", 1.0, 0.92),),
        "respiracao_profunda": ((1.65, "suspiro", "visor_lado", 1.0, 0.90),),
        "bocejar_longo": (
            (0.75, "sono", "visor_lado", 1.0, 0.95),
            (2.45, "suspiro", "visor_lado", 1.0, 0.86),
        ),
        "ajustar_fones": (
            (0.85, "estalo_fone", "fone_dir", 1.0, 0.92),
            (1.65, "estalo_fone", "fone_esq", -1.0, 0.92),
        ),
        "cochilo_em_pe": ((1.45, "sono", "visor_lado", 1.0, 0.90),),
        "balanco_relaxado": ((1.20, "musica", "fone_esq", 1.0, 0.80),),
        "arrumar_antena": ((0.95, "sinal_radio", "antena_d", 1.0, 0.90),),
        "olhar_pes": ((1.10, "curiosidade", "visor_lado", 1.0, 0.85),),
        "espirro": (
            (1.15, "espirro", "porta", 1.0, 1.06),
            (2.05, "suspiro", "visor_lado", 1.0, 0.86),
        ),
        "polir_gabinete": ((1.35, "brilho_estilo", "cabeca_topo", 1.0, 0.90),),
        "suspiro_pesado": (
            (1.05, "suspiro", "visor_lado", 1.0, 0.95),
            (1.60, "tristeza", "cabeca_topo", 1.0, 0.90),
        ),
    }

    @staticmethod
    def _cues_cena(nome: str) -> tuple[tuple[float, str, str, float, float], ...] | None:
        try:
            from sejoga.animacao.diretor_cenas import eventos_vfx_cena

            cues = eventos_vfx_cena(nome)
            if cues:
                return cues
        except ImportError:
            pass
        return GerenciadorEfeitosStreet._GATILHOS_CENAS_VFX.get(nome)

    def _gatilhos_cenas_narrativas(self, anc: dict[str, Vec3], params: dict[str, Any]) -> None:
        nome = str(params.get("cena_nome", "") or "")
        if not nome:
            self._cena_vfx_nome = ""
            self._cena_vfx_disparados.clear()
            return
        if nome != self._cena_vfx_nome:
            self._cena_vfx_nome = nome
            self._cena_vfx_disparados.clear()
        cues = self._cues_cena(nome)
        if not cues:
            return
        tempo = float(params.get("cena_tempo", 0.0) or 0.0)
        for idx, (t_cue, evento, ancora, dir_x, forca) in enumerate(cues):
            if idx not in self._cena_vfx_disparados and tempo >= t_cue:
                self._cena_vfx_disparados.add(idx)
                pos = anc.get(ancora)
                emitir_evento_estilo(self, self._paleta, evento, anc, pos=pos, dir_x=dir_x, forca=forca)

    def _gatilhos_ritmo_e_movimento(self, anc: dict[str, Vec3], params: dict[str, Any]) -> None:
        caixas = params.get("caixas_som_pos", ())
        acento = bool(caixas and params.get("acento_danca"))
        if acento and not self._prev_acento and self._cd_assinatura <= 0.0:
            self._cd_assinatura = 0.16
            self._lado_alternado *= -1
            ponto = caixas[0] if self._lado_alternado < 0 else caixas[-1]
            emitir_evento_estilo(self, self._paleta, "acento_danca", anc,
                                 pos=ponto, dir_x=float(self._lado_alternado),
                                 forca=1.65 if len(caixas) > 1 else 0.9)
        self._prev_acento = acento

    def _gatilhos_deslocamento_e_queda(self, anc: dict[str, Vec3], params: dict[str, Any]) -> None:
        grounded = bool(params.get("grounded", True))
        vx, vy = params.get("velocidade", (0.0, 0.0))
        vx_f, vy_f = float(vx), float(vy)
        vel_mag = math.hypot(vx_f, vy_f)
        if grounded and not params.get("dragging", False) and abs(vx_f) > 190.0 and self._cd_passos <= 0.0:
            self._cd_passos = 0.24
            emitir_evento_estilo(
                self,
                self._paleta,
                "poeira_passo",
                anc,
                pos=anc["pes"],
                dir_x=1.0 if vx_f >= 0.0 else -1.0,
                forca=min(1.2, abs(vx_f) / 320.0),
            )
        if params.get("dragging") and vel_mag > 420.0 and self._cd_rastro_arraste <= 0.0:
            self._cd_rastro_arraste = 0.18
            emitir_evento_estilo(
                self,
                self._paleta,
                "rastro",
                anc,
                pos=anc["tronco"],
                vel=Vec3(-vx_f * 0.002, 0.0, vy_f * 0.002),
            )
        if not grounded and not params.get("dragging", False) and vel_mag > 540.0 and self._cd_linhas_queda <= 0.0:
            self._cd_linhas_queda = 0.32
            emitir_evento_estilo(
                self,
                self._paleta,
                "rastro",
                anc,
                pos=anc["tronco"] + Vec3(self._rng.uniform(-0.8, 0.8), 0.0, 0.3),
                vel=Vec3(-vx_f * 0.002, 0.0, vy_f * 0.003),
            )

    @staticmethod
    def _escala_crescimento(inst: _InstanciaVFX, frac: float) -> tuple[float, float, float]:
        modo = inst.modo_mov
        if modo == "pincelada":
            ataque, cauda = min(1., frac / .23), min(1., (1. - frac) / .42)
            return inst.scale_x * (.26 + 1.05 * ataque) * cauda, inst.scale_x * cauda, inst.scale_z * (1.34 - .46 * ataque) * cauda
        if modo == "fumaca_voxel":
            raio = (.32 + .92 * math.sin(math.pi * frac) ** .72) * min(1., (1. - frac) / .21)
            return inst.scale_x * raio, inst.scale_x * raio, inst.scale_z * raio * (.62 + frac)
        if modo == "pilar_pulso":
            alt_m = math.sin(min(1.0, frac * 1.15) * math.pi * 0.82) * 1.15
            sx_m = 1.0 if frac < 0.75 else max(0.05, (1.0 - frac) / 0.25)
            return inst.scale_x * sx_m, inst.scale_x * sx_m, inst.scale_z * max(0.08, alt_m)
        env = 0.45 + 0.65 * math.sin((frac / 0.20) * math.pi * 0.55) if frac < 0.20 else (
            max(0.04, (1.0 - frac) / 0.22) if frac > 0.78 else 1.0
        )
        return inst.scale_x * env, inst.scale_x * env, inst.scale_z * env

    @staticmethod
    def _escala_por_modo(inst: _InstanciaVFX, frac: float) -> tuple[float, float, float]:
        modo = inst.modo_mov
        if modo in ("onda_expansao", "varredura_arco"):
            corte = 0.72 if modo == "onda_expansao" else 0.38
            ini = 0.38 if modo == "onda_expansao" else 0.52
            escala = ini + (inst.exp_final - ini) * (1.0 - (1.0 - min(1.0, frac / corte)) ** 2)
            if frac > 0.74:
                escala *= max(0.04, (1.0 - frac) / 0.26)
            return inst.scale_x * escala, inst.scale_x * escala, inst.scale_z * escala
        if modo == "yutapon_degrau":
            env = 1.08 if frac < 0.14 else (max(0.04, (1.0 - frac) / 0.20) if frac > 0.80 else 1.0)
            return inst.scale_x * env, inst.scale_x * env, inst.scale_z * env
        if modo == "esticar_vel":
            along = 1.0 + min(0.55, math.hypot(inst.vel.x, inst.vel.z) * 0.12)
            shrink = max(0.05, (1.0 - frac) / 0.22) if frac > 0.78 else 1.0
            if inst.tipo_mesh in ("hf_faisca", "cf_gota_tinta", "se_gota", "an_vento", "se_rastro"):
                return inst.scale_x * shrink, inst.scale_x * shrink, inst.scale_z * along * shrink
            return inst.scale_x * along * shrink, inst.scale_x * shrink, inst.scale_z * shrink
        return GerenciadorEfeitosStreet._escala_crescimento(inst, frac)

    def _atualizar_cartao_2d(
        self, inst: _InstanciaVFX, frac: float, perfil_mov: dict[str, float]
    ) -> None:
        alvo_idx = (
            inst.single_frame_idx
            if inst.single_frame_idx is not None
            else (0 if frac < 0.16 else (1 if math.floor((inst.age + inst.seed) * perfil_mov["fps"]) % 2 == 0 else 2) if frac < 0.76 else 3)
        )
        if alvo_idx != inst.frame_atual and 0 <= alvo_idx < len(inst.frames):
            inst.frame_atual = alvo_idx
            inst.node.setTexture(inst.frames[alvo_idx], 1)
        sx, _sy, sz = self._escala_por_modo(inst, frac)
        inst.node.setPos(inst.pos.x, inst.plane_y, inst.pos.z)
        inst.node.setR(inst.rot_base + inst.rot_vel * inst.age)
        inst.node.setScale(sx * 0.65, 1.0, sz * 0.65)

    def _atualizar_visual_instancia(
        self, inst: _InstanciaVFX, frac: float, perfil_mov: dict[str, float]
    ) -> None:
        if not inst.eh_malha_3d:
            self._atualizar_cartao_2d(inst, frac, perfil_mov)
            return

        if inst.fps_step > 0.0:
            passo = math.floor(inst.age * inst.fps_step)
            if passo == inst.frame_atual:
                return
            inst.frame_atual = passo

        sx, sy, sz = self._escala_por_modo(inst, frac)
        roll = inst.rot_base + inst.rot_vel * inst.age + inst.rot3d_vel.z * inst.age
        pitch = inst.tilt_p + inst.rot3d_vel.y * inst.age
        heading = inst.heading_h + inst.rot3d_vel.x * inst.age
        if inst.modo_mov == "planador_papel":
            pitch += math.sin(inst.age * 5.6 + inst.seed) * 14.0
        elif inst.modo_mov == "esticar_vel" and math.hypot(inst.vel.x, inst.vel.z) > 0.08:
            vx, vz = inst.vel.x, inst.vel.z
            if inst.tipo_mesh in ("hf_faisca", "cf_gota_tinta", "se_gota", "an_vento", "se_rastro"):
                roll = math.degrees(math.atan2(vx, vz))
            else:
                roll = -math.degrees(math.atan2(vz, vx))
        p = Vec3(inst.pos.x, inst.plane_y, inst.pos.z)
        if inst.modo_mov == "grade_voxel":
            passo = .065 * self._escala_global
            p = Vec3(*(round(v / passo) * passo for v in p))
        inst.node.setPos(p)
        inst.node.setHpr(heading, pitch, roll)
        inst.node.setScale(sx, sy, sz)

    @staticmethod
    def _avancar_instancia(inst: _InstanciaVFX, dt: float, anc: dict[str, Vec3]) -> None:
        if inst.modo_mov == "orbita_3d":
            base = anc.get(inst.anchor_key or "cabeca_centro", inst.pos) + inst.anchor_offset
            ang = inst.seed + inst.age * inst.orbita_vel
            inst.pos = Vec3(base.x + math.cos(ang) * inst.orbita_r[0], 0.0, base.z + math.sin(ang * 2.0 + inst.seed) * inst.orbita_r[2])
            inst.plane_y = base.y + math.sin(ang) * inst.orbita_r[1]
            return
        if inst.anchor_key is not None and inst.anchor_key in anc:
            base = anc[inst.anchor_key]
            if inst.eh_malha_3d:
                inst.anchor_offset += inst.vel * dt
                inst.plane_y = base.y + inst.anchor_offset.y
            inst.pos = Vec3(base.x + inst.anchor_offset.x, inst.plane_y, base.z + inst.anchor_offset.z)
            return
        decay = math.exp(-inst.drag * dt)
        inst.vel.x *= decay
        if inst.eh_malha_3d:
            inst.vel.y *= decay
            inst.plane_y += inst.vel.y * dt
        lift = math.sin(inst.age * 5.0 + inst.seed) * 0.9 if inst.modo_mov == "planador_papel" else 0.0
        inst.vel.z = inst.vel.z * decay + (inst.gravity + lift) * dt
        inst.pos.x += inst.vel.x * dt
        inst.pos.z += inst.vel.z * dt

    def _atualizar_instancias(self, dt: float, anc: dict[str, Vec3]) -> None:
        vivas: list[_InstanciaVFX] = []
        perfil_mov = PERFIS_MOVIMENTO_VFX.get(self._paleta, PERFIS_MOVIMENTO_VFX["spider_verse"])
        for inst in self._instancias:
            inst.age += dt
            if inst.age >= inst.ttl:
                inst.remover()
                continue
            if inst.atualizar_fase is not None:
                inst.atualizar_fase(inst.age / inst.ttl)
            elif inst.modo_mov == "grafismo":
                inst.node.setShaderInput("fase", inst.age / inst.ttl)
            else:
                self._avancar_instancia(inst, dt, anc)
                self._atualizar_visual_instancia(inst, min(1.0, inst.age / inst.ttl), perfil_mov)
            vivas.append(inst)
        self._instancias = vivas

"""Efeitos visuais Street-Punk / Spider-Verse desenhados à mão (v2.0).

Substitui os antigos cartões pixel-art genéricos por 11 sequências de 4 quadros
de tinta real (`assets/textures/vfx_street/*.png`), com:
- Ancoragem anatômica nos nós reais do rig 3D (têmpora, fones, antenas, topo
  da cabeça, sola dos tênis, laterais do corpo — nunca stickers gigantes soltos).
- Ciclo conduzido com respiro: F1 draw-on -> F2 pico -> F3 fervura a 8 FPS
  (oscilando F2/F3 com micro-wobble) -> F4 dissipação seca + respingos escapando.
- Três paletas trocáveis ao vivo: ``pb_escuro`` (nanquim + halo branco, padrão),
  ``pb_claro`` (giz/grafite branco + contorno preto) e ``colorido`` (Street Swag).
- Alpha binário puro (`AlphaTestAttrib > 0.5`, `TransparencyAttrib.MNone`) e
  guarda anti-magenta para compatibilidade total com o color key Win32.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from panda3d.core import (
    AlphaTestAttrib,
    AntialiasAttrib,
    CardMaker,
    NodePath,
    PNMImage,
    Texture,
    TransparencyAttrib,
    Vec3,
)
from PIL import Image

from sejoga.nucleo.recursos import assets_dir
from sejoga.render.sprites_efeitos import shader_sprite_bayer

logger = logging.getLogger(__name__)

# Planos Y seguros na câmera ortográfica (câmera em Y = -15 olhando +Y).
_FX_FRONT_Y = -2.25
_FX_CHAO_Y = -0.95
_MAX_INSTANCIAS = 36
_QUADROS_POR_TIRA = 4
_FPS_FERVURA = 8.0

# Paleta Street Swag (100% segura contra o chroma key magenta #FF00FF).
_CORES_STREET_SWAG: dict[str, tuple[int, int, int]] = {
    "musica": (182, 255, 42),       # Lima Mário
    "choque": (255, 232, 36),       # Amarelo elétrico
    "raiva": (236, 40, 48),         # Vermelho street punk
    "impacto": (255, 132, 28),      # Laranja impacto
    "queda_chao": (245, 236, 214),  # Poeira grafite clara com tinta quente
    "linhas_queda": (40, 232, 255), # Ciano velocidade
    "carinho": (255, 76, 152),      # Rosa seguro (G=76, longe do magenta chroma)
    "susto": (255, 224, 40),        # Amarelo exclamação
    "tontura": (38, 228, 255),      # Ciano espiral
    "sono": (152, 92, 255),         # Roxo calça Mário (G=92, chroma-safe)
    "respingo": (182, 255, 42),     # Lima respingo
}


def _seguro_chroma(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Impede qualquer pixel colorido de cair na faixa do color key magenta."""
    if r > 170 and b > 170 and g < 72:
        return (r, 76, b)
    return (r, g, b)


def _construir_quadros_paleta(
    caminho: Path,
    nome: str,
    paleta: str,
) -> tuple[Texture, ...]:
    """Fatia uma tira RGBA 1024x256 em 4 Textures Panda3D na paleta escolhida."""
    img = Image.open(caminho).convert("RGBA")
    fw = img.width // _QUADROS_POR_TIRA
    fh = img.height
    cor_swag = _seguro_chroma(*_CORES_STREET_SWAG.get(nome, (182, 255, 42)))

    quadros: list[Texture] = []
    for i in range(_QUADROS_POR_TIRA):
        cell = img.crop((i * fw, 0, (i + 1) * fw, fh))
        src = cell.load()
        pnm = PNMImage(fw, fh, 4)
        for y in range(fh):
            for x in range(fw):
                r, g, b, a = src[x, y]
                if a < 128:
                    pnm.setXelA(x, y, 0.0, 0.0, 0.0, 0.0)
                    continue
                # Na tira canônica:
                # - Tinta principal: escuro (r < 60)
                # - Miolo colorido (ex.: raiva, nuvem): cinza claro (195 <= r <= 232)
                # - Halo externo fino: branco puro (r > 235)
                if paleta == "pb_escuro":
                    if r < 60:
                        rr, gg, bb = (16, 16, 20)
                    elif r <= 232:
                        rr, gg, bb = (232, 232, 228)
                    else:
                        rr, gg, bb = (246, 246, 242)
                elif paleta == "pb_claro":
                    if r < 60:
                        rr, gg, bb = (246, 246, 242)
                    elif r <= 232:
                        rr, gg, bb = (28, 28, 34)
                    else:
                        rr, gg, bb = (16, 16, 20)
                else:
                    # colorido (Street Swag): se tem miolo (raiva/queda), pinta o miolo e mantém contorno preto;
                    # se é traço puro de tinta (notas/raio/coração/?!), pinta o traço com a cor Street Swag + contorno escuro!
                    if nome in ("raiva", "queda_chao"):
                        if r < 60:
                            rr, gg, bb = (16, 16, 20)
                        elif r <= 232:
                            rr, gg, bb = cor_swag
                        else:
                            rr, gg, bb = (246, 246, 240)
                    else:
                        if r < 60:
                            rr, gg, bb = cor_swag
                        else:
                            rr, gg, bb = (16, 16, 20)
                rr, gg, bb = _seguro_chroma(rr, gg, bb)
                pnm.setXelA(x, y, rr / 255.0, gg / 255.0, bb / 255.0, 1.0)
        tex = Texture(f"vfx-street-{nome}-{paleta}-{i}")
        tex.load(pnm)
        tex.setWrapU(Texture.WMClamp)
        tex.setWrapV(Texture.WMClamp)
        tex.setMinfilter(Texture.FTNearest)
        tex.setMagfilter(Texture.FTNearest)
        quadros.append(tex)
    return tuple(quadros)


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
    anchor_offset: Vec3 = Vec3(0.0, 0.0, 0.0)
    plane_y: float = _FX_FRONT_Y
    frame_atual: int = -1
    seed: float = 0.0
    spawned_flecks: bool = False
    allow_flecks: bool = True
    single_frame_idx: int | None = None


class GerenciadorEfeitosStreet:
    """Orquestra efeitos street-punk ancorados na anatomia do rig do Mário."""

    _NOMES_ASSETS = (
        "musica",
        "choque",
        "raiva",
        "impacto",
        "queda_chao",
        "linhas_queda",
        "carinho",
        "susto",
        "tontura",
        "sono",
        "respingo",
    )

    def __init__(
        self,
        parent_node: NodePath,
        *,
        head_node: NodePath | None = None,
        model_node: NodePath | None = None,
        paleta: str = "pb_escuro",
        escala_global: float = 1.0,
        habilitado: bool = True,
    ) -> None:
        self.root = parent_node.attachNewNode("efeitos-street-v2")
        self.root.setAntialias(AntialiasAttrib.MNone, 1)
        self.head_node = head_node
        self.model_node = model_node
        self._antena_dir_node = self._buscar_antena(head_node, "antena-direita")
        self._antena_esq_node = self._buscar_antena(head_node, "antena-esquerda")
        self._enabled = bool(habilitado)
        self._paleta = paleta if paleta in ("pb_escuro", "pb_claro", "colorido") else "pb_escuro"
        self._escala_global = max(0.5, min(1.6, float(escala_global)))
        self._rng = random.Random()
        self._tempo = 0.0
        self._instancias: list[_InstanciaVFX] = []
        self._banco_cache: dict[str, dict[str, tuple[Texture, ...]]] = {}
        self._texturas: dict[str, tuple[Texture, ...]] = {}
        self._carregar_paleta(self._paleta)
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
        self._prev_susto = False
        self._prev_choque = False
        self._lado_alternado = 1

    @staticmethod
    def _buscar_antena(head_node: NodePath | None, nome: str) -> NodePath | None:
        if head_node is None or head_node.isEmpty():
            return None
        ant = head_node.find(f"**/{nome}")
        if ant.isEmpty():
            return None
        esf = ant.find("**/sphere")
        return esf if not esf.isEmpty() else ant

    def _carregar_paleta(self, paleta: str) -> None:
        if paleta in self._banco_cache:
            self._texturas = self._banco_cache[paleta]
            return
        pasta = assets_dir() / "textures" / "vfx_street"
        banco: dict[str, tuple[Texture, ...]] = {}
        for nome in self._NOMES_ASSETS:
            caminho = pasta / f"{nome}.png"
            if not caminho.is_file():
                logger.warning("VFX street ausente: %s", caminho)
                continue
            try:
                banco[nome] = _construir_quadros_paleta(caminho, nome, paleta)
            except Exception as exc:
                logger.warning("Falha ao carregar VFX street %s: %s", nome, exc)
        self._banco_cache[paleta] = banco
        self._texturas = banco

    def configurar(
        self,
        *,
        habilitado: bool | None = None,
        paleta: str | None = None,
        escala_global: float | None = None,
    ) -> None:
        """Atualiza estado/paleta/escala ao vivo sem reiniciar o app."""
        if habilitado is not None:
            self._enabled = bool(habilitado)
            if not self._enabled:
                self.limpar()
        if escala_global is not None:
            self._escala_global = max(0.5, min(1.6, float(escala_global)))
        if paleta is not None and paleta in ("pb_escuro", "pb_claro", "colorido") and paleta != self._paleta:
            self._paleta = paleta
            self._carregar_paleta(paleta)
            # Atualiza instâncias vivas instantaneamente para feedback visual imediato.
            for inst in self._instancias:
                novas = self._texturas.get(inst.nome)
                if novas:
                    inst.frames = novas
                    idx = max(0, min(len(novas) - 1, inst.frame_atual if inst.frame_atual >= 0 else 0))
                    inst.node.setTexture(novas[idx], 1)

    def limpar(self) -> None:
        """Remove todos os efeitos ativos imediatamente."""
        for inst in self._instancias:
            if not inst.node.isEmpty():
                inst.node.removeNode()
        self._instancias.clear()

    def _criar_cartao(self, nome: str, tex: Texture) -> NodePath:
        cm = CardMaker(f"vfx-street-{nome}")
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)
        np = self.root.attachNewNode(cm.generate())
        np.setTexture(tex, 1)
        np.setTwoSided(True)
        np.setLightOff(1)
        np.setTransparency(TransparencyAttrib.MNone)
        np.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MGreater, 0.5))
        np.setShader(shader_sprite_bayer(), 2)
        np.setShaderInput("u_fade", 1.0)
        np.setCollideMask(0)
        np.setBin("fixed", 42)
        return np

    def _ancora_ponto(
        self,
        node: NodePath | None,
        local: tuple[float, float, float],
        fallback: tuple[float, float, float],
        plane_y: float = _FX_FRONT_Y,
    ) -> Vec3:
        if node is not None and not node.isEmpty():
            p = self.root.getRelativePoint(node, Vec3(*local))
            return Vec3(p.x, plane_y, p.z)
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
                return Vec3(c.x, plane_y, c.z)
            p = self.root.getRelativePoint(node, Vec3(0.0, 0.0, 0.0))
            return Vec3(p.x, plane_y, p.z)
        return Vec3(fallback[0], plane_y, fallback[2])

    def _calcular_ancoras(self) -> dict[str, Vec3]:
        """Calcula pontos anatômicos exatos no espaço do modelo atual."""
        anc = {
            # Topo real acima do arco do fone (carinho, susto, tontura — sem sobrepor a cabeça!)
            "cabeca_topo": self._ancora_ponto(self.head_node, (0.0, 0.14, 0.44), (0.0, _FX_FRONT_Y, 4.75)),
            # Canto superior da testa/gabinete (veia de raiva colada na testa, sem cobrir o fone!)
            "templo": self._ancora_ponto(self.head_node, (-0.12, 0.18, 0.24), (0.68, _FX_FRONT_Y, 3.85)),
            # Borda externa dos fones esquerdo e direito (notas saindo direto das conchas!)
            "fone_dir": self._ancora_ponto(self.head_node, (0.32, 0.10, 0.16), (-1.75, _FX_FRONT_Y, 3.45)),
            "fone_esq": self._ancora_ponto(self.head_node, (-0.32, 0.10, 0.16), (1.75, _FX_FRONT_Y, 3.45)),
            # Lateral do visor (ZZZ de sono saindo perto da boca/visor)
            "visor_lado": self._ancora_ponto(self.head_node, (-0.26, 0.16, 0.14), (1.42, _FX_FRONT_Y, 3.35)),
            # Meio e pontas das antenas (raios elétricos)
            "antenas_meio": self._ancora_ponto(self.head_node, (0.0, 0.10, 0.48), (0.0, _FX_FRONT_Y, 4.95)),
            "antena_d": self._ancora_centro(self._antena_dir_node, (-1.85, _FX_FRONT_Y, 4.85)),
            "antena_e": self._ancora_centro(self._antena_esq_node, (1.85, _FX_FRONT_Y, 4.85)),
            # Sola dos tênis / chão (queda e pouso pesado!)
            "pes": self._ancora_ponto(self.model_node, (0.0, 0.0, 0.02), (0.0, _FX_CHAO_Y, -1.48), plane_y=_FX_CHAO_Y),
            # Centro do tronco e laterais externas do corpo (linhas de queda e impactos na parede)
            "tronco": self._ancora_ponto(self.model_node, (0.0, 0.0, 0.50), (0.0, _FX_FRONT_Y, 1.35)),
            "lado_esq": self._ancora_ponto(self.model_node, (0.56, 0.0, 0.52), (-2.85, _FX_FRONT_Y, 1.65)),
            "lado_dir": self._ancora_ponto(self.model_node, (-0.56, 0.0, 0.52), (2.85, _FX_FRONT_Y, 1.65)),
        }
        return anc

    def _contar_ativos(self, nome: str) -> int:
        return sum(1 for inst in self._instancias if inst.nome == nome)

    def _emitir(
        self,
        nome: str,
        pos: Vec3,
        *,
        vel: Vec3 = Vec3(0.0, 0.0, 0.0),
        ttl: float = 1.45,
        scale_x: float = 0.85,
        scale_z: float | None = None,
        rot_base: float = 0.0,
        rot_vel: float = 0.0,
        drag: float = 1.8,
        gravity: float = 0.0,
        anchor_key: str | None = None,
        anchor_offset: Vec3 = Vec3(0.0, 0.0, 0.0),
        plane_y: float = _FX_FRONT_Y,
        allow_flecks: bool = True,
        single_frame_idx: int | None = None,
    ) -> None:
        if not self._enabled:
            return
        frames = self._texturas.get(nome)
        if not frames:
            return
        while len(self._instancias) >= _MAX_INSTANCIAS:
            antigo = self._instancias.pop(0)
            if not antigo.node.isEmpty():
                antigo.node.removeNode()
        sx = scale_x * self._escala_global
        sz = (scale_x if scale_z is None else scale_z) * self._escala_global
        p = Vec3(pos.x, plane_y, pos.z)
        node = self._criar_cartao(nome, frames[single_frame_idx or 0])
        node.setPos(p)
        node.setR(rot_base)
        node.setScale(sx * 0.55, 1.0, sz * 0.55)
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
                allow_flecks=allow_flecks,
                single_frame_idx=single_frame_idx,
            )
        )

    def _emitir_respingos(self, origem: Vec3, quantidade: int = 2, vel_bias: Vec3 = Vec3(0, 0, 0.35)) -> None:
        """Solta pequenos rabiscos/gotículas que escapam e flutuam antes de dissipar."""
        if not self._enabled or "respingo" not in self._texturas:
            return
        for _ in range(quantidade):
            ang = self._rng.uniform(0.0, math.tau)
            vel_mag = self._rng.uniform(0.55, 1.35)
            v = Vec3(
                math.cos(ang) * vel_mag + vel_bias.x,
                0.0,
                math.sin(ang) * vel_mag * 0.65 + vel_bias.z,
            )
            esc = self._rng.uniform(0.28, 0.42)
            self._emitir(
                "respingo",
                Vec3(
                    origem.x + self._rng.uniform(-0.22, 0.22),
                    _FX_FRONT_Y,
                    origem.z + self._rng.uniform(-0.18, 0.18),
                ),
                vel=v,
                ttl=self._rng.uniform(0.75, 1.25),
                scale_x=esc,
                rot_base=self._rng.uniform(-32.0, 32.0),
                rot_vel=self._rng.uniform(-45.0, 45.0),
                drag=1.2,
                gravity=-0.35,
                allow_flecks=False,
                single_frame_idx=self._rng.randint(0, 3),
            )

    # ── Eventos físicos explícitos (queda, pouso pesado, batida na parede/teto) ──

    def disparar_impacto_chao(self, forca: float = 1.0) -> None:
        """Impacto street-ink rente aos tênis no pouso/queda."""
        if not self._enabled:
            return
        anc = self._calcular_ancoras()
        pes = anc["pes"]
        f = max(0.75, min(1.6, float(forca)))
        # Onda horizontal + nuvens rabiscadas bem nos pés do Mário (abraçando fora dos tênis)
        self._emitir(
            "queda_chao",
            Vec3(pes.x, _FX_CHAO_Y, pes.z + 0.56),
            vel=Vec3(0.0, 0.0, 0.03),
            ttl=0.85 + 0.16 * min(1.0, f - 0.75),
            scale_x=3.10 * (0.86 + 0.20 * f),
            scale_z=1.75 * (0.86 + 0.18 * f),
            rot_base=self._rng.uniform(-3.0, 3.0),
            drag=2.5,
            plane_y=_FX_CHAO_Y,
            allow_flecks=True,
        )
        # Se a queda foi pesada, adiciona um estalo compacto de impacto no ponto de contato
        if f >= 1.25:
            self._emitir(
                "impacto",
                Vec3(pes.x, _FX_FRONT_Y, pes.z + 0.22),
                vel=Vec3(0.0, 0.0, 0.06),
                ttl=0.68,
                scale_x=1.08 * min(1.30, f * 0.78),
                rot_base=self._rng.uniform(-16.0, 16.0),
                allow_flecks=False,
            )
            self._emitir_respingos(
                Vec3(pes.x, _FX_FRONT_Y, pes.z + 0.30),
                quantidade=3,
                vel_bias=Vec3(0.0, 0.0, 0.95),
            )

    def disparar_impacto_parede(
        self,
        kind: str,
        velocity: tuple[float, float],
        forca: float = 1.0,
    ) -> None:
        """Impacto direcional exatamente no lado do corpo que bateu na parede/teto."""
        if not self._enabled:
            return
        anc = self._calcular_ancoras()
        vx, vy = float(velocity[0]), float(velocity[1])
        f = max(0.7, min(1.5, float(forca)))
        kind_l = str(kind).lower()
        if "ceil" in kind_l or "top" in kind_l or (abs(vy) > abs(vx) * 1.4 and vy < 0):
            pos = Vec3(anc["cabeca_topo"].x, _FX_FRONT_Y, anc["cabeca_topo"].z + 0.15)
            bias = Vec3(0.0, 0.0, -0.45)
        elif vx < -25.0:
            # Estava indo pra esquerda e bateu na parede esquerda
            pos = Vec3(anc["lado_esq"].x - 0.15, _FX_FRONT_Y, anc["lado_esq"].z)
            bias = Vec3(0.75, 0.0, 0.35)
        elif vx > 25.0:
            pos = Vec3(anc["lado_dir"].x + 0.15, _FX_FRONT_Y, anc["lado_dir"].z)
            bias = Vec3(-0.75, 0.0, 0.35)
        else:
            # Batida no chão/janela inferior
            self.disparar_impacto_chao(f)
            return

        self._emitir(
            "impacto",
            pos,
            vel=Vec3(bias.x * 0.15, 0.0, bias.z * 0.15),
            ttl=0.72,
            scale_x=1.08 * (0.80 + 0.25 * f),
            rot_base=self._rng.uniform(-22.0, 22.0),
            allow_flecks=True,
        )
        self._emitir_respingos(pos, quantidade=2, vel_bias=bias)

    def disparar_carinho(self) -> None:
        """Coração rabiscado pequeno subindo logo acima do arco do fone no carinho real."""
        if not self._enabled or self._cd_carinho > 0.0 or self._contar_ativos("carinho") >= 2:
            return
        self._cd_carinho = 0.95
        anc = self._calcular_ancoras()
        topo = anc["cabeca_topo"]
        lado = self._rng.uniform(-0.35, 0.35)
        self._emitir(
            "carinho",
            Vec3(topo.x + lado, _FX_FRONT_Y, topo.z + 0.42),
            vel=Vec3(lado * 0.45, 0.0, 0.52),
            ttl=1.55,
            scale_x=0.84,
            rot_base=self._rng.uniform(-10.0, 10.0),
            rot_vel=self._rng.uniform(-8.0, 8.0),
            drag=1.1,
            allow_flecks=True,
        )

    # ── Loop de atualização por frame ──

    def atualizar(self, dt: float, params: dict[str, Any]) -> None:
        dt = max(0.0, min(0.05, float(dt)))
        self._tempo += dt
        if not self._enabled:
            if self._instancias:
                self.limpar()
            return

        self._cd_musica = max(0.0, self._cd_musica - dt)
        self._cd_choque = max(0.0, self._cd_choque - dt)
        self._cd_raiva = max(0.0, self._cd_raiva - dt)
        self._cd_carinho = max(0.0, self._cd_carinho - dt)
        self._cd_susto = max(0.0, self._cd_susto - dt)
        self._cd_tontura = max(0.0, self._cd_tontura - dt)
        self._cd_sono = max(0.0, self._cd_sono - dt)
        self._cd_linhas_queda = max(0.0, self._cd_linhas_queda - dt)

        anc = self._calcular_ancoras()
        self._processar_gatilhos(anc, params)
        self._atualizar_instancias(dt, anc)

    def _processar_gatilhos(self, anc: dict[str, Vec3], params: dict[str, Any]) -> None:
        # 1. RAIVA (veia grossa colada no canto superior da testa, sem invadir o fone!)
        if params.get("raiva") and self._cd_raiva <= 0.0 and self._contar_ativos("raiva") == 0:
            self._cd_raiva = 1.35
            self._emitir(
                "raiva",
                anc["templo"],
                vel=Vec3(0.0, 0.0, 0.0),
                ttl=1.45,
                scale_x=0.80,
                rot_base=self._rng.uniform(-7.0, 7.0),
                anchor_key="templo",
                anchor_offset=Vec3(0.02, 0.0, 0.04),
                allow_flecks=True,
            )

        # 2. MÚSICA (notas saindo da lateral externa das conchas dos fones e subindo no beat)
        if params.get("som_fones") and self._cd_musica <= 0.0 and self._contar_ativos("musica") < 2:
            acento = bool(params.get("acento_danca"))
            self._cd_musica = 0.85 if acento else 1.45
            self._lado_alternado *= -1
            chave = "fone_esq" if self._lado_alternado > 0 else "fone_dir"
            p_fone = anc[chave]
            dir_x = 1.0 if self._lado_alternado > 0 else -1.0
            self._emitir(
                "musica",
                Vec3(p_fone.x + dir_x * 0.45, _FX_FRONT_Y, p_fone.z + 0.35),
                vel=Vec3(dir_x * self._rng.uniform(0.35, 0.62), 0.0, self._rng.uniform(0.55, 0.82)),
                ttl=1.65,
                scale_x=1.02 if acento else 0.90,
                rot_base=dir_x * self._rng.uniform(4.0, 14.0),
                rot_vel=dir_x * self._rng.uniform(-10.0, 10.0),
                drag=0.95,
                allow_flecks=True,
            )

        # 3. CHOQUE (raio elétrico compacto nas pontas das antenas)
        choque_on = bool(params.get("choque_argolas") or params.get("estouro_fone"))
        if choque_on and (not self._prev_choque or self._cd_choque <= 0.0) and self._contar_ativos("choque") < 2:
            self._cd_choque = 0.72
            alvo_key = self._rng.choice(("antena_d", "antena_e", "antenas_meio"))
            self._emitir(
                "choque",
                anc[alvo_key],
                vel=Vec3(self._rng.uniform(-0.18, 0.18), 0.0, 0.25),
                ttl=1.10,
                scale_x=0.92,
                rot_base=self._rng.uniform(-18.0, 18.0),
                anchor_key=alvo_key,
                anchor_offset=Vec3(0.0, 0.0, 0.22),
                allow_flecks=True,
            )
        self._prev_choque = choque_on

        # 4. SUSTO (?!) — compacto logo acima do arco do fone (sem sobrepor a cabeça)
        susto_on = bool(params.get("susto"))
        if susto_on and not self._prev_susto and self._cd_susto <= 0.0 and self._contar_ativos("susto") == 0:
            self._cd_susto = 1.20
            self._emitir(
                "susto",
                Vec3(anc["cabeca_topo"].x + 0.28, _FX_FRONT_Y, anc["cabeca_topo"].z + 0.65),
                vel=Vec3(0.06, 0.0, 0.18),
                ttl=1.30,
                scale_x=1.08,
                rot_base=self._rng.uniform(-8.0, 8.0),
                anchor_key="cabeca_topo",
                anchor_offset=Vec3(0.28, 0.0, 0.65),
                allow_flecks=True,
            )
        self._prev_susto = susto_on

        # 5. TONTURA (espiral compacto orbitando logo acima do arco do fone)
        if params.get("tontura") and self._cd_tontura <= 0.0 and self._contar_ativos("tontura") == 0:
            self._cd_tontura = 1.45
            self._emitir(
                "tontura",
                Vec3(anc["cabeca_topo"].x, _FX_FRONT_Y, anc["cabeca_topo"].z + 0.58),
                vel=Vec3(0.0, 0.0, 0.0),
                ttl=1.55,
                scale_x=0.98,
                rot_base=0.0,
                rot_vel=52.0,
                anchor_key="cabeca_topo",
                anchor_offset=Vec3(0.0, 0.0, 0.58),
                allow_flecks=False,
            )

        # 6. SONO (ZZZ pequeno saindo perto do visor, bem conduzido e calmo)
        if params.get("sono") and self._cd_sono <= 0.0 and self._contar_ativos("sono") < 2:
            self._cd_sono = 1.75
            p_v = anc["visor_lado"]
            self._emitir(
                "sono",
                Vec3(p_v.x + 0.36, _FX_FRONT_Y, p_v.z + 0.25),
                vel=Vec3(0.28, 0.0, 0.45),
                ttl=1.95,
                scale_x=0.86,
                rot_base=self._rng.uniform(-6.0, 8.0),
                drag=0.55,
                allow_flecks=False,
            )

        # 7. CARINHO (quando controller sinaliza carinho/pet)
        if params.get("carinho"):
            self.disparar_carinho()

        # 8. QUEDA RÁPIDA / ARREMESSO NO AR (linhas street-ink abraçando FORA dos ombros/braços)
        grounded = bool(params.get("grounded", True))
        vx, vy = params.get("velocidade", (0.0, 0.0))
        vel_mag = math.hypot(float(vx), float(vy))
        if (
            not grounded
            and not params.get("dragging", False)
            and vel_mag > 540.0
            and self._cd_linhas_queda <= 0.0
            and self._contar_ativos("linhas_queda") == 0
        ):
            self._cd_linhas_queda = 0.34
            ang_vel = max(-38.0, min(38.0, math.degrees(math.atan2(float(vx), max(120.0, abs(float(vy)))))))
            self._emitir(
                "linhas_queda",
                anc["tronco"],
                vel=Vec3(0.0, 0.0, 0.0),
                ttl=0.42,
                scale_x=4.95,
                scale_z=4.20,
                rot_base=ang_vel,
                anchor_key="tronco",
                anchor_offset=Vec3(0.0, 0.0, 0.25),
                allow_flecks=False,
            )

    def _atualizar_instancias(self, dt: float, anc: dict[str, Vec3]) -> None:
        vivas: list[_InstanciaVFX] = []
        for inst in self._instancias:
            inst.age += dt
            if inst.age >= inst.ttl:
                if not inst.node.isEmpty():
                    inst.node.removeNode()
                continue

            frac = inst.age / inst.ttl
            # Integração de movimento (livre ou ancorado com micro-flutuação)
            if inst.anchor_key is not None and inst.anchor_key in anc:
                base = anc[inst.anchor_key]
                inst.pos = Vec3(
                    base.x + inst.anchor_offset.x,
                    inst.plane_y,
                    base.z + inst.anchor_offset.z,
                )
            else:
                decay = math.exp(-inst.drag * dt)
                inst.vel.x *= decay
                inst.vel.z = inst.vel.z * decay + inst.gravity * dt
                inst.pos.x += inst.vel.x * dt
                inst.pos.z += inst.vel.z * dt

            # Seleção de quadro conduzida:
            # 0..16%: F1 (draw-on)
            # 16..76%: F2 <-> F3 fervendo a 8 FPS (estética Spider-Verse viva!)
            # 76..100%: F4 (dissipação seca)
            if inst.single_frame_idx is not None:
                alvo_idx = inst.single_frame_idx
            elif frac < 0.16:
                alvo_idx = 0
            elif frac < 0.76:
                boil_step = int(math.floor((inst.age + inst.seed) * _FPS_FERVURA))
                alvo_idx = 1 if (boil_step % 2 == 0) else 2
            else:
                alvo_idx = 3

            if alvo_idx != inst.frame_atual and 0 <= alvo_idx < len(inst.frames):
                inst.frame_atual = alvo_idx
                inst.node.setTexture(inst.frames[alvo_idx], 1)

            # Solta 1 ou 2 respingos escapando no início da fervura/dissipação
            if inst.allow_flecks and not inst.spawned_flecks and frac >= 0.56:
                inst.spawned_flecks = True
                if self._rng.random() < 0.70:
                    self._emitir_respingos(
                        inst.pos,
                        quantidade=1 if inst.nome in ("musica", "carinho", "raiva") else 2,
                        vel_bias=Vec3(inst.vel.x * 0.5, 0.0, max(0.25, inst.vel.z * 0.6)),
                    )

            # Curva de escala orgânica: pop elástico no draw-on -> pulso sutil -> encolhimento leve no fim
            if frac < 0.18:
                u = frac / 0.18
                # Overshoot suave (12 Princípios: follow-through)
                env = 0.48 + 0.62 * math.sin(u * math.pi * 0.58)
            elif frac > 0.80:
                u = (frac - 0.80) / 0.20
                env = 1.0 - 0.28 * u * u
            else:
                # Micro pulso de fervura (8 FPS stepped)
                step_b = math.floor((inst.age + inst.seed) * _FPS_FERVURA)
                env = 1.0 + (0.045 if (int(step_b) % 2 == 0) else -0.025)

            # Micro jitter de posição/rotação em 8 FPS (parece desenhado em cada quadro)
            step_j = math.floor((inst.age + inst.seed * 1.7) * _FPS_FERVURA)
            jx = math.sin(step_j * 12.9898) * 0.024
            jz = math.cos(step_j * 78.233) * 0.024
            jr = math.sin(step_j * 43.123) * 2.4

            inst.node.setPos(inst.pos.x + jx, inst.plane_y, inst.pos.z + jz)
            inst.node.setR(inst.rot_base + inst.rot_vel * inst.age + jr)
            inst.node.setScale(inst.scale_x * env, 1.0, inst.scale_z * env)
            vivas.append(inst)

        self._instancias = vivas

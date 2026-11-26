"""Small falling slime droplets, attached to the model coordinate space."""

import random
from dataclasses import dataclass

from panda3d.core import Vec3

from sejoga.animacao.dados_autorais import tentaculos_ativos
from sejoga.render.sprites_efeitos import atlas_gosma, cartao_pixel, quadro_gosma
from sejoga.tentaculos.sistema_tentaculos import Tentacle, TentacleState, raio_tentaculo


# Tensão (s), gravidade relativa, alongamento e frequência de atualização visual.
_QUEDA = {
    "padrao": (.20, 1., 1., 0),
    "pixel": (.16, 1.45, .48, 12),
    "rascunho": (.24, 1.22, 1.42, 8),
    "hifi_comic": (.14, 1.62, .83, 0),
    "cyberfunk": (.12, 1.35, 1.80, 0),
    "anime": (.27, 1.72, 2.22, 12),
    "blockbench": (.17, 1.42, .74, 12),
    "lowpoly_block": (.13, 1.90, .64, 15),
    "holograma": (.18, .38, .72, 16),
    "gameboy": (.29, .90, .55, 6),
    "manga_papel": (.22, 1.30, 2.55, 9),
}


@dataclass
class Gota:
    """Uma gota individual de gosma presa ou em queda no espaço do modelo."""

    node: object
    velocity: Vec3
    size: float
    age: float = 0.0
    source: Tentacle | None = None
    index: int = 0
    pos_livre: Vec3 | None = None


class TentacleDrips:
    """Gotas que pingam das pontas dos tentáculos."""

    def __init__(self, parent):
        """Monta o pool de gotas sob ``parent``."""
        self.parent = parent
        self.rng = random.Random()
        self.remaining = 0.6
        self.drops = []
        self.atlas = atlas_gosma()
        self._queda = _QUEDA["padrao"]
        self._cor_estilo: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)

    def aplicar_estilo(self, filtro: str, colorkey_hex: str = "#FF00FF") -> None:
        """Ajusta tensão, queda, exposição dos quadros e cor ao filtro ativo."""
        from sejoga.render.chroma_tuning import seguro_contra_chroma_255
        from sejoga.tentaculos.sistema_tentaculos import ESTILOS_TENTACULO

        filtro_norm = "anime" if filtro == "anime_impact" else filtro
        self._queda = _QUEDA.get(filtro_norm, _QUEDA["padrao"])
        estilo = ESTILOS_TENTACULO.get(filtro_norm, ESTILOS_TENTACULO["padrao"])
        r, g, b, a = estilo["drips"]
        rs, gs, bs = seguro_contra_chroma_255(
            int(round(max(0.0, min(1.0, r)) * 255.0)),
            int(round(max(0.0, min(1.0, g)) * 255.0)),
            int(round(max(0.0, min(1.0, b)) * 255.0)),
            colorkey_hex,
        )
        self._cor_estilo = (rs / 255.0, gs / 255.0, bs / 255.0, float(a))
        for drop in self.drops:
            if not drop.node.isEmpty():
                cr, cg, cb, ca = self._cor_estilo
                drop.node.setColorScale(cr, cg, cb, min(1.0, ca))

    def _gota(self, pos, size):
        node = cartao_pixel(self.parent, "pink-slime-drop", self.atlas)
        node.setBillboardPointEye()
        node.setPos(pos)
        node.setScale(size)
        node.setColorScale(*self._cor_estilo)
        quadro_gosma(node, 2, 0)
        return node

    def spray(self, tentacles):
        """A short outward burst of pink droplets at the sneeze."""
        limbs = [t for t in tentacles if t.state != TentacleState.DORMANT]
        for _ in range(min(10, 16 - len(self.drops))):
            if not limbs:
                break
            limb = self.rng.choice(limbs)
            size = self.rng.uniform(0.032, 0.060)
            node = self._gota(limb.anchor + limb.reference_front * 0.18, size)
            velocity = limb.reference_front * self.rng.uniform(0.35, 0.8)
            velocity += Vec3(
                self.rng.uniform(-0.3, 0.3), 0, self.rng.uniform(-0.05, 0.3)
            )
            self.drops.append(Gota(node, velocity, size))

    def _tentar_emitir_gota(self, tentacles) -> None:
        """Emite uma nova gota se houver tentáculos expostos e o intervalo venceu."""
        exposed = [
            t for t in tentacles if t.reveal > 0.45 and t.state != TentacleState.DORMANT
        ]
        if not exposed or self.remaining > 0 or len(self.drops) >= 16:
            return
        gotas = tentaculos_ativos().get("gotas", {})
        escala_min = float(gotas.get("escala_min", 0.033))
        escala_max = float(gotas.get("escala_max", 0.057))
        limb = self.rng.choice(exposed)
        index = max(
            1,
            int((len(limb.segments) - 1) * limb.reveal * self.rng.uniform(0.5, 0.95)),
        )
        size = self.rng.uniform(escala_min, escala_max) * limb.girth_scale
        node = self._gota(limb.segments[index].pos, size)
        self.drops.append(Gota(node, Vec3(0), size, source=limb, index=index))
        self.remaining = (
            self.rng.uniform(
                float(gotas.get("intervalo_enxurrada_min_s", 0.12)),
                float(gotas.get("intervalo_enxurrada_max_s", 0.28)),
            )
            if limb.enxurrada
            else self.rng.uniform(
                float(gotas.get("intervalo_normal_min_s", 0.4)),
                float(gotas.get("intervalo_normal_max_s", 1.1)),
            )
        )

    def _avancar_gota_presa(self, drop: Gota) -> bool:
        """Atualiza uma gota ainda presa ao tentáculo; retorna False se removida."""
        limb = drop.source
        span = limb.reveal * (len(limb.segments) - 1)
        if limb.state == TentacleState.DORMANT or span < drop.index:
            drop.node.removeNode()
            return False
        segment = limb.segments[drop.index]
        radius = raio_tentaculo(drop.index / span) * limb.girth_scale * 0.65
        stretch = min(1.0, drop.age / self._queda[0])
        length = drop.size * (0.8 + stretch * 1.15)
        drop.node.setPos(segment.pos - Vec3(0, 0, radius + length * 0.36))
        drop.node.setScale(drop.size, drop.size, length)
        quadro_gosma(drop.node, 2, 0)
        if stretch >= 1.0:
            drop.source = None
            drop.age = 0
            drop.velocity = segment.vel * 0.35 + Vec3(0, 0, -0.08)
        return True

    def _avancar_gota_livre(self, drop: Gota, dt: float) -> bool:
        """Atualiza uma gota em queda livre; retorna False quando expira."""
        gotas = tentaculos_ativos().get("gotas", {})
        ttl = max(0.05, float(gotas.get("ttl_queda_s", 0.85)))
        grav = float(gotas.get("gravidade", -0.85))
        if drop.age >= ttl:
            drop.node.removeNode()
            return False
        if drop.pos_livre is None:
            drop.pos_livre = Vec3(drop.node.getPos())
        _, peso, alongamento, fps = self._queda
        drop.velocity.z += grav * peso * dt
        drop.pos_livre += drop.velocity * dt
        if fps and int(drop.age * fps) == int(max(0., drop.age - dt) * fps):
            return True
        drop.node.setPos(drop.pos_livre)
        drop.node.setScale(drop.size, drop.size, drop.size * (1 + drop.age * alongamento))
        quadro_gosma(drop.node, 2, 1 if drop.age < 0.18 else 2)
        cr, cg, cb, _ = self._cor_estilo
        drop.node.setColorScale(cr, cg, cb, min(1, (ttl - drop.age) / 0.25))
        return True

    def limpar(self):
        """Remove gotas suspensas e em queda quando os efeitos são desligados."""
        for drop in self.drops:
            drop.node.removeNode()
        self.drops.clear()

    def update(self, dt, tentacles):
        """Avança as gotas e solta novas a partir dos tentáculos."""
        dt = max(0, min(0.05, dt))
        self.remaining -= dt
        self._tentar_emitir_gota(tentacles)
        alive = []
        for drop in self.drops:
            drop.age += dt
            continua = (
                self._avancar_gota_presa(drop)
                if drop.source is not None
                else self._avancar_gota_livre(drop, dt)
            )
            if continua:
                alive.append(drop)
        self.drops = alive

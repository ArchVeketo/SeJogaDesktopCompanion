"""Small falling slime droplets, attached to the model coordinate space."""

import random
from dataclasses import dataclass

from panda3d.core import Vec3

from sejoga.render.sprites_efeitos import atlas_gosma, cartao_pixel, quadro_gosma
from sejoga.tentaculos.sistema_tentaculos import Tentacle, TentacleState, raio_tentaculo


@dataclass
class Gota:
    """Uma gota individual de gosma presa ou em queda no espaço do modelo."""

    node: object
    velocity: Vec3
    size: float
    age: float = 0.0
    source: Tentacle | None = None
    index: int = 0


class TentacleDrips:
    """Gotas que pingam das pontas dos tentáculos."""

    def __init__(self, parent):
        """Monta o pool de gotas sob ``parent``."""
        self.parent = parent
        self.rng = random.Random()
        self.remaining = 0.6
        self.drops = []
        self.atlas = atlas_gosma()

    def _gota(self, pos, size):
        node = cartao_pixel(self.parent, "pink-slime-drop", self.atlas)
        node.setBillboardPointEye()
        node.setPos(pos)
        node.setScale(size)
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
        limb = self.rng.choice(exposed)
        index = max(
            1,
            int((len(limb.segments) - 1) * limb.reveal * self.rng.uniform(0.5, 0.95)),
        )
        size = self.rng.uniform(0.033, 0.057) * limb.girth_scale
        node = self._gota(limb.segments[index].pos, size)
        self.drops.append(Gota(node, Vec3(0), size, source=limb, index=index))
        self.remaining = (
            self.rng.uniform(0.12, 0.28)
            if limb.enxurrada
            else self.rng.uniform(0.4, 1.1)
        )

    @staticmethod
    def _avancar_gota_presa(drop: Gota) -> bool:
        """Atualiza uma gota ainda presa ao tentáculo; retorna False se removida."""
        limb = drop.source
        span = limb.reveal * (len(limb.segments) - 1)
        if limb.state == TentacleState.DORMANT or span < drop.index:
            drop.node.removeNode()
            return False
        segment = limb.segments[drop.index]
        radius = raio_tentaculo(drop.index / span) * limb.girth_scale * 0.65
        stretch = min(1.0, drop.age / 0.20)
        length = drop.size * (0.8 + stretch * 1.15)
        drop.node.setPos(segment.pos - Vec3(0, 0, radius + length * 0.36))
        drop.node.setScale(drop.size, drop.size, length)
        quadro_gosma(drop.node, 2, 0)
        if stretch >= 1.0:
            drop.source = None
            drop.age = 0
            drop.velocity = segment.vel * 0.35 + Vec3(0, 0, -0.08)
        return True

    @staticmethod
    def _avancar_gota_livre(drop: Gota, dt: float) -> bool:
        """Atualiza uma gota em queda livre; retorna False quando expira."""
        if drop.age >= 0.85:
            drop.node.removeNode()
            return False
        drop.velocity.z -= 0.85 * dt
        drop.node.setPos(drop.node.getPos() + drop.velocity * dt)
        drop.node.setScale(drop.size, drop.size, drop.size * (1 + drop.age))
        quadro_gosma(drop.node, 2, 1 if drop.age < 0.18 else 2)
        drop.node.setColorScale(1, 1, 1, min(1, (0.85 - drop.age) / 0.25))
        return True

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

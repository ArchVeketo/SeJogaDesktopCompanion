"""Finite oriented collision volumes for the procedural tentacle chain."""

import math
from dataclasses import dataclass

from panda3d.core import Mat4, Point3, Vec3


@dataclass
class ObstacleBox:
    """Caixa de obstáculo que os tentáculos não atravessam."""

    name: str
    low: Vec3
    high: Vec3
    to_local: Mat4
    to_model: Mat4

    def _cachear_matriz_modelo(self) -> None:
        """Extrai células da matriz local->modelo para projeção sem alocações."""
        w = self.to_model
        self._w00, self._w10, self._w20, self._w30 = (
            float(w.getCell(0, 0)),
            float(w.getCell(1, 0)),
            float(w.getCell(2, 0)),
            float(w.getCell(3, 0)),
        )
        self._w01, self._w11, self._w21, self._w31 = (
            float(w.getCell(0, 1)),
            float(w.getCell(1, 1)),
            float(w.getCell(2, 1)),
            float(w.getCell(3, 1)),
        )
        self._w02, self._w12, self._w22, self._w32 = (
            float(w.getCell(0, 2)),
            float(w.getCell(1, 2)),
            float(w.getCell(2, 2)),
            float(w.getCell(3, 2)),
        )

    def _cachear_matriz_local(self) -> None:
        """Extrai células da matriz modelo->local para projeção rápida."""
        m = self.to_local
        self._l00, self._l10, self._l20, self._l30 = (
            float(m.getCell(0, 0)),
            float(m.getCell(1, 0)),
            float(m.getCell(2, 0)),
            float(m.getCell(3, 0)),
        )
        self._l01, self._l11, self._l21, self._l31 = (
            float(m.getCell(0, 1)),
            float(m.getCell(1, 1)),
            float(m.getCell(2, 1)),
            float(m.getCell(3, 1)),
        )
        self._l02, self._l12, self._l22, self._l32 = (
            float(m.getCell(0, 2)),
            float(m.getCell(1, 2)),
            float(m.getCell(2, 2)),
            float(m.getCell(3, 2)),
        )

    def _atualizar_bounds_modelo(
        self, cx: float, cy: float, cz: float, hx: float, hy: float, hz: float
    ) -> None:
        """Calcula a AABB da caixa orientada no espaço do modelo."""
        wcx = cx * self._w00 + cy * self._w10 + cz * self._w20 + self._w30
        wcy = cx * self._w01 + cy * self._w11 + cz * self._w21 + self._w31
        wcz = cx * self._w02 + cy * self._w12 + cz * self._w22 + self._w32
        whx = abs(self._w00 * hx) + abs(self._w10 * hy) + abs(self._w20 * hz)
        why = abs(self._w01 * hx) + abs(self._w11 * hy) + abs(self._w21 * hz)
        whz = abs(self._w02 * hx) + abs(self._w12 * hy) + abs(self._w22 * hz)

        ml0, ml1, ml2 = wcx - whx, wcy - why, wcz - whz
        mh0, mh1, mh2 = wcx + whx, wcy + why, wcz + whz
        self._ml0, self._ml1, self._ml2 = ml0, ml1, ml2
        self._mh0, self._mh1, self._mh2 = mh0, mh1, mh2
        self.model_low = Vec3(ml0, ml1, ml2)
        self.model_high = Vec3(mh0, mh1, mh2)

    def __post_init__(self):
        """Normaliza os limites da caixa."""
        lx0, ly0, lz0 = float(self.low[0]), float(self.low[1]), float(self.low[2])
        lx1, ly1, lz1 = float(self.high[0]), float(self.high[1]), float(self.high[2])
        self._lx0, self._ly0, self._lz0 = lx0, ly0, lz0
        self._lx1, self._ly1, self._lz1 = lx1, ly1, lz1

        self._cachear_matriz_modelo()
        self._cachear_matriz_local()
        self._atualizar_bounds_modelo(
            (lx0 + lx1) * 0.5,
            (ly0 + ly1) * 0.5,
            (lz0 + lz1) * 0.5,
            (lx1 - lx0) * 0.5,
            (ly1 - ly0) * 0.5,
            (lz1 - lz0) * 0.5,
        )

    def distance(self, point) -> float:
        """Calcula a distância do ponto à caixa."""
        local = self.to_local.xformPoint(Point3(point))
        delta = Vec3(
            *(max(self.low[k] - local[k], 0, local[k] - self.high[k]) for k in range(3))
        )
        if delta.lengthSquared() > 0:
            return delta.length()
        return -min(
            min(local[k] - self.low[k], self.high[k] - local[k]) for k in range(3)
        )

    def _empurrar_face_mais_proxima(
        self, lx: float, ly: float, lz: float, clearance: float
    ) -> tuple[float, float, float]:
        """Empurra ponto já interno à caixa pela face local mais próxima."""
        d_best = lx - self._lx0
        axis, sign = 0, -1.0
        for cand_axis, cand_sign, d in (
            (0, 1.0, self._lx1 - lx),
            (1, -1.0, ly - self._ly0),
            (1, 1.0, self._ly1 - ly),
            (2, -1.0, lz - self._lz0),
            (2, 1.0, self._lz1 - lz),
        ):
            if d < d_best:
                d_best, axis, sign = d, cand_axis, cand_sign
        coords = [lx, ly, lz]
        limites = ((self._lx0, self._lx1), (self._ly0, self._ly1), (self._lz0, self._lz1))
        coords[axis] = (limites[axis][0] if sign < 0.0 else limites[axis][1]) + sign * clearance
        return (coords[0], coords[1], coords[2])

    def project_xyz(
        self, px: float, py: float, pz: float, radius: float
    ) -> tuple[float, float, float] | None:
        """Empurra coordenadas (px, py, pz) para fora da caixa; retorna None se sem contato."""
        clearance = radius + 0.002
        if (
            px < self._ml0 - clearance
            or px > self._mh0 + clearance
            or py < self._ml1 - clearance
            or py > self._mh1 + clearance
            or pz < self._ml2 - clearance
            or pz > self._mh2 + clearance
        ):
            return None
        lx = px * self._l00 + py * self._l10 + pz * self._l20 + self._l30
        ly = px * self._l01 + py * self._l11 + pz * self._l21 + self._l31
        lz = px * self._l02 + py * self._l12 + pz * self._l22 + self._l32
        nx = self._lx0 if lx < self._lx0 else (self._lx1 if lx > self._lx1 else lx)
        ny = self._ly0 if ly < self._ly0 else (self._ly1 if ly > self._ly1 else ly)
        nz = self._lz0 if lz < self._lz0 else (self._lz1 if lz > self._lz1 else lz)
        dx, dy, dz = lx - nx, ly - ny, lz - nz
        distance_squared = dx * dx + dy * dy + dz * dz
        if distance_squared >= clearance * clearance:
            return None
        if distance_squared > 1e-12:
            inv = clearance / math.sqrt(distance_squared)
            cx, cy, cz = nx + dx * inv, ny + dy * inv, nz + dz * inv
        else:
            cx, cy, cz = self._empurrar_face_mais_proxima(lx, ly, lz, clearance)
        return (
            cx * self._w00 + cy * self._w10 + cz * self._w20 + self._w30,
            cx * self._w01 + cy * self._w11 + cz * self._w21 + self._w31,
            cx * self._w02 + cy * self._w12 + cz * self._w22 + self._w32,
        )

    def project(self, point, radius):
        """Empurra o ponto para fora da caixa, respeitando o raio."""
        res = self.project_xyz(point[0], point[1], point[2], radius)
        if res is None:
            return point
        return Vec3(res[0], res[1], res[2])


class TentacleContacts:
    """Project swept spheres; oriented boxes follow the model's animated nodes."""

    def __init__(self):
        """Inicia sem obstáculos."""
        self.boxes: list[ObstacleBox] = []
        self.contacts = 0

    def project(self, point, radius, boxes=None):
        """Empurra o ponto para fora de todos os obstáculos."""
        px, py, pz = float(point[0]), float(point[1]), float(point[2])
        moved = False
        for box in self.boxes if boxes is None else boxes:
            res = box.project_xyz(px, py, pz, radius)
            if res is not None:
                self.contacts += 1
                px, py, pz = res
                moved = True
        return Vec3(px, py, pz) if moved else Vec3(point)

    def region(self, points, margin=0.1):
        """Devolve a região que envolve os pontos com a margem dada."""
        if not points:
            return []
        min_x = max_x = points[0][0]
        min_y = max_y = points[0][1]
        min_z = max_z = points[0][2]
        for p in points[1:]:
            px, py, pz = p[0], p[1], p[2]
            if px < min_x:
                min_x = px
            elif px > max_x:
                max_x = px
            if py < min_y:
                min_y = py
            elif py > max_y:
                max_y = py
            if pz < min_z:
                min_z = pz
            elif pz > max_z:
                max_z = pz
        min_x -= margin
        min_y -= margin
        min_z -= margin
        max_x += margin
        max_y += margin
        max_z += margin
        return [
            box
            for box in self.boxes
            if box._ml0 <= max_x
            and box._mh0 >= min_x
            and box._ml1 <= max_y
            and box._mh1 >= min_y
            and box._ml2 <= max_z
            and box._mh2 >= min_z
        ]

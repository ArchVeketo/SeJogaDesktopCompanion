"""Finite oriented collision volumes for the procedural tentacle chain."""
from dataclasses import dataclass
import math

from panda3d.core import Mat4, Point3, Vec3


@dataclass
class ObstacleBox:
    name: str
    low: Vec3
    high: Vec3
    to_local: Mat4
    to_model: Mat4

    def __post_init__(self):
        center = (self.low + self.high) * .5
        half = (self.high - self.low) * .5
        world_center = self.to_model.xformPoint(Point3(center))
        axes = [self.to_model.xformVec(Vec3(half.x, 0, 0)),
                self.to_model.xformVec(Vec3(0, half.y, 0)),
                self.to_model.xformVec(Vec3(0, 0, half.z))]
        world_half = Vec3(*(sum(abs(axis[k]) for axis in axes) for k in range(3)))
        self.model_low = world_center - world_half
        self.model_high = world_center + world_half

    def distance(self, point) -> float:
        local = self.to_local.xformPoint(Point3(point))
        delta = Vec3(*(max(self.low[k] - local[k], 0, local[k] - self.high[k]) for k in range(3)))
        if delta.lengthSquared() > 0:
            return delta.length()
        return -min(min(local[k] - self.low[k], self.high[k] - local[k]) for k in range(3))

    def project(self, point, radius):
        margin = radius + .002
        low, high = self.model_low, self.model_high
        if (point.x < low.x - margin or point.x > high.x + margin or
                point.y < low.y - margin or point.y > high.y + margin or
                point.z < low.z - margin or point.z > high.z + margin):
            return point
        local = self.to_local.xformPoint(Point3(point))
        nearest = Vec3(*(max(self.low[k], min(self.high[k], local[k])) for k in range(3)))
        delta = local - nearest
        distance_squared = delta.lengthSquared()
        clearance = radius + .002
        if distance_squared >= clearance * clearance:
            return Vec3(point)
        if distance_squared > 1e-12:
            corrected = nearest + delta * (clearance / math.sqrt(distance_squared))
        else:
            choices = [(local[k] - self.low[k], k, -1) for k in range(3)]
            choices += [(self.high[k] - local[k], k, 1) for k in range(3)]
            _, axis, direction = min(choices)
            corrected = Vec3(local)
            corrected[axis] = (self.low[axis] if direction < 0 else self.high[axis]) + direction * clearance
        return Vec3(self.to_model.xformPoint(Point3(corrected)))


class TentacleContacts:
    """Project swept spheres; oriented boxes follow the model's animated nodes."""

    def __init__(self):
        self.boxes: list[ObstacleBox] = []
        self.contacts = 0

    def project(self, point, radius, boxes=None):
        current = Vec3(point)
        for box in self.boxes if boxes is None else boxes:
            projected = box.project(current, radius)
            if (projected - current).lengthSquared() > 1e-12:
                self.contacts += 1
                current = projected
        return current

    def region(self, points, margin=.1):
        low = [min(point[k] for point in points) - margin for k in range(3)]
        high = [max(point[k] for point in points) + margin for k in range(3)]
        return [box for box in self.boxes
                if all(box.model_low[k] <= high[k] and box.model_high[k] >= low[k] for k in range(3))]

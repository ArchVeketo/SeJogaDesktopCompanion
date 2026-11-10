"""Collision projection in animated, oriented model space."""
import pytest
from panda3d.core import Mat4, Point3, Vec3

from sejoga.tentaculos.restricoes_tentaculos import ObstacleBox, TentacleContacts


@pytest.mark.parametrize("angle", (0, 35, 85, 120))
def test_oriented_door_projection_preserves_radius(angle):
    transform = Mat4.rotateMat(angle, Vec3(0, 0, 1)) * Mat4.translateMat(.12, .16, .9)
    inverse = Mat4(transform)
    inverse.invertInPlace()
    box = ObstacleBox("door", Vec3(-.1, -.02, -.2), Vec3(.1, .02, .2), inverse, transform)
    for local in (Point3(0), Point3(.08, .015, .1), Point3(.105, 0, 0)):
        point = transform.xformPoint(local)
        corrected = box.project(point, .035)
        assert box.distance(corrected) >= .0369


def test_far_volumes_do_not_move_point_and_region_excludes_them():
    contacts = TentacleContacts()
    identity = Mat4.identMat()
    contacts.boxes = [ObstacleBox("body", Vec3(-1), Vec3(1), identity, identity)]
    point = Vec3(4, 0, 0)
    assert contacts.project(point, .1) == point
    assert contacts.region([point], .1) == []

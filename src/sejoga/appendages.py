"""Movimento volumétrico e articulação da porta, sem dependência do engine."""
import math


class AppendageMotion:
    def __init__(self):
        self.extension = 0.0
        self.previous_extension = 0.0

    def update(self, dt, door_degrees, actual_door=None):
        self.previous_extension = self.extension
        target = max(0.0, min(1.0, (door_degrees - 55.0) / 25.0))
        if actual_door is not None and target > self.extension:
            target = min(target, max(0.0, min(1.0, (actual_door - 35) / 40)))
        rate = 2.4 if target > self.extension else 2.0
        self.extension += (target-self.extension) * (1-math.exp(-rate*max(0, min(.1, dt))))
        if abs(target-self.extension) < .001:
            self.extension = target
        return self.extension


def tentacle_center(index, u, clock, extent):
    roots = [(.025, .065, .19), (-.035, .065, .085), (-.02, .065, .16), (.035, .065, .10)]
    directions = [(.70, .28), (-.48, -.38), (.45, .20), (-.35, -.25)]
    root = roots[index]
    x, z = directions[index]
    a = (root[0], root[1]+.14, root[2])
    b = (root[0]+x*.27, root[1]+.34, root[2]+z*.05)
    end = (root[0]+x*.23, root[1]+.29, root[2]+z*.23)
    v = 1-u
    point = [v**3*root[k]+3*v*v*u*a[k]+3*v*u*u*b[k]+u**3*end[k] for k in range(3)]
    point[0] += math.sin(clock*.85 + index*1.7 + u*3)*.027*u*u
    point[1] += math.sin(clock*.7 + index + u*4)*.025*u*u
    point[2] += math.sin(clock*.9 + index*2 + u*3.5)*.026*u*u
    return tuple(root[k] + (point[k]-root[k])*extent for k in range(3))


class DoorJoint:
    """Articulação com mola: contatos esféricos impedem fechamento sobre as malhas."""
    HINGE = (-.125, .15625, .1875)
    LOW = (.003, -.040, -.2344)
    HIGH = (.2482, 0.0, .1368)
    MAX_ANGLE = 135.0

    def __init__(self):
        self.angle = 0.0
        self.velocity = 0.0
        self.contacts = 0

    @classmethod
    def local_point(cls, point, angle):
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        x, y, z = (point[k]-cls.HINGE[k] for k in range(3))
        return (c*x+s*y, -s*x+c*y, z)

    @classmethod
    def distance(cls, point, angle):
        p = cls.local_point(point, angle)
        delta = [max(cls.LOW[k]-p[k], 0, p[k]-cls.HIGH[k]) for k in range(3)]
        if any(delta):
            return math.sqrt(sum(v*v for v in delta))
        return -min(min(p[k]-cls.LOW[k], cls.HIGH[k]-p[k]) for k in range(3))

    def update(self, dt, requested, spheres):
        remaining = max(0.0, min(.1, dt))
        target = max(0.0, min(self.MAX_ANGLE, requested))
        self.contacts = sum(self.distance(p, self.angle) < radius+.002 for p, radius in spheres)
        if self.contacts:
            # Contact changes the spring target, never teleports the leaf. Mesh
            # projection supplies clearance while the door catches up.
            for candidate in range(math.ceil(self.angle), 121, 5):
                if all(self.distance(p, candidate) >= radius+.002 for p, radius in spheres):
                    target = max(target, candidate)
                    break
        while remaining > 1e-8:
            step = min(remaining, 1/120)
            self.velocity += ((target-self.angle)*12 - self.velocity*7)*step
            self.velocity = max(-38, min(38, self.velocity))
            self.angle = max(0.0, min(self.MAX_ANGLE, self.angle+self.velocity*step))
            remaining -= step
        if self.angle < .15 and abs(self.velocity) < 1 and target == 0:
            self.angle = self.velocity = 0.0
        return self.angle

    def project(self, point, radius):
        """Afasta o centro da cápsula da caixa finita da porta quando necessário."""
        p = self.local_point(point, self.angle)
        nearest = [max(self.LOW[k], min(self.HIGH[k], p[k])) for k in range(3)]
        delta = [p[k]-nearest[k] for k in range(3)]
        distance = math.sqrt(sum(v*v for v in delta))
        if distance >= radius+.002:
            return point
        if distance > 1e-8:
            p = [nearest[k]+delta[k]/distance*(radius+.002) for k in range(3)]
        else:
            choices = [(p[k]-self.LOW[k], k, -1) for k in range(3)]
            choices += [(self.HIGH[k]-p[k], k, 1) for k in range(3)]
            _, axis, sign = min(choices)
            p = list(p)
            p[axis] = (self.LOW[axis] if sign < 0 else self.HIGH[axis]) + sign*(radius+.002)
        c, s = math.cos(math.radians(self.angle)), math.sin(math.radians(self.angle))
        return (self.HINGE[0]+c*p[0]-s*p[1], self.HINGE[1]+s*p[0]+c*p[1], self.HINGE[2]+p[2])


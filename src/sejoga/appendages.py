"""Movimento volumétrico e articulação da porta, sem dependência do engine."""
import math


class AppendageMotion:
    def __init__(self):
        self.extension = 0.0
        self.previous_extension = 0.0

    def update(self, dt, door_degrees, actual_door=None):
        self.previous_extension = self.extension
        target = max(0.0, min(1.0, (door_degrees - 10.0) / 60.0))
        if actual_door is not None and target > self.extension:
            target = min(target, max(0.0, min(1.0, (actual_door - 25) / 55)))
        rate = 2.8 if target > self.extension else 1.5
        distance = max(0.0, min(.1, dt)) * rate
        delta = target - self.extension
        self.extension += max(-distance, min(distance, delta))
        return self.extension


def tentacle_center(index, u, clock, extent):
    roots = [(-.057, .065, .235), (.057, .065, .235), (-.055, .065, .045), (.055, .065, .045)]
    directions = [(-.9, .65), (.85, .7), (-.85, -.18), (.7, -.8)]
    root = roots[index]
    x, z = directions[index]
    a = (root[0], root[1]+.14, root[2])
    b = (root[0]+x*.27, root[1]+.35, root[2]+z*.05)
    end = (root[0]+x*.23, root[1]+.26, root[2]+z*.25)
    v = 1-u
    point = [v**3*root[k]+3*v*v*u*a[k]+3*v*u*u*b[k]+u**3*end[k] for k in range(3)]
    point[0] += math.sin(clock*1.4 + index*1.7 + u*3)*.027*u*u
    point[1] += math.sin(clock*1.1 + index + u*4)*.025*u*u
    point[2] += math.sin(clock*1.7 + index*2 + u*3.5)*.026*u*u
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
        while remaining > 1e-8:
            step = min(remaining, 1/120)
            self.velocity += ((target-self.angle)*110 - self.velocity*21)*step
            self.angle = max(0.0, min(self.MAX_ANGLE, self.angle+self.velocity*step))
            remaining -= step
        self.contacts = sum(self.distance(p, self.angle) < radius+.002 for p, radius in spheres)
        if self.contacts:
            # Positional contact constraint: the tentacle pushes the hinged leaf
            # outward; closing resumes as its occupied volume retracts.
            candidate = self.angle
            while candidate < self.MAX_ANGLE:
                if all(self.distance(p, candidate) >= radius+.002 for p, radius in spheres):
                    break
                candidate += .75
            self.angle = min(self.MAX_ANGLE, candidate)
            self.velocity = max(0.0, self.velocity)
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


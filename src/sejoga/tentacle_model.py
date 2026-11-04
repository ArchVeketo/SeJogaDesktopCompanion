"""Modelo low poly de um tentáculo curto, grosso e com ventosas em relevo."""
import math


def build_tentacle():
    vertices, normals, colors, indices = [], [], [], []

    def triangle(a, b, c, color):
        u = [b[i]-a[i] for i in range(3)]
        v = [c[i]-a[i] for i in range(3)]
        normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        length = math.sqrt(sum(x*x for x in normal)) or 1
        normal = tuple(x/length for x in normal)
        start = len(vertices)
        vertices.extend((a, b, c))
        normals.extend([normal]*3)
        colors.extend([color]*3)
        indices.extend((start, start+1, start+2))

    def quad(a, b, c, d, color):
        triangle(a, b, c, color)
        triangle(a, c, d, color)

    # Coordinates are Z-up here; export converts to glTF Y-up.
    profile = [(0, .044, 0), (.075, .083, -.007), (.15, .071, -.006),
               (.23, .056, .005), (.31, .041, .025), (.39, .023, .056), (.48, .001, .10)]
    profile = [(z*.9, radius*1.15, bend*1.15) for z, radius, bend in profile]
    sides = 8
    rings = [[(bend + radius*math.cos(i*math.tau/sides-math.pi/8), radius*math.sin(i*math.tau/sides-math.pi/8), z)
              for i in range(sides)] for z, radius, bend in profile]
    for ring in range(len(rings)-1):
        for side in range(sides):
            j = (side+1)%sides
            color = [(.36, .09, .36, 1), (.48, .13, .40, 1), (.68, .17, .46, 1),
                     (.44, .10, .36, 1), (.27, .07, .32, 1), (.19, .055, .27, 1),
                     (.22, .06, .29, 1), (.28, .08, .34, 1)][side]
            quad(rings[ring][side], rings[ring][j], rings[ring+1][j], rings[ring+1][side], color)
    for side in range(sides):
        triangle((0, 0, 0), rings[0][(side+1)%sides], rings[0][side], (.20, .06, .27, 1))
    # Hexagonal suction cups project out of the front, with recessed dark centers.
    for z, body_radius, bend, radius in ((.09, .080, -.007, .026), (.18, .065, 0, .024),
                                            (.275, .047, .017, .020), (.355, .030, .042, .015)):
        z, body_radius, bend, radius = z*.9, body_radius*1.15, bend*1.15, radius*1.1
        y = body_radius*math.cos(math.pi/8)
        def circle(r, depth):
            return [(bend+r*math.cos(i*math.tau/6), y+depth, z+r*math.sin(i*math.tau/6)) for i in range(6)]
        back, lip, inner, hole = circle(radius, 0), circle(radius, .025), circle(radius*.58, .026), circle(radius*.45, .006)
        for side in range(6):
            j = (side+1)%6
            quad(back[side], lip[side], lip[j], back[j], (.72, .10, .43, 1))
            quad(lip[side], inner[side], inner[j], lip[j], (1, .25, .58, 1))
            quad(inner[side], hole[side], hole[j], inner[j], (.47, .045, .30, 1))
            triangle((bend, y+.006, z), hole[j], hole[side], (.12, .025, .19, 1))
    return vertices, normals, colors, indices

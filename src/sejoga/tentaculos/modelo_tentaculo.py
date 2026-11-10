"""Modelo low poly de um tentáculo curto, grosso e com ventosas em relevo."""

import math


def build_tentacle():  # noqa: PLR0915  # TODO convenção: fatiar render/tentáculos sem prova visual na GPU arrisca mudar pixels; lote próprio
    """Monta a geometria do tentáculo."""
    vertices, normals, colors, indices = [], [], [], []

    def triangle(a, b, c, color):
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        normal = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        length = math.sqrt(sum(x * x for x in normal)) or 1
        normal = tuple(x / length for x in normal)
        start = len(vertices)
        vertices.extend((a, b, c))
        normals.extend([normal] * 3)
        colors.extend([color] * 3)
        indices.extend((start, start + 1, start + 2))

    def quad(a, b, c, d, color):
        triangle(a, b, c, color)
        triangle(a, c, d, color)

    # Coordinates are Z-up here; export converts to glTF Y-up.
    profile = [
        (0, 0.044, 0),
        (0.075, 0.083, -0.007),
        (0.15, 0.071, -0.006),
        (0.23, 0.056, 0.005),
        (0.31, 0.041, 0.025),
        (0.39, 0.023, 0.056),
        (0.48, 0.001, 0.10),
    ]
    profile = [(z * 0.9, radius * 1.15, bend * 1.15) for z, radius, bend in profile]
    sides = 8
    rings = [
        [
            (
                bend + radius * math.cos(i * math.tau / sides - math.pi / 8),
                radius * math.sin(i * math.tau / sides - math.pi / 8),
                z,
            )
            for i in range(sides)
        ]
        for z, radius, bend in profile
    ]
    for ring in range(len(rings) - 1):
        for side in range(sides):
            j = (side + 1) % sides
            color = [
                (0.36, 0.09, 0.36, 1),
                (0.48, 0.13, 0.40, 1),
                (0.68, 0.17, 0.46, 1),
                (0.44, 0.10, 0.36, 1),
                (0.27, 0.07, 0.32, 1),
                (0.19, 0.055, 0.27, 1),
                (0.22, 0.06, 0.29, 1),
                (0.28, 0.08, 0.34, 1),
            ][side]
            quad(
                rings[ring][side],
                rings[ring][j],
                rings[ring + 1][j],
                rings[ring + 1][side],
                color,
            )
    for side in range(sides):
        triangle(
            (0, 0, 0),
            rings[0][(side + 1) % sides],
            rings[0][side],
            (0.20, 0.06, 0.27, 1),
        )
    # Hexagonal suction cups project out of the front, with recessed dark centers.
    for z, body_radius, bend, radius in (
        (0.09, 0.080, -0.007, 0.026),
        (0.18, 0.065, 0, 0.024),
        (0.275, 0.047, 0.017, 0.020),
        (0.355, 0.030, 0.042, 0.015),
    ):
        z, body_radius, bend, radius = (
            z * 0.9,
            body_radius * 1.15,
            bend * 1.15,
            radius * 1.1,
        )
        y = body_radius * math.cos(math.pi / 8)

        def circle(r, depth, bend=bend, y=y, z=z):
            return [
                (
                    bend + r * math.cos(i * math.tau / 6),
                    y + depth,
                    z + r * math.sin(i * math.tau / 6),
                )
                for i in range(6)
            ]

        back, lip, inner, hole = (
            circle(radius, 0),
            circle(radius, 0.025),
            circle(radius * 0.58, 0.026),
            circle(radius * 0.45, 0.006),
        )
        for side in range(6):
            j = (side + 1) % 6
            quad(back[side], lip[side], lip[j], back[j], (0.72, 0.10, 0.43, 1))
            quad(lip[side], inner[side], inner[j], lip[j], (1, 0.25, 0.58, 1))
            quad(inner[side], hole[side], hole[j], inner[j], (0.47, 0.045, 0.30, 1))
            triangle((bend, y + 0.006, z), hole[j], hole[side], (0.12, 0.025, 0.19, 1))
    return vertices, normals, colors, indices

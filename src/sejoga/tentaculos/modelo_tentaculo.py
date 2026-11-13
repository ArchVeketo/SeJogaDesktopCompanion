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


_PERFIS_TENTACULO = {
    "musculoso": [
        (0.0, 0.056, 0.0),
        (0.075, 0.098, -0.008),
        (0.16, 0.084, -0.004),
        (0.25, 0.064, 0.008),
        (0.35, 0.044, 0.028),
        (0.45, 0.025, 0.058),
        (0.54, 0.002, 0.095),
    ],
    "chicote_longo": [
        (0.0, 0.052, 0.0),
        (0.09, 0.082, -0.006),
        (0.20, 0.062, 0.002),
        (0.32, 0.068, 0.012),
        (0.45, 0.044, 0.032),
        (0.58, 0.024, 0.064),
        (0.72, 0.003, 0.115),
    ],
    "clava_lula": [
        (0.0, 0.048, 0.0),
        (0.085, 0.074, -0.006),
        (0.22, 0.048, 0.004),
        (0.38, 0.036, 0.022),
        (0.50, 0.058, 0.050),
        (0.59, 0.034, 0.082),
        (0.67, 0.002, 0.118),
    ],
    "espinhoso_abissal": [
        (0.0, 0.054, 0.0),
        (0.08, 0.088, -0.008),
        (0.18, 0.074, 0.0),
        (0.30, 0.058, 0.014),
        (0.42, 0.042, 0.036),
        (0.54, 0.024, 0.068),
        (0.64, 0.002, 0.108),
    ],
}

_PALETA_TENTACULO = (
    (0.36, 0.09, 0.36, 1),
    (0.48, 0.13, 0.40, 1),
    (0.68, 0.17, 0.46, 1),
    (0.44, 0.10, 0.36, 1),
    (0.27, 0.07, 0.32, 1),
    (0.19, 0.055, 0.27, 1),
    (0.22, 0.06, 0.29, 1),
    (0.28, 0.08, 0.34, 1),
)


def _construir_malha_perfil(base_profile, variante: str):
    vertices: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    colors: list[tuple[float, float, float, float]] = []
    indices: list[int] = []

    def triangle(a, b, c, color):
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        normal = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        length = math.sqrt(sum(x * x for x in normal)) or 1.0
        normal = (normal[0] / length, normal[1] / length, normal[2] / length)
        start = len(vertices)
        vertices.extend((a, b, c))
        normals.extend((normal, normal, normal))
        colors.extend((color, color, color))
        indices.extend((start, start + 1, start + 2))

    def quad(a, b, c, d, color):
        triangle(a, b, c, color)
        triangle(a, c, d, color)

    profile = [(z * 0.9, r * 1.12, bend * 1.12) for z, r, bend in base_profile]
    sides = 8
    rings = [
        [
            (
                bend + radius * (1.24 if (variante == "espinhoso_abissal" and ring_idx in (1, 3) and i in (4, 5)) else 1.0) * math.cos(i * math.tau / sides - math.pi / 8),
                radius * (1.24 if (variante == "espinhoso_abissal" and ring_idx in (1, 3) and i in (4, 5)) else 1.0) * math.sin(i * math.tau / sides - math.pi / 8),
                z,
            )
            for i in range(sides)
        ]
        for ring_idx, (z, radius, bend) in enumerate(profile)
    ]
    for ring in range(len(rings) - 1):
        for side in range(sides):
            j = (side + 1) % sides
            quad(rings[ring][side], rings[ring][j], rings[ring + 1][j], rings[ring + 1][side], _PALETA_TENTACULO[side])
    for side in range(sides):
        triangle((0, 0, 0), rings[0][(side + 1) % sides], rings[0][side], (0.20, 0.06, 0.27, 1))
    _emitir_ventosas_perfil(profile, triangle, quad)
    return vertices, normals, colors, indices


def _emitir_ventosas_perfil(profile, triangle, quad) -> None:
    for z, body_radius, bend in profile[1:-1]:
        radius = max(0.012, body_radius * 0.33)
        y = body_radius * math.cos(math.pi / 8)
        rings = [
            [(bend + r * math.cos(i * math.tau / 6), y + d, z + r * math.sin(i * math.tau / 6)) for i in range(6)]
            for r, d in ((radius, 0.0), (radius, 0.025), (radius * 0.58, 0.026), (radius * 0.45, 0.006))
        ]
        back, lip, inner, hole = rings
        for side in range(6):
            j = (side + 1) % 6
            quad(back[side], lip[side], lip[j], back[j], (0.72, 0.10, 0.43, 1))
            quad(lip[side], inner[side], inner[j], lip[j], (1, 0.25, 0.58, 1))
            quad(inner[side], hole[side], hole[j], inner[j], (0.47, 0.045, 0.30, 1))
            triangle((bend, y + 0.006, z), hole[j], hole[side], (0.12, 0.025, 0.19, 1))


def build_tentacle_variant(variante: str = "padrao"):
    """Constrói variações anatômicas de tentáculo (base forte, chicote, clava ou espinhoso)."""
    if variante == "padrao":
        return build_tentacle()
    base_profile = _PERFIS_TENTACULO.get(variante, _PERFIS_TENTACULO["musculoso"])
    return _construir_malha_perfil(base_profile, variante)

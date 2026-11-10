"""Movimento volumétrico e articulação da porta, sem dependência do engine."""

import math

# --------------------------------------------------------------------------- #
# Calibração do movimento volumétrico da extensão dos apêndices pela porta.
# Valores IDÊNTICOS aos de antes, extraídos da lógica (destino 2: const. módulo).
# --------------------------------------------------------------------------- #
#: dt máximo por quadro (clamp anti-salto).
EXT_DT_MAXIMO = 0.1
#: Faixa de abertura da porta (graus) que mapeia para extensão 0..1.
EXT_PORTA_INICIO = 55.0
EXT_PORTA_FAIXA = 25.0
#: Limite pela porta real medida (graus) quando disponível.
EXT_PORTA_REAL_INICIO = 35.0
EXT_PORTA_REAL_FAIXA = 40.0
#: Taxa de suavização ao abrir e ao fechar.
EXT_TAXA_ABRINDO = 2.4
EXT_TAXA_FECHANDO = 2.0
#: Abaixo deste erro, assenta no alvo exato.
EXT_EPSILON = 0.001


class AppendageMotion:
    """Movimento dos apêndices que acompanham a abertura da porta."""

    def __init__(self):
        """Inicia os apêndices em repouso."""
        self.extension = 0.0
        self.previous_extension = 0.0

    def update(self, dt, door_degrees, actual_door=None):
        """Avança os apêndices um passo seguindo o ângulo da porta."""
        self.previous_extension = self.extension
        target = max(0.0, min(1.0, (door_degrees - EXT_PORTA_INICIO) / EXT_PORTA_FAIXA))
        if actual_door is not None and target > self.extension:
            target = min(
                target,
                max(
                    0.0,
                    min(
                        1.0,
                        (actual_door - EXT_PORTA_REAL_INICIO) / EXT_PORTA_REAL_FAIXA,
                    ),
                ),
            )
        rate = EXT_TAXA_ABRINDO if target > self.extension else EXT_TAXA_FECHANDO
        self.extension += (target - self.extension) * (
            1 - math.exp(-rate * max(0, min(EXT_DT_MAXIMO, dt)))
        )
        if abs(target - self.extension) < EXT_EPSILON:
            self.extension = target
        return self.extension


def tentacle_center(index, u, clock, extent):
    """Calcula o centro do tentáculo ``index`` na posição ``u`` da curva."""
    roots = [
        (0.025, 0.065, 0.19),
        (-0.035, 0.065, 0.085),
        (-0.02, 0.065, 0.16),
        (0.035, 0.065, 0.10),
    ]
    directions = [(0.70, 0.28), (-0.48, -0.38), (0.45, 0.20), (-0.35, -0.25)]
    root = roots[index]
    x, z = directions[index]
    a = (root[0], root[1] + 0.14, root[2])
    b = (root[0] + x * 0.27, root[1] + 0.34, root[2] + z * 0.05)
    end = (root[0] + x * 0.23, root[1] + 0.29, root[2] + z * 0.23)
    v = 1 - u
    point = [
        v**3 * root[k] + 3 * v * v * u * a[k] + 3 * v * u * u * b[k] + u**3 * end[k]
        for k in range(3)
    ]
    point[0] += math.sin(clock * 0.85 + index * 1.7 + u * 3) * 0.027 * u * u
    point[1] += math.sin(clock * 0.7 + index + u * 4) * 0.025 * u * u
    point[2] += math.sin(clock * 0.9 + index * 2 + u * 3.5) * 0.026 * u * u
    return tuple(root[k] + (point[k] - root[k]) * extent for k in range(3))


class DoorJoint:
    """Articulação com mola: contatos esféricos impedem fechamento sobre as malhas."""

    HINGE = (-0.125, 0.15625, 0.1875)
    LOW = (0.003, -0.040, -0.2344)
    HIGH = (0.2482, 0.0, 0.1368)
    MAX_ANGLE = 135.0
    # Mola da dobradiça: rigidez, atrito e teto de velocidade angular.
    RIGIDEZ = 12.0
    ATRITO = 7.0
    VELOCIDADE_MAXIMA = 38.0
    # Substep fixo da integração (independe do framerate) e dt máximo.
    SUBSTEP = 1 / 120
    DT_MAXIMO = 0.1
    # Folga de contato das cápsulas contra a caixa da porta.
    FOLGA_CONTATO = 0.002
    # Varredura de desvio por contato: passo e teto do ângulo candidato.
    VARREDURA_PASSO = 5
    VARREDURA_TETO = 121
    # Assentamento: abaixo destes limiares, trava em repouso.
    ASSENTA_ANGULO = 0.15
    ASSENTA_VELOCIDADE = 1.0

    def __init__(self):
        """Inicia a porta fechada e parada."""
        self.angle = 0.0
        self.velocity = 0.0
        self.contacts = 0

    @classmethod
    def local_point(cls, point, angle):
        """Leva o ponto para o referencial local da porta no ângulo dado."""
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        x, y, z = (point[k] - cls.HINGE[k] for k in range(3))
        return (c * x + s * y, -s * x + c * y, z)

    @classmethod
    def distance(cls, point, angle):
        """Calcula a distância do ponto à folha da porta no ângulo dado."""
        p = cls.local_point(point, angle)
        delta = [max(cls.LOW[k] - p[k], 0, p[k] - cls.HIGH[k]) for k in range(3)]
        if any(delta):
            return math.sqrt(sum(v * v for v in delta))
        return -min(min(p[k] - cls.LOW[k], cls.HIGH[k] - p[k]) for k in range(3))

    def update(self, dt, requested, spheres):
        """Avança a porta rumo ao ângulo pedido sem atravessar as esferas."""
        remaining = max(0.0, min(self.DT_MAXIMO, dt))
        target = max(0.0, min(self.MAX_ANGLE, requested))
        self.contacts = sum(
            self.distance(p, self.angle) < radius + self.FOLGA_CONTATO
            for p, radius in spheres
        )
        if self.contacts:
            # Contact changes the spring target, never teleports the leaf. Mesh
            # projection supplies clearance while the door catches up.
            for candidate in range(
                math.ceil(self.angle), self.VARREDURA_TETO, self.VARREDURA_PASSO
            ):
                if all(
                    self.distance(p, candidate) >= radius + self.FOLGA_CONTATO
                    for p, radius in spheres
                ):
                    target = max(target, candidate)
                    break
        while remaining > 1e-8:
            step = min(remaining, self.SUBSTEP)
            self.velocity += (
                (target - self.angle) * self.RIGIDEZ - self.velocity * self.ATRITO
            ) * step
            self.velocity = max(
                -self.VELOCIDADE_MAXIMA, min(self.VELOCIDADE_MAXIMA, self.velocity)
            )
            self.angle = max(
                0.0, min(self.MAX_ANGLE, self.angle + self.velocity * step)
            )
            remaining -= step
        if (
            self.angle < self.ASSENTA_ANGULO
            and abs(self.velocity) < self.ASSENTA_VELOCIDADE
            and target == 0
        ):
            self.angle = self.velocity = 0.0
        return self.angle

    def project(self, point, radius):
        """Afasta o centro da cápsula da caixa finita da porta quando necessário."""
        p = self.local_point(point, self.angle)
        nearest = [max(self.LOW[k], min(self.HIGH[k], p[k])) for k in range(3)]
        delta = [p[k] - nearest[k] for k in range(3)]
        distance = math.sqrt(sum(v * v for v in delta))
        if distance >= radius + self.FOLGA_CONTATO:
            return point
        if distance > 1e-8:
            p = [
                nearest[k] + delta[k] / distance * (radius + self.FOLGA_CONTATO)
                for k in range(3)
            ]
        else:
            choices = [(p[k] - self.LOW[k], k, -1) for k in range(3)]
            choices += [(self.HIGH[k] - p[k], k, 1) for k in range(3)]
            _, axis, sign = min(choices)
            p = list(p)
            p[axis] = (self.LOW[axis] if sign < 0 else self.HIGH[axis]) + sign * (
                radius + self.FOLGA_CONTATO
            )
        c, s = math.cos(math.radians(self.angle)), math.sin(math.radians(self.angle))
        return (
            self.HINGE[0] + c * p[0] - s * p[1],
            self.HINGE[1] + s * p[0] + c * p[1],
            self.HINGE[2] + p[2],
        )

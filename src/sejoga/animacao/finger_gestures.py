"""Escreve nos pivôs da cadeia dos dedos (ver ``render.dedos_malha``) a cada quadro.

Os ângulos vêm de ``dedos_cascata`` (lógica pura): giro do bloco ``fingers`` +
gesto + movimento secundário, repartidos entre as juntas base, meio e ponta. O
asset segue intacto; o contorno recebe os mesmos ângulos nos pivôs copiados.
"""

from math import exp

from sejoga.animacao import dedos_cascata as cascata
from sejoga.animacao import dedos_tuning as T
from sejoga.render.dedos_malha import girar_pivo, pivos_da_cadeia

GESTURES = {
    'hang_loose': (0, 75, 75, 75, 0),
    'thumbs_up': (0, 80, 80, 80, 80),
    'rock': (65, 0, 80, 80, 0),
    'finger_gun': (0, 0, 80, 80, 80),
}
#: (lado, grupo do bloco dos dedos, malhas polegar..mindinho). Gestos só na mão direita.
MAOS = (
    (1, 'fingers', T.MESH_DEDOS_DIREITA),
    (-1, 'fingers2', T.MESH_DEDOS_ESQUERDA),
)
LADO_DOS_GESTOS = 1


class FingerGestures:
    def __init__(self, renderer):
        self.renderer = renderer
        self.presentation = 0.0
        self.amounts = [0.0] * 5
        self.relogio = 0.0
        # cadeias[(lado, dedo)] = uma lista de pivôs por raiz (modelo e contorno).
        self.cadeias = {}
        self.angulos = {}

        for lado, _grupo, meshes in MAOS:
            for dedo, mesh in enumerate(meshes):
                self.cadeias[(lado, dedo)] = [
                    pivos_da_cadeia(raiz, mesh) for raiz in (renderer.model_np, renderer.outline_np)
                ]
                self.angulos[(lado, dedo)] = [0.0] * cascata.numero_de_juntas(dedo)

    def _giro_do_bloco(self, lado, grupo):
        """Giro do nó do bloco (graus), positivo = fechando, para os dois lados."""
        no = self.renderer._rig_nodes.get(grupo)

        if no is None:
            return 0.0

        delta = no.getR() - self.renderer._rig_base_hpr[grupo][2]

        return lado * ((delta + 180.0) % 360.0 - 180.0)

    def update(self, dt, gesture):
        passo = max(0.0, min(T.PASSO_MAXIMO_S, dt))
        self.relogio += passo
        target = GESTURES.get(gesture, (0, 0, 0, 0, 0))
        blend = 1 - exp(-passo * 10)
        self.presentation += ((1.0 if gesture in GESTURES else 0.0) - self.presentation) * blend

        if self.presentation > .001:
            # Resolve the wrist in model space: elbow rotations must not turn
            # the palm edge-on to the fixed frontal camera.
            renderer = self.renderer
            hand = renderer._rig_nodes['hand']
            current = hand.getHpr(renderer.model_np)
            desired = (0, 180, 90 if gesture != 'finger_gun' else 0)
            values = [a + ((b - a + 180) % 360 - 180) * self.presentation
                      for a, b in zip(current, desired, strict=True)]
            hand.setHpr(renderer.model_np, *values)
            renderer._outline_nodes['hand'].setHpr(renderer.outline_np, *values)

        self.amounts = [a + (b - a) * blend for a, b in zip(self.amounts, target, strict=True)]

        for lado, grupo, _meshes in MAOS:
            bloco = self._giro_do_bloco(lado, grupo)

            for dedo in range(len(self.amounts)):
                gesto = self.amounts[dedo] if lado == LADO_DOS_GESTOS else 0.0
                alvo = cascata.angulos_juntas(dedo, lado, self.relogio, gesture, bloco, gesto)
                chave = (lado, dedo)
                self.angulos[chave] = cascata.suavizar(self.angulos[chave], alvo, passo)

                for pivos in self.cadeias[chave]:
                    for (pivo, eixo), angulo in zip(pivos, self.angulos[chave], strict=True):
                        girar_pivo(pivo, eixo, angulo)

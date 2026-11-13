"""Escreve nos pivôs da cadeia dos dedos (ver ``render.dedos_malha``) a cada quadro.

Os ângulos vêm de ``dedos_cascata`` (lógica pura): giro do bloco ``fingers`` +
gesto + movimento secundário, repartidos entre as juntas base, meio e ponta. O
asset segue intacto; o contorno recebe os mesmos ângulos nos pivôs copiados.
"""

from math import atan2, degrees, exp, sin

from sejoga.animacao import dedos_cascata as cascata
from sejoga.animacao import dedos_tuning as tuning_dedos
from sejoga.render.dedos_malha import (
    alinhar_pulso_polegar,
    eixo_abertura,
    girar_pivo,
    medir_direcao_polegar,
    pivos_da_cadeia,
)

GESTURES = {
    "hang_loose": (0, 75, 75, 75, 0),
    "thumbs_up": (0, 80, 80, 80, 80),
    "rock": (65, 0, 80, 80, 0),
    "finger_gun": (0, 0, 80, 80, 80),
    "peace": (42, 0, 0, 80, 80),
}
#: (lado, grupo do bloco dos dedos, malhas polegar..mindinho). Gestos só na mão direita.
MAOS = (
    (1, "fingers", tuning_dedos.MESH_DEDOS_DIREITA),
    (-1, "fingers2", tuning_dedos.MESH_DEDOS_ESQUERDA),
)
LADO_DOS_GESTOS = 1
PEGADAS = {
    "open_hands": -1.0,
    "close_fists": 1.0,
    "blue_balls": 1.0,
    "virtual_insanity": -0.86,
}


def _girar_cadeias(cadeias, angulos, abertura) -> None:
    for pivos in cadeias:
        for (pivo, eixo, normal), angulo in zip(pivos, angulos, strict=True):
            girar_pivo(pivo, eixo, angulo, abertura, normal)


def _aberturas_da_mao(raiz, cadeias):
    # O lado de cada dedo vem da base da malha em relação ao centro da mão.
    bases = [pivos[0][0].getPos(raiz) for pivos in cadeias[1:] if pivos]
    if not bases:
        return (0.0,) * len(cadeias)
    centro = sum(bases[1:], bases[0]) / len(bases)
    aberturas = []
    for dedo, pivos in enumerate(cadeias):
        if not pivos:
            aberturas.append(0.0)
            continue
        pivo, eixo, _normal = pivos[0]
        lateral = raiz.getRelativeVector(pivo, eixo)
        sinal = 1.0 if lateral.dot(pivo.getPos(raiz) - centro) >= 0 else -1.0
        aberturas.append(sinal * tuning_dedos.ABERTURA_MAXIMA_GRAUS[dedo])
    return aberturas


def _pegada_natural(estado, relogio, fase_danca, lado, dedo):
    if estado in PEGADAS:
        return PEGADAS[estado]
    atraso = lado * 0.9 + dedo * 0.17
    if estado in GESTURES and lado == LADO_DOS_GESTOS:
        if estado == "rock" and dedo == 0:
            return 0.55
        if estado == "peace" and dedo in (1, 2):
            # Indicador abre para fora e médio afasta para formar o V do peace sign.
            return -1.0 if dedo == 1 else -0.85
        if dedo == 0 or GESTURES[estado][dedo] == 0:
            return -0.65 if dedo == 0 else -0.35
        return 0.0
    if fase_danca is not None:
        # Alterna abertura e pegada ao longo de dois tempos, com atraso nos dedos.
        return 0.67 * sin(fase_danca * 0.5 - atraso)
    amplitude = {"idle": 0.24, "hover": 0.28, "wave": 0.5, "stretch": 0.45}.get(
        estado, 0.0
    )
    return amplitude * sin(relogio * 1.7 - atraso)


class FingerGestures:
    """Gestos dos dedos aplicados nos nós do renderer."""

    def __init__(self, renderer):
        """Localiza os nós dos dedos no renderer."""
        self.renderer = renderer
        self.presentation = 0.0
        self.wrist_twist = 0.0
        self.amounts = [0.0] * 5
        self.relogio = 0.0
        # cadeias[(lado, dedo)] = uma lista de pivôs por raiz (modelo e contorno).
        self.cadeias = {}
        self.angulos = {}
        self.aberturas = {}
        self._abertura_maxima = {}

        for lado, _grupo, meshes in MAOS:
            for dedo, mesh in enumerate(meshes):
                chave = lado, dedo
                self.cadeias[chave] = [
                    [
                        (pivo, eixo, eixo_abertura(pivo) if junta == 0 else None)
                        for junta, (pivo, eixo) in enumerate(
                            pivos_da_cadeia(raiz, mesh)
                        )
                    ]
                    for raiz in (renderer.model_np, renderer.outline_np)
                ]
                self.angulos[chave] = [0.0] * cascata.numero_de_juntas(dedo)
                self.aberturas[chave] = 0.0
            valores = _aberturas_da_mao(
                renderer.model_np,
                [self.cadeias[lado, dedo][0] for dedo in range(len(meshes))],
            )
            self._abertura_maxima.update(
                ((lado, dedo), abertura) for dedo, abertura in enumerate(valores)
            )
        self._thumb_local_dir = medir_direcao_polegar(renderer)

    def _giro_do_bloco(self, lado, grupo):
        """Giro do nó do bloco (graus), positivo = fechando, para os dois lados."""
        no = self.renderer._rig_nodes.get(grupo)

        if no is None:
            return 0.0

        delta = no.getR() - self.renderer._rig_base_hpr[grupo][2]

        return lado * ((delta + 180.0) % 360.0 - 180.0)

    def _alinhar_pulso(self, gesture, blend: float) -> None:
        renderer = self.renderer
        hand = renderer._rig_nodes["hand"]
        if gesture in ("thumbs_up", "finger_gun"):
            alinhar_pulso_polegar(
                hand, renderer.model_np, self._thumb_local_dir, self.presentation
            )
        else:
            frente = hand.getRelativeVector(renderer.model_np, (0, -1, 0))
            if frente.y * frente.y + frente.z * frente.z > 1e-5:
                giro = degrees(atan2(frente.y, -frente.z))
                delta = (giro - self.wrist_twist + 180.0) % 360.0 - 180.0
                self.wrist_twist += delta * blend
            hand.setP(hand, self.wrist_twist * self.presentation)
        renderer._outline_nodes["hand"].setMat(hand.getMat())

    def update(self, dt, gesture, *, fase_danca=None):
        """Avança o gesto de dedos um passo de ``dt``."""
        passo = max(0.0, min(tuning_dedos.PASSO_MAXIMO_S, dt))
        self.relogio += passo
        target = GESTURES.get(gesture, (0, 0, 0, 0, 0))
        blend = 1 - exp(-passo * 10)
        self.presentation += (
            (1.0 if gesture in GESTURES else 0.0) - self.presentation
        ) * blend

        if self.presentation > 0.001:
            self._alinhar_pulso(gesture, blend)
        else:
            self.wrist_twist = 0.0

        self.amounts = [
            a + (b - a) * blend for a, b in zip(self.amounts, target, strict=True)
        ]

        for lado, grupo, _meshes in MAOS:
            bloco = self._giro_do_bloco(lado, grupo)
            self._atualizar_mao(lado, bloco, gesture, fase_danca, passo, blend)

    def _atualizar_mao(self, lado, bloco, estado, fase_danca, passo, blend):
        for dedo, flexao in enumerate(self.amounts):
            gesto = flexao if lado == LADO_DOS_GESTOS else 0.0
            pegada = _pegada_natural(estado, self.relogio, fase_danca, lado, dedo)
            alvo = cascata.angulos_juntas(
                dedo, lado, self.relogio, estado, bloco, gesto, pegada=pegada
            )
            chave = lado, dedo
            self.angulos[chave] = cascata.suavizar(self.angulos[chave], alvo, passo)
            abertura_maxima = self._abertura_maxima[chave]
            if dedo == 0 and (pegada > 0 or gesto >= 50):
                # O polegar cruza o indicador e pousa sobre o punho.
                abertura_maxima = -tuning_dedos.OPOSICAO_POLEGAR_GRAUS * (
                    1 if abertura_maxima >= 0 else -1
                )
                abertura = abertura_maxima * max(pegada, min(1.0, gesto / 75.0))
            elif estado == "peace" and dedo == 2 and lado == LADO_DOS_GESTOS:
                # Afasta o dedo médio em direção oposta ao indicador para abrir o V.
                abertura = -10.5
            else:
                abertura = abertura_maxima * max(0.0, -pegada)
            self.aberturas[chave] += (abertura - self.aberturas[chave]) * blend
            _girar_cadeias(
                self.cadeias[chave], self.angulos[chave], self.aberturas[chave]
            )

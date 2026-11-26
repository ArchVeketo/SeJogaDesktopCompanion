"""Escreve nos pivôs da cadeia dos dedos (ver ``render.dedos_malha``) a cada quadro.

Os ângulos vêm de ``dedos_cascata`` (lógica pura): giro do bloco ``fingers`` +
gesto + movimento secundário, repartidos entre as juntas base, meio e ponta. O
asset segue intacto; o contorno recebe os mesmos ângulos nos pivôs copiados.
"""

from math import atan2, degrees, exp

from sejoga.animacao import gestos_dedos as cascata
from sejoga.animacao import gestos_dedos as tuning_dedos
from sejoga.animacao.gestos_dedos import (
    GESTURES,
    LADO_DOS_GESTOS,
    MAOS,
    PEGADAS,
    _pegada_natural,
    abertura_dedo,
    pegada_de_curl,
)
from sejoga.render.dedos_malha import (
    alinhar_pulso_polegar,
    eixo_abertura,
    girar_pivo,
    medir_direcao_polegar,
    pivos_da_cadeia,
)

_MAO_POR_LADO = {1: "hand", -1: "hand2"}
# Somente sinais mostrados ao observador podem girar o pulso da pose.
_SINAIS_DE_APRESENTACAO = frozenset({"hang_loose", "thumbs_up", "rock", "finger_gun", "peace", "point"})


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


def _resolver_gestos_por_mao(gesture, gesto_esquerda) -> dict[int, tuple[str | None, bool]]:
    """Devolve ``{lado: (estado_da_mao, executa_gesto)}`` para direita e esquerda."""
    if isinstance(gesture, dict):
        return {
            lado: (gesture.get(lado), gesture.get(lado) in GESTURES)
            for lado, _g, _m in MAOS
        }
    if isinstance(gesture, (tuple, list)) and len(gesture) == 2:
        g_dir, g_esq = gesture[0], gesture[1]
        return {
            1: (g_dir, g_dir in GESTURES),
            -1: (g_esq, g_esq in GESTURES),
        }
    estado_esq = gesto_esquerda if gesto_esquerda is not None else gesture
    if gesto_esquerda is not None:
        esq_gesto = gesto_esquerda in GESTURES
    elif gesture in PEGADAS or gesture not in GESTURES:
        esq_gesto = False
    else:
        esq_gesto = False
    return {
        LADO_DOS_GESTOS: (gesture, gesture in GESTURES),
        -LADO_DOS_GESTOS: (estado_esq, esq_gesto),
    }


class FingerGestures:
    """Gestos dos dedos aplicados nos nós do renderer, independentes por mão."""

    def __init__(self, renderer):
        """Localiza os nós dos dedos no renderer."""
        self.renderer = renderer
        self.presentation_por_mao = {lado: 0.0 for lado, _grupo, _m in MAOS}
        self.wrist_twist_por_mao = {lado: 0.0 for lado, _grupo, _m in MAOS}
        #: Flexão de gesto (graus) por dedo, separada por mão (1 direita, -1 esquerda).
        self.amounts_por_mao = {lado: [0.0] * 5 for lado, _grupo, _m in MAOS}
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
        self._thumb_dir_por_mao = {1: self._thumb_local_dir}
        try:
            self._thumb_dir_por_mao[-1] = medir_direcao_polegar(
                renderer,
                hand_name="hand2",
                thumb_mesh=tuning_dedos.MESH_DEDOS_ESQUERDA[0],
            )
        except ValueError:
            self._thumb_dir_por_mao[-1] = self._thumb_local_dir

    @property
    def presentation(self) -> float:
        """Apresentação do pulso da mão principal, mantida por compatibilidade."""
        return self.presentation_por_mao[LADO_DOS_GESTOS]

    @presentation.setter
    def presentation(self, valor: float) -> None:
        self.presentation_por_mao[LADO_DOS_GESTOS] = float(valor)

    @property
    def wrist_twist(self) -> float:
        """Torção de apresentação do pulso da mão principal."""
        return self.wrist_twist_por_mao[LADO_DOS_GESTOS]

    @wrist_twist.setter
    def wrist_twist(self, valor: float) -> None:
        self.wrist_twist_por_mao[LADO_DOS_GESTOS] = float(valor)

    @property
    def amounts(self):
        """Flexão de gesto da mão dos gestos (direita), mantida por compatibilidade."""
        return self.amounts_por_mao[LADO_DOS_GESTOS]

    @amounts.setter
    def amounts(self, valores):
        self.amounts_por_mao[LADO_DOS_GESTOS] = list(valores)

    def _giro_do_bloco(self, lado, grupo):
        """Giro do nó do bloco (graus), positivo = fechando, para os dois lados."""
        no = self.renderer._rig_nodes.get(grupo)

        if no is None:
            return 0.0

        delta = no.getR() - self.renderer._rig_base_hpr[grupo][2]
        # Cada dedo dobra na própria base; restaurar HPR completo impede torção lateral do bloco.
        no.setHpr(*self.renderer._rig_base_hpr[grupo])
        out_no = self.renderer._outline_nodes.get(grupo)
        if out_no is not None:
            out_no.setMat(no.getMat())
        return lado * ((delta + 180.0) % 360.0 - 180.0)

    def _alinhar_pulso(self, lado: int, hand_name: str, gesture, blend: float) -> None:
        renderer = self.renderer
        hand = renderer._rig_nodes.get(hand_name)
        if hand is None:
            return
        pres = self.presentation_por_mao[lado]
        if gesture in ("thumbs_up", "finger_gun"):
            alinhar_pulso_polegar(
                hand, renderer.model_np, self._thumb_dir_por_mao[lado], pres
            )
        else:
            frente = hand.getRelativeVector(renderer.model_np, (0, -1, 0))
            if frente.y * frente.y + frente.z * frente.z > 1e-5:
                giro = degrees(atan2(frente.y, -frente.z))
                delta = (giro - self.wrist_twist_por_mao[lado] + 180.0) % 360.0 - 180.0
                self.wrist_twist_por_mao[lado] += delta * blend
            hand.setP(hand, self.wrist_twist_por_mao[lado] * pres)
        out_hand = renderer._outline_nodes.get(hand_name)
        if out_hand is not None:
            out_hand.setMat(hand.getMat())

    def update(
        self,
        dt,
        gesture,
        *,
        fase_danca=None,
        dedos_clipe=None,
        gesto_esquerda=None,
    ):
        """Avança os gestos individuais de dedo das duas mãos um passo de ``dt``."""
        passo = max(0.0, min(tuning_dedos.PASSO_MAXIMO_S, dt))
        self.relogio += passo
        blend = 1 - exp(-passo * 10)
        por_mao = _resolver_gestos_por_mao(gesture, gesto_esquerda)

        for idx_mao, (lado, grupo, _meshes) in enumerate(MAOS):
            estado_mao, com_gesto = por_mao[lado]
            target = GESTURES.get(estado_mao, (0, 0, 0, 0, 0)) if com_gesto else (0, 0, 0, 0, 0)
            apresentar = com_gesto and estado_mao in _SINAIS_DE_APRESENTACAO
            if (com_gesto and not apresentar) or estado_mao in ("close_fists", "open_hands"):
                # O contato e a guarda têm orientação própria. Uma torção
                # residual do sinal anterior também deslocaria as pontas.
                self.presentation_por_mao[lado] = 0.0
                self.wrist_twist_por_mao[lado] = 0.0
            self.presentation_por_mao[lado] += (
                (1.0 if apresentar else 0.0) - self.presentation_por_mao[lado]
            ) * blend
            if self.presentation_por_mao[lado] > 0.001:
                if apresentar:
                    self._alinhar_pulso(lado, _MAO_POR_LADO[lado], estado_mao, blend)
                else:
                    self.wrist_twist_por_mao[lado] += (
                        0.0 - self.wrist_twist_por_mao[lado]
                    ) * blend
                    hand = self.renderer._rig_nodes.get(_MAO_POR_LADO[lado])
                    if hand is not None and abs(self.wrist_twist_por_mao[lado]) > 0.02:
                        hand.setP(
                            hand,
                            self.wrist_twist_por_mao[lado] * self.presentation_por_mao[lado],
                        )
                        out_hand = self.renderer._outline_nodes.get(_MAO_POR_LADO[lado])
                        if out_hand is not None:
                            out_hand.setMat(hand.getMat())
            else:
                self.wrist_twist_por_mao[lado] = 0.0
            self.amounts_por_mao[lado] = [
                a + (b - a) * blend
                for a, b in zip(self.amounts_por_mao[lado], target, strict=True)
            ]

            bloco = self._giro_do_bloco(lado, grupo)
            dedos_lado = dedos_clipe[idx_mao] if dedos_clipe is not None else None
            self._atualizar_mao(
                lado,
                bloco,
                estado_mao,
                fase_danca,
                passo,
                blend,
                com_gesto=com_gesto,
                dedos_lado=dedos_lado,
            )

    def _atualizar_mao(
        self,
        lado,
        bloco,
        estado,
        fase_danca,
        passo,
        blend,
        *,
        com_gesto: bool = False,
        dedos_lado=None,
    ):
        for dedo, flexao in enumerate(self.amounts_por_mao[lado]):
            gesto = flexao if com_gesto else 0.0
            if dedos_lado is not None and not com_gesto:
                pegada = pegada_de_curl(dedos_lado[dedo])
            else:
                pegada = _pegada_natural(
                    estado,
                    self.relogio,
                    fase_danca,
                    lado,
                    dedo,
                    com_gesto=com_gesto,
                )
            alvo = cascata.angulos_juntas(
                dedo, lado, self.relogio, estado, bloco, gesto, pegada=pegada
            )
            chave = lado, dedo
            self.angulos[chave] = cascata.suavizar(self.angulos[chave], alvo, passo)
            abertura = abertura_dedo(
                estado,
                dedo,
                lado,
                pegada,
                gesto,
                self._abertura_maxima[chave],
                com_gesto=com_gesto,
            )
            self.aberturas[chave] += (abertura - self.aberturas[chave]) * blend
            _girar_cadeias(
                self.cadeias[chave], self.angulos[chave], self.aberturas[chave]
            )

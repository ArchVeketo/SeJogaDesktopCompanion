"""Molas amortecidas por junta e cadeia de atraso, independentes do engine.

Reusa ``body_motion.Spring`` (solução analítica subamortecida) para manter a
resposta idêntica em 30/60/120 Hz. Cada junta ganha uma mola por eixo (x/y/z,
em graus) e a cadeia de atraso propaga o movimento do braço para o antebraço,
a mão e os dedos, deixando a ponta "arrastar" atrás da base como num ser vivo.
"""

from __future__ import annotations

from math import isfinite

from sejoga.animacao.movimento_corpo import Spring
from sejoga.animacao.mola_tuning import (
    CADEIA_AMORTECIMENTO,
    CADEIA_ATENUACAO,
    CADEIA_FREQUENCIA,
)
from sejoga.nucleo.esqueleto import Rotation3

# Cadeias ombro->antebraço->mão->dedos e o espelho do lado esquerdo.
CADEIA_DIREITA = ("right-arm", "ant-arm", "hand", "fingers")
CADEIA_ESQUERDA = ("left-arm", "ant-arm2", "hand2", "fingers2")


class JointSpring:
    """Três molas (x/y/z em graus) seguindo um alvo por junta."""

    def __init__(self, frequencia: float = 2.2, amortecimento: float = 0.72) -> None:
        self.x = Spring(frequencia, amortecimento)
        self.y = Spring(frequencia, amortecimento)
        self.z = Spring(frequencia, amortecimento)

    def atualizar(self, dt: float, alvo: Rotation3) -> Rotation3:
        """Avança as três molas em direção ao alvo e devolve a pose atual."""
        if not isfinite(dt) or dt <= 0:
            return self.valor()

        self.x.update(dt, alvo.x)
        self.y.update(dt, alvo.y)
        self.z.update(dt, alvo.z)

        return self.valor()

    def valor(self) -> Rotation3:
        return Rotation3(self.x.value, self.y.value, self.z.value)

    def definir(self, pose: Rotation3) -> None:
        """Reposiciona as molas sem velocidade, evitando saltos no crossfade."""
        self.x.value, self.x.velocity = pose.x, 0.0
        self.y.value, self.y.velocity = pose.y, 0.0
        self.z.value, self.z.velocity = pose.z, 0.0


class SpringPose:
    """Conjunto de molas por grupo, produzindo um dict grupo->Rotation3."""

    def __init__(
        self,
        frequencia: float = 2.2,
        amortecimento: float = 0.72,
        tensoes: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        self.frequencia = frequencia
        self.amortecimento = amortecimento
        # Tensão por junta (grupo -> (frequência, amortecimento)); juntas fora
        # do dict usam os defaults, preservando o comportamento atual.
        self.tensoes = tensoes or {}
        self.molas: dict[str, JointSpring] = {}

    def _mola(self, grupo: str) -> JointSpring:
        mola = self.molas.get(grupo)
        if mola is None:
            tensao = self.tensoes.get(grupo)
            if tensao is None:
                mola = JointSpring(self.frequencia, self.amortecimento)
            else:
                mola = JointSpring(tensao[0], tensao[1])
            self.molas[grupo] = mola
        return mola

    def atualizar(self, dt: float, alvos: dict[str, Rotation3]) -> dict[str, Rotation3]:
        """Segue cada alvo por junta e mantém as juntas sem alvo em repouso."""
        pose: dict[str, Rotation3] = {}
        for grupo, alvo in alvos.items():
            pose[grupo] = self._mola(grupo).atualizar(dt, alvo)
        return pose

    def definir(self, poses: dict[str, Rotation3]) -> None:
        for grupo, pose in poses.items():
            self._mola(grupo).definir(pose)

    def pose(self) -> dict[str, Rotation3]:
        return {grupo: mola.valor() for grupo, mola in self.molas.items()}


class LagChain:
    """Propaga o movimento com atraso crescente ao longo de uma cadeia.

    Cada elo persegue o PRÓPRIO alvo com uma mola progressivamente mais lenta
    (``atenuacao``), acumulando atraso da base para a ponta (braço -> antebraço
    -> mão -> dedos). Como usa ``Spring``, o atraso independe da taxa de quadros.

    Antes cada elo perseguia o ÂNGULO LOCAL do elo anterior: o antebraço
    exibido recebia os ângulos do ombro (juntas diferentes, eixos diferentes),
    e o cotovelo apontava para direções sem relação com o gesto.
    """

    def __init__(
        self,
        cadeia: tuple[str, ...] = CADEIA_DIREITA,
        frequencia: float = CADEIA_FREQUENCIA,
        amortecimento: float = CADEIA_AMORTECIMENTO,
        atenuacao: float = CADEIA_ATENUACAO,
    ) -> None:
        self.cadeia = cadeia
        self.elos: dict[str, JointSpring] = {}
        frequencia_elo = frequencia
        # Cada elo mais distante responde um pouco mais devagar, aumentando o
        # atraso perceptível da ponta em relação à base.
        for grupo in cadeia:
            self.elos[grupo] = JointSpring(frequencia_elo, amortecimento)
            frequencia_elo *= atenuacao

    def atualizar(self, dt: float, alvos: dict[str, Rotation3]) -> dict[str, Rotation3]:
        """Avança a cadeia; só os grupos conhecidos recebem atraso."""
        return {
            grupo: self.elos[grupo].atualizar(dt, alvos[grupo])
            for grupo in self.cadeia
            if grupo in alvos
        }

    def definir(self, poses: dict[str, Rotation3]) -> None:
        for grupo in self.cadeia:
            if grupo in poses:
                self.elos[grupo].definir(poses[grupo])

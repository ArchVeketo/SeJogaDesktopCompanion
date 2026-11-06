"""Camadas aditivas de animação e o mixer que as compõe por junta.

Cada camada contribui com uma rotação aditiva por junta (em graus), limitada a
uma máscara de grupos e escalada por um peso. O mixer soma as contribuições
sobre uma base, respeitando a ordem de prioridade (determinística). Referência
de prioridades: docs/GUIA_ANIMACOES_COMPANION.md seção 6 (referência, não
contrato rígido): base < locomoção < interação < música < física.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from sejoga.nucleo.rig import Rotation3

# Ordem de prioridade determinística das camadas conhecidas. Camadas com nome
# fora desta lista são aplicadas depois, na ordem em que chegam.
ORDEM_PRIORIDADE = ("base", "locomocao", "interacao", "musica", "fisica")

# Juntas controladas pela camada de música (dança). As pernas/pés ficam de
# fora: continuam vindo da base e do IK de lower_body.
MASCARA_MUSICA = frozenset({
    "head", "body", "right-arm", "left-arm", "ant-arm", "ant-arm2",
    "hand", "hand2", "fingers", "fingers2", "door",
})

# Juntas da camada de interação (follow-through da cadeia dos braços). Cobre as
# duas cadeias ombro->antebraço->mão->dedos; não toca cabeça/corpo/pernas, para
# não sobrescrever música e locomoção.
MASCARA_INTERACAO = frozenset({
    "right-arm", "left-arm", "ant-arm", "ant-arm2",
    "hand", "hand2", "fingers", "fingers2", "shoulder", "shoulder2",
})


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                   Prioridades e camadas delta (Fase 3)                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class Prioridade(IntEnum):
    """Ordem de aplicação das camadas (menor = primeiro)."""

    BASE = 0
    LOCOMOCAO = 10
    ESTADO = 20
    REACAO = 30
    MUSICA = 40
    FISICA = 50
    FOLLOW_THROUGH = 60


@dataclass
class CamadaDelta:
    """Delta aditivo por junta, com máscara e peso.

    Diferente de ``CamadaAnim``, que guarda contribuição absoluta, esta
    representa DELTAS sobre a pose base. Cada camada soma seu delta à pose
    acumulada, na ordem de prioridade.
    """

    nome: str
    prioridade: Prioridade
    delta: dict[str, Rotation3] = field(default_factory=dict)
    peso: float = 1.0
    mascara: frozenset[str] | None = None  # None = afeta tudo

    def aplicado(self, grupo: str, base: Rotation3) -> Rotation3:
        """Soma o delta à rotação base, respeitando máscara e peso."""
        if self.mascara is not None and grupo not in self.mascara:
            return base
        d = self.delta.get(grupo)
        if d is None or self.peso == 0.0:
            return base
        return Rotation3(
            base.x + d.x * self.peso,
            base.y + d.y * self.peso,
            base.z + d.z * self.peso,
        )


class LayerStack:
    """Gerencia e compõe camadas aditivas sobre a pose de repouso.

    Cada camada contribui um delta sobre a pose base (única fonte de verdade).
    A composição ocorre em ordem de prioridade: prioridades menores primeiro.
    """

    def __init__(self) -> None:
        from sejoga.animacao.rig_base import pose_repouso

        self._camadas: dict[str, CamadaDelta] = {}
        self._base = pose_repouso()

    def set_camada(self, camada: CamadaDelta) -> None:
        """Adiciona ou atualiza uma camada."""
        self._camadas[camada.nome] = camada

    def remove_camada(self, nome: str) -> None:
        """Remove uma camada (ex.: reação que terminou)."""
        self._camadas.pop(nome, None)

    def compor(self) -> dict[str, Rotation3]:
        """Compõe todas as camadas sobre a base, em ordem de prioridade.

        Returns
        -------
        Pose composta com todos os deltas aplicados sobre a base.
        """
        ordenadas = sorted(
            self._camadas.values(),
            key=lambda c: (c.prioridade, c.nome),
        )

        resultado = dict(self._base)
        for camada in ordenadas:
            for grupo in resultado:
                resultado[grupo] = camada.aplicado(grupo, resultado[grupo])

        return resultado


@dataclass
class CamadaAnim:
    """Contribuição aditiva por junta, com máscara de grupos e peso."""

    nome: str
    contribuicao: dict[str, Rotation3] = field(default_factory=dict)
    peso: float = 1.0
    mascara: frozenset[str] | None = None

    def afeta(self, grupo: str) -> bool:
        return self.mascara is None or grupo in self.mascara

    def aplicada(self, grupo: str) -> Rotation3 | None:
        """Rotação efetiva desta camada para o grupo, ou None se não afeta."""
        if not self.afeta(grupo):
            return None
        rotacao = self.contribuicao.get(grupo)
        if rotacao is None or self.peso == 0.0:
            return None
        if self.peso == 1.0:
            return rotacao
        return Rotation3(rotacao.x * self.peso, rotacao.y * self.peso, rotacao.z * self.peso)


class MixerCamadas:
    """Compõe camadas somando aditivamente por junta."""

    @staticmethod
    def _ordenar(camadas: list[CamadaAnim]) -> list[CamadaAnim]:
        def chave(item: tuple[int, CamadaAnim]) -> tuple[int, int]:
            indice, camada = item
            try:
                prioridade = ORDEM_PRIORIDADE.index(camada.nome)
            except ValueError:
                prioridade = len(ORDEM_PRIORIDADE)
            return (prioridade, indice)

        return [camada for _, camada in sorted(enumerate(camadas), key=chave)]

    @classmethod
    def compor(
        cls,
        camadas: list[CamadaAnim],
        base: dict[str, Rotation3] | None = None,
    ) -> dict[str, Rotation3]:
        """Soma as contribuições de cada camada sobre a base, por junta."""
        resultado: dict[str, Rotation3] = {
            grupo: Rotation3(rot.x, rot.y, rot.z) for grupo, rot in (base or {}).items()
        }
        for camada in cls._ordenar(list(camadas)):
            for grupo in camada.contribuicao:
                aplicada = camada.aplicada(grupo)
                if aplicada is None:
                    continue
                atual = resultado.get(grupo, Rotation3())
                resultado[grupo] = Rotation3(
                    atual.x + aplicada.x,
                    atual.y + aplicada.y,
                    atual.z + aplicada.z,
                )
        return resultado

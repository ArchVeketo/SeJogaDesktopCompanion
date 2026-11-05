"""Camadas aditivas de animação e o mixer que as compõe por junta.

Cada camada contribui com uma rotação aditiva por junta (em graus), limitada a
uma máscara de grupos e escalada por um peso. O mixer soma as contribuições
sobre uma base, respeitando a ordem de prioridade (determinística). Referência
de prioridades: docs/GUIA_ANIMACOES_COMPANION.md seção 6 (referência, não
contrato rígido): base < locomoção < interação < música < física.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rig import Rotation3

# Ordem de prioridade determinística das camadas conhecidas. Camadas com nome
# fora desta lista são aplicadas depois, na ordem em que chegam.
ORDEM_PRIORIDADE = ("base", "locomocao", "interacao", "musica", "fisica")


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

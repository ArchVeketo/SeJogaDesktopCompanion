"""Roteiros de estímulos, metrônomo/batidas e obstáculos para ensaio no editor.

Domínio puro (sem Panda3D, Qt ou Win32). Descreve eventos reproduzíveis no tempo
para o modo ``Em contexto`` e para o ensaio de reações, dança e tentáculos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TIPOS_ESTIMULO: tuple[str, ...] = (
    "click",
    "double_click",
    "hover",
    "pet",
    "poke",
    "surprise",
    "hit",
    "land",
    "drag_inicio",
    "drag_fim",
    "sneeze",
    "teimosia",
    "obstaculo",
    "porta",
    "cena",
)


@dataclass(frozen=True, slots=True)
class ObstaculoPrevia:
    """Caixa de obstáculo opcional na prévia 3D (colisão de tentáculos)."""

    ativo: bool = False
    centro: tuple[float, float, float] = (0.42, 0.25, 0.18)
    meia_extensao: tuple[float, float, float] = (0.14, 0.14, 0.18)


@dataclass(frozen=True, slots=True)
class EstimuloRoteiro:
    """Um estímulo pontual ou alteração de estado agendada no tempo da tomada."""

    tempo_s: float
    tipo: str
    alvo: str = "body"
    direcao: float = 0.0
    intensidade: float = 1.0
    dados: dict[str, Any] = field(default_factory=dict)

    @property
    def rotulo(self) -> str:
        """Etiqueta curta para exibição na timeline e inspetor."""
        nomes = {
            "click": "Clique",
            "double_click": "Duplo clique",
            "hover": "Hover",
            "pet": "Carinho",
            "poke": "Cutucada",
            "surprise": "Susto",
            "hit": "Impacto",
            "land": "Pouso",
            "drag_inicio": "Arraste",
            "drag_fim": "Soltura",
            "sneeze": "Espirro",
            "teimosia": "Teimosia",
            "obstaculo": "Obstáculo",
            "porta": "Porta",
            "cena": "Cena",
        }
        return nomes.get(self.tipo, self.tipo)


@dataclass(frozen=True, slots=True)
class RoteiroEnsaio:
    """Configuração de contexto reproduzível para ensaiar uma ação no editor."""

    estimulos: tuple[EstimuloRoteiro, ...] = ()
    bpm: float = 108.0
    metronomo_ativo: bool = False
    batidas_gravadas_s: tuple[float, ...] = ()
    usar_musica_ao_vivo: bool = False
    modo_sono: str = "em_pe"
    personalidade: str = "calm"
    obstaculo: ObstaculoPrevia = field(default_factory=ObstaculoPrevia)

    def ordenados(self) -> tuple[EstimuloRoteiro, ...]:
        """Estímulos ordenados pelo instante em segundos."""
        return tuple(sorted(self.estimulos, key=lambda e: e.tempo_s))

    def com_estimulo(self, estimulo: EstimuloRoteiro) -> RoteiroEnsaio:
        """Retorna novo roteiro adicionando ``estimulo`` ordenado no tempo."""
        lista = sorted([*self.estimulos, estimulo], key=lambda e: e.tempo_s)
        return RoteiroEnsaio(
            estimulos=tuple(lista),
            bpm=self.bpm,
            metronomo_ativo=self.metronomo_ativo,
            batidas_gravadas_s=self.batidas_gravadas_s,
            usar_musica_ao_vivo=self.usar_musica_ao_vivo,
            modo_sono=self.modo_sono,
            personalidade=self.personalidade,
            obstaculo=self.obstaculo,
        )

    def sem_indice(self, idx: int) -> RoteiroEnsaio:
        """Retorna novo roteiro removendo o estímulo no índice ordenado ``idx``."""
        atual = list(self.ordenados())
        if 0 <= idx < len(atual):
            atual.pop(idx)
        return RoteiroEnsaio(
            estimulos=tuple(atual),
            bpm=self.bpm,
            metronomo_ativo=self.metronomo_ativo,
            batidas_gravadas_s=self.batidas_gravadas_s,
            usar_musica_ao_vivo=self.usar_musica_ao_vivo,
            modo_sono=self.modo_sono,
            personalidade=self.personalidade,
            obstaculo=self.obstaculo,
        )


def roteiro_padrao_para_categoria(
    familia: str,
    chave_dados: str,
    *,
    bpm_inicial: float = 108.0,
) -> RoteiroEnsaio:
    """Cria o cenário reproduzível inicial para uma ação do catálogo."""
    if familia == "cenas_idle":
        return RoteiroEnsaio(
            estimulos=(
                EstimuloRoteiro(tempo_s=0.05, tipo="cena", dados={"nome": chave_dados}),
            ),
            personalidade="curious",
        )
    if familia == "tentaculos":
        pers = chave_dados.split(":")[-1] if ":" in chave_dados else "curious"
        return RoteiroEnsaio(
            estimulos=(
                EstimuloRoteiro(tempo_s=0.05, tipo="porta", intensidade=1.0),
            ),
            personalidade=pers if pers != "porta" and pers != "gotas" else "curious",
            obstaculo=ObstaculoPrevia(ativo=True),
        )
    if familia == "danca":
        step = 60.0 / max(40.0, bpm_inicial)
        batidas = tuple(round(i * step, 4) for i in range(16))
        return RoteiroEnsaio(
            bpm=bpm_inicial,
            metronomo_ativo=True,
            batidas_gravadas_s=batidas,
        )
    if familia == "reacoes":
        if chave_dados in ("aceno", "wave"):
            return RoteiroEnsaio(estimulos=(EstimuloRoteiro(tempo_s=0.1, tipo="click"),))
        if chave_dados in ("cutucar", "poke"):
            return RoteiroEnsaio(estimulos=(EstimuloRoteiro(tempo_s=0.15, tipo="poke"),))
        if chave_dados in ("surpresa", "surprise"):
            return RoteiroEnsaio(
                estimulos=(EstimuloRoteiro(tempo_s=0.15, tipo="surprise"),)
            )
    return RoteiroEnsaio()

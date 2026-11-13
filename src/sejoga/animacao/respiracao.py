"""Curva autoral de repouso e resposta respiratória a impulsos."""

from __future__ import annotations

from math import sin, tau

from sejoga.animacao.interpolacao import amostrar_pista
from sejoga.animacao.movimento_corpo import Spring, clamp

# A expiração ocupa a maior parte do ciclo.
_CICLO_REPOUSO = (
    (0.0, (-1.0, 0.0, 0.0)),
    (1.35, (1.0, 0.0, 0.0)),
    (3.6, (-1.0, 0.0, 0.0)),
)


def amostrar_respiracao_repouso(tempo: float) -> float:
    """Amostra um ciclo contínuo de inspiração e expiração, entre -1 e 1."""
    return amostrar_pista(_CICLO_REPOUSO, tempo % _CICLO_REPOUSO[-1][0])[0]

# Frequência default do oscilador lento do idle (ciclos por segundo). ~0.25 Hz
# dá uma inspiração/expiração a cada ~4 segundos, no ritmo de um corpo parado.
FREQUENCIA_PADRAO = 0.25

# Amortecimento da mola que suaviza o alvo. Perto de 1 assenta seco, sem
# oscilação extra sobre o próprio seno do oscilador.
AMORTECIMENTO_PADRAO = 0.85

# Rigidez (Hz) da mola de suavização. Alta o bastante para seguir o oscilador
# lento sem atraso perceptível, mas ainda absorvendo os impulsos de empurrar.
RIGIDEZ_MOLA_PADRAO = 2.4

# Fração do impulso de ``empurrar`` que sobra a cada segundo (decaimento
# exponencial do alvo de volta ao repouso). Menor = decai mais rápido.
RETENCAO_IMPULSO_POR_SEGUNDO = 0.08


class Respiracao:
    """Oscilador lento de respiração suavizado por mola, engine-agnóstico.

    A fase avança de forma contígua (``frequencia * dt``), então o seno do
    oscilador é o alvo base da mola; ``empurrar`` adiciona um impulso que decai
    sozinho. ``norm`` devolve ``0..1`` (vazio..cheio) e ``centrada`` devolve
    ``-1..1`` (ao redor do repouso), que é o valor consumido pelo renderer.
    """

    def __init__(
        self,
        frequencia: float = FREQUENCIA_PADRAO,
        amplitude: float = 1.0,
        *,
        rigidez: float = RIGIDEZ_MOLA_PADRAO,
        amortecimento: float = AMORTECIMENTO_PADRAO,
    ) -> None:
        """Cria o oscilador e a mola da respiração."""
        self.frequencia = max(0.0, frequencia)
        # Amplitude do oscilador base (0..1): escala o quanto o seno ocupa a faixa.
        self.amplitude = clamp(amplitude, 0.0, 1.0)
        self._fase = 0.0
        self._impulso = 0.0
        self._mola = Spring(rigidez, amortecimento)
        # Começa no repouso (centrado em 0), não no extremo do seno.
        self._mola.value = 0.0
        self._mola.velocity = 0.0

    def _alvo(self) -> float:
        """Alvo centrado (-1..1) do frame: oscilador lento mais impulso."""
        oscilador = sin(self._fase) * self.amplitude
        return clamp(oscilador + self._impulso, -1.0, 1.0)

    def atualizar(self, dt: float) -> float:
        """Avança a fase e a mola; devolve o valor centrado (-1..1) do frame.

        ``dt`` é o passo de tempo em segundos. A integração da fase e a solução
        analítica da mola tornam o resultado independente do framerate.
        """
        if dt <= 0.0:
            return self.centrada

        self._fase = (self._fase + tau * self.frequencia * dt) % tau
        # Impulso de ``empurrar`` decai exponencialmente de volta ao repouso.
        self._impulso *= RETENCAO_IMPULSO_POR_SEGUNDO**dt
        self._mola.update(dt, self._alvo())
        return self.centrada

    def empurrar(self, quantidade: float) -> None:
        """Soma um impulso ao alvo da mola para inflar o tórax por evento.

        Usado como gancho de eventos (ex.: inspiração antes de um espirro). O
        impulso decai sozinho em ``atualizar``; valores positivos incham o peito.
        """
        self._impulso = clamp(self._impulso + quantidade, -1.0, 1.0)

    @property
    def impulso_ativo(self) -> bool:
        """Indica se ainda há impulso de ``empurrar`` em curso (sob demanda).

        Read-only; não altera a API existente. Serve para o controlador só expor
        a respiração enquanto houver um impulso vivo, deixando o idle parado.
        """
        return abs(self._impulso) > 1e-4

    @property
    def centrada(self) -> float:
        """Valor suavizado ao redor do repouso, na faixa ``-1..1``."""
        return clamp(self._mola.value, -1.0, 1.0)

    @property
    def norm(self) -> float:
        """Valor suavizado em ``0..1`` (0 = vazio, 1 = cheio)."""
        return (self.centrada + 1.0) * 0.5

    @property
    def fase(self) -> float:
        """Fase atual do oscilador em radianos (``0..2*pi``)."""
        return self._fase

    def reset(self) -> None:
        """Fixa a respiração no repouso, zerando fase, impulso e inércia."""
        self._fase = 0.0
        self._impulso = 0.0
        self._mola.value = 0.0
        self._mola.velocity = 0.0

"""Agendador de pacotes de animação, pacote principal "Olhar a tela" e profundidade visual.

Implementa as seções 7 e 8 de ``docs/MUDANCA_ANIMACAO_NATURALIDADE.md`` e §4.6 de
``docs/ESTUDO_ANIMACAO_PROCEDURAL.md``:
- ``NivelProfundidade`` (``perto``, ``medio``, ``longe``) e ``OrientacaoCorpo``
  (``frente``, ``perfil_direito``, ``perfil_esquerdo``, ``costas``).
- ``EstadoProfundidade``: suaviza com mola crítica a escala visual (1.0, 0.9, 0.8) e
  a subida na tela, retornando a ``perto`` quando o mascote é arrastado ("puxado").
- ``PacoteOlharTela``: sequência de 4 fases (olhar por cima do ombro com torção
  distribuída na coluna → virar com passos → observar a tela de costas → voltar).
- ``AgendadorPacotes``: sorteio ponderado com resfriamento e memória anti-repetição.

FRONTEIRA: Python puro (sem Panda3D, Qt ou Win32).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from enum import StrEnum
from math import pi, radians, sin

from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.mola_critica import avancar_mola_critica
from sejoga.nucleo.esqueleto import Rotation3


class NivelProfundidade(StrEnum):
    """Três níveis discretos de distância visual para dentro da tela (§8.5.1)."""

    PERTO = "perto"
    MEDIO = "medio"
    LONGE = "longe"


_ORDEM_PROFUNDIDADE = tuple(NivelProfundidade)


class OrientacaoCorpo(StrEnum):
    """Orientações nominais do corpo no lugar (§7.2 e §8.5.2)."""

    FRENTE = "frente"
    PERFIL = "perfil"
    PERFIL_ESQUERDO = "perfil_esquerdo"
    COSTAS = "costas"


#: Escala visual do modelo por nível de profundidade (§8.5.1: 100%, 90%, 80%).
ESCALA_POR_PROFUNDIDADE: dict[NivelProfundidade, float] = {
    NivelProfundidade.PERTO: 1.0,
    NivelProfundidade.MEDIO: 0.90,
    NivelProfundidade.LONGE: 0.80,
}

#: Subida vertical (fração da altura do modelo) por nível de profundidade (§8.5.1).
SUBIDA_POR_PROFUNDIDADE: dict[NivelProfundidade, float] = {
    NivelProfundidade.PERTO: 0.0,
    NivelProfundidade.MEDIO: 0.08,
    NivelProfundidade.LONGE: 0.16,
}

#: Ângulo de giro de corpo (graus) por orientação nominal.
ANGULO_POR_ORIENTACAO: dict[OrientacaoCorpo, float] = {
    OrientacaoCorpo.FRENTE: 0.0,
    OrientacaoCorpo.PERFIL: 90.0,
    OrientacaoCorpo.PERFIL_ESQUERDO: -90.0,
    OrientacaoCorpo.COSTAS: 180.0,
}

#: Meia-vida (s) da transição suave de profundidade (caminhando vs puxado pelo mouse).
MEIA_VIDA_PROFUNDIDADE_CAMINHANDO_S = 0.45
MEIA_VIDA_PROFUNDIDADE_PUXADO_S = 0.14

#: Durações das fases do pacote principal "Olhar a tela" (segundos).
DURACAO_FASE_OMBRO_S = 1.4
DURACAO_FASE_VIRAR_COSTAS_S = 1.2
DURACAO_FASE_OBSERVAR_TELA_S = 4.0
DURACAO_FASE_VOLTAR_FRENTE_S = 1.2
DURACAO_TOTAL_OLHAR_TELA_S = (
    DURACAO_FASE_OMBRO_S
    + DURACAO_FASE_VIRAR_COSTAS_S
    + DURACAO_FASE_OBSERVAR_TELA_S
    + DURACAO_FASE_VOLTAR_FRENTE_S
)


class EstadoProfundidade:
    """Controla a escala e subida visual dos 3 níveis de profundidade (§8.5.1)."""

    def __init__(self) -> None:
        """Inicia no nível mais próximo da tela."""
        self.nivel_alvo: NivelProfundidade = NivelProfundidade.PERTO
        self.escala_atual: float = 1.0
        self._vel_escala: float = 0.0
        self.subida_atual: float = 0.0
        self._vel_subida: float = 0.0

    def definir_nivel(self, nivel: NivelProfundidade | str) -> None:
        """Define o nível-alvo de profundidade (`perto`, `medio` ou `longe`)."""
        self.nivel_alvo = NivelProfundidade(nivel)

    def avancar_fundo(self) -> NivelProfundidade:
        """Avança um nível para dentro da tela (`perto -> medio -> longe`)."""
        idx = min(len(_ORDEM_PROFUNDIDADE) - 1, _ORDEM_PROFUNDIDADE.index(self.nivel_alvo) + 1)
        self.nivel_alvo = _ORDEM_PROFUNDIDADE[idx]
        return self.nivel_alvo

    def avancar_frente(self) -> NivelProfundidade:
        """Volta um nível para a frente da tela (`longe -> medio -> perto`)."""
        idx = max(0, _ORDEM_PROFUNDIDADE.index(self.nivel_alvo) - 1)
        self.nivel_alvo = _ORDEM_PROFUNDIDADE[idx]
        return self.nivel_alvo

    def atualizar(self, dt: float, *, arrastando: bool = False) -> tuple[float, float]:
        """Atualiza ``(escala, subida_fracao)``; puxa para ``perto`` se arrastado."""
        if arrastando:
            self.nivel_alvo = NivelProfundidade.PERTO
        meia_vida = (
            MEIA_VIDA_PROFUNDIDADE_PUXADO_S
            if arrastando
            else MEIA_VIDA_PROFUNDIDADE_CAMINHANDO_S
        )
        alvo_escala = ESCALA_POR_PROFUNDIDADE[self.nivel_alvo]
        alvo_subida = SUBIDA_POR_PROFUNDIDADE[self.nivel_alvo]
        self.escala_atual, self._vel_escala = avancar_mola_critica(
            self.escala_atual, self._vel_escala, alvo_escala, meia_vida, dt
        )
        self.subida_atual, self._vel_subida = avancar_mola_critica(
            self.subida_atual, self._vel_subida, alvo_subida, meia_vida, dt
        )
        return self.escala_atual, self.subida_atual


@dataclass(frozen=True, slots=True)
class AmostraOlharTela:
    """Saída instantânea do pacote principal ``Olhar a tela``."""

    ativo: bool
    fase: str
    angulo_giro_corpo: float | None
    em_passo: bool
    delta_pose: dict[str, Rotation3]


class PacoteOlharTela:
    """Executa o pacote principal 'Olhar a tela' (§7.2 e §8.3).

    Fases:
    1. ``olhar_ombro``: torce gradualmente ``cintura``, ``abdomen``, ``peitoral`` e
       ``head`` para olhar por cima do ombro antes dos pés saírem do lugar.
    2. ``virar_costas``: gira ``body_facing`` até 180° enquanto dá passos e relaxa
       a torção da coluna.
    3. ``observar_tela``: permanece de costas (180°) observando a tela com leve
       balanço curioso de cabeça, tronco, fones e antenas.
    4. ``voltar_frente``: retorna ``body_facing`` a 0° dando passos até assentar.
    """

    def __init__(self) -> None:
        """Prepara a sequência para o primeiro disparo."""
        self.ativo: bool = False
        self.tempo: float = 0.0
        self.lado: float = 1.0

    def iniciar(self, *, lado: float = 1.0) -> None:
        """Dispara o pacote 'Olhar a tela' pelo lado indicado (+1 ou -1)."""
        self.ativo = True
        self.tempo = 0.0
        self.lado = 1.0 if lado >= 0.0 else -1.0

    def interromper(self) -> None:
        """Interrompe o pacote imediatamente (ex.: em caso de arraste ou clique)."""
        self.ativo = False
        self.tempo = 0.0

    def _amostrar_fase(self, t):
        t1 = DURACAO_FASE_OMBRO_S
        t2 = t1 + DURACAO_FASE_VIRAR_COSTAS_S
        t3 = t2 + DURACAO_FASE_OBSERVAR_TELA_S
        lado = self.lado
        if t < t1:
            u = suavizar_quintico(t / t1)
            return "olhar_ombro", 0.0, False, u, 0.0
        if t < t2:
            u = suavizar_quintico((t - t1) / DURACAO_FASE_VIRAR_COSTAS_S)
            return "virar_costas", lado * 180.0 * u, True, 1.0 - u, 0.0
        if t < t3:
            u = (t - t2) / DURACAO_FASE_OBSERVAR_TELA_S
            return "observar_tela", lado * 180.0, False, 0.0, sin(u * pi)
        u = suavizar_quintico((t - t3) / DURACAO_FASE_VOLTAR_FRENTE_S)
        return "voltar_frente", lado * 180.0 * (1.0 - u), True, 0.0, 0.0

    def atualizar(self, dt: float, *, interromper: bool = False) -> AmostraOlharTela:
        """Avança o pacote por ``dt`` e devolve a amostra para o controlador."""
        if interromper or not self.ativo:
            self.interromper()
            return AmostraOlharTela(False, "inativo", None, False, {})

        self.tempo += max(0.0, dt)
        t = self.tempo
        if t >= DURACAO_TOTAL_OLHAR_TELA_S:
            self.interromper()
            return AmostraOlharTela(False, "inativo", None, False, {})

        fase, giro_corpo, em_passo, torcao, curiosidade = self._amostrar_fase(t)
        s = self.lado

        # Torção distribuída ("olhar por cima do ombro"): cintura + abdomen + peitoral + head
        osc_obs = sin(t * 2.4) * curiosidade
        delta: dict[str, Rotation3] = {
            "cintura": Rotation3(
                radians(-2.0 * torcao),
                radians(s * 14.0 * torcao + osc_obs * 3.0),
                radians(s * 2.5 * torcao),
            ),
            "abdomen": Rotation3(
                radians(-3.0 * torcao),
                radians(s * 20.0 * torcao + osc_obs * 4.5),
                radians(s * 3.5 * torcao),
            ),
            "peitoral": Rotation3(
                radians(-4.0 * torcao - 3.0 * curiosidade),
                radians(s * 26.0 * torcao + osc_obs * 6.0),
                radians(s * 4.5 * torcao),
            ),
            "head": Rotation3(
                radians(-6.0 * torcao - 5.0 * curiosidade),
                radians(s * 35.0 * torcao + osc_obs * 12.0),
                radians(s * 6.0 * torcao + osc_obs * 4.0),
            ),
            "antena-direita": Rotation3(
                radians(8.0 * torcao),
                0.0,
                radians(-s * 10.0 * torcao + osc_obs * 8.0),
            ),
            "antena-esquerda": Rotation3(
                radians(8.0 * torcao),
                0.0,
                radians(-s * 10.0 * torcao - osc_obs * 8.0),
            ),
        }
        return AmostraOlharTela(True, fase, giro_corpo, em_passo, delta)


@dataclass(slots=True)
class ItemPacote:
    """Configuração de peso e resfriamento de um pacote no agendador (§4.6)."""

    nome: str
    peso: float = 1.0
    resfriamento_s: float = 45.0
    restante_s: float = 0.0


class AgendadorPacotes:
    """Sorteio ponderado com resfriamento e memória anti-repetição (estudo §4.6)."""

    def __init__(
        self,
        pacotes: tuple[ItemPacote, ...] | None = None,
        *,
        intervalo_base_s: float = 65.0,
        semente: int | None = None,
    ) -> None:
        """Inicializa os relógios com cópias da configuração recebida."""
        self._rng = random.Random(semente)
        self.intervalo_base_s = max(5.0, intervalo_base_s)
        self.pacotes: dict[str, ItemPacote] = {
            p.nome: replace(p)
            for p in (
                pacotes
                if pacotes is not None
                else (
                    ItemPacote("olhar_tela", peso=1.5, resfriamento_s=60.0),
                    ItemPacote("caminhar_fundo", peso=0.8, resfriamento_s=90.0),
                    ItemPacote("caminhar_lado", peso=1.0, resfriamento_s=50.0),
                )
            )
        }
        self.ultimo_escolhido: str | None = None
        self.tempo_ate_proximo_s: float = self._sortear_intervalo()

    def _sortear_intervalo(self) -> float:
        # estudo §4.6: base * (0.7 + 0.6 * ruido_0_1)
        return self.intervalo_base_s * (0.7 + 0.6 * self._rng.random())

    def atualizar(self, dt: float, *, elegivel: bool = True) -> str | None:
        """Avança relógios de resfriamento e devolve o nome do pacote sorteado ou ``None``."""
        if dt <= 0.0:
            return None
        for item in self.pacotes.values():
            item.restante_s = max(0.0, item.restante_s - dt)
        if not elegivel:
            return None
        self.tempo_ate_proximo_s -= dt
        if self.tempo_ate_proximo_s > 0.0:
            return None
        self.tempo_ate_proximo_s = self._sortear_intervalo()
        return self.sortear()

    def sortear(self) -> str | None:
        """Escolhe um pacote disponível sem repetir o último se houver alternativa."""
        disponiveis = [
            p for p in self.pacotes.values() if p.restante_s <= 0.0 and p.peso > 0.0
        ]
        if not disponiveis:
            return None
        sem_repetir = [p for p in disponiveis if p.nome != self.ultimo_escolhido]
        candidatos = sem_repetir or disponiveis
        escolhido = self._rng.choices(candidatos, weights=[p.peso for p in candidatos])[0]
        escolhido.restante_s = escolhido.resfriamento_s
        self.ultimo_escolhido = escolhido.nome
        return escolhido.nome

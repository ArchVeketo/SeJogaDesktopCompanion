"""Camada de ATENÇÃO/olhar: decide PARA ONDE o mascote olha.

Esta camada não renderiza nem fala com o Windows. Ela só traduz "pontos de
atenção" em coordenadas de tela (globais) para o sinal ``(direcao, vertical)``
que ``pose_interaction`` já consome (olhar de cabeça/tronco/braço), e escolhe,
entre vários gatilhos concorrentes, de qual deles o olhar deve vir.

Gatilhos são NÃO-invasivos: o app só alimenta sinais que já coleta (cursor
global, janela em foco, batida da música, borda do monitor) ou timers/aleatório
de personalidade. Nada aqui lê conteúdo da tela, captura pixels, faz OCR ou
engancha teclado de conteúdo.

LIMITE desta feature: só a atenção da CABEÇA/tronco/braço com o look-at atual.
O giro amplo de corpo (virar de costas) e a locomoção são fases posteriores e
NÃO são implementados aqui.

Os parâmetros numéricos (ganhos de olhar, limiares de gatilho, duração da
surpresa) estão nomeados e comentados para calibração visual na GPU.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# --- Parâmetros CALIBRÁVEIS (validar visualmente na GPU) --------------------

# Centro vertical da janela usado na normalização do olhar. Espelha o 0.52 do
# cálculo histórico em window._animation_tick (o rosto do mascote fica um pouco
# acima do centro geométrico da janela).
CENTRO_VERTICAL = 0.52

# Prioridades dos gatilhos (maior vence quando há concorrência). A surpresa de
# troca de foco manda mais que o cursor; o cursor manda mais que a atenção de
# ambiente espontânea.
PRIORIDADE_FOCO = 30
PRIORIDADE_CURSOR = 20
PRIORIDADE_BEAT = 15
PRIORIDADE_BORDA = 10
PRIORIDADE_AMBIENTE = 5

# Janela de ambiente espontâneo: de tempos em tempos o mascote lança o olhar
# para um ponto aleatório, como quem repara em algo. Intervalos em segundos.
AMBIENTE_INTERVALO_MIN = 8.0
AMBIENTE_INTERVALO_MAX = 18.0
# Quanto dura cada episódio de atenção de ambiente antes de expirar.
AMBIENTE_DURACAO = 2.2

# Surpresa: diferença angular mínima (em unidades de direção, -1..1) entre o
# alvo atual e o anterior para disparar o susto. Evita sustos por micro-ajustes.
SURPRESA_LIMIAR_SALTO = 0.9
# Intensidade mínima do gatilho para um susto valer a pena.
SURPRESA_FORCA_MINIMA = 0.5


def ponto_para_direcao(
    ponto_global: tuple[float, float],
    origem_janela: tuple[float, float],
    largura: float,
    altura: float,
) -> tuple[float, float]:
    """Converte um ponto de atenção GLOBAL na direção local do modelo.

    Generaliza a conversão que ``window._animation_tick`` já fazia só para o
    cursor DENTRO da janela: subtrai a origem (canto superior-esquerdo da
    janela, em coordenadas de tela) para obter o ponto em espaço local e
    normaliza pelo tamanho da janela. O olhar de cabeça e a inclinação
    continuam vindo de ``pose_interaction``; aqui muda apenas a FONTE do alvo.

    Devolve ``(direcao, vertical)`` já saturado em ``[-1, 1]``:
    - ``direcao > 0`` quando o ponto está à DIREITA da janela;
    - ``vertical > 0`` quando o ponto está ABAIXO do centro do rosto.
    """
    if largura <= 0 or altura <= 0:
        return 0.0, 0.0

    local_x = ponto_global[0] - origem_janela[0]
    local_y = ponto_global[1] - origem_janela[1]
    direcao = (local_x / largura - 0.5) * 2.0
    vertical = (local_y / altura - CENTRO_VERTICAL) * 2.0
    return _saturar(direcao), _saturar(vertical)


def _saturar(valor: float) -> float:
    return max(-1.0, min(1.0, valor))


@dataclass(frozen=True)
class GatilhoAtencao:
    """Um candidato a alvo de atenção, em coordenadas de tela (globais).

    ``fonte`` é o nome legível do gatilho (ex.: "cursor", "foco", "beat").
    ``prioridade`` resolve a concorrência (maior vence). ``forca`` em ``[0, 1]``
    pondera micro-reações (ex.: energia da batida) e alimenta a surpresa.
    """

    fonte: str
    ponto: tuple[float, float]
    prioridade: int
    forca: float = 1.0


@dataclass
class AlvoAtencao:
    """Resultado de um quadro: direção de olhar + metadados do gatilho vencedor."""

    direcao: float = 0.0
    vertical: float = 0.0
    fonte: str | None = None
    forca: float = 0.0
    surpresa: bool = False


@dataclass
class GateAtencao:
    """Escolhe o alvo de atenção entre gatilhos concorrentes e por prioridade.

    Também gera atenção de AMBIENTE (timer + aleatório) quando nenhum gatilho
    externo está ativo, e sinaliza SURPRESA quando o alvo salta bruscamente
    para um gatilho forte (ex.: troca de janela em foco em outra borda).

    O gate é engine-agnóstico e determinístico sob um ``random.Random`` dado,
    para ser testável sem GPU.
    """

    rng: random.Random = field(default_factory=random.Random)
    _ambiente_em: float = 0.0
    _ambiente_restante: float = 0.0
    _ambiente_ponto: tuple[float, float] | None = None
    _direcao_anterior: float | None = None
    _inicializado: bool = False

    def _sortear_intervalo_ambiente(self) -> float:
        return self.rng.uniform(AMBIENTE_INTERVALO_MIN, AMBIENTE_INTERVALO_MAX)

    def _sortear_ponto_ambiente(
        self, origem_janela: tuple[float, float], largura: float, altura: float
    ) -> tuple[float, float]:
        """Ponto espontâneo numa moldura ao redor da janela (algo "lá fora")."""
        margem_x = largura * 1.5
        margem_y = altura * 1.5
        return (
            origem_janela[0] + self.rng.uniform(-margem_x, margem_x),
            origem_janela[1] + self.rng.uniform(-margem_y, margem_y),
        )

    def atualizar(
        self,
        dt: float,
        *,
        gatilhos: list[GatilhoAtencao],
        origem_janela: tuple[float, float],
        largura: float,
        altura: float,
        habilitado: bool = True,
        ambiente_habilitado: bool = True,
    ) -> AlvoAtencao:
        """Avança o gate um quadro e devolve o alvo de olhar escolhido.

        - ``gatilhos`` concorrentes: vence o de maior prioridade (empate: o
          primeiro da lista). Lista vazia e ambiente desligado => olhar neutro.
        - ``habilitado=False`` desliga a feature inteira: nenhum movimento
          (direção/vertical zerados, sem surpresa).
        - ``ambiente_habilitado=False`` mantém só os gatilhos externos.
        """
        if not self._inicializado:
            self._ambiente_em = self._sortear_intervalo_ambiente()
            self._inicializado = True

        if not habilitado:
            # Feature desligada: zera tudo e não produz movimento nem susto.
            self._direcao_anterior = None
            self._ambiente_restante = 0.0
            return AlvoAtencao()

        self._avancar_ambiente(dt, origem_janela, largura, altura, ambiente_habilitado)

        candidatos = list(gatilhos)
        if ambiente_habilitado and self._ambiente_restante > 0 and self._ambiente_ponto is not None:
            candidatos.append(
                GatilhoAtencao("ambiente", self._ambiente_ponto, PRIORIDADE_AMBIENTE)
            )

        if not candidatos:
            self._direcao_anterior = None
            return AlvoAtencao()

        vencedor = max(candidatos, key=lambda g: g.prioridade)
        direcao, vertical = ponto_para_direcao(
            vencedor.ponto, origem_janela, largura, altura
        )

        surpresa = self._detectar_surpresa(direcao, vencedor.forca)
        self._direcao_anterior = direcao

        return AlvoAtencao(
            direcao=direcao,
            vertical=vertical,
            fonte=vencedor.fonte,
            forca=vencedor.forca,
            surpresa=surpresa,
        )

    def _avancar_ambiente(
        self,
        dt: float,
        origem_janela: tuple[float, float],
        largura: float,
        altura: float,
        ambiente_habilitado: bool,
    ) -> None:
        if not ambiente_habilitado:
            self._ambiente_restante = 0.0
            return

        if self._ambiente_restante > 0:
            self._ambiente_restante = max(0.0, self._ambiente_restante - dt)
            return

        self._ambiente_em = max(0.0, self._ambiente_em - dt)
        if self._ambiente_em <= 0.0:
            self._ambiente_restante = AMBIENTE_DURACAO
            self._ambiente_ponto = self._sortear_ponto_ambiente(
                origem_janela, largura, altura
            )
            self._ambiente_em = self._sortear_intervalo_ambiente()

    def _detectar_surpresa(self, direcao: float, forca: float) -> bool:
        """Susto quando o olhar salta muito para um gatilho forte."""
        if forca < SURPRESA_FORCA_MINIMA:
            return False
        if self._direcao_anterior is None:
            return False
        return abs(direcao - self._direcao_anterior) >= SURPRESA_LIMIAR_SALTO

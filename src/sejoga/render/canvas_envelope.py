"""Dimensionamento estável da janela do mascote (envelope de pior caso).

Motivação (flicker da "janela dinâmica"):
    O código antigo media ``getTightBounds`` do rig a cada frame e
    redimensionava a janela seguindo os limites vivos. Em poses "pendurado
    pela perna" o torso gira ±155° por uma mola subamortecida, então a
    projeção do bounding box oscila frame a frame. Como o CRESCIMENTO era
    imediato e sem zona-morta, cada sobressalto virava um resize — e cada
    resize forçava um repaint/erase síncrono numa janela layered com color
    key magenta, que o olho percebe como piscada.

Estratégia:
    Em vez de perseguir os limites vivos, a janela assume um de POUCOS
    tamanhos discretos ("degraus de envelope") grandes o bastante para
    comportar a pose mais extensa possível. O tamanho só muda quando a
    necessidade atravessa um degrau inteiro com folga (zona-morta), e com
    COOLDOWN SIMÉTRICO (mesmo valor para crescer e encolher). Dentro de um
    degrau a pose pode balançar à vontade sem mover a janela.

Esta lógica é pura (sem Panda3D/Win32) para ser testável sem engine gráfico.

Como o envelope foi calculado (derivação defensável):
    - ``base`` é o lado da janela em repouso (``settings.window.size``,
      padrão 480 px). O mascote ocupa ``renderer.FRAME_FILL`` (= 0,66) da
      vista nessa janela, logo seu lado projetado em pé é ~0,66·base.
    - Na pose de arraste o torso é rolado até ±178° (clamp em
      ``body_motion``) com membros estendidos (``grab_part`` de braço/perna).
      Girar 45° um corpo de lado ``s`` projeta até ``s·√2`` (~1,41·s); com
      membros estendidos no grab a extensão plausível chega a ~2·base.
    - Por isso os degraus são múltiplos inteiros da base (base, 2·base,
      3·base). ``base`` cobre o repouso; ``2·base`` cobre a diagonal rolada
      com membros estendidos; ``3·base`` é o teto de segurança (igual ao
      ``min(base*3, …)`` histórico), evitando qualquer corte residual.
    - A escolha final é sempre ≥ ``necessário`` (medido pela projeção real
      dos limites), então o envelope NUNCA corta a pose: ele só arredonda
      para cima até o próximo degrau com margem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Margem anti-corte (px) somada à necessidade antes de escolher o degrau.
# Garante folga para a assincronia de propriedades do Panda (a lente cresce
# no frame, o framebuffer 1-2 frames depois) sem reintroduzir corte.
MARGEM_ANTICORTE = 48

# Cooldown simétrico (s): tempo mínimo entre qualquer troca de degrau,
# idêntico para crescer e encolher, para o tamanho jamais "pulsar".
COOLDOWN = 0.6


@dataclass
class EstadoEnvelope:
    """Estado mutável do dimensionamento entre frames."""

    cooldown: float = 0.0


def degraus_envelope(base: int, teto_mult: int = 3) -> list[int]:
    """Lista de tamanhos discretos permitidos, de ``base`` a ``base*teto_mult``.

    São poucos tamanhos estáveis (repouso, estendido, pior caso) em vez de
    uma escala contínua, para que a pose viva não gere resizes por frame.
    """

    if base <= 0:
        raise ValueError("base deve ser positiva")

    return [base * fator for fator in range(1, teto_mult + 1)]


def degrau_para(necessario: float, base: int, teto_mult: int = 3) -> int:
    """Menor degrau de envelope que comporta ``necessario`` + margem.

    O resultado é sempre ≥ ``necessario`` (mais a margem anti-corte, exceto
    quando esbarra no teto), garantindo que a pose não seja cortada.
    """

    alvo = necessario + MARGEM_ANTICORTE
    degraus = degraus_envelope(base, teto_mult)

    for degrau in degraus:
        if degrau >= alvo:
            return degrau

    return degraus[-1]


def escolher_tamanho(
    necessario: float,
    atual: int,
    base: int,
    estado: EstadoEnvelope,
    dt: float,
    *,
    dragging: bool = False,
    fixar_degrau: bool = False,
    teto_mult: int = 3,
) -> int:
    """Decide o lado da janela para o frame atual (puro, determinístico).

    Regras:
    - Escolhe o degrau de envelope que comporta ``necessario`` com margem.
    - Só muda de degrau se o alvo for diferente do atual E o cooldown
      simétrico tiver expirado. Durante o arraste, nunca encolhe (evita
      corte no meio de uma pose rápida), mas pode crescer imediatamente se
      o alvo exceder o atual (segurança anti-corte tem prioridade).
    - Dentro de um degrau a pose balança sem redimensionar (zona-morta: o
      degrau é largo o bastante para absorver o ringing da mola).

    Quando ``fixar_degrau=True`` (arraste pelo pé: o torso rola ~155° e o
    bbox projetado oscila frame a frame, podendo PULAR degraus para cima e
    reintroduzir o resize/piscada): NÃO reavalia o degrau por frame. Trava no
    ``atual`` enquanto ele já comportar ``necessario`` (sempre ≥ necessario,
    nunca corta); só quando ``necessario`` exceder o degrau atual sobe UMA
    vez para o menor degrau que comporte (via ``degrau_para``) e ali
    permanece. Assim, para uma necessidade oscilante que já cabe no pico, o
    tamanho fica constante — sem cooldown nem zona-morta, que não bastam
    contra saltos de degrau. Nunca encolhe nesse modo.

    Retorna o tamanho a aplicar (igual a ``atual`` quando nada muda).
    """

    estado.cooldown = max(0.0, estado.cooldown - dt)
    alvo = degrau_para(necessario, base, teto_mult)

    if fixar_degrau:
      # Degrau travado: só sobe se o atual não comporta mais a necessidade;
      # caso contrário fica cravado, ignorando a oscilação do bbox rolado.
      if alvo > atual:
        return alvo
      return atual

    if alvo == atual:
        return atual

    crescer = alvo > atual

    # Crescer para evitar corte tem prioridade: durante o arraste aplica já;
    # fora do arraste respeita o cooldown simétrico para não pulsar.
    if crescer:
        if dragging or estado.cooldown <= 0.0:
            estado.cooldown = COOLDOWN
            return alvo
        return atual

    # Encolher: bloqueado durante o arraste e sob cooldown simétrico.
    if dragging or estado.cooldown > 0.0:
        return atual

    estado.cooldown = COOLDOWN
    return alvo


def extensao_necessaria(pontos_px: list[tuple[float, float]], folga: int = 32) -> float:
    """Lado em px (centrado) que contém os pontos projetados do modelo.

    ``pontos_px`` são os cantos do bounding box projetados em coordenadas de
    pixel relativas ao centro da janela. Espelha o cálculo histórico de
    ``extent`` para preservar o comportamento anti-corte da medição.
    """

    if not pontos_px:
        return 0.0

    pico = max(max(abs(x), abs(y)) for x, y in pontos_px if math.isfinite(x) and math.isfinite(y))

    return pico * 2 + folga

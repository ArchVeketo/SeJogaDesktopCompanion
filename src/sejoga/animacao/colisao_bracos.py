"""Anti-atravessamento dos braços contra o corpo, com a FK real do rig.

Os braços são cápsulas (braço, antebraço, mão+dedos) medidas por
``nucleo.cinematica`` (mesma FK do Panda3D). O corpo são caixas do referencial de
AUTORIA (``+X`` direita, ``+Y`` frente, ``+Z`` cima) medidas no grafo de cena
do asset em repouso (``tools/oraculo_cena.py``). As primitivas de interseção são
as de ``rig_mapa.colisao_membros`` (cápsula-caixa e cápsula-cápsula).

A correção é MÍNIMA e determinística: busca em subida de encosta, sobre os
quatro graus de liberdade do lado (P, H, R do ombro e a flexão do cotovelo), o
menor deslocamento que zera a penetração. O deslocamento é guardado por lado
(partida a quente) e relaxa de volta a zero quando deixa de ser necessário, para
a correção entrar e sair sem tranco.

shortcut: as caixas do corpo são as do repouso (tronco/cabeça/pernas não
acompanham inclinações pequenas da pose), refazer por pose se o tronco passar a
girar muito.

FRONTEIRA: Python puro (só ``math`` e módulos puros do projeto).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from math import radians

from sejoga.nucleo import cinematica as cin
from sejoga.nucleo.model import Model
from sejoga.nucleo.rig import Rotation3
from sejoga.rig_mapa.colisao_membros import (
    CaixaOrientada,
    Capsula,
    penetracao_capsula_caixa,
    penetracao_capsula_capsula,
)

Vec3 = cin.Vec3

# --------------------------------------------------------------------------- #
# Geometria do braço (medida no asset; ver tools/oraculo_cena.py)
# --------------------------------------------------------------------------- #
#: Menor meia-aresta medida do cubo do braço (seção 0.273 x 0.227).
MEIA_ESPESSURA_BRACO_U = 0.1135
#: Fração da meia-espessura que conta como NÚCLEO do membro. "Atravessar" = o
#: núcleo entrar num volume do corpo; encostar a casca não conta. Com a espessura
#: cheia (fração 1) só o T-pose fica livre: braço+mão (≈0.61) são do tamanho do
#: corpo e qualquer mão à frente encosta no tronco. A_CONFIRMAR (C4/C6).
FRACAO_NUCLEO_BRACO = 0.5
RAIO_BRACO_U = MEIA_ESPESSURA_BRACO_U * FRACAO_NUCLEO_BRACO
#: Comprimento da mão + dedos além do punho (``hand`` → ponta de ``fingers``).
COMPRIMENTO_MAO_U = 0.33
#: Meia-largura medida do tronco (malha ``mesh20``). O pivô do ombro (x=0.125)
#: nasce DENTRO dela: no próprio T-pose do asset os primeiros
#: ``MEIA_LARGURA_TRONCO_U + RAIO_BRACO_U - |x_ombro|`` (≈0.171) do eixo do braço
#: ficam dentro do tronco. Esse trecho estrutural da raiz não conta como colisão.
MEIA_LARGURA_TRONCO_U = 0.186

# --------------------------------------------------------------------------- #
# Volumes do corpo em repouso (referencial de autoria): (centro, meias-dimensões)
# --------------------------------------------------------------------------- #
def _caixa(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> CaixaOrientada:
    """Caixa alinhada aos eixos de autoria a partir dos limites medidos."""
    return CaixaOrientada(
        centro=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
        eixos=(cin.EIXO_DIREITA, cin.EIXO_FRENTE, cin.EIXO_CIMA),
        meias_dim=((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2),
    )


def _espelhada(caixa: CaixaOrientada) -> CaixaOrientada:
    return CaixaOrientada(
        centro=cin.espelhar_ponto(caixa.centro), eixos=caixa.eixos, meias_dim=caixa.meias_dim
    )


#: Medido por AABB de cada malha (Panda3D, relativo ao nó raiz do asset).
_ORELHA = _caixa(0.146, 0.303, -0.126, 0.112, 0.789, 1.027)
_CHAPEU_LATERAL = _caixa(0.240, 0.394, -0.200, -0.030, 1.018, 1.125)
_PE = _caixa(0.028, 0.277, -0.140, 0.269, 0.091, 0.384)

CAIXAS_CORPO: dict[str, CaixaOrientada] = {
    "tronco": _caixa(-0.186, 0.186, -0.146, 0.143, 0.420, 0.723),
    "cabeca": _caixa(-0.146, 0.146, -0.161, 0.151, 0.651, 1.100),
    "topo_cabeca": _caixa(-0.195, 0.195, -0.070, 0.032, 1.140, 1.234),
    # mesh18 (plano inclinado do cabo do fone na frente da camiseta) fica de fora:
    # é decalque fino, a AABB dele bloquearia qualquer mão à frente do peito.
    "quadril": _caixa(-0.312, 0.312, -0.189, 0.188, 0.135, 0.474),
    "orelha_direita": _ORELHA,
    "orelha_esquerda": _espelhada(_ORELHA),
    "chapeu_direito": _CHAPEU_LATERAL,
    "chapeu_esquerdo": _espelhada(_CHAPEU_LATERAL),
    "pe_direito": _PE,
    "pe_esquerdo": _espelhada(_PE),
}

# --------------------------------------------------------------------------- #
# Correção
# --------------------------------------------------------------------------- #
#: Penetração (unidades do modelo) tolerada: abaixo disto a pose passa intacta.
FOLGA_PENETRACAO_U = 0.01
#: Passos (graus) da busca em cada grau de liberdade: o fino ajusta, os grossos
#: saltam mínimos locais (ex.: antebraço dobrado contra o peito).
PASSOS_BUSCA_GRAUS = (3.0, 9.0, 27.0)
#: Passos de melhoria por quadro. Um passo por quadro (≥3°, ~180°/s a 60 fps)
#: já corrige rápido e espalha o custo; o resto continua no quadro seguinte
#: (partida a quente). Custo medido (CPython, esta máquina): ~2 ms/quadro com os
#: braços livres; corrigindo, mediana ~12 ms e pico ~41 ms (quadro em que só o
#: passo grosso resolve).
#: shortcut: busca por coordenadas em Python puro, com picos de ~41 ms durante
#: correções; trocar por gradiente analítico ou cápsula-caixa fechada se o
#: usuário notar engasgos ao entrar/sair de gestos.
ITERACOES_POR_QUADRO = 1
#: Deslocamento máximo acumulado (graus) por grau de liberdade.
DESLOCAMENTO_MAXIMO_GRAUS = 70.0
#: Fração do deslocamento mantida por quadro quando a pose já está livre.
RELAXAMENTO_POR_QUADRO = 0.88
#: Deslocamento (graus) abaixo do qual o relaxamento zera de vez.
DESLOCAMENTO_DESPREZIVEL_GRAUS = 0.05
#: Graus de liberdade corrigidos: P, H, R do ombro e flexão do cotovelo.
GRAUS_DE_LIBERDADE = 4

_GRUPOS = {
    "right": ("right-arm", "ant-arm", "hand"),
    "left": ("left-arm", "ant-arm2", "hand2"),
}


def raiz_isenta(model: Model) -> float:
    """Comprimento da raiz do braço que fica no tronco por construção do asset."""
    x_ombro = abs(cin.posicao_no(model, _GRUPOS["right"][0])[0])

    return max(0.0, MEIA_LARGURA_TRONCO_U + RAIO_BRACO_U - x_ombro)


def capsulas_do_braco(model: Model, lado: str, pose: dict[str, Rotation3]) -> list[Capsula]:
    """Cápsulas da cadeia ombro→cotovelo→punho→ponta dos dedos, sem a raiz isenta."""
    braco, antebraco, mao = _GRUPOS[lado]
    nos = cin.cadeia(model, mao, pose)
    rot_mao, punho = nos[mao]
    eixo_osso = cin.EIXO_DIREITA if lado == "right" else cin.espelhar_ponto(cin.EIXO_DIREITA)
    ponta = cin.somar(punho, cin.escalar(cin.aplicar(rot_mao, eixo_osso), COMPRIMENTO_MAO_U))
    pontos = [nos[braco][1], nos[antebraco][1], punho, ponta]
    restante = raiz_isenta(model)
    capsulas: list[Capsula] = []

    for inicio, fim in pairwise(pontos):
        trecho = cin.subtrair(fim, inicio)
        comprimento = cin.norma(trecho)

        if restante >= comprimento:
            restante -= comprimento
            continue

        if restante > 0.0:
            inicio = cin.somar(inicio, cin.escalar(trecho, restante / comprimento))
            restante = 0.0

        capsulas.append(Capsula(inicio, fim, RAIO_BRACO_U))

    return capsulas


def _longe(capsula: Capsula, caixa: CaixaOrientada) -> bool:
    """Descarte barato: esfera da cápsula e esfera circunscrita da caixa não se tocam."""
    meio = cin.escalar(cin.somar(capsula.a, capsula.b), 0.5)
    meio_comprimento = cin.norma(cin.subtrair(capsula.b, capsula.a)) * 0.5
    distancia = cin.norma(cin.subtrair(meio, caixa.centro))

    return distancia > meio_comprimento + cin.norma(caixa.meias_dim) + capsula.raio


def penetracao_do_lado(
    model: Model, lado: str, pose: dict[str, Rotation3], do_outro: list[Capsula] | None = None
) -> float:
    """Maior penetração (u) das cápsulas do ``lado`` no corpo e no outro braço.

    ``do_outro`` permite reaproveitar as cápsulas do outro braço quando só este
    lado muda (busca do resolvedor).
    """
    minhas = capsulas_do_braco(model, lado, pose)

    if do_outro is None:
        do_outro = capsulas_do_braco(model, "left" if lado == "right" else "right", pose)
    maior = 0.0

    for capsula in minhas:
        for caixa in CAIXAS_CORPO.values():
            if _longe(capsula, caixa):
                continue

            maior = max(maior, penetracao_capsula_caixa(capsula, caixa))

        for alheia in do_outro:
            maior = max(maior, penetracao_capsula_capsula(capsula, alheia))

    return maior


def _com_deslocamento(
    pose: dict[str, Rotation3], lado: str, deslocamento: list[float]
) -> dict[str, Rotation3]:
    """Pose com o deslocamento (graus, convenção do braço DIREITO) somado ao lado."""
    braco, antebraco, _mao = _GRUPOS[lado]
    dp, dh, dr, dflexao = (radians(v) for v in deslocamento)
    atual_braco = pose.get(braco, Rotation3())
    atual_ante = pose.get(antebraco, Rotation3())
    soma_braco = Rotation3(dp, dh, dr)
    soma_ante = Rotation3(0.0, 0.0, dflexao)

    if lado == "left":
        soma_braco, soma_ante = cin.espelhar_rotacao(soma_braco), cin.espelhar_rotacao(soma_ante)

    resultado = dict(pose)
    resultado[braco] = Rotation3(
        atual_braco.x + soma_braco.x, atual_braco.y + soma_braco.y, atual_braco.z + soma_braco.z
    )
    resultado[antebraco] = Rotation3(
        atual_ante.x + soma_ante.x, atual_ante.y + soma_ante.y, atual_ante.z + soma_ante.z
    )

    return resultado


@dataclass
class ResolvedorBracos:
    """Corrige a pose para os braços não atravessarem o corpo (com estado)."""

    model: Model

    def __post_init__(self) -> None:
        self._do_outro: list[Capsula] | None = None
        self._deslocamento: dict[str, list[float]] = {
            "right": [0.0] * GRAUS_DE_LIBERDADE,
            "left": [0.0] * GRAUS_DE_LIBERDADE,
        }

    def deslocamento(self, lado: str) -> tuple[float, ...]:
        """Deslocamento corrente (graus) do lado, para diagnóstico."""
        return tuple(self._deslocamento[lado])

    def resolver(self, pose: dict[str, Rotation3]) -> dict[str, Rotation3]:
        """Devolve a pose com os braços corrigidos (cópia; a original não muda)."""
        resultado = dict(pose)

        for lado in ("right", "left"):
            resultado = self._resolver_lado(resultado, lado)

        return resultado

    def _penetracao(self, pose: dict[str, Rotation3], lado: str, desloc: list[float]) -> float:
        return penetracao_do_lado(
            self.model, lado, _com_deslocamento(pose, lado, desloc), do_outro=self._do_outro
        )

    def _resolver_lado(self, pose: dict[str, Rotation3], lado: str) -> dict[str, Rotation3]:
        desloc = self._deslocamento[lado]
        outro = "left" if lado == "right" else "right"
        self._do_outro = capsulas_do_braco(self.model, outro, pose)
        atual = self._penetracao(pose, lado, desloc)

        for _ in range(ITERACOES_POR_QUADRO):
            if atual <= FOLGA_PENETRACAO_U:
                break

            melhor, melhor_pen = None, atual

            for passo in PASSOS_BUSCA_GRAUS:
                for eixo in range(GRAUS_DE_LIBERDADE):
                    for sinal in (1.0, -1.0):
                        tentativa = list(desloc)
                        tentativa[eixo] = max(
                            -DESLOCAMENTO_MAXIMO_GRAUS,
                            min(DESLOCAMENTO_MAXIMO_GRAUS, tentativa[eixo] + sinal * passo),
                        )
                        pen = self._penetracao(pose, lado, tentativa)

                        if pen < melhor_pen:
                            melhor, melhor_pen = tentativa, pen

                if melhor is not None:
                    break  # o menor passo que melhora vence (correção mínima)

            if melhor is None:
                break  # sem progresso (mínimo local ou limite): aceita o que há

            desloc[:] = melhor
            atual = melhor_pen

        if atual <= FOLGA_PENETRACAO_U and any(desloc):
            relaxado = [
                0.0 if abs(v * RELAXAMENTO_POR_QUADRO) < DESLOCAMENTO_DESPREZIVEL_GRAUS
                else v * RELAXAMENTO_POR_QUADRO
                for v in desloc
            ]

            if self._penetracao(pose, lado, relaxado) <= FOLGA_PENETRACAO_U:
                desloc[:] = relaxado

        return _com_deslocamento(pose, lado, desloc)

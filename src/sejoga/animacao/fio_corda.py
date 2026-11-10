"""Corda simulada do fio do fone: Verlet com ligações de comprimento.

O fio tem forma de Y: um ramo sai de cada orelha, os dois se juntam numa
junção livre no peito e uma haste desce até o aparelho de música na cintura.
Os três pontos de ponta (duas orelhas e o aparelho) são presos às âncoras; o
resto cai com a gravidade, dobra e encosta SÓ no corpo do mascote (caixas e
cápsulas recebidas a cada quadro). Não há colisão com chão nem borda de tela.

Também gera a malha do tubo (seção quadrada, faces planas) por funções puras,
para o renderer só copiar os vértices para o Panda3D.

FRONTEIRA: Python puro (``math`` e módulos puros do projeto).
"""

from __future__ import annotations

from itertools import pairwise
from math import copysign, sqrt

from sejoga.animacao import fio_tuning as tuning
from sejoga.animacao.primitivas_colisao import CaixaOrientada, Capsula

Vetor3 = tuple[float, float, float]

#: Lados da seção do tubo (quadrada: visual pixelado e barato).
LADOS_SECAO = 4
#: Vértices por segmento do tubo: 4 faces planas x 4 cantos.
VERTICES_POR_SEGMENTO = LADOS_SECAO * 4
#: Comprimento mínimo de vetor tratado como não degenerado.
EPSILON = 1e-9
#: Posição da haste (aparelho) na lista de cadeias e de âncoras.
ORDEM_HASTE = 2
#: Direção de escape quando o ponto cai exatamente no eixo de um colisor.
ESCAPE_PADRAO: Vetor3 = (0.0, 0.0, 1.0)


def _soma(a: Vetor3, b: Vetor3) -> Vetor3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vetor3, b: Vetor3) -> Vetor3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _esc(v: Vetor3, k: float) -> Vetor3:
    return (v[0] * k, v[1] * k, v[2] * k)


def _dot(a: Vetor3, b: Vetor3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cruz(a: Vetor3, b: Vetor3) -> Vetor3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norma(v: Vetor3) -> float:
    return sqrt(_dot(v, v))


def _normalizar(v: Vetor3, padrao: Vetor3 = ESCAPE_PADRAO) -> Vetor3:
    comprimento = _norma(v)

    if comprimento < EPSILON:
        return padrao

    return _esc(v, 1.0 / comprimento)


def _interpolar(a: Vetor3, b: Vetor3, t: float) -> Vetor3:
    return _soma(a, _esc(_sub(b, a), t))


# --------------------------------------------------------------------------- #
# Colisão ponto-colisor (empurra o centro da corda para fora)
# --------------------------------------------------------------------------- #
def empurrar_ponto_de_capsula(ponto: Vetor3, capsula: Capsula, folga: float) -> Vetor3:
    """Afasta ``ponto`` da cápsula até ficar ``folga`` além do raio dela."""
    eixo = _sub(capsula.b, capsula.a)
    comprimento_quadrado = _dot(eixo, eixo)
    t = 0.0

    if comprimento_quadrado > EPSILON:
        t = max(
            0.0, min(1.0, _dot(_sub(ponto, capsula.a), eixo) / comprimento_quadrado)
        )

    mais_proximo = _soma(capsula.a, _esc(eixo, t))
    saida = _sub(ponto, mais_proximo)
    limite = capsula.raio + folga

    if _norma(saida) >= limite:
        return ponto

    return _soma(mais_proximo, _esc(_normalizar(saida), limite))


def empurrar_ponto_de_caixa(
    ponto: Vetor3, caixa: CaixaOrientada, folga: float
) -> Vetor3:
    """Afasta ``ponto`` da caixa até ficar ``folga`` fora da superfície."""
    relativo = _sub(ponto, caixa.centro)
    locais = [_dot(relativo, eixo) for eixo in caixa.eixos]
    meias = caixa.meias_dim
    excessos = [abs(local) - meia for local, meia in zip(locais, meias, strict=True)]

    if max(excessos) > 0.0:
        destino = _destino_fora_da_caixa(locais, meias, folga)
    else:
        destino = _destino_saida_por_dentro(locais, meias, excessos, folga)

    if destino is None:
        return ponto

    resultado = caixa.centro

    for local, eixo in zip(destino, caixa.eixos, strict=True):
        resultado = _soma(resultado, _esc(eixo, local))

    return resultado


def _destino_fora_da_caixa(
    locais: list[float], meias: Vetor3, folga: float
) -> list[float] | None:
    """Ponto fora da caixa: só move se estiver mais perto que ``folga``."""
    presos = [
        max(-meia, min(meia, local)) for local, meia in zip(locais, meias, strict=True)
    ]
    delta = [local - preso for local, preso in zip(locais, presos, strict=True)]
    distancia = sqrt(sum(d * d for d in delta))

    if distancia >= folga:
        return None

    fator = folga / distancia
    return [preso + d * fator for preso, d in zip(presos, delta, strict=True)]


def _destino_saida_por_dentro(
    locais: list[float], meias: Vetor3, excessos: list[float], folga: float
) -> list[float]:
    """Ponto dentro da caixa: sai pela face mais próxima."""
    eixo_saida = max(range(len(excessos)), key=lambda i: excessos[i])
    destino = list(locais)
    destino[eixo_saida] = copysign(meias[eixo_saida] + folga, locais[eixo_saida] or 1.0)
    return destino


# --------------------------------------------------------------------------- #
# Corda
# --------------------------------------------------------------------------- #
class FioFone:
    """Corda em Y presa a duas orelhas e ao aparelho de música.

    Atributos públicos: ``posicoes`` (um ponto por partícula) e ``cadeias``
    (índices de cada ramo na ordem orelha esquerda, orelha direita e haste,
    todos terminando ou começando na junção).
    """

    def __init__(self, ancoras: tuple[Vetor3, Vetor3, Vetor3]) -> None:
        """Cria a corda reta entre as âncoras (orelha, orelha, aparelho)."""
        ramo = tuning.SEGMENTOS_RAMO_ORELHA
        haste = tuning.SEGMENTOS_HASTE
        self._indice_juncao = 2 * ramo
        self._indice_aparelho = 2 * ramo + haste
        total = self._indice_aparelho + 1
        self.cadeias = self._montar_cadeias(ramo, haste)
        self.posicoes: list[Vetor3] = [(0.0, 0.0, 0.0)] * total
        self._anteriores: list[Vetor3] = [(0.0, 0.0, 0.0)] * total
        self._acumulado = 0.0
        self._fixos = {0: 0, ramo: 1, self._indice_aparelho: 2}
        self._ligacoes = self._montar_ligacoes()
        self._dobras = self._montar_dobras()
        self.reiniciar(ancoras)

    def _montar_cadeias(self, ramo: int, haste: int) -> list[list[int]]:
        juncao = self._indice_juncao
        esquerda = [*range(ramo), juncao]
        direita = [*range(ramo, 2 * ramo), juncao]
        central = [juncao, *range(juncao + 1, juncao + haste + 1)]
        return [esquerda, direita, central]

    @staticmethod
    def _comprimento_do_segmento(ordem_da_cadeia: int) -> float:
        """Comprimento de repouso de cada segmento da cadeia (ramo ou haste)."""
        if ordem_da_cadeia == ORDEM_HASTE:
            return tuning.COMPRIMENTO_HASTE_U / tuning.SEGMENTOS_HASTE

        return tuning.COMPRIMENTO_RAMO_ORELHA_U / tuning.SEGMENTOS_RAMO_ORELHA

    def _montar_ligacoes(self) -> list[tuple[int, int, float]]:
        ligacoes = []

        for ordem, cadeia in enumerate(self.cadeias):
            comprimento = self._comprimento_do_segmento(ordem)
            ligacoes.extend((a, b, comprimento) for a, b in pairwise(cadeia))

        return ligacoes

    def _montar_dobras(self) -> list[tuple[int, int, float]]:
        dobras = []

        for ordem, cadeia in enumerate(self.cadeias):
            minimo = (
                2.0 * self._comprimento_do_segmento(ordem) * tuning.FRACAO_MINIMA_DOBRA
            )
            dobras.extend(
                (a, b, minimo) for a, b in zip(cadeia, cadeia[2:], strict=False)
            )

        return dobras

    def reiniciar(self, ancoras: tuple[Vetor3, Vetor3, Vetor3]) -> None:
        """Estica a corda em linhas retas entre as âncoras, sem velocidade."""
        esquerda, direita, aparelho = ancoras
        juncao = _esc(_soma(_soma(esquerda, direita), aparelho), 1.0 / 3.0)

        for ordem, cadeia in enumerate(self.cadeias):
            self._distribuir(cadeia, ancoras[ordem], juncao, ordem == ORDEM_HASTE)

        self._anteriores = list(self.posicoes)

    def _distribuir(
        self, cadeia: list[int], ponta: Vetor3, juncao: Vetor3, invertida: bool
    ) -> None:
        origem, destino = (juncao, ponta) if invertida else (ponta, juncao)
        passos = len(cadeia) - 1

        for ordem, indice in enumerate(cadeia):
            self.posicoes[indice] = _interpolar(origem, destino, ordem / passos)

    def atualizar(
        self,
        dt: float,
        ancoras: tuple[Vetor3, Vetor3, Vetor3],
        gravidade: Vetor3,
        caixas: list[CaixaOrientada],
        capsulas: list[Capsula],
    ) -> None:
        """Avança a corda ``dt`` segundos.

        ``gravidade`` é o vetor unitário de "para baixo" no mesmo referencial
        das âncoras e dos colisores.
        """
        if self._salto_grande(ancoras):
            self.reiniciar(ancoras)

        self._acumulado += max(0.0, min(dt, tuning.TEMPO_MAXIMO_QUADRO_FIO_S))

        while self._acumulado >= tuning.PASSO_FIO_S:
            self._acumulado -= tuning.PASSO_FIO_S
            self._passo_fixo(
                ancoras, _esc(gravidade, tuning.GRAVIDADE_FIO_U), caixas, capsulas
            )

    def _passo_fixo(
        self,
        ancoras: tuple[Vetor3, Vetor3, Vetor3],
        aceleracao: Vetor3,
        caixas: list[CaixaOrientada],
        capsulas: list[Capsula],
    ) -> None:
        self._integrar(tuning.PASSO_FIO_S, aceleracao)
        self._prender(ancoras)

        for iteracao in range(tuning.ITERACOES_FIO):
            self._resolver_ligacoes()
            self._prender(ancoras)

            # Colisão é a parte cara: só na metade e no fim, e o fim manda (a
            # corda nunca termina o quadro dentro do corpo).
            if iteracao in (tuning.ITERACOES_FIO // 2, tuning.ITERACOES_FIO - 1):
                self._colidir(caixas, capsulas)

    def _salto_grande(self, ancoras: tuple[Vetor3, Vetor3, Vetor3]) -> bool:
        for indice, ordem in self._fixos.items():
            if (
                _norma(_sub(self.posicoes[indice], ancoras[ordem]))
                > tuning.SALTO_REINICIO_FIO_U
            ):
                return True

        return False

    def _integrar(self, passo: float, aceleracao: Vetor3) -> None:
        mantida = tuning.VELOCIDADE_RESTANTE_POR_SEGUNDO**passo
        deslocamento_gravidade = _esc(aceleracao, passo * passo)

        for indice, atual in enumerate(self.posicoes):
            velocidade = _esc(_sub(atual, self._anteriores[indice]), mantida)
            self._anteriores[indice] = atual
            self.posicoes[indice] = _soma(
                _soma(atual, velocidade), deslocamento_gravidade
            )

    def _prender(self, ancoras: tuple[Vetor3, Vetor3, Vetor3]) -> None:
        for indice, ordem in self._fixos.items():
            self.posicoes[indice] = ancoras[ordem]
            self._anteriores[indice] = ancoras[ordem]

    def _resolver_ligacoes(self) -> None:
        for a, b, comprimento in self._ligacoes:
            self._corrigir_par(a, b, comprimento, 1.0, esticar=True)

        for a, b, minimo in self._dobras:
            self._corrigir_par(a, b, minimo, tuning.RIGIDEZ_DOBRA, esticar=False)

    def _corrigir_par(
        self, a: int, b: int, alvo: float, forca: float, *, esticar: bool
    ) -> None:
        """Move as duas partículas para a distância ``alvo`` (``esticar``: nos dois sentidos)."""
        diferenca = _sub(self.posicoes[b], self.posicoes[a])
        distancia = _norma(diferenca)

        if distancia < EPSILON or (not esticar and distancia >= alvo):
            return

        livres_a = a not in self._fixos
        livres_b = b not in self._fixos
        peso_total = livres_a + livres_b

        if peso_total == 0:
            return

        correcao = _esc(diferenca, forca * (distancia - alvo) / distancia / peso_total)

        if livres_a:
            self.posicoes[a] = _soma(self.posicoes[a], correcao)

        if livres_b:
            self.posicoes[b] = _sub(self.posicoes[b], correcao)

    def _colidir(self, caixas: list[CaixaOrientada], capsulas: list[Capsula]) -> None:
        folga = tuning.RAIO_COLISAO_FIO_U

        for indice, ponto in enumerate(self.posicoes):
            if indice in self._fixos:
                continue

            for capsula in capsulas:
                ponto = empurrar_ponto_de_capsula(ponto, capsula, folga)

            for caixa in caixas:
                ponto = empurrar_ponto_de_caixa(ponto, caixa, folga)

            self.posicoes[indice] = ponto

    def assentar(
        self,
        ancoras: tuple[Vetor3, Vetor3, Vetor3],
        gravidade: Vetor3,
        caixas: list[CaixaOrientada],
        capsulas: list[Capsula],
    ) -> None:
        """Roda a simulação por ``PASSOS_ASSENTAMENTO_FIO`` quadros até a corda cair."""
        for _ in range(tuning.PASSOS_ASSENTAMENTO_FIO):
            self.atualizar(tuning.PASSO_FIO_S, ancoras, gravidade, caixas, capsulas)

    def pontos_das_cadeias(self) -> list[list[Vetor3]]:
        """Pontos de cada ramo, na ordem de ``cadeias``."""
        return [[self.posicoes[i] for i in cadeia] for cadeia in self.cadeias]


# --------------------------------------------------------------------------- #
# Malha do tubo (seção quadrada, faces planas)
# --------------------------------------------------------------------------- #
def _quadro_do_ponto(
    pontos: list[Vetor3], indice: int, referencia: Vetor3
) -> tuple[Vetor3, Vetor3]:
    """Eixos ``u`` e ``v`` da seção no ponto, estáveis em relação à ``referencia``."""
    anterior = pontos[max(0, indice - 1)]
    proximo = pontos[min(len(pontos) - 1, indice + 1)]
    tangente = _normalizar(_sub(proximo, anterior), (0.0, 0.0, -1.0))
    lateral = _cruz(referencia, tangente)

    if _norma(lateral) < 1e-4:
        lateral = _cruz((1.0, 0.0, 0.0), tangente)

    u = _normalizar(lateral)
    v = _cruz(tangente, u)
    return u, v


def construir_tubo(
    pontos: list[Vetor3], referencia: Vetor3, raio: float
) -> tuple[list[Vetor3], list[Vetor3]]:
    """Vértices e normais (faces planas) do tubo que segue ``pontos``.

    Devolve ``VERTICES_POR_SEGMENTO`` vértices por segmento, na ordem usada por
    ``indices_dos_tubos``. As faces ficam em sentido anti-horário visto de fora.
    """
    cantos = ((1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0), (1.0, -1.0))
    normais_locais = ((0.0, 1.0), (-1.0, 0.0), (0.0, -1.0), (1.0, 0.0))
    quadros = [_quadro_do_ponto(pontos, i, referencia) for i in range(len(pontos))]
    vertices: list[Vetor3] = []
    normais: list[Vetor3] = []

    for i in range(len(pontos) - 1):
        for lado in range(LADOS_SECAO):
            vertices.extend(_face_do_tubo(pontos, quadros, i, lado, cantos, raio))
            nu, nv = normais_locais[lado]
            u_atual, v_atual = quadros[i]
            normal = _soma(_esc(u_atual, nu), _esc(v_atual, nv))
            normais.extend([normal] * 4)

    return vertices, normais


def _face_do_tubo(
    pontos: list[Vetor3],
    quadros: list[tuple[Vetor3, Vetor3]],
    i: int,
    lado: int,
    cantos: tuple[tuple[float, float], ...],
    raio: float,
) -> list[Vetor3]:
    """Quatro vértices (a, b, c, d) da face ``lado`` entre os anéis ``i`` e ``i+1``."""
    proximo_canto = (lado + 1) % LADOS_SECAO
    resultado = []

    for anel, canto in (
        (i, lado),
        (i, proximo_canto),
        (i + 1, proximo_canto),
        (i + 1, lado),
    ):
        u, v = quadros[anel]
        cu, cv = cantos[canto]
        deslocamento = _soma(_esc(u, cu * raio), _esc(v, cv * raio))
        resultado.append(_soma(pontos[anel], deslocamento))

    return resultado


def indices_dos_tubos(quantidades_de_pontos: list[int]) -> list[tuple[int, int, int]]:
    """Triângulos (a, b, c) e (a, c, d) de cada face, para tubos concatenados."""
    triangulos = []
    base = 0

    for quantidade in quantidades_de_pontos:
        for _ in range((quantidade - 1) * LADOS_SECAO):
            triangulos.append((base, base + 1, base + 2))
            triangulos.append((base, base + 2, base + 3))
            base += 4

    return triangulos

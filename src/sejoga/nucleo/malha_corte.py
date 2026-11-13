"""Recorte puro de malhas triangulares em faixas ao longo de um eixo.

Serve para dividir, em código e sem tocar no asset, cada dedo do mascote em
segmentos de uma cadeia articulada (base, meio, ponta). Os vértices são tuplas
planas ``(px, py, pz, nx, ny, nz, u, v, tx, ty, tz, tw)``; qualquer atributo é
interpolado linearmente no plano de corte, então a textura (NEAREST) continua a
mesma da malha original e o dedo reto fica idêntico ao recortado em pedaços.

FRONTEIRA: Python puro (só ``math``); NÃO importa Panda3D, Qt nem Win32.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, inf, radians, sqrt, tan

Vertice = tuple[float, ...]
Triangulo = tuple[Vertice, Vertice, Vertice]
Vec3 = tuple[float, float, float]

#: Posição dos atributos dentro da tupla do vértice.
POS = slice(0, 3)
NORMAL = slice(3, 6)
UV = slice(6, 8)
TANGENTE = slice(8, 12)
ATRIBUTOS_POR_VERTICE = 12

#: Distância (u) abaixo da qual um vértice é considerado sobre o plano.
TOLERANCIA_PLANO = 1e-6
#: Área² mínima de um triângulo para não ser descartado como degenerado.
AREA2_MINIMA = 1e-14
#: Origem dos planos de corte (as distâncias são relativas a ela).
ORIGEM: Vec3 = (0.0, 0.0, 0.0)

#: Semente e iterações da iteração de potência do eixo principal.
SEMENTE_EIXO_PRINCIPAL: Vec3 = (1.0, 0.37, 0.21)
ITERACOES_EIXO_PRINCIPAL = 60

#: Tangente padrão das tampas quando a malha original não traz tangente.
TANGENTE_PADRAO = (1.0, 0.0, 0.0, 1.0)

#: Casas decimais para tratar posições como iguais ao deduplicar.
CASAS_POSICAO_UNICA = 6
#: Se |direcao.z| passar disto, o vetor ajudante da tampa deixa de ser Z.
LIMITE_PARALELO_AJUDANTE = 0.9


def _distancia(v: Vertice, origem: Vec3, direcao: Vec3) -> float:
    return (
        (v[0] - origem[0]) * direcao[0]
        + (v[1] - origem[1]) * direcao[1]
        + (v[2] - origem[2]) * direcao[2]
    )


def _interpolar(a: Vertice, b: Vertice, t: float) -> Vertice:
    return tuple(x + (y - x) * t for x, y in zip(a, b, strict=True))


def _cortar_poligono(
    poligono: list[Vertice],
    origem: Vec3,
    direcao: Vec3,
    limite: float,
    manter_acima: bool,
) -> list[Vertice]:
    """Sutherland-Hodgman contra o plano ``dist == limite``."""
    sinal = 1.0 if manter_acima else -1.0
    saida: list[Vertice] = []

    for atual, proximo in zip(poligono, poligono[1:] + poligono[:1], strict=True):
        da = sinal * (_distancia(atual, origem, direcao) - limite)
        db = sinal * (_distancia(proximo, origem, direcao) - limite)

        if da >= 0:
            saida.append(atual)

        if (da >= 0) != (db >= 0):
            saida.append(_interpolar(atual, proximo, da / (da - db)))

    return saida


def _area2(a: Vertice, b: Vertice, c: Vertice) -> float:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx

    return cx * cx + cy * cy + cz * cz


def recortar_faixa(
    triangulos: list[Triangulo],
    origem: Vec3,
    direcao: Vec3,
    s_min: float = -inf,
    s_max: float = inf,
) -> list[Triangulo]:
    """Parte dos triângulos com ``s_min <= dist <= s_max`` (``dist`` ao longo de ``direcao``).

    A malha recortada fica ABERTA nos planos de corte (use ``tampa_no_plano``).
    """
    resultado: list[Triangulo] = []

    for triangulo in triangulos:
        poligono = list(triangulo)

        if s_min > -inf:
            poligono = _cortar_poligono(poligono, origem, direcao, s_min, True)

        if len(poligono) >= 3 and s_max < inf:
            poligono = _cortar_poligono(poligono, origem, direcao, s_max, False)

        for i in range(1, len(poligono) - 1):
            a, b, c = poligono[0], poligono[i], poligono[i + 1]

            if _area2(a, b, c) > AREA2_MINIMA:
                resultado.append((a, b, c))

    return resultado


def pontos_no_plano(
    triangulos: list[Triangulo], origem: Vec3, direcao: Vec3, s: float
) -> list[Vec3]:
    """Posições únicas dos vértices sobre o plano ``dist == s``."""
    vistos: dict[tuple[float, float, float], Vec3] = {}

    for triangulo in triangulos:
        for v in triangulo:
            if abs(_distancia(v, origem, direcao) - s) <= TOLERANCIA_PLANO:
                p = (v[0], v[1], v[2])
                vistos[
                    (
                        round(p[0], CASAS_POSICAO_UNICA),
                        round(p[1], CASAS_POSICAO_UNICA),
                        round(p[2], CASAS_POSICAO_UNICA),
                    )
                ] = p

    return list(vistos.values())


def centro(pontos: list[Vec3]) -> Vec3:
    """Média dos pontos (a seção da lâmina é convexa)."""
    n = len(pontos)

    return (
        sum(p[0] for p in pontos) / n,
        sum(p[1] for p in pontos) / n,
        sum(p[2] for p in pontos) / n,
    )


def centro_da_caixa(pontos: list[Vec3]) -> Vec3:
    """Centro da caixa envolvente: não depende de quantos vértices o corte criou."""
    return (
        (min(p[0] for p in pontos) + max(p[0] for p in pontos)) / 2.0,
        (min(p[1] for p in pontos) + max(p[1] for p in pontos)) / 2.0,
        (min(p[2] for p in pontos) + max(p[2] for p in pontos)) / 2.0,
    )


def extensao(pontos: list[Vec3], vetor: Vec3) -> float:
    """Largura dos pontos projetados em ``vetor`` (unitário)."""
    projecoes = [p[0] * vetor[0] + p[1] * vetor[1] + p[2] * vetor[2] for p in pontos]

    return max(projecoes) - min(projecoes)


def faixa_de_distancias(
    triangulos: list[Triangulo], origem: Vec3, direcao: Vec3
) -> tuple[float, float]:
    """``(menor, maior)`` distância dos vértices ao longo de ``direcao``."""
    d = [_distancia(v, origem, direcao) for t in triangulos for v in t]

    return min(d), max(d)


def uv_da_face(
    triangulos: list[Triangulo], direcao: Vec3, sinal: float
) -> tuple[float, float]:
    """UV médio da face cuja normal mais se alinha a ``sinal * direcao``.

    É a cor da "tampa" original do dedo, reaproveitada nas tampas internas.
    """
    melhor, melhor_ponto = -inf, (0.0, 0.0)

    for t in triangulos:
        n = t[0][NORMAL]
        alinhamento = sinal * (
            n[0] * direcao[0] + n[1] * direcao[1] + n[2] * direcao[2]
        )

        if alinhamento > melhor:
            melhor = alinhamento
            melhor_ponto = (
                sum(v[6] for v in t) / 3.0,
                sum(v[7] for v in t) / 3.0,
            )

    return melhor_ponto


def tampa_no_plano(
    triangulos: list[Triangulo],
    origem: Vec3,
    direcao: Vec3,
    s: float,
    sinal: float,
    uv: tuple[float, float],
) -> list[Triangulo]:
    """Fecha o corte em ``dist == s`` com um leque; normal ``sinal * direcao``.

    ``sinal=-1`` fecha a face de raiz do segmento, ``+1`` a face da ponta.
    """
    pontos = pontos_no_plano(triangulos, origem, direcao, s)

    if len(pontos) < 3:
        return []

    c = centro(pontos)
    ajudante = (
        (0.0, 0.0, 1.0)
        if abs(direcao[2]) < LIMITE_PARALELO_AJUDANTE
        else (1.0, 0.0, 0.0)
    )
    u1 = _normalizar(_vetorial(ajudante, direcao))
    u2 = _vetorial(direcao, u1)
    pontos.sort(key=lambda p: atan2(_escalar(_sub(p, c), u2), _escalar(_sub(p, c), u1)))

    normal = (direcao[0] * sinal, direcao[1] * sinal, direcao[2] * sinal)

    def vertice(p: Vec3) -> Vertice:
        return (*p, *normal, *uv, *TANGENTE_PADRAO)

    leque: list[Triangulo] = []

    for i, p in enumerate(pontos):
        q = pontos[(i + 1) % len(pontos)]
        a, b = (p, q) if sinal > 0 else (q, p)
        leque.append((vertice(c), vertice(a), vertice(b)))

    return leque


def sobreposicao(
    espessura: float,
    angulo_projeto_graus: float,
    comprimento_vizinho: float,
    fracao_maxima: float,
) -> float:
    """Extensão ``e = (t/2) * tan(θ/2)`` que tampa a cunha externa da junta.

    Limitada a ``fracao_maxima`` do segmento vizinho para não atravessá-lo.
    """
    e = (espessura / 2.0) * tan(radians(angulo_projeto_graus) / 2.0)

    return min(e, comprimento_vizinho * fracao_maxima)


def eixo_principal(pontos: list[Vec3]) -> Vec3:
    """Direção de maior variância (PCA 3D por iteração de potência, unitária).

    Serve para o eixo longo de dedos retos, inclusive o polegar (estendido em Z).
    """
    # Posições únicas: vértices repetidos por triângulo enviesariam a covariância.
    unicos = list(
        {
            (
                round(p[0], CASAS_POSICAO_UNICA),
                round(p[1], CASAS_POSICAO_UNICA),
                round(p[2], CASAS_POSICAO_UNICA),
            ): p
            for p in pontos
        }.values()
    )
    c = centro(unicos)
    d = [_sub(p, c) for p in unicos]
    cov = [[sum(v[i] * v[j] for v in d) for j in range(3)] for i in range(3)]
    x: Vec3 = _normalizar(SEMENTE_EIXO_PRINCIPAL)

    for _ in range(ITERACOES_EIXO_PRINCIPAL):
        x = _normalizar(
            tuple(sum(cov[i][j] * x[j] for j in range(3)) for i in range(3))  # type: ignore[arg-type]
        )

    return x


def orientar_para_ponta(eixo: Vec3, pontos: list[Vec3], origem_mao: Vec3) -> Vec3:
    """Inverte ``eixo`` se necessário para apontar da mão (``origem_mao``) à ponta."""
    c = centro(pontos)

    if _escalar(_sub(c, origem_mao), eixo) < 0:
        return (-eixo[0], -eixo[1], -eixo[2])

    return eixo


def ortogonalizar(eixo: Vec3, direcao: Vec3) -> Vec3:
    """Componente de ``eixo`` perpendicular a ``direcao`` (unitário)."""
    k = _escalar(eixo, direcao)

    return _normalizar(
        (eixo[0] - k * direcao[0], eixo[1] - k * direcao[1], eixo[2] - k * direcao[2])
    )


def eixo_de_flexao(direcao: Vec3) -> Vec3:
    """Eixo da dobradiça: produto vetorial ``cima`` por ``direcao``. Ângulo POSITIVO fecha.

    Em repouso a palma olha para baixo (-Z); com ``cima`` x ``direcao`` a ponta
    desce (regra da mão direita). Para o dedo direito (``direcao = +X``) isso é
    ``+Y`` (= ``setR`` positivo); para o esquerdo, ``-Y``: o espelho cai sozinho.
    """
    return _normalizar(_vetorial((0.0, 0.0, 1.0), direcao))


@dataclass(frozen=True)
class SegmentoCortado:
    """Um segmento da cadeia: triângulos (coords originais) e pivô da sua junta."""

    triangulos: list[Triangulo]
    pivo: Vec3
    superficie: tuple[Triangulo, ...] = ()
    tampas: tuple[Triangulo, ...] = ()


def _secao(triangulos: list[Triangulo], direcao: Vec3, s: float) -> list[Vec3]:
    corte = recortar_faixa(triangulos, ORIGEM, direcao, s_min=s)

    return pontos_no_plano(corte, ORIGEM, direcao, s)


def cortar_cadeia(
    triangulos: list[Triangulo],
    direcao: Vec3,
    eixo: Vec3,
    fracoes: tuple[float, ...],
    angulo_projeto_graus: float,
    fracao_maxima: float,
    fracao_secao_raiz: float,
) -> list[SegmentoCortado]:
    """Divide um dedo reto em ``len(fracoes)`` segmentos de cadeia, com sobreposição.

    ``direcao``: unitário da raiz à ponta. ``eixo``: dobradiça (⟂ a ``direcao``).
    O segmento k vai da sua junta até a junta k+1 MAIS ``e`` sobre o vizinho
    (mesma malha original, UV continuada), tampando a cunha externa ao dobrar.
    """
    eixo = ortogonalizar(eixo, direcao)
    s_baixo, s_alto = faixa_de_distancias(triangulos, ORIGEM, direcao)
    comprimento = s_alto - s_baixo
    juntas = [s_baixo]

    for f in fracoes[:-1]:
        juntas.append(juntas[-1] + f * comprimento)

    fins = [*juntas[1:], s_alto]
    todos = [(v[0], v[1], v[2]) for t in triangulos for v in t]
    cima = _normalizar(_vetorial(eixo, direcao))
    espessura = extensao(todos, cima)
    extensoes = [0.0] + [
        sobreposicao(
            espessura, angulo_projeto_graus, fins[k] - juntas[k], fracao_maxima
        )
        for k in range(1, len(fracoes))
    ]
    uv_raiz = uv_da_face(triangulos, direcao, -1.0)
    uv_ponta = uv_da_face(triangulos, direcao, 1.0)
    ultimo = len(fracoes) - 1
    segmentos: list[SegmentoCortado] = []

    for k in range(len(fracoes)):
        s_min = -inf if k == 0 else juntas[k]
        s_max = inf if k == ultimo else fins[k] + extensoes[k + 1]
        faixa = recortar_faixa(triangulos, ORIGEM, direcao, s_min, s_max)
        superficie = tuple(faixa)
        tampas: list[Triangulo] = []

        if k > 0:
            tampas += tampa_no_plano(faixa, ORIGEM, direcao, juntas[k], -1.0, uv_raiz)

        if k < ultimo:
            tampas += tampa_no_plano(faixa, ORIGEM, direcao, s_max, 1.0, uv_ponta)

        s_pivo = juntas[0] + fracao_secao_raiz * comprimento if k == 0 else juntas[k]
        pontos = _secao(triangulos, direcao, s_pivo)
        segmentos.append(
            SegmentoCortado(
                faixa + tampas,
                centro_da_caixa(pontos),
                superficie=superficie,
                tampas=tuple(tampas),
            )
        )

    return segmentos


# --------------------------------------------------------------------------- #
# Vetores mínimos
# --------------------------------------------------------------------------- #
def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _escalar(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vetorial(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalizar(v: Vec3) -> Vec3:
    n = sqrt(_escalar(v, v))

    if n < 1e-12:
        return (0.0, 0.0, 0.0)

    return (v[0] / n, v[1] / n, v[2] / n)

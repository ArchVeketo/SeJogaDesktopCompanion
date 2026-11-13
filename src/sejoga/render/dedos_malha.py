"""Fatia em código os dedos do asset numa cadeia de pivôs (base, meio, ponta).

O GLTF fica intacto: cada dedo é um bloco reto (``meshN``) e aqui ele é cortado
em faixas ao longo do comprimento (``nucleo.malha_corte``), interpolando posição,
normal, UV e tangente no plano de corte. Cada faixa vira um ``GeomNode`` filho de
um pivô; os pivôs formam uma cadeia, então girar a junta da base leva o resto.
Roda ANTES do ``copyTo`` do contorno, que herda a cadeia.

Cada pivô guarda no tag ``TAG_EIXO`` o eixo de dobra no referencial do pivô.
"""

from __future__ import annotations

import math

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexReader,
    GeomVertexWriter,
    InternalName,
    NodePath,
    Quat,
    Vec3,
)

from sejoga.animacao import dedos_tuning as tuning_dedos
from sejoga.nucleo import malha_corte as mc

TAG_EIXO = "eixo-dobra"
TAG_ABERTURA = "eixo-abertura"
TAG_COMPRIMENTO = "eixo-comprimento"
NOME_JUNTA = "dedo-{mesh}-junta{junta}"
NOME_MALHA = "mesh{mesh}"
#: Índice do dedo médio na tupla de malhas da mão (eixo longitudinal mais limpo dos 4 dedos).
INDICE_REFERENCIA_LONGO = 2
INDICE_REFERENCIA_EIXO = 1
INDICE_POLEGAR = 0
#: Nomes das colunas do asset (o UV do glTF é ``texcoord.0``).
_COLUNAS = ("vertex", "normal", "texcoord.0", "tangent")


def nome_junta(mesh: int, junta: int) -> str:
    """Monta o nome do nó da junta ``junta`` do dedo ``mesh``."""
    return NOME_JUNTA.format(mesh=mesh, junta=junta)


def _ler_vertice(linha: int, leitores: dict, tem_tangente: bool) -> tuple:
    """Lê posição, normal, UV e tangente da linha ``linha`` dos dados de vértice."""
    for leitor in leitores.values():
        leitor.setRow(linha)

    p = leitores["vertex"].getData3()
    n = leitores["normal"].getData3()
    uv = leitores["texcoord.0"].getData2()
    tan = leitores["tangent"].getData4() if tem_tangente else mc.TANGENTE_PADRAO
    return (p.x, p.y, p.z, n.x, n.y, n.z, uv.x, uv.y, *tan)


def _ler_triangulos(geom_node: GeomNode) -> list[mc.Triangulo]:
    geom = geom_node.getGeom(0)
    dados = geom.getVertexData()
    formato = dados.getFormat()
    tem_tangente = formato.hasColumn(InternalName.make("tangent"))
    leitores = {
        nome: GeomVertexReader(dados, nome)
        for nome in _COLUNAS
        if nome != "tangent" or tem_tangente
    }
    triangulos: list[mc.Triangulo] = []

    for i in range(geom.getNumPrimitives()):
        primitiva = geom.getPrimitive(i).decompose()

        for inicio in range(0, primitiva.getNumVertices(), 3):
            vertices = [
                _ler_vertice(primitiva.getVertex(k), leitores, tem_tangente)
                for k in range(inicio, inicio + 3)
            ]
            triangulos.append((vertices[0], vertices[1], vertices[2]))

    return triangulos


def _montar_geom(
    modelo: Geom, triangulos: list[mc.Triangulo], deslocamento: mc.Vec3
) -> Geom:
    formato = modelo.getVertexData().getFormat()
    dados = GeomVertexData("dedo", formato, Geom.UHStatic)
    dados.setNumRows(len(triangulos) * 3)
    escritores = {nome: GeomVertexWriter(dados, nome) for nome in _COLUNAS}
    ox, oy, oz = deslocamento

    for triangulo in triangulos:
        for v in triangulo:
            escritores["vertex"].addData3(v[0] - ox, v[1] - oy, v[2] - oz)
            escritores["normal"].addData3(v[3], v[4], v[5])
            escritores["texcoord.0"].addData2(v[6], v[7])
            escritores["tangent"].addData4(v[8], v[9], v[10], v[11])

    primitiva = GeomTriangles(Geom.UHStatic)
    primitiva.addConsecutiveVertices(0, len(triangulos) * 3)
    primitiva.closePrimitive()
    geom = Geom(dados)
    geom.addPrimitive(primitiva)

    return geom


def _para_tupla(v: Vec3) -> mc.Vec3:
    return (float(v.x), float(v.y), float(v.z))


def _direcao_longitudinal_malha(model_np: NodePath, mesh: int) -> tuple[NodePath, mc.Vec3] | None:
    malha = model_np.find("**/" + NOME_MALHA.format(mesh=mesh))
    if malha.isEmpty():
        return None
    pai = malha.getParent()
    triangulos = _ler_triangulos(malha.node())
    pontos = [(v[0], v[1], v[2]) for t in triangulos for v in t]
    origem_mao = _para_tupla(pai.getParent().getPos(pai))
    direcao = mc.orientar_para_ponta(mc.eixo_principal(pontos), pontos, origem_mao)
    return pai, direcao


def _fatiar_malha(  # noqa: PLR0915
    model_np: NodePath,
    mesh: int,
    fracoes: tuple[float, ...],
    referencia_longitudinal: tuple[NodePath, mc.Vec3] | None = None,
    pronacao_graus: float = 0.0,
) -> None:
    """Troca a malha do dedo por uma cadeia que dobra no eixo dela."""
    malha = model_np.find("**/" + NOME_MALHA.format(mesh=mesh))

    if malha.isEmpty():
        return None

    pai = malha.getParent()
    geom_node = malha.node()
    triangulos = _ler_triangulos(geom_node)
    pontos = [(v[0], v[1], v[2]) for t in triangulos for v in t]
    origem_mao = _para_tupla(pai.getParent().getPos(pai))
    if referencia_longitudinal is not None:
        ref_pai, ref_dir = referencia_longitudinal
        eixo_local = _para_tupla(pai.getRelativeVector(ref_pai, Vec3(*ref_dir)))
        direcao = mc.orientar_para_ponta(eixo_local, pontos, origem_mao)
    else:
        direcao = mc.orientar_para_ponta(mc.eixo_principal(pontos), pontos, origem_mao)

    eixo = mc.eixo_de_flexao(direcao)

    segmentos = mc.cortar_cadeia(
        triangulos,
        direcao,
        eixo,
        fracoes,
        tuning_dedos.ANGULO_PROJETO_SOBREPOSICAO_GRAUS,
        tuning_dedos.FRACAO_MAXIMA_SOBREPOSICAO,
        tuning_dedos.FRACAO_SECAO_DA_RAIZ,
    )
    modelo = geom_node.getGeom(0)
    estado = geom_node.getGeomState(0)
    anterior: NodePath = pai
    pivo_anterior: mc.Vec3 = (0.0, 0.0, 0.0)
    eixo_dobra = Vec3(*mc.ortogonalizar(eixo, direcao))
    eixo_abertura = Vec3(*direcao).cross(eixo_dobra)
    eixo_abertura.normalize()
    if pronacao_graus:
        # Pronação anatômica simétrica (direita -X, esquerda +X) faz a flexão
        # do polegar dobrar em direção à palma/indicador em vez de cair reto em -Z.
        phi = math.radians(pronacao_graus)
        c, s = math.cos(phi), math.sin(phi)
        sinal_lado = 1.0 if direcao[0] < 0.0 else -1.0
        eixo_dobra = eixo_dobra * c + eixo_abertura * (sinal_lado * s)
        eixo_dobra.normalize()

    for k, segmento in enumerate(segmentos):
        pivo = anterior.attachNewNode(nome_junta(mesh, k))
        pivo.setPos(*(c - a for c, a in zip(segmento.pivo, pivo_anterior, strict=True)))
        pivo.setTag(TAG_EIXO, " ".join(map(str, eixo_dobra)))
        pivo.setTag(TAG_COMPRIMENTO, " ".join(map(str, direcao)))
        if k == 0:
            pivo.setTag(TAG_ABERTURA, " ".join(map(str, eixo_abertura)))
        superficie = list(segmento.superficie or segmento.triangulos)
        no = GeomNode(NOME_MALHA.format(mesh=mesh) + f"-seg{k}")
        no.addGeom(_montar_geom(modelo, superficie, segmento.pivo), estado)
        pivo.attachNewNode(no)
        # Tampas internas dos cortes ficam num nó separado para serem removidas
        # do contorno (evita pontas rosas extrudadas ao dobrar os dedos).
        if segmento.tampas:
            no_tampa = GeomNode(NOME_MALHA.format(mesh=mesh) + f"-seg{k}-tampa")
            no_tampa.addGeom(_montar_geom(modelo, list(segmento.tampas), segmento.pivo), estado)
            pivo.attachNewNode(no_tampa)
        anterior, pivo_anterior = pivo, segmento.pivo

    malha.removeNode()


def pivos_da_cadeia(raiz: NodePath, mesh: int) -> list[tuple[NodePath, Vec3]]:
    """Pivôs `(nó, eixo de dobra)` do dedo `mesh`, da base à ponta."""
    cadeia = []
    k = 0

    while not (pivo := raiz.find("**/" + nome_junta(mesh, k))).isEmpty():
        cadeia.append((pivo, Vec3(*(float(c) for c in pivo.getTag(TAG_EIXO).split()))))
        k += 1

    return cadeia


def eixo_abertura(pivo: NodePath) -> Vec3:
    """Normal ao plano da palma na base do dedo."""
    return Vec3(*(float(c) for c in pivo.getTag(TAG_ABERTURA).split()))


def girar_pivo(
    pivo: NodePath, eixo: Vec3, graus: float, abertura: float = 0.0,
    normal_palmar: Vec3 | None = None,
) -> None:
    """Gira o pivô em ``graus`` em torno do eixo dado com abertura palmar."""
    rotacao = Quat()
    rotacao.setFromAxisAngle(graus, eixo)
    if normal_palmar is not None:
        leque = Quat()
        leque.setFromAxisAngle(abertura, normal_palmar)
        rotacao *= leque
    pivo.setQuat(rotacao)


def medir_direcao_polegar(renderer) -> Vec3:
    """Direção longitudinal do polegar direito em coordenadas da mão."""
    hand = renderer._rig_nodes.get("hand")
    thumb_mesh = renderer.model_np.find("**/mesh32")
    if hand is not None and not thumb_mesh.isEmpty():
        bounds = thumb_mesh.getTightBounds(hand)
        pivots = pivos_da_cadeia(renderer.model_np, 32)
        if bounds and pivots:
            base = pivots[0][0].getPos(hand)
            center = (bounds[0] + bounds[1]) * 0.5
            vec = center - base
            if vec.lengthSquared() > 1e-6:
                vec.normalize()
                return vec
    vec = Vec3(0.713, 0.673, -0.194)
    vec.normalize()
    return vec


def alinhar_pulso_polegar(hand: NodePath, model_np: NodePath, thumb_local_dir: Vec3, presentation: float) -> None:
    """Alinha o eixo real do polegar à vertical do modelo para joinha/pistolinha."""
    from math import acos, degrees

    alvo = hand.getRelativeVector(model_np, (0, -0.12, 1.0))
    if alvo.lengthSquared() <= 1e-5:
        return
    alvo.normalize()
    dot = max(-1.0, min(1.0, thumb_local_dir.dot(alvo)))
    eixo = thumb_local_dir.cross(alvo)
    if eixo.lengthSquared() > 1e-7:
        eixo.normalize()
        angulo = degrees(acos(dot))
    else:
        eixo = Vec3(0, 0, 1) if dot < 0.0 else Vec3(0, 1, 0)
        angulo = 180.0 if dot < 0.0 else 0.0
    dq = Quat()
    dq.setFromAxisAngle(angulo * presentation, eixo)
    hand.setQuat(hand, dq)


def fatiar_dedos(model_np: NodePath) -> None:
    """Fatia os 5 dedos de cada mão com eixo consistente nos dedos longos."""
    for meshes in (tuning_dedos.MESH_DEDOS_DIREITA, tuning_dedos.MESH_DEDOS_ESQUERDA):
        ref_longa = _direcao_longitudinal_malha(
            model_np, meshes[INDICE_REFERENCIA_LONGO]
        )
        ordem = [*meshes[INDICE_REFERENCIA_EIXO:], meshes[INDICE_POLEGAR]]

        for mesh in ordem:
            polegar = mesh == meshes[INDICE_POLEGAR]
            fracoes = (
                tuning_dedos.FRACOES_SEGMENTOS_POLEGAR
                if polegar
                else tuning_dedos.FRACOES_SEGMENTOS_DEDO
            )
            _fatiar_malha(
                model_np,
                mesh,
                fracoes,
                referencia_longitudinal=None if polegar else ref_longa,
                pronacao_graus=tuning_dedos.PRONACAO_POLEGAR_GRAUS if polegar else 0.0,
            )

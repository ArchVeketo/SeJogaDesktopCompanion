"""Fatia em código os dedos do asset numa cadeia de pivôs (base, meio, ponta).

O GLTF fica intacto: cada dedo é um bloco reto (``meshN``) e aqui ele é cortado
em faixas ao longo do comprimento (``nucleo.malha_corte``), interpolando posição,
normal, UV e tangente no plano de corte. Cada faixa vira um ``GeomNode`` filho de
um pivô; os pivôs formam uma cadeia, então girar a junta da base leva o resto.
Roda ANTES do ``copyTo`` do contorno, que herda a cadeia.

Cada pivô guarda no tag ``TAG_EIXO`` o eixo de dobra no referencial do pivô.
"""

from __future__ import annotations

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
NOME_JUNTA = "dedo-{mesh}-junta{junta}"
NOME_MALHA = "mesh{mesh}"
#: Índice do indicador na tupla de malhas da mão: define o eixo de dobra do polegar.
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


def _fatiar_malha(  # noqa: PLR0915  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
    model_np: NodePath,
    mesh: int,
    fracoes: tuple[float, ...],
    eixo_modelo: mc.Vec3 | None,
) -> mc.Vec3 | None:
    """Troca ``meshN`` pela cadeia de pivôs. Devolve o eixo de dobra no referencial do modelo."""
    malha = model_np.find("**/" + NOME_MALHA.format(mesh=mesh))

    if malha.isEmpty():
        return None

    pai = malha.getParent()
    geom_node = malha.node()
    triangulos = _ler_triangulos(geom_node)
    pontos = [(v[0], v[1], v[2]) for t in triangulos for v in t]
    origem_mao = _para_tupla(pai.getParent().getPos(pai))
    direcao = mc.orientar_para_ponta(mc.eixo_principal(pontos), pontos, origem_mao)

    if eixo_modelo is None:
        eixo = mc.eixo_de_flexao(direcao)
        eixo_modelo = _para_tupla(model_np.getRelativeVector(pai, Vec3(*eixo)))
    else:
        eixo = _para_tupla(pai.getRelativeVector(model_np, Vec3(*eixo_modelo)))

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
    eixo_local = " ".join(repr(c) for c in mc.ortogonalizar(eixo, direcao))

    for k, segmento in enumerate(segmentos):
        pivo = anterior.attachNewNode(nome_junta(mesh, k))
        pivo.setPos(*(c - a for c, a in zip(segmento.pivo, pivo_anterior, strict=True)))
        pivo.setTag(TAG_EIXO, eixo_local)
        no = GeomNode(NOME_MALHA.format(mesh=mesh) + f"-seg{k}")
        no.addGeom(_montar_geom(modelo, segmento.triangulos, segmento.pivo), estado)
        pivo.attachNewNode(no)
        anterior, pivo_anterior = pivo, segmento.pivo

    malha.removeNode()

    return eixo_modelo


def pivos_da_cadeia(raiz: NodePath, mesh: int) -> list[tuple[NodePath, Vec3]]:
    """Pivôs `(nó, eixo de dobra)` do dedo `mesh`, da base à ponta."""
    cadeia = []
    k = 0

    while not (pivo := raiz.find("**/" + nome_junta(mesh, k))).isEmpty():
        cadeia.append((pivo, Vec3(*(float(c) for c in pivo.getTag(TAG_EIXO).split()))))
        k += 1

    return cadeia


def girar_pivo(pivo: NodePath, eixo: Vec3, graus: float) -> None:
    """Gira o pivô em ``graus`` em torno do eixo dado."""
    rotacao = Quat()
    rotacao.setFromAxisAngle(graus, eixo)
    pivo.setQuat(rotacao)


def fatiar_dedos(model_np: NodePath) -> None:
    """Fatia os 5 dedos de cada mão (polegar por último, com o eixo do indicador)."""
    for meshes in (tuning_dedos.MESH_DEDOS_DIREITA, tuning_dedos.MESH_DEDOS_ESQUERDA):
        eixo_mao: mc.Vec3 | None = None
        ordem = [*meshes[INDICE_REFERENCIA_EIXO:], meshes[INDICE_POLEGAR]]

        for mesh in ordem:
            polegar = mesh == meshes[INDICE_POLEGAR]
            fracoes = (
                tuning_dedos.FRACOES_SEGMENTOS_POLEGAR
                if polegar
                else tuning_dedos.FRACOES_SEGMENTOS_DEDO
            )
            resultado = _fatiar_malha(
                model_np, mesh, fracoes, eixo_mao if polegar else None
            )

            if not polegar and eixo_mao is None:
                eixo_mao = resultado

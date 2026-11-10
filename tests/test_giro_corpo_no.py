"""Fiação do nó ``body_facing`` do GIRO DE CORPO LIMITADO no grafo de cena.

Testa a mecânica do giro no grafo (sem GPU: só matemática de NodePath) e a
INDEPENDÊNCIA dos nós: girar o corpo não mexe no tilt de voo (model_anchor)
nem no pivô de arraste (_suspension_pivot). O visual (franja/flicker em perfil)
é validado na GPU; aqui garantimos a mecânica do grafo e os limites.

Nota: ``panda3d.core`` é importado DENTRO de cada teste, não no topo do módulo.
Carregar a extensão C do Panda3D durante a coleta, antes dos testes de diálogo
Qt (PySide6), provoca uma violação de acesso no processo — a mesma fragilidade
de DLL Panda3D x Qt documentada no AGENTS.md. Importar tarde preserva a ordem
que já funciona. Também NÃO importamos ``Panda3DRenderer`` (puxa simplepbr/GPU);
reproduzimos a MESMA fiação e a MESMA transformação translate-rotate-translate
de ``Panda3DRenderer._aplicar_giro_corpo``, mantendo o teste leve e estável.
"""

from sejoga.animacao.movimento_corpo import GiroCorpo

# Correção de export espelhada de ``Panda3DRenderer.MODEL_FACING_HEADING``: a
# malha nasce apontando para +Y e o setH base mostra o rosto para a câmera.
MODEL_FACING_HEADING = 180


def _novo_grafo():
    """Reconstrói o grafo do renderer sem GPU e devolve os nós + o giro.

    model_anchor -> suspension_pivot -> body_facing -> model_np, exatamente
    como ``apply_body_motion`` monta.
    """
    from panda3d.core import NodePath

    model_anchor = NodePath("mascot-motion-root")
    suspension_pivot = model_anchor.attachNewNode("suspension-pivot")
    body_facing = suspension_pivot.attachNewNode("body-facing")
    model_np = body_facing.attachNewNode("model")
    model_np.setH(MODEL_FACING_HEADING)
    return {
        "model_anchor": model_anchor,
        "suspension_pivot": suspension_pivot,
        "body_facing": body_facing,
        "model_np": model_np,
        "giro": GiroCorpo(),
    }


def _girar(grafo, dt, *, direcao_olhar=0.0, angulo_pedido=None, dragging=False):
    from panda3d.core import Mat4, Point3, TransformState, Vec3

    olhar = 0.0 if dragging else direcao_olhar
    pedido = None if dragging else angulo_pedido
    angulo = grafo["giro"].update(dt, direcao_olhar=olhar, angulo_pedido=pedido)
    body_facing = grafo["body_facing"]
    if abs(angulo) < 0.01:
        body_facing.setMat(Mat4.identMat())
        return
    pivot = body_facing.getRelativePoint(grafo["model_np"], Point3(0, 0, 0.44))
    rotacao = TransformState.makeHpr(Vec3(angulo, 0, 0)).getMat()
    body_facing.setMat(Mat4.translateMat(-pivot) * rotacao * Mat4.translateMat(pivot))


def _assentar(grafo, *, frames=240, **kwargs):
    for _ in range(frames):
        _girar(grafo, 1 / 60, **kwargs)


def test_no_body_facing_aplica_o_heading_pedido():
    grafo = _novo_grafo()
    _assentar(grafo, angulo_pedido=45)
    assert grafo["body_facing"].getNetTransform().getHpr().getX() != 0
    assert grafo["giro"].angulo != 0


def test_giro_nao_altera_tilt_de_voo_nem_pivo_de_arraste():
    grafo = _novo_grafo()
    # Estados independentes: tilt de voo no anchor, arraste no suspension_pivot.
    grafo["model_anchor"].setHpr(5, 12, -3)
    grafo["suspension_pivot"].setHpr(7, 0, 2)
    anchor_antes = grafo["model_anchor"].getHpr()
    pivot_antes = grafo["suspension_pivot"].getHpr()
    _assentar(grafo, direcao_olhar=1.0)
    assert grafo["model_anchor"].getHpr() == anchor_antes
    assert grafo["suspension_pivot"].getHpr() == pivot_antes
    assert grafo["body_facing"].getNetTransform().getHpr().getX() != 0


def test_giro_zero_nao_desloca_o_modelo():
    grafo = _novo_grafo()
    antes = grafo["model_np"].getNetTransform().getMat()
    _assentar(grafo, direcao_olhar=0.0, frames=30)
    assert grafo["model_np"].getNetTransform().getMat() == antes


def test_giro_em_torno_do_centro_preserva_a_altura_do_pivo():
    from panda3d.core import Point3

    grafo = _novo_grafo()
    centro = Point3(0, 0, 0.44)
    antes = grafo["model_np"].getRelativePoint(grafo["body_facing"], centro)
    _assentar(grafo, angulo_pedido=GiroCorpo.LIMITE_GRAUS)
    depois = grafo["model_np"].getRelativePoint(grafo["body_facing"], centro)
    # Gira em torno do eixo vertical pelo centro: a altura (Z) não muda.
    assert depois.getZ() == antes.getZ()


def test_giro_durante_arraste_relaxa_para_zero():
    grafo = _novo_grafo()
    _assentar(grafo, direcao_olhar=1.0)  # vira para o lado primeiro
    assert grafo["giro"].angulo != 0
    _assentar(grafo, direcao_olhar=1.0, dragging=True)  # arraste zera o giro
    assert abs(grafo["giro"].angulo) < 0.01

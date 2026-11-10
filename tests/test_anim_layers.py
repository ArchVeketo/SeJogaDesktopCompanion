"""Contratos das camadas aditivas e do mixer."""
import pytest

from sejoga.animacao.anim_layers import (
    CamadaAnim,
    CamadaDelta,
    LayerStack,
    MixerCamadas,
    Prioridade,
)
from sejoga.nucleo.esqueleto import Rotation3


def test_soma_aditiva_por_junta():
    base = {"body": Rotation3(1, 0, 0)}
    camadas = [
        CamadaAnim("locomocao", {"body": Rotation3(2, 0, 3)}),
        CamadaAnim("musica", {"body": Rotation3(0, 5, 1)}),
    ]
    resultado = MixerCamadas.compor(camadas, base)
    assert resultado["body"] == Rotation3(3, 5, 4)


def test_mascara_restringe_grupos_afetados():
    camadas = [
        CamadaAnim("interacao", {"body": Rotation3(10, 0, 0), "head": Rotation3(10, 0, 0)},
                   mascara=frozenset({"head"})),
    ]
    resultado = MixerCamadas.compor(camadas)
    assert "body" not in resultado
    assert resultado["head"] == Rotation3(10, 0, 0)


def test_peso_zero_nao_altera_a_base():
    base = {"body": Rotation3(4, 0, 0)}
    camadas = [CamadaAnim("musica", {"body": Rotation3(90, 90, 90)}, peso=0.0)]
    resultado = MixerCamadas.compor(camadas, base)
    assert resultado["body"] == Rotation3(4, 0, 0)


def test_peso_fracionario_escala_a_contribuicao():
    camadas = [CamadaAnim("musica", {"body": Rotation3(10, 20, 0)}, peso=0.5)]
    resultado = MixerCamadas.compor(camadas)
    assert resultado["body"].x == pytest.approx(5)
    assert resultado["body"].y == pytest.approx(10)


def test_ordem_de_prioridade_e_deterministica():
    # Mesmo passando fora de ordem, a composição segue ORDEM_PRIORIDADE.
    direta = MixerCamadas.compor([
        CamadaAnim("base", {"body": Rotation3(1, 0, 0)}),
        CamadaAnim("fisica", {"body": Rotation3(0, 0, 1)}),
    ])
    invertida = MixerCamadas.compor([
        CamadaAnim("fisica", {"body": Rotation3(0, 0, 1)}),
        CamadaAnim("base", {"body": Rotation3(1, 0, 0)}),
    ])
    assert direta == invertida == {"body": Rotation3(1, 0, 1)}


# ═══════════════════════════════════════════════════════════════════════════════
# Testes do LayerStack e CamadaDelta (Fase 3)
# ═══════════════════════════════════════════════════════════════════════════════


def test_camada_delta_aplica_delta_sobre_base():
    """CamadaDelta soma delta à rotação base."""
    camada = CamadaDelta(
        nome="estado",
        prioridade=Prioridade.ESTADO,
        delta={"body": Rotation3(0.1, 0.2, 0.3)},
    )
    base = Rotation3(1.0, 2.0, 3.0)
    resultado = camada.aplicado("body", base)
    assert resultado.x == pytest.approx(1.1)
    assert resultado.y == pytest.approx(2.2)
    assert resultado.z == pytest.approx(3.3)


def test_camada_delta_respeita_mascara():
    """CamadaDelta não altera grupos fora da máscara."""
    camada = CamadaDelta(
        nome="musica",
        prioridade=Prioridade.MUSICA,
        delta={"body": Rotation3(1, 1, 1), "head": Rotation3(2, 2, 2)},
        mascara=frozenset({"head"}),
    )
    base_body = Rotation3(0, 0, 0)
    base_head = Rotation3(0, 0, 0)

    # body fora da máscara: retorna base inalterada
    assert camada.aplicado("body", base_body) == base_body

    # head na máscara: soma o delta
    resultado = camada.aplicado("head", base_head)
    assert resultado.x == pytest.approx(2)
    assert resultado.y == pytest.approx(2)
    assert resultado.z == pytest.approx(2)


def test_camada_delta_peso_zero_nao_altera():
    """CamadaDelta com peso=0 não altera a base."""
    camada = CamadaDelta(
        nome="estado",
        prioridade=Prioridade.ESTADO,
        delta={"body": Rotation3(100, 100, 100)},
        peso=0.0,
    )
    base = Rotation3(1, 2, 3)
    assert camada.aplicado("body", base) == base


def test_camada_delta_peso_fracionario():
    """CamadaDelta com peso fracionário escala o delta."""
    camada = CamadaDelta(
        nome="estado",
        prioridade=Prioridade.ESTADO,
        delta={"body": Rotation3(10, 20, 30)},
        peso=0.5,
    )
    base = Rotation3(0, 0, 0)
    resultado = camada.aplicado("body", base)
    assert resultado.x == pytest.approx(5)
    assert resultado.y == pytest.approx(10)
    assert resultado.z == pytest.approx(15)


def test_layer_stack_compor_sobre_base_de_repouso():
    """LayerStack compõe deltas sobre a pose de repouso."""
    stack = LayerStack()

    # Sem camadas, retorna a base de repouso
    base = stack.compor()
    assert "body" in base
    assert "right-arm" in base

    # Adiciona camada de estado
    stack.set_camada(CamadaDelta(
        nome="estado",
        prioridade=Prioridade.ESTADO,
        delta={"body": Rotation3(0.1, 0, 0)},
    ))
    resultado = stack.compor()
    assert resultado["body"].x == pytest.approx(base["body"].x + 0.1)


def test_layer_stack_ordem_de_prioridade():
    """LayerStack aplica camadas em ordem de prioridade."""
    stack = LayerStack()

    # Camadas em ordem reversa de prioridade
    stack.set_camada(CamadaDelta(
        nome="fisica",
        prioridade=Prioridade.FISICA,
        delta={"body": Rotation3(0.3, 0, 0)},
    ))
    stack.set_camada(CamadaDelta(
        nome="estado",
        prioridade=Prioridade.ESTADO,
        delta={"body": Rotation3(0.1, 0, 0)},
    ))

    base = stack._base["body"]
    resultado = stack.compor()

    # Os deltas são aditivos: base + 0.1 (estado) + 0.3 (fisica)
    assert resultado["body"].x == pytest.approx(base.x + 0.1 + 0.3)


def test_layer_stack_remove_camada():
    """LayerStack.remove_camada elimina a contribuição da camada."""
    stack = LayerStack()

    stack.set_camada(CamadaDelta(
        nome="reacao",
        prioridade=Prioridade.REACAO,
        delta={"body": Rotation3(1.0, 0, 0)},
    ))

    com_reacao = stack.compor()
    stack.remove_camada("reacao")
    sem_reacao = stack.compor()

    # A diferença é exatamente o delta da reação
    assert com_reacao["body"].x == pytest.approx(sem_reacao["body"].x + 1.0)


def test_layer_stack_set_camada_substitui():
    """LayerStack.set_camada substitui camada existente com mesmo nome."""
    stack = LayerStack()

    stack.set_camada(CamadaDelta(
        nome="estado",
        prioridade=Prioridade.ESTADO,
        delta={"body": Rotation3(0.1, 0, 0)},
    ))
    primeiro = stack.compor()

    stack.set_camada(CamadaDelta(
        nome="estado",
        prioridade=Prioridade.ESTADO,
        delta={"body": Rotation3(0.5, 0, 0)},
    ))
    segundo = stack.compor()

    # Só o segundo delta está presente, não a soma dos dois
    base = stack._base["body"]
    assert segundo["body"].x == pytest.approx(base.x + 0.5)
    assert primeiro["body"].x != segundo["body"].x

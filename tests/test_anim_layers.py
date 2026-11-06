"""Contratos das camadas aditivas e do mixer."""
import pytest

from sejoga.animacao.anim_layers import CamadaAnim, MixerCamadas
from sejoga.nucleo.rig import Rotation3


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

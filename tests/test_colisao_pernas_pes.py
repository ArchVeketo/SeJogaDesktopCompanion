"""Pernas e pés: a correção legada (rig_medidas, modelo Y-up) é inerte no app.

PENDÊNCIA declarada (recalibracao-gpu.md, C8): pernas/pés ainda são medidos pelo
modelo Y-up de ``rig_medidas``, que não bate com o grafo de cena. Em vez de
confiar nele, o ``PoseResolver`` só avalia os pares ``PARES_PERNAS_PES`` (os
braços têm correção própria com a FK real) e este teste prova que, na faixa de
pose de pernas/pés que o app produz, essa correção NÃO mexe em nada: o modelo
errado não consegue deformar a perna.
"""

from __future__ import annotations

from itertools import product
from math import radians

import pytest

from sejoga.nucleo.assets import resolve_model
from sejoga.nucleo.model import load_model
from sejoga.nucleo.rig import Rotation3
from sejoga.rig_mapa import colisao_membros as col
from sejoga.rig_mapa import rig_medidas as med
from sejoga.rig_mapa.rig_mapa import Parte

#: Amplitude máxima (graus) que o app escreve em pernas/pés (rig.py: queda, dança,
#: acordar, caminhada), com folga.
AMPLITUDE_PERNA_GRAUS = 25.0
#: Passo da grade de varredura (graus).
PASSO_GRAUS = 12.5
#: Amplitude (graus) dos eixos secundários (y/z), bem menor que a de pitch.
AMPLITUDE_SECUNDARIA_GRAUS = 10.0


@pytest.fixture(scope="module")
def model():
    return load_model(resolve_model())


def _valores(amplitude: float) -> list[float]:
    passos = int(amplitude // PASSO_GRAUS)

    return [radians(i * PASSO_GRAUS) for i in range(-passos, passos + 1)]


def test_pares_de_pernas_e_pes_nao_incluem_braco():
    assert col.PARES_PERNAS_PES
    permitidas = {Parte.PERNAS, Parte.PE_ESQUERDO, Parte.PE_DIREITO}

    for par in col.PARES_PERNAS_PES:
        assert set(par) <= permitidas


def test_correcao_legada_nao_mexe_em_pernas_e_pes(model):
    """Grade de poses de pernas/pés: nada é empurrado pela correção legada."""
    pitchs = _valores(AMPLITUDE_PERNA_GRAUS)
    laterais = _valores(AMPLITUDE_SECUNDARIA_GRAUS)

    for pernas, pe_esq, pe_dir, lateral in product(pitchs, pitchs, pitchs, laterais):
        pose = {
            "legs": Rotation3(pernas, lateral, 0.0),
            "left-feet": Rotation3(pe_esq, 0.0, lateral),
            "right-feet": Rotation3(pe_dir, 0.0, -lateral),
        }
        partes = med.medir_todas_as_partes(pose, model)
        alvo = col.resolver_colisoes(pose, partes, pares=col.PARES_PERNAS_PES)

        assert alvo == pose, pose

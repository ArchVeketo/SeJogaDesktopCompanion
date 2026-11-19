"""Contratos da malha autoral; qualidade de movimento é avaliada na janela real."""

import json
from PySide6 import QtCore  # noqa: F401
from panda3d.core import Mat4, Point3, Vec3
import pytest
from sejoga.nucleo.recursos import model_dir
from sejoga.render.pernas_tecido import _misturar_transformacoes, _pesos_vertice


def test_repouso_preserva_vertices_sem_encolher_a_cintura():
    dados = json.loads((model_dir() / "calca-autoral.json").read_text(encoding="utf-8"))
    assert len(dados["vertices"]) == 28
    assert len(dados["faces"]) == 26
    for p in dados["vertices"].values():
        p = Point3(*p)
        pesos = _pesos_vertice(p, 0.0375, -0.06875)
        assert sum(pesos) == pytest.approx(1)
        assert all(0 <= w <= 1 for w in pesos)
        mat = _misturar_transformacoes((Mat4.identMat(),) * 3, pesos)
        assert mat.xformPoint(p).almostEqual(p, 1e-6)
    for face in dados["faces"]:
        assert len(face["vertices"]) == len(face["uv"])
        assert all(k in dados["vertices"] for k in face["vertices"])
        assert all(0 <= u <= 1 and 0 <= v <= 1 for u, v in face["uv"])


def test_costura_central_nao_abre_quando_as_pernas_giram():
    ponto = Point3(0, 0.14, -0.04)
    pesos = _pesos_vertice(ponto, 0.0375, -0.06875)
    for angulo in (-85, 85):
        giro = Mat4.rotateMat(angulo, Vec3(1, 0, 0))
        mat = _misturar_transformacoes((Mat4.identMat(), giro, giro), pesos)
        assert mat.xformPoint(ponto).almostEqual(ponto, 1e-6)


def test_skinning_preserva_transformacao_rigida_e_translacao():
    matriz = Mat4.rotateMat(70, Vec3(1, 0, 0)) * Mat4.translateMat(0, 0.2, -0.1)
    ponto = Point3(0.12, 0.08, -0.2)
    mistura = _misturar_transformacoes((Mat4.identMat(), matriz, matriz), (0, 0.4, 0.6))
    assert mistura.xformPoint(ponto).almostEqual(matriz.xformPoint(ponto), 1e-6)

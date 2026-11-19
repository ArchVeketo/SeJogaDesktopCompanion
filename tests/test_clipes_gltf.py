"""Testes do carregador glTF 2.0 externo e do clipe piloto no controlador."""

from __future__ import annotations

import ast
import base64
import json
import struct
from math import radians, sqrt
from pathlib import Path

import pytest

from sejoga.animacao.clipes_gltf import (
    _carregar_buffers,
    amostrar_clipe_gltf,
    carregar_clipe_gltf,
    carregar_clipe_gltf_arquivo,
    listar_clipes_gltf,
)
from sejoga.animacao.controlador_animacao import AnimationController, AnimationState
from sejoga.nucleo import cinematica as cin
from sejoga.nucleo.esqueleto import ALL_GROUPS, Rig, Rotation3
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.recursos import assets_dir, resolve_model

_RAIZ = Path(__file__).resolve().parents[1]
_MODULOS_PROIBIDOS = ("panda3d", "PySide6", "win32", "sejoga.render")


def _matriz_para_quat(m: tuple[float, ...]) -> tuple[float, float, float, float]:
    m00, m01, m02, m10, m11, m12, m20, m21, m22 = m
    t = m00 + m11 + m22
    if t > 0.0:
        s = sqrt(t + 1.0) * 2.0
        return (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s
    if m00 > m11 and m00 > m22:
        s = sqrt(1.0 + m00 - m11 - m22) * 2.0
        return 0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s
    if m11 > m22:
        s = sqrt(1.0 + m11 - m00 - m22) * 2.0
        return (m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s
    s = sqrt(1.0 + m22 - m00 - m11) * 2.0
    return (m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s


def _rot_autoria_para_quat_gltf(rot: Rotation3) -> tuple[float, float, float, float]:
    """Inverte ``_quat_gltf_para_rotation3`` usando a convenção canônica de cinemática."""
    mat_aut = cin.rot_hpr(rot.y, rot.x, rot.z)
    c = cin._GLTF_PARA_AUTORIA
    return _matriz_para_quat(cin.mul(cin.mul(cin.transposta(c), mat_aut), c))


def _escrever_gltf_teste(destino: Path) -> None:
    """Gera um `.gltf` mínimo com trilhas STEP, LINEAR (antípoda) e CUBICSPLINE."""
    tempos = (0.0, 1.0)
    q0 = _rot_autoria_para_quat_gltf(Rotation3())
    q1 = _rot_autoria_quat(0.0, 0.60, 0.0)
    q1_neg = (-q1[0], -q1[1], -q1[2], -q1[3])
    zero_q = (0.0, 0.0, 0.0, 0.0)
    dados_bin = bytearray()

    def _add(fmt: str, vals: list[float]) -> tuple[int, int]:
        off = len(dados_bin)
        dados_bin.extend(struct.pack("<" + fmt * len(vals), *vals))
        return off, len(dados_bin) - off

    off_t, len_t = _add("f", list(tempos))
    off_step, len_step = _add("f", list(q0) + list(q1))
    off_lin, len_lin = _add("f", list(q0) + list(q1_neg))
    off_cub, len_cub = _add(
        "f", [*zero_q, *q0, *zero_q, *zero_q, *q1, *zero_q]
    )
    b64 = base64.b64encode(bytes(dados_bin)).decode("ascii")
    doc = {
        "asset": {"version": "2.0", "generator": "pytest-gltf"},
        "buffers": [{"uri": f"data:application/gltf-buffer;base64,{b64}", "byteLength": len(dados_bin)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": off_t, "byteLength": len_t},
            {"buffer": 0, "byteOffset": off_step, "byteLength": len_step},
            {"buffer": 0, "byteOffset": off_lin, "byteLength": len_lin},
            {"buffer": 0, "byteOffset": off_cub, "byteLength": len_cub},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 2, "type": "SCALAR", "min": [0.0], "max": [1.0]},
            {"bufferView": 1, "componentType": 5126, "count": 2, "type": "VEC4"},
            {"bufferView": 2, "componentType": 5126, "count": 2, "type": "VEC4"},
            {"bufferView": 3, "componentType": 5126, "count": 6, "type": "VEC4"},
        ],
        "nodes": [{"name": "door"}, {"name": "head"}, {"name": "peitoral"}],
        "animations": [
            {
                "name": "teste_interpolacao",
                "samplers": [
                    {"input": 0, "interpolation": "STEP", "output": 1},
                    {"input": 0, "interpolation": "LINEAR", "output": 2},
                    {"input": 0, "interpolation": "CUBICSPLINE", "output": 3},
                ],
                "channels": [
                    {"sampler": 0, "target": {"node": 0, "path": "rotation"}},
                    {"sampler": 1, "target": {"node": 1, "path": "rotation"}},
                    {"sampler": 2, "target": {"node": 2, "path": "rotation"}},
                ],
            }
        ],
    }
    destino.write_text(json.dumps(doc), encoding="utf-8")


def _rot_autoria_quat(x: float, y: float, z: float) -> tuple[float, float, float, float]:
    return _rot_autoria_para_quat_gltf(Rotation3(x=x, y=y, z=z))


def test_clipes_gltf_modulo_puro_sem_dependencias_graficas() -> None:
    src = (_RAIZ / "src" / "sejoga" / "animacao" / "clipes_gltf.py").read_text(encoding="utf-8")
    arvore = ast.parse(src)
    importados: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.extend(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.append(no.module)
    for mod in importados:
        for proibido in _MODULOS_PROIBIDOS:
            assert not mod.startswith(proibido), f"Import proibido em clipes_gltf.py: {mod}"


def test_piloto_olhar_ombro_cumpre_contrato_gltf_2_0() -> None:
    assert "piloto/olhar_ombro" in listar_clipes_gltf("piloto")
    gltf_path = assets_dir() / "animation" / "piloto" / "olhar_ombro.gltf"
    doc = json.loads(gltf_path.read_text(encoding="utf-8"))
    assert doc["asset"]["version"] == "2.0"
    buffers = _carregar_buffers(doc, gltf_path.parent, None)
    assert len(buffers[0]) == doc["buffers"][0]["byteLength"]

    anim = doc["animations"][0]
    grupos_validos = frozenset(ALL_GROUPS)
    for ch in anim["channels"]:
        node_idx = ch["target"]["node"]
        assert doc["nodes"][node_idx]["name"] in grupos_validos
        samp = anim["samplers"][ch["sampler"]]
        acc_in = doc["accessors"][samp["input"]]
        acc_out = doc["accessors"][samp["output"]]
        assert acc_in["type"] == "SCALAR"
        assert acc_in["componentType"] == 5126
        assert acc_out["type"] == "VEC4"
        esperado = acc_in["count"] * 3 if samp.get("interpolation") == "CUBICSPLINE" else acc_in["count"]
        assert acc_out["count"] == esperado

    clipe = carregar_clipe_gltf("piloto/olhar_ombro")
    assert clipe is not None
    assert clipe.contrato is not None
    assert clipe.contrato.id == "piloto/olhar_ombro"
    assert clipe.contrato.duracao_s == pytest.approx(1.8)
    assert clipe.contrato.modo_canal == "delta_local"
    for trilha in clipe.trilhas:
        assert trilha.tempos[0] == pytest.approx(0.0)
        assert all(b > a for a, b in zip(trilha.tempos, trilha.tempos[1:], strict=False))


def test_interpolacoes_step_linear_menor_arco_e_cubicspline(tmp_path: Path) -> None:
    caminho = tmp_path / "interp.gltf"
    _escrever_gltf_teste(caminho)
    clipe = carregar_clipe_gltf_arquivo(caminho)
    assert clipe is not None
    por_grupo = {t.grupo: t for t in clipe.trilhas}

    from sejoga.animacao.clipes_gltf import _amostrar_trilha

    # STEP segura o primeiro keyframe em t=0.5s e salta apenas em t=1.0s
    assert _amostrar_trilha(por_grupo["door"], 0.5).y == pytest.approx(0.0, abs=1e-4)
    assert _amostrar_trilha(por_grupo["door"], 1.0).y == pytest.approx(0.60, abs=1e-4)

    # LINEAR com quaternião antípoda segue o menor arco (~0.30 rad em t=0.5s)
    meio_lin = _amostrar_trilha(por_grupo["head"], 0.5)
    assert meio_lin.y == pytest.approx(0.30, abs=1e-3)
    assert _amostrar_trilha(por_grupo["head"], 1.0).y == pytest.approx(0.60, abs=1e-4)

    # CUBICSPLINE com tangentes zero cruza o ponto médio em ~0.30 rad suavemente
    meio_cub = _amostrar_trilha(por_grupo["peitoral"], 0.5)
    assert meio_cub.y == pytest.approx(0.30, abs=1e-2)
    assert _amostrar_trilha(por_grupo["peitoral"], 1.0).y == pytest.approx(0.60, abs=1e-4)


def test_piloto_amostra_keyframes_e_dispara_eventos_uma_vez() -> None:
    ev_vistos: list[str] = []
    t_ant = -1e-6
    for passo in range(1, 39):
        t = passo * 0.05
        am = amostrar_clipe_gltf("piloto/olhar_ombro", t, tempo_anterior=t_ant)
        ev_vistos.extend(am.eventos)
        t_ant = t
    assert ev_vistos == [
        "antecipacao_ombro",
        "pico_espiada_porta",
        "recuperacao_repouso",
    ]
    assert amostrar_clipe_gltf("piloto/olhar_ombro", 0.24).delta_rig["head"].y > radians(5.0)
    assert amostrar_clipe_gltf("piloto/olhar_ombro", 0.62).delta_rig["head"].y < -radians(25.0)
    assert amostrar_clipe_gltf("piloto/olhar_ombro", 0.62).delta_rig["door"].y > radians(12.0)
    assert amostrar_clipe_gltf("piloto/olhar_ombro", 1.85).ativa is False


def test_controlador_executa_e_interrompe_clipe_gltf_sem_travamento() -> None:
    modelo = load_model(resolve_model())
    ctrl = AnimationController(Rig.from_model(modelo), model=modelo)
    assert ctrl.tocar_clipe_gltf("inexistente/nada") is False
    assert ctrl.tocar_clipe_gltf("piloto/olhar_ombro") is True

    eventos_ctrl: list[str] = []
    pose: dict[str, Rotation3] = {}
    for _ in range(13):  # ~0.65s -> pico do olhar por cima do ombro
        pose = ctrl.update(dt=0.05, velocity=(0.0, 0.0), grounded=True, gravity_active=False)
        eventos_ctrl.extend(ctrl.clipe_gltf_eventos)
    assert ctrl.state == AnimationState.IDLE
    assert ctrl.clipe_gltf_amostra.ativa is True
    assert "antecipacao_ombro" in eventos_ctrl
    assert abs(pose["door"].y) > radians(8.0)

    ctrl.update(dt=0.02, velocity=(120.0, 0.0), grounded=False, dragging=True)
    assert ctrl.state == AnimationState.DRAG
    assert ctrl.clipe_gltf_amostra.ativa is False
    assert ctrl._clipe_gltf_nome == ""


@pytest.mark.parametrize("modo_interrupcao", ["fall", "sleep"])
def test_controlador_interrompe_clipe_gltf_em_fall_e_sleep(modo_interrupcao: str) -> None:
    modelo = load_model(resolve_model())
    ctrl = AnimationController(Rig.from_model(modelo), model=modelo)
    assert ctrl.tocar_clipe_gltf("piloto/olhar_ombro") is True
    ctrl.update(dt=0.10, velocity=(0.0, 0.0), grounded=True, gravity_active=False)
    assert ctrl.clipe_gltf_amostra.ativa is True
    if modo_interrupcao == "fall":
        ctrl.update(dt=0.02, velocity=(0.0, 180.0), grounded=False, gravity_active=True)
        assert ctrl.state == AnimationState.FALL
    else:
        ctrl.colocar_para_dormir("sentado")
        ctrl.update(dt=0.05, velocity=(0.0, 0.0), grounded=True, gravity_active=False)
        assert ctrl.state == AnimationState.SLEEP
    assert ctrl.clipe_gltf_amostra.ativa is False

"""Testes de eixo do gizmo de rotação 3D e da ferramenta de movimento do editor."""

from __future__ import annotations

import math
import shutil
from typing import TYPE_CHECKING, Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from sejoga.animacao.movimento_pernas import LegPose
from sejoga.editor.catalogo import construir_catalogo
from sejoga.editor.documento import DocumentoEditor
from sejoga.editor.ik_membros import (
    compor_pose_pernas,
    resolver_espec_mover_membro,
    resolver_ik_perna,
    resolver_mira_coxa,
    valor_chave_membro,
)
from sejoga.editor.janela_editor import JanelaEditor
from sejoga.editor.persistencia import (
    CAMINHO_ANIMATION_PADRAO,
    carregar_arquivo_animacao,
    validar_dados_animacao,
)
from sejoga.editor.roteiro import ObstaculoPrevia
from sejoga.editor.sessao_previa import QuadroPrevia, SessaoPrevia
from sejoga.editor.viewport_panda import (
    _ESPEC_ANEL_ROTACAO,
    _ESPEC_EIXOS_MUNDO,
    EstadoAlvoMover,
    ModoCamera,
    ModoFerramenta,
    PandaViewportSession,
)
from sejoga.nucleo.esqueleto import Rotation3

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

_ASPECTO_TESTE = 960.0 / 600.0


def _qt_app() -> QApplication:
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _copia_doc(tmp_path: Path) -> tuple[DocumentoEditor, Path]:
    copia = tmp_path / "animation.py"
    shutil.copy2(CAMINHO_ANIMATION_PADRAO, copia)
    return DocumentoEditor(carregar_arquivo_animacao(copia)), copia


@pytest.fixture
def sessao_gpu(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[tuple[PandaViewportSession, SessaoPrevia]]:
    """Cria sessão Panda3D offscreen com cena posada e descarta ao sair."""
    monkeypatch.setenv("SEJOGA_CONFIG_PATH", str(tmp_path / "cfg.toml"))
    _qt_app()
    sessao_panda = PandaViewportSession(0, 960, 600)
    try:
        doc = DocumentoEditor()
        previa = SessaoPrevia(doc)
        acao = next(
            a
            for a in construir_catalogo(doc.rascunho)
            if a.id == "cenas_idle:fone_com_problema"
        )
        previa.selecionar_acao(acao)
        quadro = previa.ir_para(0.85)
        sessao_panda.sincronizar_quadro(quadro, controller=previa._controller)
        sessao_panda.step()
        yield sessao_panda, previa
    finally:
        sessao_panda.destruir()


def _rotacao_com_delta(pose_base: Rotation3, eixo: str, delta_rad: float) -> Rotation3:
    return Rotation3(
        x=pose_base.x + (delta_rad if eixo == "x" else 0.0),
        y=pose_base.y + (delta_rad if eixo == "y" else 0.0),
        z=pose_base.z + (delta_rad if eixo == "z" else 0.0),
    )


def _medir_eixo_real(
    sessao_panda: PandaViewportSession,
    quadro: QuadroPrevia,
    grupo: str,
    eixo: str,
    r_ortho: Any,
) -> Any:
    from panda3d.core import Point3, Vec3

    pose_base = quadro.pose.get(grupo, Rotation3())
    renderer = sessao_panda.renderer
    render = sessao_panda.showbase.render
    node = renderer._rig_nodes[grupo]
    piv = render.getRelativePoint(node, Point3(0.0, 0.0, 0.0))
    probe_local = node.getRelativePoint(render, Point3(piv + r_ortho))
    delta_rad = math.radians(1.0)
    renderer.apply_rig_pose({**quadro.pose, grupo: _rotacao_com_delta(pose_base, eixo, -delta_rad)})
    p_neg = render.getRelativePoint(node, probe_local)
    renderer.apply_rig_pose({**quadro.pose, grupo: _rotacao_com_delta(pose_base, eixo, delta_rad)})
    p_pos = render.getRelativePoint(node, probe_local)
    renderer.apply_rig_pose(quadro.pose)
    eixo_medido = r_ortho.cross(Vec3(p_pos - p_neg))
    assert eixo_medido.lengthSquared() > 1e-12
    eixo_medido.normalize()
    return eixo_medido


def _provar_eixos_rotacao_grupo(
    sessao_panda: PandaViewportSession,
    quadro: QuadroPrevia,
    grupo: str,
) -> list[str]:
    from panda3d.core import Quat, Vec3

    pose_base = quadro.pose.get(grupo, Rotation3())
    euler_deg = (math.degrees(pose_base.x), math.degrees(pose_base.y), math.degrees(pose_base.z))
    sessao_panda.definir_junta_selecionada(grupo)
    sessao_panda.step()

    quats = sessao_panda._gizmo._quaternions_eixos(
        sessao_panda.renderer, grupo, sessao_panda.renderer._rig_nodes[grupo], euler_deg, Quat
    )
    eixos_mundo: dict[str, Vec3] = {}
    for eixo, (ax_loc, u_vec, _v_vec) in _ESPEC_ANEL_ROTACAO.items():
        r_ortho = quats[eixo].xform(Vec3(*u_vec)) * 0.22
        eixo_medido = _medir_eixo_real(sessao_panda, quadro, grupo, eixo, r_ortho)
        eixo_gizmo = quats[eixo].xform(Vec3(*ax_loc))
        eixo_gizmo.normalize()
        eixos_mundo[eixo] = eixo_gizmo
        assert float(eixo_gizmo.dot(eixo_medido)) > 0.999

    return [
        eixo
        for idx, eixo in enumerate(("x", "y", "z"))
        if not any(
            abs(float(eixos_mundo[eixo].dot(eixos_mundo[outro]))) > 0.985
            for outro in ("x", "y", "z")[:idx]
        )
    ]


def _achar_ponto_anel_picking(
    sessao_panda: PandaViewportSession,
    eixo: str,
    cam: Any,
    lens: Any,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float, float]]:
    amostras = sessao_panda._gizmo._projetar_anel(eixo, lens, cam, 36)
    assert amostras
    for sx, sy, _, pt_loc in sorted(amostras, key=lambda item: item[2]):
        if abs(sx) > 0.96 or abs(sy) > 0.96:
            continue
        res = sessao_panda._gizmo.escolher_eixo(cam, (sx, sy), _ASPECTO_TESTE)
        if res is not None and res[0] == eixo:
            return (sx, sy), res[1], pt_loc
    raise AssertionError(f"Nao foi possivel selecionar anel {eixo}")


def _projetar_ponto_mundo(cam: Any, render: Any, lens: Any, p_w: Any) -> tuple[float, float]:
    from panda3d.core import Point2

    p2d = Point2()
    assert lens.project(cam.getRelativePoint(render, p_w), p2d)
    return float(p2d.x), float(p2d.y)


def _validar_tangente_rotacao_eixo(
    sessao_panda: PandaViewportSession,
    quadro: QuadroPrevia,
    grupo: str,
    eixo: str,
) -> None:
    from panda3d.core import Point3

    cam = sessao_panda.showbase.cam
    lens = cam.node().getLens()
    render = sessao_panda.showbase.render
    node = sessao_panda.renderer._rig_nodes[grupo]
    pose_base = quadro.pose.get(grupo, Rotation3())
    euler_deg = (math.degrees(pose_base.x), math.degrees(pose_base.y), math.degrees(pose_base.z))

    mp, tang, pt_loc = _achar_ponto_anel_picking(sessao_panda, eixo, cam, lens)
    assert math.hypot(tang[0], tang[1]) > 0.5
    sessao_panda._iniciar_drag_gizmo(eixo, tang, mp, _ASPECTO_TESTE)
    passo = 0.02
    sessao_panda._atualizar_drag_gizmo((tang[0] * passo) / _ASPECTO_TESTE, tang[1] * passo)
    e_novo = sessao_panda._pose_euler_selecionada
    assert sessao_panda.cancelar_drag_gizmo() is True
    assert math.isclose(e_novo["xyz".index(eixo)] - euler_deg["xyz".index(eixo)], passo * 190.0, abs_tol=1e-4)

    p_hit_w = render.getRelativePoint(sessao_panda._gizmo.aneis[eixo], Point3(*pt_loc))
    r_local_node = node.getRelativePoint(render, p_hit_w)
    x0, y0 = _projetar_ponto_mundo(cam, render, lens, p_hit_w)

    pose_pos = {**quadro.pose, grupo: Rotation3(*(math.radians(v) for v in e_novo))}
    sessao_panda.renderer.apply_rig_pose(pose_pos)
    x1, y1 = _projetar_ponto_mundo(cam, render, lens, render.getRelativePoint(node, r_local_node))
    sessao_panda.renderer.apply_rig_pose(quadro.pose)

    dx_s, dy_s = (x1 - x0) * _ASPECTO_TESTE, y1 - y0
    norm = math.hypot(dx_s, dy_s)
    assert norm > 1e-4
    assert (dx_s * tang[0] + dy_s * tang[1]) / norm > 0.90


def test_gizmo_rotacao_eixos_e_tangentes_cameras(
    sessao_gpu: tuple[PandaViewportSession, SessaoPrevia],
) -> None:
    """Aneis X/Y/Z refletem eixos reais de Rotation3 e tangentes batem na tela."""
    sessao_panda, previa = sessao_gpu
    quadro = previa.ir_para(0.85)
    for grupo in ("right-arm", "ant-arm", "hand", "head"):
        eixos_distintos = _provar_eixos_rotacao_grupo(sessao_panda, quadro, grupo)
        for modo in (ModoCamera.PERSPECTIVA, ModoCamera.FRONTAL, ModoCamera.LATERAL):
            sessao_panda.definir_modo_camera(modo)
            sessao_panda.sincronizar_quadro(quadro, controller=previa._controller)
            sessao_panda.step()
            for eixo in eixos_distintos:
                _validar_tangente_rotacao_eixo(sessao_panda, quadro, grupo, eixo)


def _verificar_mover_eixo(
    sessao_panda: PandaViewportSession,
    eixo: str,
    dir_t: tuple[float, float, float],
    capturados: list[tuple[str, tuple[float, float, float]]],
) -> None:
    from panda3d.core import Point2, Point3, Vec3

    cam = sessao_panda.showbase.cam
    lens = cam.node().getLens()
    gizmo = sessao_panda._gizmo_mover
    d_vec = Vec3(*dir_t)
    p_seta = cam.getRelativePoint(gizmo.root, Point3(d_vec.x * 0.34, d_vec.y * 0.34, d_vec.z * 0.34))
    p2d = Point2()
    assert lens.project(p_seta, p2d)
    mp = (float(p2d.x), float(p2d.y))
    escolhido = gizmo.escolher_eixo(cam, mp, _ASPECTO_TESTE)
    assert escolhido is not None
    eixo_sel, jac = escolhido
    assert eixo_sel == eixo

    capturados.clear()
    sessao_panda._iniciar_drag_mover(eixo, jac, mp, _ASPECTO_TESTE)
    sessao_panda._atualizar_drag_mover((0.5 * jac[0]) / _ASPECTO_TESTE, 0.5 * jac[1])
    assert capturados
    tipo_mov, trio = capturados[-1]
    assert tipo_mov == "corpo"
    esperado = tuple(0.5 if e == eixo else 0.0 for e in ("x", "y", "z"))
    assert trio == pytest.approx(esperado, abs=1e-3)
    assert sessao_panda.cancelar_drag_gizmo() is True


def test_gizmo_movimento_picking_jacobiana_e_cancelamento(
    sessao_gpu: tuple[PandaViewportSession, SessaoPrevia],
) -> None:
    """Seta 3D de movimento projeta jacobiana 1:1 e atualiza overlay de obstaculo."""
    from panda3d.core import Vec3

    sessao_panda, previa = sessao_gpu
    quadro = previa.ir_para(0.85)
    sessao_panda.sincronizar_quadro(quadro, obstaculo=ObstaculoPrevia(ativo=True))
    sessao_panda.definir_ferramenta(ModoFerramenta.MOVER)
    sessao_panda.definir_alvo_mover(EstadoAlvoMover(tipo="obstaculo", rotulo="Obs"))
    assert sessao_panda._overlays_3d._node_contatos is not None

    capturados: list[tuple[str, tuple[float, float, float]]] = []
    sessao_panda._on_mover_update = lambda tipo, trio: capturados.append((tipo, trio))
    sessao_panda.definir_alvo_mover(
        EstadoAlvoMover(tipo="corpo", rotulo="Corpo", valor_atual=(0.0, 0.0, 0.0))
    )
    sessao_panda.step()
    assert sessao_panda._gizmo.root.isHidden() is True
    assert sessao_panda._gizmo_mover.root.isHidden() is False
    assert sessao_panda.cancelar_drag_gizmo() is False

    cam = sessao_panda.showbase.cam
    for modo in (ModoCamera.PERSPECTIVA, ModoCamera.FRONTAL, ModoCamera.LATERAL):
        sessao_panda.definir_modo_camera(modo)
        sessao_panda.step()
        cam_fwd = sessao_panda.showbase.render.getRelativeVector(cam, Vec3(0, 1, 0))
        cam_fwd.normalize()
        testados = 0
        for eixo, dir_t in _ESPEC_EIXOS_MUNDO.items():
            if abs(float(Vec3(*dir_t).dot(cam_fwd))) > 0.94:
                continue
            _verificar_mover_eixo(sessao_panda, eixo, dir_t, capturados)
            testados += 1
        assert testados >= 2


def _verificar_atalhos_ferramenta(janela: JanelaEditor, app: QApplication) -> None:
    assert janela._ferramenta is ModoFerramenta.GIRAR
    assert janela.barra_camera._btn_girar.isChecked()

    janela.catalogo._campo_busca.setFocus()
    app.processEvents()
    QTest.keyClick(janela.catalogo._campo_busca, Qt.Key.Key_G)
    QTest.keyClick(janela.catalogo._campo_busca, Qt.Key.Key_R)
    app.processEvents()
    assert janela.catalogo._campo_busca.text() == "gr"
    assert janela._ferramenta is ModoFerramenta.GIRAR

    janela.barra_camera._btn_girar.setFocus()
    app.processEvents()
    QTest.keyClick(janela.barra_camera._btn_girar, Qt.Key.Key_G)
    app.processEvents()
    assert janela._ferramenta is ModoFerramenta.MOVER
    assert janela.barra_camera._btn_mover.isChecked()
    QTest.keyClick(janela.barra_camera._btn_mover, Qt.Key.Key_R)
    app.processEvents()
    assert janela._ferramenta is ModoFerramenta.GIRAR


def _verificar_mover_corpo_e_undo(janela: JanelaEditor, doc: DocumentoEditor) -> None:
    assert janela.abrir_acao("cenas_idle:fone_com_problema", confirmar=False)
    janela.definir_ferramenta(ModoFerramenta.MOVER)
    assert janela._resolver_alvo_mover().tipo == "membro"

    janela.selecionar_junta("body")
    alvo_cena = janela._resolver_alvo_mover()
    assert alvo_cena is not None and alvo_cena.tipo == "corpo"

    janela.selecionar_junta("hand")
    assert janela._resolver_alvo_mover().tipo == "membro"
    janela.inspetor._btn_mover_corpo_linha.click()
    assert janela._resolver_alvo_mover().tipo == "corpo"

    janela._on_mover_iniciado("corpo", "x")
    janela._on_mover_confirmado("corpo", (0.12, -0.05, 0.08))
    assert doc.rascunho["CENAS_IDLE"]["fone_com_problema"]["deslocamento_corpo"] == (0.12, -0.05, 0.08)
    assert [s.value() for s in janela.inspetor._spins_desloc_corpo] == pytest.approx(
        [0.12, -0.05, 0.08], abs=1e-4
    )

    janela.desfazer()
    assert "deslocamento_corpo" not in doc.rascunho["CENAS_IDLE"]["fone_com_problema"]
    janela.refazer()
    janela._on_mover_iniciado("corpo", "y")
    janela._on_mover_atualizado("corpo", (0.66, 0.77, 0.88))
    janela._on_atalho_esc()
    assert doc.rascunho["CENAS_IDLE"]["fone_com_problema"]["deslocamento_corpo"] == (0.12, -0.05, 0.08)


def _verificar_mover_vfx_e_persistencia(
    janela: JanelaEditor, doc: DocumentoEditor, copia: Path
) -> None:
    janela.inspetor.alvo_mover_solicitado.emit("vfx")
    alvo_vfx = janela._resolver_alvo_mover()
    assert alvo_vfx is not None and alvo_vfx.tipo == "vfx"
    janela._on_mover_iniciado("vfx", "x")
    janela._on_mover_confirmado("vfx", (0.03, -0.04, 0.06))
    assert doc.rascunho["VFX"]["estouro_fone"]["deslocamento"] == (0.03, -0.04, 0.06)

    assert janela.abrir_acao("idle_clips:calm", confirmar=False)
    janela._on_mover_iniciado("corpo", "z")
    janela._on_mover_confirmado("corpo", (0.04, 0.02, -0.03))
    assert janela.salvar_projeto(forcar=True)
    recarregado = carregar_arquivo_animacao(copia)
    validar_dados_animacao(recarregado.dados)
    assert recarregado.dados["IDLE_CLIPS"]["calm"]["deslocamento_corpo"] == (0.04, 0.02, -0.03)
    assert recarregado.dados["VFX"]["estouro_fone"]["deslocamento"] == (0.03, -0.04, 0.06)


def test_janela_editor_ferramentas_atalhos_e_mover_alvos(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Alterna ferramentas, protege busca de texto, move alvos com Undo/Esc e salva."""
    monkeypatch.setenv("SEJOGA_CONFIG_PATH", str(tmp_path / "cfg.toml"))
    app = _qt_app()
    doc, copia = _copia_doc(tmp_path)
    janela = JanelaEditor(
        doc,
        habilitar_gpu=False,
        caminho_ui=tmp_path / "ui.json",
        confirmar_pendencias=False,
    )
    try:
        janela.show()
        janela.activateWindow()
        app.processEvents()
        _verificar_atalhos_ferramenta(janela, app)
        _verificar_mover_corpo_e_undo(janela, doc)
        _verificar_mover_vfx_e_persistencia(janela, doc, copia)

        assert janela.abrir_acao("vfx:pouso", confirmar=False)
        alvo_vfx_prop = janela._resolver_alvo_mover()
        assert alvo_vfx_prop is not None and alvo_vfx_prop.tipo == "vfx"

        assert janela.abrir_acao("tentaculos:trajetoria_ponta", confirmar=False)
        alvo_obs = janela._resolver_alvo_mover()
        assert alvo_obs is not None and alvo_obs.tipo == "obstaculo"
        janela._on_mover_iniciado("obstaculo", "x")
        janela._on_mover_confirmado("obstaculo", (0.45, -0.35, 0.25))
        assert janela.sessao.roteiro.obstaculo.centro == (0.45, -0.35, 0.25)
    finally:
        janela.close()


def test_ik_membros_puro_especs_e_composicao() -> None:
    """Classifica membros uniformemente e compõe LegPose e deltas de pista sem saltos."""
    assert resolver_espec_mover_membro("body") is None
    assert resolver_espec_mover_membro("cintura") is None
    assert resolver_espec_mover_membro("legs") is None

    esp_mao = resolver_espec_mover_membro("hand")
    esp_pe = resolver_espec_mover_membro("left-feet")
    esp_cab = resolver_espec_mover_membro("head")
    assert esp_mao is not None and esp_mao.juntas == ("right-arm", "ant-arm")
    assert esp_pe is not None and esp_pe.juntas == ("coxa-esquerda", "canela-esquerda")
    assert esp_cab is not None and esp_cab.modo == "mira"

    base = LegPose(left=-12.0, left_knee=20.0)
    assert compor_pose_pernas(base, {"coxa-esquerda": Rotation3()}) is base
    pose_ed = {
        "coxa-esquerda": Rotation3(math.radians(-10.0), math.radians(5.0), math.radians(4.0)),
        "canela-esquerda": Rotation3(math.radians(15.0), 0.0, 0.0),
    }
    comp = compor_pose_pernas(base, pose_ed)
    assert comp is not None and comp.left == pytest.approx(-22.0, abs=1e-4)
    assert (comp.left_yaw, comp.left_roll, comp.left_knee) == pytest.approx((5.0, 4.0, 35.0), abs=1e-4)

    q, k, rl = resolver_ik_perna((0.095, 0.0, 0.456), (0.119, 0.0, 0.35), (0.125, 0.0, 0.25), (0.125, -0.05, 0.30))
    assert q < -5.0 and k > 15.0 and abs(rl) < 25.0
    qm, rlm = resolver_mira_coxa((0.095, 0.0, 0.456), (0.119, 0.0, 0.35), (0.119, -0.04, 0.36))
    assert qm < -10.0 and abs(rlm) < 25.0
    assert valor_chave_membro((5.0, -3.0, 2.0), (20.0, 10.0, -4.0), (25.0, 7.0, 1.0)) == (10.0, -6.0, 7.0)


def _arrastar_membro_gpu(
    sessao_panda: PandaViewportSession,
    quadro_base: QuadroPrevia,
    grupo: str,
    desloc_world: tuple[float, float, float],
) -> tuple[dict[str, tuple[float, float, float]], Any]:
    espec = resolver_espec_mover_membro(grupo)
    assert espec is not None
    sessao_panda.definir_junta_selecionada(grupo)
    sessao_panda.definir_ferramenta(ModoFerramenta.MOVER)
    sessao_panda.definir_alvo_mover(
        EstadoAlvoMover(
            tipo="membro",
            rotulo=espec.rotulo,
            grupo=grupo,
            modo_ik=espec.modo,
            juntas_afetadas=espec.juntas,
        )
    )
    sessao_panda.step()
    p0 = sessao_panda._posicao_mover_atual()
    assert p0 is not None
    sessao_panda._iniciar_drag_mover("x", (1.0, 0.0), (0.0, 0.0), 1.0)
    alvo = (p0[0] + desloc_world[0], p0[1] + desloc_world[1], p0[2] + desloc_world[2])
    poses = sessao_panda._resolver_ik_membro_drag(alvo)
    nova_pose = dict(quadro_base.pose)
    for g, (dx, dy, dz) in poses.items():
        nova_pose[g] = Rotation3(math.radians(dx), math.radians(dy), math.radians(dz))
    pernas_ed = compor_pose_pernas(quadro_base.pernas, nova_pose)
    sessao_panda.sincronizar_quadro(
        QuadroPrevia(
            tempo_s=quadro_base.tempo_s,
            duracao_s=quadro_base.duracao_s,
            pose=nova_pose,
            pose_pretendida=nova_pose,
            pernas=pernas_ed,
        )
    )
    sessao_panda.cancelar_drag_gizmo()
    return poses, p0


def _validar_ponto_membro_gpu(
    sessao_panda: PandaViewportSession,
    quadro: QuadroPrevia,
    grupo: str,
    desloc: tuple[float, float, float],
) -> None:
    from panda3d.core import Point3

    render = sessao_panda.showbase.render
    sessao_panda.sincronizar_quadro(quadro)
    poses, p0 = _arrastar_membro_gpu(sessao_panda, quadro, grupo, desloc)
    p_node = sessao_panda.renderer._rig_nodes[grupo].getPos(render)
    esperado = Point3(p0[0] + desloc[0], p0[1] + desloc[1], p0[2] + desloc[2])
    assert (p_node - esperado).length() < 0.015
    assert len(poses) == 2


def test_mover_membros_ik_braco_perna_e_cabeca_gpu(
    sessao_gpu: tuple[PandaViewportSession, SessaoPrevia],
) -> None:
    """Arraste 3D move mão (IK braço), pé (IK perna via LowerBody) e cabeça (mira)."""
    from panda3d.core import Vec3

    sessao_panda, previa = sessao_gpu
    quadro = previa.ir_para(0.85)
    render = sessao_panda.showbase.render

    for grupo, desloc in (
        ("hand", (-0.18, -0.35, 0.42)),
        ("hand2", (0.20, -0.30, 0.35)),
        ("right-feet", (-0.18, -0.32, 0.28)),
        ("left-feet", (0.16, -0.28, 0.24)),
    ):
        _validar_ponto_membro_gpu(sessao_panda, quadro, grupo, desloc)

    sessao_panda.sincronizar_quadro(quadro)
    poses_dedo, _ = _arrastar_membro_gpu(sessao_panda, quadro, "fingers", (-0.10, -0.25, 0.25))
    assert all(math.isfinite(c) for trio in poses_dedo.values() for c in trio)

    sessao_panda.sincronizar_quadro(quadro)
    piv_h = sessao_panda.renderer._rig_nodes["head"].getPos(render)
    poses_h, p0_h = _arrastar_membro_gpu(sessao_panda, quadro, "head", (-0.45, 0.0, 0.25))
    assert "head" in poses_h
    p1_h = sessao_panda._posicao_alca_membro("head")
    assert p1_h is not None
    v_alc = Vec3(p1_h[0] - piv_h.x, p1_h[1] - piv_h.y, p1_h[2] - piv_h.z)
    v_des = Vec3(p0_h[0] - 0.45 - piv_h.x, p0_h[1] - piv_h.y, p0_h[2] + 0.25 - piv_h.z)
    v_alc.normalize()
    v_des.normalize()
    assert float(v_alc.dot(v_des)) > 0.98


def _verificar_provisoria_e_undo_membro(janela: JanelaEditor, doc: DocumentoEditor) -> None:
    assert janela.abrir_acao("cenas_idle:fone_com_problema", confirmar=False)
    janela.definir_ferramenta(ModoFerramenta.MOVER)
    janela.selecionar_junta("hand")
    alvo = janela._resolver_alvo_mover()
    assert alvo.tipo == "membro" and alvo.juntas_afetadas == ("right-arm", "ant-arm")

    janela.ir_para_tempo(0.25)
    janela.timeline.transporte._btn_autochave.setChecked(False)
    janela._on_mover_iniciado("membro", "x")
    janela._on_mover_atualizado("membro", {"right-arm": (18.0, -25.0, 12.0), "ant-arm": (0.0, 0.0, 42.0)})
    assert doc.provisoria.ativa
    janela._on_atalho_esc()
    assert not doc.provisoria.ativa

    janela.timeline.transporte._btn_autochave.setChecked(True)
    janela.ir_para_tempo(1.0)
    pistas_antes = dict(doc.rascunho["CENAS_IDLE"]["fone_com_problema"]["tracks"])
    janela._on_mover_iniciado("membro", "z")
    janela._on_mover_confirmado("membro", {"right-arm": (22.0, -30.0, 15.0), "ant-arm": (0.0, 0.0, 55.0)})
    pistas_depois = doc.rascunho["CENAS_IDLE"]["fone_com_problema"]["tracks"]
    assert any(abs(t - 1.0) < 1e-3 for t, _ in pistas_depois["right-arm"])
    assert any(abs(t - 1.0) < 1e-3 for t, _ in pistas_depois["ant-arm"])

    janela.desfazer()
    assert doc.rascunho["CENAS_IDLE"]["fone_com_problema"]["tracks"] == pistas_antes
    janela.refazer()
    assert any(abs(t - 1.0) < 1e-3 for t, _ in doc.rascunho["CENAS_IDLE"]["fone_com_problema"]["tracks"]["right-arm"])


def test_janela_editor_mover_membro_undo_esc_e_idle_sem_salto(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Undo/Redo em 1 passo para IK multi-junta, Esc provisório e IDLE_CLIPS sem salto."""
    monkeypatch.setenv("SEJOGA_CONFIG_PATH", str(tmp_path / "cfg.toml"))
    _qt_app()
    doc, copia = _copia_doc(tmp_path)
    janela = JanelaEditor(
        doc,
        habilitar_gpu=False,
        caminho_ui=tmp_path / "ui.json",
        confirmar_pendencias=False,
    )
    try:
        _verificar_provisoria_e_undo_membro(janela, doc)
        assert janela.abrir_acao("idle_clips:calm", confirmar=False)
        janela.ir_para_tempo(0.5)
        janela.selecionar_junta("hand")
        q_ini = janela.sessao.ultimo_quadro.pose["right-arm"]
        alvo_deg = (math.degrees(q_ini.x) + 12.0, math.degrees(q_ini.y) - 8.0, math.degrees(q_ini.z) + 5.0)
        janela._on_mover_iniciado("membro", "x")
        janela._on_mover_confirmado("membro", {"right-arm": alvo_deg, "ant-arm": (0.0, 0.0, 40.0)})
        q_pos = janela.sessao.ir_para(0.5).pose["right-arm"]
        assert math.degrees(q_pos.x) == pytest.approx(alvo_deg[0], abs=0.25)
        assert math.degrees(q_pos.y) == pytest.approx(alvo_deg[1], abs=0.25)
        assert janela.salvar_projeto(forcar=True)
        validar_dados_animacao(carregar_arquivo_animacao(copia).dados)

        assert janela.abrir_acao("locomocao:walk", confirmar=False)
        janela.selecionar_junta("right-feet")
        assert janela._resolver_alvo_mover().tipo == "membro"
        janela.selecionar_junta("body")
        assert janela._resolver_alvo_mover().tipo == ""
    finally:
        janela.close()

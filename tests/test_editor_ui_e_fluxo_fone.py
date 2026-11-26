"""Testes completos de interface Qt, fluxo 'Fone com problema', CLI e Panda offscreen."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6 import QtCore, QtWidgets  # noqa: F401
from PySide6.QtWidgets import QApplication

from sejoga.__main__ import build_parser
from sejoga.editor.catalogo import construir_catalogo
from sejoga.editor.documento import DocumentoEditor
from sejoga.editor.janela_editor import JanelaEditor
from sejoga.editor.persistencia import (
    CAMINHO_ANIMATION_PADRAO,
    carregar_arquivo_animacao,
)
from sejoga.editor.sessao_previa import ModoPrevia, SessaoPrevia
from sejoga.editor.viewport_panda import (
    EstadoOverlays,
    ModoCamera,
    PandaViewportSession,
)


def _qt_app() -> QApplication:
    inst = QApplication.instance()
    if isinstance(inst, QApplication):
        return inst
    return QApplication([])


def _executar_etapas_fone(janela: JanelaEditor, doc: DocumentoEditor) -> None:
    janela.catalogo.buscar("fone")
    visiveis = set(janela.catalogo.acoes_visiveis_ids())
    assert "cenas_idle:fone_com_problema" in visiveis
    assert "vfx:estouro_fone" in visiveis

    assert janela.abrir_acao("cenas_idle:fone_com_problema", confirmar=False)
    janela.ir_para_tempo(0.85)
    janela.definir_modo_camera(ModoCamera.LATERAL)
    janela.selecionar_junta("right-arm")

    chave_orig = min(
        doc.rascunho["CENAS_IDLE"]["fone_com_problema"]["tracks"]["right-arm"],
        key=lambda kv: abs(kv[0] - 0.85),
    )
    y_orig = float(chave_orig[1][1])
    y_novo = -45.0
    janela._on_gizmo_iniciado("right-arm", "y")
    janela._on_gizmo_atualizado("right-arm", (61.4, -60.0, 23.6))
    janela._on_gizmo_confirmado("right-arm", (61.4, y_novo, 23.6))
    assert doc.pode_desfazer
    chave_alvo = min(
        doc.rascunho["CENAS_IDLE"]["fone_com_problema"]["tracks"]["right-arm"],
        key=lambda kv: abs(kv[0] - 0.85),
    )
    assert abs(chave_alvo[1][1] - y_novo) < 1e-2

    janela.desfazer()
    chave_desf = min(
        doc.rascunho["CENAS_IDLE"]["fone_com_problema"]["tracks"]["right-arm"],
        key=lambda kv: abs(kv[0] - 0.85),
    )
    assert abs(chave_desf[1][1] - y_orig) < 1e-2
    janela.refazer()

    janela._on_efeito_janela_preview("estouro_fone", 3.60, 4.00)
    janela._on_efeito_janela_confirmada("estouro_fone", 3.60, 4.00)
    assert doc.rascunho["CENAS_IDLE"]["fone_com_problema"]["janelas_efeito"][
        "estouro_fone"
    ] == (3.6, 4.0)


def test_fluxo_completo_fone_com_problema_e_salvamento_isolado(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _qt_app()
    monkeypatch.setenv("SEJOGA_CONFIG_PATH", str(tmp_path / "cfg.toml"))
    anim_copia = tmp_path / "animation.py"
    shutil.copy2(CAMINHO_ANIMATION_PADRAO, anim_copia)
    ui_prefs = tmp_path / "editor_ui.json"

    doc = DocumentoEditor(carregar_arquivo_animacao(anim_copia))
    janela = JanelaEditor(
        doc,
        habilitar_gpu=False,
        caminho_ui=ui_prefs,
        confirmar_pendencias=False,
    )
    try:
        _executar_etapas_fone(janela, doc)
        janela.disparar_estimulo_contexto("click")
        assert janela.sessao.modo == ModoPrevia.EM_CONTEXTO
        assert "click" in janela.sessao.ultimo_quadro.prioridade_contexto

        assert janela.salvar_projeto()
        recarregado = carregar_arquivo_animacao(anim_copia)
        assert recarregado.dados["CENAS_IDLE"]["fone_com_problema"]["janelas_efeito"][
            "estouro_fone"
        ] == (3.6, 4.0)
    finally:
        janela.close()

    assert ui_prefs.is_file()


def test_conflito_externo_banner_curvas_e_paineis_recolhiveis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _qt_app()
    monkeypatch.setenv("SEJOGA_CONFIG_PATH", str(tmp_path / "cfg.toml"))
    anim_copia = tmp_path / "animation.py"
    shutil.copy2(CAMINHO_ANIMATION_PADRAO, anim_copia)
    doc = DocumentoEditor(carregar_arquivo_animacao(anim_copia))
    janela = JanelaEditor(
        doc,
        habilitar_gpu=False,
        caminho_ui=tmp_path / "ui.json",
        confirmar_pendencias=False,
    )
    try:
        # Gráfico de curvas e recolhimento dos painéis
        janela.timeline.alternar_curvas(True)
        assert janela.timeline._pilha.currentIndex() == 1
        janela.timeline.alternar_curvas(False)
        assert janela.timeline._pilha.currentIndex() == 0

        assert not janela.catalogo.isHidden()
        assert not janela.inspetor.isHidden()
        janela._alternar_catalogo(False)
        janela._alternar_inspetor(False)
        assert janela.catalogo.isHidden()
        assert janela.inspetor.isHidden()

        # Simula alteração externa antes de salvar
        anim_copia.write_text(
            anim_copia.read_text(encoding="utf-8") + "\n# alterado fora\n",
            encoding="utf-8",
        )
        janela._on_campo_editado(
            "Alterar escala VFX",
            ("VFX", "estouro_fone", "escala"),
            8.0,
        )
        assert not janela.salvar_projeto()
        assert not janela.banners._frame_erro.isHidden()
        assert not janela.banners._btn_rec.isHidden()
        assert not janela.banners._btn_retry.isHidden()
    finally:
        janela.close()


def test_cli_registra_subcomando_editor() -> None:
    parser = build_parser()
    ns = parser.parse_args(
        ["editor", "--acao", "cenas_idle:fone_com_problema", "--sem-gpu"],
    )
    assert ns.command == "editor"
    assert ns.acao == "cenas_idle:fone_com_problema"
    assert ns.sem_gpu is True


def test_viewport_panda_offscreen_render_cameras_e_overlays() -> None:
    _qt_app()
    sessao_panda = PandaViewportSession(0, 320, 240)
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
        quadro_salvo = previa.avaliar_quadro_salvo()
        sessao_panda.overlays = EstadoOverlays(
            grade=True,
            ossos=True,
            contatos=True,
            ancoras=True,
            trilhas=True,
            comparar_salvo=True,
        )
        for modo in (
            ModoCamera.PERSPECTIVA,
            ModoCamera.FRONTAL,
            ModoCamera.LATERAL,
            ModoCamera.COMPANION,
        ):
            sessao_panda.definir_modo_camera(modo)
            sessao_panda.sincronizar_quadro(
                quadro,
                controller=previa._controller,
                quadro_salvo=quadro_salvo,
                trilhas_pts=([(0.0, 0.0, 0.2), (0.2, 0.1, 0.4)], [(0.0, 0.0, 0.2), (0.1, 0.1, 0.3)]),
            )
            sessao_panda.step()
    finally:
        sessao_panda.destruir()

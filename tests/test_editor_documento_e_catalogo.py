"""Testes de catálogo, documento, desfazer/refazer, pose provisória e pureza."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from sejoga.editor.catalogo import (
    FAMILIAS_ORDEM,
    buscar_catalogo,
    construir_catalogo,
)
from sejoga.editor.documento import DocumentoEditor
from sejoga.editor.mutacoes_pistas import (
    inserir_ou_atualizar_chave,
    mover_chave_indice,
    mutar_caminho_rascunho,
    remover_chave_no_tempo,
)
from sejoga.editor.persistencia import carregar_arquivo_animacao


def test_catalogo_cobre_todas_familias_e_busca_fone() -> None:
    doc = DocumentoEditor()
    acoes = construir_catalogo(doc.rascunho)
    familias_presentes = {a.familia_id for a in acoes}
    for fam_id, _ in FAMILIAS_ORDEM:
        assert fam_id in familias_presentes

    resultados_fone = buscar_catalogo(acoes, "fone")
    ids_fone = {a.id for a in resultados_fone}
    assert "cenas_idle:fone_com_problema" in ids_fone
    assert "cenas_idle:ajeitar_fone" in ids_fone
    assert "vfx:estouro_fone" in ids_fone


def test_transacao_gera_um_desfazer_e_cancelamento_reverte() -> None:
    doc = DocumentoEditor()
    escala_orig = doc.rascunho["VFX"]["estouro_fone"]["escala"]

    doc.iniciar_transacao("Arrastar escala")
    doc.atualizar_transacao(
        lambda d: mutar_caminho_rascunho(d, ("VFX", "estouro_fone", "escala"), 6.0),
    )
    doc.atualizar_transacao(
        lambda d: mutar_caminho_rascunho(d, ("VFX", "estouro_fone", "escala"), 7.5),
    )
    assert doc.confirmar_transacao()

    assert doc.rascunho["VFX"]["estouro_fone"]["escala"] == 7.5
    assert doc.desfazer() == "Arrastar escala"
    assert doc.rascunho["VFX"]["estouro_fone"]["escala"] == escala_orig
    assert doc.refazer() == "Arrastar escala"
    assert doc.rascunho["VFX"]["estouro_fone"]["escala"] == 7.5

    doc.iniciar_transacao("Cancelar")
    doc.atualizar_transacao(
        lambda d: mutar_caminho_rascunho(d, ("VFX", "estouro_fone", "escala"), 12.0),
    )
    assert doc.cancelar_transacao()
    assert doc.rascunho["VFX"]["estouro_fone"]["escala"] == 7.5


def test_pose_provisoria_impede_salvamento_ate_gravar_ou_descartar(
    tmp_path: Path,
) -> None:
    destino = tmp_path / "animation.py"
    shutil.copy2(carregar_arquivo_animacao().caminho, destino)
    doc = DocumentoEditor(carregar_arquivo_animacao(destino))

    doc.definir_provisoria(
        "cenas_idle:fone_com_problema",
        None,
        1.1,
        "right-arm",
        (10.0, -40.0, 25.0),
    )
    assert doc.provisoria.ativa
    with pytest.raises(ValueError):
        doc.salvar()

    assert doc.gravar_provisoria_em_pista("CENAS_IDLE", "fone_com_problema")
    assert not doc.provisoria.ativa
    doc.salvar()


def test_reducao_duracao_detecta_conflitos_e_ajusta(tmp_path: Path) -> None:
    destino = tmp_path / "animation.py"
    shutil.copy2(carregar_arquivo_animacao().caminho, destino)
    doc = DocumentoEditor(carregar_arquivo_animacao(destino))

    conflitos = doc.verificar_reducao_duracao("CENAS_IDLE", "fone_com_problema", 3.0)
    assert conflitos
    assert any(c.tempo_s > 3.0 for c in conflitos)

    assert doc.aplicar_nova_duracao(
        "CENAS_IDLE",
        "fone_com_problema",
        3.0,
        ajustar_excedentes=True,
    )
    novo_bloco = doc.rascunho["CENAS_IDLE"]["fone_com_problema"]
    assert novo_bloco["duration"] == 3.0
    assert novo_bloco["janelas_efeito"]["estouro_fone"][1] <= 3.0


def test_mutacoes_pistas_mantem_curvas_alinhadas() -> None:
    doc = DocumentoEditor()
    bloco = doc.rascunho["CENAS_IDLE"]["fone_com_problema"]
    qtd_antes = len(bloco["tracks"]["right-arm"])

    idx = inserir_ou_atualizar_chave(bloco, "right-arm", 0.6, (5.0, -5.0, 5.0))
    assert len(bloco["tracks"]["right-arm"]) == qtd_antes + 1
    assert len(bloco["curvas"]["right-arm"]) == len(bloco["tracks"]["right-arm"]) - 1

    novo_idx = mover_chave_indice(bloco, "right-arm", idx, 0.7)
    assert abs(bloco["tracks"]["right-arm"][novo_idx][0] - 0.7) < 1e-4

    assert remover_chave_no_tempo(bloco, "right-arm", 0.7)
    assert len(bloco["tracks"]["right-arm"]) == qtd_antes
    assert len(bloco["curvas"]["right-arm"]) == qtd_antes - 1


def test_modulos_puros_editor_nao_importam_engines() -> None:
    modulos = (
        "sejoga.editor.esquema",
        "sejoga.editor.persistencia",
        "sejoga.editor.roteiro",
        "sejoga.editor.documento",
        "sejoga.editor.catalogo",
        "sejoga.editor.sessao_previa",
        "sejoga.editor.mutacoes_pistas",
    )
    proibidos = ("panda3d", "win32gui", "win32con", "win32api")
    for nome in modulos:
        mod = sys.modules[nome]
        for proibido in proibidos:
            assert proibido not in getattr(mod, "__dict__", {})

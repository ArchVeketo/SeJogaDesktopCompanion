"""Testes da sessão de prévia: determinismo, seek reverso, solo/mudo e contexto."""

from __future__ import annotations

from dataclasses import replace

from sejoga.editor.catalogo import construir_catalogo
from sejoga.editor.documento import DocumentoEditor
from sejoga.editor.mutacoes_pistas import inserir_ou_atualizar_chave
from sejoga.editor.roteiro import (
    EstimuloRoteiro,
    ObstaculoPrevia,
    RoteiroEnsaio,
)
from sejoga.editor.sessao_previa import ModoPrevia, SessaoPrevia
from sejoga.musica.escuta_musica import MusicSnapshot
from sejoga.nucleo.modelo import load_model
from sejoga.nucleo.recursos import resolve_model


def _acao_por_id(doc: DocumentoEditor, acao_id: str):
    return next(a for a in construir_catalogo(doc.rascunho) if a.id == acao_id)


def test_determinismo_busca_reversa_e_reset_em_loop() -> None:
    doc = DocumentoEditor()
    sessao = SessaoPrevia(doc, semente=42)
    resets: list[int] = []
    sessao.registrar_callback_reset(lambda: resets.append(1))
    acao = _acao_por_id(doc, "cenas_idle:fone_com_problema")

    sessao.selecionar_acao(acao)
    q_avancado = sessao.ir_para(1.5)
    assert abs(q_avancado.tempo_s - 1.5) < 1e-4

    # Seek reverso obriga reset determinístico e idêntico quadro
    sessao.ir_para(3.0)
    q_reverso = sessao.ir_para(1.5)
    assert len(resets) >= 2
    assert q_reverso.pose == q_avancado.pose


def test_solo_e_mudo_isolam_juntas_em_tomada() -> None:
    doc = DocumentoEditor()
    sessao = SessaoPrevia(doc)
    acao = _acao_por_id(doc, "cenas_idle:fone_com_problema")
    sessao.selecionar_acao(acao)

    q_normal = sessao.ir_para(1.0)
    sessao.definir_solo("right-arm")
    q_solo = sessao.reavaliar_quadro_atual()
    assert q_solo.pose["right-arm"] == q_normal.pose["right-arm"]

    sessao.definir_solo(None)
    sessao.alternar_silenciada("right-arm")
    q_mudo = sessao.reavaliar_quadro_atual()
    assert q_mudo.pose["right-arm"] != q_normal.pose["right-arm"]


def test_modo_contexto_prioridade_estimulo_e_comparacao_salvo() -> None:
    doc = DocumentoEditor()
    sessao = SessaoPrevia(doc)
    acao = _acao_por_id(doc, "cenas_idle:fone_com_problema")
    sessao.selecionar_acao(acao)
    sessao.ir_para(0.85)

    doc.aplicar_edicao(
        "Ajustar ombro",
        lambda d: inserir_ou_atualizar_chave(
            d["CENAS_IDLE"]["fone_com_problema"],
            "right-arm",
            0.85,
            (40.0, -45.0, 20.0),
        ),
    )
    q_rascunho = sessao.reavaliar_quadro_atual()
    q_salvo = sessao.avaliar_quadro_salvo()
    assert q_rascunho.pose["right-arm"] != q_salvo.pose["right-arm"]

    q_click = sessao.disparar_estimulo_agora(
        EstimuloRoteiro(tempo_s=0.85, tipo="click"),
    )
    assert q_click.modo == ModoPrevia.EM_CONTEXTO
    assert "click" in q_click.prioridade_contexto


def test_estimulo_cena_usa_nome_dos_dados_em_contexto() -> None:
    doc = DocumentoEditor()
    sessao = SessaoPrevia(doc)
    sessao.selecionar_acao(_acao_por_id(doc, "idle_clips:calm"))
    sessao.definir_modo(ModoPrevia.EM_CONTEXTO)
    sessao.definir_roteiro(
        RoteiroEnsaio(
            estimulos=(
                EstimuloRoteiro(
                    tempo_s=0.2, tipo="cena", dados={"nome": "ajeitar_fone"}
                ),
            ),
        )
    )

    quadro = sessao.ir_para(0.5)

    assert quadro.amostra_cena.ativa
    assert quadro.amostra_cena.nome == "ajeitar_fone"


def test_selecao_cria_roteiro_de_cena_sem_afetar_idle_da_mesma_familia() -> None:
    doc = DocumentoEditor()
    sessao = SessaoPrevia(doc)
    cena = _acao_por_id(doc, "cenas_idle:ajeitar_fone")
    idle = _acao_por_id(doc, "idle_clips:calm")
    assert cena.familia_id == idle.familia_id

    sessao.selecionar_acao(cena)
    assert len(sessao.roteiro.estimulos) == 1
    evento = sessao.roteiro.estimulos[0]
    assert evento.tipo == "cena"
    assert evento.dados["nome"] == "ajeitar_fone"

    sessao.selecionar_acao(idle)
    assert not sessao.roteiro.estimulos


def test_danca_ritmo_ao_vivo_tentaculos_obstaculo_e_trilha() -> None:
    doc = DocumentoEditor()
    snap = MusicSnapshot(
        is_playing=True,
        audio_active=True,
        bpm=124.0,
        beat_phase=0.05,
        beat_detected=True,
        audio_level=0.85,
        bass_level=0.75,
    )
    sessao = SessaoPrevia(doc, provedor_musica=lambda: snap)
    acao_danca = _acao_por_id(doc, "danca:tuning")
    sessao.selecionar_acao(acao_danca)
    sessao.definir_roteiro(
        replace(sessao.roteiro, usar_musica_ao_vivo=True, metronomo_ativo=True),
    )
    q_danca = sessao.ir_para(0.5)
    assert q_danca.bpm_efetivo == 124.0
    assert q_danca.batida_ativa is True

    acao_tent = _acao_por_id(doc, "tentaculos:porta")
    sessao.selecionar_acao(acao_tent)
    sessao.definir_roteiro(
        RoteiroEnsaio(
            obstaculo=ObstaculoPrevia(
                ativo=True,
                centro=(0.0, 0.25, 0.2),
                meia_extensao=(0.45, 0.45, 0.45),
            ),
        ),
    )
    q_tent = sessao.ir_para(1.2)
    assert q_tent.tentaculos_ativos
    assert q_tent.pontos_tentaculos

    acao_cena = _acao_por_id(doc, "cenas_idle:fone_com_problema")
    sessao.selecionar_acao(acao_cena)
    model = load_model(resolve_model())
    pts_r, pts_s = sessao.amostrar_trilha(model, "hand", passos=12)
    assert len(pts_r) == 13
    assert len(pts_s) == 13

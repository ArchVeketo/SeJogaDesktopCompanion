"""Estado puro do modo confirmar do calibrador."""

from __future__ import annotations

import json

import pytest

from sejoga.rig_mapa.confirmacao_poses import POSES, ConfirmacaoPoses, Resposta


def test_responder_avanca_e_conclui():
    estado = ConfirmacaoPoses()

    for _ in POSES:
        estado.responder(Resposta.CORRETO)

    assert estado.concluido()
    assert set(estado.respostas()) == {p.nome for p in POSES}


def test_avancar_pula_respondidas_e_volta_circular():
    estado = ConfirmacaoPoses()
    estado.responder(Resposta.ERRADO)  # responde a 1ª, vai para a 2ª
    estado.avancar(-1)  # volta: a 1ª já foi respondida, cai na última

    assert estado.atual.nome == POSES[-1].nome


def test_salvar_e_carregar_ida_e_volta(tmp_path):
    destino = tmp_path / "confirmacao.json"
    estado = ConfirmacaoPoses()
    estado.selecionar("aceno")
    estado.responder(Resposta.ERRADO)
    estado.salvar(destino)

    dados = json.loads(destino.read_text(encoding="utf-8"))
    assert dados["respostas"]["aceno"]["resposta"] == "errado"
    assert not destino.read_bytes().startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in destino.read_bytes()

    outro = ConfirmacaoPoses()
    assert outro.carregar(destino) == 1
    assert outro.respostas() == {"aceno": Resposta.ERRADO}


def test_carregar_ignora_lixo():
    estado = ConfirmacaoPoses()

    assert estado.carregar_dict({"respostas": {"inexistente": {"resposta": "correto"},
                                               "aceno": {"resposta": "talvez"}}}) == 0


def test_selecionar_pose_desconhecida_falha():
    with pytest.raises(KeyError):
        ConfirmacaoPoses().selecionar("nao-existe")


def test_hud_mostra_pergunta_e_teclas():
    linhas = ConfirmacaoPoses().linhas_hud()

    assert POSES[0].pergunta in linhas
    assert any("1 = correto" in linha for linha in linhas)

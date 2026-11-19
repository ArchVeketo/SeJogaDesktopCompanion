"""Testes de esquema, validação, serialização AST e persistência atômica do editor."""

from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from sejoga.animacao import dados_autorais
from sejoga.animacao.cenas_idle import amostrar_cena_idle
from sejoga.editor.esquema import TOP_LEVEL_KEYS
from sejoga.editor.persistencia import (
    CAMINHO_ANIMATION_PADRAO,
    ConflitoArquivoExternoError,
    ErroPersistenciaAnimacao,
    carregar_arquivo_animacao,
    parse_texto_animation,
    salvar_arquivo_animacao,
    serializar_dados_animacao,
    validar_dados_animacao,
)


def test_paridade_roundtrip_todas_familias(tmp_path: Path) -> None:
    arq = carregar_arquivo_animacao(CAMINHO_ANIMATION_PADRAO)
    assert set(arq.dados.keys()) == set(TOP_LEVEL_KEYS)

    destino = tmp_path / "animation.py"
    shutil.copy2(CAMINHO_ANIMATION_PADRAO, destino)
    arq_tmp = carregar_arquivo_animacao(destino)
    gravado = salvar_arquivo_animacao(
        arq_tmp.caminho,
        arq.dados,
        sha256_esperado=arq_tmp.sha256,
    )
    recarregado = carregar_arquivo_animacao(gravado.caminho)

    for chave in TOP_LEVEL_KEYS:
        assert recarregado.dados[chave] == arq.dados[chave]


def test_parse_rejeita_chamadas_e_codigo_arbitrario() -> None:
    codigo_malicioso = 'IDLE_CLIPS = {"calm": {"duration": eval("1")}}\n'
    with pytest.raises(ErroPersistenciaAnimacao):
        parse_texto_animation(codigo_malicioso)


def test_validar_rejeita_curva_junta_ancora_e_duracao_invalidas() -> None:
    arq = carregar_arquivo_animacao(CAMINHO_ANIMATION_PADRAO)

    dados_curva = deepcopy(arq.dados)
    dados_curva["CENAS_IDLE"]["fone_com_problema"]["curvas"]["right-arm"] = (
        "bezier_inexistente",
    )
    with pytest.raises(ErroPersistenciaAnimacao):
        validar_dados_animacao(dados_curva)

    dados_ancora = deepcopy(arq.dados)
    dados_ancora["VFX"]["estouro_fone"]["ancora"] = "osso_que_nao_existe"
    with pytest.raises(ErroPersistenciaAnimacao):
        validar_dados_animacao(dados_ancora)

    dados_dur = deepcopy(arq.dados)
    dados_dur["IDLE_CLIPS"]["calm"]["duration"] = -1.0
    with pytest.raises(ErroPersistenciaAnimacao):
        validar_dados_animacao(dados_dur)


def test_conflito_externo_sha256_e_overwrite_forcado(tmp_path: Path) -> None:
    destino = tmp_path / "animation.py"
    shutil.copy2(CAMINHO_ANIMATION_PADRAO, destino)
    arq = carregar_arquivo_animacao(destino)

    conteudo_ext = destino.read_text(encoding="utf-8") + "\n# externo\n"
    destino.write_text(conteudo_ext, encoding="utf-8")

    alterado = deepcopy(arq.dados)
    alterado["VFX"]["estouro_fone"]["escala"] = 7.25

    with pytest.raises(ConflitoArquivoExternoError):
        salvar_arquivo_animacao(
            arq.caminho,
            alterado,
            sha256_esperado=arq.sha256,
            forcar=False,
        )

    salvo_forcado = salvar_arquivo_animacao(
        arq.caminho,
        alterado,
        sha256_esperado=arq.sha256,
        forcar=True,
    )
    recarregado = carregar_arquivo_animacao(salvo_forcado.caminho)
    assert recarregado.dados["VFX"]["estouro_fone"]["escala"] == 7.25


def test_override_rascunho_runtime_reflete_em_cenas() -> None:
    arq = carregar_arquivo_animacao(CAMINHO_ANIMATION_PADRAO)
    rascunho = deepcopy(arq.dados)
    bloco = rascunho["CENAS_IDLE"]["fone_com_problema"]
    tracks = dict(bloco["tracks"])
    chaves = list(tracks["right-arm"])
    chaves[1] = (chaves[1][0], (15.0, -33.0, 22.0))
    tracks["right-arm"] = tuple(chaves)
    bloco["tracks"] = tracks

    antes = amostrar_cena_idle("fone_com_problema", 0.42)
    with dados_autorais.usar_rascunho(rascunho):
        durante = amostrar_cena_idle("fone_com_problema", 0.42)
    depois = amostrar_cena_idle("fone_com_problema", 0.42)

    assert antes.delta_rig != durante.delta_rig
    assert depois.delta_rig == antes.delta_rig


def test_serializacao_gera_cabecalho_limpo() -> None:
    arq = carregar_arquivo_animacao(CAMINHO_ANIMATION_PADRAO)
    texto = serializar_dados_animacao(arq.dados)
    assert "IDLE_CLIPS" in texto
    assert "CENAS_IDLE" in texto
    assert "CLIPES_GLTF" in texto

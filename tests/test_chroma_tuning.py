"""Testes do helper puro de derivação do color key (chroma_tuning)."""

from __future__ import annotations

from sejoga.render.chroma_tuning import (
    CHROMA_CLEAR_MAGENTA,
    CHROMA_MAGENTA_RGB,
    derivar_chroma,
    pixel_e_chroma,
)


def test_default_reproduz_magenta_historico():
    config = derivar_chroma()
    assert config.rgb == CHROMA_MAGENTA_RGB
    assert config.clear_rgba == CHROMA_CLEAR_MAGENTA


def test_calibracao_magenta_equivale_aos_limiares_antigos():
    config = derivar_chroma("#FF00FF")
    assert config.limites == ((129, 255), (0, 19), (129, 255))


def test_pixel_e_chroma_para_magenta():
    config = derivar_chroma("#FF00FF")
    # Pixel magenta pós-tonemap (R/B altos, G quase nulo) é adotado.
    assert pixel_e_chroma((230, 5, 230), config)
    # Verde alto (superfície) é rejeitado.
    assert not pixel_e_chroma((230, 200, 230), config)
    # R/B baixos são rejeitados.
    assert not pixel_e_chroma((100, 5, 100), config)


def test_cor_configurada_chega_ao_rgb_e_clear():
    config = derivar_chroma("#00FF00")
    assert config.rgb == (0.0, 1.0, 0.0)
    assert config.clear_rgba == (0.0, 1.0, 0.0, 0.0)
    # Verde é o canal alto; vermelho e azul são baixos.
    assert config.limites == ((0, 19), (129, 255), (0, 19))
    assert pixel_e_chroma((5, 230, 5), config)


def test_chroma_intermediario():
    assert pixel_e_chroma((96, 96, 96), derivar_chroma("#606060"))

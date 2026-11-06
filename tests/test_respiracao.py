"""Contratos do motor de respiração (engine-agnóstico, sem GPU)."""

from sejoga.animacao.respiracao import Respiracao


def test_norm_oscila_e_fica_em_zero_um():
    respiracao = Respiracao(frequencia=0.25, amplitude=1.0)
    amostras = []

    for _ in range(600):  # ~10 s a 1/60
      respiracao.atualizar(1.0 / 60.0)
      valor = respiracao.norm
      assert 0.0 <= valor <= 1.0
      amostras.append(valor)

    # Precisa variar de forma perceptível ao longo do tempo (oscila).
    assert max(amostras) - min(amostras) > 0.3


def test_independencia_de_framerate():
    lento = Respiracao(frequencia=0.25, amplitude=1.0)
    rapido = Respiracao(frequencia=0.25, amplitude=1.0)

    tempo = 0.0
    while tempo < 3.0:
      lento.atualizar(1.0 / 30.0)
      tempo += 1.0 / 30.0

    tempo = 0.0
    while tempo < 3.0:
      rapido.atualizar(1.0 / 120.0)
      tempo += 1.0 / 120.0

    assert abs(lento.centrada - rapido.centrada) < 0.05


def test_empurrar_infla_e_depois_decai():
    respiracao = Respiracao(frequencia=0.25, amplitude=1.0)
    # Estabiliza a partir do repouso antes de medir o impulso.
    for _ in range(30):
      respiracao.atualizar(1.0 / 60.0)

    antes = respiracao.centrada
    respiracao.empurrar(0.8)
    for _ in range(10):
      respiracao.atualizar(1.0 / 60.0)
    pico = respiracao.centrada

    # Empurrar aumenta o valor (infla o peito).
    assert pico > antes

    # Sem novos empurrões, o impulso decai e o valor recua do pico.
    for _ in range(180):
      respiracao.atualizar(1.0 / 60.0)
    assert respiracao.centrada < pico


def test_reset_volta_ao_repouso():
    respiracao = Respiracao()
    respiracao.empurrar(1.0)
    for _ in range(20):
      respiracao.atualizar(1.0 / 60.0)

    respiracao.reset()
    assert respiracao.centrada == 0.0
    assert respiracao.fase == 0.0

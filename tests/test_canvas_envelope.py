"""Dimensionamento da janela por envelope: estável e sem corte.

Prova — sem engine gráfico — que a janela não oscila para uma sequência de
poses variáveis (causa do flicker) e que o degrau escolhido sempre comporta
a pose de pior caso (não reintroduz o corte do Mário).
"""

import itertools
import math

from sejoga.render.canvas_envelope import (
    COOLDOWN,
    MARGEM_ANTICORTE,
    EstadoEnvelope,
    degrau_para,
    degraus_envelope,
    escolher_tamanho,
    extensao_necessaria,
)

BASE = 480


def _rodar_sequencia(necessarios, *, dt=1.0 / 60, dragging=False, base=BASE):
    """Aplica uma sequência de necessidades e devolve os tamanhos escolhidos."""

    estado = EstadoEnvelope()
    atual = base
    tamanhos = []
    for necessario in necessarios:
        atual = escolher_tamanho(necessario, atual, base, estado, dt, dragging=dragging)
        tamanhos.append(atual)

    return tamanhos


def test_degraus_sao_poucos_e_discretos():
    assert degraus_envelope(BASE) == [480, 960, 1440]


def test_degrau_sempre_comporta_a_necessidade_com_margem():
    # Abaixo do teto, o degrau escolhido cobre necessidade + margem anti-corte.
    for necessario in (0, 400, 479, 600, 931, 1200):
        degrau = degrau_para(necessario, BASE)
        if degrau < BASE * 3:
            assert degrau >= necessario + MARGEM_ANTICORTE


def test_pose_de_pior_caso_nao_corta():
    # Torso rolado ±178° com membros estendidos: extensão perto de 2*base.
    necessario = BASE * 2 - 10
    degrau = degrau_para(necessario, BASE)
    assert degrau >= necessario
    assert degrau == 1440  # precisa do degrau maior por causa da margem


def test_necessidade_acima_do_teto_satura_sem_erro():
    assert degrau_para(5000, BASE) == 1440


def test_tamanho_nao_oscila_para_pose_jitterosa():
    # Simula o ringing da mola subamortecida em volta de ~0,8*base: a
    # necessidade sobe e desce dentro de um degrau. O tamanho deve ficar
    # cravado no degrau de repouso, sem nenhuma troca.
    jitter = [BASE * (0.5 + 0.35 * math.sin(i * 0.7)) for i in range(240)]
    tamanhos = _rodar_sequencia(jitter)

    assert set(tamanhos) == {BASE}


def test_cruzar_degrau_cresce_uma_vez_e_estabiliza():
    # Necessidade salta para o degrau estendido e lá oscila: cresce uma vez
    # e permanece, mesmo com a necessidade balançando dentro do degrau.
    necessarios = [BASE * 1.6 + 60 * math.sin(i * 0.9) for i in range(240)]
    tamanhos = _rodar_sequencia(necessarios)

    assert set(tamanhos) == {960}


def test_oscilacao_na_fronteira_do_degrau_nao_pulsa():
    # Necessidade oscila cruzando a fronteira entre repouso e estendido. Sem
    # o cooldown simétrico isso pulsaria; aqui deve haver no máximo uma
    # transição por período de cooldown — nunca alternância frame a frame.
    fronteira = BASE - MARGEM_ANTICORTE  # logo acima => degrau 2
    necessarios = [fronteira + (120 if i % 2 == 0 else -120) for i in range(120)]
    tamanhos = _rodar_sequencia(necessarios)

    trocas = sum(1 for a, b in itertools.pairwise(tamanhos) if a != b)
    # Em 2 s a ~60 fps, com cooldown de 0,6 s, no máximo ~4 trocas; o antigo
    # resize por frame faria dezenas. Garante que não há pulso por frame.
    assert trocas <= 4


def test_arraste_cresce_imediato_mas_nunca_encolhe():
    estado = EstadoEnvelope()
    # Cresce na hora para não cortar durante o arraste.
    size = escolher_tamanho(BASE * 2, BASE, BASE, estado, 0.01, dragging=True)
    assert size == 1440
    # Mesmo com a necessidade caindo, não encolhe enquanto arrasta.
    for _ in range(60):
        size = escolher_tamanho(0, size, BASE, estado, 0.5, dragging=True)
    assert size == 1440


def test_arraste_por_pe_fixa_degrau_sem_pular():
    # Pose rolada ~155° pendurado pelo pé: o bbox projetado oscila muito
    # (ex.: alternando ~700 e ~1000 px) por muitos frames. Com fixar_degrau,
    # o tamanho deve ficar CONSTANTE e comportar o maior necessário da
    # sequência (nunca corta). Começa já no degrau estendido que a fiação de
    # window.py garante (>= 2*base) para o arraste por pé.
    necessarios = [700 if i % 2 == 0 else 1000 for i in range(200)]
    # O degrau inicial já comporta o pico da sequência (como a fiação de
    # window.py garante ao arrastar pelo pé): não há nenhuma troca.
    atual_inicial = degrau_para(max(necessarios), BASE)
    estado = EstadoEnvelope()
    atual = atual_inicial
    tamanhos = []
    for necessario in necessarios:
        atual = escolher_tamanho(
            necessario, atual, BASE, estado, 1.0 / 60,
            dragging=True, fixar_degrau=True,
        )
        tamanhos.append(atual)

    assert set(tamanhos) == {atual_inicial}
    assert min(tamanhos) >= max(necessarios)


def test_arraste_por_pe_sobe_uma_vez_se_exceder_e_estabiliza():
    # Se a necessidade exceder o degrau travado, sobe UMA vez para o menor
    # que comporta e ali permanece, mesmo com a oscilação continuando.
    estado = EstadoEnvelope()
    atual = BASE * 2
    tamanhos = []
    for i in range(120):
        necessario = 1500 if i % 3 == 0 else 900
        atual = escolher_tamanho(
            necessario, atual, BASE, estado, 1.0 / 60,
            dragging=True, fixar_degrau=True,
        )
        tamanhos.append(atual)

    # Sobe para o teto (1440) por causa do pico 1500 e fica cravado lá.
    assert set(tamanhos) == {BASE * 3}


def test_sem_fixar_degrau_a_mesma_sequencia_pode_pular():
    # Contraste: sem fixar_degrau, uma sequência que cruza fronteiras pode
    # trocar de degrau (o que no arraste por pé causaria a piscada).
    necessarios = [700 if i % 2 == 0 else 1000 for i in range(200)]
    tamanhos = _rodar_sequencia(necessarios, dragging=True)

    assert len(set(tamanhos)) > 1


def test_encolhe_apos_soltar_respeitando_cooldown():
    estado = EstadoEnvelope()
    size = escolher_tamanho(BASE * 2, BASE, BASE, estado, 0.01, dragging=True)
    assert size == 1440
    # Soltou: logo após crescer o cooldown ainda segura o encolhimento.
    size = escolher_tamanho(0, size, BASE, estado, 0.01, dragging=False)
    assert size == 1440
    # Passado o cooldown simétrico, encolhe de volta ao repouso.
    size = escolher_tamanho(0, size, BASE, estado, COOLDOWN, dragging=False)
    assert size == BASE


def test_extensao_necessaria_centrada_com_folga():
    pontos = [(-100, 0), (100, 0), (0, -80), (0, 80)]
    assert extensao_necessaria(pontos) == 100 * 2 + 32


def test_extensao_ignora_pontos_nao_finitos():
    pontos = [(math.inf, 0), (50, 0), (0, 40)]
    assert extensao_necessaria(pontos) == 50 * 2 + 32

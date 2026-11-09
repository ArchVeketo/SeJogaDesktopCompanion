"""Testes para as funções delta de cada estado de animação."""
import pytest

from sejoga.animacao.body_motion import BodyPose
from sejoga.animacao.delta_states import (
    delta_drag,
    delta_fall,
    delta_fisica,
    delta_idle,
    delta_sleep,
    delta_walk,
)
from sejoga.animacao.rig_base import pose_repouso
from sejoga.nucleo.rig import IdlePersonality, Rotation3


def test_delta_idle_produz_delta_nao_pose_absoluta():
    """delta_idle retorna delta (diferença), não pose absoluta."""
    delta = delta_idle(1.0, IdlePersonality.CALM)

    # Delta não deve ter valores enormes como uma pose absoluta teria
    # Por exemplo, a pose de repouso tem right-arm.z ≈ 1.19 rad (68°)
    # Mas o delta deveria ser pequeno (oscilação)
    for grupo, rotacao in delta.items():
        # Deltas de idle são pequenos (oscilações)
        assert abs(rotacao.x) < 1.0, f"{grupo}.x muito grande para um delta"
        assert abs(rotacao.y) < 1.0, f"{grupo}.y muito grande para um delta"
        # z pode ser maior para ajustes de braço, mas não tanto quanto a pose completa
        assert abs(rotacao.z) < 2.0, f"{grupo}.z muito grande para um delta"


def test_delta_idle_personalidades_autorais():
    """Personalidades com clips autorais (street, fighter, etc) produzem deltas."""
    for style in ("street", "fighter", "rhythm", "stylish"):
        delta = delta_idle(2.5, IdlePersonality(style))
        # Deve ter conteúdo (não vazio)
        assert delta, f"delta_idle({style}) retornou vazio"


def test_delta_drag_varia_por_grab_part():
    """delta_drag produz deltas diferentes dependendo de onde está sendo arrastado."""
    motion = BodyPose(roll=5, pitch=-10, limb_swing=15)

    drag_body = delta_drag(motion, "body")
    drag_arm = delta_drag(motion, "right-arm")
    drag_leg = delta_drag(motion, "legs")

    # Cada tipo de arraste deve produzir pose diferente
    assert drag_body != drag_arm
    assert drag_body != drag_leg
    assert drag_arm != drag_leg


def test_delta_drag_perna_recolhe_bracos():
    """Arraste pela perna não ergue os braços acima do repouso (FK real)."""
    from fk_bracos import punho

    motion = BodyPose(limb_swing=0)
    delta = delta_drag(motion, "legs")
    base = pose_repouso()
    composta = {
        g: Rotation3(r.x + delta.get(g, Rotation3()).x, r.y + delta.get(g, Rotation3()).y,
                     r.z + delta.get(g, Rotation3()).z)
        for g, r in base.items()
    }

    # O alvo drag_perna é o ponto livre mais baixo (ver arm_targets): os punhos
    # ficam no máximo na altura do repouso, nunca acima.
    for lado in ("right", "left"):
        assert punho(composta, lado)[1] <= punho(base, lado)[1] + 1e-6, lado


def test_delta_walk_alterna_bracos():
    """delta_walk produz oscilação alternada dos braços."""
    delta1 = delta_walk(0.0)
    delta2 = delta_walk(0.5)

    # Em tempos diferentes, os braços devem estar em posições diferentes
    if "right-arm" in delta1 and "right-arm" in delta2:
        assert delta1["right-arm"].x != delta2["right-arm"].x


def test_delta_walk_run_tem_mais_amplitude():
    """delta_walk com run=True tem mais amplitude que caminhada."""
    walk = delta_walk(0.25, run=False)
    run = delta_walk(0.25, run=True)

    # A amplitude do balanço deve ser maior na corrida
    # (testamos em um ponto onde o sin não é zero)
    if "body" in walk and "body" in run:
        # Em algum eixo a corrida deve ter valor absoluto maior
        assert (
            abs(run["body"].x) >= abs(walk["body"].x) or
            abs(run["body"].y) >= abs(walk["body"].y)
        )


def test_delta_fall_reage_a_velocidade():
    """delta_fall produz deltas diferentes baseado na velocidade."""
    subindo = delta_fall(0.5, velocity=(0, -500))
    descendo = delta_fall(0.5, velocity=(0, 500))

    # Cabeça deve ter inclinação diferente subindo vs descendo
    assert subindo["head"].x != descendo["head"].x


def test_delta_sleep_tem_posicao_relaxada():
    """delta_sleep inclina a cabeça para baixo (dormindo)."""
    delta = delta_sleep(0.0)

    # Cabeça pendente no sono
    assert "head" in delta
    assert delta["head"].x < 0, "Cabeça deveria pender no sono"


def test_delta_fisica_aplica_motion_ao_corpo():
    """delta_fisica converte BodyPose em deltas para body e head."""
    motion = BodyPose(roll=10, pitch=-5, yaw=3, head_roll=2, head_pitch=-1)
    delta = delta_fisica(motion)

    # Deve conter body e head
    assert "body" in delta
    assert "head" in delta

    # Valores devem corresponder (convertidos para radianos)
    from math import radians
    assert delta["body"].z == pytest.approx(radians(10))
    assert delta["body"].x == pytest.approx(radians(-5))
    assert delta["body"].y == pytest.approx(radians(3))


def test_composicao_delta_com_base_de_repouso():
    """Deltas somados à base de repouso produzem pose válida."""
    from math import degrees

    base = pose_repouso()
    delta = delta_idle(1.0, IdlePersonality.CALM)

    # Compõe manualmente: base + delta
    resultado = {}
    for grupo in base:
        base_rot = base[grupo]
        delta_rot = delta.get(grupo, Rotation3())
        resultado[grupo] = Rotation3(
            base_rot.x + delta_rot.x,
            base_rot.y + delta_rot.y,
            base_rot.z + delta_rot.z,
        )

    # FK do grafo de cena: o idle composto mantém o punho abaixo do ombro e à
    # frente (o idle só soma pequena oscilação sobre o repouso do IK).
    from fk_bracos import punho

    del degrees
    assert punho(resultado, "right")[1] < 0.0
    assert punho(resultado, "right")[2] > 0.0


def test_delta_idle_respiracao_afeta_corpo():
    """delta_idle com respiração ativa infla o peito."""
    sem_respiracao = delta_idle(1.0, IdlePersonality.CALM, respiracao=0.0)
    com_respiracao = delta_idle(1.0, IdlePersonality.CALM, respiracao=0.8)

    # Com respiração, o body deve ter delta x diferente (peito inflado)
    if "body" in sem_respiracao and "body" in com_respiracao:
        assert sem_respiracao["body"].x != com_respiracao["body"].x

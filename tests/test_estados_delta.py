"""Testes para as funções delta de cada estado de animação."""

import pytest

from sejoga.animacao.estados_delta import (
    delta_drag,
    delta_fall,
    delta_fisica,
    delta_idle,
    delta_sleep,
    delta_walk,
)
from sejoga.animacao.movimento_corpo import BodyPose
from sejoga.animacao.pose_repouso import pose_repouso
from sejoga.nucleo.esqueleto import IdlePersonality, Rotation3


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
        g: Rotation3(
            r.x + delta.get(g, Rotation3()).x,
            r.y + delta.get(g, Rotation3()).y,
            r.z + delta.get(g, Rotation3()).z,
        )
        for g, r in base.items()
    }

    # O alvo drag_perna é o ponto livre mais baixo (ver arm_targets): os punhos
    # ficam no máximo na altura do repouso, nunca acima.
    for lado in ("right", "left"):
        assert punho(composta, lado)[1] <= punho(base, lado)[1] + 1e-6, lado


def test_delta_drag_fecha_dedos_com_a_intensidade_e_espelha():
    """Os dedos fecham com a intensidade do arraste; fingers2 usa o espelho."""
    motion = BodyPose()
    solto = delta_drag(motion, "body", 0.0)
    firme = delta_drag(motion, "body", 1.0)

    assert firme["fingers"].z > solto["fingers"].z > 0
    assert firme["fingers2"].z == pytest.approx(-firme["fingers"].z)


def test_delta_drag_mantem_termos_de_balanco_em_z():
    """A intensidade só mexe nos dedos: os braços seguem a física como antes."""
    motion = BodyPose(roll=5, pitch=-10, limb_swing=15)
    sem = delta_drag(motion, "body", 0.0)
    com = delta_drag(motion, "body", 1.0)

    for grupo in ("right-arm", "left-arm", "head"):
        assert sem[grupo] == com[grupo]


def test_delta_soltura_abre_alem_do_ponto_e_fecha_em_zero():
    """Ao largar os dedos abrem (curl negativo) e voltam a zero sem salto."""
    from sejoga.animacao import locomocao_tuning as loc
    from sejoga.animacao.estados_delta import delta_soltura

    abertura = delta_soltura(loc.SOLTURA_ABERTURA_S, 1.0)
    assert abertura["fingers"].z < 0 < abertura["fingers2"].z
    assert delta_soltura(loc.SOLTURA_DURACAO_S, 1.0) == {}
    assert abs(delta_soltura(loc.SOLTURA_DURACAO_S - 1e-4, 1.0)["fingers"].z) < 1e-3


def test_delta_walk_balanca_bracos_por_y_e_quase_sem_torcao():
    """delta_walk balança por y (frente/trás); a torção x é desprezível."""
    from math import pi

    frente = delta_walk(pi / 2)
    tras = delta_walk(3 * pi / 2)

    assert frente["right-arm"].y > 0 > tras["right-arm"].y
    assert abs(frente["right-arm"].y) > 10 * abs(frente["right-arm"].x)
    assert abs(frente["left-arm"].x) < 1e-9


def test_delta_walk_braco_oposto_a_perna():
    """Perna esquerda à frente (sin(fase)>0) = braço direito à frente (y>0)."""
    from math import pi

    from sejoga.animacao.movimento_pernas import LegMotion

    movimento = LegMotion()
    for _ in range(10):
        movimento.update(1 / 60, "walk")
    fase = movimento.phase
    perna_esquerda_a_frente = fase % (2 * pi) < pi
    braco_direito_a_frente = delta_walk(fase)["right-arm"].y > 0

    assert perna_esquerda_a_frente == braco_direito_a_frente


def test_delta_walk_run_tem_mais_amplitude():
    """delta_walk com run=True tem mais amplitude que caminhada."""
    from math import pi

    walk = delta_walk(pi / 2, run=False)
    run = delta_walk(pi / 2, run=True)

    assert abs(run["right-arm"].y) > abs(walk["right-arm"].y)
    assert run["body"].x > walk["body"].x


def test_delta_fall_reage_a_velocidade():
    """delta_fall produz deltas diferentes baseado na velocidade."""
    subindo = delta_fall(0.5, velocity=(0, -500))
    descendo = delta_fall(0.5, velocity=(0, 500))

    # Cabeça deve ter inclinação diferente subindo vs descendo
    assert subindo["head"].x != descendo["head"].x


def test_delta_fall_flail_em_z_e_y_sem_torcao_e_espelhado():
    """A queda balança por z/y; a torção x dos braços é só a base de IK."""
    from math import radians

    base = delta_fall(0.0, (0, 800))
    for t in (0.1, 0.2, 0.3, 0.45):
        delta = delta_fall(t, (0, 800))
        for lado in ("right-arm", "left-arm"):
            assert delta[lado].x == pytest.approx(base[lado].x)
        # Espelho: z e y invertem; fingers2 é o oposto de fingers.
        flail_z = delta["right-arm"].z - base["right-arm"].z
        assert delta["left-arm"].z - base["left-arm"].z == pytest.approx(-flail_z)
        flail_y = delta["right-arm"].y - base["right-arm"].y
        assert delta["left-arm"].y - base["left-arm"].y == pytest.approx(-flail_y)
        assert delta["ant-arm"].z >= base["ant-arm"].z - 1e-9
        assert delta["ant-arm2"].z <= base["ant-arm2"].z + 1e-9

    delta = delta_fall(0.1, (0, 800))
    assert delta["fingers"].z < 0 < delta["fingers2"].z
    assert abs(delta["right-arm"].z - base["right-arm"].z) > radians(1.0)


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


def test_delta_fisica_peito_pendurado_tem_balanco_limitado():
    """Pendurado o renderer já gira o corpo: o peito só soma fração do giro e limitada."""
    from math import degrees

    from sejoga.animacao import movimento_corpo_tuning as tune

    pequeno = delta_fisica(BodyPose(roll=10.0, hanging=1.0))["body"]
    assert degrees(pequeno.z) == pytest.approx(10.0 * tune.PEITO_FATOR_PENDURADO)
    grande = delta_fisica(BodyPose(roll=155.0, pitch=-26.0, hanging=1.0))["body"]
    assert abs(degrees(grande.z)) == pytest.approx(tune.PEITO_PENDURADO_MAX_GRAUS)
    assert abs(degrees(grande.x)) <= tune.PEITO_PENDURADO_MAX_GRAUS + 1e-9


def test_delta_fisica_peito_limiar_igual_ao_do_renderer():
    """Logo acima do limiar já vale o regime pendurado; logo abaixo, o em pé."""
    from sejoga.animacao import movimento_corpo_tuning as tune

    abaixo = delta_fisica(BodyPose(roll=10.0, hanging=tune.PENDURADO_LIMIAR))["body"]
    acima = delta_fisica(BodyPose(roll=10.0, hanging=tune.PENDURADO_LIMIAR + 0.01))[
        "body"
    ]
    assert abaixo.z > acima.z


def test_delta_fisica_peito_mantem_rotacao_em_pe():
    """Em pé (sem suspensão) o peito segue recebendo a resposta física."""
    peito = delta_fisica(BodyPose(roll=10.0, pitch=-5.0, hanging=0.0))["body"]

    assert peito.x != 0.0
    assert peito.z != 0.0


@pytest.mark.parametrize("personalidade", list(IdlePersonality))
def test_delta_idle_fecha_a_frase_sem_pop(personalidade):
    """Na virada do clipe (10 s) o delta não salta: posição contínua."""
    from math import degrees

    antes = delta_idle(9.999, personalidade)
    depois = delta_idle(10.001, personalidade)

    for grupo, rot in antes.items():
        for eixo in "xyz":
            salto = degrees(abs(getattr(rot, eixo) - getattr(depois[grupo], eixo)))
            assert salto < 0.5, (
                f"{personalidade.value}.{grupo}.{eixo} saltou {salto:.2f}"
            )


def test_delta_idle_nove_personalidades_distintas():
    """As nove personalidades produzem deltas diferentes entre si."""
    for t in (0.0, 2.5, 5.0):
        deltas = [delta_idle(t, p) for p in IdlePersonality]
        assert all(a != b for i, a in enumerate(deltas) for b in deltas[i + 1 :]), t


@pytest.mark.parametrize("personalidade", list(IdlePersonality))
def test_delta_idle_respiracao_soma_uma_unica_vez(personalidade):
    """Com respiração=1 o delta difere do de respiração=0 exatamente pela camada."""
    from math import radians

    from sejoga.animacao.clipes_ocioso import camada_respiracao

    sem = delta_idle(3.3, personalidade, respiracao=0.0)
    com = delta_idle(3.3, personalidade, respiracao=1.0)

    for grupo, (ex, ey, ez) in camada_respiracao(1.0, 1.0).items():
        assert com[grupo].x - sem[grupo].x == pytest.approx(radians(ex))
        assert com[grupo].y - sem[grupo].y == pytest.approx(radians(ey))
        assert com[grupo].z - sem[grupo].z == pytest.approx(radians(ez))

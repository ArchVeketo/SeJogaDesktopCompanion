import math
from itertools import pairwise

from sejoga.animacao.animation import AnimationController, AnimationState
from sejoga.nucleo.rig import ALL_GROUPS, Rig, Rotation3


def controller():
    return AnimationController(Rig(rest={group: Rotation3() for group in ALL_GROUPS}))


def test_controller_starts_in_composed_idle_pose_not_t_pose():
    from math import degrees
    animation = controller()
    pose = animation.update(1 / 60)
    # Pós-IK, o repouso tem os braços BAIXADOS (mãos ao lado do quadril):
    # right-arm.z ≈ -86° e o espelho ≈ +86° (Z mede a elevação a partir de +X,
    # Z=-90 reto p/ baixo, Z=0 lateral/T-pose). A INTENÇÃO permanece: não
    # iniciar em T-pose (Z≈0) nem com o braço solto/aberto — e sim baixado.
    assert degrees(pose["right-arm"].z) < -60
    assert degrees(pose["left-arm"].z) > 60


def test_hover_reaches_toward_the_cursor_without_flapping_both_arms():
    neutral = controller()
    for _ in range(40):
        base_pose = neutral.update(1 / 60)
    animation = controller()
    for _ in range(40):
        pose = animation.update(1 / 60, hovered=True, look_direction=.8)
    assert animation.state == AnimationState.HOVER
    assert pose["left-arm"].z > pose["right-arm"].z * -1
    assert pose["left-arm"].z - base_pose["left-arm"].z > .2


def test_hover_keeps_personality_phrase_and_arm_motion():
    animation = controller()
    animation.set_idle_personality("fighter")
    samples = []
    for frame in range(180):
        pose = animation.update(1/60, hovered=True, look_direction=.5)
        if frame > 60:
            samples.append(pose["right-arm"])
    assert animation.state == AnimationState.HOVER
    assert animation._idle_clock > 2.9
    assert len(set(samples)) > 50
    # Pós-IK, a base dos braços é BAIXADA (z≈-86°). A frase 'fighter' segue
    # viva por cima (o set acima garante movimento); o braço permanece na
    # região baixada sob o cursor, não escancarado para fora (z>0).
    assert samples[-1].z < 0.0


def test_fall_pose_uses_velocity_not_application_uptime():
    from sejoga.nucleo.rig import pose_thrown
    animation = controller()
    pose_thrown(animation.rig, .7, (0, -600))
    ascending = animation.rig.pose()
    pose_thrown(animation.rig, .7, (0, 600))
    descending = animation.rig.pose()
    assert ascending["head"].x < descending["head"].x
    assert abs(ascending["right-arm"].z - ascending["left-arm"].z) > 0.5
    pose_thrown(animation.rig, 1.8, (180, 700))
    first = animation.rig.pose()
    pose_thrown(animation.rig, 2.5, (180, 700))
    second = animation.rig.pose()
    assert first["right-arm"].z != second["right-arm"].z


def test_wave_turns_palm_out_and_keeps_elbow_bent():
    from math import degrees

    from sejoga.nucleo.assets import resolve_model
    from sejoga.nucleo.model import load_model
    from sejoga.nucleo.rig import pose_flourish
    from sejoga.rig_mapa import rig_debug

    animation = controller()
    pose_flourish(animation.rig, "wave", .95)
    pose = animation.rig.pose()

    # Pós-IK: o aceno leva a MÃO para acima do ombro (alvo de mão), com o
    # cotovelo dobrado — a palma fica virada para FORA com o pulso NEUTRO (a
    # geometria diagonal inverteu o roll de 180° da pose antiga). Verificamos a
    # intenção pela posição/flag reais, não por ângulos crus mal-rotulados.
    estado = rig_debug.estado_rig(pose, load_model(resolve_model()))
    assert estado.mao_direita.palma_flag == "PALMA_PARA_FORA"
    # Mão acima do ombro: offset Y bem positivo em relação ao corpo.
    assert estado.mao_direita.posicao_offset[1] > 0.35
    # Cotovelo dobrado (antebraço ergue em relação ao braço).
    assert estado.articulacoes["cotovelo_direito"].flag == "DOBRADO"


def test_walk_dance_and_drag_poses_have_counterbalanced_arms():
    from math import degrees, pi

    from sejoga.nucleo.rig import pose_dance, pose_drag, pose_walk
    animation = controller()
    pose_walk(animation.rig, 1 / 6)
    walk_left = degrees(animation.rig.current["left-arm"].z)
    pose_walk(animation.rig, .5)
    walk_other = degrees(animation.rig.current["left-arm"].z)
    assert abs(walk_left - walk_other) > 10
    pose_dance(animation.rig, pi / 18)
    dance = animation.rig.pose()
    # No beat o braço condutor ERGUE enquanto o outro fica baixo — braços
    # contrabalançados, não escancarados em espelho. A asserção antiga
    # `right-arm.z < 45` codificava a convenção invertida (erguer = Z baixo);
    # na geometria real, erguer = Z alto. Aqui t=pi/18 → right_lift=1 (direito
    # conduz): o direito sobe (Z alto) e o esquerdo permanece recolhido. Pós-IK
    # a dança parte de um ALVO de mão à frente/em cima e o braço condutor ergue
    # MAIS (Z sobe ~45° com o lift); o gap é menor que o exagero da convenção
    # antiga, mas o braço direito claramente lidera sobre o esquerdo.
    assert degrees(dance["right-arm"].z) > degrees(dance["left-arm"].z) + 15
    # Pós-IK, o arraste estende o braço para a frente pelo AZIMUTE (Y/heading),
    # não pela elevação (Z): cada direção avança um lado diferente. Comparamos
    # o azimute, que é o DOF correto do "reach" na geometria real.
    pose_drag(animation.rig, 0, direction=1, drag_intensity=.8)
    right_drag = animation.rig.pose()
    pose_drag(animation.rig, 0, direction=-1, drag_intensity=.8)
    left_drag = animation.rig.pose()
    assert right_drag["left-arm"].y != left_drag["left-arm"].y
    assert right_drag["right-arm"].y != left_drag["right-arm"].y


def test_raised_arm_survives_the_resolver_clamp_in_the_live_pipeline():
    # Regressão: o clamp anatômico do PoseResolver (passo final do pipeline
    # vivo, aplicado em TODO frame) precisa deixar passar as poses erguidas da
    # base nova. O teto antigo (+65°/-65°) decapitava wave/dance/flourish para
    # ~65° (abaixo da horizontal) — o sintoma "as poses continuam iguais".
    # Este teste dirige pose_resolver.resolver() diretamente (a montante só da
    # composição, a jusante do clamp) e exige que o braço erguido chegue
    # erguido ao renderer.
    from math import degrees

    animation = controller()
    animation.pose_resolver.definir_pose({g: Rotation3() for g in ALL_GROUPS})
    alvo = {g: Rotation3() for g in ALL_GROUPS}
    # Pós-IK, braço reto para CIMA = Z≈+90° (não mais 150°, que na convenção
    # antiga mal-rotulada representava "erguido"). O clamp deve deixar passar a
    # pose erguida sem rebaixá-la.
    alvo["right-arm"] = Rotation3(z=math.radians(90.0))   # reto para cima
    alvo["left-arm"] = Rotation3(z=math.radians(-90.0))   # espelho
    resolvida = None
    for _ in range(120):
        resolvida = animation.pose_resolver.resolver(1 / 60, alvo)
    # Após o clamp, o braço continua erguido (acima da horizontal/T-pose=0°).
    assert degrees(resolvida["right-arm"].z) > 70
    assert degrees(resolvida["left-arm"].z) < -70


def test_wave_reaches_renderer_raised_end_to_end():
    # Pipeline completo: interact('wave') → update() leva o estado a WAVE e
    # a pose renderizada (após crossfade + clamp) precisa erguer a MÃO no
    # pico do gesto, não ser rebaixada pelo clamp.
    from sejoga.nucleo.assets import resolve_model
    from sejoga.nucleo.model import load_model
    from sejoga.rig_mapa import rig_debug

    modelo = load_model(resolve_model())
    animation = controller()
    animation.interact("wave")
    pico_y = -1.0
    viu_wave = False
    for _ in range(140):
        pose = animation.update(1 / 60)
        if animation.state == AnimationState.WAVE:
            viu_wave = True
        estado = rig_debug.estado_rig(pose, modelo)
        pico_y = max(pico_y, estado.mao_direita.posicao_offset[1])
    assert viu_wave
    # Pós-IK: o "erguido" é medido pela POSIÇÃO da mão (que o alvo de mão pede),
    # não pelo ângulo cru do ombro. No pico, a mão sobe bem acima do ombro
    # (offset Y alto) e o clamp não a rebaixa.
    assert pico_y > 0.35


def test_leg_steps_alternate_and_airborne_pose_settles():
    from sejoga.animacao.leg_motion import LegMotion
    legs = LegMotion()
    poses = [legs.update(1/60, "walk", (200, 0)) for _ in range(120)]
    assert any(p.left > 5 and p.right < -5 for p in poses)
    assert any(p.right > 5 and p.left < -5 for p in poses)
    for _ in range(60):
        ascending = legs.update(1/60, "fall", (0, -300))
    for _ in range(60):
        descending = legs.update(1/60, "fall", (0, 300))
    assert ascending.left_knee > 15
    assert descending.left_knee > ascending.left_knee
    fall_steps = [legs.update(1/60, "fall", (120, 300)).left for _ in range(120)]
    assert max(fall_steps) - min(fall_steps) > 4
    for _ in range(120):
        rest = legs.update(1/60, "idle")
    assert abs(rest.left) < .001 and rest.left_knee < .001


def _arraste_por(part):
    """Dirige o controlador em DRAG por ``part`` até a pose convergir."""
    animation = controller()
    pose = None
    for _ in range(240):
        pose = animation.update(1/60, dragging=True, grab_part=part)
    assert animation.state == AnimationState.DRAG
    return pose


def test_arraste_por_perna_pendura_bracos_e_cabeca():
    from math import degrees

    # Pego pela perna/pé: braços e cabeça pendem a favor da gravidade. Pós-IK,
    # "pendente/recolhido junto ao tronco" = braço BAIXADO (Z próximo de -90°),
    # não mais magnitude pequena (a convenção antiga invertia o sentido).
    for part in ('legs', 'left-feet', 'right-feet'):
        pose = _arraste_por(part)
        braco_dir = degrees(pose["right-arm"].z)
        braco_esq = degrees(pose["left-arm"].z)
        # Braços baixados/recolhidos: direito bem negativo, esquerdo bem positivo.
        assert braco_dir < -70, part
        assert braco_esq > 70, part
        # Cabeça pende (olhar para baixo no mundo com o tronco invertido).
        assert degrees(pose["head"].x) > 10, part


def test_arraste_por_perna_difere_de_corpo_e_braco():
    from math import degrees

    perna = _arraste_por('legs')
    corpo = _arraste_por('body')
    braco = _arraste_por('right-arm')
    # Pós-IK: a pose de perna BAIXA mais os braços (Z mais negativo, recolhidos
    # junto ao tronco) do que o arraste pelo corpo, que ergue a mão à frente.
    assert degrees(perna["right-arm"].z) < degrees(corpo["right-arm"].z)
    assert degrees(perna["left-arm"].z) > degrees(corpo["left-arm"].z)
    # As três poses de arraste diferem entre si na posição do braço.
    assert degrees(perna["right-arm"].z) != degrees(braco["right-arm"].z)


def test_click_wakes_sleep_and_does_not_immediately_fall_asleep():
    animation = controller()
    for _ in range(12):
        animation.update(0.1, sleep_after_idle_seconds=1)
    assert animation.state == AnimationState.SLEEP
    animation.interact("click")
    animation.update(0.1, sleep_after_idle_seconds=1)
    assert animation.state == AnimationState.WAKE
    for _ in range(12):
        animation.update(0.1, sleep_after_idle_seconds=1)
    assert animation.state == AnimationState.IDLE


def test_reactions_expire_and_drag_has_priority():
    animation = controller()
    animation.interact("pet")
    animation.update(0.1)
    assert animation.state == AnimationState.PET
    animation.interact("drag_start")
    animation.update(0.1, dragging=True)
    assert animation.state == AnimationState.DRAG
    animation.update(0.1)
    assert animation.state == AnimationState.IDLE


def test_rapid_click_does_not_restart_reaction_forever():
    animation = controller()
    animation.interact("click")
    for _ in range(5):
        animation.interact("click")
        animation.update(0.1)
    assert animation.state == AnimationState.IDLE


def test_hover_tracks_cursor_and_exits_smoothly():
    animation = controller()
    for _ in range(10):
        pose = animation.update(0.1, hovered=True, look_direction=1.0)
    assert animation.state == AnimationState.HOVER
    assert pose["head"].y > 0
    assert pose["door"].y > 0
    previous_pose = pose
    pose = animation.update(0.01)
    assert animation.state == AnimationState.IDLE
    # Authored state holds its first transition frame; hand follow-through
    # remains alive, with no visible discontinuity at the state boundary.
    for group, rotation in pose.items():
        before = previous_pose[group]
        assert max(abs(rotation.x-before.x), abs(rotation.y-before.y),
                   abs(rotation.z-before.z)) < .01


def test_landing_reaction_finishes_and_returns_to_idle():
    animation = controller()
    animation.interact("land")
    animation.update(0.1)
    assert animation.state == AnimationState.LAND
    for _ in range(5):
        animation.update(0.1)
    assert animation.state == AnimationState.IDLE


def test_music_preferences_disable_and_enable_dance():
    animation = controller()
    animation.update(.1, music_playing=True, music_intensity=.5, dance_chance=0)
    assert animation.state == AnimationState.IDLE
    animation.update(.1, music_playing=True, music_intensity=.5, react_to_beat=False)
    assert animation.state == AnimationState.IDLE
    animation.update(.1, music_playing=True, music_intensity=.5)
    assert animation.state == AnimationState.DANCE
    animation.update(.1, music_playing=False)
    assert animation.state == AnimationState.IDLE


def test_music_probability_is_not_sampled_every_frame():
    from unittest.mock import Mock
    animation = controller()
    animation._dance_rng.random = Mock(return_value=.9)
    for _ in range(60):
        animation.update(.016, music_playing=True, music_intensity=.5, dance_chance=.35)
    assert animation.state == AnimationState.IDLE
    assert animation._dance_rng.random.call_count == 1


def test_airborne_motion_never_selects_walk_or_run():
    animation = controller()
    for speed in (150, 500, 1500):
        animation.update(.1, grounded=False, velocity=(speed, 0))
        assert animation.state == AnimationState.FALL


def test_hover_tracks_both_axes_and_new_reactions_generate_distinct_poses():
    animation = controller()
    for _ in range(10):
        pose = animation.update(.1, hovered=True, look_direction=-1, look_vertical=1)
    assert pose["head"].x < 0 and pose["head"].y < 0
    frames = []
    for kind in ("wave", "stretch", "peek", "hit"):
        other = controller()
        other.interact(kind)
        for _ in range(5):
            pose = other.update(.1)
        frames.append(tuple(pose.values()))
        assert other.appendage_remaining > 0 if kind == 'peek' else other.state.value == kind
    assert len(set(frames)) == 4


def test_tentacle_peeks_are_rare_but_manual_peek_remains_available():
    animation = controller()
    animation._personality_rng.seed(1)
    animation._peek_in = 60
    starts = []
    previous = None
    for frame in range(1800):
        animation.update(.1)
        if animation.appendage_remaining > 0 and not previous:
            starts.append(frame/10)
        previous = animation.appendage_remaining > 0
    assert starts and starts[0] >= 59.9
    assert all(b-a >= 60 for a,b in pairwise(starts))
    other = controller()
    other.interact("peek")
    other.update(.1)
    assert other.appendage_remaining > 0


def test_dance_keeps_body_animation_while_peeking_and_ignores_ambient_wave():
    animation = controller()
    for _ in range(60):
        animation.update(1/60, music_playing=True, music_intensity=.5)
    animation.interact('peek')
    animation.interact('wave')
    samples = []
    for _ in range(120):
        pose = animation.update(1/60, music_playing=True, music_intensity=.5)
        assert animation.state == AnimationState.DANCE
        assert animation.appendage_remaining > 0
        samples.append(pose['head'])
    assert len(set(samples)) > 100


def test_silent_dance_preview_expires_without_restarting_itself():
    animation = controller()
    animation.preview_dance('rock')
    for _ in range(120):
        animation.update(1/60)
    assert animation.state == AnimationState.DANCE
    assert animation.dance_motion.style == 'rock'
    for _ in range(900):
        animation.update(1/60)
    assert animation._dance_preview_remaining == 0
    assert animation.state != AnimationState.DANCE


def test_crossfade_por_junta_deixa_a_ponta_balancar_mais_que_a_ancora():
    from math import isfinite

    from sejoga.nucleo.rig import Rotation3
    animation = controller()
    # Estabiliza em idle por muitos frames: o regime estável deixa cada junta
    # com a sua tensão da tabela (sem uniformizar a frequência).
    for _ in range(600):
        animation.update(1 / 60)
    assert animation.state == AnimationState.IDLE

    # Degrau de alvo igual em body (âncora) e fingers (ponta) a partir do mesmo
    # ponto de repouso, avançando só o crossfade por junta.
    degrau = {grupo: Rotation3() for grupo in ALL_GROUPS}
    animation.pose_resolver.definir_pose(degrau)
    alvo = {grupo: Rotation3(x=0.7) for grupo in ("body", "fingers")}
    for _ in range(60):
        resultado = animation.pose_resolver.resolver(1 / 60, alvo)

    body = animation.pose_resolver.molas["body"]
    fingers = animation.pose_resolver.molas["fingers"]
    # Depois da acomodação da âncora, a ponta solta ainda balança/atrasa mais.
    assert abs(fingers.x.value - 0.7) > abs(body.x.value - 0.7)
    for rotacao in resultado.values():
        assert isfinite(rotacao.x) and isfinite(rotacao.y) and isfinite(rotacao.z)
        assert abs(rotacao.x) < 10 and abs(rotacao.y) < 10 and abs(rotacao.z) < 10


def test_double_click_interrupts_single_click_then_recovers():
    animation = controller()
    animation.interact("click")
    animation.update(.1)
    animation.interact("double_click")
    assert animation.body_motion.pitch.velocity < 0
    for _ in range(6):
        pose = animation.update(.1)
    assert animation.state == AnimationState.DOUBLE_CLICK
    assert pose["hand"].z != 0 and pose["ant-arm"].x != 0
    for _ in range(10):
        animation.update(.1)
    assert animation.state == AnimationState.IDLE


def test_surprise_reaction_fires_and_expires_like_the_others():
    animation = controller()
    animation.interact("surprise", direction=.8, strength=1.0)
    animation.update(0.1)
    assert animation.state == AnimationState.SURPRISE
    # Expira dentro da sua janela (0.7 s) e volta ao idle, como as demais.
    for _ in range(10):
        animation.update(0.1)
    assert animation.state == AnimationState.IDLE


def test_surprise_pose_recoils_body_and_turns_head_toward_stimulus():
    from math import degrees

    from sejoga.nucleo.rig import pose_interaction
    animation = controller()
    # Estímulo à direita: a cabeça gira para o lado (y>0) e o tronco recua (x<0).
    pose_interaction(animation.rig, "surprise", 0.35, direction=1.0, vertical=0.0)
    pose = animation.rig.pose()
    assert degrees(pose["head"].y) > 0
    assert degrees(pose["body"].x) < 0


def test_respiracao_fica_parada_no_idle_sem_empurrar():
    # Idle por vários segundos sem empurrar: a respiração não oscila, o valor
    # exposto permanece 0.0 (respiração sob demanda).
    animation = controller()
    for _ in range(600):  # 10 s a 60 fps
        animation.update(1 / 60)
        assert animation.respiracao_valor == 0.0


def test_empurrar_respiracao_infla_e_decai_sozinho():
    # Após empurrar, o valor sobe por alguns frames e depois recua para ~0.
    animation = controller()
    animation.empurrar_respiracao(0.8)
    valor_pico = 0.0
    for _ in range(30):
        animation.update(1 / 60)
        valor_pico = max(valor_pico, abs(animation.respiracao_valor))
    assert valor_pico > 0.0
    # Deixa o impulso decair: o valor volta a 0.0 (sob demanda, sem desligar).
    for _ in range(600):
        animation.update(1 / 60)
    assert abs(animation.respiracao_valor) < 1e-3

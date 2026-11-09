"""Catálogo do rig e utilitários de animação procedural.

O modelo do Mário (export Blockbench 4.12.4) **não tem skin**: os grupos
``head``, ``door``, ``shoulder``... são nós de transformação. Isso permite
animar em Python sem nenhum clip pré-autorado:

    rig.set_rotation("head", yaw=8)      # olha para o lado
    rig.set_rotation("door", yaw=-90)    # abre a portinha

A camada de render só precisa ler ``rig.pose()`` e aplicar nos nós do engine.

Os nomes abaixo foram extraídos do arquivo real (``tools/inspect_model.py``);
``tests/test_model.py`` garante que continuam presentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from itertools import pairwise
from math import degrees, exp, pi, radians, sin, tanh

from sejoga.nucleo.model import Model

# --------------------------------------------------------------------------- #
# IK de braço: resolução preguiçosa do Model + cache dos HPR por alvo de mão
# --------------------------------------------------------------------------- #
# Os gestos de braço declaram ALVOS DE MÃO (ver sejoga.animacao.arm_targets) e o
# solver 3D (sejoga.animacao.arm_ik) os converte nos HPR reais dos bones. Como
# resolver a IK a cada frame custaria caro, cacheamos o HPR por (alvo, lado): os
# alvos dos gestos são fixos, então a cadeia FK roda uma vez por alvo.
_MODELO_IK_CACHE: Model | None = None
_HPR_ALVO_CACHE: dict[tuple, dict[str, Rotation3]] = {}


def _modelo_ik() -> Model:
    """Carrega o Model de produção uma vez (resolução preguiçosa, cacheada)."""
    global _MODELO_IK_CACHE

    if _MODELO_IK_CACHE is None:
        from sejoga.nucleo.assets import resolve_model
        from sejoga.nucleo.model import load_model

        _MODELO_IK_CACHE = load_model(resolve_model())

    return _MODELO_IK_CACHE


def definir_modelo_ik(model: Model | None) -> None:
    """Injeta o Model usado pela IK de braço (ex.: o renderer passa o seu).

    Limpa o cache de HPR para recomputar os alvos com a nova geometria.
    """
    global _MODELO_IK_CACHE

    _MODELO_IK_CACHE = model
    _HPR_ALVO_CACHE.clear()


def braco_hpr_graus(lado: str, nome_alvo: str, model: Model | None = None) -> dict[str, tuple[float, float, float]]:
    """HPR (graus) do braço do ``lado`` para o alvo de mão nomeado em arm_targets.

    Devolve ``{grupo: (x_pitch, y_heading, z_roll)}`` em GRAUS, pronto para
    ``rig.set_rotation``. Cacheado por (lado, nome_alvo). O eixo X (torção) fica
    em 0: o IK posiciona a mão; o giro do pulso é termo aditivo do gesto.
    """
    chave = (lado, nome_alvo)
    cache = _HPR_ALVO_CACHE.get(chave)

    if cache is None:
        from sejoga.animacao import arm_ik
        from sejoga.animacao.arm_targets import ALVOS

        alvo = ALVOS[nome_alvo]
        m = model if model is not None else _modelo_ik()
        alvo_lado = alvo.alvo if lado == "right" else alvo.alvo_espelhado()
        cache = arm_ik.braco_para(m, lado, alvo_lado, alvo.polo)
        _HPR_ALVO_CACHE[chave] = cache

    return {
        grupo: (degrees(rot.x), degrees(rot.y), degrees(rot.z))
        for grupo, rot in cache.items()
    }


def _idle_pulse(t: float, period: float, attack: float, hold: float, release: float, offset: float = 0.0) -> float:
    """One eased gesture followed by a readable rest inside an idle loop."""
    phase = (t + offset) % period

    def ease(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

    if phase < attack:
        return ease(phase / attack)
    phase -= attack
    if phase < hold:
        return 1.0
    phase -= hold
    if phase < release:
        return 1.0 - ease(phase / release)
    return 0.0

#: Grupos que formam o rig animável, por região do corpo.
HEAD_GROUPS = ("head", "door")
BODY_GROUPS = ("body", "legs")
ARM_GROUPS = ("right-arm", "left-arm")
ARM_SUBGROUPS = (
    "shoulder",
    "shoulder2",
    "ant-arm",
    "ant-arm2",
    "hand",
    "hand2",
    "fingers",
    "fingers2",
)
FOOT_GROUPS = ("left-feet", "right-feet")

ALL_GROUPS = HEAD_GROUPS + BODY_GROUPS + ARM_GROUPS + ARM_SUBGROUPS + FOOT_GROUPS


class IdlePersonality(StrEnum):
    CALM = "calm"
    CURIOUS = "curious"
    PLAYFUL = "playful"
    SHY = "shy"
    CONFIDENT = "confident"
    STREET = "street"
    FIGHTER = "fighter"
    RHYTHM = "rhythm"
    STYLISH = "stylish"


@dataclass(frozen=True, slots=True)
class Rotation3:
    """Rotação em radianos (eixo Y = "olhar para os lados")."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Rig:
    """Estado de pose por nome de grupo.

    ``rest`` guarda o estado inicial lido do modelo, para que qualquer pose
    seja relativa (evita "deriva" acumulada entre animações).
    """

    rest: dict[str, Rotation3] = field(default_factory=dict)
    current: dict[str, Rotation3] = field(default_factory=dict)

    @classmethod
    def from_model(cls, model: Model) -> Rig:
        rig = cls()
        for group in ALL_GROUPS:
            if model.find(group) is not None:
                rig.rest[group] = Rotation3()
                rig.current[group] = Rotation3()
        return rig

    @property
    def groups(self) -> tuple[str, ...]:
        return tuple(self.rest)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(g for g in ALL_GROUPS if g not in self.rest)

    def set_rotation(
        self,
        group: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        degrees: bool = True,
    ) -> None:
        """Define a rotação *absoluta* do grupo (em graus por padrão)."""
        if group not in self.rest:
            raise KeyError(f"grupo de rig desconhecido: {group!r}")
        if degrees:
            x, y, z = radians(x), radians(y), radians(z)
        self.current[group] = Rotation3(x, y, z)

    def pose(self) -> dict[str, Rotation3]:
        """Snapshot imutável para o renderizador."""
        return dict(self.current)

    def reset(self) -> None:
        self.current = dict(self.rest)


# --------------------------------------------------------------------------- #
# Presets de pose — ponto de partida para as animações do companion
# --------------------------------------------------------------------------- #
def pose_idle(
    rig: Rig,
    t: float,
    personality: IdlePersonality = IdlePersonality.CALM,
    respiracao: float = 0.0,
) -> None:
    """Idle com personalidade própria, sem deixar de respeitar a dobradiça.

    ``respiracao`` é o valor centrado (-1..1) vindo de ``Respiracao`` (0 no
    repouso); default 0.0 preserva o comportamento de quem não passa respiração.
    A amplitude/bounce por personalidade vêm de ``respiracao_tuning``: o peito
    (``body`` eixo x) infla e ombros/cabeça acompanham de leve, garantindo que
    NENHUM idle fique totalmente estático (sempre respiração + micro-movimento).
    """
    from sejoga.animacao.idle_clips import (
        CLIPS,
        REPOUSO_ANTEBRACO_X,
        REPOUSO_ANTEBRACO_Z,
        REPOUSO_BRACO_X,
        REPOUSO_BRACO_Y,
        REPOUSO_BRACO_Z,
        camada_respiracao,
        sample_idle,
    )
    from sejoga.animacao.respiracao_tuning import parametros_de
    parametros = parametros_de(personality)
    if personality.value in CLIPS:
        pose = sample_idle(personality.value, t, respiracao, parametros.amplitude)
        for group, (x, y, z) in pose.items():
            rig.set_rotation(group, x=x, y=y, z=z)
        return

    breath = sin(t * 0.72)
    sway = sin(t * 0.42)
    # Keep small movements slow enough to read as weight shifts, not vibration.
    finger_breath = sin(t * 0.48) * 2.0

    if personality == IdlePersonality.CURIOUS:
        look = sin(t * 0.43)
        tilt = sin(t * 0.31)
        rig.set_rotation("body", x=breath * 0.9, y=sway * 1.5, z=tilt * 1.2)
        rig.set_rotation("head", x=-3.0 + sin(t * 0.62) * 1.5, y=look * 16.0, z=tilt * 8.0)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        # Curiosa: um braço um pouco mais aberto que a base, para gesto. Parte
        # da base natural (REPOUSO_*) e soma a assinatura própria por cima.
        rig.set_rotation("right-arm", x=REPOUSO_BRACO_X + sin(t * 0.43) * 3.0, y=REPOUSO_BRACO_Y, z=REPOUSO_BRACO_Z - 20.0)
        rig.set_rotation("left-arm", x=REPOUSO_BRACO_X + sin(t * 0.43 + .4) * 2.5, y=-REPOUSO_BRACO_Y, z=-REPOUSO_BRACO_Z)
        rig.set_rotation("ant-arm", x=REPOUSO_ANTEBRACO_X + sin(t * 0.48) * 4.5, z=REPOUSO_ANTEBRACO_Z + tilt * 5.0)
        rig.set_rotation("ant-arm2", x=REPOUSO_ANTEBRACO_X + sin(t * 0.48 + .5) * 3.5, z=-REPOUSO_ANTEBRACO_Z - tilt * 4.0)
        rig.set_rotation("fingers", z=finger_breath + sin(t * .33) * 1.0)
        rig.set_rotation("fingers2", z=finger_breath - sin(t * .33 + .6) * 1.0)
    elif personality == IdlePersonality.PLAYFUL:
        bounce = sin(t * 1.12)
        compression = (1.0 - sin(t * 2.24 + 1.5707963268)) * .5
        rig.set_rotation("body", x=compression * 2.2, y=sway * 2.2, z=bounce * 2.2)
        rig.set_rotation("head", x=-compression * 1.8, y=sin(t * .72) * 6.0, z=bounce * 3.0)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        # More varied arm positions - not always down
        arm_bounce = sin(t * 1.12 + .6)
        # Brincalhona: muito quique, mas a partir da base natural (não do braço
        # pendurado). O balanço vivo fica no sin(...), a pose de osso na base.
        rig.set_rotation("right-arm", x=REPOUSO_BRACO_X + bounce * 6.0, y=REPOUSO_BRACO_Y, z=REPOUSO_BRACO_Z - 14.0 + bounce * 5.0)
        rig.set_rotation("left-arm", x=REPOUSO_BRACO_X + bounce * 6.0, y=-REPOUSO_BRACO_Y, z=-REPOUSO_BRACO_Z + 2.0 - arm_bounce * 5.0)
        rig.set_rotation("ant-arm", x=REPOUSO_ANTEBRACO_X + sin(t * 1.12 + .35) * 8.0, z=REPOUSO_ANTEBRACO_Z + bounce * 7.0)
        rig.set_rotation("ant-arm2", x=REPOUSO_ANTEBRACO_X + sin(t * 1.12 + .35) * 8.0, z=-REPOUSO_ANTEBRACO_Z - arm_bounce * 7.0)
        rig.set_rotation("fingers", z=finger_breath * 1.4 + sin(t * .78) * 2.0)
        rig.set_rotation("fingers2", z=finger_breath * 1.4 - sin(t * .78 + .45) * 2.0)
    elif personality == IdlePersonality.SHY:
        rig.set_rotation("body", x=1.0 + breath * 0.6, y=-2.0 + sway * 1.0, z=-1.5)
        rig.set_rotation("head", x=6.0 + breath * .7, y=sin(t * 0.34) * 4.0, z=-5.0 + sway * 1.5)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        # Varied arm positions - sometimes crossed, sometimes at sides
        arm_variation = sin(t * 0.25) * 8.0
        # Tímida: braços recolhidos junto ao corpo (ombro ainda mais fechado) e
        # cotovelo um pouco mais à frente, partindo da base natural.
        rig.set_rotation("right-arm", x=REPOUSO_BRACO_X + 2.0 + sin(t * 0.3) * 2, y=REPOUSO_BRACO_Y, z=REPOUSO_BRACO_Z + arm_variation)
        rig.set_rotation("left-arm", x=REPOUSO_BRACO_X + 2.0 + sin(t * 0.3 + .4) * 2, y=-REPOUSO_BRACO_Y, z=-REPOUSO_BRACO_Z - arm_variation)
        rig.set_rotation("ant-arm", x=REPOUSO_ANTEBRACO_X + 2.0 + breath * 1.5, z=REPOUSO_ANTEBRACO_Z + sin(t * 0.36) * 4.0)
        rig.set_rotation("ant-arm2", x=REPOUSO_ANTEBRACO_X + 2.0 + breath * 1.2, z=-REPOUSO_ANTEBRACO_Z - sin(t * 0.36 + .25) * 4.0)
        rig.set_rotation("fingers", z=finger_breath * .7 + sin(t * 0.45) * 2.0)
        rig.set_rotation("fingers2", z=finger_breath * .7 + 1.0 + sin(t * 0.45 + .3) * 1.5)
    elif personality == IdlePersonality.CONFIDENT:
        nod = sin(t * 0.4)
        punctuation = _idle_pulse(t, 6.4, .3, .18, .7, offset=1.1)
        rig.set_rotation("body", x=-2.5 + breath * 0.6, y=sway * 1.0, z=sin(t * 0.3) * 1.2)
        rig.set_rotation("head", x=-4.0 + nod * 1.8 - punctuation * 3.0, y=sin(t * 0.29) * 5.0, z=nod * 1.5)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        # More open, confident arm positions with asymmetry
        arm_confidence = sin(t * 0.35) * 3.0
        # Confiante: postura aberta e com leve assimetria viva, mas ancorada na
        # base natural (ombro ligeiramente mais aberto que o repouso).
        rig.set_rotation("right-arm", x=REPOUSO_BRACO_X + sin(t * .3) * 2.5, y=REPOUSO_BRACO_Y, z=REPOUSO_BRACO_Z - 8.0 + arm_confidence)
        rig.set_rotation("left-arm", x=REPOUSO_BRACO_X + sin(t * .3 + .4) * 2.5, y=-REPOUSO_BRACO_Y, z=-REPOUSO_BRACO_Z - arm_confidence * 0.5)
        rig.set_rotation("ant-arm", x=REPOUSO_ANTEBRACO_X + sin(t * 0.4) * 3.5, z=REPOUSO_ANTEBRACO_Z + sway * 3.0)
        rig.set_rotation("ant-arm2", x=REPOUSO_ANTEBRACO_X + sin(t * 0.4 + .4) * 3.5, z=-REPOUSO_ANTEBRACO_Z - sway * 2.5)
        rig.set_rotation("fingers", z=finger_breath + sin(t * 0.5) * 1.5)
        rig.set_rotation("fingers2", z=finger_breath - 1.0 - sin(t * 0.5 + .3) * 1.2)
    else:
        # Calm with subtle variations in arm position
        arm_sway = sin(t * 0.32) * 2.5
        rig.set_rotation("body", x=breath * 0.9, y=sway * 1.5, z=sway * 1.0)
        rig.set_rotation("head", x=sin(t * 0.52) * 1.3, y=sin(t * 0.36) * 3.0)
        rig.set_rotation("door", y=max(0.0, sin(t * .28)) * 3.0)
        # Calma: a base natural quase pura (braços baixados pelo IK do alvo
        # idle), só com micro-deriva de peso. Referência de repouso das 9
        # personalidades. O heading (REPOUSO_BRACO_Y) vem do solver de IK.
        rig.set_rotation("right-arm", x=REPOUSO_BRACO_X + sin(t * 0.36) * 3.0, y=REPOUSO_BRACO_Y, z=REPOUSO_BRACO_Z + sin(t * .4) * 2.0 - breath * .5 + arm_sway * .5)
        rig.set_rotation("left-arm", x=REPOUSO_BRACO_X + sin(t * 0.36) * 3.0, y=-REPOUSO_BRACO_Y, z=-REPOUSO_BRACO_Z - sin(t * .4 + .3) * 2.0 + breath * .5 - arm_sway * .5)
        rig.set_rotation("ant-arm", x=REPOUSO_ANTEBRACO_X + sin(t * .42) * 2.5, z=REPOUSO_ANTEBRACO_Z + sin(t * 0.42) * 4.0)
        rig.set_rotation("ant-arm2", x=REPOUSO_ANTEBRACO_X + sin(t * .42 + .35) * 2.5, z=-REPOUSO_ANTEBRACO_Z - sin(t * 0.42 + .35) * 4.0)
        # Calm hands breathe with the shoulders; no rapid idle twitch.
        rig.set_rotation("fingers", z=finger_breath + sin(t * 0.38) * 1.0)
        rig.set_rotation("fingers2", z=finger_breath + sin(t * 0.38 + .4) * 1.0)

    # Short authored phrases interrupt breathing, then return to the same rest.
    # Each phrase has anticipation, a readable hold and a slower recovery.
    def add(group, x=0.0, y=0.0, z=0.0):
        current = rig.current[group]
        rig.set_rotation(group, x=current.x + radians(x), y=current.y + radians(y),
                         z=current.z + radians(z), degrees=False)

    # Subtle leg shifting during idle for more life
    leg_shift = sin(t * 0.28) * 1.2
    rig.set_rotation("left-feet", x=max(0, leg_shift) * 3.0)
    rig.set_rotation("right-feet", x=max(0, -leg_shift) * 3.0)

    if personality == IdlePersonality.CURIOUS:
        inspect = _idle_pulse(t, 12.0, .8, 1.1, 1.2, offset=2.0)
        follow = _idle_pulse(t, 12.0, 1.0, .9, 1.4, offset=1.8)
        add("head", x=-5 * inspect, y=12 * inspect, z=4 * inspect)
        add("body", y=3 * follow)
        add("right-arm", z=-26 * follow)
        add("ant-arm", x=-8 * follow, z=-24 * follow)
        add("hand", y=10 * follow, z=-8 * follow)
    elif personality == IdlePersonality.PLAYFUL:
        groove = _idle_pulse(t, 9.6, .65, 1.0, 1.1, offset=2.4)
        add("body", y=sin(t * 2.2) * 7 * groove)
        add("head", x=sin(t * 2.2 - .3) * 4 * groove)
        add("right-arm", x=sin(t * 2.2 - .5) * 7 * groove)
        add("left-arm", x=sin(t * 2.2 - .5) * 7 * groove)
        add("right-arm", z=sin(t * 2.2 - .5) * 22 * groove)
        add("left-arm", z=-sin(t * 2.2 - .5) * 18 * groove)
        add("ant-arm", z=sin(t * 2.2 + .2) * 14 * groove)
        add("ant-arm2", z=-sin(t * 2.2 + .55) * 11 * groove)
    elif personality == IdlePersonality.CONFIDENT:
        taunt = _idle_pulse(t, 13.0, .45, .7, 1.1, offset=3.0)
        add("head", x=-4 * taunt, y=-10 * taunt)
        add("body", y=4 * taunt, z=-2 * taunt)
        add("right-arm", z=-22 * taunt)
        add("left-arm", z=12 * taunt)
        add("ant-arm", x=-8 * taunt, z=10 * taunt)
    elif personality == IdlePersonality.SHY:
        glance = _idle_pulse(t, 11.0, .65, .45, 1.2, offset=2.0)
        add("head", y=-12 * glance, x=-3 * glance)
        add("body", y=-2 * glance)
        add("right-arm", z=-16 * glance)
        add("left-arm", z=16 * glance)
        add("ant-arm", z=-16 * glance)
        add("ant-arm2", z=16 * glance)
    else:
        settle = _idle_pulse(t, 14.0, 1.4, .5, 1.8, offset=3.0)
        add("body", z=2 * settle)
        add("head", z=-2.5 * settle)
        add("right-arm", z=-3 * settle)
        add("left-arm", z=3 * settle)

    # Respiração viva por cima das senoides: o peito infla (body.x) e ombros/
    # cabeça acompanham de leve. Somada por último para nunca deixar o idle
    # estático; a amplitude/bounce por personalidade vêm de respiracao_tuning.
    if respiracao:
        for group, (bx, by, bz) in camada_respiracao(respiracao, parametros.amplitude).items():
            add(group, x=bx, y=by, z=bz)


def pose_walk(rig: Rig, t: float, *, run: bool = False) -> None:
    """Passada alternada, lida de um clipe de keyframes (ver anim_clips)."""
    from sejoga.animacao.anim_clips import amostrar_clipe
    frequency = 2.5 if run else 1.5
    # Um ciclo do clipe = uma passada completa; a frequência controla o ritmo.
    pose = amostrar_clipe("run" if run else "walk", t * frequency)
    rig.set_rotation("legs", x=0)
    rig.set_rotation("left-feet", x=0)
    rig.set_rotation("right-feet", x=0)
    for group, (x, y, z) in pose.items():
        rig.set_rotation(group, x=x, y=y, z=z)

    # Compensação de ombro a partir do antebraço amostrado do clipe.
    shoulder_comp = degrees(rig.current["ant-arm"].x) * 0.15
    rig.set_rotation("shoulder", x=shoulder_comp)
    rig.set_rotation("shoulder2", x=-shoulder_comp)


def pose_wave(rig: Rig, t: float) -> None:
    """Aceno: braço direito sobe e o antebraço oscila.

    Braço e cotovelo vêm do IK (``braco_hpr_graus('right', 'wave')``); o balanço
    é a torção do antebraço somada por cima.
    """
    aceno = braco_hpr_graus("right", "wave")
    rb, re = aceno["right-arm"], aceno["ant-arm"]
    rig.set_rotation("right-arm", x=rb[0], y=rb[1], z=rb[2])
    rig.set_rotation("ant-arm", x=re[0] + sin(t * 8.0) * 25.0, y=re[1], z=re[2])
    rig.set_rotation("head", z=6.0)


def pose_dance(rig: Rig, t: float, intensity: float = 0.6) -> None:
    """Dança reativa a batida; ``intensity`` 0..1 amortece a amplitude."""
    amp = 6.0 + 18.0 * max(0.0, min(1.0, intensity))
    beat = sin(t * 9.0)
    rig.set_rotation("body", y=beat * amp * 0.5, z=sin(t * 4.5) * amp * 0.4)
    rig.set_rotation("head", y=sin(t * 4.5) * amp * 0.6, z=beat * amp * 0.3)
    # The door pulses on the beat while the arms take turns leading, with
    # bent elbows to keep the movement readable without mirrored flapping.
    door_open = max(0.0, sin(t * 4.5))
    rig.set_rotation("door", y=door_open * 48.0)
    right_lift = max(0.0, beat)
    left_lift = max(0.0, -beat)
    # IK: mãos à frente/em cima (alvo de dança); o braço condutor ERGUE mais no
    # ritmo. Medido no grafo de cena (oraculo_cena --eixos): elevação = eixo do nó ROLL (anatomia não confirmada na GPU, C3); z mais NEGATIVO =
    # mão mais alta. O lift soma na elevação Z (negativo), não no azimute Y.
    dance_r = braco_hpr_graus("right", "dance")
    dance_l = braco_hpr_graus("left", "dance")
    rb, re = dance_r["right-arm"], dance_r["ant-arm"]
    lb, le = dance_l["left-arm"], dance_l["ant-arm2"]
    # Torção alternada (os braços se revezam): assimetria intencional da dança.
    rig.set_rotation("right-arm", x=rb[0] + beat * amp * .75, y=rb[1], z=rb[2] - 45.0 * right_lift)
    rig.set_rotation("left-arm", x=lb[0] - beat * amp * .75, y=lb[1], z=lb[2] + 45.0 * left_lift)
    rig.set_rotation("ant-arm", y=re[1], z=re[2] + 20.0 * right_lift)
    rig.set_rotation("ant-arm2", y=le[1], z=le[2] - 20.0 * left_lift)
    rig.set_rotation("hand", z=-5.0 + beat * 9.0)
    rig.set_rotation("hand2", z=5.0 - beat * 9.0)
    rig.set_rotation("fingers", z=sin(t * 9.0 + .4) * 8.0)
    rig.set_rotation("fingers2", z=sin(t * 9.0 - .4) * 8.0)
    rig.set_rotation("legs", x=sin(t * 9.0) * amp * 0.25)

    # Shoulder compensation for ant-arm z rotation (minimal since x is ~0)
    # But add subtle shoulder movement for visual appeal
    rig.set_rotation("shoulder", x=sin(t * 9.0) * amp * 0.1)
    rig.set_rotation("shoulder2", x=-sin(t * 9.0) * amp * 0.1)


def pose_drag(rig: Rig, t: float, direction: float = 0.0, drag_intensity: float = 0.0) -> None:
    """Inclina-se na direção do arraste e estende os braços para se equilibrar."""
    grip = max(0, min(1, drag_intensity))
    rig.set_rotation("fingers", z=8 + 24*grip)
    rig.set_rotation("fingers2", z=-8 - 24*grip)

    direction = max(-1.0, min(1.0, direction))
    rig.set_rotation("body", y=-direction * 3.0)
    rig.set_rotation("head", y=direction * 3.0)
    right_reach = max(0.0, -direction)
    left_reach = max(0.0, direction)

    # IK: a mão vai para o ALVO de arraste (à frente, equilibrando). O "reach"
    # por direção estende o braço mais para a frente (PROFUNDIDADE = heading Y),
    # em vez de chutar ângulos diretos. Os termos secundários seguem por cima.
    drag_r = braco_hpr_graus("right", "drag")
    drag_l = braco_hpr_graus("left", "drag")
    rb, re = drag_r["right-arm"], drag_r["ant-arm"]
    lb, le = drag_l["left-arm"], drag_l["ant-arm2"]
    # Reach: leva o braço MAIS para a frente = H positivo no direito (medido no
    # grafo de cena), espelhado (negativo) no esquerdo.
    rig.set_rotation("right-arm", x=rb[0], y=rb[1] + 24.0 * right_reach, z=rb[2])
    rig.set_rotation("left-arm", x=lb[0], y=lb[1] - 24.0 * left_reach, z=lb[2])
    rig.set_rotation("ant-arm", x=re[0], y=re[1], z=re[2] + 20.0 * right_reach)
    rig.set_rotation("ant-arm2", x=le[0], y=le[1], z=le[2] - 20.0 * left_reach)
    rig.set_rotation("hand", z=direction * 10.0)
    rig.set_rotation("hand2", z=direction * 10.0)

    # Shoulder compensation: shoulder follows ~15% of ant-arm x rotation
    shoulder_comp = re[0] * 0.15
    rig.set_rotation("shoulder", x=shoulder_comp)
    rig.set_rotation("shoulder2", x=-shoulder_comp)


def pose_sleep(rig: Rig, t: float) -> None:
    """Pose repousada com respiração lenta."""
    breath = sin(t * 0.75)
    rig.set_rotation("body", x=1.5 + breath * 0.6, z=-2.0)
    rig.set_rotation("head", x=12.0 + breath * 0.8, y=4.0)

    # IK: braços relaxados, mãos recolhidas junto ao corpo (alvo de sono).
    sleep_r = braco_hpr_graus("right", "sleep")
    sleep_l = braco_hpr_graus("left", "sleep")
    rb, re = sleep_r["right-arm"], sleep_r["ant-arm"]
    lb, le = sleep_l["left-arm"], sleep_l["ant-arm2"]
    rig.set_rotation("right-arm", x=rb[0] + 10.0, y=rb[1], z=rb[2])
    rig.set_rotation("left-arm", x=lb[0] + 10.0, y=lb[1], z=lb[2])
    rig.set_rotation("ant-arm", x=re[0] + 8.0, y=re[1], z=re[2])
    rig.set_rotation("ant-arm2", x=le[0] + 8.0, y=le[1], z=le[2])

    # Shoulder compensation (minimal since ant-arms are static)
    rig.set_rotation("shoulder", x=1.2)
    rig.set_rotation("shoulder2", x=-1.2)

    # Fingers: relaxed curl
    rig.set_rotation("fingers", z=15.0 + breath * 2.0)
    rig.set_rotation("fingers2", z=-15.0 - breath * 2.0)


def pose_thrown(rig: Rig, t: float = 0.0, velocity=(0.0, 450.0)) -> None:
    """Readable airborne silhouette driven by ascent/descent, without flailing."""
    descent = .5 + .5 * tanh(velocity[1] / 320.0)
    drift = tanh(velocity[0] / 650.0)
    settle = 1.0 - exp(-max(0, t) * 5)
    air_sway = sin(t * 2.7) * (0.55 + 0.45 * descent)
    # One shoulder catches the air while the other trails; symmetrical arms
    # made the fall read as a rigid T-pose. The body turns into the drift and
    # the wrists lag behind the elbows.
    rig.set_rotation("body", x=-6 + 13 * descent, z=-drift * 10 + air_sway * 2)
    rig.set_rotation("head", x=-6 + 14 * descent, y=-drift * 9, z=drift * 5 - air_sway * 2)
    # IK: silhueta aérea com as mãos abertas para fora (alvo de queda). O
    # descent/drift/air_sway modulam o braço por cima (inércia do voo).
    thr_r = braco_hpr_graus("right", "thrown")
    thr_l = braco_hpr_graus("left", "thrown")
    rb, re = thr_r["right-arm"], thr_r["ant-arm"]
    lb, le = thr_l["left-arm"], thr_l["ant-arm2"]
    rig.set_rotation("right-arm", x=rb[0] - 11 + 8 * descent, y=rb[1], z=rb[2] + 10 * descent + drift * 8 + air_sway * 6)
    rig.set_rotation("left-arm", x=lb[0] - 8 + 6 * descent, y=lb[1], z=lb[2] - 10 * descent + drift * 4 - air_sway * 7)
    rig.set_rotation("ant-arm", x=re[0] - 20 + 8 * descent, y=re[1], z=re[2] + 12 * descent - air_sway * 5)
    rig.set_rotation("ant-arm2", x=le[0] - 14 + 4 * descent, y=le[1], z=le[2] - 12 * descent + air_sway * 4)
    rig.set_rotation("hand", x=8 * settle - 5 * descent, y=drift * 3, z=-18 + drift * 5 - air_sway * 4)
    rig.set_rotation("hand2", x=5 * settle - 3 * descent, y=-drift * 2, z=14 - drift * 3 + air_sway * 3)
    # Fingers spread slightly during fall
    rig.set_rotation("fingers", z=-8 + sin(t * 3.5) * 2)
    rig.set_rotation("fingers2", z=8 - sin(t * 3.5 + 0.5) * 2)
    # Legs move during fall for more natural motion
    rig.set_rotation("left-feet", x=-8 - 12 * descent + 4 * drift)
    rig.set_rotation("right-feet", x=5 - 8 * descent - 4 * drift)


def pose_interaction(rig: Rig, kind: str, t: float, direction: float = 0.0, vertical: float = 0.0) -> None:
    """Reações procedurais: porta gira na dobradiça, sem escala da malha."""
    direction = max(-1.0, min(1.0, direction))
    # Keep arms close during reactions. Hover starts from the current idle
    # pose so the cursor can invite one small, directional reach. As demais
    # interações partem do ALVO de interação (mãos à frente) resolvido por IK.
    _inter_r = braco_hpr_graus("right", "interaction")
    _inter_l = braco_hpr_graus("left", "interaction")
    def _graus(grupo: str) -> tuple[float, float, float]:
        rot = rig.current[grupo]
        return degrees(rot.x), degrees(rot.y), degrees(rot.z)

    # Base completa (P, H, R) do ombro e do cotovelo: a torção do IK escolhe o
    # plano do cotovelo, então não pode ser descartada.
    if kind == "hover":
        rbx, rby, right_base = _graus("right-arm")
        lbx, lby, left_base = _graus("left-arm")
        rex, _rey, right_elbow = _graus("ant-arm")
        lex, _ley, left_elbow = _graus("ant-arm2")
    else:
        rbx, rby, right_base = _inter_r["right-arm"]
        lbx, lby, left_base = _inter_l["left-arm"]
        rex, _rey, right_elbow = _inter_r["ant-arm"]
        lex, _ley, left_elbow = _inter_l["ant-arm2"]
    rig.set_rotation("right-arm", x=rbx, y=rby, z=right_base)
    rig.set_rotation("left-arm", x=lbx, y=lby, z=left_base)
    rig.set_rotation("ant-arm", x=rex, z=right_elbow)
    rig.set_rotation("ant-arm2", x=lex, z=left_elbow)
    rig.set_rotation("head", x=-max(-1.0, min(1.0, vertical)) * 26.0, y=direction * 40.0)
    if kind == "hover":
        right_reach = max(0.0, -direction) ** 1.3
        left_reach = max(0.0, direction) ** 1.3
        down = max(0.0, vertical)
        up = max(0.0, -vertical)
        rig.set_rotation("right-arm", x=rbx - 3.0 - up * 10.0, y=rby,
                         z=right_base - 40.0 * right_reach - 18.0 * up + 10.0 * down)
        rig.set_rotation("left-arm", x=lbx - 3.0 - up * 10.0, y=lby,
                         z=left_base + 40.0 * left_reach + 18.0 * up - 10.0 * down)
        rig.set_rotation("ant-arm", x=rex - 5.0 - up * 12.0,
                         z=right_elbow + 54.0 * right_reach + 14.0 * up)
        rig.set_rotation("ant-arm2", x=lex - 5.0 - up * 12.0,
                         z=left_elbow - 54.0 * left_reach - 14.0 * up)
        rig.set_rotation("hand", z=-5.0 * right_reach)
        rig.set_rotation("hand2", z=5.0 * left_reach)
        rig.set_rotation("fingers", z=-5.0 * right_reach)
        rig.set_rotation("fingers2", z=5.0 * left_reach)
        rig.set_rotation("door", y=20.0)
    elif kind == "click":
        pulse = sin(pi * min(1.0, t / 0.5))
        rig.set_rotation("head", y=direction * 35.0, z=pulse * 8.0)
        rig.set_rotation("door", y=45.0 * sin(t * 4.0 * pi) ** 2)
    elif kind == "double_click":
        from sejoga.animacao.idle_clips import sample_track
        def track(*keys):
            return sample_track(tuple((at, (value, 0, 0)) for at, value in keys), t)[0]
        recoil = track((0, 0), (.18, 5), (.42, -7), (.75, 2), (1.4, 0))
        reach = track((0, 0), (.18, -4), (.44, 1), (.65, 1), (1.4, 0))
        extension = track((0, 0), (.20, -6), (.48, -48), (.72, -42), (1.4, 0))
        rig.set_rotation("body", x=recoil, y=-direction * reach)
        rig.set_rotation("head", x=-recoil * .65, y=direction * 15, z=-recoil * .4)
        rig.set_rotation("right-arm", x=rbx - abs(extension) * .2, y=rby, z=right_base + extension)
        rig.set_rotation("ant-arm", x=rex + extension * .4, z=right_elbow + extension * .3)
        rig.set_rotation("hand", x=-recoil, z=-extension * .2)
        curl = track((0, 0), (.18, 20), (.43, -10), (.8, 4), (1.4, 0))
        rig.set_rotation("fingers", z=curl)
        rig.set_rotation("door", y=max(0, -recoil) * 3)
    elif kind == "pet":
        pulse = sin(pi * min(1.0, t / 1.5))
        rig.set_rotation("head", x=-12.0 * pulse, y=direction * 25.0, z=8.0 * pulse)
        rig.set_rotation("body", z=direction * 5.0 * pulse)
        rig.set_rotation("door", y=pulse * (20.0 + 4.0 * sin(t * 20.0)))
    elif kind == "poke":
        pulse = sin(pi * min(1.0, t / 0.4))
        rig.set_rotation("body", x=-8.0 * pulse)
        rig.set_rotation("head", x=-12.0 * pulse, z=8.0 * pulse)
        # Aponta/cutuca para a frente: parte da base de interação (IK), leva o
        # ombro à frente (H+ no direito) e estica o cotovelo.
        rig.set_rotation("right-arm", x=rbx, y=rby + pulse * 55.0, z=right_base)
        rig.set_rotation("ant-arm", x=rex, z=right_elbow * (1.0 - pulse))
        rig.set_rotation("door", y=35.0 * pulse)
    elif kind == "land":
        pulse = sin(pi * min(1.0, t / 0.45))
        rig.set_rotation("body", x=10.0 * pulse)
        rig.set_rotation("legs", x=-12.0 * pulse)
        rig.set_rotation("head", x=8.0 * pulse)
        rig.set_rotation("door", y=15.0 * pulse)
    elif kind == "wake":
        pulse = sin(pi * min(1.0, t / 1.2))
        rig.set_rotation("body", x=-6.0 * pulse)
        rig.set_rotation("head", x=-10.0 * pulse, y=sin(t * 12.0) * 5.0 * pulse)
        rig.set_rotation("door", y=75.0 * pulse)
        # Acorda: parte dos braços baixados (idle) e os ergue ao espreguiçar.
        # Medido no grafo de cena: elevação = eixo do nó ROLL (anatomia não confirmada na GPU, C3) (Z); z NEGATIVO ergue.
        _wake_r = braco_hpr_graus("right", "idle")["right-arm"]
        _wake_l = braco_hpr_graus("left", "idle")["left-arm"]
        rig.set_rotation("right-arm", x=_wake_r[0], y=_wake_r[1], z=_wake_r[2] - 70.0 * pulse)
        rig.set_rotation("left-arm", x=_wake_l[0], y=_wake_l[1], z=_wake_l[2] + 70.0 * pulse)
        # Shoulder compensation for wake (arms move)
        shoulder_comp = -45.0 * pulse * 0.15  # approx half of 90
        rig.set_rotation("shoulder", x=shoulder_comp)
        rig.set_rotation("shoulder2", x=-shoulder_comp)
    elif kind == "surprise":
        # Susto: recuo rápido do tronco + volta, cabeça e tronco reagindo na
        # direção do estímulo (direction/vertical vêm do gatilho de atenção).
        # Fica na camada de olhar da cabeça/tronco/braço — NADA de giro amplo
        # de corpo aqui (fase posterior). Ganhos CALIBRÁVEIS (validar na GPU).
        _SURPRESA_RECUO = 16.0      # recuo do tronco no pico do susto
        _SURPRESA_CABECA = 20.0     # inclinação extra da cabeça para trás
        _SURPRESA_GIRO = 18.0       # leve giro do tronco em direção ao estímulo
        _SURPRESA_BRACO = 22.0      # braços sobem um pouco (reação de guarda)
        pulse = sin(pi * min(1.0, t / 0.7))
        rig.set_rotation("body", x=-_SURPRESA_RECUO * pulse, y=direction * _SURPRESA_GIRO * pulse)
        rig.set_rotation(
            "head",
            x=-max(-1.0, min(1.0, vertical)) * 26.0 - _SURPRESA_CABECA * pulse,
            y=direction * 40.0,
        )
        # Guarda: os braços sobem um pouco a partir do repouso baixado (IK).
        # elevação = eixo do nó ROLL (anatomia não confirmada na GPU, C3) (Z); z NEGATIVO ergue.
        _surp_r = braco_hpr_graus("right", "idle")["right-arm"]
        _surp_l = braco_hpr_graus("left", "idle")["left-arm"]
        rig.set_rotation("right-arm", x=_surp_r[0], y=_surp_r[1], z=_surp_r[2] - _SURPRESA_BRACO * pulse)
        rig.set_rotation("left-arm", x=_surp_l[0], y=_surp_l[1], z=_surp_l[2] + _SURPRESA_BRACO * pulse)


def pose_flourish(rig: Rig, kind: str, t: float) -> None:
    """Aceno, alongamento, espiada e recuperação de impacto."""
    durations = {"wave": 2.2, "stretch": 2.8, "peek": 9.0, "hit": .65}
    phase = min(1.0, max(0.0, t / durations[kind]))
    envelope = sin(phase * pi)
    # Default dos braços: repouso baixado (IK do alvo idle). Cada ramo ergue a
    # partir daqui conforme o gesto; antes era z=70 (que, pós-IK, seria quase
    # overhead e deixava os gestos tortos).
    _repouso_fl = {**braco_hpr_graus("right", "idle"), **braco_hpr_graus("left", "idle")}
    _fl_r, _fl_l = _repouso_fl["right-arm"], _repouso_fl["left-arm"]
    _fle_r, _fle_l = _repouso_fl["ant-arm"], _repouso_fl["ant-arm2"]
    rig.set_rotation("right-arm", x=_fl_r[0], y=_fl_r[1], z=_fl_r[2])
    rig.set_rotation("left-arm", x=_fl_l[0], y=_fl_l[1], z=_fl_l[2])
    if kind in ("wave", "stretch"):
        from sejoga.animacao.idle_clips import sample_track
        def value(*keys):
            return sample_track(tuple((at, (v, 0, 0)) for at, v in keys), t)[0]
        if kind == "wave":
            # IK: a mão vai para o ALVO do aceno (acima do ombro, à direita) —
            # os HPR do ombro/cotovelo vêm do solver 3D sobre a geometria real,
            # não de ângulos diretos. O ``lift`` interpola do repouso ao alvo; o
            # balanço (``wave``) e o giro do pulso entram aditivos por cima.
            lift = value((0, 0), (.18, -.04), (.58, 1), (1.28, 1), (1.92, .12), (2.2, 0))
            wave = value((0, 0), (.56, 0), (.82, 1), (1.08, -.78), (1.34, .78),
                         (1.58, -.5), (1.82, 0), (2.2, 0))
            repouso = braco_hpr_graus("right", "idle")
            aceno = braco_hpr_graus("right", "wave")

            def _interp(grupo: str, eixo: int) -> float:
                return repouso[grupo][eixo] + (aceno[grupo][eixo] - repouso[grupo][eixo]) * lift

            rig.set_rotation(
                "right-arm",
                x=_interp("right-arm", 0),
                y=_interp("right-arm", 1),
                z=_interp("right-arm", 2),
            )
            rig.set_rotation(
                "ant-arm",
                x=_interp("ant-arm", 0),
                y=_interp("ant-arm", 1),
                z=_interp("ant-arm", 2) + 7 * wave,
            )
            # Braço esquerdo fica em repouso baixado (só o direito acena).
            rig.set_rotation("left-arm", x=_fl_l[0] + 2 * lift, y=_fl_l[1], z=_fl_l[2])
            rig.set_rotation("ant-arm2", x=_fle_l[0] - 3 * lift, z=_fle_l[2])
            # Com o braço na nova orientação de IK (mão acima do ombro), a palma
            # já aponta para FORA com o pulso neutro — a geometria diagonal fez o
            # roll de 180° (necessário na pose antiga) virar a palma para DENTRO.
            # O balanço do aceno (``wave``) oscila o pulso em torno do neutro.
            rig.set_rotation("hand", x=12 * wave, z=2 * wave)
            rig.set_rotation("fingers", z=-8 * lift + 3 * wave)
            rig.set_rotation("body", y=-3 * lift, z=-3 * lift - wave)
            rig.set_rotation("head", y=5 * lift, z=4 * lift + 2 * wave)
        else:
            # Jacket adjustment: natural fidget gesture replacing overhead stretch
            right = value((0, 0), (.28, -.15), (.82, 1), (1.25, .68), (1.95, 0), (2.8, 0))
            left = value((0, 0), (.72, 0), (1.35, 1), (1.78, .62), (2.58, 0), (2.8, 0))
            # Ajuste de jaqueta: ERGUE cada braço em sequência, a partir do
            # repouso baixado (IK). Medido no grafo de cena (oraculo_cena --eixos): elevação = eixo do nó ROLL (anatomia não confirmada na GPU, C3)
            # (Z); z NEGATIVO ergue a mão.
            rig.set_rotation("right-arm", x=_fl_r[0] - 16 * right, y=_fl_r[1], z=_fl_r[2] - 70 * right)
            rig.set_rotation("left-arm", x=_fl_l[0] - 16 * left, y=_fl_l[1], z=_fl_l[2] + 70 * left)
            # O cotovelo DOBRA ao ajustar a jaqueta (antes o sinal pedia
            # hiperextensão, que o clamp do cotovelo zeraria).
            rig.set_rotation("ant-arm", x=_fle_r[0] - 24 * right, z=_fle_r[2] + 22 * right)
            rig.set_rotation("ant-arm2", x=_fle_l[0] - 24 * left, z=_fle_l[2] - 22 * left)
            rig.set_rotation("hand", y=15 * right, z=-8 * right)
            rig.set_rotation("hand2", y=-15 * left, z=8 * left)
            # Body rotates slightly as shoulders roll
            rig.set_rotation("body", y=6 * (right-left), z=3 * (left-right))
            rig.set_rotation("head", y=-8 * (right-left), x=4 * (right+left))
    elif kind == "peek":
        rig.set_rotation("head", y=sin(t * 2) * 12 * envelope, z=5 * envelope)
        opening = min(1.0, t / 2.5, max(0.0, (9.0-t) / 2.5))
        opening = opening*opening*(3-2*opening)
        rig.set_rotation("door", y=85 * opening)
        rig.set_rotation("ant-arm", x=-12 * envelope)
        rig.set_rotation("ant-arm2", x=-12 * envelope)
        # Shoulder compensation for peek
        shoulder_comp = -12 * envelope * 0.15
        rig.set_rotation("shoulder", x=shoulder_comp)
        rig.set_rotation("shoulder2", x=-shoulder_comp)
    else:
        recoil = sin(t * 18) * (1 - phase) ** 2
        rig.set_rotation("body", x=-15 * envelope, z=recoil * 10)
        rig.set_rotation("head", x=-18 * envelope, z=-recoil * 12)
        rig.set_rotation("door", y=40 * envelope)


def pose_sneeze(rig: Rig, t: float) -> None:
    """Three inhalations, downward contraction, then damped recovery."""
    # Slow inhalation, held anticipation, one sharp forward sneeze.
    inhale = min(1.0, max(0.0, t/3.3))
    inhale = inhale*inhale*(3-2*inhale)
    if t >= 3.6:
        inhale *= exp(-(t-3.6)*12)
    inhale += sum(amp*exp(-((t-at)/width)**2) for at, width, amp in ((.65,.24,.25),(1.65,.32,.35),(2.85,.4,.45)))
    hit = exp(-((t-3.68)/.105)**2)
    settle = sin(max(0, t-3.8)*8)*exp(-max(0,t-3.8)*4) if t > 3.8 else 0
    rig.set_rotation('head', x=-10*inhale-42*hit-5*settle, z=-3*inhale)
    rig.set_rotation('body', x=-5*inhale-22*hit-3*settle)
    # Braços partem do repouso baixado (IK); o espirro os ergue um pouco à
    # frente (inhale/hit modulam por cima). Medido no grafo de cena: elevação = eixo do nó ROLL (anatomia não confirmada na GPU, C3)
    # (Z); z NEGATIVO ergue.
    _sz_r = braco_hpr_graus("right", "idle")["right-arm"]
    _sz_l = braco_hpr_graus("left", "idle")["left-arm"]
    _sze = {**braco_hpr_graus("right", "idle"), **braco_hpr_graus("left", "idle")}
    _sze_r, _sze_l = _sze["ant-arm"][2], _sze["ant-arm2"][2]
    rig.set_rotation('right-arm', x=_sz_r[0]-12*inhale-48*hit, y=_sz_r[1], z=_sz_r[2]-40-12*inhale)
    rig.set_rotation('left-arm', x=_sz_l[0]-10*inhale-44*hit, y=_sz_l[1], z=_sz_l[2]+40+10*inhale)
    # Cotovelos DOBRAM (o sinal antigo pedia hiperextensão).
    rig.set_rotation('ant-arm', x=-12*inhale-18*hit, z=_sze_r+20+20*inhale)
    rig.set_rotation('ant-arm2', x=-10*inhale-16*hit, z=_sze_l-20-18*inhale)
    rig.set_rotation('hand', x=15*hit, z=-8*inhale)
    rig.set_rotation('hand2', x=12*hit, z=8*inhale)
    rig.set_rotation('fingers', z=18*inhale-10*hit)
    rig.set_rotation('fingers2', z=-18*inhale+10*hit)
    rig.set_rotation('door', y=120*hit)

    # Rub the closed cabinet's front, then lower the hand gently.
    rub = max(0.0, min(1.0, (t-7.7)/.3, (8.8-t)/.5))
    stroke = sin(t*12)*rub
    if rub:
        rig.set_rotation('right-arm', x=_sz_r[0]-35*rub, y=_sz_r[1], z=_sz_r[2]-40+55*rub)
        rig.set_rotation('ant-arm', x=-28*rub, z=_sze_r+20+48*rub)
        rig.set_rotation('hand', x=20*rub, y=8*stroke, z=10*stroke)
        rig.set_rotation('head', x=3*rub, z=-2*rub)


def pose_secondary(rig: Rig, t: float, state: str, personality=IdlePersonality.CALM) -> None:
    """Small shoulder/wrist follow-through; finger curl follows mirrored rig axes."""
    for forearm, shoulder, hand, fingers, side in (
        ("ant-arm", "shoulder", "hand", "fingers", 1),
        ("ant-arm2", "shoulder2", "hand2", "fingers2", -1),
    ):
        arm = rig.current[forearm]
        authored_hand = rig.current[hand]
        authored_fingers = rig.current[fingers]
        rig.set_rotation(shoulder, x=max(-3, min(3, degrees(arm.x)*.12)))
        arm_roll = degrees(arm.z)
        if state in ('idle', 'hover'):
            # Counterbalance the torso with delayed elbows, rather than a rigid sway.
            rig.set_rotation(forearm, x=degrees(arm.x) + sin(t*.8-side*.45)*1.6,
                             y=degrees(arm.y), z=arm_roll + side*sin(t*.8-side*.6)*2.4)
        wrist_follow = max(-10.0, min(10.0, -arm_roll*.22))
        sway_scale = {
            "idle": 2.2, "hover": 1.8, "walk": 5.0, "run": 6.5,
            "drag": 1.0, "fall": 5.5, "dance": 7.0,
            "wave": .7, "stretch": 1.0, "peek": 1.5, "hit": .4,
            "click": 1.0, "double_click": 1.2, "pet": 1.0,
            "poke": .8, "wake": 1.0, "land": .8,
        }.get(state, 1.5)
        hand_sway = sin(t*.58-side*.35)*sway_scale
        wrist_pitch = -degrees(arm.x)*.24 + sin(t*.52-side*.3)*2.0
        rig.set_rotation(hand, x=degrees(authored_hand.x) + wrist_pitch,
                         y=degrees(authored_hand.y),
                         z=degrees(authored_hand.z) + wrist_follow + side*hand_sway)
        if state != "drag":
            amplitude = 7.0 if personality in (IdlePersonality.CURIOUS, IdlePersonality.PLAYFUL) else 4.5
            curl = 12 + sin(t*.62-side*.3)*amplitude + wrist_follow*.3
            idle_wrist = 0.0
            if state == "idle" and personality == IdlePersonality.CURIOUS and side == 1:
                reach = _idle_pulse(t, 7.8, .65, .55, .9, offset=1.0)
                idle_wrist += 15.0 * reach
                curl -= 5.0 * reach
            elif state == "idle" and personality == IdlePersonality.PLAYFUL and side == 1:
                flick = _idle_pulse(t, 4.8, .18, .08, .35, offset=.7)
                idle_wrist += 10.0 * flick
                curl -= 8.0 * flick
            elif state == "idle" and personality == IdlePersonality.SHY:
                fidget = _idle_pulse(t, 6.2, .5, .2, .6, offset=side * .8)
                idle_wrist += side * 4.0 * fidget
            if state == "sleep":
                curl = 8 + sin(t*.6)*.7
            elif state == "fall":
                # Fingers slightly open during fall
                curl = -5 + sin(t * 4.0) * 3.0
            elif state in ("wave", "stretch", "peek", "hit"):
                # Reactive finger movement during flourishes
                curl = 5 + sin(t * 1.3 + side) * 4.0
            rig.set_rotation(hand, x=degrees(authored_hand.x) + wrist_pitch,
                             y=degrees(authored_hand.y),
                             z=degrees(authored_hand.z) + wrist_follow + side * hand_sway + idle_wrist)
            rig.set_rotation(fingers, z=degrees(authored_fingers.z) + side*curl)


def pose_throw_release(rig: Rig, t: float, grip: float = .5) -> None:
    """Release the captured grip, overshoot open, then settle over 0.9 seconds."""
    keys = [(0, 8+32*max(0, min(1, grip))), (.22, -22), (.6, 7), (.9, 3)]
    curl = keys[-1][1]
    for (a, x), (b, y) in pairwise(keys):
        if t <= b:
            u = max(0, (t-a)/(b-a));u=u*u*(3-2*u)  # noqa: E702  # intencional: smoothstep compacto inline
            curl = x+(y-x)*u
            break
    rig.set_rotation("fingers", z=curl)
    rig.set_rotation("fingers2", z=-curl)

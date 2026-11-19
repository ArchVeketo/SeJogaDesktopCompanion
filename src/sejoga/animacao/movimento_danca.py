"""Coreografia de poses autorais sincronizada com a música."""

from math import cos, exp, floor, pi, radians, sin, tau
from time import monotonic

from sejoga.animacao import danca_tuning as tune
from sejoga.animacao.danca_clipes import (
    amostrar_clipe_emote,
    amostrar_dedos_emote,
    amostrar_deslocamento_emote,
    amostrar_orientacao_raiz_emote,
    amostrar_raiz_emote,
    carregar_clipe_emote,
)
from sejoga.animacao.danca_frases_tuning import frase_do_estilo
from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.poses_danca import amostrar_passo
from sejoga.nucleo.esqueleto import Rotation3

_BANDAS_MIXAMO: dict[str, tuple[str, ...]] = {
    "breakdance": (
        "breakdance",
        "breakdance_1990",
        "flair",
        "breakdance_uprock",
        "breakdance_freeze",
    ),
    "hip_hop": ("hip_hop", "dancing_twerk", "breakdance_uprock", "cyber_bounce"),
}


class DanceMotion:
    """Coreografia da dança sincronizada com a música."""

    def __init__(self):
        """Inicia a dança parada no estilo padrão."""
        self.phase = 0.0
        self.energy = self.bass = 0.0
        self.style = "head_bob"
        self.dwell = 0.0
        self.pose = {}
        self._pose_anterior = {}
        self.tempo = 90.0
        self.strength = 0.0
        self.override = "auto"
        self.style_beats = 0.0
        self.tempo_clipe = 0.0
        self.dz_pelvis_emote = 0.0
        self.giro_corpo_emote = 0.0
        self.raiz_quat_emote = None
        self.deslocamento_emote = (0.0, 0.0)
        self.dedos_clipe = None
        self.acento = 0.0
        self.phrase_phase = 0.0
        self._indice_mixamo = 0
        self._dt_passo = 0.0
        self._pose_suavizada: dict[str, Rotation3] = {}

    def _sincronizar_fase(
        self,
        dt: float,
        beat: bool,
        beat_phase: float | None,
        music_updated_at: float | None,
        now: float | None,
    ) -> None:
        """Avanca a fase da danca e alinha ao ``beat_phase`` compensando latencia."""
        self.phase += dt * self.tempo / 60 * tau
        self.style_beats += dt * self.tempo / 60
        if beat_phase is not None:
            atraso = 0.0
            if music_updated_at is not None and music_updated_at > 0.0:
                agora = monotonic() if now is None else now
                atraso = max(0.0, min(0.25, agora - music_updated_at))
            alvo_rad = ((beat_phase + atraso * self.tempo / 60.0) % 1.0) * tau
            erro = (self.phase - alvo_rad + pi) % tau - pi
            taxa = 14.0 if beat else 12.0
            self.phase -= erro * min(1.0, 1.0 - exp(-max(0.0, dt) * taxa))
        elif beat:
            # Soft phase correction avoids a discontinuity in the joints.
            error = (self.phase + tau / 2) % tau - tau / 2
            self.phase -= error * tune.CORRECAO_FASE
        self.phrase_phase = (self.phase / (tune.COMPASSO_FASE * 2.0)) % 1.0

    def _selecionar_estilo_danca(self, bar_boundary: bool) -> str:
        """Escolhe o estilo ou rotacao Mixamo compativel com o trecho musical."""
        if self.override != "auto":
            return self.override
        desired = (
            "breakdance"
            if self.energy > tune.BREAK_ENERGIA_MIN and self.bass > tune.BREAK_GRAVE_MIN
            else "rock"
            if tune.TEMPO_ROCK_MIN <= self.tempo <= tune.TEMPO_ROCK_MAX
            and self.energy > tune.ROCK_ENERGIA_MIN
            and self.bass < tune.ROCK_GRAVE_MAX
            else "hip_hop"
            if self.bass > tune.HIPHOP_GRAVE_MIN
            and self.energy > tune.HIPHOP_ENERGIA_MIN
            else "head_bob"
        )
        if self.dwell <= 14.0 and self.style in _BANDAS_MIXAMO.get(desired, ()):
            return self.style
        if self.dwell > 14.0 and bar_boundary and desired in _BANDAS_MIXAMO:
            pool = _BANDAS_MIXAMO[desired]
            self._indice_mixamo = (self._indice_mixamo + 1) % len(pool)
            return pool[self._indice_mixamo]
        return desired

    def _atualizar_estilo_e_acento(self, dt: float, bpm: float | None, bar_boundary: bool) -> None:
        """Atualiza o estilo escolhido, relógio de emote, força e acento rítmico."""
        params = tune.parametros_danca()
        desired = self._selecionar_estilo_danca(bar_boundary)
        if desired != self.style and (
            self.override != "auto" or (self.dwell > params["dwell_minimo"] and bar_boundary)
        ):
            self._pose_anterior = self.pose
            self.style, self.dwell = desired, 0.0
            self.style_beats = 0.0
            self.tempo_clipe = 0.0
        clipe_ativo = carregar_clipe_emote(self.style) if self.style != "head_bob" else None
        bpm_real = bpm is not None and bpm > 0.0
        if clipe_ativo is not None and clipe_ativo.bpm_nativo > 0.0 and bpm_real:
            escala_bpm = max(0.80, min(1.25, self.tempo / clipe_ativo.bpm_nativo))
        elif clipe_ativo is not None:
            escala_bpm = 1.0
        else:
            escala_bpm = max(0.88, min(1.18, self.tempo / 108.0)) if bpm_real else 1.0
        velocidade_clipe = clipe_ativo.velocidade if clipe_ativo is not None else 1.0
        self.tempo_clipe += max(0.0, dt) * velocidade_clipe * escala_bpm
        target_strength = (
            params["forca_head_bob"]
            if self.style == "head_bob"
            else params["forca_hip_hop"]
            if self.style == "hip_hop"
            else params["forca_padrao"]
        )
        self.strength += (target_strength - self.strength) * (
            1 - exp(-dt * tune.SUAVIZACAO_FORCA)
        )
        batida = (self.phase / tau) % 1
        downbeat = (self.phase / tune.COMPASSO_FASE) % 1
        acento = (1 - batida) ** 2 * (1 + (1 - downbeat) * params["acento_downbeat"])
        self.acento += (
            acento * (params["acento_base"] + self.energy * params["acento_ganho_energia"])
            - self.acento
        ) * (1 - exp(-dt * tune.SUAVIZACAO_ACENTO))

    def update(
        self,
        dt,
        level,
        bass,
        bpm=None,
        beat=False,
        beat_phase=None,
        music_updated_at=None,
        now=None,
    ):
        """Avança a coreografia com o nível, o grave e o BPM da música."""
        params = tune.parametros_danca()
        blend = 1 - exp(-max(0, dt) * tune.SUAVIZACAO_AUDIO)
        self.energy += (max(0, min(1, level)) - self.energy) * blend
        self.bass += (max(0, min(1, bass)) - self.bass) * blend
        tempo = max(
            params["tempo_min"],
            min(params["tempo_max"], bpm or params["tempo_padrao"]),
        )
        self.tempo += (tempo - self.tempo) * (1 - exp(-dt * tune.SUAVIZACAO_TEMPO))
        previous_bar = int(self.phase / tune.COMPASSO_FASE)
        self._sincronizar_fase(dt, beat, beat_phase, music_updated_at, now)
        bar_boundary = int(self.phase / tune.COMPASSO_FASE) != previous_bar
        self.dwell += dt
        self._dt_passo = max(0.0, dt)
        self._atualizar_estilo_e_acento(dt, bpm, bar_boundary)

    def _posicao_na_frase(self, passos):
        """Devolve (indice do passo, u da batida) da frase de ``passos``.

        O u vem da fase corrigida pelos onsets (acento em u = 0); a batida
        inteira vem de ``style_beats``. Rock acima de ROCK_MEIO_TEMPO_BPM dura
        duas batidas por passo.
        """
        u = (self.phase / tau) % 1
        batida = round(self.style_beats - u) + u
        if self.style == "rock" and self.tempo > tune.ROCK_MEIO_TEMPO_BPM:
            batida /= 2
        return floor(batida) % len(passos), batida % 1

    def _frase_ganho(self) -> float:
        """Envelope musical ZZZ de 1-6s ao longo de 8 batidas."""
        return 0.80 + 0.36 * (0.5 - 0.5 * cos(self.phrase_phase * tau))

    def _groove_tronco(self, rig, pose, pulso, onda, meia_onda):
        # Groove contínuo de coluna, fones e antenas em cascata progressiva (ZZZ)
        # sincronizado à fase da batida e à frase musical.
        energia_ef = (0.55 + 0.45 * self.energy) * self._frase_ganho()
        p_cint = self.phase - 0.15
        p_abd = self.phase - 0.42
        p_pei = self.phase - 0.70
        p_fone = self.phase - 1.05
        p_ant = self.phase - 1.35

        bx, by, bz = pose.get("body", (0.0, 0.0, 0.0))
        hx, hy, hz = pose.get("head", (0.0, 0.0, 0.0))
        if self.style == "head_bob":
            hx -= 6.0 * pulso**4 * energia_ef
            rig.set_rotation("head", x=hx, y=hy, z=hz)

        # 1. Cadeia da coluna com defasagem progressiva (cintura -> abdomen -> peitoral)
        rig.set_rotation(
            "cintura",
            x=bx * 0.25 + (0.5 + 0.5 * cos(p_cint)) * 2.4 * energia_ef,
            y=by * 0.25 + sin(p_cint * 0.5) * 4.8 * energia_ef,
            z=bz * 0.30 + sin(p_cint * 0.5) * 4.0 * energia_ef,
        )
        rig.set_rotation(
            "abdomen",
            x=bx * 0.35 + sin(p_abd) * 2.8 * energia_ef,
            y=by * 0.35 - sin(p_abd * 0.5) * 3.8 * energia_ef,
            z=bz * 0.35 + sin(p_abd * 0.5 - 0.25) * 3.5 * energia_ef,
        )
        rig.set_rotation(
            "peitoral",
            x=bx * 0.45 - (0.5 + 0.5 * cos(p_pei)) * 3.6 * energia_ef,
            y=by * 0.45 + sin(p_pei * 0.5) * 5.4 * energia_ef,
            z=bz * 0.40 - sin(p_pei * 0.5) * 3.2 * energia_ef,
        )

        # 2. Fones e antenas na ponta da hierarquia com chicote secundário atrasado
        rig.set_rotation(
            "fones",
            x=-hx * 0.24 + sin(p_fone) * 3.8 * energia_ef,
            y=-hy * 0.16,
            z=-hz * 0.26 + sin(p_fone * 0.5) * 3.0 * energia_ef,
        )
        rig.set_rotation(
            "fone-direito",
            x=-hx * 0.15,
            y=-hy * 0.10,
            z=-hz * 0.22 + sin(p_fone) * 2.8 * energia_ef,
        )
        rig.set_rotation(
            "fone-esquerdo",
            x=-hx * 0.15,
            y=-hy * 0.10,
            z=-hz * 0.22 - sin(p_fone) * 2.8 * energia_ef,
        )
        rig.set_rotation(
            "antena-direita",
            x=-hx * 0.44 + sin(p_ant) * 8.2 * energia_ef,
            y=-hy * 0.30 + sin(p_ant * 0.5) * 4.2 * energia_ef,
            z=-hz * 0.50 + sin(p_ant) * 7.0 * energia_ef,
        )
        rig.set_rotation(
            "antena-esquerda",
            x=-hx * 0.44 + sin(p_ant) * 8.2 * energia_ef,
            y=-hy * 0.30 - sin(p_ant * 0.5) * 4.2 * energia_ef,
            z=-hz * 0.50 - sin(p_ant) * 7.0 * energia_ef,
        )

    def _aplicar_ombros_zzz(self, rig, energia_ef: float) -> None:
        """Soma atraso hierárquico sutil aos ombros sem sobrescrever o estilo."""
        p_ombro = self.phase - 0.92
        dp = (0.5 + 0.5 * cos(p_ombro) - 0.5) * 2.4 * energia_ef
        dw = sin(p_ombro * 0.5) * 2.2 * energia_ef
        for lado, sinal in (("shoulder", -1.0), ("shoulder2", 1.0)):
            atual = rig.current.get(lado, rig.rest[lado])
            rig.current[lado] = Rotation3(atual.x + dp, atual.y, atual.z + sinal * dw)

    @staticmethod
    def _somar_punhos_dedos(
        rig,
        pose,
        dx_r: float,
        dy_r: float,
        dz_r: float,
        dx_l: float,
        dy_l: float,
        dz_l: float,
        df_r: float,
        df_l: float,
    ) -> None:
        hx_r, hy_r, hz_r = pose.get("hand", (0.0, 0.0, 0.0))
        hx_l, hy_l, hz_l = pose.get("hand2", (0.0, 0.0, 0.0))
        fx_r, fy_r, fz_r = pose.get("fingers", (0.0, 0.0, 0.0))
        fx_l, fy_l, fz_l = pose.get("fingers2", (0.0, 0.0, 0.0))
        rig.set_rotation("hand", x=hx_r + dx_r, y=hy_r + dy_r, z=hz_r + dz_r)
        rig.set_rotation("hand2", x=hx_l + dx_l, y=hy_l + dy_l, z=hz_l + dz_l)
        rig.set_rotation("fingers", x=fx_r, y=fy_r, z=fz_r + df_r)
        rig.set_rotation("fingers2", x=fx_l, y=fy_l, z=fz_l + df_l)

    @classmethod
    def _groove_head_bob(cls, rig, pose, pulso, onda, meia_onda):
        # 3. Groove adicional nos braços, cotovelos, ombros, punhos e dedos por estilo
        rx, ry, rz = pose.get("right-arm", (0.0, 0.0, 0.0))
        lx, ly, lz = pose.get("left-arm", (0.0, 0.0, 0.0))
        arx, ary, arz = pose.get("ant-arm", (0.0, 0.0, 0.0))
        alx, aly, alz = pose.get("ant-arm2", (0.0, 0.0, 0.0))

        rig.set_rotation(
            "right-arm",
            x=rx + onda * 2.5,
            y=ry + meia_onda * 3.0,
            z=rz - pulso * 3.5,
        )
        rig.set_rotation(
            "left-arm",
            x=lx - onda * 2.0,
            y=ly + meia_onda * 2.5,
            z=lz + pulso * 3.0,
        )
        rig.set_rotation("ant-arm", x=arx, y=ary, z=arz + pulso * 4.0)
        rig.set_rotation("ant-arm2", x=alx, y=aly, z=alz - pulso * 4.0)
        rig.set_rotation("shoulder", x=pulso * 2.0, y=0.0, z=-pulso * 2.5)
        rig.set_rotation("shoulder2", x=pulso * 2.0, y=0.0, z=pulso * 2.5)
        cls._somar_punhos_dedos(
            rig, pose, -onda * 6.0, meia_onda * 3.5, onda * 5.0,
            onda * 4.5, meia_onda * 2.5, -onda * 4.0,
            3.0 + pulso * 4.0, -3.0 - pulso * 2.5,
        )

    @classmethod
    def _groove_rock(cls, rig, pose, pulso, onda, meia_onda):
        # 3. Groove adicional nos braços, cotovelos, ombros, punhos e dedos por estilo
        rx, ry, rz = pose.get("right-arm", (0.0, 0.0, 0.0))
        lx, ly, lz = pose.get("left-arm", (0.0, 0.0, 0.0))
        arx, ary, arz = pose.get("ant-arm", (0.0, 0.0, 0.0))
        alx, aly, alz = pose.get("ant-arm2", (0.0, 0.0, 0.0))

        rig.set_rotation(
            "right-arm",
            x=rx + onda * 4.0,
            y=ry + meia_onda * 11.0,
            z=rz - pulso * 7.5,
        )
        rig.set_rotation(
            "left-arm",
            x=lx - onda * 4.5,
            y=ly - meia_onda * 10.0,
            z=lz + pulso * 6.5,
        )
        rig.set_rotation("ant-arm", x=arx, y=ary, z=arz + pulso * 15.0)
        rig.set_rotation("ant-arm2", x=alx, y=aly, z=alz - (1.0 - pulso) * 15.0)
        rig.set_rotation("shoulder", x=pulso * 3.0, y=0.0, z=-pulso * 4.0)
        rig.set_rotation("shoulder2", x=pulso * 2.5, y=0.0, z=pulso * 3.0)
        cls._somar_punhos_dedos(
            rig, pose, onda * 9.0, meia_onda * 4.5, -pulso * 7.0,
            -onda * 10.0, meia_onda * 4.0, pulso * 7.0,
            onda * 4.0, -pulso * 5.0,
        )

    @classmethod
    def _groove_hip_hop(cls, rig, pose, pulso, onda, meia_onda):
        # 3. Groove adicional nos braços, cotovelos, ombros, punhos e dedos por estilo
        rx, ry, rz = pose.get("right-arm", (0.0, 0.0, 0.0))
        lx, ly, lz = pose.get("left-arm", (0.0, 0.0, 0.0))
        arx, ary, arz = pose.get("ant-arm", (0.0, 0.0, 0.0))
        alx, aly, alz = pose.get("ant-arm2", (0.0, 0.0, 0.0))

        rig.set_rotation(
            "right-arm",
            x=rx + onda * 4.0,
            y=ry + meia_onda * 13.0,
            z=rz - pulso * 5.0,
        )
        rig.set_rotation(
            "left-arm",
            x=lx - onda * 4.0,
            y=ly + meia_onda * 13.0,
            z=lz + pulso * 5.0,
        )
        rig.set_rotation("ant-arm", x=arx, y=ary, z=arz + pulso * 12.0)
        rig.set_rotation("ant-arm2", x=alx, y=aly, z=alz - (1 - pulso) * 12.0)
        rig.set_rotation(
            "shoulder",
            x=onda * 2.5,
            y=0.0,
            z=-pulso * 3.0 + meia_onda * 2.0,
        )
        rig.set_rotation(
            "shoulder2",
            x=-onda * 2.5,
            y=0.0,
            z=pulso * 3.0 + meia_onda * 2.0,
        )
        cls._somar_punhos_dedos(
            rig, pose, -onda * 10.0, meia_onda * 5.0, pulso * 7.0,
            onda * 10.0, meia_onda * 5.0, -pulso * 7.0,
            onda * 4.5, -onda * 4.5,
        )

    def _groove_breakdance(self, rig, pose, pulso, onda, meia_onda):
        # 3. Groove adicional nos braços, cotovelos, ombros, punhos e dedos por estilo
        rx, ry, rz = pose.get("right-arm", (0.0, 0.0, 0.0))
        lx, ly, lz = pose.get("left-arm", (0.0, 0.0, 0.0))
        arx, ary, arz = pose.get("ant-arm", (0.0, 0.0, 0.0))
        alx, aly, alz = pose.get("ant-arm2", (0.0, 0.0, 0.0))

        toprock = 1.0 - self.floor_amount
        rig.set_rotation(
            "right-arm",
            x=rx + onda * 4.0 * toprock,
            y=ry + meia_onda * 13.0 * toprock,
            z=rz - pulso * 7.0 * toprock,
        )
        rig.set_rotation(
            "left-arm",
            x=lx - onda * 4.0 * toprock,
            y=ly + meia_onda * 13.0 * toprock,
            z=lz + pulso * 7.0 * toprock,
        )
        rig.set_rotation("ant-arm", x=arx, y=ary, z=arz + pulso * 10.0 * toprock)
        rig.set_rotation("ant-arm2", x=alx, y=aly, z=alz - pulso * 10.0 * toprock)
        rig.set_rotation("shoulder", x=onda * 4.0, y=0.0, z=-pulso * 5.0)
        rig.set_rotation("shoulder2", x=-onda * 4.0, y=0.0, z=pulso * 5.0)
        self._somar_punhos_dedos(
            rig, pose, -onda * (6.0 + 6.0 * toprock), 0.0, meia_onda * 7.0,
            onda * (6.0 + 6.0 * toprock), 0.0, -meia_onda * 7.0,
            0.0, 0.0,
        )

    @classmethod
    def _groove_street_groove(cls, rig, pose, pulso, onda, meia_onda):
        # BRC Street groove: braços soltos com follow-through, ombros com sway,
        # punhos com micro-ruído orgânico. Estilo toprock fluido.
        rx, ry, rz = pose.get("right-arm", (0.0, 0.0, 0.0))
        lx, ly, lz = pose.get("left-arm", (0.0, 0.0, 0.0))
        arx, ary, arz = pose.get("ant-arm", (0.0, 0.0, 0.0))
        alx, aly, alz = pose.get("ant-arm2", (0.0, 0.0, 0.0))

        rig.set_rotation(
            "right-arm",
            x=rx + onda * 3.5,
            y=ry + meia_onda * 8.0,
            z=rz - pulso * 4.0,
        )
        rig.set_rotation(
            "left-arm",
            x=lx - onda * 3.5,
            y=ly + meia_onda * 8.0,
            z=lz + pulso * 4.0,
        )
        rig.set_rotation("ant-arm", x=arx, y=ary, z=arz + pulso * 8.0)
        rig.set_rotation("ant-arm2", x=alx, y=aly, z=alz - pulso * 8.0)
        rig.set_rotation(
            "shoulder",
            x=onda * 2.0,
            y=0.0,
            z=-pulso * 2.5 + meia_onda * 1.5,
        )
        rig.set_rotation(
            "shoulder2",
            x=-onda * 2.0,
            y=0.0,
            z=pulso * 2.5 + meia_onda * 1.5,
        )
        cls._somar_punhos_dedos(
            rig, pose, -onda * 8.0, meia_onda * 4.0, pulso * 5.0,
            onda * 8.0, meia_onda * 4.0, -pulso * 5.0,
            onda * 3.0, -onda * 3.0,
        )

    @classmethod
    def _groove_graffiti(cls, rig, pose, pulso, onda, meia_onda):
        # BRC Graffiti dance: braços descrevem arcos largos, punhos com torque
        # de spray, ombros com atitude. Porta vibra no ritmo.
        rx, ry, rz = pose.get("right-arm", (0.0, 0.0, 0.0))
        lx, ly, lz = pose.get("left-arm", (0.0, 0.0, 0.0))
        arx, ary, arz = pose.get("ant-arm", (0.0, 0.0, 0.0))
        alx, aly, alz = pose.get("ant-arm2", (0.0, 0.0, 0.0))

        rig.set_rotation(
            "right-arm",
            x=rx + onda * 5.0,
            y=ry + meia_onda * 10.0,
            z=rz - pulso * 6.0,
        )
        rig.set_rotation(
            "left-arm",
            x=lx - onda * 5.0,
            y=ly + meia_onda * 10.0,
            z=lz + pulso * 6.0,
        )
        rig.set_rotation("ant-arm", x=arx, y=ary, z=arz + pulso * 10.0)
        rig.set_rotation("ant-arm2", x=alx, y=aly, z=alz - pulso * 10.0)
        rig.set_rotation(
            "shoulder",
            x=onda * 3.0,
            y=0.0,
            z=-pulso * 3.5 + meia_onda * 2.0,
        )
        rig.set_rotation(
            "shoulder2",
            x=-onda * 3.0,
            y=0.0,
            z=pulso * 3.5 + meia_onda * 2.0,
        )
        cls._somar_punhos_dedos(
            rig, pose, -onda * 10.0, meia_onda * 5.0, pulso * 8.0,
            onda * 10.0, meia_onda * 5.0, -pulso * 8.0,
            pulso * 4.5, -pulso * 4.5,
        )

    @classmethod
    def _groove_cyber_bounce(cls, rig, pose, pulso, onda, meia_onda):
        # BRC Cyber bounce: braços angulares com squash & stretch,
        # antenas vibram com o bounce, ombros com impacto acentuado.
        rx, ry, rz = pose.get("right-arm", (0.0, 0.0, 0.0))
        lx, ly, lz = pose.get("left-arm", (0.0, 0.0, 0.0))
        arx, ary, arz = pose.get("ant-arm", (0.0, 0.0, 0.0))
        alx, aly, alz = pose.get("ant-arm2", (0.0, 0.0, 0.0))

        # Bounce: pulso vai de 0 a 1, criando squash/stretch rítmico
        bounce = pulso ** 2  # Acentua o impacto no fundo

        rig.set_rotation(
            "right-arm",
            x=rx + onda * 4.0,
            y=ry + meia_onda * 6.0,
            z=rz - bounce * 10.0,
        )
        rig.set_rotation(
            "left-arm",
            x=lx - onda * 4.0,
            y=ly + meia_onda * 6.0,
            z=lz + bounce * 10.0,
        )
        # Antenas vibram com o bounce — amplitude alta
        rig.set_rotation("ant-arm", x=arx, y=ary, z=arz + bounce * 20.0)
        rig.set_rotation("ant-arm2", x=alx, y=aly, z=alz - bounce * 20.0)
        rig.set_rotation(
            "shoulder",
            x=bounce * 5.0,
            y=0.0,
            z=-pulso * 4.0,
        )
        rig.set_rotation(
            "shoulder2",
            x=bounce * 5.0,
            y=0.0,
            z=pulso * 4.0,
        )
        cls._somar_punhos_dedos(
            rig, pose, -onda * 9.0, 0.0, bounce * 7.0,
            onda * 9.0, 0.0, -bounce * 7.0,
            bounce * 5.0, -bounce * 5.0,
        )

    def _groove_bracos(self, rig, pose, pulso, onda, meia_onda):
        if self.style == "head_bob":
            self._groove_head_bob(rig, pose, pulso, onda, meia_onda)
        elif self.style == "rock":
            self._groove_rock(rig, pose, pulso, onda, meia_onda)
        elif self.style == "hip_hop":
            self._groove_hip_hop(rig, pose, pulso, onda, meia_onda)
        elif self.style == "street_groove":
            self._groove_street_groove(rig, pose, pulso, onda, meia_onda)
        elif self.style == "graffiti_dance":
            self._groove_graffiti(rig, pose, pulso, onda, meia_onda)
        elif self.style == "cyber_bounce":
            self._groove_cyber_bounce(rig, pose, pulso, onda, meia_onda)
        else:
            self._groove_breakdance(rig, pose, pulso, onda, meia_onda)

    def _aplicar_acessorios_zzz_emote(self, rig) -> None:
        """Aplica sobreposição ZZZ só em fones e antenas preservando membros 1:1."""
        ganho = self._frase_ganho()
        p1 = self.phase - 0.55
        p2 = self.phase - 1.05
        pulso_f = 0.5 + 0.5 * cos(p1)
        onda_f = sin(p1)
        pulso_a = 0.5 + 0.5 * cos(p2)
        onda_a = sin(p2)
        rig.set_rotation("fones", x=onda_f * 2.8 * ganho, z=sin(p1 * 0.5) * 2.0 * ganho)
        rig.set_rotation("fone-direito", x=pulso_f * 5.2 * ganho, z=onda_f * 4.5 * ganho)
        rig.set_rotation("fone-esquerdo", x=pulso_f * 5.2 * ganho, z=-onda_f * 4.5 * ganho)
        rig.set_rotation("antena-direita", x=pulso_a * 13.0 * ganho, z=onda_a * 15.0 * ganho)
        rig.set_rotation("antena-esquerda", x=-pulso_a * 11.0 * ganho, z=-onda_a * 15.0 * ganho)

    def _ganho_passo(self) -> float:
        params = tune.parametros_danca()
        return params["ganho_passo_base"] + self.energy * params["ganho_passo_energia"]

    def _montar_alvo(self, rig):
        """Monta a pose do passo e o movimento secundário da batida."""
        clipe = carregar_clipe_emote(self.style) if self.style != "head_bob" else None
        if clipe is not None:
            pose_clipe = amostrar_clipe_emote(clipe, self.tempo_clipe)
            self.dz_pelvis_emote, self.giro_corpo_emote = amostrar_raiz_emote(
                clipe, self.tempo_clipe
            )
            self.raiz_quat_emote = amostrar_orientacao_raiz_emote(
                clipe, self.tempo_clipe
            )
            self.deslocamento_emote = amostrar_deslocamento_emote(clipe, self.tempo_clipe)
            self.dedos_clipe = amostrar_dedos_emote(clipe, self.tempo_clipe)
            for grupo, rot in pose_clipe.items():
                if grupo in rig.rest and grupo != "door":
                    rig.current[grupo] = rot
            self._aplicar_acessorios_zzz_emote(rig)
            rig.set_rotation("door", y=0)
            return rig.pose()
        self.dz_pelvis_emote = 0.0
        self.giro_corpo_emote = 0.0
        self.raiz_quat_emote = None
        self.deslocamento_emote = (0.0, 0.0)
        self.dedos_clipe = None
        passos = frase_do_estilo(self.style)
        indice, u = self._posicao_na_frase(passos)
        pose = amostrar_passo(
            passos[indice],
            u,
            passos[(indice + 1) % len(passos)],
            self._ganho_passo(),
        )
        for grupo, (x, y, z) in pose.items():
            rig.set_rotation(grupo, x=x, y=y, z=z)

        pulso = 0.5 + 0.5 * cos(self.phase)
        onda = sin(self.phase)
        meia_onda = sin(self.phase * 0.5)
        self._groove_tronco(rig, pose, pulso, onda, meia_onda)
        self._groove_bracos(rig, pose, pulso, onda, meia_onda)
        self._aplicar_ombros_zzz(rig, (0.55 + 0.45 * self.energy) * self._frase_ganho())
        rig.set_rotation("door", y=0)
        return rig.pose()

    def apply(self, rig):
        """Aplica a pose de dança atual no rig."""
        rig.current = self.contribuicao(rig)

    def contribuicao(self, rig):
        """Amostra a coreografia e interpola a entrada de um novo estilo."""
        alvo = self._montar_alvo(rig)
        if self._pose_anterior and self.style_beats < 1.0:
            peso = suavizar_quintico(self.style_beats)
            for grupo, rotacao in alvo.items():
                origem = self._pose_anterior.get(grupo, rotacao)
                alvo[grupo] = Rotation3(
                    origem.x + (rotacao.x - origem.x) * peso,
                    origem.y + (rotacao.y - origem.y) * peso,
                    origem.z + (rotacao.z - origem.z) * peso,
                )
        mistura = max(0.0, min(1.0, float(tune.parametros_danca().get("mistura_base", 1.0))))
        if mistura < 1.0 - 1e-6:
            for grupo, rotacao in alvo.items():
                base = rig.rest.get(grupo, Rotation3())
                alvo[grupo] = Rotation3(
                    base.x + (rotacao.x - base.x) * mistura,
                    base.y + (rotacao.y - base.y) * mistura,
                    base.z + (rotacao.z - base.z) * mistura,
                )
        clipe_ativo = carregar_clipe_emote(self.style) if self.style != "head_bob" else None
        if clipe_ativo is None and self._dt_passo > 0.0 and self._pose_suavizada:
            teto = radians(460.0) * self._dt_passo
            for grupo in (
                "body",
                "head",
                "right-arm",
                "left-arm",
                "ant-arm",
                "ant-arm2",
                "hand",
                "hand2",
            ):
                if grupo in alvo and grupo in self._pose_suavizada:
                    ant = self._pose_suavizada[grupo]
                    nov = alvo[grupo]
                    alvo[grupo] = Rotation3(
                        ant.x + max(-teto, min(teto, nov.x - ant.x)),
                        ant.y + max(-teto, min(teto, nov.y - ant.y)),
                        ant.z + max(-teto, min(teto, nov.z - ant.z)),
                    )
        self._pose_suavizada = dict(alvo)
        self.pose = alvo
        return dict(alvo)

    @property
    def lean_amount(self):
        """Devolve a inclinação do corpo pedida pelo passo atual."""
        if self.style == "head_bob":
            value = max(0, min(1, self.style_beats / tune.LEAN_HEADBOB_BATIDAS))
            return value * value * (3 - 2 * value)
        beat = self.style_beats % tune.FRASE_BATIDAS
        value = max(
            0, min(1, beat - tune.LEAN_JANELA_INICIO, tune.LEAN_JANELA_FIM - beat)
        )
        return value * value * (3 - 2 * value)

    @property
    def floor_amount(self):
        """Devolve o quanto o passo atual leva o corpo ao chão."""
        beat = self.style_beats % tune.FRASE_BATIDAS
        value = max(
            0,
            min(
                1,
                (beat - tune.FLOOR_INICIO) / tune.FLOOR_SUBIDA,
                (tune.FLOOR_FIM - beat) / tune.FLOOR_DESCIDA,
            ),
        )
        return value * value * (3 - 2 * value)

    @property
    def floor_spin(self):
        """Devolve o giro no chão do passo atual."""
        beat = self.style_beats % tune.FRASE_BATIDAS
        return (
            max(0, min(1, (beat - tune.SPIN_INICIO) / tune.SPIN_SUBIDA))
            * tune.SPIN_GRAUS
        )

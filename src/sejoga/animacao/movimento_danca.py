"""Dança guiada por áudio: passos de quatro poses por batida e molas por junta.

O estilo escolhido pelo áudio toca uma frase de passos (``danca_frases_tuning``)
amostrada por ``poses_danca``: o acento cai no onset da batida (u = 0). O
resultado por junta é suavizado por molas amortecidas, dando peso e recuperação
naturais.
"""

from math import cos, exp, floor, sin, tau

from sejoga.animacao import danca_tuning as tune
from sejoga.animacao.danca_frases_tuning import frase_do_estilo
from sejoga.animacao.mola_tuning import DANCA_AMORTECIMENTO, DANCA_FREQUENCIA
from sejoga.animacao.molas_juntas import SpringPose
from sejoga.animacao.poses_danca import amostrar_passo


class DanceMotion:
    """Coreografia da dança sincronizada com a música."""

    def __init__(self):
        """Inicia a dança parada no estilo padrão."""
        self.phase = 0.0
        self.energy = self.bass = 0.0
        self.style = "head_bob"
        self.dwell = 0.0
        self.pose = {}
        self.dt = 0.0
        self.tempo = 90.0
        self.strength = 0.0
        self.override = "auto"
        self.style_beats = 0.0
        # Acento do downbeat (0..1) e molas por junta para a saída.
        self.acento = 0.0
        self._molas = SpringPose(
            frequencia=DANCA_FREQUENCIA, amortecimento=DANCA_AMORTECIMENTO
        )

    def update(self, dt, level, bass, bpm=None, beat=False):
        """Avança a coreografia com o nível, o grave e o BPM da música."""
        self.dt = dt
        blend = 1 - exp(-max(0, dt) * tune.SUAVIZACAO_AUDIO)
        self.energy += (max(0, min(1, level)) - self.energy) * blend
        self.bass += (max(0, min(1, bass)) - self.bass) * blend
        tempo = max(tune.TEMPO_MIN, min(tune.TEMPO_MAX, bpm or tune.TEMPO_PADRAO))
        self.tempo += (tempo - self.tempo) * (1 - exp(-dt * tune.SUAVIZACAO_TEMPO))
        previous_bar = int(self.phase / tune.COMPASSO_FASE)
        self.phase += dt * self.tempo / 60 * tau
        self.style_beats += dt * self.tempo / 60
        bar_boundary = int(self.phase / tune.COMPASSO_FASE) != previous_bar
        if beat:
            # Soft phase correction avoids a discontinuity in the joints.
            error = (self.phase + tau / 2) % tau - tau / 2
            self.phase -= error * tune.CORRECAO_FASE
        self.dwell += dt
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
        if self.override != "auto":
            desired = self.override
        if desired != self.style and self.dwell > tune.DWELL_MINIMO and bar_boundary:
            self.style, self.dwell = desired, 0.0
            self.style_beats = 0.0
        target_strength = (
            tune.FORCA_HEAD_BOB
            if self.style == "head_bob"
            else tune.FORCA_HIP_HOP
            if self.style == "hip_hop"
            else tune.FORCA_PADRAO
        )
        self.strength += (target_strength - self.strength) * (
            1 - exp(-dt * tune.SUAVIZACAO_FORCA)
        )
        # Envelope por batida: acento forte no downbeat (início do compasso),
        # decaindo ao longo da batida. A energia do áudio escala o acento.
        batida = (self.phase / tau) % 1
        downbeat = (self.phase / tune.COMPASSO_FASE) % 1
        acento = (1 - batida) ** 2 * (1 + (1 - downbeat) * tune.ACENTO_DOWNBEAT)
        self.acento += (
            acento * (tune.ACENTO_BASE + self.energy * tune.ACENTO_GANHO_ENERGIA)
            - self.acento
        ) * (1 - exp(-dt * tune.SUAVIZACAO_ACENTO))

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

    def _montar_alvo(self, rig):
        """Autora a pose crua da dança no rig e devolve o snapshot alvo.

        Compartilhado por apply (que grava no rig) e contribuicao (que apenas
        lê o resultado suavizado por molas), garantindo o mesmo resultado.
        Cabeça e tronco escalam com a energia; os braços vão aos alvos de mão.
        """
        passos = frase_do_estilo(self.style)
        indice, u = self._posicao_na_frase(passos)
        ganho = tune.GANHO_PASSO_BASE + self.energy * tune.GANHO_PASSO_ENERGIA
        pose = amostrar_passo(
            passos[indice], u, passos[(indice + 1) % len(passos)], ganho
        )
        for grupo, (x, y, z) in pose.items():
            rig.set_rotation(grupo, x=x, y=y, z=z)

        # Groove contínuo de coluna, ombros, braços, punhos, dedos e fones
        # sincronizado à fase da batida, dando articulação viva a cada estilo.
        pulso = 0.5 + 0.5 * cos(self.phase)
        onda = sin(self.phase)
        meia_onda = sin(self.phase * 0.5)
        energia_ef = 0.55 + 0.45 * self.energy

        bx, by, bz = pose.get("body", (0.0, 0.0, 0.0))
        hx, hy, hz = pose.get("head", (0.0, 0.0, 0.0))

        # 1. Cadeia da coluna (cintura -> abdomen -> peitoral)
        rig.set_rotation(
            "cintura",
            x=bx * 0.25 + pulso * 2.2 * energia_ef,
            y=by * 0.25 + meia_onda * 4.5 * energia_ef,
            z=bz * 0.30 + meia_onda * 3.8 * energia_ef,
        )
        rig.set_rotation(
            "abdomen",
            x=bx * 0.35 + onda * 2.5 * energia_ef,
            y=by * 0.35 - meia_onda * 3.5 * energia_ef,
            z=bz * 0.35 + sin(self.phase * 0.5 - 0.4) * 3.2 * energia_ef,
        )
        rig.set_rotation(
            "peitoral",
            x=bx * 0.45 - pulso * 3.2 * energia_ef,
            y=by * 0.45 + meia_onda * 5.0 * energia_ef,
            z=bz * 0.40 - meia_onda * 2.8 * energia_ef,
        )

        # 2. Fones e antenas reagindo ao headbang/nod com chicote secundário
        atraso = sin(self.phase - 0.65)
        rig.set_rotation(
            "fones",
            x=-hx * 0.22 + atraso * 3.5 * energia_ef,
            y=-hy * 0.16,
            z=-hz * 0.25 + meia_onda * 2.8 * energia_ef,
        )
        rig.set_rotation(
            "fone-direito",
            x=-hx * 0.14,
            y=-hy * 0.10,
            z=-hz * 0.22 + onda * 2.5 * energia_ef,
        )
        rig.set_rotation(
            "fone-esquerdo",
            x=-hx * 0.14,
            y=-hy * 0.10,
            z=-hz * 0.22 - onda * 2.5 * energia_ef,
        )
        rig.set_rotation(
            "antena-direita",
            x=-hx * 0.42 + atraso * 7.5 * energia_ef,
            y=-hy * 0.30 + meia_onda * 4.0 * energia_ef,
            z=-hz * 0.48 + onda * 6.5 * energia_ef,
        )
        rig.set_rotation(
            "antena-esquerda",
            x=-hx * 0.42 + atraso * 7.5 * energia_ef,
            y=-hy * 0.30 - meia_onda * 4.0 * energia_ef,
            z=-hz * 0.48 - onda * 6.5 * energia_ef,
        )

        # 3. Groove adicional nos braços, cotovelos, ombros, punhos e dedos por estilo
        rx, ry, rz = pose.get("right-arm", (0.0, 0.0, 0.0))
        lx, ly, lz = pose.get("left-arm", (0.0, 0.0, 0.0))
        arx, ary, arz = pose.get("ant-arm", (0.0, 0.0, 0.0))
        alx, aly, alz = pose.get("ant-arm2", (0.0, 0.0, 0.0))

        if self.style == "head_bob":
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
            rig.set_rotation("hand", x=-onda * 3.5, y=meia_onda * 3.0, z=onda * 4.0)
            rig.set_rotation("hand2", x=onda * 3.5, y=meia_onda * 3.0, z=-onda * 4.0)
            rig.set_rotation("fingers", z=4.0 + pulso * 4.0)
            rig.set_rotation("fingers2", z=-4.0)
        elif self.style == "rock":
            rig.set_rotation(
                "right-arm",
                x=rx + onda * 4.0,
                y=ry + meia_onda * 4.5,
                z=rz - pulso * 7.5,
            )
            rig.set_rotation(
                "left-arm",
                x=lx - onda * 4.5,
                y=ly - meia_onda * 5.0,
                z=lz + pulso * 6.5,
            )
            rig.set_rotation("ant-arm", x=arx, y=ary, z=arz + pulso * 7.0)
            rig.set_rotation("ant-arm2", x=alx, y=aly, z=alz - (1.0 - pulso) * 8.0)
            rig.set_rotation("shoulder", x=pulso * 3.0, y=0.0, z=-pulso * 4.0)
            rig.set_rotation("shoulder2", x=pulso * 2.5, y=0.0, z=pulso * 3.0)
            hx_m, hy_m, hz_m = pose.get("hand", (180.0, 0.0, 0.0))
            rig.set_rotation(
                "hand",
                x=hx_m + onda * 6.0,
                y=hy_m + meia_onda * 4.5,
                z=hz_m - pulso * 7.0,
            )
            rig.set_rotation("hand2", x=-onda * 5.0, y=0.0, z=pulso * 6.0)
            rig.set_rotation("fingers", z=-4.0 + onda * 4.0)
            rig.set_rotation("fingers2", z=-12.0 - pulso * 6.0)
        elif self.style == "hip_hop":
            rig.set_rotation(
                "right-arm",
                x=rx + onda * 4.0,
                y=ry + meia_onda * 5.0,
                z=rz - pulso * 5.0,
            )
            rig.set_rotation(
                "left-arm",
                x=lx - onda * 4.0,
                y=ly + meia_onda * 5.0,
                z=lz + pulso * 5.0,
            )
            rig.set_rotation("ant-arm", x=arx, y=ary, z=arz + pulso * 2.5)
            rig.set_rotation("ant-arm2", x=alx, y=aly, z=alz - pulso * 2.5)
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
            rig.set_rotation(
                "hand", x=-onda * 5.0, y=meia_onda * 4.0, z=pulso * 6.0
            )
            rig.set_rotation(
                "hand2", x=onda * 5.0, y=meia_onda * 4.0, z=-pulso * 6.0
            )
            rig.set_rotation("fingers", z=6.0 + onda * 5.0)
            rig.set_rotation("fingers2", z=-6.0 - onda * 5.0)
        else:  # breakdance
            toprock = 1.0 - self.floor_amount
            rig.set_rotation(
                "right-arm",
                x=rx + onda * 4.0 * toprock,
                y=ry + meia_onda * 8.0 * toprock,
                z=rz - pulso * 7.0 * toprock,
            )
            rig.set_rotation(
                "left-arm",
                x=lx - onda * 4.0 * toprock,
                y=ly + meia_onda * 8.0 * toprock,
                z=lz + pulso * 7.0 * toprock,
            )
            rig.set_rotation("ant-arm", x=arx, y=ary, z=arz + pulso * 2.0)
            rig.set_rotation("ant-arm2", x=alx, y=aly, z=alz - pulso * 2.0)
            rig.set_rotation("shoulder", x=onda * 4.0, y=0.0, z=-pulso * 5.0)
            rig.set_rotation("shoulder2", x=-onda * 4.0, y=0.0, z=pulso * 5.0)
            rig.set_rotation("hand", x=-onda * 9.0, y=0.0, z=meia_onda * 10.0)
            rig.set_rotation("hand2", x=onda * 9.0, y=0.0, z=-meia_onda * 10.0)

        rig.set_rotation("door", y=0)
        return rig.pose()

    def _suavizar(self, rig):
        """Avança as molas por junta sobre o alvo cru e grava em self.pose."""
        target = self._montar_alvo(rig)
        # Molas por junta: o corpo "pesa" no acento e recupera suavemente,
        # em vez de um blend exponencial uniforme para todas as juntas.
        if not self.pose:
            self._molas.definir(target)
        self.pose = self._molas.atualizar(max(0.0, self.dt), target)
        return self.pose

    def apply(self, rig):
        """Aplica a pose de dança atual no rig."""
        rig.current = dict(self._suavizar(rig))

    def contribuicao(self, rig):
        """Pose de dança suavizada por molas, sem mutar o rig do controlador.

        Usa o rig recebido apenas como scratch para montar o alvo (o chamador
        deve passar um rig em reset); devolve o mesmo dict que apply gravaria.
        """
        return dict(self._suavizar(rig))

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

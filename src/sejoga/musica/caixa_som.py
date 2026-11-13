"""Palco musical montado a partir do GLTF exportado pelo Blockbench."""

from math import cos, exp, pi, sin

import gltf
from panda3d.core import NodePath, Point3, TransparencyAttrib, Vec3

from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.musica.efeitos_caixa_som import SpeakerEffects
from sejoga.nucleo.recursos import model_dir

PRIMEIRO_ARREMESSO_S = 1.65
INTERVALO_ARREMESSOS_S = 0.95
VOO_CAIXA_S = 0.8
BATIDAS_ARREMESSO_S = tuple(
    PRIMEIRO_ARREMESSO_S + index * INTERVALO_ARREMESSOS_S for index in range(3)
)
FIM_ARREMESSOS_S = BATIDAS_ARREMESSO_S[-1] + VOO_CAIXA_S
INICIO_SALTO_S = FIM_ARREMESSOS_S + 0.65
DURACAO_SALTO_S = 1.05


class MusicSpeaker:
    """Três caixas com base no chão e arremessos escalonados."""

    def __init__(self, renderer):  # noqa: PLR0915
        """Carrega e calibra as caixas pela altura do mascote em repouso."""
        self.renderer = renderer
        self._measure_character()
        self.root = renderer.model_anchor.attachNewNode("music-speaker")
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.root.setCollideMask(0)
        asset = NodePath(gltf.load_model(str(model_dir() / "Boomboxes.gltf")))
        self.boxes = []
        self.destinations = []
        self.bounds = []
        limites_x = []
        self.scales = []
        self.effects = []
        self.launch_origin = Point3(0.23, -0.12, 0.94)
        height = self.character_size.z
        for name, ratio in (("meio", 2.0), ("esquerda", 1.0), ("direita", 1.0)):
            box = asset.find("Caixa de som " + name)
            offset = box.getPos()
            box.reparentTo(self.root)
            box.setPos(0, 0, 0)
            box.setH(box.getH() + 180)
            low, high = box.getTightBounds()
            box.setScale(height * ratio / (high.z - low.z))
            low, high = box.getTightBounds(self.root)
            self.boxes.append(box)
            self.scales.append(box.getSx())
            box_low, box_high = box.getTightBounds(box)
            self.bounds.append((box_low, box_high))
            effects_anchor = box.attachNewNode("speaker-effects")
            effects_anchor.setPos(0, box_high.y, box_low.z)
            effects_anchor.setScale((box_high.z - box_low.z) / 1.75)
            self.effects.append(SpeakerEffects(effects_anchor))
            self.destinations.append(
                Point3(
                    height * 0.48 + offset.x * height * 1.10,
                    max(0.24 - low.y, 1.15 * height + offset.y * height),
                    self.floor_z - low.z,
                )
            )
            limites_x.append((self.destinations[-1].x + low.x, self.destinations[-1].x + high.x))
            if name == "meio":
                self.seat = Point3(
                    self.destinations[0].x,
                    self.destinations[0].y + low.y - 0.12,
                    self.floor_z + high.z - low.z,
                )
        self.limites_x = (min(lo for lo, _ in limites_x), max(hi for _, hi in limites_x))
        self.age = 0.0
        self.visibility = 0.0
        self.was_dancing = False
        self.ejecting = False
        self.throw_index = -1
        self._landing_sound_played = False
        self.root.hide()

    def _measure_character(self):
        from sejoga.animacao.poses_base import pose_idle
        from sejoga.nucleo.esqueleto import IdlePersonality

        rig = self.renderer.rig
        previous = rig.pose()
        rig.reset()
        pose_idle(rig, 0, IdlePersonality.CALM)
        self.renderer.apply_rig_pose(rig.pose())
        bounds = [
            self.renderer._rig_nodes[name].getTightBounds(self.renderer.model_np)
            for name in (
                "head",
                "body",
                "right-arm",
                "left-arm",
                "legs",
                "left-feet",
                "right-feet",
            )
        ]
        low = Vec3(*(min(b[0][i] for b in bounds) for i in range(3)))
        high = Vec3(*(max(b[1][i] for b in bounds) for i in range(3)))
        self.character_size = high - low
        self.floor_z = low.z
        self.renderer.apply_rig_pose(previous)
        rig.current = previous

    def update(self, dt, dancing, phase, energy, bass=0):  # noqa: PLR0915
        """Atualiza os arremessos, os efeitos e o retorno do palco."""
        if dancing and not self.was_dancing:
            self.age = 0.0
            self._landing_sound_played = False
        self.was_dancing = dancing
        if dancing:
            self.age += dt
        self.visibility += ((1 if dancing else 0) - self.visibility) * (
            1 - exp(-dt * 5)
        )
        self.ejecting = dancing and 0.65 <= self.age < FIM_ARREMESSOS_S
        self.throw_index = -1
        if self.visibility < 0.005 or self.age < PRIMEIRO_ARREMESSO_S - 0.27:
            self.root.hide()
            return
        self.root.show()
        model = self.renderer.model_np
        self.root.setPos(model.getPos())
        self.root.setScale(model.getScale())
        strength = max(0, min(1, energy * 0.7 + bass * 0.9))
        ajuste_x = self._ajustar_palco_na_tela()
        for index, (box, destination) in enumerate(
            zip(self.boxes, self.destinations, strict=True)
        ):
            elapsed = self.age - BATIDAS_ARREMESSO_S[index]
            (box.show if elapsed >= 0 else box.hide)()
            u = max(0, min(1, elapsed / VOO_CAIXA_S))
            if dancing and -0.27 <= elapsed < VOO_CAIXA_S - 0.04:
                self.throw_index = index
            pos = self.launch_origin + (destination - self.launch_origin) * u
            pos.x += ajuste_x * u
            arc = sin(pi * u)
            pos.z += arc * 0.55
            grow = 0.07 + 0.93 * suavizar_quintico(u / 0.86)
            # A face da caixa passa atrás da silhueta durante o voo.
            low, high = self.bounds[index]
            box.setR(-75 * (1 - u))
            box.setScale(self.scales[index] * grow)
            if u >= 1:
                self._pulso_no_chao(index, box, pos, phase, strength, elapsed - VOO_CAIXA_S)
            else:
                vertical = box.getQuat().conjugate().xform(Vec3(0, 0, 1))
                base_rotacionada = sum(
                    min(a * v, b * v) * scale
                    for a, b, v, scale in zip(low, high, vertical, box.getScale(), strict=True)
                )
                pos.z = max(pos.z, self.floor_z - base_rotacionada)
            axis = box.getQuat().conjugate().xform(Vec3(0, 1, 0))
            front = sum(
                min(a * v, b * v) * scale
                for a, b, v, scale in zip(low, high, axis, box.getScale(), strict=True)
            )
            pos.y = max(pos.y + arc * 0.36, 0.24 - front)
            box.setPos(pos)
            if u >= 1 and index == 0:
                borda = box.getQuat().xform(Vec3(0, high.y * box.getSy() + 0.12, 0))
                self.seat.set(pos.x + borda.x, pos.y + borda.y, pos.z + high.z * box.getSz())
            box.setColorScale(1, 1, 1, self.visibility)
            self.effects[index].update(elapsed - VOO_CAIXA_S)
        if (
            self.age >= PRIMEIRO_ARREMESSO_S + VOO_CAIXA_S
            and not self._landing_sound_played
        ):
            self._landing_sound_played = True
            app = self.renderer.showbase
            if (
                app.settings.audio.enabled
                and app.animation_controller._dance_preview_remaining <= 0
            ):
                from sejoga.musica.efeitos_sonoros import play_speaker_landing

                play_speaker_landing(app.settings.audio.master_volume)

    def _ajustar_palco_na_tela(self):
        r = self.renderer
        x = getattr(r, "_scene_x_px", None)
        if x is None:
            return 0.0
        pixels = r.width * r.model_np.getSx() / r._view_width
        low, high = self.limites_x
        esquerda = (18 - x) / pixels - low
        direita = (r.width - 18 - x) / pixels - high
        return max(esquerda, min(direita, 0.0))

    def _pulso_no_chao(self, index, box, pos, phase, strength, idade_pouso):
        low, _ = self.bounds[index]
        escala = self.scales[index]
        acento = (0.5 + 0.5 * cos(phase - index * 0.22)) ** 6 * strength
        impacto = sin(idade_pouso * 21) * exp(-idade_pouso * 11)
        compressao = 1 - 0.045 * acento - 0.085 * impacto
        altura = escala * compressao
        lateral = escala / compressao**0.5
        box.setScale(lateral, lateral, altura)
        pos.x += 0.036 * sin(phase * 9 + index) * acento
        pos.z = self.floor_z - low.z * altura

    @property
    def jump_progress(self):
        """Fração percorrida do salto."""
        return max(0, min(1, (self.age - INICIO_SALTO_S) / DURACAO_SALTO_S))

    @property
    def turn(self):
        """Ângulo lateral durante a saída das caixas."""
        turn_out = suavizar_quintico(self.age / 1.35)
        turn_back = suavizar_quintico((self.age - INICIO_SALTO_S) / 0.65)
        return 76 * turn_out * (1 - turn_back)

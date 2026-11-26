"""Palco musical montado a partir do GLTF exportado pelo Blockbench."""

from math import cos, exp, pi, sin

import gltf
from panda3d.core import NodePath, PNMImage, Point3, Texture, TransparencyAttrib, Vec3

from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.nucleo.recursos import model_dir
from sejoga.render.sprites_efeitos import atlas_gosma, cartao_pixel, quadro_gosma

PRIMEIRO_ARREMESSO_S = 1.65
INTERVALO_ARREMESSOS_S = 0.95
VOO_CAIXA_S = 0.8
BATIDAS_ARREMESSO_S = tuple(
    PRIMEIRO_ARREMESSO_S + index * INTERVALO_ARREMESSOS_S for index in range(3)
)
DURACAO_SALTO_S = 1.05


class SpeakerEffects:
    """Espalha a gosma pelas duas quinas inferiores e seca no chão."""

    def __init__(self, geometry):
        """Cria um respingo para cada quina voltada à câmera."""
        self.slime = []
        for _ in range(2):
            node = cartao_pixel(geometry, "speaker-splash", atlas_gosma())
            node.setColorScale(1.22, 0.64, 0.91, 1)
            node.hide()
            self.slime.append(node)

    def update(self, age):
        """Expande os respingos no impacto e troca pelos quadros de secagem."""
        for lado, node in zip((-1, 1), self.slime, strict=True):
            if not 0 <= age < 1.4:
                node.hide()
                continue
            node.show()
            espalha = min(1.0, age / 0.28)
            node.setPos(lado * (0.72 + 0.13 * espalha), 0.015, 0.12 - 0.05 * espalha)
            node.setScale(0.26 + 0.25 * espalha, 1, 0.28 - 0.10 * espalha)
            if age < 0.28:
                quadro_gosma(node, 0, min(3, int(age / 0.07)))
            else:
                quadro_gosma(node, 3, min(3, int((age - 0.28) / 0.28)))


class MusicSpeaker:
    """Três caixas com base no chão e arremessos escalonados."""

    def __init__(self, renderer, style: str = "palco"):  # noqa: PLR0915
        """Carrega e calibra as caixas pela altura do mascote em repouso."""
        self.renderer = renderer
        self.compact = style == "radio"
        self.throw_beats = BATIDAS_ARREMESSO_S[:1] if self.compact else BATIDAS_ARREMESSO_S
        self.end_throws = self.throw_beats[-1] + VOO_CAIXA_S
        self.start_jump = self.end_throws + 0.65
        self._measure_character()
        render_root = getattr(renderer.showbase, "render", None)
        self.root = (render_root or renderer.model_anchor).attachNewNode("music-speaker")
        self.root.setTransparency(TransparencyAttrib.MNone)
        self.root.setCollideMask(0)
        arquivo = "radio-compacto.glb" if self.compact else "Boomboxes.gltf"
        asset = NodePath(gltf.load_model(str(model_dir() / arquivo)))
        self.boxes = []
        self.destinations = []
        self.bounds = []
        self.emissores_graves = []
        limites_x = []
        self.scales = []
        self.effects = []
        self._cones_por_caixa: list[list[tuple[NodePath, Point3, Vec3]]] = []
        self.launch_origin = Point3(0.23, -0.12, 0.94)
        self._stage_world_anchor: Point3 | None = None
        self._stage_screen_anchor: tuple[float, float] | None = None
        self._stage_scale = None
        height = self.character_size.z
        for tex in asset.findAllTextures():
            self._realcar_textura_caixa(tex)
        caixas = (("radio", 0.38),) if self.compact else (
            ("meio", 2), ("esquerda", 1), ("direita", 1)
        )
        for name, ratio in caixas:
            if self.compact:
                box = NodePath("radio-compacto")
                asset.setName("mesh-radio")
                asset.reparentTo(box)
            else:
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
            cones: list[tuple[NodePath, Point3, Vec3]] = []
            vistos_cones: set[int] = set()
            for padrao in ("**/Cone*", "**/Calota*"):
                for no_cone in box.findAllMatches(padrao):
                    if no_cone.getKey() in vistos_cones:
                        continue
                    vistos_cones.add(no_cone.getKey())
                    cones.append((no_cone, Point3(no_cone.getPos()), Vec3(no_cone.getScale())))
            self._cones_por_caixa.append(cones)
            box_low, box_high = box.getTightBounds(box)
            self.bounds.append((box_low, box_high))
            calota = box.find("**/Calota_" + name + "_0")
            if calota.isEmpty():
                # O rádio compacto tem a frente integrada em uma malha única.
                calota = box.attachNewNode("centro-alto-falante")
                calota.setPos((box_low.x + box_high.x) * 0.5, box_high.y,
                              box_low.z + (box_high.z - box_low.z) * 0.52)
            self.emissores_graves.append(calota)
            effects_anchor = box.attachNewNode("speaker-effects")
            effects_anchor.setPos(0, box_high.y, box_low.z)
            effects_anchor.setScale((box_high.z - box_low.z) / 1.75)
            self.effects.append(SpeakerEffects(effects_anchor))
            self.destinations.append(
                Point3(
                    height * (0.80 if self.compact else 0.48 + offset.x * 1.10),
                    max(0.24 - low.y, 1.15 * height + offset.y * height),
                    self.floor_z - low.z,
                )
            )
            limites_x.append((self.destinations[-1].x + low.x, self.destinations[-1].x + high.x))
            if not self.compact and name == "meio":
                self.seat = Point3(
                    self.destinations[0].x,
                    self.destinations[0].y + low.y - 0.12,
                    self.floor_z + high.z - low.z,
                )
        if not hasattr(self, "seat"):
            low0, high0 = self.boxes[0].getTightBounds(self.root)
            self.seat = Point3(
                self.destinations[0].x,
                self.destinations[0].y + low0.y - 0.12,
                self.floor_z + high0.z - low0.z,
            )
        self.limites_x = (min(lo for lo, _ in limites_x), max(hi for _, hi in limites_x))
        self.age = 0.0
        self.visibility = 0.0
        self.was_dancing = False
        self.ejecting = False
        self.throw_index = -1
        self._landing_sound_played = False
        self._album_colors: tuple[tuple[float, float, float], ...] = ()
        self.root.hide()

    def set_album_colors(
        self, colors: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]] | None
    ) -> None:
        """Atualiza o sotaque cromático vindo da capa do álbum em reprodução."""
        self._album_colors = tuple(colors or ())

    @staticmethod
    def _normalizar_imagem_caixa(img: PNMImage) -> None:
        """Remapeia luminância da jukebox para curva escura arcade com contraste legível."""
        w, h = img.getXSize(), img.getYSize()
        lums = [
            (img.getRed(x, y) + img.getGreen(x, y) + img.getBlue(x, y)) / 3.0
            for y in range(h)
            for x in range(w)
            if img.getAlpha(x, y) >= 0.1
        ]
        lo_lum = min(lums) if lums else 0.01
        hi_lum = max(lums) if lums else 0.05
        span = max(0.012, hi_lum - lo_lum)
        for y in range(h):
            for x in range(w):
                if img.getAlpha(x, y) < 0.1:
                    continue
                r, g, b = img.getXel(x, y)
                lum = (r + g + b) / 3.0
                t = max(0.0, min(1.0, (lum - lo_lum) / span))
                alvo_lum = 0.0045 + (t**1.65) * 0.082
                escala = alvo_lum / max(lum, 1e-4)
                img.setXel(
                    x,
                    y,
                    max(0.0, min(0.18, r * escala * 0.94)),
                    max(0.0, min(0.18, g * escala * 0.92)),
                    max(0.0, min(0.24, b * escala * 1.16)),
                )

    @staticmethod
    def _realcar_textura_caixa(tex) -> None:
        """Restaura leitura e contraste cromático da jukebox evitando bloco escuro ou lavado."""
        img = PNMImage()
        if not tex.getName().startswith("pixel-") and tex.store(img):
            MusicSpeaker._normalizar_imagem_caixa(img)
            tex.load(img)
        tex.setMinfilter(Texture.FTNearest)
        tex.setMagfilter(Texture.FTNearest)

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

    def _atualizar_ancora_palco(self) -> None:
        """Fixa a origem no desktop e a reprojeta quando a janela se move."""
        model = self.renderer.model_np
        app = self.renderer.showbase
        render_root = getattr(app, "render", None)
        anchor_world = self.renderer.model_anchor.getPos(
            render_root or self.renderer.model_anchor
        )
        if self._stage_world_anchor is None:
            self._stage_model_offset = Point3(model.getX(), model.getY(), model.getZ())
            self._stage_world_anchor = Point3(
                anchor_world.x + self._stage_model_offset.x,
                anchor_world.y + self._stage_model_offset.y,
                anchor_world.z + self._stage_model_offset.z,
            )
            self._stage_scale = model.getScale()
            if hasattr(app, "_mascot_screen"):
                self._stage_screen_anchor = tuple(app._mascot_screen)
        stage_pos = self._stage_world_anchor
        canvas_origin = getattr(app, "_canvas_origin", None)
        if (
            self._stage_screen_anchor is not None
            and canvas_origin is not None
            and self.renderer.width > 0
            and self.renderer.height > 0
        ):
            lx = self._stage_screen_anchor[0] - canvas_origin[0]
            ly = self._stage_screen_anchor[1] - canvas_origin[1]
            wx = (lx - self.renderer.width / 2.0) * self.renderer._view_width / self.renderer.width
            wz = (
                self.renderer._view_target_z
                + (self.renderer.height / 2.0 - ly)
                * self.renderer._view_height
                / self.renderer.height
            )
            off = getattr(self, "_stage_model_offset", Point3(0, 0, 0))
            stage_pos = Point3(wx + off.x, self._stage_world_anchor.y, wz + off.z)
        self.root.setPos(stage_pos)
        self.root.setScale(
            self._stage_scale if self._stage_scale is not None else model.getScale()
        )

    @property
    def ancora_na_tela(self) -> tuple[float, float] | None:
        """Origem absoluta do palco enquanto ele está visível."""
        return self._stage_screen_anchor if self.visibility > 0.005 else None

    @staticmethod
    def _extensao_eixo(box, low, high, eixo_mundo: Vec3) -> float:
        eixo_local = box.getQuat().conjugate().xform(eixo_mundo)
        return sum(
            min(a * v, b * v) * scale
            for a, b, v, scale in zip(low, high, eixo_local, box.getScale(), strict=True)
        )

    def _atualizar_caixa(
        self,
        index: int,
        box,
        destination,
        dancing: bool,
        phase: float,
        strength: float,
        ajuste_x: float,
    ) -> None:
        """Atualiza voo, colisão de chão/frente e efeito sonoro visual de uma caixa."""
        elapsed = self.age - self.throw_beats[index]
        (box.show if elapsed >= 0 else box.hide)()
        u = max(0, min(1, elapsed / VOO_CAIXA_S))
        if dancing and -0.27 <= elapsed < VOO_CAIXA_S - 0.04:
            self.throw_index = index
        pos = self.launch_origin + (destination - self.launch_origin) * u
        pos.x += ajuste_x * u
        arc = sin(pi * u)
        pos.z += arc * 0.55
        low, high = self.bounds[index]
        box.setR(-75 * (1 - u))
        box.setScale(self.scales[index] * (0.07 + 0.93 * suavizar_quintico(u / 0.86)))
        if u >= 1:
            self._pulso_no_chao(index, box, pos, phase, strength, elapsed - VOO_CAIXA_S)
        else:
            pos.z = max(pos.z, self.floor_z - self._extensao_eixo(box, low, high, Vec3(0, 0, 1)))
        pos.y = max(pos.y + arc * 0.36, 0.24 - self._extensao_eixo(box, low, high, Vec3(0, 1, 0)))
        if not dancing and self.visibility < 0.99:
            fade_scale = max(0.02, self.visibility)
            cur_s = box.getScale()
            box.setScale(cur_s * fade_scale)
            pos.z = self.floor_z - low.z * float(box.getSz())
        box.setPos(pos)
        if u >= 1 and index == 0 and not self.compact:
            borda = box.getQuat().xform(Vec3(0, high.y * box.getSy() + 0.12, 0))
            self.seat.set(pos.x + borda.x, pos.y + borda.y, pos.z + high.z * box.getSz())
        self.effects[index].update(elapsed - VOO_CAIXA_S)

    def _tocar_som_pouso(self) -> None:
        if (
            self.age < PRIMEIRO_ARREMESSO_S + VOO_CAIXA_S
            or self._landing_sound_played
        ):
            return
        self._landing_sound_played = True
        app = self.renderer.showbase
        if (
            app.settings.audio.enabled
            and app.animation_controller._dance_preview_remaining <= 0
        ):
            from sejoga.musica.efeitos_sonoros import play_speaker_landing

            play_speaker_landing(app.settings.audio.master_volume)

    def update(self, dt, dancing, phase, energy, bass=0):
        """Atualiza os arremessos, os efeitos e o retorno do palco."""
        if dancing and not self.was_dancing:
            self.age = 0.0
            self._landing_sound_played = False
            self._stage_world_anchor = None
            self._stage_screen_anchor = None
        self.was_dancing = dancing
        if dancing:
            self.age += dt
        self.visibility += ((1 if dancing else 0) - self.visibility) * (1 - exp(-dt * 5))
        self.ejecting = dancing and 0.65 <= self.age < self.end_throws
        self.throw_index = -1
        if self.visibility < 0.005 or self.age < PRIMEIRO_ARREMESSO_S - 0.27:
            if self.visibility < 0.005 and not dancing:
                self._stage_world_anchor = None
                self._stage_screen_anchor = None
            self.root.hide()
            return
        self.root.show()
        self._atualizar_ancora_palco()
        strength = max(0, min(1, energy * 0.7 + bass * 0.9))
        ajuste_x = self._ajustar_palco_na_tela()
        for index, (box, destination) in enumerate(zip(self.boxes, self.destinations, strict=True)):
            self._atualizar_caixa(index, box, destination, dancing, phase, strength, ajuste_x)
        self._tocar_som_pouso()

    def _ajustar_palco_na_tela(self):
        r = self.renderer
        app = r.showbase
        desktop = getattr(app, "_desktop_rect", None)
        if self._stage_screen_anchor is not None and desktop is not None:
            x = self._stage_screen_anchor[0] - desktop[0]
            largura = desktop[2]
        else:
            x = getattr(r, "_scene_x_px", None)
            largura = r.width if x is not None else 0
        if x is None:
            return 0.0
        pixels = r.width * self.root.getSx() / r._view_width
        low, high = self.limites_x
        esquerda = (18 - x) / pixels - low
        direita = (largura - 18 - x) / pixels - high
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
        for no_cone, pos_base, esc_base in self._cones_por_caixa[index]:
            # No referencial local da caixa, +Y aponta para a câmera após setH(180).
            impulso = 0.042 * acento
            no_cone.setPos(pos_base.x, pos_base.y + impulso, pos_base.z)
            no_cone.setScale(esc_base * (1.0 + 0.055 * acento))
            if self._album_colors:
                cr, cg, cb = self._album_colors[index % len(self._album_colors)]
                ganho = 0.28 + 0.52 * max(0.0, min(1.0, strength))
                no_cone.setColorScale(
                    1.0 + (cr * 1.45 - 1.0) * ganho,
                    1.0 + (cg * 1.45 - 1.0) * ganho,
                    1.0 + (cb * 1.45 - 1.0) * ganho,
                    1.0,
                )
            else:
                no_cone.clearColorScale()

    @property
    def jump_progress(self):
        """Fração percorrida do salto."""
        return max(0, min(1, (self.age - self.start_jump) / DURACAO_SALTO_S))

    @property
    def turn(self):
        """Ângulo lateral durante a saída das caixas."""
        turn_out = suavizar_quintico(self.age / 1.35)
        turn_back = suavizar_quintico((self.age - self.start_jump) / 0.65)
        return 76 * turn_out * (1 - turn_back)

"""Efeitos visuais 2D de cena (micro-partículas pixel art e cartões expressivos)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from panda3d.core import Vec3

from sejoga.animacao.dados_autorais import vfx_ativos
from sejoga.render import arte_efeitos
from sejoga.render.sprites_efeitos import cartao_pixel

MAX_PARTICULAS = 64
# Plano frontal seguro diante da malha 3D e das caixas (camera ortografica em Y=-15).
_FX_FRONT_Y = -2.20
# Plano alinhado aos calcados para poeira de pouso/derrapagem passar atras dos pes.
_FX_CHAO_Y = 0.14


@dataclass(frozen=True, slots=True)
class EfeitoSpec:
    """Configuração reutilizável para emissão de sprites/partículas 2D."""

    ttl: float
    base_scale: float
    gravity: float = 0.0
    drag: float = 4.8
    wobble_amp: float = 0.0
    wobble_freq: float = 0.0
    spin_speed: float = 110.0
    pop_amp: float = 0.45
    fade_start: float = 0.30
    color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    stretch_x: float = 1.0
    stretch_y: float = 1.0


@dataclass
class _Particula:
    node: object
    vel: Vec3
    age: float
    ttl: float
    base_scale: float
    gravity: float = 0.0
    drag: float = 4.8
    wobble_amp: float = 0.0
    wobble_freq: float = 0.0
    wobble_phase: float = 0.0
    spin_speed: float = 110.0
    pop_amp: float = 0.45
    fade_start: float = 0.30
    base_x: float = 0.0
    frames: tuple[object, ...] | None = None
    frame_atual: int = 0
    flip_x: bool = False
    estatico: bool = False
    stretch_x: float = 1.0
    stretch_y: float = 1.0
    base_alpha: float = 1.0


class GerenciadorEfeitosCena:
    """Sistema unificado para micro-efeitos pixelados e expressões 2D de cena."""

    def __init__(self, parent_node, *, head_node=None, model_node=None) -> None:
        """Inicializa texturas, cartões fixos, nós auxiliares e temporizadores."""
        self.root = parent_node.attachNewNode("efeitos-cena")
        self.head_node = head_node
        self.model_node = model_node
        self._antena_dir_node = self._buscar_no_antena(head_node, "antena-direita")
        self._antena_esq_node = self._buscar_no_antena(head_node, "antena-esquerda")
        self._mao_dir_node = self._buscar_no_modelo(model_node, "hand")
        self._mao_esq_node = self._buscar_no_modelo(model_node, "hand2")
        self._tempo = 0.0
        self._particulas: list[_Particula] = []
        self._resetar_temporizadores()
        self._carregar_texturas()
        self._criar_cartoes_fixos()

    def _resetar_temporizadores(self) -> None:
        self._prev_ground = True
        self._prev_estouro = False
        self._prev_choque = False
        self._prev_celebrate = False
        self._prev_gosma = False
        self._prev_susto = False
        self._timer_nota = 0.0
        self._timer_onda = 0.0
        self._timer_deslize = 0.0
        self._timer_queda = 0.0
        self._timer_zzz = 0.0
        self._timer_celebrate = 0.0
        self._timer_carinho = 0.0
        self._prev_hit = False
        self._onda_lado = 0
        self._seq_nota = 0
        self._seq_zzz = 0
        self._peso_medo = 0.0
        self._peso_raiva = 0.0
        self._peso_tontura = 0.0
        self._peso_tremor = 0.0

    @staticmethod
    def _buscar_no_antena(head_node, nome_antena: str):
        if head_node is None or head_node.isEmpty():
            return None
        ant = head_node.find(f"**/{nome_antena}")
        if ant.isEmpty():
            return None
        esfera = ant.find("**/sphere")
        return esfera if not esfera.isEmpty() else ant

    @staticmethod
    def _buscar_no_modelo(model_node, nome: str):
        if model_node is None or model_node.isEmpty():
            return None
        no = model_node.find(f"**/{nome}")
        return None if no.isEmpty() else no

    def _carregar_texturas(self) -> None:
        self._tex_suor = arte_efeitos.tex_suor()
        self._tex_tremor = arte_efeitos.tex_tremor()
        self._tex_raiva = arte_efeitos.tex_raiva()
        self._tex_estrela = arte_efeitos.tex_estrela()
        self._tex_z = arte_efeitos.tex_z()
        self._tex_rastro_queda = arte_efeitos.tex_rastro_queda()
        self._tex_clarao = arte_efeitos.tex_clarao()
        self._tex_faisca = arte_efeitos.tex_faisca()
        self._tex_brilho = arte_efeitos.tex_brilho()
        self._tex_nota_simples = arte_efeitos.tex_nota_simples()
        self._tex_nota_dupla = arte_efeitos.tex_nota_dupla()
        self._tex_onda_sonora = arte_efeitos.tex_onda_sonora()
        self._tex_poeira = arte_efeitos.tex_poeira()
        self._tex_poeira_fiapo = arte_efeitos.tex_poeira_fiapo()
        self._tex_gosma = arte_efeitos.tex_gosma()
        self._tex_coracao = arte_efeitos.tex_coracao()
        # v2.0: ressuscita as 8 folhas 2x2 autorais de vfx_grafite (chroma-safe!)
        try:
            from sejoga.render.vfx_grafite import carregar_banco_grafite

            self._grafite = carregar_banco_grafite()
        except Exception:
            self._grafite = {}

    def _criar_cartoes_fixos(self) -> None:
        self._card_suor = self._criar_cartao("fx-suor", self._tex_suor, 0.30)
        self._card_tremor_l = self._criar_cartao("fx-tremor-l", self._tex_tremor, 0.30)
        self._card_tremor_r = self._criar_cartao("fx-tremor-r", self._tex_tremor, 0.30)
        self._card_raiva = self._criar_cartao("fx-raiva", self._tex_raiva, 0.34)
        self._estrelas = []
        for i in range(3):
            estrela = self._criar_cartao(f"fx-estrela-{i}", self._tex_estrela, 0.28)
            estrela.setColorScale(1.0, 0.90, 0.24, 1.0)
            self._estrelas.append(estrela)

    @property
    def total_particulas(self) -> int:
        """Quantidade de partículas ativas no gerenciador."""
        return len(self._particulas)

    def _criar_cartao(self, nome: str, tex, escala: float):
        card = cartao_pixel(self.root, nome, tex)
        card.setScale(escala)
        card.hide()
        return card

    def limpar(self) -> None:
        """Remove imediatamente todas as partículas ativas e oculta cartões fixos."""
        for p in self._particulas:
            p.node.removeNode()
        self._particulas.clear()
        for card in (
            self._card_suor,
            self._card_tremor_l,
            self._card_tremor_r,
            self._card_raiva,
            *self._estrelas,
        ):
            card.hide()

    def _registrar_particula(
        self,
        node,
        pos: Vec3,
        vel: Vec3,
        spec: EfeitoSpec,
        *,
        rot_deg: float = 0.0,
        wobble_phase: float = 0.0,
        frames: tuple[object, ...] | None = None,
        flip_x: bool = False,
        estatico: bool = False,
    ) -> _Particula:
        while len(self._particulas) >= MAX_PARTICULAS:
            antiga = self._particulas.pop(0)
            antiga.node.removeNode()
        node.setPos(pos.x, pos.y, pos.z)
        node.setColorScale(*spec.color)
        sx = spec.base_scale * spec.stretch_x
        sz = spec.base_scale * spec.stretch_y
        node.setScale(-sx if flip_x else sx, spec.base_scale, sz)
        if rot_deg:
            node.setR(rot_deg)
        particula = _Particula(
            node=node,
            vel=Vec3(vel),
            age=0.0,
            ttl=max(0.05, spec.ttl),
            base_scale=spec.base_scale,
            gravity=spec.gravity,
            drag=spec.drag,
            wobble_amp=spec.wobble_amp,
            wobble_freq=spec.wobble_freq,
            wobble_phase=wobble_phase,
            spin_speed=spec.spin_speed,
            pop_amp=spec.pop_amp,
            fade_start=spec.fade_start,
            base_x=float(pos.x),
            frames=frames,
            flip_x=flip_x,
            estatico=estatico,
            stretch_x=spec.stretch_x,
            stretch_y=spec.stretch_y,
            base_alpha=float(spec.color[3]) if len(spec.color) >= 4 else 1.0,
        )
        self._particulas.append(particula)
        return particula

    def emitir_particula(
        self,
        nome: str,
        tex,
        pos: Vec3,
        vel: Vec3,
        spec: EfeitoSpec,
        *,
        rot_deg: float = 0.0,
        wobble_phase: float = 0.0,
        flip_x: bool = False,
    ) -> _Particula:
        """Emissor compartilhado para partículas pixeladas 2D simples."""
        node = cartao_pixel(self.root, nome, tex)
        return self._registrar_particula(
            node,
            pos,
            vel,
            spec,
            rot_deg=rot_deg,
            wobble_phase=wobble_phase,
            flip_x=flip_x,
        )

    @staticmethod
    def _vfx(nome: str) -> dict[str, Any]:
        return vfx_ativos().get(nome, {})

    @staticmethod
    def _trio(
        cfg: dict[str, Any],
        chave: str,
        padrao: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        val = cfg.get(chave, padrao)
        if isinstance(val, (tuple, list)) and len(val) == 3:
            return (float(val[0]), float(val[1]), float(val[2]))
        return padrao

    @staticmethod
    def _cor(
        cfg: dict[str, Any],
        padrao: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> tuple[float, float, float, float]:
        val = cfg.get("cor", padrao)
        if isinstance(val, (tuple, list)) and len(val) == 4:
            return (float(val[0]), float(val[1]), float(val[2]), float(val[3]))
        return padrao

    @staticmethod
    def _ancora_de(
        cfg: dict[str, Any],
        anc: dict[str, Vec3],
        padrao: str,
    ) -> Vec3:
        nome_anc = str(cfg.get("ancora", padrao))
        return anc.get(nome_anc, anc[padrao])

    def emitir_poeira(self, pos: Vec3, quantidade: int = 2, intensidade: float = 1.0) -> None:
        """Emite duas micro-nuvens horizontais rentes à sola no pouso."""
        if quantidade <= 0:
            return
        fator = min(1.33, max(0.75, float(intensidade)))
        escala = 0.24 * fator
        for i, lado in enumerate((-1.0, 1.0)):
            tex = self._tex_poeira if i == 0 else self._tex_poeira_fiapo
            self.emitir_particula(
                "fx-poeira-p",
                tex,
                Vec3(pos.x + lado * 0.32, _FX_CHAO_Y, pos.z + 0.04),
                Vec3(lado * (1.20 * fator), 0.0, 0.22 * fator),
                EfeitoSpec(
                    ttl=0.26,
                    base_scale=escala,
                    gravity=-0.3,
                    drag=4.5,
                    spin_speed=-lado * 24.0,
                    pop_amp=0.25,
                    fade_start=0.45,
                    color=(0.96, 0.94, 0.88, 0.86),
                    stretch_x=1.20,
                    stretch_y=0.70,
                ),
                rot_deg=lado * -6.0,
                flip_x=(lado < 0.0 and tex is self._tex_poeira_fiapo),
            )

    def emitir_poeira_deslize(
        self, pos: Vec3, direcao_vel: float, intensidade: float = 1.0
    ) -> None:
        """Emite um fiapo horizontal discreto atrás do calcanhar ao deslizar/correr."""
        tras = -1.0 if direcao_vel >= 0.0 else 1.0
        fator = min(1.25, max(0.75, float(intensidade)))
        self.emitir_particula(
            "fx-deslize-p",
            self._tex_poeira_fiapo,
            Vec3(pos.x + tras * 0.26, _FX_CHAO_Y, pos.z + 0.03),
            Vec3(tras * 1.15 * fator, 0.0, 0.16),
            EfeitoSpec(
                ttl=0.22,
                base_scale=0.22 * fator,
                gravity=0.0,
                drag=3.8,
                spin_speed=tras * 16.0,
                pop_amp=0.20,
                fade_start=0.40,
                color=(0.95, 0.93, 0.88, 0.78),
                stretch_x=1.25,
                stretch_y=0.60,
            ),
            rot_deg=tras * 6.0,
            flip_x=(tras < 0.0),
        )

    def emitir_rastro_queda(self, pos: Vec3, quantidade: int = 2) -> None:
        """Emite apenas dois filetes finos verticais discretos durante queda rápida."""
        if quantidade <= 0:
            return
        dx, dz = 1.95, 0.55
        n = min(2, max(1, quantidade))
        for i in range(n):
            lado = -1.0 if i == 0 else 1.0
            self.emitir_particula(
                "fx-queda-p",
                self._tex_rastro_queda,
                Vec3(pos.x + lado * dx, _FX_FRONT_Y, pos.z + dz),
                Vec3(lado * 0.15, 0.0, 3.8),
                EfeitoSpec(
                    ttl=0.22,
                    base_scale=0.34,
                    gravity=0.0,
                    drag=1.2,
                    spin_speed=0.0,
                    pop_amp=0.12,
                    fade_start=0.32,
                    color=(0.82, 0.96, 1.0, 0.72),
                    stretch_x=0.55,
                    stretch_y=1.15,
                ),
            )

    def emitir_notas_musicais(self, pos: Vec3, quantidade: int = 1) -> None:
        """Emite notas musicais pixeladas minimalistas acima da cabeça."""
        if quantidade <= 0:
            return
        paleta_notas = (
            (0.32, 0.96, 1.0, 0.92),
            (0.56, 1.0, 0.42, 0.92),
            (1.0, 0.86, 0.32, 0.92),
            (1.0, 0.46, 0.62, 0.92),
        )
        for _ in range(min(1, quantidade)):
            idx = self._seq_nota
            self._seq_nota += 1
            lado = -1.0 if idx % 2 == 0 else 1.0
            tex = self._tex_nota_simples if idx % 2 == 0 else self._tex_nota_dupla
            self.emitir_particula(
                "fx-nota-p",
                tex,
                Vec3(pos.x + lado * 1.45, _FX_FRONT_Y, pos.z + 0.75),
                Vec3(lado * 0.32, 0.0, 0.72),
                EfeitoSpec(
                    ttl=0.52,
                    base_scale=0.26,
                    gravity=-0.15,
                    drag=1.0,
                    wobble_amp=0.10,
                    wobble_freq=3.8,
                    spin_speed=lado * 18.0,
                    pop_amp=0.24,
                    fade_start=0.52,
                    color=paleta_notas[idx % len(paleta_notas)],
                ),
                rot_deg=lado * -8.0,
                wobble_phase=idx * 1.1,
            )

    def emitir_ondas_sonoras(
        self, pos: Vec3, *, direcao: float = 1.0, scale: float = 0.84
    ) -> None:
        """Emite um arco sonoro discreto a partir do fone ou da caixa de som."""
        sinal = 1.0 if direcao >= 0.0 else -1.0
        fator = min(1.15, max(0.85, scale / 0.84))
        self.emitir_particula(
            "fx-onda-p",
            self._tex_onda_sonora,
            Vec3(pos.x + sinal * 0.68, _FX_FRONT_Y, pos.z + 0.05),
            Vec3(sinal * 0.82, 0.0, 0.18),
            EfeitoSpec(
                ttl=0.40,
                base_scale=0.28 * fator,
                drag=0.9,
                spin_speed=0.0,
                pop_amp=0.28,
                fade_start=0.45,
                color=(0.48, 0.96, 1.0, 0.85),
            ),
            rot_deg=0.0 if sinal >= 0.0 else 180.0,
        )

    def emitir_zzz(self, pos: Vec3) -> None:
        """Emite letra 'Z' pixelada flutuando em escada diagonal com leve inclinação."""
        cfg = self._vfx("zzz")
        idx = self._seq_zzz
        self._seq_zzz += 1
        escala = float(cfg.get("escala", 0.46)) + 0.07 * (idx % 3)
        dx, _, dz = self._trio(cfg, "deslocamento", (1.48, 0.0, 0.58))
        spec = EfeitoSpec(
            ttl=float(cfg.get("duracao_s", 1.75)),
            base_scale=escala,
            gravity=float(cfg.get("gravity", 0.0)),
            drag=float(cfg.get("drag", 0.42)),
            wobble_amp=0.16,
            wobble_freq=3.4,
            spin_speed=-10.0 if idx % 2 == 0 else 10.0,
            pop_amp=float(cfg.get("pop_amp", 0.20)),
            fade_start=float(cfg.get("fade_start", 0.65)),
            color=self._cor(cfg),
        )
        self.emitir_particula(
            "fx-z-p",
            self._tex_z,
            Vec3(pos.x + dx, _FX_FRONT_Y, pos.z + dz),
            Vec3(*self._trio(cfg, "velocidade", (0.92, 0.0, 1.55))),
            spec,
            rot_deg=-8.0 + 6.0 * (idx % 3),
            wobble_phase=idx * 0.9,
        )

    def emitir_gosma(
        self, pos: Vec3, quantidade: int = 2, direcao: float = 0.0
    ) -> None:
        """Emite duas gotas balísticas discretas quando tentáculos cospem/espirram."""
        if quantidade <= 0:
            return
        sinal = -1.0 if direcao < 0.0 else 1.0
        for i in range(2):
            nome = "fx-gosma-p" if i == 0 else "fx-gosma-gota"
            espalha = -0.35 if i == 0 else 0.35
            self.emitir_particula(
                nome,
                self._tex_gosma,
                Vec3(pos.x + sinal * (0.45 + 0.14 * i), _FX_FRONT_Y, pos.z + 0.10 * i),
                Vec3(sinal * (0.95 + 0.35 * i) + espalha * 0.40, 0.0, 1.85 - 0.25 * i),
                EfeitoSpec(
                    ttl=0.38,
                    base_scale=0.22 - 0.03 * i,
                    gravity=-11.0,
                    drag=0.55,
                    spin_speed=sinal * (68.0 + 28.0 * i),
                    pop_amp=0.22,
                    fade_start=0.55,
                    color=(1.0, 0.42, 0.72, 0.92),
                ),
            )

    def emitir_particulas_luminosas(
        self, pos: Vec3, quantidade: int = 3, *, pontos: tuple[Vec3, ...] = ()
    ) -> None:
        """Emite três pequenas estrelas cintilantes minimalistas ao redor das mãos erguidas."""
        if quantidade <= 0:
            return
        cores_festa = (
            (1.0, 0.92, 0.34, 0.94),
            (0.40, 0.96, 1.0, 0.94),
            (0.64, 1.0, 0.48, 0.94),
        )
        alvos = pontos if len(pontos) >= 3 else (
            Vec3(pos.x - 1.35, _FX_FRONT_Y, pos.z + 0.25),
            Vec3(pos.x + 1.35, _FX_FRONT_Y, pos.z + 0.25),
            Vec3(pos.x, _FX_FRONT_Y, pos.z + 0.72),
        )
        for i in range(3):
            lado = -1.0 if i == 0 else (1.0 if i == 1 else 0.0)
            p_alvo = alvos[i]
            self.emitir_particula(
                "fx-luz-p",
                self._tex_estrela if i != 1 else self._tex_brilho,
                Vec3(p_alvo.x, _FX_FRONT_Y, p_alvo.z + 0.18),
                Vec3(lado * 0.55, 0.0, 0.85 + 0.15 * (i % 2)),
                EfeitoSpec(
                    ttl=0.36,
                    base_scale=0.20 + 0.02 * i,
                    gravity=-1.2,
                    drag=1.6,
                    spin_speed=(1.0 if i % 2 else -1.0) * 90.0,
                    pop_amp=0.36,
                    fade_start=0.45,
                    color=cores_festa[i],
                ),
            )

    def _emitir_rajada_eletrica(self, centro: Vec3, escala_base: float, ttl_base: float) -> None:
        """Dispara micro-rajada elétrica limpa com clarão curto e três faíscas."""
        self.emitir_particula(
            "fx-clarao-fx",
            self._tex_clarao,
            centro,
            Vec3(0.0, 0.0, 0.0),
            EfeitoSpec(
                ttl=ttl_base * 0.72,
                base_scale=escala_base * 0.22,
                drag=0.0,
                spin_speed=120.0,
                pop_amp=0.40,
                fade_start=0.25,
                color=(1.0, 0.96, 0.72, 0.96),
            ),
        )
        for i, (ang_deg, speed) in enumerate(((38.0, 1.55), (152.0, 1.45), (-32.0, 1.35))):
            ang = math.radians(ang_deg)
            vx = math.cos(ang) * speed
            vz = math.sin(ang) * speed
            self.emitir_particula(
                "fx-faisca-fx",
                self._tex_faisca,
                Vec3(centro.x + math.cos(ang) * 0.14, _FX_FRONT_Y, centro.z + math.sin(ang) * 0.14),
                Vec3(vx, 0.0, vz),
                EfeitoSpec(
                    ttl=ttl_base * (0.75 + 0.08 * i),
                    base_scale=0.22,
                    drag=3.6,
                    spin_speed=(-1.0 if i % 2 else 1.0) * 85.0,
                    pop_amp=0.30,
                    fade_start=0.40,
                    color=(0.45, 0.96, 1.0, 0.96) if i != 1 else (1.0, 0.92, 0.36, 0.96),
                ),
                rot_deg=ang_deg,
            )

    def _emitir_estouro_fone(self, pos_fone: Vec3) -> None:
        origem = Vec3(pos_fone.x - 0.35, _FX_FRONT_Y, pos_fone.z + 0.08)
        self._emitir_rajada_eletrica(origem, 0.90, 0.24)

    def _emitir_choque_argolas(self, anc_d: Vec3, anc_e: Vec3) -> None:
        for ancora in (anc_d, anc_e):
            self._emitir_rajada_eletrica(Vec3(ancora.x, _FX_FRONT_Y, ancora.z), 0.90, 0.24)

    def _emitir_susto(self, ant_d: Vec3, ant_e: Vec3 | None = None) -> None:
        if ant_e is None:
            pontos = (
                Vec3(ant_d.x - 1.10, _FX_FRONT_Y, ant_d.z + 0.85),
                Vec3(ant_d.x + 1.10, _FX_FRONT_Y, ant_d.z + 0.85),
            )
        else:
            pontos = (
                Vec3(ant_d.x - 0.12, _FX_FRONT_Y, ant_d.z + 0.36),
                Vec3(ant_e.x + 0.12, _FX_FRONT_Y, ant_e.z + 0.36),
            )
        for idx, (lado, origem) in enumerate(((-1.0, pontos[0]), (1.0, pontos[1]))):
            tex = self._tex_faisca if idx == 0 else self._tex_clarao
            self.emitir_particula(
                "fx-susto-p",
                tex,
                origem,
                Vec3(lado * 0.95, 0.0, 1.15),
                EfeitoSpec(
                    ttl=0.18,
                    base_scale=0.24,
                    drag=3.2,
                    spin_speed=-lado * 70.0,
                    pop_amp=0.30,
                    fade_start=0.35,
                    color=(1.0, 0.92, 0.40, 0.96),
                ),
                rot_deg=lado * -24.0,
            )

    def _ancora_grupo(
        self,
        node,
        tabela: tuple[tuple[str, tuple[float, float, float], tuple[float, float, float]], ...],
    ) -> dict[str, Vec3]:
        out: dict[str, Vec3] = {}
        tem_no = node is not None and not node.isEmpty()
        for chave, local, fallback in tabela:
            if tem_no:
                p = self.root.getRelativePoint(node, Vec3(*local))
                out[chave] = Vec3(p.x, _FX_FRONT_Y, p.z)
            else:
                out[chave] = Vec3(*fallback)
        return out

    def _ancora_centro_no(self, node, fallback: tuple[float, float, float]) -> Vec3:
        if node is not None and not node.isEmpty():
            limites = node.getTightBounds(self.root)
            if limites:
                c = (limites[0] + limites[1]) * 0.5
                return Vec3(c.x, _FX_FRONT_Y, c.z)
            p = self.root.getRelativePoint(node, Vec3(0.0, 0.0, 0.0))
            return Vec3(p.x, _FX_FRONT_Y, p.z)
        return Vec3(*fallback)

    def _calcular_ancoras(self) -> dict[str, Vec3]:
        cabeca = (
            ("cabeca", (0.0, 0.14, 0.24), (0.0, _FX_FRONT_Y, 3.80)),
            ("antenas", (0.0, 0.10, 0.36), (0.0, _FX_FRONT_Y, 4.60)),
            ("fone_dir", (0.24, 0.10, 0.12), (-1.30, _FX_FRONT_Y, 3.25)),
            ("fone_esq", (-0.24, 0.10, 0.12), (1.35, _FX_FRONT_Y, 3.25)),
            ("suor", (0.27, 0.16, 0.25), (-1.50, _FX_FRONT_Y, 4.10)),
            ("raiva", (-0.31, 0.14, 0.32), (1.74, _FX_FRONT_Y, 4.52)),
            ("boca", (0.0, 0.18, 0.04), (0.0, _FX_FRONT_Y, 2.85)),
        )
        corpo = (
            ("pes", (0.0, 0.0, 0.01), (0.0, _FX_CHAO_Y, -1.52)),
            ("ombro_l", (-0.42, 0.0, 0.62), (-2.30, _FX_FRONT_Y, 2.00)),
            ("ombro_r", (0.42, 0.0, 0.62), (2.30, _FX_FRONT_Y, 2.00)),
            ("tronco", (0.0, 0.0, 0.52), (0.0, _FX_FRONT_Y, 1.35)),
        )
        anc = self._ancora_grupo(self.head_node, cabeca)
        anc.update(self._ancora_grupo(self.model_node, corpo))
        anc["antena_d"] = self._ancora_centro_no(self._antena_dir_node, (-2.05, _FX_FRONT_Y, 4.92))
        anc["antena_e"] = self._ancora_centro_no(self._antena_esq_node, (2.18, _FX_FRONT_Y, 4.92))
        anc["mao_d"] = self._ancora_centro_no(self._mao_dir_node, (-1.65, _FX_FRONT_Y, 3.60))
        anc["mao_e"] = self._ancora_centro_no(self._mao_esq_node, (1.65, _FX_FRONT_Y, 3.60))
        return anc

    @staticmethod
    def _definir_cartao(
        card,
        ativo: bool,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        escala_x: float | None = None,
        escala_z: float | None = None,
        flip_x: bool = False,
        rot_deg: float = 0.0,
    ) -> None:
        if not ativo:
            card.hide()
            return
        card.show()
        card.setPos(x, y, z)
        card.setR(rot_deg)
        if escala_x is not None:
            sz = escala_x if escala_z is None else escala_z
            card.setScale(-escala_x if flip_x else escala_x, escala_x, sz)
        elif flip_x:
            sx = abs(card.getSx())
            card.setScale(-sx, sx, sx)

    @staticmethod
    def _rampa_peso(atual: float, alvo: bool, dt: float) -> float:
        dest = 1.0 if alvo else 0.0
        taxa = dt / (0.10 if alvo else 0.14) if dt > 0.0 else 1.0
        return atual + max(-taxa, min(taxa, dest - atual))

    def _atualizar_cartoes_expressao(
        self,
        anc: dict[str, Vec3],
        *,
        dt: float,
        medo: bool,
        tremor: bool,
        raiva: bool,
        tontura: bool,
    ) -> None:
        self._peso_medo = self._rampa_peso(self._peso_medo, medo, dt)
        self._peso_raiva = self._rampa_peso(self._peso_raiva, raiva, dt)
        self._peso_tontura = self._rampa_peso(self._peso_tontura, tontura, dt)
        self._peso_tremor = self._rampa_peso(self._peso_tremor, tremor, dt)

        p_cab, p_suor, p_raiva = anc["cabeca"], anc["suor"], anc["raiva"]
        c_suor = (self._tempo * 1.35) % 1.0
        queda_suor = c_suor ** 1.45
        estica_z = 0.92 + 0.24 * c_suor
        estica_x = 1.08 - 0.14 * c_suor
        w_medo = self._peso_medo * (
            0.86 if c_suor > 0.80 else 1.0 + 0.14 * math.sin(min(1.0, c_suor * 4.0) * math.pi)
        )
        self._definir_cartao(
            self._card_suor,
            self._peso_medo > 0.02,
            p_suor.x,
            _FX_FRONT_Y,
            p_suor.z - queda_suor * 0.36,
            0.30 * w_medo * estica_x,
            0.30 * w_medo * estica_z,
        )
        batida_raiva = abs(math.sin(self._tempo * 11.0))
        pulso_raiva = (0.94 + 0.20 * (batida_raiva ** 1.6)) * self._peso_raiva
        tilt_raiva = math.sin(self._tempo * 14.0) * 7.0
        self._definir_cartao(
            self._card_raiva,
            self._peso_raiva > 0.02,
            p_raiva.x,
            _FX_FRONT_Y,
            p_raiva.z,
            0.34 * pulso_raiva,
            0.34 * pulso_raiva,
            rot_deg=tilt_raiva,
        )
        for i, estrela in enumerate(self._estrelas):
            ang = self._tempo * 5.0 + i * (math.tau / 3.0)
            escala_orb = 0.28 * (0.88 - 0.22 * math.sin(ang)) * self._peso_tontura
            self._definir_cartao(
                estrela,
                self._peso_tontura > 0.02,
                p_cab.x + math.cos(ang) * 0.92,
                _FX_FRONT_Y,
                p_cab.z + 0.72 + math.sin(ang) * 0.14,
                escala_orb,
                escala_orb,
                rot_deg=(self._tempo * 130.0 + i * 70.0) % 360.0,
            )
        p_ol, p_or = anc["ombro_l"], anc["ombro_r"]
        vib = (math.sin(self._tempo * 45.0) * 0.08 + math.sin(self._tempo * 29.0) * 0.03) * self._peso_tremor
        escala_tremor = 0.30 * self._peso_tremor * (1.0 + 0.12 * abs(math.sin(self._tempo * 22.0)))
        self._definir_cartao(
            self._card_tremor_l,
            self._peso_tremor > 0.02,
            p_ol.x + vib,
            _FX_FRONT_Y,
            p_ol.z,
            escala_tremor,
            escala_tremor,
            rot_deg=math.sin(self._tempo * 36.0) * 5.0,
        )
        self._definir_cartao(
            self._card_tremor_r,
            self._peso_tremor > 0.02,
            p_or.x - vib,
            _FX_FRONT_Y,
            p_or.z,
            escala_tremor,
            escala_tremor,
            flip_x=True,
            rot_deg=-math.sin(self._tempo * 36.0) * 5.0,
        )

    def _emitir_grafite(
        self,
        chave: str,
        pos: Vec3,
        *,
        escala: float = 0.82,
        ttl: float = 0.34,
        rot_deg: float = 0.0,
        flip_x: bool = False,
        vel: Vec3 = Vec3(0.0, 0.0, 0.0),
    ) -> bool:
        """Dispara uma folha 2x2 animada de ``vfx_grafite`` se disponível."""
        seq = self._grafite.get(chave)
        if seq is None or not seq.frames:
            return False
        node = cartao_pixel(self.root, f"fx-grafite-{chave}", seq.frames[0])
        spec = EfeitoSpec(
            ttl=ttl,
            base_scale=escala,
            pop_amp=0.16,
            fade_start=0.68,
            color=(1.0, 1.0, 1.0, 1.0),
        )
        self._registrar_particula(
            node,
            Vec3(pos.x, _FX_FRONT_Y - 0.04, pos.z),
            vel,
            spec,
            rot_deg=rot_deg,
            frames=seq.frames,
            flip_x=flip_x,
        )
        return True

    def emitir_carinho(self, pos: Vec3, quantidade: int = 2) -> None:
        """Emite corações pixelados e brilhos subindo suavemente no carinho real (v2.0)."""
        for i in range(quantidade):
            lado = -1.0 if i % 2 == 0 else 1.0
            spec = EfeitoSpec(
                ttl=1.05 + 0.15 * i,
                base_scale=0.26 + 0.04 * (i % 2),
                gravity=0.18,
                drag=0.9,
                wobble_amp=0.045,
                wobble_freq=4.2 + i,
                pop_amp=0.22,
                fade_start=0.58,
                color=(1.0, 1.0, 1.0, 1.0),
            )
            self.emitir_particula(
                "fx-coracao",
                self._tex_coracao,
                Vec3(pos.x + lado * (0.14 + 0.06 * i), _FX_FRONT_Y, pos.z + 0.24),
                Vec3(lado * 0.18, 0.0, 0.56 + 0.12 * i),
                spec,
                wobble_phase=i * 1.9,
            )
        self.emitir_particulas_luminosas(pos, quantidade=1)

    def _processar_gatilhos_disparo(
        self,
        anc: dict[str, Vec3],
        *,
        estouro_fone: bool,
        choque_argolas: bool,
        forca_impacto: float,
        grounded: bool,
        gosma_evento: bool,
        hit_evento: bool = False,
    ) -> None:
        if estouro_fone and not self._prev_estouro:
            self._emitir_estouro_fone(anc["fone_dir"])
            self._emitir_grafite("estouro_fone", anc["fone_dir"], escala=0.78, ttl=0.36)
        self._prev_estouro = estouro_fone

        if choque_argolas and not self._prev_choque:
            self._emitir_choque_argolas(anc["antena_d"], anc["antena_e"])
            meio_ant = (anc["antena_d"] + anc["antena_e"]) * 0.5
            self._emitir_grafite("choque_argolas", meio_ant, escala=0.86, ttl=0.38)
        self._prev_choque = choque_argolas

        if gosma_evento and not self._prev_gosma:
            self.emitir_gosma(anc["boca"], quantidade=3, direcao=-1.0)
            self._emitir_grafite("gosma", anc["boca"], escala=0.68, ttl=0.34)
        self._prev_gosma = gosma_evento

        if hit_evento and not self._prev_hit:
            self._emitir_grafite("batida", anc["tronco"], escala=0.95, ttl=0.30)
        self._prev_hit = hit_evento

        if not self._prev_ground and grounded and forca_impacto >= 0.85:
            qtd = 4 if forca_impacto >= 1.3 else 2
            self.emitir_poeira(anc["pes"], quantidade=qtd, intensidade=forca_impacto)
            if forca_impacto >= 1.15:
                self._emitir_grafite(
                    "pouso",
                    anc["pes"] + Vec3(0.0, 0.0, 0.14),
                    escala=0.88 if forca_impacto >= 1.35 else 0.68,
                    ttl=0.34,
                )
        self._prev_ground = grounded

    def _disparar_com_cooldown(
        self, attr: str, dt: float, ativo: bool, intervalo: float, acao
    ) -> None:
        restante = max(0.0, getattr(self, attr) - dt)
        if ativo and restante <= 0.0:
            acao()
            restante = intervalo
        setattr(self, attr, restante)

    def _emitir_ondas_cena(
        self, anc: dict[str, Vec3], som_fones: bool, caixas_som_pos: tuple[Vec3, ...]
    ) -> None:
        if som_fones:
            # v2.0: ondas sonoras bilaterais alternadas nos dois fones!
            if self._onda_lado % 2 == 0:
                self.emitir_ondas_sonoras(anc["fone_dir"], direcao=-1.0, scale=0.86)
            else:
                self.emitir_ondas_sonoras(anc["fone_esq"], direcao=1.0, scale=0.86)
            self._onda_lado += 1
        cx = anc["tronco"].x
        if caixas_som_pos:
            caixa_pos = caixas_som_pos[self._onda_lado % len(caixas_som_pos)]
            self.emitir_ondas_sonoras(
                caixa_pos, direcao=-1.0 if caixa_pos.x < cx else 1.0, scale=0.92
            )

    def _processar_emissores_continuos(
        self,
        dt: float,
        anc: dict[str, Vec3],
        *,
        estado: str,
        grounded: bool,
        velocidade: tuple[float, float],
        sono: bool,
        susto: bool,
        acento_danca: bool,
        deslizando: bool,
        comemorando: bool,
        som_fones: bool,
        caixas_som_pos: tuple[Vec3, ...],
    ) -> None:
        self._disparar_com_cooldown(
            "_timer_nota",
            dt,
            (estado == "dance" and acento_danca) or som_fones,
            1.05 if estado != "dance" else 1.25,
            lambda: self.emitir_notas_musicais(anc["cabeca"], quantidade=1),
        )
        emite_onda = (som_fones and (acento_danca or estado != "dance")) or (
            acento_danca and bool(caixas_som_pos)
        )
        self._disparar_com_cooldown(
            "_timer_onda",
            dt,
            emite_onda,
            1.5,
            lambda: self._emitir_ondas_cena(
                anc,
                som_fones and (acento_danca or estado != "dance"),
                caixas_som_pos,
            ),
        )
        self._disparar_com_cooldown(
            "_timer_deslize",
            dt,
            deslizando,
            0.26,
            lambda: (
                self.emitir_poeira_deslize(
                    anc["pes"], velocidade[0] if abs(velocidade[0]) > 10.0 else 1.0
                ),
                self._emitir_grafite(
                    "derrapagem",
                    anc["pes"] + Vec3(0.0, 0.0, 0.10),
                    escala=0.62,
                    ttl=0.28,
                    flip_x=velocidade[0] < 0.0,
                ),
            ),
        )
        self._disparar_com_cooldown(
            "_timer_queda",
            dt,
            not grounded and abs(velocidade[1]) > 420.0,
            0.22,
            lambda: self.emitir_rastro_queda(anc["pes"] + Vec3(0.0, 0.0, 0.35), quantidade=2),
        )
        self._disparar_com_cooldown(
            "_timer_zzz",
            dt,
            sono,
            float(self._vfx("zzz").get("cooldown_s", 0.62)),
            lambda: self.emitir_zzz(self._ancora_de(self._vfx("zzz"), anc, "cabeca")),
        )
        if susto and not self._prev_susto:
            self._emitir_susto(anc["antena_d"], anc["antena_e"])
            self._emitir_grafite("susto", anc["cabeca"] + Vec3(0.0, 0.0, 0.34), escala=0.82, ttl=0.34)
        self._prev_susto = susto
        if comemorando and not self._prev_celebrate:
            self._emitir_grafite("comemoracao", anc["cabeca"] + Vec3(0.0, 0.0, 0.30), escala=0.92, ttl=0.40)
        self._prev_celebrate = comemorando
        self._disparar_com_cooldown(
            "_timer_celebrate",
            dt,
            comemorando,
            0.52,
            lambda: self.emitir_particulas_luminosas(
                anc["cabeca"],
                quantidade=3,
                pontos=(anc["mao_d"], anc["mao_e"], anc["cabeca"] + Vec3(0.0, 0.0, 0.68)),
            ),
        )
        self._disparar_com_cooldown(
            "_timer_carinho",
            dt,
            estado == "pet",
            0.48,
            lambda: self.emitir_carinho(anc["cabeca"], quantidade=2),
        )

    def _atualizar_particulas(self, dt: float) -> None:
        vivas: list[_Particula] = []
        dt_clamped = max(0.0, dt)
        for p in self._particulas:
            p.age += dt_clamped
            if p.age >= p.ttl:
                p.node.removeNode()
                continue
            self._avancar_particula(p, dt_clamped)
            vivas.append(p)
        self._particulas = vivas

    def _avancar_particula(self, p: _Particula, dt: float) -> None:
        u = p.age / p.ttl
        if p.frames:
            idx_f = min(len(p.frames) - 1, int(u * len(p.frames)))
            if idx_f != p.frame_atual:
                p.node.setTexture(p.frames[idx_f], 1)
                p.frame_atual = idx_f
        arrasto = max(0.25, 1.0 - p.drag * dt) if p.drag > 0.0 else 1.0
        vz = p.vel.z + p.gravity * dt
        p.vel = Vec3(p.vel.x * arrasto, p.vel.y * arrasto, vz * max(0.45, arrasto))
        pos = p.node.getPos()
        novo_x = pos.x + p.vel.x * dt
        if p.wobble_amp > 0.0 and p.wobble_freq > 0.0:
            novo_x += (
                math.cos(self._tempo * p.wobble_freq + p.wobble_phase)
                * p.wobble_amp
                * p.wobble_freq
                * dt
            )
        p.node.setPos(novo_x, pos.y + p.vel.y * dt, pos.z + p.vel.z * dt)
        if p.spin_speed:
            p.node.setR(p.node.getR() + dt * p.spin_speed)
        if p.estatico:
            escala = p.base_scale
        else:
            entrada = 0.65 + 0.35 * min(1.0, u / 0.16)
            incha = 1.0 + p.pop_amp * math.sin(min(1.0, u * 2.2) * math.pi)
            corte = max(0.05, 1.0 - p.fade_start)
            t_fade = max(0.0, u - p.fade_start) / corte
            encolhe = max(0.14, 1.0 - (t_fade * t_fade) * 0.86)
            escala = p.base_scale * entrada * incha * encolhe
            if not p.frames:
                alpha = max(0.0, min(1.0, p.base_alpha * (1.0 - t_fade ** 1.35)))
                p.node.setShaderInput("u_fade", alpha)
            else:
                fade_g = max(0.0, min(1.0, 1.0 - t_fade ** 1.6))
                p.node.setShaderInput("u_fade", fade_g)
        sx = escala * p.stretch_x
        sz = escala * p.stretch_y
        p.node.setScale(-sx if p.flip_x else sx, escala, sz)

    def atualizar(
        self,
        dt: float,
        *,
        estado: str,
        tempo_estado: float,
        grounded: bool,
        velocidade: tuple[float, float] = (0.0, 0.0),
        medo: bool = False,
        tremor: bool = False,
        susto: bool = False,
        raiva: bool = False,
        tontura: bool = False,
        sono: bool = False,
        aviso_antena: float = 0.0,
        estouro_fone: bool = False,
        choque_argolas: bool = False,
        acento_danca: bool = False,
        forca_impacto: float = 1.0,
        deslizando: bool = False,
        comemorando: bool = False,
        som_fones: bool = False,
        caixas_som_pos: tuple[Vec3, ...] = (),
        gosma_evento: bool = False,
    ) -> None:
        """Atualiza cartões expressivos, emissores de grafite e partículas vivas."""
        del tempo_estado, aviso_antena
        dt_clamped = max(0.0, dt)
        self._tempo += dt_clamped
        anc = self._calcular_ancoras()
        self._atualizar_cartoes_expressao(
            anc, dt=dt_clamped, medo=medo, tremor=tremor, raiva=raiva, tontura=tontura
        )
        self._processar_gatilhos_disparo(
            anc,
            estouro_fone=estouro_fone,
            choque_argolas=choque_argolas,
            forca_impacto=forca_impacto,
            grounded=grounded,
            gosma_evento=gosma_evento,
            hit_evento=(estado == "hit"),
        )
        self._processar_emissores_continuos(
            dt_clamped,
            anc,
            estado=estado,
            grounded=grounded,
            velocidade=velocidade,
            sono=sono,
            susto=susto,
            acento_danca=acento_danca,
            deslizando=deslizando,
            comemorando=comemorando,
            som_fones=som_fones,
            caixas_som_pos=caixas_som_pos,
        )
        self._atualizar_particulas(dt_clamped)

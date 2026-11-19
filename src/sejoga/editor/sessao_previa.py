"""Motor determinístico de prévia e ensaio do editor (Python puro).

Suporta os modos ``Tomada`` (ensaio isolado da ação com solo/silenciamento e
comparação Salvo vs Rascunho) e ``Em contexto`` (simulação completa do
``AnimationController`` com roteiro de estímulos, música e obstáculos).

FRONTEIRA: nunca importa ``panda3d``, ``PySide6`` nem ``win32*``.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from sejoga.animacao import dados_autorais
from sejoga.animacao.animacao_entrada import IntroAnimation
from sejoga.animacao.animacao_saida import ExitAnimation
from sejoga.animacao.cenas_idle import AmostraCenaIdle, amostrar_cena_idle
from sejoga.animacao.clipes_animacao import amostrar_clipe
from sejoga.animacao.clipes_gltf import AmostraClipeGltf, amostrar_clipe_gltf
from sejoga.animacao.clipes_ocioso import (
    camada_respiracao,
    deslocamento_idle_ativo,
    sample_idle,
)
from sejoga.animacao.controlador_animacao import AnimationController
from sejoga.animacao.danca_clipes import carregar_clipe_emote
from sejoga.animacao.movimento_danca import DanceMotion
from sejoga.animacao.movimento_pernas import LegMotion, LegPose
from sejoga.animacao.pose_repouso import pose_repouso
from sejoga.animacao.poses_base import (
    pose_flourish,
    pose_idle,
    pose_interaction,
    pose_secondary,
    pose_sleep,
    pose_walk,
)
from sejoga.animacao.respiracao import amostrar_respiracao_repouso
from sejoga.animacao.respiracao_tuning import parametros_de
from sejoga.animacao.teimosia_pose import aplicar_fase as aplicar_pose_teimosia
from sejoga.editor.catalogo import AcaoCatalogo
from sejoga.editor.documento import DocumentoEditor
from sejoga.editor.ik_membros import compor_pose_pernas
from sejoga.editor.roteiro import (
    EstimuloRoteiro,
    ObstaculoPrevia,
    RoteiroEnsaio,
    roteiro_padrao_para_categoria,
)
from sejoga.musica.escuta_musica import MusicSnapshot
from sejoga.nucleo.cinematica import posicao_no
from sejoga.nucleo.esqueleto import ALL_GROUPS, IdlePersonality, Rig, Rotation3
from sejoga.nucleo.modelo import Model
from sejoga.tentaculos.coreografia_porta import CoreografiaPorta, saida_do_temperamento
from sejoga.tentaculos.ondulacao import (
    OndulacaoTuning,
    deslocamento_ondulante,
    ondulacao_do_temperamento,
)

STEP_SIM_S = 1.0 / 60.0
_ANCORAS_PONTOS_BASE: tuple[tuple[float, float, float], ...] = (
    (0.06, 0.04, 0.34),
    (0.11, 0.05, 0.42),
    (-0.04, 0.06, 0.38),
    (0.08, 0.03, 0.28),
)


class ModoPrevia(StrEnum):
    """Modos de reprodução da janela de edição."""

    TOMADA = "tomada"
    EM_CONTEXTO = "em_contexto"


@dataclass(frozen=True, slots=True)
class EventoVfxPrevia:
    """Disparo de efeito visual capturado em um instante da simulação."""

    nome: str
    tempo_s: float
    origem: str = "tomada"
    pos: tuple[float, float, float] | None = None
    dados: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QuadroPrevia:
    """Snapshot completo do estado avaliado no cursor atual da prévia."""

    tempo_s: float = 0.0
    duracao_s: float = 4.0
    quadro_indice: int = 0
    fps: int = 60
    modo: ModoPrevia = ModoPrevia.TOMADA
    acao_id: str = ""
    variante: str | None = None
    pose: dict[str, Rotation3] = field(default_factory=pose_repouso)
    pose_pretendida: dict[str, Rotation3] = field(default_factory=pose_repouso)
    pernas: LegPose | None = None
    raiz_quat: tuple[float, float, float, float] | None = None
    dedos_clipe: tuple[tuple[float, ...], tuple[float, ...]] | None = None
    deslocamento_corpo: tuple[float, float, float] = (0.0, 0.0, 0.0)
    orientacao_graus: tuple[float, float, float] = (0.0, 0.0, 0.0)
    escala: float = 1.0
    dissolve: float = 0.0
    tentaculos_ativos: bool = False
    tentaculo_temperamento: str = "calm"
    tentaculos_porta_aberta: float = 0.0
    pontos_tentaculos: tuple[tuple[tuple[float, float, float], ...], ...] = ()
    contatos_obstaculo: tuple[tuple[float, float, float], ...] = ()
    eventos_vfx: tuple[EventoVfxPrevia, ...] = ()
    janelas_vfx_ativas: tuple[str, ...] = ()
    eventos_gltf: tuple[str, ...] = ()
    estado_contexto: str = "tomada"
    reacao_contexto: str | None = None
    prioridade_contexto: str = "isolada"
    respiracao_valor: float = 0.0
    batida_ativa: bool = False
    fase_batida: float = 0.0
    bpm_efetivo: float = 108.0
    amostra_cena: AmostraCenaIdle | None = None
    provisoria_ativa: bool = False


def _somar_rot(a: Rotation3, b: Rotation3) -> Rotation3:
    return Rotation3(x=a.x + b.x, y=a.y + b.y, z=a.z + b.z)


def _pose_de_graus_sobre_repouso(
    deltas_graus: dict[str, tuple[float, float, float]],
    *,
    base_absoluta: bool = False,
) -> dict[str, Rotation3]:
    pose = pose_repouso()
    for grupo, (gx, gy, gz) in deltas_graus.items():
        if grupo not in ALL_GROUPS:
            continue
        rot = Rotation3(math.radians(gx), math.radians(gy), math.radians(gz))
        pose[grupo] = rot if base_absoluta else _somar_rot(pose[grupo], rot)
    return pose


def _limitar_aabb(
    ponto: tuple[float, float, float], obstaculo: ObstaculoPrevia
) -> tuple[tuple[float, float, float], bool]:
    if not obstaculo.ativo:
        return ponto, False
    cx, cy, cz = obstaculo.centro
    hx, hy, hz = obstaculo.meia_extensao
    dentro = (
        abs(ponto[0] - cx) <= hx
        and abs(ponto[1] - cy) <= hy
        and abs(ponto[2] - cz) <= hz
    )
    if not dentro:
        return ponto, False
    dx = (ponto[0] - cx) / max(1e-4, hx)
    dy = (ponto[1] - cy) / max(1e-4, hy)
    dz = (ponto[2] - cz) / max(1e-4, hz)
    ax, ay, az = abs(dx), abs(dy), abs(dz)
    px, py, pz = ponto
    if ax >= ay and ax >= az:
        px = cx + (hx + 0.015 if dx >= 0.0 else -(hx + 0.015))
    elif ay >= ax and ay >= az:
        py = cy + (hy + 0.015 if dy >= 0.0 else -(hy + 0.015))
    else:
        pz = cz + (hz + 0.015 if dz >= 0.0 else -(hz + 0.015))
    return (px, py, pz), True


def _novo_rig() -> Rig:
    return Rig(rest=pose_repouso(), current=pose_repouso())


def _amostrar_segmentos_tentaculo(
    idx: int,
    base: tuple[float, float, float],
    tempo_local: float,
    fator_ext: float,
    traj: dict[str, Any],
    ond: OndulacaoTuning,
    obstaculo: ObstaculoPrevia,
) -> tuple[tuple[tuple[float, float, float], ...], list[tuple[float, float, float]]]:
    atraso_seg = float(traj.get("atraso_segmento_s", 0.045))
    elevacao_arco = float(traj.get("elevacao_arco", 0.30))
    avanco_frontal = float(traj.get("avanco_frontal", -0.18))
    escala_alcance = float(traj.get("escala_alcance", 1.0))

    segs: list[tuple[float, float, float]] = []
    contatos: list[tuple[float, float, float]] = []
    for s_idx in range(6):
        u = (s_idx / 5.0) * fator_ext
        t_seg = max(0.0, tempo_local - s_idx * atraso_seg)
        onda_x_px, onda_z_px = deslocamento_ondulante(
            ond, u, t_seg, fase_inicial=idx * 1.35
        )
        alcance = 0.55 * escala_alcance * u
        px = base[0] + (0.28 + idx * 0.04) * alcance + onda_x_px / 216.8
        py = base[1] + avanco_frontal * alcance - 0.14 * u
        pz = base[2] + elevacao_arco * math.sin(u * math.pi) + onda_z_px / 216.8
        p_res, tocou = _limitar_aabb((px, py, pz), obstaculo)
        segs.append(p_res)
        if tocou:
            contatos.append(p_res)
    return tuple(segs), contatos


def _amostrar_tentaculos_puros(
    tempo_s: float,
    duracao_s: float,
    personalidade: str,
    obstaculo: ObstaculoPrevia,
) -> tuple[
    float,
    tuple[tuple[tuple[float, float, float], ...], ...],
    tuple[tuple[float, float, float], ...],
]:
    """Calcula porta, trajetórias segmentadas e contatos no domínio puro."""
    tent_cfg = dados_autorais.obter_secao("TENTACULOS")
    traj = dict(tent_cfg.get("trajetoria_ponta", {}))
    saida = saida_do_temperamento(personalidade)
    ond = ondulacao_do_temperamento(personalidade)
    coreo = CoreografiaPorta()
    coreo.iniciar_empurrao()

    rev = min(1.0, tempo_s / max(0.25, saida.duracao_s))
    retraindo = tempo_s > max(saida.duracao_s * 1.4, duracao_s * 0.72)
    fator_ext = (
        max(0.0, 1.0 - (tempo_s - duracao_s * 0.72) / max(0.3, duracao_s * 0.25))
        if retraindo
        else min(1.0, tempo_s / max(0.25, saida.duracao_s * 0.65))
    )
    passo = coreo.avancar(
        STEP_SIM_S,
        revelacao_atuador=rev,
        angulo_porta=saida.angulo_empurrao_graus * rev,
        ha_ativos=not retraindo,
        angulo_empurrao=saida.angulo_empurrao_graus,
    )
    angulo_porta = (
        passo.angulo_porta
        if passo.angulo_porta is not None
        else saida.angulo_empurrao_graus * fator_ext
    )

    curvas: list[tuple[tuple[float, float, float], ...]] = []
    contatos: list[tuple[float, float, float]] = []
    for idx, base in enumerate(_ANCORAS_PONTOS_BASE):
        t_local = max(0.0, tempo_s - idx * saida.escalonamento_s * 0.35)
        segs, cont = _amostrar_segmentos_tentaculo(
            idx, base, t_local, fator_ext, traj, ond, obstaculo
        )
        curvas.append(segs)
        contatos.extend(cont)
    return float(angulo_porta), tuple(curvas), tuple(contatos)


def _ritmo_no_instante(
    tempo_s: float,
    tempo_ant: float,
    roteiro: RoteiroEnsaio,
    provedor_musica: Callable[[], MusicSnapshot] | None,
) -> tuple[bool, float, float, float, float, bool]:
    """Devolve ``(playing, intensity, bass, bpm, phase, beat_edge)``."""
    if roteiro.usar_musica_ao_vivo and provedor_musica is not None:
        snap = provedor_musica()
        bpm_vivo = float(snap.bpm or roteiro.bpm or 108.0)
        return (
            bool(snap.is_playing or snap.audio_active),
            float(snap.audio_level),
            float(snap.bass_level),
            bpm_vivo,
            float(snap.beat_phase),
            bool(snap.beat_detected),
        )
    bpm = max(40.0, min(240.0, float(roteiro.bpm or 108.0)))
    periodo = 60.0 / bpm
    fase = (tempo_s / periodo) % 1.0
    if roteiro.batidas_gravadas_s:
        bateu = any(
            tempo_ant < b <= tempo_s + 1e-6 for b in roteiro.batidas_gravadas_s
        )
    else:
        bateu = roteiro.metronomo_ativo and (
            math.floor(tempo_s / periodo) > math.floor(max(0.0, tempo_ant) / periodo)
            or (tempo_ant < 0.0 <= tempo_s)
        )
    pulso = math.exp(-fase * 4.5)
    return True, 0.58 + 0.25 * pulso, 0.35 + 0.35 * pulso, bpm, fase, bateu


def _personalidade_segura(nome: str) -> IdlePersonality:
    try:
        return IdlePersonality(nome)
    except ValueError:
        return IdlePersonality.CALM


def _chave_segundo_segmento(chave_dados: str) -> str:
    return chave_dados.split(":", 1)[1] if ":" in chave_dados else chave_dados


def _extrair_pos_raiz(deslocamento: tuple[float, ...]) -> tuple[float, float, float]:
    if len(deslocamento) >= 3:
        return (float(deslocamento[0]), float(deslocamento[1]), float(deslocamento[2]))
    return (0.0, 0.0, 0.0)


def _aplicar_provisoria(
    pose: dict[str, Rotation3],
    documento: DocumentoEditor,
    acao_id: str,
) -> tuple[dict[str, Rotation3], bool]:
    prov = documento.provisoria
    if not prov.ativa or prov.acao_id != acao_id:
        return pose, False
    saida = dict(pose)
    for grupo, (gx, gy, gz) in prov.grupos.items():
        if grupo in saida:
            saida[grupo] = Rotation3(
                math.radians(gx), math.radians(gy), math.radians(gz)
            )
    return saida, True


def _aplicar_mascaras_pistas(
    pose: dict[str, Rotation3],
    base_neutra: dict[str, Rotation3],
    pista_solo: str | None,
    pistas_silenciadas: set[str],
) -> dict[str, Rotation3]:
    if pista_solo is None and not pistas_silenciadas:
        return pose
    saida = dict(pose)
    for grupo in ALL_GROUPS:
        if pista_solo is not None:
            if grupo != pista_solo:
                saida[grupo] = base_neutra[grupo]
        elif grupo in pistas_silenciadas:
            saida[grupo] = base_neutra[grupo]
    return saida


def _duracao_acao(acao: AcaoCatalogo | None, dados: dict[str, Any]) -> float:
    if acao is None:
        return 4.0
    if acao.secao_dados == "CENAS_IDLE":
        cfg = dados.get("CENAS_IDLE", {}).get(acao.chave_dados, {})
        return max(0.25, float(cfg.get("duration", acao.duracao_padrao_s)))
    if acao.secao_dados == "IDLE_CLIPS":
        cfg = dados.get("IDLE_CLIPS", {}).get(acao.chave_dados, {})
        return max(0.5, float(cfg.get("duration", acao.duracao_padrao_s)))
    if acao.secao_dados == "RESPIRACAO" and acao.chave_dados == "ciclo":
        ciclo = dados.get("RESPIRACAO", {}).get("ciclo", ())
        if ciclo:
            return max(0.5, float(ciclo[-1][0]))
    if acao.secao_dados == "CLIPES_GLTF":
        cfg = dados.get("CLIPES_GLTF", {}).get(acao.chave_dados, {})
        ini = float(cfg.get("inicio_s", 0.0))
        fim = float(cfg.get("fim_s") or acao.duracao_padrao_s)
        vel = max(0.1, float(cfg.get("velocidade", 1.0)))
        return max(0.3, (fim - ini) / vel)
    if acao.secao_dados == "VFX":
        cfg = dados.get("VFX", {}).get(acao.chave_dados, {})
        return max(1.0, float(cfg.get("duracao_s", 0.5)) * 2.5)
    return max(0.5, float(acao.duracao_padrao_s))


class SessaoPrevia:
    """Coordena a simulação de prévia no modo ``Tomada`` ou ``Em contexto``."""

    def __init__(
        self,
        documento: DocumentoEditor,
        *,
        semente: int = 12345,
        provedor_musica: Callable[[], MusicSnapshot] | None = None,
    ) -> None:
        """Inicializa o estado da prévia sem acoplar engine gráfico."""
        self.documento = documento
        self.semente = int(semente)
        self.provedor_musica = provedor_musica
        self.acao: AcaoCatalogo | None = None
        self.variante: str | None = None
        self.modo: ModoPrevia = ModoPrevia.TOMADA
        self.roteiro = RoteiroEnsaio()
        self.fps: int = 60
        self.loop_ativo: bool = False
        self.velocidade: float = 1.0
        self.reproduzindo: bool = False
        self.tempo_s: float = 0.0
        self.pista_solo: str | None = None
        self.pistas_silenciadas: set[str] = set()
        self._callbacks_reset: list[Callable[[], None]] = []

        self._rig = _novo_rig()
        self._controller = AnimationController(self._rig, transition_seconds=0.35)
        self._dance_tomada = DanceMotion()
        self._leg_tomada = LegMotion()
        self._sim_tempo: float = 0.0
        self._tempo_anterior_frame: float = -STEP_SIM_S
        self._ultimo_quadro = QuadroPrevia()
        self._janelas_disparadas: set[str] = set()
        self._estimulos_disparados: set[int] = set()
        self._drag_ativo: bool = False
        self._obstaculo_dinamico: ObstaculoPrevia | None = None

    def registrar_callback_reset(self, callback: Callable[[], None]) -> None:
        """Registra observador notificado ao reiniciar ou buscar para trás."""
        self._callbacks_reset.append(callback)

    def _notificar_reset(self) -> None:
        for cb in self._callbacks_reset:
            cb()

    @property
    def duracao_s(self) -> float:
        """Duração da ação atualmente selecionada considerando o rascunho vivo."""
        return _duracao_acao(self.acao, self.documento.rascunho)

    @property
    def ultimo_quadro(self) -> QuadroPrevia:
        """Último quadro calculado pela sessão."""
        return self._ultimo_quadro

    def definir_fps(self, fps: int) -> None:
        """Define a taxa visual de quadros na timeline (24, 30 ou 60)."""
        self.fps = fps if fps in (24, 30, 60) else 60
        self._ultimo_quadro = self.reavaliar_quadro_atual()

    def definir_loop(self, ativo: bool) -> None:
        """Ativa ou desativa repetição automática ao fim da tomada."""
        self.loop_ativo = bool(ativo)

    def definir_velocidade(self, velocidade: float) -> None:
        """Ajusta o multiplicador de velocidade da prévia."""
        self.velocidade = max(0.1, min(2.0, float(velocidade)))

    def reproduzir(self) -> None:
        """Inicia reprodução contínua a partir do cursor atual."""
        self.reproduzindo = True

    def pausar(self) -> None:
        """Pausa a reprodução mantendo o cursor no instante atual."""
        self.reproduzindo = False

    def alternar_reproducao(self) -> bool:
        """Alterna entre reprodução e pausa retornando o novo estado."""
        self.reproduzindo = not self.reproduzindo
        return self.reproduzindo

    def selecionar_acao(
        self, acao: AcaoCatalogo | None, variante: str | None = None
    ) -> QuadroPrevia:
        """Abre ``acao`` no cursor ``0.0`` com o roteiro padrão da família."""
        self.acao = acao
        if variante is not None:
            self.variante = variante
        elif acao is not None and acao.variantes:
            self.variante = acao.variantes[0]
        else:
            self.variante = None
        if acao is not None:
            self.roteiro = roteiro_padrao_para_categoria(
                "cenas_idle" if acao.secao_dados == "CENAS_IDLE" else acao.familia_id,
                acao.chave_dados,
                bpm_inicial=float(
                    self.documento.rascunho.get("DANCA", {})
                    .get("tuning", {})
                    .get("bpm_padrao", 108.0)
                ),
            )
        else:
            self.roteiro = RoteiroEnsaio()
        self.pista_solo = None
        self.pistas_silenciadas.clear()
        self.reproduzindo = False
        return self.ir_para(0.0, forcar_reset=True)

    def definir_variante(self, variante: str | None) -> QuadroPrevia:
        """Troca a variante selecionada e reavalia no instante atual."""
        self.variante = variante
        return self.ir_para(self.tempo_s, forcar_reset=True)

    def definir_modo(self, modo: ModoPrevia) -> QuadroPrevia:
        """Alterna entre ``Tomada`` e ``Em contexto`` preservando o instante."""
        if modo == self.modo:
            return self._ultimo_quadro
        self.modo = modo
        return self.ir_para(self.tempo_s, forcar_reset=True)

    def definir_roteiro(self, roteiro: RoteiroEnsaio) -> QuadroPrevia:
        """Atualiza roteiro de estímulos/ritmo/obstáculo e reavalia."""
        self.roteiro = roteiro
        return self.ir_para(self.tempo_s, forcar_reset=True)

    def definir_solo(self, pista: str | None) -> QuadroPrevia:
        """Isola uma junta na camada da tomada (ou limpa com ``None``)."""
        self.pista_solo = None if self.pista_solo == pista else pista
        return self.reavaliar_quadro_atual()

    def alternar_silenciada(self, pista: str) -> QuadroPrevia:
        """Silencia ou reativa uma junta na tomada."""
        if pista in self.pistas_silenciadas:
            self.pistas_silenciadas.remove(pista)
        else:
            self.pistas_silenciadas.add(pista)
        return self.reavaliar_quadro_atual()

    def avancar(self, dt: float) -> QuadroPrevia:
        """Avança o relógio da prévia durante reprodução contínua."""
        if not self.reproduzindo or dt <= 0.0:
            return self._ultimo_quadro
        dur = self.duracao_s
        novo_t = self.tempo_s + dt * self.velocidade
        if novo_t >= dur:
            if self.loop_ativo:
                sobra = novo_t % max(1e-4, dur)
                return self.ir_para(sobra, forcar_reset=True)
            self.reproduzindo = False
            novo_t = dur
        return self.ir_para(novo_t, forcar_reset=False)

    def avancar_quadro(self, delta_quadros: int = 1) -> QuadroPrevia:
        """Desloca o cursor em quadros discretos segundo ``self.fps``."""
        passo = 1.0 / max(1, self.fps)
        alvo = max(0.0, min(self.duracao_s, self.tempo_s + delta_quadros * passo))
        return self.ir_para(alvo, forcar_reset=delta_quadros < 0)

    def reavaliar_quadro_atual(self) -> QuadroPrevia:
        """Recomputa o quadro atual refletindo edições recém-feitas no rascunho."""
        return self.ir_para(self.tempo_s, forcar_reset=True)

    def disparar_estimulo_agora(self, estimulo: EstimuloRoteiro) -> QuadroPrevia:
        """Executa imediatamente ``estimulo`` no contexto atual e atualiza o quadro."""
        if self.modo != ModoPrevia.EM_CONTEXTO:
            self.definir_modo(ModoPrevia.EM_CONTEXTO)
        with dados_autorais.usar_rascunho(self.documento.rascunho):
            self._executar_estimulo(estimulo)
            quadro = self._avancar_passo_contexto(STEP_SIM_S, tempo_ant=self.tempo_s)
        self._ultimo_quadro = quadro
        return quadro

    def ir_para(self, tempo_s: float, *, forcar_reset: bool = False) -> QuadroPrevia:
        """Move determinísticamente para ``tempo_s`` com reset em busca reversa."""
        dur = self.duracao_s
        alvo = max(0.0, min(dur, float(tempo_s)))
        precisa_reset = forcar_reset or alvo < self._sim_tempo - 1e-6

        with dados_autorais.usar_rascunho(self.documento.rascunho):
            if precisa_reset:
                self._reiniciar_estado_interno()
                self._notificar_reset()
            quadro = self._simular_ate(alvo)
        self.tempo_s = alvo
        self._ultimo_quadro = quadro
        return quadro

    def avaliar_quadro_salvo(self) -> QuadroPrevia:
        """Avalia a mesma ação com ``documento.salvo`` para comparação visual."""
        sombra = SessaoPrevia(
            self.documento,
            semente=self.semente,
            provedor_musica=self.provedor_musica,
        )
        sombra.acao = self.acao
        sombra.variante = self.variante
        sombra.modo = self.modo
        sombra.roteiro = self.roteiro
        sombra.fps = self.fps
        with dados_autorais.usar_rascunho(self.documento.salvo):
            sombra._reiniciar_estado_interno()
            quadro = sombra._simular_ate(min(self.tempo_s, _duracao_acao(self.acao, self.documento.salvo)))
        return quadro

    def amostrar_trilha(
        self,
        model: Model,
        grupo: str,
        *,
        passos: int = 40,
    ) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
        """Amostra trajetória ``(pretendida, resolvida)`` de ``grupo`` na tomada."""
        n = max(4, int(passos))
        dur = self.duracao_s
        sombra = SessaoPrevia(
            self.documento,
            semente=self.semente,
            provedor_musica=self.provedor_musica,
        )
        sombra.acao = self.acao
        sombra.variante = self.variante
        sombra.modo = self.modo
        sombra.roteiro = self.roteiro
        sombra.fps = self.fps
        pretendida: list[tuple[float, float, float]] = []
        resolvida: list[tuple[float, float, float]] = []
        with dados_autorais.usar_rascunho(self.documento.rascunho):
            sombra._reiniciar_estado_interno()
            for i in range(n + 1):
                t = dur * (i / n)
                q = sombra._simular_ate(t)
                pretendida.append(posicao_no(model, grupo, q.pose_pretendida))
                resolvida.append(posicao_no(model, grupo, q.pose))
        return pretendida, resolvida

    def _reiniciar_estado_interno(self) -> None:
        self._sim_tempo = 0.0
        self._tempo_anterior_frame = -STEP_SIM_S
        self._janelas_disparadas.clear()
        self._estimulos_disparados.clear()
        self._drag_ativo = False
        self._obstaculo_dinamico = None

        self._rig = _novo_rig()
        self._controller = AnimationController(self._rig, transition_seconds=0.35)
        self._controller._personality_rng = random.Random(self.semente)
        self._controller._dance_rng = random.Random(self.semente + 17)
        self._dance_tomada = DanceMotion()
        self._leg_tomada = LegMotion()
        self._configurar_estado_inicial_controller()

    def _configurar_estado_inicial_controller(self) -> None:
        pers = _personalidade_segura(self.roteiro.personalidade)
        self._controller.idle_personality = pers
        self._controller.modo_sono = self.roteiro.modo_sono
        if self.acao is None or self.modo != ModoPrevia.EM_CONTEXTO:
            return
        secao = self.acao.secao_dados
        chave = self.acao.chave_dados
        if secao == "CENAS_IDLE":
            self._controller.interact(chave)
        elif secao == "IDLE_CLIPS":
            self._controller.set_idle_personality(_personalidade_segura(chave))
        elif secao == "RESPIRACAO" and chave.startswith("personalidades:"):
            self._controller.set_idle_personality(
                _personalidade_segura(_chave_segundo_segmento(chave))
            )
        elif secao == "DANCA":
            estilo = (
                _chave_segundo_segmento(chave)
                if ":" in chave
                else "street_groove"
            )
            self._controller.preview_dance(estilo)
        elif secao == "TENTACULOS":
            if chave.startswith("ondulacoes:"):
                self._controller.set_idle_personality(
                    _personalidade_segura(_chave_segundo_segmento(chave))
                )
            self._controller.appendage_remaining = max(5.5, self.duracao_s)
        elif secao == "REACOES":
            self._configurar_reacao_contexto(chave)
        elif secao == "CLIPES_GLTF":
            self._controller.tocar_clipe_gltf(chave)

    def _configurar_reacao_contexto(self, chave: str) -> None:
        mapa = {
            "aceno": "wave",
            "alongar": "stretch",
            "cutucar": "poke",
            "surpresa": "surprise",
            "teimosia": "teimosia",
        }
        if chave in mapa:
            self._controller.interact(mapa[chave])
        elif chave == "sono":
            self._controller.colocar_para_dormir(self.roteiro.modo_sono)
        elif chave.startswith("duracoes:"):
            kind = _chave_segundo_segmento(chave)
            if kind in ("click", "double_click", "pet", "hit", "land", "surprise", "wave", "stretch", "poke"):
                self._controller.interact(kind)

    def _simular_ate(self, tempo_alvo: float) -> QuadroPrevia:
        if tempo_alvo <= 1e-6:
            if self.modo == ModoPrevia.EM_CONTEXTO:
                return self._avancar_passo_contexto(0.0)
            return self._avaliar_tomada(0.0, -STEP_SIM_S)

        quadro = self._ultimo_quadro
        while self._sim_tempo < tempo_alvo - 1e-6:
            t_ant = self._sim_tempo
            proximo = min(tempo_alvo, self._sim_tempo + STEP_SIM_S)
            dt = proximo - t_ant
            self._sim_tempo = proximo
            if self.modo == ModoPrevia.EM_CONTEXTO:
                quadro = self._avancar_passo_contexto(dt, tempo_ant=t_ant)
            else:
                quadro = self._avaliar_tomada(proximo, t_ant)
        if self._sim_tempo <= 1e-6 and self.modo == ModoPrevia.TOMADA:
            quadro = self._avaliar_tomada(tempo_alvo, -STEP_SIM_S)
        return quadro

    def _despachar_estimulos(self, tempo_ant: float, tempo_atual: float) -> None:
        for idx, est in enumerate(self.roteiro.ordenados()):
            if idx in self._estimulos_disparados:
                continue
            if tempo_ant <= est.tempo_s <= tempo_atual + 1e-6:
                self._estimulos_disparados.add(idx)
                self._executar_estimulo(est)

    def _executar_estimulo(self, est: EstimuloRoteiro) -> None:
        if est.tipo == "drag_inicio":
            self._drag_ativo = True
            self._controller.interact("drag_start")
        elif est.tipo == "drag_fim":
            self._drag_ativo = False
        elif est.tipo == "obstaculo":
            self._obstaculo_dinamico = ObstaculoPrevia(
                ativo=bool(est.dados.get("ativo", True)),
                centro=tuple(est.dados.get("centro", self.roteiro.obstaculo.centro)),
                meia_extensao=tuple(
                    est.dados.get("meia_extensao", self.roteiro.obstaculo.meia_extensao)
                ),
            )
        elif est.tipo == "porta":
            self._controller.appendage_remaining = max(
                self._controller.appendage_remaining, float(est.intensidade * 5.0)
            )
        elif est.tipo in (
            "click",
            "double_click",
            "hover",
            "pet",
            "poke",
            "surprise",
            "hit",
            "land",
            "sneeze",
            "teimosia",
        ) or est.tipo == "cena":
            kind = (
                str(est.dados.get("nome") or est.alvo or est.tipo)
                if est.tipo == "cena"
                else est.tipo
            )
            self._controller.interact(
                kind,
                direction=est.direcao,
                strength=est.intensidade,
                part=est.alvo or "body",
            )

    def _obstaculo_efetivo(self) -> ObstaculoPrevia:
        return self._obstaculo_dinamico or self.roteiro.obstaculo

    def _coletar_vfx_e_tentaculos_contexto(
        self, tempo_atual: float
    ) -> tuple[
        list[EventoVfxPrevia],
        list[str],
        AmostraCenaIdle,
        bool,
        float,
        tuple[tuple[tuple[float, float, float], ...], ...],
        tuple[tuple[float, float, float], ...],
    ]:
        eventos_vfx = list(self._coletar_vfx_passivo(tempo_atual))
        amostra_cena = self._controller.cena_idle_amostra
        janelas_ativas: list[str] = []
        if amostra_cena.ativa:
            janelas_ativas = self._janelas_cena_ativas(
                amostra_cena.nome, self._controller._cena_idle_tempo
            )
            for cond, fx_nome in (
                (amostra_cena.estouro_fone, "estouro_fone"),
                (amostra_cena.choque_argolas, "choque_argolas"),
            ):
                if cond and fx_nome not in self._janelas_disparadas:
                    self._janelas_disparadas.add(fx_nome)
                    eventos_vfx.append(
                        EventoVfxPrevia(fx_nome, tempo_atual, "contexto")
                    )

        tent_ativos = self._controller.appendage_remaining > 0.0
        if tent_ativos:
            porta, pts, contatos = _amostrar_tentaculos_puros(
                tempo_atual,
                self.duracao_s,
                self.roteiro.personalidade,
                self._obstaculo_efetivo(),
            )
        else:
            porta, pts, contatos = 0.0, (), ()
        return (
            eventos_vfx,
            janelas_ativas,
            amostra_cena,
            tent_ativos,
            porta,
            pts,
            contatos,
        )

    def _avancar_passo_contexto(
        self, dt: float, *, tempo_ant: float = -STEP_SIM_S
    ) -> QuadroPrevia:
        tempo_atual = self._sim_tempo
        if tempo_atual > 0.0:
            self._despachar_estimulos(tempo_ant, tempo_atual)
        hovered = any(
            e.tipo == "hover" and abs(tempo_atual - e.tempo_s) <= 0.45
            for e in self.roteiro.estimulos
        )
        vel = self._velocidade_contexto()
        playing, intensity, bass, bpm, fase_batida, bateu = _ritmo_no_instante(
            tempo_atual, tempo_ant, self.roteiro, self.provedor_musica
        )
        force_dance = self.acao is not None and self.acao.secao_dados == "DANCA"
        pose_resolvida = self._controller.update(
            dt,
            velocity=vel,
            grounded=not self._drag_ativo,
            gravity_active=self.acao is not None
            and self.acao.secao_dados in ("LOCOMOCAO_CLIPS",),
            dragging=self._drag_ativo,
            music_playing=playing
            and (
                force_dance
                or self.roteiro.metronomo_ativo
                or self.roteiro.usar_musica_ao_vivo
            ),
            music_intensity=intensity,
            music_bass=bass,
            music_bpm=bpm,
            beat_detected=bateu,
            beat_phase=fase_batida,
            hovered=hovered,
        )
        acao_id = self.acao.id if self.acao else ""
        pose_pretendida, prov_ativa = _aplicar_provisoria(
            dict(self._controller._pose), self.documento, acao_id
        )
        if prov_ativa:
            pose_resolvida, _ = _aplicar_provisoria(
                pose_resolvida, self.documento, acao_id
            )

        (
            eventos_vfx,
            janelas_ativas,
            amostra_cena,
            tent_ativos,
            porta,
            pts,
            contatos,
        ) = self._coletar_vfx_e_tentaculos_contexto(tempo_atual)
        estado_ctrl = (
            self._controller.state.value
            if self._controller.state is not None
            else "idle"
        )
        reac = self._controller._reaction.value if self._controller._reaction else None
        prio = (
            "arraste (prioridade física)"
            if self._drag_ativo
            else (f"reação:{reac}" if reac else f"estado:{estado_ctrl}")
        )
        return QuadroPrevia(
            tempo_s=tempo_atual,
            duracao_s=self.duracao_s,
            quadro_indice=round(tempo_atual * self.fps),
            fps=self.fps,
            modo=self.modo,
            acao_id=acao_id,
            variante=self.variante,
            pose=pose_resolvida,
            pose_pretendida=pose_pretendida,
            pernas=self._controller.leg_motion.pose,
            raiz_quat=self._controller.raiz_quat_ativa,
            dedos_clipe=self._controller.dedos_clipe_ativo,
            tentaculos_ativos=tent_ativos,
            tentaculo_temperamento=self.roteiro.personalidade,
            tentaculos_porta_aberta=porta,
            pontos_tentaculos=pts,
            contatos_obstaculo=contatos,
            eventos_vfx=tuple(eventos_vfx),
            janelas_vfx_ativas=tuple(janelas_ativas),
            eventos_gltf=self._controller.clipe_gltf_eventos,
            estado_contexto=estado_ctrl,
            reacao_contexto=reac,
            prioridade_contexto=prio,
            respiracao_valor=float(self._controller.respiracao_valor),
            batida_ativa=bateu,
            fase_batida=fase_batida,
            bpm_efetivo=bpm,
            amostra_cena=amostra_cena if amostra_cena.ativa else None,
            provisoria_ativa=prov_ativa,
        )

    def _velocidade_contexto(self) -> tuple[float, float]:
        if self.acao is None:
            return (0.0, 0.0)
        if self.acao.secao_dados == "LOCOMOCAO_CLIPS":
            return (220.0 if self.acao.chave_dados == "run" else 125.0, 0.0)
        if self.acao.secao_dados == "REACOES" and self.acao.chave_dados == "pernas":
            return (125.0, 0.0)
        return (0.0, 0.0)

    def _coletar_vfx_passivo(self, tempo_atual: float) -> tuple[EventoVfxPrevia, ...]:
        if self.acao is None or self.acao.secao_dados != "VFX":
            return ()
        onset = 0.15
        if tempo_atual >= onset and self.acao.chave_dados not in self._janelas_disparadas:
            self._janelas_disparadas.add(self.acao.chave_dados)
            vfx_cfg = self.documento.rascunho.get("VFX", {}).get(self.acao.chave_dados, {})
            return (
                EventoVfxPrevia(
                    nome=self.acao.chave_dados,
                    tempo_s=tempo_atual,
                    origem="vfx_direto",
                    dados=dict(vfx_cfg),
                ),
            )
        return ()

    def _janelas_cena_ativas(self, nome_cena: str, tempo_cena: float) -> list[str]:
        cfg = self.documento.rascunho.get("CENAS_IDLE", {}).get(nome_cena, {})
        janelas = cfg.get("janelas_efeito", {})
        ativas: list[str] = []
        for eff_nome, faixa in janelas.items():
            if len(faixa) == 2 and float(faixa[0]) <= tempo_cena <= float(faixa[1]):
                ativas.append(eff_nome)
        return ativas

    def _avaliar_tomada(self, tempo_s: float, tempo_ant: float) -> QuadroPrevia:
        acao = self.acao
        if acao is None:
            return QuadroPrevia(tempo_s=tempo_s, fps=self.fps)

        base = pose_repouso()
        handler = {
            "CENAS_IDLE": self._tomada_cena_idle,
            "IDLE_CLIPS": self._tomada_idle_clip,
            "LOCOMOCAO_CLIPS": self._tomada_locomocao,
            "RESPIRACAO": self._tomada_respiracao,
            "DANCA": self._tomada_danca,
            "TENTACULOS": self._tomada_tentaculos,
            "REACOES": self._tomada_reacao,
            "VFX": self._tomada_vfx,
            "CLIPES_GLTF": self._tomada_gltf,
        }.get(acao.secao_dados)

        quadro = (
            handler(tempo_s, tempo_ant)
            if handler is not None
            else QuadroPrevia(tempo_s=tempo_s, duracao_s=self.duracao_s, fps=self.fps)
        )
        pose_prov, prov_ativa = _aplicar_provisoria(
            quadro.pose, self.documento, acao.id
        )
        pose_final = _aplicar_mascaras_pistas(
            pose_prov, base, self.pista_solo, self.pistas_silenciadas
        )
        pernas_final = compor_pose_pernas(quadro.pernas, pose_final, repouso=base)
        return QuadroPrevia(
            tempo_s=tempo_s,
            duracao_s=self.duracao_s,
            quadro_indice=round(tempo_s * self.fps),
            fps=self.fps,
            modo=ModoPrevia.TOMADA,
            acao_id=acao.id,
            variante=self.variante,
            pose=pose_final,
            pose_pretendida=quadro.pose_pretendida,
            pernas=pernas_final,
            raiz_quat=quadro.raiz_quat,
            dedos_clipe=quadro.dedos_clipe,
            deslocamento_corpo=quadro.deslocamento_corpo,
            orientacao_graus=quadro.orientacao_graus,
            escala=quadro.escala,
            dissolve=quadro.dissolve,
            tentaculos_ativos=quadro.tentaculos_ativos,
            tentaculo_temperamento=quadro.tentaculo_temperamento,
            tentaculos_porta_aberta=quadro.tentaculos_porta_aberta,
            pontos_tentaculos=quadro.pontos_tentaculos,
            contatos_obstaculo=quadro.contatos_obstaculo,
            eventos_vfx=quadro.eventos_vfx,
            janelas_vfx_ativas=quadro.janelas_vfx_ativas,
            eventos_gltf=quadro.eventos_gltf,
            estado_contexto="tomada",
            prioridade_contexto="isolada",
            respiracao_valor=quadro.respiracao_valor,
            batida_ativa=quadro.batida_ativa,
            fase_batida=quadro.fase_batida,
            bpm_efetivo=quadro.bpm_efetivo,
            amostra_cena=quadro.amostra_cena,
            provisoria_ativa=prov_ativa,
        )

    def _tomada_cena_idle(self, tempo_s: float, _tempo_ant: float) -> QuadroPrevia:
        assert self.acao is not None
        chave = self.acao.chave_dados
        cfg = self.documento.rascunho.get("CENAS_IDLE", {}).get(chave, {})
        var_idx = (
            self.acao.variantes.index(self.variante)
            if self.variante in self.acao.variantes
            else 0
        )
        amostra = amostrar_cena_idle(chave, tempo_s, variante=var_idx)
        pose = pose_repouso()
        for grupo, delta in amostra.delta_rig.items():
            if grupo in pose:
                pose[grupo] = _somar_rot(pose[grupo], delta)
        pernas = (
            LegPose(
                left=amostra.pernas_graus[0],
                right=amostra.pernas_graus[1],
                left_knee=amostra.pernas_graus[2],
                right_knee=amostra.pernas_graus[3],
                left_yaw=amostra.pernas_graus[4],
                right_yaw=amostra.pernas_graus[5],
            )
            if amostra.pernas_graus is not None
            else None
        )
        desl = _extrair_pos_raiz(tuple(cfg.get("deslocamento_corpo", (0.0, 0.0, 0.0))))
        desl_z = desl[2] + amostra.deslocamento_z
        janelas = self._janelas_cena_ativas(chave, tempo_s)
        ev_vfx: list[EventoVfxPrevia] = []
        for eff_nome in janelas:
            if eff_nome not in self._janelas_disparadas:
                self._janelas_disparadas.add(eff_nome)
                ev_vfx.append(EventoVfxPrevia(eff_nome, tempo_s, "cena"))
        return QuadroPrevia(
            pose=pose,
            pose_pretendida=dict(pose),
            pernas=pernas,
            deslocamento_corpo=(desl[0], desl[1], desl_z),
            janelas_vfx_ativas=tuple(janelas),
            eventos_vfx=tuple(ev_vfx),
            amostra_cena=amostra,
        )

    def _tomada_idle_clip(self, tempo_s: float, _tempo_ant: float) -> QuadroPrevia:
        assert self.acao is not None
        chave = self.acao.chave_dados
        var_nome = self.variante if self.variante else None
        resp_val = amostrar_respiracao_repouso(tempo_s)
        amp = parametros_de(_personalidade_segura(chave)).amplitude
        angulos = sample_idle(
            chave, tempo_s, resp_val, amp, variante=var_nome
        )
        pose = _pose_de_graus_sobre_repouso(angulos, base_absoluta=True)
        desl = deslocamento_idle_ativo(chave)
        return QuadroPrevia(
            pose=pose,
            pose_pretendida=dict(pose),
            deslocamento_corpo=(desl[0], desl[1], desl[2]),
            respiracao_valor=float(resp_val),
        )

    def _tomada_locomocao(self, tempo_s: float, _tempo_ant: float) -> QuadroPrevia:
        assert self.acao is not None
        chave = self.acao.chave_dados
        u = tempo_s / max(0.2, self.duracao_s)
        deltas = amostrar_clipe(chave, u)
        pose = _pose_de_graus_sobre_repouso(deltas, base_absoluta=False)
        vel = (220.0 if chave == "run" else 125.0, 0.0)
        self._leg_tomada.update(
            STEP_SIM_S, chave, vel, tempo_s, 0.0, pixels_per_unit=216.8
        )
        return QuadroPrevia(
            pose=pose,
            pose_pretendida=dict(pose),
            pernas=self._leg_tomada.pose,
        )

    def _tomada_respiracao(self, tempo_s: float, _tempo_ant: float) -> QuadroPrevia:
        assert self.acao is not None
        pers = (
            _chave_segundo_segmento(self.acao.chave_dados)
            if ":" in self.acao.chave_dados
            else self.roteiro.personalidade
        )
        ciclo = amostrar_respiracao_repouso(tempo_s)
        amp = parametros_de(_personalidade_segura(pers)).amplitude
        deltas = camada_respiracao(ciclo, amp, estilo=pers)
        pose = _pose_de_graus_sobre_repouso(deltas, base_absoluta=False)
        return QuadroPrevia(
            pose=pose,
            pose_pretendida=dict(pose),
            respiracao_valor=float(ciclo),
        )

    def _tomada_danca(self, tempo_s: float, tempo_ant: float) -> QuadroPrevia:
        assert self.acao is not None
        estilo = (
            _chave_segundo_segmento(self.acao.chave_dados)
            if ":" in self.acao.chave_dados
            else "street_groove"
        )
        self._dance_tomada.style = estilo
        self._dance_tomada.override = estilo
        playing, intensity, bass, bpm, fase, bateu = _ritmo_no_instante(
            tempo_s, tempo_ant, self.roteiro, self.provedor_musica
        )
        if not playing:
            bpm = float(self.roteiro.bpm or 108.0)
        self._dance_tomada.update(
            STEP_SIM_S if tempo_s > 0.0 else 0.0,
            intensity,
            bass,
            bpm,
            bateu,
            beat_phase=fase,
        )
        rig_tmp = _novo_rig()
        contrib = self._dance_tomada.contribuicao(rig_tmp)
        pose = pose_repouso()
        for grupo, rot in contrib.items():
            if grupo in pose:
                pose[grupo] = rot
        self._leg_tomada.update(
            STEP_SIM_S if tempo_s > 0.0 else 0.0,
            "dance",
            (0.0, 0.0),
            tempo_s,
            0.0,
            dance_phase=self._dance_tomada.phase,
            dance_strength=self._dance_tomada.strength,
            dance_style=estilo,
            dance_time=self._dance_tomada.tempo_clipe,
        )
        clipe_e = carregar_clipe_emote(estilo)
        raiz_q = self._dance_tomada.raiz_quat_emote if clipe_e is not None else None
        return QuadroPrevia(
            pose=pose,
            pose_pretendida=dict(pose),
            pernas=self._leg_tomada.pose,
            raiz_quat=raiz_q,
            dedos_clipe=self._dance_tomada.dedos_clipe,
            batida_ativa=bateu,
            fase_batida=fase,
            bpm_efetivo=bpm,
        )

    def _tomada_tentaculos(self, tempo_s: float, _tempo_ant: float) -> QuadroPrevia:
        assert self.acao is not None
        pers = (
            _chave_segundo_segmento(self.acao.chave_dados)
            if self.acao.chave_dados.startswith("ondulacoes:")
            else self.roteiro.personalidade
        )
        angulo_porta, pts, contatos = _amostrar_tentaculos_puros(
            tempo_s, self.duracao_s, pers, self._obstaculo_efetivo()
        )
        rig_tmp = _novo_rig()
        pose_idle(rig_tmp, tempo_s, _personalidade_segura(pers))
        rig_tmp.set_rotation("door", y=angulo_porta)
        pose = rig_tmp.pose()
        ev: tuple[EventoVfxPrevia, ...] = ()
        if self.acao.chave_dados == "gotas" and tempo_s >= 0.45 and "gosma" not in self._janelas_disparadas:
            self._janelas_disparadas.add("gosma")
            ev = (EventoVfxPrevia("gosma", tempo_s, "tentaculos"),)
        return QuadroPrevia(
            pose=pose,
            pose_pretendida=dict(pose),
            tentaculos_ativos=True,
            tentaculo_temperamento=pers,
            tentaculos_porta_aberta=angulo_porta,
            pontos_tentaculos=pts,
            contatos_obstaculo=contatos,
            eventos_vfx=ev,
        )

    def _tomada_transicao(self, chave: str, tempo_s: float) -> QuadroPrevia:
        rig_tmp = _novo_rig()
        pose_idle(rig_tmp, tempo_s, IdlePersonality.CALM)
        estilo = _chave_segundo_segmento(chave)
        if chave.startswith("entradas:"):
            fr_in = IntroAnimation(estilo, from_side=1).sample(tempo_s)
            return QuadroPrevia(
                pose=rig_tmp.pose(),
                pose_pretendida=rig_tmp.pose(),
                deslocamento_corpo=(fr_in.offset_x / 216.8, fr_in.offset_y / 216.8, 0.0),
                orientacao_graus=(fr_in.pitch, fr_in.yaw, fr_in.roll),
                escala=fr_in.scale,
                dissolve=fr_in.dissolve,
            )
        fr_out = ExitAnimation((400, 400), 260, (0, 0, 1280, 720), style=estilo).sample(tempo_s)
        return QuadroPrevia(
            pose=rig_tmp.pose(),
            pose_pretendida=rig_tmp.pose(),
            deslocamento_corpo=((fr_out.x - 400) / 216.8, (fr_out.y - 400) / 216.8, 0.0),
            orientacao_graus=(fr_out.pitch, fr_out.yaw, fr_out.roll),
            escala=fr_out.scale,
            dissolve=fr_out.dissolve,
        )

    def _tomada_reacao(self, tempo_s: float, _tempo_ant: float) -> QuadroPrevia:
        assert self.acao is not None
        chave = self.acao.chave_dados
        if chave.startswith(("entradas:", "saidas:")):
            return self._tomada_transicao(chave, tempo_s)
        rig_tmp = _novo_rig()
        rig_tmp.current = pose_repouso()
        if chave in ("aceno", "alongar"):
            pose_flourish(rig_tmp, "wave" if chave == "aceno" else "stretch", tempo_s)
            return QuadroPrevia(pose=rig_tmp.pose(), pose_pretendida=rig_tmp.pose())
        if chave in ("cutucar", "surpresa"):
            pose_interaction(rig_tmp, "poke" if chave == "cutucar" else "surprise", tempo_s)
            return QuadroPrevia(pose=rig_tmp.pose(), pose_pretendida=rig_tmp.pose())
        if chave == "teimosia":
            aplicar_pose_teimosia(rig_tmp, tempo_s, 0.0)
            return QuadroPrevia(pose=rig_tmp.pose(), pose_pretendida=rig_tmp.pose())
        if chave == "sono":
            pose_sleep(rig_tmp, tempo_s, modo=self.roteiro.modo_sono, entrada=min(3.0, tempo_s))
            self._leg_tomada.update(
                STEP_SIM_S, "sleep", (0.0, 0.0), tempo_s, 0.0, modo_sono=self.roteiro.modo_sono
            )
            return QuadroPrevia(
                pose=rig_tmp.pose(), pose_pretendida=rig_tmp.pose(), pernas=self._leg_tomada.pose
            )
        if chave == "pernas":
            pose_walk(rig_tmp, tempo_s, run=False)
            self._leg_tomada.update(STEP_SIM_S, "walk", (125.0, 0.0), tempo_s, 0.0)
            return QuadroPrevia(
                pose=rig_tmp.pose(), pose_pretendida=rig_tmp.pose(), pernas=self._leg_tomada.pose
            )
        kind = _chave_segundo_segmento(chave) if chave.startswith("duracoes:") else "click"
        pose_interaction(rig_tmp, kind, tempo_s)
        pose_secondary(rig_tmp, tempo_s, kind, IdlePersonality.CALM)
        return QuadroPrevia(pose=rig_tmp.pose(), pose_pretendida=rig_tmp.pose())

    def _tomada_vfx(self, tempo_s: float, _tempo_ant: float) -> QuadroPrevia:
        assert self.acao is not None
        chave = self.acao.chave_dados
        vfx_cfg = self.documento.rascunho.get("VFX", {}).get(chave, {})
        dur_fx = max(0.2, float(vfx_cfg.get("duracao_s", 0.5)))
        rig_tmp = _novo_rig()
        pose_idle(rig_tmp, tempo_s, IdlePersonality.CALM)
        pose = rig_tmp.pose()
        ev = self._coletar_vfx_passivo(tempo_s)
        ativas = (chave,) if 0.15 <= tempo_s <= 0.15 + dur_fx else ()
        return QuadroPrevia(
            pose=pose,
            pose_pretendida=dict(pose),
            eventos_vfx=ev,
            janelas_vfx_ativas=ativas,
        )

    def _tomada_gltf(self, tempo_s: float, tempo_ant: float) -> QuadroPrevia:
        assert self.acao is not None
        amostra: AmostraClipeGltf = amostrar_clipe_gltf(
            self.acao.chave_dados, tempo_s, tempo_anterior=tempo_ant
        )
        pose = pose_repouso()
        for grupo, delta in amostra.delta_rig.items():
            if grupo in pose:
                pose[grupo] = _somar_rot(pose[grupo], delta)
        return QuadroPrevia(
            pose=pose,
            pose_pretendida=dict(pose),
            eventos_gltf=amostra.eventos,
        )

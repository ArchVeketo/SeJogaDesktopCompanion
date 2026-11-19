"""Controlador procedural de animação do mascote.

As poses são produzidas pelo rig sem depender de clipes exportados. O
controlador escolhe um estado a partir da interação/física e faz crossfade
entre poses para evitar saltos bruscos.
"""

from __future__ import annotations

import random
from enum import StrEnum
from math import degrees, radians
from typing import ClassVar

from sejoga.animacao import movimento_corpo_tuning as tune
from sejoga.animacao.agencia import Agencia, Humor, MetaTipo
from sejoga.animacao.braco_hpr import braco_hpr_graus
from sejoga.animacao.camadas_animacao import (
    MASCARA_MUSICA,
    CamadaAnim,
    CamadaDelta,
    LayerStack,
    MixerCamadas,
    Prioridade,
)
from sejoga.animacao.cenas_idle import (
    DURACOES_CENAS,
    AmostraCenaIdle,
    amostrar_cena_idle,
    duracoes_cenas_ativas,
)
from sejoga.animacao.clipes_gltf import (
    AmostraClipeGltf,
    amostrar_clipe_gltf,
    carregar_clipe_gltf,
)
from sejoga.animacao.danca_clipes import (
    amostrar_clipe_completo,
    carregar_clipe_acao,
    carregar_clipe_emote,
    listar_clipes_emote,
)
from sejoga.animacao.estados_delta import (
    delta_drag,
    delta_fall,
    delta_fisica,
    delta_hover,
    delta_idle,
    delta_secundario,
    delta_sleep,
    delta_soltura,
    delta_walk,
    misturar_deltas_seletivo,
    somar_deltas,
)
from sejoga.animacao.gestos_reacao import aplicar_defesa
from sejoga.animacao.gestos_tuning import (
    ACENO_DURACAO_S,
    ALONGAR_DURACAO_S,
    CUTUCAR_DURACAO_S,
    duracoes_reacoes,
)
from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.molas_juntas import (
    CADEIA_COLUNA,
    CADEIA_DIREITA,
    CADEIA_ESQUERDA,
    CADEIA_FONE_DIREITO,
    CADEIA_FONE_ESQUERDO,
    LagChain,
)
from sejoga.animacao.movimento_corpo import BodyMotion
from sejoga.animacao.movimento_danca import DanceMotion
from sejoga.animacao.movimento_maos import HandMotion
from sejoga.animacao.movimento_pernas import LegMotion
from sejoga.animacao.pacotes_animacao import (
    ANGULO_POR_ORIENTACAO,
    AgendadorPacotes,
    EstadoProfundidade,
    ItemPacote,
    NivelProfundidade,
    OrientacaoCorpo,
    PacoteOlharTela,
)
from sejoga.animacao.pose_repouso import REPOUSO
from sejoga.animacao.poses_base import (
    pose_blue_balls,
    pose_flourish,
    pose_idle,
    pose_interaction,
    pose_secondary,
    pose_sneeze,
    pose_throw_release,
    pose_virtual_insanity,
)
from sejoga.animacao.resolvedor_poses import PoseResolver
from sejoga.animacao.respiracao import Respiracao, amostrar_respiracao_repouso
from sejoga.animacao.sono_tuning import SONO_TRANSICAO_S
from sejoga.animacao.teimosia_pose import (
    aplicar_fase as aplicar_pose_teimosia,
)
from sejoga.animacao.teimosia_pose import (
    fase_do_tempo as fase_teimosia_do_tempo,
)
from sejoga.nucleo.esqueleto import IdlePersonality, Rig, Rotation3
from sejoga.nucleo.modelo import Model

_GESTOS_MAO_DIREITA: dict[str, tuple[tuple[float, float, float], float]] = {
    "rock": ((76.0, -24.0, 14.0), 62.0),
    "hang_loose": ((78.0, -22.0, 16.0), 48.0),
    "peace": ((74.0, -24.0, 14.0), 58.0),
    "thumbs_up": ((56.0, -28.0, 14.0), 56.0),
    "finger_gun": ((36.0, -32.0, 18.0), 48.0),
    "point": ((44.0, -32.0, 14.0), 48.0),
}

#: Braço no arraste: o z=62 original era REPOUSO.BRACO_Z - 6 (afasta um pouco).
_ARRASTE_BRACO_Z = REPOUSO.BRACO_Z - 6
#: Braço na pega pelo corpo: o z=65 original era REPOUSO.BRACO_Z - 3 (mais solto).
_PEGA_CORPO_BRACO_Z = REPOUSO.BRACO_Z - 3


class AnimationState(StrEnum):
    """Estados de animação; o valor é o nome usado nas poses e nas reações."""

    IDLE = "idle"
    WALK = "walk"
    RUN = "run"
    DRAG = "drag"
    FALL = "fall"
    DANCE = "dance"
    SLEEP = "sleep"
    HOVER = "hover"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    PET = "pet"
    POKE = "poke"
    WAKE = "wake"
    LAND = "land"
    CELEBRATE = "celebrate"
    WAVE = "wave"
    STRETCH = "stretch"
    PEEK = "peek"
    HIT = "hit"
    SNEEZE = "sneeze"
    HANG_LOOSE = "hang_loose"
    THUMBS_UP = "thumbs_up"
    ROCK = "rock"
    FINGER_GUN = "finger_gun"
    PEACE = "peace"
    POINT = "point"
    OPEN_HANDS = "open_hands"
    CLOSE_FISTS = "close_fists"
    BLUE_BALLS = "blue_balls"
    VIRTUAL_INSANITY = "virtual_insanity"
    SURPRISE = "surprise"
    # Teimosia: manifesto §1.4 — resistência → repreensão → bote → roubo do mouse
    TEIMOSIA = "teimosia"


#: Estados totalmente migrados para composição aditiva via ``LayerStack``.
_ESTADOS_MIGRADOS = frozenset(
    {
        AnimationState.IDLE,
        AnimationState.HOVER,
        AnimationState.WALK,
        AnimationState.RUN,
        AnimationState.DRAG,
        AnimationState.FALL,
        AnimationState.SLEEP,
    }
)


class AnimationController:
    """Gera poses a cada frame e interpola mudanças de estado."""

    def __init__(  # noqa: PLR0915  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
        self,
        rig: Rig,
        transition_seconds: float = 0.55,
        model: Model | None = None,
    ) -> None:
        """Monta o controlador com a pose idle composta como ponto de partida."""
        self.rig = rig
        self.transition_seconds = max(0.0, transition_seconds)
        self._active_transition_seconds = self.transition_seconds
        self.state: AnimationState | None = None
        self.state_time = 0.0
        self._estado_origem = ""
        self.idle_time = 0.0
        self._idle_clock = 0.0
        self.clock = 0.0
        self.idle_personality = IdlePersonality.CALM
        self.respiracao = Respiracao(frequencia=0.0)
        self._peso_repouso = 0.0
        self.respiracao_valor = 0.0
        self._personality_rng = random.Random()
        # Start in a composed idle pose. Starting every joint at zero exposes
        # the asset's T-pose during the first state crossfade.
        rig.reset()
        pose_idle(rig, 0.0, self.idle_personality)
        pose_secondary(rig, 0.0, AnimationState.IDLE.value, self.idle_personality)
        self._pose = rig.pose()
        rig.reset()
        self._reaction: AnimationState | None = None
        self._reaction_time = 0.0
        self._reaction_direction = 1.0
        self._reaction_part = "body"
        self._gesto_mao_esquerda: str | None = None
        self._pending_intent: tuple[str, float | None, float] | None = None
        self._pending_intent_part: str | None = None
        self._cooldowns: dict[str, float] = {}
        self._look_direction = 0.0
        self._look_vertical = 0.0
        self._idle_torso_look_dir = 0.0
        self._idle_torso_look_vert = 0.0
        self._hover_enter_timer = 0.0
        self._hover_exit_timer = 0.0
        self.appendage_remaining = 0.0
        self._cursor_anterior: tuple[float, float] | None = None
        self._quietude = 0.0
        self.modo_sono: str = "em_pe"
        self._fila_modos_sono: list[str] = []
        self._ultimo_sono_auto: str | None = None
        self._sleep_locked: bool = False
        self._last_velocity: tuple[float, float] = (0.0, 0.0)
        self._dance_remaining = 0.0
        self._music_grace = 0.0
        self._dance_decision_in = 0.0
        self._previous_beat = False
        self._dance_rng = random.Random()
        self.drag_intensity = 0.0
        self._release_time = 1.0
        self._release_grip = 0.0
        self._was_grounded: bool | None = None
        self._peak_fall_vy: float = 0.0
        self.body_motion = BodyMotion()
        self.leg_motion = LegMotion()
        self.hand_motion = HandMotion()
        self.dance_motion = DanceMotion()
        self._dance_preview_remaining = 0.0
        self._dance_preview_style = "head_bob"
        self._cena_idle_nome = ""
        self._cena_idle_tempo = 0.0
        self._cena_idle_variante = 0
        self.cena_idle_amostra = AmostraCenaIdle()
        self._clipe_gltf_nome = ""
        self._clipe_gltf_tempo = 0.0
        self.clipe_gltf_amostra = AmostraClipeGltf()
        self.clipe_gltf_eventos: tuple[str, ...] = ()
        # Camada 'interacao': atraso efetivo da cadeia dos braços (braço ->
        # antebraço -> mão -> dedos). Cada cadeia persegue o alvo autoral com
        # molas, e a diferença (saída - alvo) vira um follow-through aditivo
        # somado sobre o follow-through das mãos (hand_motion).
        self.cadeia_direita = LagChain(CADEIA_DIREITA)
        self.cadeia_esquerda = LagChain(CADEIA_ESQUERDA)
        self.cadeia_fone_direito = LagChain(CADEIA_FONE_DIREITO)
        self.cadeia_fone_esquerdo = LagChain(CADEIA_FONE_ESQUERDO)
        self.cadeia_coluna = LagChain(CADEIA_COLUNA)
        for _c in (
            self.cadeia_direita,
            self.cadeia_esquerda,
            self.cadeia_fone_direito,
            self.cadeia_fone_esquerdo,
            self.cadeia_coluna,
        ):
            _c.definir(dict(self._pose))
        self._collision_model = model
        self.pose_resolver = PoseResolver()
        self.pose_resolver.iniciar_transicao(
            dict(self._pose), transition_seconds=self.transition_seconds
        )
        # LayerStack para composição aditiva de deltas (Fase 3).
        self.layer_stack = LayerStack()
        # Pacotes de animação, profundidade visual e orientação manual (Fases 3-4).
        self.profundidade = EstadoProfundidade()
        self.pacote_olhar_tela = PacoteOlharTela()
        self.agendador_pacotes = AgendadorPacotes(
            (
                ItemPacote("olhar_tela", peso=0.75, resfriamento_s=180.0),
                ItemPacote("caminhar_fundo", peso=0.45, resfriamento_s=210.0),
            ),
            intervalo_base_s=95.0,
        )
        self._curiosidade_fundo_restante: float = 0.0
        self.orientacao_manual: OrientacaoCorpo | None = None
        self.angulo_giro_pedido: float | None = None
        self.permitir_giro_costas: bool = False
        self._fonte_atencao: str | None = None

        # ── Sistema de agência (manifesto §4.1 — Camada 1) ──────────────
        self.agencia = Agencia()
        self._teimosia_fase: str = "resistencia"  # resistencia → repreensao → bote → roubo → cospe
        self._teimosia_tempo = 0.0
        self._cursor_oculto = False  # Track if we hid the cursor via Win32
        self._acao_clipe_nome: str | None = None
        self.acao_clipe_tempo: float = 0.0
        self.raiz_quat_acao: tuple[float, float, float, float] | None = None
        self.dz_clipe_ativo: float = 0.0
        self.dedos_clipe_acao: tuple[tuple[float, ...], tuple[float, ...]] | None = None
        self._canais_pernas_acao: dict[str, float] | None = None
        self._defesa_firmeza = 0.0
        self._peso_tatil = 0.0
        self._peso_indignacao = 0.0
        self._peso_colisao = 1.0
        self._land_heavy = False
        self._indice_cena_musica = 0
        self._indice_cena_cursor = 0
        self._indice_pos_atividade = 0
        self._tempo_musica_discreta = 0.0
        self._hover_sem_clique_tempo = 0.0
        self._passou_perto_restante = 0.0
        self._atividade_previa = ""
        self._tempo_atividade_previa = 0.0
        self._pos_atividade_pendente = ""
        self._tempo_assentado_idle = 0.0
        self._fonte_atencao_anterior: str | None = None
        self._pensamento_janela_restante = 0.0

    @property
    def acao_clipe_ativa(self) -> str | None:
        """Nome do clipe Mixamo de ação/locomoção em reprodução no frame."""
        return self._acao_clipe_nome

    @property
    def raiz_quat_ativa(self) -> tuple[float, float, float, float] | None:
        """Quaternion 3D da raiz ativa (dança emote ou clipe de ação, ex.: nado)."""
        if self.state == AnimationState.DANCE:
            return getattr(self.dance_motion, "raiz_quat_emote", None)
        return self.raiz_quat_acao

    @property
    def dedos_clipe_ativo(
        self,
    ) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
        """Flexão individual dos 5 dedos vinda de dança emote, clipe ou cena idle."""
        if self.state == AnimationState.DANCE:
            return getattr(self.dance_motion, "dedos_clipe", None)
        if self.cena_idle_amostra.ativa and self.cena_idle_amostra.dedos is not None:
            return self.cena_idle_amostra.dedos
        return self.dedos_clipe_acao

    @property
    def gesto_mao_esquerda(self) -> str | None:
        """Gesto opcional ativo para a mão esquerda durante reação."""
        return self._gesto_mao_esquerda if self._reaction is not None else None

    def _especificacao_clipe_walk(
        self, vx: float, humor: Humor, irritado: bool
    ) -> tuple[str, bool, float, float, str, bool, bool]:
        """Escolhe a passada pela intenção de movimento e pelo ritmo."""
        avx = abs(vx)
        meta = self.agencia.meta_ativa
        if avx <= 40.0:
            return ("walk_standard", False, 1.0, 0.0, "viagem", False, False)
        if avx < 88.0 and humor in (Humor.CURIOSO, Humor.DESCONFIADO):
            rate = max(0.75, min(1.30, avx / 72.0))
            return ("walk_strafe_slow", vx < 0.0, rate, 0.0, "raiz", False, False)
        if (
            avx < 168.0
            and not irritado
            and meta is not None
            and meta.tipo == MetaTipo.PROCURAR_ATENCAO
        ):
            nome = "walk_strafe_left" if vx > 0.0 else "walk_strafe_right"
            return (nome, False, max(0.85, min(1.35, avx / 125.0)), 0.0, "raiz", False, False)
        return ("walk_standard", False, max(0.85, min(1.55, avx / 145.0)), 0.0, "viagem", False, False)

    def _especificacao_clipe_acao(
        self,
        velocity: tuple[float, float],
        speed: float,
    ) -> tuple[str, bool, float, float, str, bool, bool] | None:
        """Escolhe o clipe Mixamo adequado ao estado, velocidade e humor."""
        st = self.state
        vx, vy = velocity
        humor = self.agencia.humor_atual
        irritado = humor in (Humor.INDIGNADO, Humor.TEIMOSO)
        if st == AnimationState.FALL and vy > 780.0 and self.state_time > 0.65:
            return ("swimming", vx < 0.0, 1.55, 0.0, "nado", False, False)
        if st == AnimationState.RUN:
            rate = max(0.85, min(1.55, abs(vx) / 245.0)) if abs(vx) > 40.0 else 1.0
            return ("run_mixamo", False, rate, 0.0, "viagem", False, False)
        if st == AnimationState.WALK:
            return self._especificacao_clipe_walk(vx, humor, irritado)
        if st == AnimationState.LAND and self._land_heavy:
            return ("cover_to_stand", self._reaction_direction < 0.0, 1.05, 0.0, "zero", False, False)
        if st == AnimationState.STRETCH:
            return ("arm_stretching", False, 1.75, 0.0, "raiz", False, False)
        if st == AnimationState.TEIMOSIA and self._teimosia_fase == "roubo" and abs(vx) > 40.0:
            return ("run_mixamo", False, 1.35, 0.0, "viagem", True, True)
        return None

    def _limpar_acao_clipe(self) -> None:
        if self._acao_clipe_nome is not None and self.pose_resolver._state_time > 1e-6:
            self.pose_resolver.iniciar_transicao(
                dict(self._pose),
                transition_seconds=min(self.transition_seconds, 0.28),
            )
        self._acao_clipe_nome = None
        self.acao_clipe_tempo = 0.0
        self.raiz_quat_acao = None
        self.dz_clipe_ativo = 0.0
        self.dedos_clipe_acao = None
        self._canais_pernas_acao = None

    def _resolver_acao_frame(
        self,
        dt: float,
        velocity: tuple[float, float],
        speed: float,
    ) -> tuple[dict[str, Rotation3], str, float, bool, bool] | None:
        """Amostra o clipe Mixamo ativo no frame (ou limpa o estado caso ausente)."""
        espec = self._especificacao_clipe_acao(velocity, speed)
        if espec is None:
            self._limpar_acao_clipe()
            return None
        nome, espelhar, escala, inicio, modo_giro, apenas_pernas, manter_door = espec
        clipe = carregar_clipe_acao(nome)
        if clipe is None:
            self._limpar_acao_clipe()
            return None
        if nome != self._acao_clipe_nome:
            anterior = self._acao_clipe_nome
            tempo = inicio
            if nome.startswith("walk_") and anterior and anterior.startswith("walk_"):
                clipe_anterior = carregar_clipe_acao(anterior)
                if clipe_anterior and clipe_anterior.quadros:
                    fase = (self.acao_clipe_tempo * clipe_anterior.fps) % len(clipe_anterior.quadros)
                    tempo += fase / len(clipe_anterior.quadros) * len(clipe.quadros) / clipe.fps
            if not apenas_pernas and self.pose_resolver._state_time > 1e-6:
                dur_clipe = 0.38 if nome == "swimming" else (0.22 if nome.startswith("walk_") else 0.26)
                self.pose_resolver.iniciar_transicao(
                    dict(self._pose),
                    transition_seconds=min(self.transition_seconds, dur_clipe),
                )
            self._acao_clipe_nome = nome
            self.acao_clipe_tempo = tempo
        else:
            self.acao_clipe_tempo += max(0.0, dt) * escala
        pose_clipe, pernas_clipe, dz, yaw_clipe, quat, dedos = amostrar_clipe_completo(
            clipe, self.acao_clipe_tempo, espelhar=espelhar
        )
        self.raiz_quat_acao = None if apenas_pernas else quat
        self.dedos_clipe_acao = None if apenas_pernas else dedos
        self.dz_clipe_ativo = dz
        self._canais_pernas_acao = pernas_clipe
        return pose_clipe, modo_giro, yaw_clipe, apenas_pernas, manter_door

    def iniciar_pacote_olhar_tela(self, lado: float | None = None) -> None:
        """Dispara o pacote 'Olhar a tela' (olhar por cima do ombro -> costas -> frente)."""
        self.idle_time = 0.0
        escolhido = (
            (1.0 if self._personality_rng.random() < 0.5 else -1.0)
            if lado is None
            else lado
        )
        self.pacote_olhar_tela.iniciar(lado=escolhido)

    def tocar_clipe_gltf(self, nome: str = "piloto/olhar_ombro") -> bool:
        """Inicia um clipe externo glTF sob o contrato aditivo em delta local."""
        if carregar_clipe_gltf(nome) is None:
            return False
        self.idle_time = 0.0
        self._cena_idle_nome = ""
        self._clipe_gltf_nome = nome
        self._clipe_gltf_tempo = 0.0
        self.clipe_gltf_amostra = AmostraClipeGltf()
        self.clipe_gltf_eventos = ()
        return True

    def parar_clipe_gltf(self) -> None:
        """Interrompe imediatamente qualquer clipe glTF em execução."""
        self._clipe_gltf_nome = ""
        self._clipe_gltf_tempo = 0.0
        self.clipe_gltf_amostra = AmostraClipeGltf()
        self.clipe_gltf_eventos = ()

    def _atualizar_clipe_gltf(
        self,
        dt: float,
        *,
        interromper: bool,
        delta_estado: dict[str, Rotation3],
    ) -> dict[str, Rotation3]:
        if interromper or not self._clipe_gltf_nome:
            if self._clipe_gltf_nome:
                self.parar_clipe_gltf()
            else:
                self.clipe_gltf_eventos = ()
            return delta_estado
        t_ant = -1e-6 if self._clipe_gltf_tempo == 0.0 else self._clipe_gltf_tempo
        t_novo = self._clipe_gltf_tempo + dt
        amostra = amostrar_clipe_gltf(
            self._clipe_gltf_nome, t_novo, tempo_anterior=t_ant
        )
        self._clipe_gltf_tempo = t_novo
        if not amostra.ativa:
            self.parar_clipe_gltf()
            return delta_estado
        self.clipe_gltf_amostra = amostra
        self.clipe_gltf_eventos = amostra.eventos
        if amostra.delta_rig:
            return somar_deltas(delta_estado, amostra.delta_rig)
        return delta_estado

    def definir_profundidade(self, nivel: NivelProfundidade | str) -> None:
        """Define o nível de profundidade visual (`perto`, `medio` ou `longe`)."""
        self._curiosidade_fundo_restante = 0.0
        self.profundidade.definir_nivel(nivel)

    def caminhar_para_fundo(self) -> NivelProfundidade:
        """Avança um nível de profundidade para dentro da tela (`perto -> medio -> longe`)."""
        return self.profundidade.avancar_fundo()

    def caminhar_para_frente(self) -> NivelProfundidade:
        """Avança um nível de profundidade para a frente da tela (`longe -> medio -> perto`)."""
        return self.profundidade.avancar_frente()

    def definir_orientacao(self, orientacao: OrientacaoCorpo | str | None) -> None:
        """Define a orientação manual do corpo (`frente`, `perfil`, `costas`) ou limpa."""
        if orientacao is None:
            self.orientacao_manual = None
            return
        self.orientacao_manual = OrientacaoCorpo(orientacao)
        if self.orientacao_manual != OrientacaoCorpo.COSTAS:
            self.pacote_olhar_tela.interromper()

    def voltar_ao_plano(self) -> None:
        """Retorna imediatamente ao plano frontal (`perto` e `frente`)."""
        self._curiosidade_fundo_restante = 0.0
        self.pacote_olhar_tela.interromper()
        self.orientacao_manual = None
        self.angulo_giro_pedido = 0.0
        self.permitir_giro_costas = False
        self.profundidade.definir_nivel(NivelProfundidade.PERTO)

    def preview_dance(self, style):
        """Força a prévia de um estilo de dança por alguns segundos."""
        if style not in (
            "head_bob", "hip_hop", "rock", "breakdance",
            "street_groove", "graffiti_dance", "cyber_bounce",
            *listar_clipes_emote(),
        ):
            return
        if self.state == AnimationState.DANCE:
            self.pose_resolver.iniciar_transicao(dict(self._pose), transition_seconds=0.65)
        self._cena_idle_nome = ""
        self._dance_preview_remaining = 16.0
        self._dance_preview_style = style
        self.dance_motion.style = style
        self.dance_motion.override = style
        self.dance_motion.tempo_clipe = 0.0
        self.dance_motion.style_beats = 0
        self.dance_motion.pose.clear()

    def _escolher_modo_sono_automatico(self) -> str:
        """Alterna organicamente entre dormir em pé, sentado e deitado sem repetir em sequência."""
        if not self._fila_modos_sono:
            candidatos = ["em_pe", "sentado", "deitado"]
            self._personality_rng.shuffle(candidatos)
            if candidatos[-1] == self._ultimo_sono_auto:
                candidatos.reverse()
            self._fila_modos_sono = candidatos
        modo = self._fila_modos_sono.pop()
        self._ultimo_sono_auto = modo
        self.modo_sono = modo
        return modo

    def colocar_para_dormir(self, modo: str = "em_pe") -> None:
        """Coloca o mascote para dormir em um dos 3 estados: em_pe, sentado ou deitado."""
        if modo not in ("em_pe", "sentado", "deitado"):
            modo = "em_pe"
        self.modo_sono = modo
        self._sleep_locked = True
        self.state = AnimationState.SLEEP
        self.state_time = 0.0
        self.appendage_remaining = 0.0
        self.pose_resolver.iniciar_transicao(
            dict(self._pose), transition_seconds=SONO_TRANSICAO_S
        )

    def acordar(self) -> None:
        """Acorda o mascote e retorna ao idle."""
        self._sleep_locked = False
        if self.state == AnimationState.SLEEP:
            self.interact("wake")

    def empurrar_respiracao(self, quantidade: float) -> None:
        """Soma uma inspiração breve ao movimento em curso."""
        self.respiracao.empurrar(quantidade)

    def set_idle_personality(self, personality: IdlePersonality | str | None) -> None:
        """Seleciona uma variação ou retorna ao repouso padrão."""
        selected = (
            IdlePersonality.CALM
            if personality is None or personality == "auto"
            else IdlePersonality(personality)
        )
        if selected == self.idle_personality:
            return
        self.idle_personality = selected
        self._idle_clock = 0.0
        self.pose_resolver.iniciar_transicao(
            dict(self._pose), transition_seconds=max(self.transition_seconds, 1.0)
        )
        self._active_transition_seconds = max(self.transition_seconds, 1.0)
        self.state_time = 0.0

    REACTION_SECONDS: ClassVar[dict[AnimationState, float]] = {
        **{
            AnimationState(k): 3.2
            for k in ("hang_loose", "thumbs_up", "rock", "finger_gun", "peace", "point")
        },
        AnimationState.OPEN_HANDS: 2.5,
        AnimationState.CLOSE_FISTS: 2.5,
        AnimationState.BLUE_BALLS: 2.4,
        AnimationState.VIRTUAL_INSANITY: 3.6,
        AnimationState.SNEEZE: 9.0,
        AnimationState.CLICK: 0.5,
        AnimationState.DOUBLE_CLICK: 1.4,
        AnimationState.PET: 1.5,
        AnimationState.POKE: CUTUCAR_DURACAO_S,
        AnimationState.WAKE: 1.2,
        AnimationState.LAND: 0.50,
        AnimationState.CELEBRATE: 2.0,
        AnimationState.WAVE: ACENO_DURACAO_S,
        AnimationState.STRETCH: ALONGAR_DURACAO_S,
        AnimationState.PEEK: 9.0,
        AnimationState.HIT: 0.65,
        # SURPRESA: recuo rápido + retorno no mesmo padrão das outras reações.
        # Duração CALIBRÁVEL (validar na GPU): curta o bastante para parecer um
        # susto, longa o bastante para o retorno ser visível.
        AnimationState.SURPRISE: 0.7,
        # TEIMOSIA: manifesto §1.4 — sequência completa (bote → roubo → cospe)
        AnimationState.TEIMOSIA: 6.0,
    }

    def _registrar_humor_interacao(self, kind: str, strength: float) -> None:
        if kind in ("pet", "double_click", "celebrate"):
            self.agencia.registrar_interacao_positiva(carinho=kind in ("pet", "double_click"))
        elif kind in ("hit", "poke"):
            self.agencia.registrar_interacao_negativa(strength)

    def _preparar_evento_especial(self, kind: str) -> bool:
        """Trata cenas idle, espiada, início de arraste e bloqueios de cooldown."""
        if kind in DURACOES_CENAS or kind in duracoes_cenas_ativas():
            if not (
                self.state in (AnimationState.FALL, AnimationState.DRAG)
                or self._reaction == AnimationState.LAND
            ):
                self._cena_idle_nome = kind
                self._cena_idle_tempo = 0.0
                self._cena_idle_variante += 1
                self._dance_preview_remaining = 0.0
                self._dance_remaining = 0.0
                self.pose_resolver.iniciar_transicao(dict(self._pose), transition_seconds=0.45)
            return True
        if kind == "peek":
            self.appendage_remaining = 9.0
            return True
        if kind == "drag_start":
            self._hover_sem_clique_tempo = 0.0
            self._passou_perto_restante = 0.0
            if self._reaction == AnimationState.TEIMOSIA:
                self._encerrar_teimosia()
            else:
                self._reaction = None
                if self.agencia.tem_meta_ativa or self.agencia.teimosia_ativa:
                    self.agencia.registrar_interrupcao()
            return True
        return False

    def _atualizar_sinais_cena_contextual(
        self,
        dt: float,
        *,
        grounded: bool,
        dragging: bool,
        hovered: bool,
        velocity: tuple[float, float],
        idle_enabled: bool,
        music_playing: bool,
        music_intensity: float,
        fonte_atencao: str | None,
        desejos_antes: int,
        meta_antes: object,
    ) -> None:
        """Atualiza memórias curtas que disparam cenas narrativas sem spam."""
        self._atualizar_sinais_musica_e_cursor(
            dt,
            grounded=grounded,
            dragging=dragging,
            hovered=hovered,
            music_playing=music_playing,
            music_intensity=music_intensity,
        )
        self._atualizar_sinais_pos_atividade(
            dt,
            grounded=grounded,
            dragging=dragging,
            velocity=velocity,
            idle_enabled=idle_enabled,
            music_playing=music_playing,
        )
        self._atualizar_sinais_pensamento_agencia(
            dt,
            music_playing=music_playing,
            fonte_atencao=fonte_atencao,
            desejos_antes=desejos_antes,
            meta_antes=meta_antes,
        )

    def _atualizar_sinais_musica_e_cursor(
        self,
        dt: float,
        *,
        grounded: bool,
        dragging: bool,
        hovered: bool,
        music_playing: bool,
        music_intensity: float,
    ) -> None:
        """Registra duração de música discreta e passagem próxima do cursor."""
        em_repouso = self.state in (AnimationState.IDLE, AnimationState.HOVER)
        if (
            music_playing
            and 0.01 < music_intensity <= 0.35
            and grounded
            and not dragging
            and not self._cena_idle_nome
            and em_repouso
        ):
            self._tempo_musica_discreta += dt
        else:
            self._tempo_musica_discreta = 0.0

        self._passou_perto_restante = max(0.0, self._passou_perto_restante - dt)
        reacao_toque = self._reaction in (
            AnimationState.CLICK,
            AnimationState.DOUBLE_CLICK,
            AnimationState.POKE,
            AnimationState.PET,
            AnimationState.HIT,
            AnimationState.TEIMOSIA,
        )
        if dragging or reacao_toque:
            self._hover_sem_clique_tempo = 0.0
            self._passou_perto_restante = 0.0
        elif hovered and not self._cena_idle_nome and em_repouso:
            self._hover_sem_clique_tempo += dt
        else:
            if 0.25 <= self._hover_sem_clique_tempo < 2.2:
                self._passou_perto_restante = 4.0
            self._hover_sem_clique_tempo = 0.0

    def _atualizar_sinais_pos_atividade(
        self,
        dt: float,
        *,
        grounded: bool,
        dragging: bool,
        velocity: tuple[float, float],
        idle_enabled: bool,
        music_playing: bool,
    ) -> None:
        """Marca cena de assentamento após queda, arraste, caminhada ou sono."""
        em_impacto = (
            dragging
            or self.state
            in (
                AnimationState.DRAG,
                AnimationState.FALL,
                AnimationState.LAND,
                AnimationState.HIT,
                AnimationState.POKE,
            )
            or self._reaction in (AnimationState.LAND, AnimationState.HIT, AnimationState.POKE)
        )
        if em_impacto:
            self._atividade_previa = "impacto_arraste"
            self._tempo_atividade_previa += dt
            self._tempo_assentado_idle = 0.0
            self._pos_atividade_pendente = ""
            return
        if self.state in (AnimationState.WALK, AnimationState.RUN):
            if self._atividade_previa != "impacto_arraste":
                self._atividade_previa = "caminhada"
            self._tempo_atividade_previa += dt
            self._tempo_assentado_idle = 0.0
            return
        if self.state == AnimationState.SLEEP:
            self._atividade_previa = "sono"
            self._tempo_atividade_previa += dt
            self._tempo_assentado_idle = 0.0
            return
        if not (grounded and self.state in (AnimationState.IDLE, AnimationState.HOVER)):
            return

        if (
            self._atividade_previa == "impacto_arraste"
            and self._tempo_atividade_previa >= 0.08
        ) or (
            self._atividade_previa == "caminhada"
            and self._tempo_atividade_previa >= 0.8
        ):
            self._pos_atividade_pendente = (
                "conferir_luva"
                if (self._indice_pos_atividade % 2 == 0)
                else "alongar_pescoco_ombros"
            )
        elif self._atividade_previa == "sono" and self._tempo_atividade_previa >= 2.0:
            self._pos_atividade_pendente = "alongar_pescoco_ombros"
        self._atividade_previa = ""
        self._tempo_atividade_previa = 0.0

        parado = (
            idle_enabled
            and not music_playing
            and not self._cena_idle_nome
            and abs(velocity[0]) < 30.0
            and abs(velocity[1]) < 30.0
        )
        self._tempo_assentado_idle = (self._tempo_assentado_idle + dt) if parado else 0.0

    def _atualizar_sinais_pensamento_agencia(
        self,
        dt: float,
        *,
        music_playing: bool,
        fonte_atencao: str | None,
        desejos_antes: int,
        meta_antes: object,
    ) -> None:
        """Detecta mudança de foco de janela ou avaliação de meta pela agência."""
        self._pensamento_janela_restante = max(0.0, self._pensamento_janela_restante - dt)
        mudanca_foco = (
            fonte_atencao in ("foco", "janela")
            and fonte_atencao != self._fonte_atencao_anterior
        )
        meta_concluida = meta_antes is not None and self.agencia.meta_ativa is None
        novo_desejo_maduro = (
            self.clock >= 18.0
            and len(self.agencia._desejos) > desejos_antes
            and not self.agencia.tem_meta_ativa
        )
        if not music_playing and (mudanca_foco or meta_concluida or novo_desejo_maduro):
            self._pensamento_janela_restante = 6.0
        elif music_playing or self.state in (AnimationState.DRAG, AnimationState.FALL, AnimationState.SLEEP):
            self._pensamento_janela_restante = 0.0
        self._fonte_atencao_anterior = fonte_atencao

    def _escolher_cena_contextual(
        self,
        *,
        musica_comecou: bool,
        music_playing: bool,
        music_intensity: float,
        react_to_beat: bool,
        cursor_retornou: bool,
        hovered: bool = False,
    ) -> tuple[str, float]:
        """Seleciona a próxima cena contextual respeitando prioridades e cooldowns."""
        if musica_comecou and react_to_beat and music_intensity > 0.01:
            if music_intensity > 0.32:
                return ("escutar_fone", 60.0)
            opcoes = ("batida_guardada", "checar_walkman", "groove_um_pe", "escutar_fone")
            cena = opcoes[self._indice_cena_musica % len(opcoes)]
            self._indice_cena_musica += 1
            return (cena, 60.0)

        if (
            not musica_comecou
            and music_playing
            and react_to_beat
            and 0.01 < music_intensity <= 0.35
            and self._tempo_musica_discreta >= 10.0
            and self._dance_remaining <= 0.0
        ):
            opcoes = ("batida_guardada", "checar_walkman", "groove_um_pe", "escutar_fone")
            cena = opcoes[self._indice_cena_musica % len(opcoes)]
            self._indice_cena_musica += 1
            return (cena, 54.0)

        if cursor_retornou and not music_playing:
            return ("disfarcar_olhar", 60.0)

        if not hovered and not music_playing and self._passou_perto_restante > 0.0:
            opcoes = ("segurar_porta_timido", "disfarcar_olhar")
            cena = opcoes[self._indice_cena_cursor % len(opcoes)]
            self._indice_cena_cursor += 1
            return (cena, 52.0)

        if (
            not music_playing
            and self._pos_atividade_pendente
            and self._tempo_assentado_idle >= 1.4
        ):
            cena = self._pos_atividade_pendente
            self._indice_pos_atividade += 1
            return (cena, 50.0)

        if not music_playing and not self._pos_atividade_pendente and self._pensamento_janela_restante > 0.0:
            return ("pensar_gabinete", 55.0)

        return ("", 0.0)

    def interact(
        self,
        kind: str,
        *,
        direction: float | None = None,
        strength: float = 1.0,
        part: str | None = None,
        left_gesture: str | None = None,
    ) -> None:
        """Interação acorda o mascote e dispara uma reação com cooldown."""
        if (
            part is None
            and self._pending_intent is None
            and self._pending_intent_part is not None
        ):
            part = self._pending_intent_part
            self._pending_intent_part = None
        self.idle_time = 0.0
        if self._preparar_evento_especial(kind):
            self._gesto_mao_esquerda = None
            return
        if self.state == AnimationState.SLEEP:
            kind = "wake"
        sem_cooldown = ("blue_balls", "virtual_insanity", "peace", "open_hands", "hit")
        if kind not in self.REACTION_SECONDS or (
            kind not in sem_cooldown and self.clock < self._cooldowns.get(kind, 0.0)
        ):
            return
        # Continuidade pós-queda (Rain World): guarda intenções não-emergenciais
        # recebidas durante FALL/DRAG/LAND para retomá-las após amortecer o pouso.
        em_queda = (
            self.state in (AnimationState.FALL, AnimationState.DRAG)
            or self._reaction == AnimationState.LAND
        )
        if kind not in ("hit", "land", "wake") and em_queda:
            self._pending_intent = (kind, direction, strength)
            self._pending_intent_part = part
            return
        parte_normalizada = part or "body"
        if direction is None:
            p_low = parte_normalizada.lower()
            if any(k in p_low for k in ("left", "esquerd", "hand2", "ant-arm2", "fingers2", "shoulder2")):
                dir_ref = -1.0
            elif any(k in p_low for k in ("right", "direit", "ant-arm", "hand", "fingers", "shoulder")):
                dir_ref = 1.0
            else:
                dir_ref = self._look_direction
        else:
            dir_ref = direction
        self.body_motion.impulse(kind, dir_ref, strength, part=parte_normalizada)
        if kind == "wake":
            self._sleep_locked = False
        self._gesto_mao_esquerda = (
            left_gesture if left_gesture in _GESTOS_MAO_DIREITA else None
        )
        self._ativar_reacao_humor(kind, dir_ref, strength, parte_normalizada)

    def _ativar_reacao_humor(
        self, kind: str, dir_ref: float, strength: float, parte_normalizada: str
    ) -> None:
        """Atualiza humor/marcos da agência e registra estado e cooldown da reação."""
        ja_irritado = (
            self.agencia.humor_atual in (Humor.INDIGNADO, Humor.TEIMOSO)
            or self.agencia.interrupcoes.contador >= 2
            or getattr(self.agencia, "_humor_tempo", {}).get(Humor.INDIGNADO, 0.0) > 0.0
        )
        if self._reaction == AnimationState.TEIMOSIA and kind != "teimosia":
            self._encerrar_teimosia()
        self._registrar_humor_interacao(kind, strength)
        if kind in ("pet", "double_click") and self.agencia.consumir_marco_carinho():
            self._pending_intent = ("celebrate", dir_ref, 1.0)
            self._pending_intent_part = parte_normalizada
        self._reaction = AnimationState(kind)
        self._reaction_time = 0.0
        self._reaction_part = parte_normalizada
        self._land_heavy = kind == "land" and strength >= 1.35
        self._defesa_firmeza = max(0.0, min(1.0, 0.5 * strength + 0.5 * ja_irritado))
        self._reaction_direction = 1.0 if dir_ref >= 0.0 else -1.0
        if self.state == self._reaction == AnimationState.HIT:
            self.pose_resolver.iniciar_transicao(
                dict(self._pose), transition_seconds=min(self.transition_seconds, 0.10)
            )
        recuo_min = 6.0 if kind == "surprise" else 0.5
        dur = duracoes_reacoes().get(
            self._reaction.value, self.REACTION_SECONDS[self._reaction]
        )
        self._cooldowns[kind] = self.clock + max(dur, recuo_min)

    @staticmethod
    def _choose_state(
        *,
        speed: float,
        grounded: bool,
        gravity_active: bool,
        dragging: bool,
        music_playing: bool,
        music_intensity: float,
        current_state: AnimationState | None = None,
    ) -> AnimationState:
        from sejoga.animacao.selecao_estado import escolher_estado

        return escolher_estado(
            speed=speed,
            grounded=grounded,
            gravity_active=gravity_active,
            dragging=dragging,
            music_playing=music_playing,
            music_intensity=music_intensity,
            current_state=current_state,
        )

    def update(  # noqa: C901, PLR0915  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
        self,
        dt: float,
        *,
        velocity: tuple[float, float] = (0.0, 0.0),
        grounded: bool = True,
        gravity_active: bool = False,
        dragging: bool = False,
        drag_direction: float = 0.0,
        drag_intensity: float = 0.0,
        music_playing: bool = False,
        music_intensity: float = 0.0,
        music_bass: float = 0.0,
        music_bpm: float | None = None,
        dance_chance: float = 1.0,
        react_to_beat: bool = True,
        beat_detected: bool = False,
        beat_phase: float | None = None,
        music_updated_at: float | None = None,
        now: float | None = None,
        idle_enabled: bool = True,
        sleep_after_idle_seconds: int = 0,
        hovered: bool = False,
        look_direction: float = 0.0,
        look_vertical: float = 0.0,
        fonte_atencao: str | None = None,
        pointer_position: tuple[float, float] | None = None,
        body_position: tuple[float, float] | None = None,
        grab_part: str = "body",
        grab_point: tuple[float, float, float] | None = None,
        pixels_per_unit: float = 216.8,
    ) -> dict[str, Rotation3]:
        """Atualiza o estado e devolve um snapshot de rotações em radianos."""
        dt = min(0.1, max(0.0, dt))
        if self._dance_preview_remaining > 0:
            self._dance_preview_remaining = max(0, self._dance_preview_remaining - dt)
            music_playing = react_to_beat = True
            dance_chance = 1.0
            clipe_previa = (
                carregar_clipe_emote(self._dance_preview_style)
                if self._dance_preview_style != "head_bob"
                else None
            )
            music_intensity, music_bass, music_bpm = {
                "head_bob": (0.2, 0.03, 80),
                "hip_hop": (0.5, 0.3, 95),
                "rock": (0.6, 0.15, 135),
                "breakdance": (0.9, 0.6, 145),
                "street_groove": (0.65, 0.4, 108),
                "graffiti_dance": (0.55, 0.25, 100),
                "cyber_bounce": (0.75, 0.5, 124),
            }.get(
                self._dance_preview_style,
                (
                    0.65,
                    0.4,
                    clipe_previa.bpm_nativo if clipe_previa is not None else 108.0,
                ),
            )
            if clipe_previa is not None:
                music_bpm = clipe_previa.bpm_nativo
            self.dance_motion.override = self._dance_preview_style
            self._dance_remaining = 1.0
        self.clock += dt
        self.delta_time = dt
        musica_comecou = music_playing and self._music_grace <= 0.0
        self._music_grace = 0.65 if music_playing else max(0.0, self._music_grace - dt)
        music_playing = self._music_grace > 0
        self.music_active = music_playing
        giro_norm = ((float(self.angulo_giro_pedido or 0.0) + 180.0) % 360.0) - 180.0
        if self.orientacao_manual == OrientacaoCorpo.COSTAS or (
            self.permitir_giro_costas and abs(giro_norm) > 90.0
        ):
            look_direction = -look_direction
        self.appendage_remaining = max(0, self.appendage_remaining - dt)

        # ── Sistema de agência: atualizar cérebro do Mário ──────────────
        cursor_parado = False
        cursor_retornou = False
        if pointer_position is not None:
            if self._cursor_anterior is None:
                self._cursor_anterior = pointer_position
                self.agencia.registrar_cursor_movimento()
            else:
                dx = pointer_position[0] - self._cursor_anterior[0]
                dy = pointer_position[1] - self._cursor_anterior[1]
                if dx * dx + dy * dy <= 16.0:
                    cursor_parado = True
                else:
                    cursor_retornou = self.agencia.tempo_sem_cursor_movimento >= 8.0
                    self._cursor_anterior = pointer_position
                    self.agencia.registrar_cursor_movimento()
        else:
            self._cursor_anterior = None
        if body_position is not None:
            self.agencia.definir_posicao_corpo(*body_position)
        self._last_velocity = velocity
        desejos_antes = len(self.agencia._desejos)
        meta_antes = self.agencia.meta_ativa
        self.agencia.atualizar(dt)
        self._atualizar_sinais_cena_contextual(
            dt,
            grounded=grounded,
            dragging=dragging,
            hovered=hovered,
            velocity=velocity,
            idle_enabled=idle_enabled,
            music_playing=music_playing,
            music_intensity=music_intensity,
            fonte_atencao=fonte_atencao,
            desejos_antes=desejos_antes,
            meta_antes=meta_antes,
        )

        pode_encenar = (
            idle_enabled and grounded and not gravity_active and not dragging
            and self.state in (AnimationState.IDLE, AnimationState.HOVER)
            and abs(velocity[0]) < 75.0 and abs(velocity[1]) < 75.0
            and not self._sleep_locked and self._reaction is None
            and not self._cena_idle_nome and not self._clipe_gltf_nome
            and not self.pacote_olhar_tela.ativo and not self.agencia.tem_meta_ativa
            and self.orientacao_manual is None and self.appendage_remaining <= 0.0
            and self._curiosidade_fundo_restante <= 0.0
            and self._dance_preview_remaining <= 0.0
            and self.clock >= self._cooldowns.get("cena_contextual", 0.0)
        )
        if pode_encenar:
            cena, recarga = self._escolher_cena_contextual(
                musica_comecou=musica_comecou,
                music_playing=music_playing,
                music_intensity=music_intensity,
                react_to_beat=react_to_beat,
                cursor_retornou=cursor_retornou,
                hovered=hovered,
            )
            if cena:
                self.interact(cena)
                self._cooldowns["cena_contextual"] = self.clock + recarga
                self._tempo_musica_discreta = 0.0
                self._passou_perto_restante = 0.0
                self._hover_sem_clique_tempo = 0.0
                self._pos_atividade_pendente = ""
                self._tempo_assentado_idle = 0.0
                self._pensamento_janela_restante = 0.0

        # Direção da meta ativa para resistência durante arraste
        meta_dir = self.agencia.direcao_meta
        resistencia = self.agencia.resistencia_ao_arraste

        self.body_motion.update(
            dt,
            pointer=pointer_position,
            dragging=dragging,
            hovered=hovered,
            look=(look_direction, look_vertical),
            grounded=grounded,
            velocity=velocity,
            grab_part=grab_part,
            grab_point=grab_point,
            meta_direcao=meta_dir,
            resistencia_nivel=resistencia,
        )
        if self.state == AnimationState.DRAG and not dragging:
            self._release_time = 0.0
            self._release_grip = self.drag_intensity
        else:
            self._release_time += dt
        self.drag_intensity += (
            max(0, min(1, drag_intensity)) - self.drag_intensity
        ) * min(1, dt * 8)
        self._dance_remaining = max(0.0, self._dance_remaining - dt)
        self._dance_decision_in = max(0.0, self._dance_decision_in - dt)
        if not music_playing or not react_to_beat or dance_chance <= 0:
            self._dance_remaining = 0.0
            self._dance_decision_in = 0.0
        elif self._dance_decision_in == 0 and not self._cena_idle_nome:
            # One decision per phrase, never one random draw per rendered frame.
            self._dance_decision_in = 8.0
            if self._dance_rng.random() < min(1.0, dance_chance):
                self._dance_remaining = 8.0
        beat_edge = beat_detected and not self._previous_beat
        self._previous_beat = beat_detected
        # Onsets corrigem a cadência; não classificam áudio baixo como alto.
        estilo_anterior = self.dance_motion.style
        self.dance_motion.update(
            dt,
            music_intensity,
            music_bass,
            music_bpm,
            beat_edge,
            beat_phase=beat_phase,
            music_updated_at=music_updated_at,
            now=now,
        )
        if self.state == AnimationState.DANCE and estilo_anterior != self.dance_motion.style:
            self.pose_resolver.iniciar_transicao(dict(self._pose), transition_seconds=0.65)
        suave_olhar = min(1.0, dt * 5.2)
        self._look_direction += (
            max(-1.0, min(1.0, look_direction)) - self._look_direction
        ) * suave_olhar
        self._look_vertical += (
            max(-1.0, min(1.0, look_vertical)) - self._look_vertical
        ) * suave_olhar
        # Tronco acompanha o olhar com atraso suave (ação sobreposta).
        self._idle_torso_look_dir += (
            self._look_direction - self._idle_torso_look_dir
        ) * min(1.0, dt * 3.0)
        self._idle_torso_look_vert += (
            self._look_vertical - self._idle_torso_look_vert
        ) * min(1.0, dt * 3.0)
        if self._reaction is not None:
            self._reaction_time += dt
            duracao_base = duracoes_reacoes().get(
                self._reaction.value, self.REACTION_SECONDS[self._reaction]
            )
            duracao_reacao = (
                1.45
                if self._reaction == AnimationState.LAND and self._land_heavy
                else duracao_base
            )
            if self._reaction_time >= duracao_reacao:
                self._land_heavy = False
                if self._reaction == AnimationState.TEIMOSIA:
                    self._encerrar_teimosia()
                self._reaction = None
                if (
                    grounded
                    and not dragging
                    and self._pending_intent is not None
                ):
                    pending = self._pending_intent
                    self._pending_intent = None
                    self.interact(
                        pending[0], direction=pending[1], strength=pending[2]
                    )

        if not grounded and not dragging:
            self._peak_fall_vy = max(self._peak_fall_vy, abs(velocity[1]))
        if (
            self._was_grounded is False
            and grounded
            and not dragging
            and (self.state == AnimationState.FALL or self._peak_fall_vy > 100.0)
        ):
            forca = max(0.75, min(1.9, self._peak_fall_vy / 360.0))
            self.interact(
                "land",
                direction=max(-1.0, min(1.0, velocity[0] / 400.0)),
                strength=forca,
            )
        self._was_grounded = grounded
        if grounded:
            self._peak_fall_vy = 0.0

        speed = (velocity[0] ** 2 + velocity[1] ** 2) ** 0.5
        next_state = self._choose_state(
            speed=speed,
            grounded=grounded,
            gravity_active=gravity_active,
            dragging=dragging,
            music_playing=music_playing and self._dance_remaining > 0 and not self._cena_idle_nome,
            music_intensity=music_intensity,
            current_state=self.state,
        )
        if self._reaction == AnimationState.TEIMOSIA and next_state in (
            AnimationState.DRAG, AnimationState.FALL,
        ):
            self._encerrar_teimosia()
        elif self._reaction == AnimationState.POKE and next_state == AnimationState.DRAG:
            self._reaction = None
        condicao_quietude = (
            cursor_parado
            and grounded
            and idle_enabled
            and not hovered
            and not music_playing
            and not dragging
            and self._reaction is None
            and not self._cena_idle_nome
        )
        if (
            condicao_quietude
            and next_state == AnimationState.IDLE
            and self.state == AnimationState.IDLE
        ):
            if self.appendage_remaining <= 0.0:
                anterior = self._quietude
                self._quietude += dt
                # Tentáculos saem quando Mário acha que ninguém está olhando (Manifesto §1.3 C)
                if anterior < 14.0 <= self._quietude:
                    self.appendage_remaining = 5.5
                    self._quietude = 0.0
        elif not (
            condicao_quietude
            and (
                next_state == AnimationState.WALK
                or (
                    self.state == AnimationState.WALK
                    and next_state == AnimationState.IDLE
                )
            )
        ):
            self._quietude = 0.0
            if next_state in (AnimationState.SLEEP, AnimationState.DRAG, AnimationState.FALL):
                self.appendage_remaining = 0.0
        if hovered:
            self._hover_enter_timer += dt
            self._hover_exit_timer = 0.0
        else:
            self._hover_exit_timer += dt
            self._hover_enter_timer = 0.0

        if next_state != AnimationState.DRAG and (
            next_state != AnimationState.FALL or self._reaction == AnimationState.HIT
        ):
            if self._reaction is not None and (
                next_state != AnimationState.DANCE
                or self._reaction in (
                    AnimationState.HIT,
                    AnimationState.POKE,
                    AnimationState.TEIMOSIA,
                    AnimationState.LAND,
                    AnimationState.SNEEZE,
                    AnimationState.OPEN_HANDS,
                    AnimationState.CLOSE_FISTS,
                    AnimationState.BLUE_BALLS,
                    AnimationState.VIRTUAL_INSANITY,
                    AnimationState.CELEBRATE,
                )
            ):
                next_state = self._reaction
            elif next_state == AnimationState.IDLE and not self._cena_idle_nome and (
                (
                    hovered
                    and (
                        self.state == AnimationState.HOVER
                        or self._hover_enter_timer >= 0.08
                    )
                )
                or (
                    not hovered
                    and self.state == AnimationState.HOVER
                    and self._hover_exit_timer < 0.18
                )
            ):
                next_state = AnimationState.HOVER
        if self._sleep_locked:
            if next_state in (AnimationState.DRAG, AnimationState.FALL):
                self._sleep_locked = False
            else:
                next_state = AnimationState.SLEEP
        elif next_state in (
            AnimationState.IDLE,
            AnimationState.WAVE,
            AnimationState.STRETCH,
            AnimationState.PEEK,
        ):
            self.idle_time += dt
            if (
                sleep_after_idle_seconds > 0
                and self.idle_time >= sleep_after_idle_seconds
            ):
                if self.state != AnimationState.SLEEP:
                    self._escolher_modo_sono_automatico()
                next_state = AnimationState.SLEEP
        else:
            self.idle_time = 0.0

        # ── Teimosia: se agência detectou 3+ interrupções, acionar TEIMOSIA ─
        if (
            self.agencia.teimosia_ativa
            and grounded
            and self.state
            not in (
                AnimationState.TEIMOSIA,
                AnimationState.DRAG,
                AnimationState.FALL,
                AnimationState.LAND,
            )
            and next_state not in (AnimationState.DRAG, AnimationState.FALL, AnimationState.SLEEP)
            and self._reaction is None
        ):
            self._reaction = AnimationState.TEIMOSIA
            self._reaction_time = 0.0
            self._cooldowns["teimosia"] = self.clock + 6.0
            next_state = AnimationState.TEIMOSIA

        if (
            self._reaction == AnimationState.TEIMOSIA
            and 2.0 <= self._reaction_time <= 5.2
        ):
            self.appendage_remaining = max(
                self.appendage_remaining, 5.2 - self._reaction_time
            )

        if next_state != self.state:
            self._estado_origem = self.state.value if self.state is not None else ""
            if next_state in (AnimationState.FALL, AnimationState.HIT):
                self._active_transition_seconds = min(self.transition_seconds, 0.11)
            elif next_state in (
                AnimationState.DRAG,
                AnimationState.POKE,
                AnimationState.BLUE_BALLS,
                AnimationState.VIRTUAL_INSANITY,
            ):
                self._active_transition_seconds = min(self.transition_seconds, 0.14)
            else:
                self._active_transition_seconds = self.transition_seconds

            if next_state == AnimationState.SLEEP:
                # Adormecer é lento: crossfade longo para o corpo não cair de uma vez.
                self._active_transition_seconds = max(
                    self.transition_seconds, SONO_TRANSICAO_S
                )
            elif next_state == AnimationState.WAKE:
                self._active_transition_seconds = 0.65
            elif (
                self.state in (AnimationState.HIT, AnimationState.POKE, AnimationState.LAND, AnimationState.TEIMOSIA)
                and next_state in (AnimationState.IDLE, AnimationState.HOVER, AnimationState.WALK, AnimationState.RUN, AnimationState.DANCE)
            ):
                self._active_transition_seconds = min(self.transition_seconds, 0.34)
            elif (
                next_state in (AnimationState.HOVER, AnimationState.IDLE)
                and self.state in (AnimationState.HOVER, AnimationState.IDLE)
            ):
                # Entrada/saída de hover sem tranco nas mãos ou cabeça.
                self._active_transition_seconds = max(self.transition_seconds, 0.28)

            self.pose_resolver.iniciar_transicao(
                dict(self._pose), transition_seconds=self._active_transition_seconds
            )
            self.state = next_state
            self.state_time = 0.0
        else:
            self.state_time += dt

        if self.state == AnimationState.TEIMOSIA:
            fase = fase_teimosia_do_tempo(self._reaction_time)
            if fase != self._teimosia_fase:
                self._teimosia_fase = fase
                self.pose_resolver.iniciar_transicao(
                    dict(self._pose), transition_seconds=min(self.transition_seconds, 0.20)
                )

        indignado = (
            self.state == AnimationState.IDLE
            and self.agencia.humor_atual in (Humor.INDIGNADO, Humor.TEIMOSO)
            and not self._cena_idle_nome
            and not self._clipe_gltf_nome
            and not self.pacote_olhar_tela.ativo
            and self.orientacao_manual is None
        )
        self._peso_indignacao = max(
            0.0, min(1.0, self._peso_indignacao + (1.0 if indignado else -1.0) * dt / 0.45)
        )

        self.rig.reset()
        em_repouso = idle_enabled and self.state in (AnimationState.IDLE, AnimationState.HOVER)
        passo = dt / 0.55
        self._peso_repouso = (
            min(1.0, self._peso_repouso + passo)
            if em_repouso
            else max(0.0, self._peso_repouso - passo)
        )
        peso_repouso = suavizar_quintico(self._peso_repouso)
        ciclo = amostrar_respiracao_repouso(self.clock)
        impulso = self.respiracao.atualizar(dt)
        self.respiracao_valor = max(
            -1.0, min(1.0, ciclo * peso_repouso + impulso)
        )
        if self.state in (AnimationState.IDLE, AnimationState.HOVER) and idle_enabled:
            self._idle_clock += dt
        eh_danca_emote = (
            self.state == AnimationState.DANCE
            and carregar_clipe_emote(self.dance_motion.style) is not None
        )
        target = (
            {}
            if self.state in _ESTADOS_MIGRADOS
            else self._pose_nao_migrada(
                dragging=dragging, eh_danca_emote=eh_danca_emote
            )
        )

        # ═══════════════════════════════════════════════════════════════════════
        # Pacotes de animação, profundidade visual e giro de corpo (Fases 3-4)
        # ═══════════════════════════════════════════════════════════════════════
        self.profundidade.atualizar(dt, arrastando=dragging)
        interromper_pacote = (
            dragging
            or not grounded
            or self.state
            not in (
                AnimationState.IDLE,
                AnimationState.HOVER,
                AnimationState.WALK,
                AnimationState.RUN,
            )
        )
        amostra_olhar = self.pacote_olhar_tela.atualizar(
            dt, interromper=interromper_pacote
        )
        self._fonte_atencao = fonte_atencao
        if self._curiosidade_fundo_restante > 0.0:
            self._curiosidade_fundo_restante = max(0.0, self._curiosidade_fundo_restante - dt)
            if self._curiosidade_fundo_restante <= 0.0 or dragging:
                self._curiosidade_fundo_restante = 0.0
                self.profundidade.definir_nivel(NivelProfundidade.PERTO)

        elegivel_curiosidade = (
            self.state == AnimationState.IDLE
            and grounded
            and idle_enabled
            and not dragging
            and not amostra_olhar.ativo
            and not self._cena_idle_nome
            and self.orientacao_manual is None
            and self._curiosidade_fundo_restante <= 0.0
        )
        pacote_sorteado = self.agendador_pacotes.atualizar(
            dt, elegivel=elegivel_curiosidade
        )
        if pacote_sorteado in ("olhar_tela", "caminhar_fundo"):
            lado_olhar = 1.0 if look_direction >= 0 else -1.0
            if pacote_sorteado == "caminhar_fundo":
                self.caminhar_para_fundo()
                self._curiosidade_fundo_restante = 16.0
            self.iniciar_pacote_olhar_tela(lado=lado_olhar)
            amostra_olhar = self.pacote_olhar_tela.atualizar(0.0)

        acao_frame = self._resolver_acao_frame(dt, velocity, speed)

        if dragging:
            self.angulo_giro_pedido = None
            self.permitir_giro_costas = False
        elif eh_danca_emote:
            self.angulo_giro_pedido = self.dance_motion.giro_corpo_emote
            self.permitir_giro_costas = True
        elif amostra_olhar.ativo:
            self.angulo_giro_pedido = amostra_olhar.angulo_giro_corpo
            self.permitir_giro_costas = True
        elif self.orientacao_manual is not None:
            self.angulo_giro_pedido = ANGULO_POR_ORIENTACAO[self.orientacao_manual]
            self.permitir_giro_costas = (
                self.orientacao_manual == OrientacaoCorpo.COSTAS
            )
        elif acao_frame is not None:
            _pose_a, modo_giro, yaw_acao, _apenas_p, _manter_door = acao_frame
            if modo_giro == "nado":
                self.angulo_giro_pedido = 42.0 if velocity[0] >= 0.0 else -42.0
            elif modo_giro == "viagem":
                self.angulo_giro_pedido = (
                    90.0 if velocity[0] > 40.0 else (-90.0 if velocity[0] < -40.0 else None)
                )
            elif modo_giro == "raiz":
                self.angulo_giro_pedido = max(-95.0, min(95.0, yaw_acao))
            else:
                self.angulo_giro_pedido = 0.0
            self.permitir_giro_costas = False
        elif self.state in (AnimationState.WALK, AnimationState.RUN) and abs(velocity[0]) > 40.0:
            self.angulo_giro_pedido = 90.0 if velocity[0] > 0.0 else -90.0
            self.permitir_giro_costas = False
        else:
            self.angulo_giro_pedido = None
            self.permitir_giro_costas = False

        # ═══════════════════════════════════════════════════════════════════════
        # Composição via LayerStack (Fase 3): produz delta do estado atual
        # e usa layer_stack.compor() para obter pose composta.
        # ═══════════════════════════════════════════════════════════════════════
        motion = self.body_motion.snapshot

        # Produz delta do estado atual
        delta_estado = self._delta_do_estado(
            self.state,
            self._idle_clock
            if self.state in (AnimationState.IDLE, AnimationState.HOVER)
            else self.clock,
            velocity,
            grab_part,
        )
        # Soltura: os dedos abrem além do ponto ao largar (aditivo, fecha em 0).
        if delta_estado and not dragging and self.state != AnimationState.DRAG:
            delta_estado = somar_deltas(
                delta_estado, delta_soltura(self._release_time, self._release_grip)
            )
        if self.state in (AnimationState.IDLE, AnimationState.HOVER) and self._cena_idle_nome:
            cena_anterior_ativa = self.cena_idle_amostra.ativa
            ritmo_cena = (
                max(0.8, min(1.3, music_bpm / 100.0))
                if self._cena_idle_nome in ("batida_guardada", "checar_walkman", "groove_um_pe")
                and music_bpm
                else 1.0
            )
            self._cena_idle_tempo += dt * ritmo_cena
            self.cena_idle_amostra = amostrar_cena_idle(
                self._cena_idle_nome,
                self._cena_idle_tempo,
                variante=self._cena_idle_variante,
            )
            if not self.cena_idle_amostra.ativa:
                self._cena_idle_nome = ""
                self._cena_idle_tempo = 0.0
                if cena_anterior_ativa and self.pose_resolver._state_time > 1e-6:
                    self.pose_resolver.iniciar_transicao(
                        dict(self._pose),
                        transition_seconds=min(self.transition_seconds, 0.40),
                    )
            elif self.cena_idle_amostra.delta_rig:
                if self.cena_idle_amostra.peso_mistura > 0.0:
                    delta_estado = misturar_deltas_seletivo(
                        delta_estado,
                        self.cena_idle_amostra.delta_rig,
                        self.cena_idle_amostra.peso_mistura,
                    )
                else:
                    delta_estado = somar_deltas(delta_estado, self.cena_idle_amostra.delta_rig)
        else:
            self._cena_idle_nome = ""
            self._cena_idle_tempo = 0.0
            self.cena_idle_amostra = AmostraCenaIdle()
        interromper_gltf = (
            dragging
            or not grounded
            or self._reaction is not None
            or bool(self._cena_idle_nome)
            or self.state not in (AnimationState.IDLE, AnimationState.HOVER)
        )
        delta_estado = self._atualizar_clipe_gltf(
            dt, interromper=interromper_gltf, delta_estado=delta_estado
        )
        if amostra_olhar.ativo and amostra_olhar.delta_pose:
            delta_estado = somar_deltas(delta_estado, amostra_olhar.delta_pose)

        # Determina se o estado atual usa exclusivamente o caminho aditivo LayerStack.
        estado_migrado = self.state in _ESTADOS_MIGRADOS and bool(delta_estado)

        if estado_migrado:
            relogio_sec = (
                self._idle_clock
                if self.state in (AnimationState.IDLE, AnimationState.HOVER)
                else self.clock
            )
            # Set camadas no LayerStack
            self.layer_stack.set_camada(
                CamadaDelta(
                    nome="estado",
                    prioridade=Prioridade.ESTADO,
                    delta=delta_estado,
                )
            )

            # Camada de física (roll, pitch, yaw do body_motion)
            self.layer_stack.set_camada(
                CamadaDelta(
                    nome="fisica",
                    prioridade=Prioridade.FISICA,
                    delta=delta_fisica(
                        motion,
                        pendurado=dragging and motion.hanging > tune.PENDURADO_LIMIAR,
                    ),
                )
            )

            # Camada secundária (follow-through de coluna, fones, antenas, ombros e mãos)
            self.layer_stack.set_camada(
                CamadaDelta(
                    nome="secundario",
                    prioridade=Prioridade.FOLLOW_THROUGH,
                    delta=delta_secundario(
                        relogio_sec,
                        self.state.value,
                        self.idle_personality,
                        delta_estado,
                    ),
                )
            )

            # Compõe todas as juntas sobre pose_repouso() (já cobre os 30 grupos do rig).
            composed = self.layer_stack.compor()
        else:
            # Estados não migrados: usa sistema legado com MixerCamadas
            camadas = [CamadaAnim("base", dict(target))]
            if self.state == AnimationState.DANCE:
                base = camadas[0].contribuicao
                contribuicao_musica = {
                    grupo: base[grupo] for grupo in MASCARA_MUSICA if grupo in base
                }
                for grupo in contribuicao_musica:
                    base[grupo] = Rotation3()
                camadas.append(
                    CamadaAnim("musica", contribuicao_musica, mascara=MASCARA_MUSICA)
                )
            composed = MixerCamadas.compor(camadas)

        apenas_pernas = bool(acao_frame is not None and acao_frame[3])
        eh_clipe_completo = eh_danca_emote or (acao_frame is not None and not apenas_pernas)
        if acao_frame is not None and not apenas_pernas:
            pose_a, _modo_g, _yaw_a, _ap_p, manter_door = acao_frame
            for grupo, rot in pose_a.items():
                if grupo in composed and not (manter_door and grupo == "door"):
                    composed[grupo] = rot
            if not manter_door and "door" in composed:
                composed["door"] = Rotation3()

        from sejoga.animacao.estados_delta import delta_conexao

        for grupo, extra in delta_conexao(self._estado_origem, self.state.value, self.state_time).items():
            atual = composed.get(grupo, Rotation3())
            composed[grupo] = Rotation3(atual.x + extra.x, atual.y + extra.y, atual.z + extra.z)

        # Inertialização quíntica, colisão e clamps delegados ao PoseResolver.
        # A colisão dos braços entra/sai por rampa suave (~0,38 s) para que a
        # entrada/saída de clipes retargetados ou cenas nunca dê estalo em 1 frame.
        alvo_colisao = (
            0.0
            if (
                self.state == AnimationState.DRAG
                or self.cena_idle_amostra.ativa
                or eh_clipe_completo
            )
            else 1.0
        )
        passo_colisao = max(0.0, dt) / 0.38 if dt > 0.0 else 1.0
        self._peso_colisao += max(
            -passo_colisao, min(passo_colisao, alvo_colisao - self._peso_colisao)
        )
        modelo_colisao = (
            self._collision_model if self._peso_colisao > 1e-4 else None
        )
        self._pose = self.pose_resolver.resolver(
            dt, composed, model=modelo_colisao, peso_colisao=self._peso_colisao,
        )
        displayed_pose = self.hand_motion.apply(
            self._pose,
            dt,
            self.state.value,
            ativo=not (eh_clipe_completo or self.cena_idle_amostra.ativa),
        )
        # O atraso tátil das cadeias entra e sai por rampa (~0,2 s): ligar em degrau
        # somava o lag acumulado de uma reação rápida num único quadro (estalo).
        alvo_tatil = 1.0 if self.state in (AnimationState.DRAG, AnimationState.FALL) else 0.0
        passo_tatil = max(0.0, dt) / 0.2
        self._peso_tatil += max(-passo_tatil, min(passo_tatil, alvo_tatil - self._peso_tatil))
        displayed_pose = self._aplicar_interacao(displayed_pose, dt, self._peso_tatil)
        self.rig.current = dict(displayed_pose)
        roubo_em_movimento = (
            self.state == AnimationState.TEIMOSIA
            and self._teimosia_fase == "roubo"
            and abs(velocity[0]) > 40.0
        )
        estado_pernas = (
            AnimationState.RUN.value
            if roubo_em_movimento
            else AnimationState.WALK.value
            if amostra_olhar.ativo and amostra_olhar.em_passo
            else self.state.value
        )
        vel_pernas = (
            (160.0 * self.pacote_olhar_tela.lado, 0.0)
            if amostra_olhar.ativo and amostra_olhar.em_passo
            else velocity
        )
        tempo_pernas = (
            self._idle_clock
            if self.state in (AnimationState.IDLE, AnimationState.HOVER)
            else self.state_time
            if self.state in (AnimationState.DRAG, AnimationState.SLEEP, AnimationState.FALL, AnimationState.LAND)
            else self._reaction_time
        )
        self.leg_motion.update(
            dt,
            estado_pernas,
            vel_pernas,
            tempo_pernas,
            self.body_motion.snapshot.limb_swing
            if dragging
            else self.body_motion.snapshot.roll
            + degrees(displayed_pose.get("body", Rotation3()).z) * 0.85,
            dance_phase=(
                self.dance_motion.style_beats * 6.28318530718
                if self.dance_motion.style == "breakdance"
                else self.dance_motion.phase
            ),
            dance_strength=self.dance_motion.strength,
            dance_style=self.dance_motion.style,
            dance_time=self.dance_motion.tempo_clipe,
            modo_sono=self.modo_sono,
            grab_part=grab_part,
            heavy_land=self._land_heavy,
            roll=self.body_motion.snapshot.roll,
            roll_velocity=self.body_motion.snapshot.roll_velocity,
            pixels_per_unit=pixels_per_unit,
            reaction_part=self._reaction_part,
            acao_canais=self._canais_pernas_acao,
            acao_nome=self._acao_clipe_nome,
            cena_nome=self.cena_idle_amostra.nome if self.cena_idle_amostra.ativa else "",
            cena_pernas=self.cena_idle_amostra.pernas_graus if self.cena_idle_amostra.ativa else None,
            teimosia_fase=self._teimosia_fase,
            reaction_direction=self._reaction_direction,
        )
        return displayed_pose

    def _aplicar_interacao(
        self, pose: dict[str, Rotation3], dt: float, peso: float
    ) -> dict[str, Rotation3]:
        """Camada 'interacao': soma o atraso das cadeias dos braços à pose.

        Cada cadeia persegue, por mola, os alvos autorais da pose composta
        (``self._pose``, em radianos). O follow-through aditivo por junta é a
        diferença entre a saída atrasada da cadeia e o alvo, deixando a ponta
        (antebraço/mão/dedos) arrastar atrás da base do braço. Isso soma sobre
        o follow-through já aplicado por hand_motion.
        """
        resultado = dict(pose)
        for cadeia in (
            self.cadeia_direita,
            self.cadeia_esquerda,
            self.cadeia_fone_direito,
            self.cadeia_fone_esquerdo,
            self.cadeia_coluna,
        ):
            alvos = {
                grupo: self._pose[grupo]
                for grupo in cadeia.cadeia
                if grupo in self._pose
            }
            if not alvos:
                continue
            saida = cadeia.atualizar(dt, alvos)
            for grupo, atrasada in saida.items():
                if grupo not in resultado:
                    continue
                alvo = alvos[grupo]
                base = resultado[grupo]
                resultado[grupo] = Rotation3(
                    base.x + (atrasada.x - alvo.x) * peso,
                    base.y + (atrasada.y - alvo.y) * peso,
                    base.z + (atrasada.z - alvo.z) * peso,
                )
        return resultado

    def _aplicar_mao_gesto(self) -> None:
        """Posiciona braços e mãos para gestos de interação não migrados."""
        if self.state in (AnimationState.OPEN_HANDS, AnimationState.CLOSE_FISTS):
            palma_aberta = self.state == AnimationState.OPEN_HANDS
            for lado, mao, dedos, sinal in (
                ("right", "hand", "fingers", 1),
                ("left", "hand2", "fingers2", -1),
            ):
                for grupo, (x, y, z) in braco_hpr_graus(lado, "interaction").items():
                    self.rig.set_rotation(grupo, x=x, y=y, z=z)
                self.rig.set_rotation(
                    mao,
                    x=36 if palma_aberta else -16,
                    y=-sinal * 18.0,
                    z=sinal * 6,
                )
                self.rig.set_rotation(dedos)
            return
        pose_idle(self.rig, self.clock, self.idle_personality)
        rot_braco, z_ant = _GESTOS_MAO_DIREITA[self.state.value]
        self.rig.set_rotation("right-arm", x=rot_braco[0], y=rot_braco[1], z=rot_braco[2])
        self.rig.set_rotation("ant-arm", x=-12.0, z=z_ant)
        self.rig.set_rotation("hand", x=0.0, y=-14.0, z=-10.0)
        self.rig.set_rotation("fingers", z=0)
        if self._gesto_mao_esquerda in _GESTOS_MAO_DIREITA:
            rot_esq, z_ant_esq = _GESTOS_MAO_DIREITA[self._gesto_mao_esquerda]
            self.rig.set_rotation(
                "left-arm", x=rot_esq[0], y=-rot_esq[1], z=-rot_esq[2]
            )
            self.rig.set_rotation("ant-arm2", x=-12.0, z=-z_ant_esq)
            self.rig.set_rotation("hand2", x=0.0, y=14.0, z=10.0)
            self.rig.set_rotation("fingers2", z=0)

    def _aplicar_cena_nao_migrada(self) -> None:
        """Aplica danças, memes e reações especiais ainda não migrados para deltas."""
        if self.state == AnimationState.DANCE:
            self.rig.current = dict(self.dance_motion.contribuicao(self.rig))
        elif self.state == AnimationState.BLUE_BALLS:
            pose_blue_balls(self.rig, self._reaction_time)
        elif self.state == AnimationState.VIRTUAL_INSANITY:
            pose_virtual_insanity(
                self.rig, self._reaction_time, self._reaction_direction
            )
        elif self.state == AnimationState.SNEEZE:
            pose_sneeze(self.rig, self._reaction_time)
        elif self.state == AnimationState.TEIMOSIA:
            aplicar_pose_teimosia(self.rig, self._reaction_time, self._look_direction)
        elif self.state in (AnimationState.HIT, AnimationState.POKE):
            aplicar_defesa(
                self.rig, self._reaction_time,
                duracoes_reacoes().get(self.state.value, self.REACTION_SECONDS[self.state]),
                self._reaction_direction, impacto=self.state == AnimationState.HIT,
                firmeza=self._defesa_firmeza,
            )
        elif self.state in (
            AnimationState.WAVE,
            AnimationState.STRETCH,
            AnimationState.PEEK,
        ):
            pose_flourish(self.rig, self.state.value, self._reaction_time)
        elif self.state in self.REACTION_SECONDS:
            pose_interaction(
                self.rig,
                self.state.value,
                self._reaction_time,
                self._look_direction,
                self._look_vertical,
                part=self._reaction_part,
                heavy=(self.state == AnimationState.LAND and self._land_heavy),
            )

    def _pose_nao_migrada(
        self, *, dragging: bool, eh_danca_emote: bool
    ) -> dict[str, Rotation3]:
        """Calcula a pose absoluta para estados ainda fora do LayerStack."""
        if (
            self.state in (AnimationState.OPEN_HANDS, AnimationState.CLOSE_FISTS)
            or self.state.value in _GESTOS_MAO_DIREITA
        ):
            self._aplicar_mao_gesto()
        else:
            self._aplicar_cena_nao_migrada()
        if not eh_danca_emote:
            pose_secondary(
                self.rig,
                self.clock,
                self.state.value,
                self.idle_personality,
            )
        if not dragging and self._release_time < 0.9:
            pose_throw_release(self.rig, self._release_time, self._release_grip)
        return self.rig.pose()

    def _encerrar_teimosia(self) -> None:
        self._reaction = None
        self.agencia.interrupcoes.resetar()
        self.agencia._teimosia_ativa = False
        self.agencia._teimosia_nivel = 0.0
        self._teimosia_fase = "resistencia"

    @staticmethod
    def _blend(start: Rotation3, end: Rotation3, amount: float) -> Rotation3:
        inverse = 1.0 - amount
        return Rotation3(
            x=start.x * inverse + end.x * amount,
            y=start.y * inverse + end.y * amount,
            z=start.z * inverse + end.z * amount,
        )

    def _delta_do_estado(
        self,
        state: AnimationState,
        t: float,
        velocity: tuple[float, float],
        grab_part: str,
    ) -> dict[str, Rotation3]:
        """Produz o delta do estado atual via funções delta_*.

        Cada delta retorna apenas a diferença sobre a pose base, não a pose
        absoluta. Estados não migrados retornam delta vazio.
        """
        motion = self.body_motion.snapshot

        if state == AnimationState.IDLE:
            repouso = delta_idle(
                t,
                self.idle_personality,
                self.respiracao_valor,
                look_direction=self._look_direction,
                look_vertical=self._look_vertical,
                torso_look_direction=self._idle_torso_look_dir,
                torso_look_vertical=self._idle_torso_look_vert,
            )
            firmeza = suavizar_quintico(self._peso_indignacao)
            return somar_deltas(repouso, {
                "peitoral": Rotation3(x=radians(5.0 * firmeza)),
                "head": Rotation3(
                    x=radians(9.0 * firmeza), z=radians(-4.0 * self._look_direction * firmeza)
                ),
            })
        if state == AnimationState.HOVER:
            return delta_hover(
                t,
                self.idle_personality,
                self.respiracao_valor,
                look_direction=self._look_direction,
                look_vertical=self._look_vertical,
                torso_look_direction=self._idle_torso_look_dir,
                torso_look_vertical=self._idle_torso_look_vert,
            )
        if state == AnimationState.DRAG:
            return delta_drag(motion, grab_part, self.drag_intensity)
        if state in (AnimationState.WALK, AnimationState.RUN):
            return delta_walk(self.leg_motion.phase, run=state == AnimationState.RUN)
        if state == AnimationState.FALL:
            return delta_fall(self.state_time, velocity)
        if state == AnimationState.SLEEP:
            return delta_sleep(t, self.modo_sono)
        # Estados não migrados: delta vazio (usa pose legada)
        return {}

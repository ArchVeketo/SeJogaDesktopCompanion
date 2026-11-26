"""Controlador procedural de animação do mascote.

As poses são produzidas pelo rig sem depender de clipes exportados. O
controlador escolhe um estado a partir da interação/física e faz crossfade
entre poses para evitar saltos bruscos.
"""

from __future__ import annotations

import random
from enum import StrEnum
from math import degrees, exp, pi, radians, sin, tau
from typing import ClassVar

from sejoga.animacao import movimento_corpo_tuning as tune
from sejoga.animacao.agencia import Agencia, Humor, MetaTipo
from sejoga.animacao.antenas_expressivas import (
    _HUMOR_ANTENAS,
    _HUMOR_POSTURA,
    delta_expressao_viva,
)
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
    delta_conexao,
    delta_drag,
    delta_fall,
    delta_fisica,
    delta_hover,
    delta_idle,
    delta_indignacao,
    delta_jump,
    delta_secundario,
    delta_sit,
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
from sejoga.animacao.diretor_cenas import metadados_cena
from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.molas_juntas import (
    CADEIA_CABECA,
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
    pose_goku_teleport,
    pose_idle,
    pose_interaction,
    pose_secondary,
    pose_sneeze,
    pose_throw_release,
    pose_virtual_insanity,
)
from sejoga.animacao.resolvedor_poses import PoseResolver
from sejoga.animacao.respiracao import (
    Respiracao,
    amostrar_respiracao_cascata,
    avancar_fase_respiracao,
)
from sejoga.animacao.ritmo_humano import RitmoHumano
from sejoga.animacao.selecao_estado import escolher_estado
from sejoga.animacao.sono_tuning import SONO_TRANSICAO_S
from sejoga.animacao.teimosia_pose import (
    aplicar_fase as aplicar_pose_teimosia,
)

_LOCOMOCAO_CLIPES_SEM_VEL_EXTRA = frozenset(
    {
        "walk_standard",
        "run_mixamo",
        "walk_strafe_slow",
        "walk_strafe_left",
        "walk_strafe_right",
    }
)
_CENAS_COMPATIVEL_SENTADO = frozenset(
    {
        "conferir_luva",
        "pensar_gabinete",
        "checar_walkman",
        "alongar_pescoco_ombros",
        "escutar_fone",
        "batida_guardada",
        "conferir_estilo",
        "ajeitar_fone",
        "disfarcar_olhar",
        "argolas_antena",
        "fone_com_problema",
        "finger_guns_camera",
    }
)
from sejoga.animacao.idles_autorais import dedos_idle_autoral, pernas_idle_autoral
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
    JUMP = "jump"
    SIT = "sit"
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
    GOKU_TELEPORT = "goku_teleport"
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
        AnimationState.JUMP,
        AnimationState.SIT,
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
        self._fase_respiracao = 0.0
        self.respiracao_valor = 0.0
        self._respiracao_cascata: tuple[float, float, float] | None = None
        self._look_antecipacao = 0.0
        self._vitoria_meta_idx = 0
        # v2.0 — Estado vivo contínuo: esforço físico (ofegante), tontura (sacudida/pouso) e troca de faixa
        self.esforco = 0.0
        self.tontura = 0.0
        self._ultima_faixa_musica = ""
        self._indice_cena_estilo = 0
        self._historico_cenas: list[str] = []
        self.ritmo = RitmoHumano()
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
        self._music_confirm_time = 0.0
        self._dance_decision_in = 0.0
        self._previous_beat = False
        self._dance_rng = random.Random()
        self.drag_intensity = 0.0
        self._release_time = 1.0
        self._release_grip = 0.0
        self._was_grounded: bool | None = None
        self._peak_fall_vy: float = 0.0
        self._pixels_per_unit: float = 216.8
        self._sitting: bool = False
        self._sit_locked: bool = False
        self._em_pulo: bool = False
        self._pulo_impulso_pendente: tuple[float, float] | None = None
        self._pulo_atraso_s: float = 0.0
        self._ultima_dir_caminhada: float = 1.0
        self._acao_fase_ciclo: float | None = None
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
        self.cadeia_cabeca = LagChain(CADEIA_CABECA)
        for _c in (
            self.cadeia_direita,
            self.cadeia_esquerda,
            self.cadeia_fone_direito,
            self.cadeia_fone_esquerdo,
            self.cadeia_coluna,
            self.cadeia_cabeca,
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
        self._giro_profundidade: float | None = None
        self.orientacao_manual: OrientacaoCorpo | None = None
        self.angulo_giro_pedido: float | None = None
        self.permitir_giro_costas: bool = False
        self._fonte_atencao: str | None = None

        # ── Sistema de agência (manifesto §4.1 — Camada 1) ──────────────
        self.agencia = Agencia()
        self._proximo_espirro_em: float = self._personality_rng.uniform(75.0, 145.0)
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
        self._humor_antenas_suave: tuple[float, float, float] = _HUMOR_ANTENAS[Humor.CALMO]
        self._humor_postura_suave: tuple[float, float, float] = _HUMOR_POSTURA[Humor.CALMO]
        self._dance_prev_override: str | None = None
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
        if self.dedos_clipe_acao is not None:
            return self.dedos_clipe_acao
        if self.state in (AnimationState.IDLE, AnimationState.HOVER):
            return dedos_idle_autoral(self.idle_personality.value, self._idle_clock)
        return None

    @property
    def gesto_mao_esquerda(self) -> str | None:
        """Gesto opcional ativo para a mão esquerda durante reação."""
        return self._gesto_mao_esquerda if self._reaction is not None else None

    def _especificacao_clipe_walk(
        self, vx: float, humor: Humor, irritado: bool
    ) -> tuple[str, bool, float, float, str, bool, bool]:
        """Escolhe a passada acoplada estritamente a velocidade / passo / pixels_per_unit."""
        avx = abs(vx)
        meta = self.agencia.meta_ativa
        fator_ppu = max(20.0, self._pixels_per_unit) / 216.8
        if avx < 88.0 and humor in (Humor.CURIOSO, Humor.DESCONFIADO):
            rate = max(0.42, min(1.30, avx / max(1.0, 72.0 * fator_ppu)))
            return ("walk_strafe_slow", vx < 0.0, rate, 0.0, "raiz", False, False)
        if (
            avx < 168.0
            and not irritado
            and meta is not None
            and meta.tipo == MetaTipo.PROCURAR_ATENCAO
        ):
            nome = "walk_strafe_left" if vx > 0.0 else "walk_strafe_right"
            rate = max(0.50, min(1.35, avx / max(1.0, 125.0 * fator_ppu)))
            return (nome, False, rate, 0.0, "raiz", False, False)
        step_len_walk = 4.0 * 0.192 * sin(radians(36.0))
        freq_nat_walk = (30.0 * 1.05) / 36.0
        rate = max(
            0.35,
            min(2.40, avx / max(1.0, step_len_walk * self._pixels_per_unit * freq_nat_walk)),
        )
        return ("walk_standard", False, rate, 0.0, "viagem", False, False)

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
            # Sprint inclui fase aérea no passo (~1.35x alcance) e limita rate<=1.75
            # para evitar aliasing (< 1 quadro do clipe por tick de 60 Hz).
            step_len_run = 1.35 * 4.0 * 0.192 * sin(radians(42.0))
            freq_nat_run = (30.0 * 1.05) / 17.0
            rate = max(
                0.75,
                min(
                    1.75,
                    abs(vx) / max(1.0, step_len_run * self._pixels_per_unit * freq_nat_run),
                ),
            )
            return ("run_mixamo", False, rate, 0.0, "viagem", False, False)
        if st == AnimationState.WALK:
            return self._especificacao_clipe_walk(vx, humor, irritado)
        if st == AnimationState.STRETCH:
            return ("arm_stretching", False, 1.0, 0.0, "raiz", False, False)
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
        self._acao_fase_ciclo = None

    def _tempo_inicial_clipe_acao(self, nome: str, clipe, inicio: float) -> float:
        """Preserva a fase da passada ao trocar entre clipes de caminhada/corrida."""
        anterior = self._acao_clipe_nome
        if anterior is None:
            return inicio
        mesmo_ciclo = (nome.startswith("walk_") and anterior.startswith("walk_")) or (
            nome in ("walk_standard", "run_mixamo")
            and anterior in ("walk_standard", "run_mixamo")
        )
        if not mesmo_ciclo:
            return inicio
        clipe_ant = carregar_clipe_acao(anterior)
        if not clipe_ant or not clipe_ant.quadros:
            return inicio
        fase = (self.acao_clipe_tempo * clipe_ant.fps) % len(clipe_ant.quadros)
        return inicio + fase / len(clipe_ant.quadros) * len(clipe.quadros) / clipe.fps

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
            tempo = self._tempo_inicial_clipe_acao(nome, clipe, inicio)
            if not apenas_pernas and self.pose_resolver._state_time > 1e-6:
                dur_clipe = (
                    0.38 if nome == "swimming" else (0.22 if nome.startswith("walk_") else 0.28)
                )
                self.pose_resolver.iniciar_transicao(
                    dict(self._pose),
                    transition_seconds=min(self.transition_seconds, dur_clipe),
                )
            self._acao_clipe_nome = nome
            self.acao_clipe_tempo = tempo
        else:
            fator_vel = (
                1.0
                if nome in _LOCOMOCAO_CLIPES_SEM_VEL_EXTRA
                else clipe.velocidade
            )
            self.acao_clipe_tempo += max(0.0, dt) * escala * fator_vel
        pose_clipe, pernas_clipe, dz, yaw_clipe, quat, dedos = amostrar_clipe_completo(
            clipe, self.acao_clipe_tempo, espelhar=espelhar
        )
        if nome in ("walk_standard", "run_mixamo") and clipe.quadros:
            ciclo_u = (self.acao_clipe_tempo * clipe.fps / len(clipe.quadros)) % 1.0
            self._acao_fase_ciclo = ciclo_u * tau
        else:
            self._acao_fase_ciclo = None
        self.raiz_quat_acao = None if apenas_pernas else quat
        self.dedos_clipe_acao = None if apenas_pernas else dedos
        self.dz_clipe_ativo = dz
        self._canais_pernas_acao = pernas_clipe
        return pose_clipe, modo_giro, yaw_clipe, apenas_pernas, manter_door

    def _preparar_acao_manual(
        self, *, levantar: bool = True, cancelar_danca: bool = True
    ) -> None:
        """Acorda/interrompe cenários automáticos para obedecer uma ação manual imediata."""
        self.idle_time = 0.0
        self._sleep_locked = False
        self._reaction = None
        self._cena_idle_nome = ""
        self._cena_idle_tempo = 0.0
        self._clipe_gltf_nome = ""
        if cancelar_danca:
            self._dance_preview_remaining = 0.0
            self._dance_remaining = 0.0
            self._music_grace = 0.0
        if levantar:
            self._sitting = False
            self._sit_locked = False
        if self.state == AnimationState.SLEEP or (
            levantar and self.state == AnimationState.SIT
        ):
            self.state = AnimationState.IDLE
            self.state_time = 0.0

    def converter_cacar_para_falha(self) -> None:
        """Troca ``cacar_cursor_sucesso`` para ``cacar_cursor_falha`` preservando o tempo."""
        if self._cena_idle_nome == "cacar_cursor_sucesso":
            self._cena_idle_nome = "cacar_cursor_falha"

    def iniciar_pacote_olhar_tela(self, lado: float | None = None) -> None:
        """Dispara o pacote 'Olhar a tela' (olhar por cima do ombro -> costas -> frente)."""
        self._preparar_acao_manual(levantar=True)
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
        self.pose_resolver.iniciar_transicao(dict(self._pose), transition_seconds=0.35)
        return True

    def parar_clipe_gltf(self) -> None:
        """Interrompe imediatamente qualquer clipe glTF em execução."""
        estava_ativo = bool(self._clipe_gltf_nome)
        self._clipe_gltf_nome = ""
        self._clipe_gltf_tempo = 0.0
        self.clipe_gltf_amostra = AmostraClipeGltf()
        self.clipe_gltf_eventos = ()
        if estava_ativo:
            self.pose_resolver.iniciar_transicao(dict(self._pose), transition_seconds=0.35)

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

    def _esta_de_costas(self) -> bool:
        """Indica se o mascote já está orientado de costas (~180°)."""
        return bool(
            self.orientacao_manual == OrientacaoCorpo.COSTAS
            or (
                self.angulo_giro_pedido is not None
                and abs(self.angulo_giro_pedido) >= 150.0
            )
            or (
                self._giro_profundidade is not None
                and abs(self._giro_profundidade) >= 150.0
            )
        )

    @property
    def em_passo_profundidade(self) -> bool:
        """Indica se o mascote está dando passos para virar ou caminhar em profundidade."""
        return bool(
            self.profundidade.em_caminhada
            or (
                self.pacote_olhar_tela.ativo
                and getattr(self.pacote_olhar_tela, "em_passo_atual", False)
            )
        )

    def definir_profundidade(self, nivel: NivelProfundidade | str) -> None:
        """Define o nível de profundidade visual (`perto`, `medio` ou `longe`) caminhando até lá."""
        self._preparar_acao_manual(levantar=True)
        novo = NivelProfundidade(nivel)
        atual = self.profundidade.nivel_alvo
        self._curiosidade_fundo_restante = 0.0
        self.profundidade.definir_nivel(novo)
        if novo != atual:
            ordem = (
                NivelProfundidade.PERTO,
                NivelProfundidade.MEDIO,
                NivelProfundidade.LONGE,
            )
            indo_fundo = ordem.index(novo) > ordem.index(atual)
            ja_alinhado = (
                self._esta_de_costas() if indo_fundo else not self._esta_de_costas()
            )
            self.profundidade.agendar_caminhada(
                atraso_giro_s=0.0 if ja_alinhado else 0.42,
                duracao_passo_s=0.95,
            )
            self._giro_profundidade = 180.0 if indo_fundo else 0.0

    def caminhar_para_fundo(self) -> NivelProfundidade:
        """Vira de costas (se necessário) e caminha um nível para o fundo (`perto -> medio -> longe`)."""
        self._preparar_acao_manual(levantar=True)
        atual = self.profundidade.nivel_alvo
        ja_costas = self._esta_de_costas()
        alvo = self.profundidade.avancar_fundo()
        if alvo != atual:
            self.profundidade.agendar_caminhada(
                atraso_giro_s=0.0 if ja_costas else 0.42,
                duracao_passo_s=0.95,
            )
            self._giro_profundidade = 180.0
        return alvo

    def caminhar_para_frente(self) -> NivelProfundidade:
        """Vira para a frente (se necessário) e caminha um nível para a frente (`longe -> medio -> perto`)."""
        self._preparar_acao_manual(levantar=True)
        atual = self.profundidade.nivel_alvo
        ja_frente = not self._esta_de_costas()
        alvo = self.profundidade.avancar_frente()
        if alvo != atual:
            self.profundidade.agendar_caminhada(
                atraso_giro_s=0.0 if ja_frente else 0.42,
                duracao_passo_s=0.95,
            )
            self._giro_profundidade = 0.0
        return alvo

    def definir_orientacao(self, orientacao: OrientacaoCorpo | str | None) -> None:
        """Define a orientação manual do corpo (`frente`, `perfil`, `costas`) ou limpa."""
        if orientacao is None or OrientacaoCorpo(orientacao) == OrientacaoCorpo.FRENTE:
            self.orientacao_manual = None
            self.pacote_olhar_tela.interromper()
            return
        self.orientacao_manual = OrientacaoCorpo(orientacao)
        if self.orientacao_manual != OrientacaoCorpo.COSTAS:
            self.pacote_olhar_tela.interromper()

    def voltar_ao_plano(self) -> None:
        """Retorna imediatamente ao plano frontal (`perto` e `frente`)."""
        self._curiosidade_fundo_restante = 0.0
        self._giro_profundidade = None
        self.pacote_olhar_tela.interromper()
        self.orientacao_manual = None
        self.angulo_giro_pedido = 0.0
        self.permitir_giro_costas = False
        self.profundidade.definir_nivel(NivelProfundidade.PERTO)
        self.profundidade._atraso_s = 0.0
        self.profundidade._caminhando_s = 0.0

    def preview_dance(self, style, duration: float = 16.0):
        """Força a prévia de um estilo de dança por alguns segundos."""
        if style not in (
            "head_bob", "hip_hop", "rock", "breakdance",
            "street_groove", "graffiti_dance", "cyber_bounce",
            "walkman_shuffle", "funk_glide", "cyber_skank",
            *listar_clipes_emote(),
        ):
            return
        self._preparar_acao_manual(levantar=True, cancelar_danca=False)
        if self.state == AnimationState.DANCE:
            self.pose_resolver.iniciar_transicao(dict(self._pose), transition_seconds=0.65)
        if self._dance_preview_remaining <= 0.0:
            self._dance_prev_override = self.dance_motion.override
        self._cena_idle_nome = ""
        self._dance_preview_remaining = max(0.5, float(duration))
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
        self._sitting = False
        self._sit_locked = False
        self.state = AnimationState.SLEEP
        self.state_time = 0.0
        self.appendage_remaining = 0.0
        self.pose_resolver.iniciar_transicao(
            dict(self._pose), transition_seconds=SONO_TRANSICAO_S
        )

    def acordar(self) -> None:
        """Acorda o mascote e retorna ao idle."""
        self._sleep_locked = False
        self._sitting = False
        self._sit_locked = False
        if self.state == AnimationState.SLEEP:
            self.interact("wake")

    def sentar(self, *, manual: bool = True) -> None:
        """Faz Mário sentar acordado para descansar com olhar e respiração ativos."""
        self._preparar_acao_manual(levantar=False, cancelar_danca=True)
        self._sitting = True
        self._sit_locked = bool(manual)

    def levantar(self) -> None:
        """Faz Mário levantar de volta à postura em pé."""
        self._sitting = False
        self._sit_locked = False

    def alternar_sentado(self) -> bool:
        """Alterna entre sentado acordado e em pé, devolvendo o novo estado."""
        if self._sitting or self.state == AnimationState.SIT:
            self.levantar()
            return False
        self.sentar(manual=True)
        return True

    def pular(self, vx: float = 0.0, vy_impulse: float = -560.0) -> None:
        """Agenda um salto com breve antecipação de agachamento (0.11s) antes do impulso."""
        self._sleep_locked = False
        self._sitting = False
        self._sit_locked = False
        self._cena_idle_nome = ""
        self._reaction = None
        self._em_pulo = True
        self._pulo_impulso_pendente = (float(vx), float(vy_impulse))
        self._pulo_atraso_s = 0.11

    def consumir_impulso_pulo(self) -> tuple[float, float] | None:
        """Retorna ``(vx, vy_impulse)`` assim que a antecipação do salto termina."""
        if self._pulo_impulso_pendente is None or self._pulo_atraso_s > 0.0:
            return None
        impulso = self._pulo_impulso_pendente
        self._pulo_impulso_pendente = None
        return impulso

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
        AnimationState.GOKU_TELEPORT: 1.65,
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
                manter_sentado = (
                    self.state == AnimationState.SIT
                    and kind in _CENAS_COMPATIVEL_SENTADO
                )
                self._preparar_acao_manual(levantar=not manter_sentado)
                self._music_grace = 0.0
                self._cena_idle_nome = kind
                self._cena_idle_tempo = 0.0
                self._cena_idle_variante += 1
                self._dance_remaining = 0.0
                self.pose_resolver.iniciar_transicao(dict(self._pose), transition_seconds=0.18)
            return True
        if kind == "peek":
            if self.state == AnimationState.SLEEP:
                self._preparar_acao_manual(levantar=False)
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
            self._pos_atividade_pendente = self._sortear_cena_sem_repetir(
                ("conferir_luva", "alongar_pescoco_ombros", "ajeitar_fone", "conferir_estilo")
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

    def notificar_sacudida(self) -> None:
        """Ativa tontura após o usuário sacudir Mário no ar (v2.0)."""
        self.tontura = 1.0
        self.agencia.registrar_interacao_negativa(0.55)
        self.respiracao.empurrar(0.45)

    def notificar_faixa_musica(self, chave_faixa: str) -> None:
        """Ao trocar de música no player, dispara checagem do Walkman se estiver em repouso."""
        if not chave_faixa or chave_faixa == self._ultima_faixa_musica:
            return
        anterior = self._ultima_faixa_musica
        self._ultima_faixa_musica = chave_faixa
        if not anterior:
            return
        if (
            self.state in (AnimationState.IDLE, AnimationState.HOVER)
            and not self._cena_idle_nome
            and self._reaction is None
            and self.clock >= self._cooldowns.get("cena_contextual", 0.0)
        ):
            self.interact("checar_walkman")
            self._cooldowns["cena_contextual"] = self.clock + 24.0

    def _sortear_cena_sem_repetir(self, opcoes: tuple[str, ...]) -> str:
        """Escolhe uma cena evitando repetir qualquer uma das últimas 4 executadas."""
        if not opcoes:
            return ""
        recentes = set(self._historico_cenas[-4:])
        disponiveis = [c for c in opcoes if c not in recentes]
        if not disponiveis:
            ultimo = self._historico_cenas[-1] if self._historico_cenas else ""
            disponiveis = [c for c in opcoes if c != ultimo] or list(opcoes)
        escolhida = self._personality_rng.choice(disponiveis)
        self._historico_cenas.append(escolhida)
        if len(self._historico_cenas) > 12:
            self._historico_cenas = self._historico_cenas[-12:]
        return escolhida

    def escolher_cena_pos_caminhada(self) -> str:
        """Escolhe uma reação/cena variada ao chegar ao destino de uma caminhada."""
        return self._sortear_cena_sem_repetir(
            (
                "olhar_curioso_chao",
                "conferir_estilo",
                "conferir_luva",
                "pensar_gabinete",
                "ajeitar_fone",
                "checar_walkman",
            )
        )

    def escolher_vitoria_meta(self) -> tuple[str, str | None]:
        """Alterna celebração de conquista entre comemoração e mini-danças variadas."""
        opcoes: tuple[tuple[str, str | None], ...] = (
            ("celebrate", None),
            ("dance", "hip_hop"),
            ("dance", "celebration_dance"),
            ("celebrate", None),
            ("dance", "street_groove"),
            ("dance", "boogie_down"),
            ("dance", "jazz_dance"),
            ("dance", "electro_swing"),
        )
        escolha = opcoes[self._vitoria_meta_idx % len(opcoes)]
        self._vitoria_meta_idx += 1
        return escolha

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
        """Seleciona a próxima cena contextual com variedade real e anti-repetição."""
        if musica_comecou and react_to_beat and music_intensity > 0.01:
            if music_intensity > 0.32:
                return (
                    self._sortear_cena_sem_repetir(
                        ("escutar_fone", "groove_um_pe", "bater_pe_ritmo", "solo_guitarra_ar", "checar_walkman")
                    ),
                    34.0,
                )
            opcoes = (
                "batida_guardada",
                "bater_pe_ritmo",
                "checar_walkman",
                "groove_um_pe",
                "escutar_fone",
                "ajeitar_fone",
            )
            return (self._sortear_cena_sem_repetir(opcoes), 32.0)

        if (
            not musica_comecou
            and music_playing
            and react_to_beat
            and 0.01 < music_intensity <= 0.35
            and self._tempo_musica_discreta >= 8.0
            and self._dance_remaining <= 0.0
        ):
            opcoes = (
                "batida_guardada",
                "bater_pe_ritmo",
                "solo_guitarra_ar",
                "checar_walkman",
                "groove_um_pe",
                "escutar_fone",
                "ajeitar_fone",
            )
            return (self._sortear_cena_sem_repetir(opcoes), 30.0)

        if cursor_retornou and not music_playing:
            return (
                self._sortear_cena_sem_repetir(
                    ("finger_guns_camera", "disfarcar_olhar", "segurar_porta_timido", "conferir_estilo")
                ),
                34.0,
            )

        if (
            hovered
            and not music_playing
            and self._hover_sem_clique_tempo >= 3.2
            and self.clock >= self._cooldowns.get("cena_cursor_interativa", 0.0)
        ):
            self._hover_sem_clique_tempo = 0.0
            if (
                self.agencia.humor_atual in (Humor.BRINQUEDOIRO, Humor.TEIMOSO)
                and self.clock >= self._cooldowns.get("roubo_cursor_tentaculo", 0.0)
                and self._personality_rng.random() < 0.28
            ):
                self._cooldowns["roubo_cursor_tentaculo"] = self.clock + 125.0
                self._cooldowns["cena_cursor_interativa"] = self.clock + 65.0
                return ("roubo_cursor_tentaculo", 42.0)
            self._cooldowns["cena_cursor_interativa"] = self.clock + 58.0
            return ("cacar_cursor_sucesso", 36.0)

        if not hovered and not music_playing and self._passou_perto_restante > 0.0:
            if (
                self.clock >= self._cooldowns.get("cena_cursor_interativa", 0.0)
                and self._personality_rng.random() < 0.38
            ):
                self._cooldowns["cena_cursor_interativa"] = self.clock + 52.0
                return (
                    self._sortear_cena_sem_repetir(("cacar_cursor_falha", "cacar_cursor_sucesso")),
                    34.0,
                )
            opcoes = ("segurar_porta_timido", "disfarcar_olhar", "finger_guns_camera", "conferir_estilo", "ajeitar_fone")
            return (self._sortear_cena_sem_repetir(opcoes), 30.0)

        if (
            not music_playing
            and self._pos_atividade_pendente
            and self._tempo_assentado_idle >= 1.2
        ):
            cena = self._pos_atividade_pendente
            self._historico_cenas.append(cena)
            self._indice_pos_atividade += 1
            return (cena, 28.0)

        if not music_playing and not self._pos_atividade_pendente and self._pensamento_janela_restante > 0.0:
            opcoes_cur = (
                "pensar_gabinete",
                "olhar_curioso_chao",
                "tentaculo_fujao",
                "conferir_luva",
                "ajeitar_fone",
                "argolas_antena",
            )
            return (self._sortear_cena_sem_repetir(opcoes_cur), 32.0)

        # Cenas espontâneas guiadas pelo humor vivo (todas as cenas alcançáveis sem repetição!)
        if not music_playing and not hovered:
            humor = self.agencia.humor_atual
            if humor == Humor.TEDIOSO and self.idle_time >= 16.0:
                opcoes_tedio = (
                    "bater_pe_impaciente",
                    "tentaculo_fujao",
                    "espreguicar_pesado",
                    "alongar_pescoco_ombros",
                    "fone_com_problema",
                    "checar_walkman",
                    "olhar_curioso_chao",
                    "argolas_antena",
                )
                return (self._sortear_cena_sem_repetir(opcoes_tedio), 34.0)
            if humor == Humor.BRINQUEDOIRO and self.idle_time >= 8.0:
                opcoes_play = (
                    "finger_guns_camera",
                    "bater_pe_ritmo",
                    "solo_guitarra_ar",
                    "cuspir_item",
                    "conferir_estilo",
                    "conferir_luva",
                    "groove_um_pe",
                    "argolas_antena",
                )
                return (self._sortear_cena_sem_repetir(opcoes_play), 28.0)
            if humor == Humor.DESCONFIADO and self.idle_time >= 10.0:
                opcoes_desc = (
                    "tentaculo_fujao",
                    "bater_pe_impaciente",
                    "disfarcar_olhar",
                    "olhar_curioso_chao",
                    "segurar_porta_timido",
                    "pensar_gabinete",
                )
                return (self._sortear_cena_sem_repetir(opcoes_desc), 30.0)
            if humor in (Humor.CALMO, Humor.CURIOSO) and self.idle_time >= 22.0:
                opcoes_calmo = (
                    "bater_pe_ritmo",
                    "tentaculo_fujao",
                    "finger_guns_camera",
                    "ajeitar_fone",
                    "checar_walkman",
                    "conferir_estilo",
                    "conferir_luva",
                    "pensar_gabinete",
                    "alongar_pescoco_ombros",
                    "espreguicar_pesado",
                    "fone_com_problema",
                    "argolas_antena",
                )
                return (self._sortear_cena_sem_repetir(opcoes_calmo), 36.0)

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
        sem_cooldown = (
            "blue_balls",
            "virtual_insanity",
            "goku_teleport",
            "peace",
            "open_hands",
            "hit",
            "wake",
        )
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
        if kind == "goku_teleport" and left_gesture is None:
            self._gesto_mao_esquerda = "close_fists"
        else:
            self._gesto_mao_esquerda = (
                left_gesture
                if (
                    left_gesture in _GESTOS_MAO_DIREITA
                    or left_gesture in ("open_hands", "close_fists")
                )
                else None
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
        if self._land_heavy:
            self.tontura = max(self.tontura, min(1.0, (strength - 1.1) * 0.9))
        self._defesa_firmeza = max(0.0, min(1.0, 0.5 * strength + 0.5 * ja_irritado))
        self._reaction_direction = 1.0 if dir_ref >= 0.0 else -1.0
        if self.state == self._reaction and self._pose:
            janela = (
                min(self.transition_seconds, 0.10)
                if self._reaction == AnimationState.HIT
                else min(self.transition_seconds, 0.22)
            )
            self.pose_resolver.iniciar_transicao(
                dict(self._pose), transition_seconds=janela
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
        sitting: bool = False,
        jumping: bool = False,
    ) -> AnimationState:
        return escolher_estado(
            speed=speed,
            grounded=grounded,
            gravity_active=gravity_active,
            dragging=dragging,
            music_playing=music_playing,
            music_intensity=music_intensity,
            current_state=current_state,
            sitting=sitting,
            jumping=jumping,
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
        music_entry_debounce_s: float = 0.0,
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
        height_above_floor_px: float = 0.0,
    ) -> dict[str, Rotation3]:
        """Atualiza o estado e devolve um snapshot de rotações em radianos."""
        dt = min(0.1, max(0.0, dt))
        self._pixels_per_unit = max(20.0, float(pixels_per_unit))
        if self._pulo_atraso_s > 0.0:
            self._pulo_atraso_s = max(0.0, self._pulo_atraso_s - dt)
        if self._em_pulo:
            if dragging:
                self._em_pulo = False
                self._pulo_impulso_pendente = None
                self._pulo_atraso_s = 0.0
            elif (not grounded and velocity[1] >= 25.0) or (
                grounded
                and self._pulo_impulso_pendente is None
                and self._pulo_atraso_s <= 0.0
                and self.state == AnimationState.JUMP
                and self.state_time > 0.14
            ):
                self._em_pulo = False
        if self._dance_preview_remaining > 0:
            self._dance_preview_remaining = max(0.0, self._dance_preview_remaining - dt)
            if self._dance_preview_remaining > 0.0:
                music_playing = react_to_beat = True
                dance_chance = 1.0
                clipe_previa = (
                    carregar_clipe_emote(self._dance_preview_style)
                    if self._dance_preview_style != "head_bob"
                    else None
                )
                music_intensity, music_bass, music_bpm = {
                    "head_bob": (0.42, 0.20, 102),
                    "hip_hop": (0.5, 0.3, 95),
                    "rock": (0.6, 0.15, 135),
                    "breakdance": (0.9, 0.6, 145),
                    "street_groove": (0.65, 0.4, 108),
                    "graffiti_dance": (0.55, 0.25, 100),
                    "cyber_bounce": (0.75, 0.5, 124),
                    "walkman_shuffle": (0.62, 0.35, 106),
                    "funk_glide": (0.70, 0.45, 114),
                    "cyber_skank": (0.82, 0.55, 128),
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
            else:
                self.dance_motion.override = self._dance_prev_override
                self._dance_preview_style = ""
                self._dance_remaining = 0.0
        self.clock += dt
        self.delta_time = dt
        if music_playing:
            self._music_confirm_time = min(10.0, self._music_confirm_time + dt)
        elif self._music_grace <= 0.0:
            self._music_confirm_time = 0.0
        music_confirmada = music_playing and (
            self._dance_preview_remaining > 0.0
            or self._music_grace > 0.0
            or self._music_confirm_time >= max(0.0, music_entry_debounce_s)
        )
        musica_comecou = music_confirmada and self._music_grace <= 0.0
        self._music_grace = 0.65 if music_confirmada else max(0.0, self._music_grace - dt)
        music_playing = self._music_grace > 0
        self.music_active = music_playing
        giro_norm = ((float(self.angulo_giro_pedido or 0.0) + 180.0) % 360.0) - 180.0
        if self.orientacao_manual == OrientacaoCorpo.COSTAS or (
            self.permitir_giro_costas and abs(giro_norm) > 90.0
        ):
            look_direction = -look_direction
        if self.pacote_olhar_tela.ativo:
            look_direction = 0.0
            look_vertical *= 0.2
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
        self.ritmo.atualizar(dt)
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
            and self.state in (AnimationState.IDLE, AnimationState.HOVER, AnimationState.SIT)
            and abs(velocity[0]) < 75.0 and abs(velocity[1]) < 75.0
            and not self._sleep_locked and self._reaction is None
            and not self.ritmo.em_rebalanceio
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
            if cena and (
                self.state != AnimationState.SIT or cena in _CENAS_COMPATIVEL_SENTADO
            ):
                self.ritmo.sortear_intencao("calma")
                self.interact(cena)
                self._cooldowns["cena_contextual"] = self.clock + recarga
                self._tempo_musica_discreta = 0.0
                self._passou_perto_restante = 0.0
                self._hover_sem_clique_tempo = 0.0
                self._pos_atividade_pendente = ""
                self._tempo_assentado_idle = 0.0
                self._pensamento_janela_restante = 0.0
            elif (
                not music_playing
                and self.state == AnimationState.IDLE
                and self.idle_time >= 14.0
                and self.clock >= self._proximo_espirro_em
            ):
                # Causa física orgânica (poeira do gabinete / cócega na antena) em repouso quieto.
                self._proximo_espirro_em = self.clock + self._personality_rng.uniform(
                    85.0, 175.0
                )
                self.interact("sneeze")

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
        elif self._dance_remaining > 0.0:
            # v2.0: uma vez dançando, continua no groove enquanto a música tocar
            # (sem parar aleatoriamente no meio da faixa deixando a caixa sozinha!).
            self._dance_remaining = max(self._dance_remaining, 2.0)
        elif self._dance_decision_in == 0 and not self._cena_idle_nome:
            self._dance_decision_in = 6.0
            # Música animada ou chance alta engata a dança; se não rolar, fica no Idle Groove vivo!
            chance_efetiva = min(1.0, dance_chance + max(0.0, music_intensity - 0.45) * 0.45)
            if self._dance_rng.random() < chance_efetiva:
                self._dance_remaining = 10.0
        beat_edge = beat_detected and not self._previous_beat
        self._previous_beat = beat_detected
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
        alvo_look_dir = max(-1.0, min(1.0, look_direction))
        salto_look = alvo_look_dir - self._look_direction
        if abs(salto_look) > 0.45:
            self._look_antecipacao = -0.14 * (1.0 if salto_look > 0.0 else -1.0)
        else:
            self._look_antecipacao *= max(0.0, 1.0 - dt * 10.0)
        suave_cabeca = min(1.0, dt * 8.2)
        self._look_direction += salto_look * suave_cabeca
        self._look_vertical += (
            max(-1.0, min(1.0, look_vertical)) - self._look_vertical
        ) * min(1.0, dt * 6.4)
        # Tronco acompanha o olhar após breve contra-antecipação (princípios 2 e 5).
        alvo_tronco_dir = max(-1.0, min(1.0, self._look_direction + self._look_antecipacao))
        self._idle_torso_look_dir += (
            alvo_tronco_dir - self._idle_torso_look_dir
        ) * min(1.0, dt * 2.6)
        self._idle_torso_look_vert += (
            self._look_vertical - self._idle_torso_look_vert
        ) * min(1.0, dt * 2.8)
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
            and (
                self.state in (AnimationState.FALL, AnimationState.JUMP)
                or self._peak_fall_vy > 100.0
            )
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

        if (
            dragging
            or not grounded
            or self._em_pulo
            or abs(velocity[0]) > 45.0
            or (music_playing and self._dance_remaining > 0 and not self._cena_idle_nome)
        ):
            self._sitting = False
            self._sit_locked = False

        speed = (velocity[0] ** 2 + velocity[1] ** 2) ** 0.5
        next_state = self._choose_state(
            speed=speed,
            grounded=grounded,
            gravity_active=gravity_active,
            dragging=dragging,
            music_playing=music_playing and self._dance_remaining > 0 and not self._cena_idle_nome,
            music_intensity=music_intensity,
            current_state=self.state,
            sitting=self._sitting,
            jumping=self._em_pulo,
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
                    AnimationState.GOKU_TELEPORT,
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
            AnimationState.SIT,
            AnimationState.WAVE,
            AnimationState.STRETCH,
            AnimationState.PEEK,
        ):
            self.idle_time += dt
            limiar_sit = (
                max(28.0, float(sleep_after_idle_seconds) * 0.45)
                if sleep_after_idle_seconds >= 60
                else 36.0
            )
            if (
                not self._sitting
                and not music_playing
                and not hovered
                and next_state == AnimationState.IDLE
                and self.idle_time >= limiar_sit
                and (
                    sleep_after_idle_seconds <= 0
                    or self.idle_time < sleep_after_idle_seconds
                )
            ):
                self._sitting = True
                next_state = AnimationState.SIT
            if (
                sleep_after_idle_seconds > 0
                and self.idle_time >= sleep_after_idle_seconds
            ):
                self._sitting = False
                self._sit_locked = False
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
            rapida_s = {
                AnimationState.FALL: 0.12,
                AnimationState.HIT: 0.12,
                AnimationState.GOKU_TELEPORT: 0.12,
                AnimationState.SURPRISE: 0.12,
                AnimationState.LAND: 0.10,
                AnimationState.CLICK: 0.13,
                AnimationState.JUMP: 0.09,
                AnimationState.DRAG: 0.15,
                AnimationState.POKE: 0.14,
                AnimationState.CELEBRATE: 0.14,
                AnimationState.BLUE_BALLS: 0.15,
                AnimationState.VIRTUAL_INSANITY: 0.15,
            }.get(next_state)
            if rapida_s is not None:
                self.ritmo.sortear_intencao("impacto")
                self._active_transition_seconds = self.ritmo.duracao_transicao(rapida_s)
            else:
                calma = next_state in (AnimationState.IDLE, AnimationState.HOVER, AnimationState.SLEEP)
                self.ritmo.sortear_intencao("calma" if calma else "normal")
                base_tr = max(self.transition_seconds, 0.36) if calma else self.transition_seconds
                self._active_transition_seconds = self.ritmo.duracao_transicao(base_tr, calma=calma)

            if next_state == AnimationState.SLEEP:
                self._active_transition_seconds = self.ritmo.duracao_transicao(
                    max(self.transition_seconds, SONO_TRANSICAO_S), calma=True
                )
            elif next_state == AnimationState.WAKE:
                self._active_transition_seconds = self.ritmo.duracao_transicao(0.85, calma=True)
            elif (
                self.state in (AnimationState.HIT, AnimationState.POKE, AnimationState.LAND, AnimationState.TEIMOSIA, AnimationState.SURPRISE)
                and next_state in (AnimationState.IDLE, AnimationState.HOVER, AnimationState.WALK, AnimationState.RUN, AnimationState.DANCE)
            ):
                # Recuperação respirada e orgânica após impacto/reação + tempo de rebalanceio!
                self._active_transition_seconds = self.ritmo.duracao_transicao(0.68, calma=True)
                self.ritmo.iniciar_rebalanceio(1.45)
            elif (
                self.state in (AnimationState.WALK, AnimationState.RUN, AnimationState.DANCE, AnimationState.CELEBRATE)
                and next_state == AnimationState.IDLE
            ):
                self._active_transition_seconds = self.ritmo.duracao_transicao(0.72, calma=True)
                self.ritmo.iniciar_rebalanceio(1.25)
            elif (
                next_state in (AnimationState.HOVER, AnimationState.IDLE)
                and self.state in (AnimationState.HOVER, AnimationState.IDLE)
            ):
                self._active_transition_seconds = self.ritmo.duracao_transicao(0.46, calma=True)

            if self.state == AnimationState.DANCE and next_state != AnimationState.DANCE:
                self.dance_motion.resetar_suavizacao()
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
        alpha_humor = 1.0 - exp(-dt * 3.8) if dt > 0.0 else 1.0
        alvo_ant = _HUMOR_ANTENAS.get(self.agencia.humor_atual, (0.0, 0.0, 0.0))
        alvo_pos = _HUMOR_POSTURA.get(self.agencia.humor_atual, (0.0, 0.0, 0.0))
        self._humor_antenas_suave = (
            self._humor_antenas_suave[0] + (alvo_ant[0] - self._humor_antenas_suave[0]) * alpha_humor,
            self._humor_antenas_suave[1] + (alvo_ant[1] - self._humor_antenas_suave[1]) * alpha_humor,
            self._humor_antenas_suave[2] + (alvo_ant[2] - self._humor_antenas_suave[2]) * alpha_humor,
        )
        self._humor_postura_suave = (
            self._humor_postura_suave[0] + (alvo_pos[0] - self._humor_postura_suave[0]) * alpha_humor,
            self._humor_postura_suave[1] + (alvo_pos[1] - self._humor_postura_suave[1]) * alpha_humor,
            self._humor_postura_suave[2] + (alvo_pos[2] - self._humor_postura_suave[2]) * alpha_humor,
        )

        # v2.0 — Esforço físico (ofegante após corrida/dança/roubo) e decaimento de tontura
        em_esforco = self.state in (AnimationState.RUN, AnimationState.DANCE, AnimationState.TEIMOSIA)
        if em_esforco:
            self.esforco = min(1.0, self.esforco + dt * 0.28)
        else:
            self.esforco = max(0.0, self.esforco - dt * 0.19)
        if self.tontura > 0.0:
            self.tontura = max(0.0, self.tontura - dt * 0.28)

        self.rig.reset()
        em_repouso = idle_enabled and self.state in (
            AnimationState.IDLE,
            AnimationState.HOVER,
            AnimationState.SIT,
        )
        passo = dt / 0.55
        self._peso_repouso = (
            min(1.0, self._peso_repouso + passo)
            if em_repouso
            else max(0.0, self._peso_repouso - passo)
        )
        peso_repouso = suavizar_quintico(self._peso_repouso)
        humor_atual = self.agencia.humor_atual
        cadencia_resp = (
            0.78 if humor_atual == Humor.TEDIOSO
            else 1.18 if humor_atual in (Humor.INDIGNADO, Humor.TEIMOSO)
            else 1.08 if humor_atual == Humor.BRINQUEDOIRO
            else 1.0
        ) * self.ritmo.modulacao_respiracao(self.clock)
        self._fase_respiracao = avancar_fase_respiracao(
            self._fase_respiracao, dt, cadencia=cadencia_resp, esforco=self.esforco
        )
        ciclo_peito, ciclo_cab, ciclo_bra, ciclo_ant = amostrar_respiracao_cascata(
            self.clock,
            cadencia=cadencia_resp,
            esforco=self.esforco,
            fase_integrada=self._fase_respiracao,
        )
        impulso = self.respiracao.atualizar(dt)
        self.respiracao_valor = max(
            -1.0, min(1.0, ciclo_peito * peso_repouso + impulso)
        )
        self._respiracao_cascata = (
            max(-1.0, min(1.0, ciclo_cab * peso_repouso + impulso * 0.85)),
            max(-1.0, min(1.0, ciclo_bra * peso_repouso + impulso * 0.70)),
            max(-1.0, min(1.0, ciclo_ant * peso_repouso + impulso * 0.55)),
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
                if dragging:
                    self.profundidade.definir_nivel(NivelProfundidade.PERTO)
                else:
                    self.definir_profundidade(NivelProfundidade.PERTO)

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
                # Primeiro olha sobre o ombro (1.4s) e vira de costas dando passos (1.2s = 2.6s),
                # e só então caminha de costas para o plano de fundo sem deslizar!
                self.pacote_olhar_tela.iniciar(lado=lado_olhar, caminhar_no_fundo=True)
                self.profundidade.avancar_fundo()
                self.profundidade.agendar_caminhada(
                    atraso_giro_s=2.6,
                    duracao_passo_s=1.15,
                )
                self._giro_profundidade = 180.0 * lado_olhar
                self._curiosidade_fundo_restante = 16.0
            else:
                self.iniciar_pacote_olhar_tela(lado=lado_olhar)
            amostra_olhar = self.pacote_olhar_tela.atualizar(0.0)

        # Quando o personagem estiver de costas e se mover, caminha em direção ao fundo da tela!
        if (
            not dragging
            and grounded
            and self.orientacao_manual == OrientacaoCorpo.COSTAS
            and self.state in (AnimationState.WALK, AnimationState.RUN)
            and self.profundidade.nivel_alvo == NivelProfundidade.PERTO
        ):
            self.caminhar_para_fundo()

        if not self.profundidade.em_caminhada:
            self._giro_profundidade = None

        acao_frame = self._resolver_acao_frame(dt, velocity, speed)

        if dragging:
            self.angulo_giro_pedido = None
            self.permitir_giro_costas = False
            self._giro_profundidade = None
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
        elif self._giro_profundidade is not None and self.profundidade.em_caminhada:
            self.angulo_giro_pedido = self._giro_profundidade
            self.permitir_giro_costas = abs(self._giro_profundidade) >= 150.0
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
            self._ultima_dir_caminhada = 1.0 if velocity[0] > 0.0 else -1.0
            self.angulo_giro_pedido = 90.0 * self._ultima_dir_caminhada
            self.permitir_giro_costas = False
        elif (
            self.state in (AnimationState.IDLE, AnimationState.HOVER)
            and self.leg_motion.em_freada
        ):
            self.angulo_giro_pedido = 90.0 * self._ultima_dir_caminhada
            self.permitir_giro_costas = False
        elif self.state in (AnimationState.IDLE, AnimationState.HOVER):
            alvo_34 = 8.5 * sin(self._idle_clock * 0.14 + 0.5) + self._look_direction * 3.5
            self.angulo_giro_pedido = max(-10.0, min(10.0, alvo_34))
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
        if self._peso_indignacao > 0.005:
            delta_estado = somar_deltas(
                delta_estado,
                delta_indignacao(
                    self._idle_clock, suavizar_quintico(self._peso_indignacao)
                ),
            )
        # Soltura: os dedos abrem além do ponto ao largar (aditivo, fecha em 0).
        if delta_estado and not dragging and self.state != AnimationState.DRAG:
            delta_estado = somar_deltas(
                delta_estado, delta_soltura(self._release_time, self._release_grip)
            )
        cena_permitida_no_estado = (
            self.state in (AnimationState.IDLE, AnimationState.HOVER)
            or (
                self.state == AnimationState.SIT
                and self._cena_idle_nome in _CENAS_COMPATIVEL_SENTADO
            )
        )
        if cena_permitida_no_estado and self._cena_idle_nome:
            cena_anterior_ativa = self.cena_idle_amostra.ativa
            ritmo_cena = (
                max(0.8, min(1.3, music_bpm / 100.0))
                if self._cena_idle_nome in ("batida_guardada", "checar_walkman", "groove_um_pe")
                and music_bpm
                else self.ritmo.escala_velocidade
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
                self.ritmo.iniciar_rebalanceio(1.6)
                if cena_anterior_ativa and self.pose_resolver._state_time > 1e-6:
                    self.pose_resolver.iniciar_transicao(
                        dict(self._pose),
                        transition_seconds=self.ritmo.duracao_transicao(0.58, calma=True),
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
        passo_prof_ativo = bool(
            (amostra_olhar.ativo and amostra_olhar.em_passo)
            or self.profundidade.em_caminhada
        )
        if passo_prof_ativo and self.state in (AnimationState.IDLE, AnimationState.HOVER):
            # Balanço natural de caminhada nos braços, ombros e tronco durante passos de giro/profundidade!
            delta_marcha_prof = delta_walk(self.leg_motion.phase, run=False)
            delta_estado = somar_deltas(delta_estado, delta_marcha_prof)

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

            delta_sec = delta_secundario(
                relogio_sec,
                self.state.value,
                self.idle_personality,
                delta_estado,
            )
            if self.cena_idle_amostra.ativa and self.cena_idle_amostra.delta_rig:
                # A cena dirigida já traz overlap e hold vivo próprios: a camada
                # secundária cai a 12% nas juntas autorais para não brigar com a
                # coreografia (era 28%, o que borrava ataques e assentos).
                fator_sec = (
                    max(0.12, 1.0 - 0.88 * min(1.0, self.cena_idle_amostra.peso_mistura))
                    if self.cena_idle_amostra.peso_mistura > 0.0
                    else 0.12
                )
                for grp in self.cena_idle_amostra.delta_rig:
                    if grp in delta_sec:
                        r = delta_sec[grp]
                        delta_sec[grp] = Rotation3(
                            r.x * fator_sec, r.y * fator_sec, r.z * fator_sec
                        )

            # Camada secundária (follow-through de coluna, fones, antenas, ombros e mãos)
            self.layer_stack.set_camada(
                CamadaDelta(
                    nome="secundario",
                    prioridade=Prioridade.FOLLOW_THROUGH,
                    delta=delta_sec,
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
            # v2.0: preserva olhar vivo na cabeça durante caminhada/corrida (Mário não fica "cego" andando!).
            if self.state in (AnimationState.WALK, AnimationState.RUN) and "head" in composed:
                h = composed["head"]
                composed["head"] = Rotation3(
                    h.x + radians(-self._look_vertical * 8.0),
                    h.y + radians(self._look_direction * 14.0),
                    h.z,
                )

        for grupo, extra in delta_conexao(self._estado_origem, self.state.value, self.state_time).items():
            atual = composed.get(grupo, Rotation3())
            composed[grupo] = Rotation3(atual.x + extra.x, atual.y + extra.y, atual.z + extra.z)

        # v2.0 — Camada viva de antenas ("orelhas"), fones, mangas, pelve, humor e micro-porta
        fase_beat_atual = (
            beat_phase
            if beat_phase is not None
            else (self.dance_motion.phase / tau) % 1.0
        )
        delta_vivo = delta_expressao_viva(
            self.clock,
            self.state.value,
            self.agencia.humor_atual,
            composed,
            look_direction=self._look_direction,
            look_vertical=self._look_vertical,
            music_playing=music_playing,
            beat_phase=fase_beat_atual,
            music_bass=music_bass,
            music_energy=music_intensity,
            reacao_tempo=self._reaction_time,
            tontura=self.tontura,
            esforco=self.esforco,
            humor_antenas_override=self._humor_antenas_suave,
            humor_postura_override=self._humor_postura_suave,
            cena_ativa=self.cena_idle_amostra.ativa,
            eh_clipe_completo=eh_clipe_completo,
            fase_perna=self.leg_motion.phase,
            pelvis_animada=bool(
                eh_clipe_completo
                or (
                    self.cena_idle_amostra.ativa
                    and "pelvis" in self.cena_idle_amostra.delta_rig
                )
            ),
            afeicao=self.agencia.afeicao,
            rancor=self.agencia.rancor_arremesso,
            respiracao=self.respiracao_valor,
        )
        for grupo, extra in delta_vivo.items():
            if grupo in composed:
                atual = composed[grupo]
                if grupo == "door" and abs(atual.y) > radians(12.0):
                    # Nunca sobrescreve abertura grande da porta (espirro, bocejo, tentáculos).
                    continue
                composed[grupo] = Rotation3(
                    atual.x + extra.x, atual.y + extra.y, atual.z + extra.z
                )

        # Inertialização quíntica primeiro; colisão única após HandMotion e LagChain
        # para nenhuma camada secundária reinvadir o corpo nem rodar duas vezes.
        # Cenas de contato isentam apenas a mão/lado que toca fone/gabinete.
        caixas_isentas = None
        if self._cena_idle_nome in ("ajeitar_fone", "escutar_fone", "fone_com_problema"):
            caixas_isentas = {
                "right": {"cabeca", "topo_cabeca"},
                "left": {"cabeca", "topo_cabeca"},
            }
        elif self._cena_idle_nome in (
            "pensar_gabinete",
            "tentaculo_fujao",
            "roubo_cursor_tentaculo",
            "cuspir_item",
        ):
            caixas_isentas = {
                "right": {"cabeca", "topo_cabeca", "tronco"},
                "left": {"cabeca", "topo_cabeca", "tronco"},
            }
        if (
            self.state
            in (
                AnimationState.GOKU_TELEPORT,
                AnimationState.CELEBRATE,
                AnimationState.BLUE_BALLS,
            )
            or eh_clipe_completo
        ):
            alvo_colisao = 0.0
        elif self.state == AnimationState.DRAG:
            alvo_colisao = 0.65
        else:
            alvo_colisao = 1.0
        passo_colisao = max(0.0, dt) / 0.38 if dt > 0.0 else 1.0
        if self.state == AnimationState.GOKU_TELEPORT:
            self._peso_colisao = 0.0
        else:
            self._peso_colisao += max(
                -passo_colisao, min(passo_colisao, alvo_colisao - self._peso_colisao)
            )
        self._pose = self.pose_resolver.resolver(
            dt, composed, aplicar_colisao=False
        )
        cena_ativa = bool(self.cena_idle_amostra.ativa and self.cena_idle_amostra.delta_rig)
        cena_trava_maos = cena_ativa and metadados_cena(self.cena_idle_amostra.nome)["trava_maos"]
        displayed_pose = self.hand_motion.apply(
            self._pose,
            dt,
            self.state.value,
            ativo=not (
                eh_clipe_completo
                or cena_trava_maos
                or self.state == AnimationState.GOKU_TELEPORT
            ),
        )
        # Follow-through inercial: pleno em DRAG/FALL, leve no idle e mínimo em cena
        # dirigida (a cena já carrega o próprio overlap; amortecedor extra a deixava travada).
        if self.state in (AnimationState.DRAG, AnimationState.FALL):
            alvo_tatil = 1.0
        elif eh_clipe_completo or self.state == AnimationState.GOKU_TELEPORT:
            alvo_tatil = 0.0
        elif cena_ativa:
            alvo_tatil = 0.15
        elif self.state in (AnimationState.IDLE, AnimationState.HOVER):
            alvo_tatil = 0.32
        else:
            alvo_tatil = 0.62
        passo_tatil = max(0.0, dt) / 0.24
        self._peso_tatil += max(-passo_tatil, min(passo_tatil, alvo_tatil - self._peso_tatil))
        peso_tatil_suave = suavizar_quintico(self._peso_tatil)
        displayed_pose = self._aplicar_interacao(displayed_pose, dt, peso_tatil_suave)
        if self.state not in (AnimationState.SLEEP, AnimationState.GOKU_TELEPORT):
            displayed_pose = self._aplicar_imperfeicao_humana(
                displayed_pose, self.clock, 0.45 if eh_clipe_completo else 1.0
            )
        peso_colisao_suave = suavizar_quintico(self._peso_colisao)
        modelo_colisao = (
            self._collision_model if peso_colisao_suave > 1e-4 else None
        )
        displayed_pose = self.pose_resolver.resolver_colisao_bracos(
            displayed_pose,
            model=modelo_colisao,
            dt=dt,
            peso_colisao=peso_colisao_suave,
            leg_pose=self.leg_motion.pose,
            caixas_isentas_por_lado=caixas_isentas,
        )
        self.rig.current = dict(displayed_pose)
        roubo_em_movimento = (
            self.state == AnimationState.TEIMOSIA
            and self._teimosia_fase == "roubo"
            and abs(velocity[0]) > 40.0
        )
        passo_prof_pernas = bool(
            (amostra_olhar.ativo and amostra_olhar.em_passo)
            or self.profundidade.em_caminhada
        )
        estado_pernas = (
            AnimationState.RUN.value
            if roubo_em_movimento
            else AnimationState.WALK.value
            if passo_prof_pernas
            else self.state.value
        )
        vel_prof = (
            self.profundidade.velocidade_caminhada
            if self.profundidade.em_caminhada
            else 160.0
        )
        vel_pernas = (
            (vel_prof * (self.pacote_olhar_tela.lado if amostra_olhar.ativo else 1.0), 0.0)
            if passo_prof_pernas
            else velocity
        )
        tempo_pernas = (
            self._idle_clock
            if self.state in (AnimationState.IDLE, AnimationState.HOVER)
            else self.state_time
            if self.state
            in (
                AnimationState.WALK,
                AnimationState.RUN,
                AnimationState.DANCE,
                AnimationState.DRAG,
                AnimationState.SLEEP,
                AnimationState.SIT,
                AnimationState.JUMP,
                AnimationState.FALL,
            )
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
            cena_nome=(
                self.cena_idle_amostra.nome
                if self.cena_idle_amostra.ativa
                else (
                    f"idle:{self.idle_personality.value}"
                    if self.state in (AnimationState.IDLE, AnimationState.HOVER)
                    and pernas_idle_autoral(self.idle_personality.value, 0.0) is not None
                    else ""
                )
            ),
            cena_pernas=(
                None
                if self.state == AnimationState.SIT
                else (
                    self.cena_idle_amostra.pernas_graus
                    if self.cena_idle_amostra.ativa
                    else (
                        pernas_idle_autoral(
                            self.idle_personality.value,
                            self._idle_clock,
                            self.respiracao_valor,
                        )
                        if self.state in (AnimationState.IDLE, AnimationState.HOVER)
                        else None
                    )
                )
            ),
            teimosia_fase=self._teimosia_fase,
            reaction_direction=self._reaction_direction,
            respiracao=self.respiracao_valor,
            height_above_floor_px=height_above_floor_px,
            resistencia=self.agencia.resistencia_ao_arraste,
            fase_clipe=self._acao_fase_ciclo,
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
            self.cadeia_cabeca,
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

    @staticmethod
    def _aplicar_imperfeicao_humana(
        pose: dict[str, Rotation3], t: float, peso: float
    ) -> dict[str, Rotation3]:
        """Micro-deriva orgânica não-repetitiva (frequências irracionais) contra robotização."""
        if peso <= 1e-4:
            return pose
        # Soma de senos com razões irracionais (phi, sqrt(2), e) nunca repete exatamente
        d1 = sin(t * 2.13) * 0.55 + sin(t * 3.47 + 1.1) * 0.45
        d2 = sin(t * 1.73 + 0.7) * 0.60 + sin(t * 4.31 + 2.3) * 0.40
        d3 = sin(t * 2.89 + 2.0) * 0.50 + sin(t * 5.17 + 0.4) * 0.50
        micro_graus: dict[str, tuple[float, float, float]] = {
            "body": (d1 * 0.9, d2 * 1.2, d1 * 0.8),
            "head": (d2 * 1.4, d1 * 1.8, d3 * 1.3),
            "shoulder": (d3 * 1.1, 0.0, -d1 * 0.9),
            "shoulder2": (-d2 * 1.1, 0.0, d1 * 0.9),
            "hand": (d3 * 2.2, d1 * 1.6, d2 * 1.8),
            "hand2": (-d2 * 2.2, -d3 * 1.6, -d1 * 1.8),
            "antena-direita": (d3 * 2.8, 0.0, d2 * 2.4),
            "antena-esquerda": (d1 * 2.8, 0.0, -d3 * 2.4),
        }
        out = dict(pose)
        for grp, (gx, gy, gz) in micro_graus.items():
            if grp in out:
                r = out[grp]
                out[grp] = Rotation3(
                    r.x + radians(gx * peso),
                    r.y + radians(gy * peso),
                    r.z + radians(gz * peso),
                )
        return out

    def _aplicar_mao_gesto(self) -> None:
        """Posiciona braços, tronco e cabeça para os 8 gestos de mão com vida v2.0."""
        t = max(0.0, self._reaction_time)
        dur = self.REACTION_SECONDS.get(self.state, 3.0) if self.state is not None else 3.0
        entrada = suavizar_quintico(t / 0.28)
        saida = 1.0 - suavizar_quintico((t - max(0.35, dur - 0.34)) / 0.34)
        env = entrada * saida
        overshoot = sin(min(1.0, t / 0.36) * pi) * 0.12 * saida
        vida = sin(t * 3.4) * env
        pose_idle(self.rig, self.clock, self.idle_personality)
        if self.state in (AnimationState.OPEN_HANDS, AnimationState.CLOSE_FISTS):
            palma_aberta = self.state == AnimationState.OPEN_HANDS
            pulso = 1.0 + overshoot
            self.rig.set_rotation("peitoral", x=(3.5 if palma_aberta else -3.0) * env, z=vida * 1.5)
            self.rig.set_rotation("head", x=(-3.0 if palma_aberta else 2.5) * env, z=vida * 2.0)
            self.rig.set_rotation("antena-direita", x=(6.0 if palma_aberta else -5.0) * env, z=4.0 * env)
            self.rig.set_rotation("antena-esquerda", x=(6.0 if palma_aberta else -5.0) * env, z=-4.0 * env)
            for lado, ombro, mao, dedos, sinal in (
                ("right", "shoulder", "hand", "fingers", 1),
                ("left", "shoulder2", "hand2", "fingers2", -1),
            ):
                base_idle = braco_hpr_graus(lado, "idle")
                alvo_int = braco_hpr_graus(lado, "interaction")
                for grupo, (ax, ay, az) in alvo_int.items():
                    bx, by, bz = base_idle[grupo]
                    self.rig.set_rotation(
                        grupo,
                        x=bx + (ax - bx) * env * pulso,
                        y=by + (ay - by) * env,
                        z=bz + (az - bz) * env + sinal * vida * 2.0,
                    )
                self.rig.set_rotation(ombro, x=-2.5 * env, z=-sinal * 3.5 * env)
                self.rig.set_rotation(
                    mao,
                    x=(36.0 if palma_aberta else -16.0) * env + vida * 3.0,
                    y=-sinal * 18.0 * env,
                    z=sinal * (6.0 * env + vida * 2.5),
                )
                self.rig.set_rotation(dedos)
            return
        rot_braco, z_ant = _GESTOS_MAO_DIREITA[self.state.value]
        self.rig.set_rotation("peitoral", x=2.0 * env, y=-6.5 * env, z=2.2 * env + vida * 1.4)
        self.rig.set_rotation("head", x=-2.5 * env, y=8.0 * env, z=-4.0 * env + vida * 2.2)
        self.rig.set_rotation("shoulder", x=-3.5 * env, z=-5.0 * env)
        self.rig.set_rotation("fones", z=2.5 * env - vida * 1.8)
        self.rig.set_rotation("antena-direita", x=7.0 * env, z=4.0 * env + vida * 2.5)
        self.rig.set_rotation("antena-esquerda", x=4.0 * env, z=-2.0 * env + vida * 2.0)
        b_dir = braco_hpr_graus("right", "idle")["right-arm"]
        e_dir = braco_hpr_graus("right", "idle")["ant-arm"]
        p_ov = env + overshoot
        self.rig.set_rotation(
            "right-arm",
            x=b_dir[0] + (rot_braco[0] - b_dir[0]) * p_ov,
            y=b_dir[1] + (rot_braco[1] - b_dir[1]) * env,
            z=b_dir[2] + (rot_braco[2] - b_dir[2]) * env + vida * 2.5,
        )
        self.rig.set_rotation(
            "ant-arm",
            x=e_dir[0] + (-12.0 - e_dir[0]) * env,
            z=max(0.0, e_dir[2] + (z_ant - e_dir[2]) * p_ov + vida * 3.0),
        )
        self.rig.set_rotation("hand", x=vida * 4.5, y=-14.0 * env, z=-10.0 * env + vida * 3.5)
        self.rig.set_rotation("fingers", z=0)
        if self._gesto_mao_esquerda in _GESTOS_MAO_DIREITA:
            rot_esq, z_ant_esq = _GESTOS_MAO_DIREITA[self._gesto_mao_esquerda]
            b_esq = braco_hpr_graus("left", "idle")["left-arm"]
            e_esq = braco_hpr_graus("left", "idle")["ant-arm2"]
            self.rig.set_rotation(
                "left-arm",
                x=b_esq[0] + (rot_esq[0] - b_esq[0]) * p_ov,
                y=b_esq[1] + (-rot_esq[1] - b_esq[1]) * env,
                z=b_esq[2] + (-rot_esq[2] - b_esq[2]) * env - vida * 2.5,
            )
            self.rig.set_rotation(
                "ant-arm2",
                x=e_esq[0] + (-12.0 - e_esq[0]) * env,
                z=min(0.0, e_esq[2] + (-z_ant_esq - e_esq[2]) * p_ov - vida * 3.0),
            )
            self.rig.set_rotation("hand2", x=vida * 4.5, y=14.0 * env, z=10.0 * env - vida * 3.5)
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
        elif self.state == AnimationState.GOKU_TELEPORT:
            pose_goku_teleport(self.rig, self._reaction_time)
        elif self.state == AnimationState.SNEEZE:
            pose_sneeze(self.rig, self._reaction_time)
        elif self.state == AnimationState.TEIMOSIA:
            aplicar_pose_teimosia(self.rig, self._reaction_time, self._look_direction)
        elif self.state == AnimationState.HIT:
            aplicar_defesa(
                self.rig, self._reaction_time,
                duracoes_reacoes().get(self.state.value, self.REACTION_SECONDS[self.state]),
                self._reaction_direction, impacto=True,
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
            return delta_idle(
                t,
                self.idle_personality,
                self.respiracao_valor,
                look_direction=self._look_direction,
                look_vertical=self._look_vertical,
                torso_look_direction=self._idle_torso_look_dir,
                torso_look_vertical=self._idle_torso_look_vert,
                respiracao_cascata=self._respiracao_cascata,
            )
        if state == AnimationState.HOVER:
            return delta_hover(
                t,
                self.idle_personality,
                self.respiracao_valor,
                look_direction=self._look_direction,
                look_vertical=self._look_vertical,
                torso_look_direction=self._idle_torso_look_dir,
                torso_look_vertical=self._idle_torso_look_vert,
                respiracao_cascata=self._respiracao_cascata,
            )
        if state == AnimationState.DRAG:
            return delta_drag(motion, grab_part, self.drag_intensity)
        if state in (AnimationState.WALK, AnimationState.RUN):
            return delta_walk(self.leg_motion.phase, run=state == AnimationState.RUN)
        if state == AnimationState.FALL:
            return delta_fall(self.state_time, velocity)
        if state == AnimationState.JUMP:
            return delta_jump(self.state_time, velocity)
        if state == AnimationState.SIT:
            return delta_sit(
                t,
                look_direction=self._look_direction,
                look_vertical=self._look_vertical,
                respiracao=self.respiracao_valor,
            )
        if state == AnimationState.SLEEP:
            return delta_sleep(t, self.modo_sono)
        # Estados não migrados: delta vazio (usa pose legada)
        return {}

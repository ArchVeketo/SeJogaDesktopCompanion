"""Sistema de agência e vontade própria do Mário.

Fonte da verdade: MANUAL_UNIFICADO_MARIO.md §4.1 (Camada 1 — Agência & Sistema de Desejos).

O Mário não é um widget reativo: ele possui metas, curiosidade, foco do olhar,
teimosia e paciência. Este módulo decide **O QUE** o mascote quer fazer a cada
momento, independentemente de estímulos externos.

Arquitetura
-----------
1. `Meta` — Um objetivo na tela (ex: caminhar até um ponto, olhar uma notificação).
2. `Desejo` — Impulso interno que pode gerar uma meta (curiosidade, tédio, fome de atenção).
3. `Humor` — Estado emocional derivado do histórico de interações recentes.
4. `Agencia` — Cérebro que orquestra desejos → metas → ações.

Regras canônicas (do manifesto)
-------------------------------
- O idle não troca por relógio: muda conforme o histórico recente.
- A dança não é um botão solto: é comemoração após meta ou reação rítmica.
- Os tentáculos saem quando Mário acha que ninguém está olhando.
- O espirro tem causa física (poeira, cócegas, engoliu o que não devia).
- Teimosia escala com interrupções consecutivas: 3 interrupções → bote → roubo do mouse.
"""

from __future__ import annotations

import enum
import random
import time
from dataclasses import dataclass
from math import hypot

# ─── Humor / Estado Emocional ────────────────────────────────────────────────

class Humor(enum.StrEnum):
    """Estado emocional do Mário, derivado do histórico de interações."""

    CALMO = "calmo"
    CURIOSO = "curioso"
    TEIMOSO = "teimoso"
    INDIGNADO = "indignado"
    BRINQUEDOIRO = "brinquedoiro"
    TEDIOSO = "tedioso"
    DESCONFIADO = "desconfiado"


# ─── Meta (Objetivo na Tela) ─────────────────────────────────────────────────

class MetaTipo(enum.IntEnum):
    """Tipos de meta que Mário pode ter."""

    OLHAR_PONTO = 1       # Olhar para um ponto interessante na tela
    CAMINHAR_A_TELEFONE = 2  # Caminhar até um ponto por curiosidade
    PROCURAR_ATENCAO = 3  # Buscar interação com o usuário
    EXPLORAR_TELA = 4     # Explorar uma área não vista recentemente


@dataclass
class Meta:
    """Um objetivo ativo do Mário na tela."""

    tipo: MetaTipo
    alvo_x: float  # Posição alvo em coordenadas do desktop
    alvo_y: float
    prioridade: float = 1.0  # 0..1; quanto mais alto, mais insistente
    criado_em: float = 0.0   # Timestamp de criação
    tempo_maximo: float = 12.0  # Segundos antes de expirar
    intensidade: float = 1.0  # Fator de resistência quando contrariado

    def esta_expirada(self, agora: float) -> bool:
        """Retorna True se a meta excedeu o tempo máximo."""
        return (agora - self.criado_em) > self.tempo_maximo

    def urgencia_em(self, agora: float) -> float:
        """Urgência decrescente usando o relógio interno da agência (1.0 → 0.0)."""
        if self.tempo_maximo <= 0:
            return 0.0
        restante = self.tempo_maximo - (agora - self.criado_em)
        return max(0.0, min(1.0, restante / self.tempo_maximo))

    @property
    def urgencia(self) -> float:
        """Urgência decrescente (compatível com chamadas sem relógio explícito)."""
        return self.urgencia_em(time.monotonic())


# ─── Desejo (Impulso Interno) ────────────────────────────────────────────────

class DesejoTipo(enum.IntEnum):
    """Tipos de desejo que podem surgir internamente."""

    CURIOSIDADE = 1       # Algo na tela chamou atenção
    TEDIO = 2             # Muito tempo sem interação
    FOME_ATENCAO = 3      # Quer brincar com o usuário
    EXPLORACAO = 4        # Quer ver uma área nova
    DEFESA = 5            # Reação a tratamento rude


@dataclass
class Desejo:
    """Impulso interno que pode gerar uma meta."""

    tipo: DesejoTipo
    intensidade: float = 1.0  # 0..1
    criado_em: float = 0.0
    tempo_decaimento: float = 30.0  # Segundos para decair a zero

    def decair(self, dt: float) -> None:
        """Reduz a intensidade com o tempo."""
        if self.tempo_decaimento <= 0:
            self.intensidade = 0.0
            return
        decaimento = dt / self.tempo_decaimento
        self.intensidade = max(0.0, self.intensidade - decaimento)

    @property
    def esta_ativo(self) -> bool:
        """Desejo ativo se intensidade > 0.1."""
        return self.intensidade > 0.1


# ─── Registro de Interrupções ────────────────────────────────────────────────

@dataclass
class InterrupcaoRegistro:
    """Rastreia interrupções consecutivas para escalar teimosia."""

    contador: int = 0
    ultima_interrupcao: float = 0.0
    janela_temporal: float = 15.0  # Segundos para considerar "consecutiva"
    tentativas_resistencia: int = 0  # Quantas vezes tentou escapar

    def registrar(self, agora: float) -> None:
        """Registra uma nova interrupção e atualiza o contador."""
        if agora - self.ultima_interrupcao > self.janela_temporal:
            # Reset se passou muito tempo desde a última
            self.contador = 1
        else:
            self.contador += 1
        self.ultima_interrupcao = agora
        self.tentativas_resistencia = 0

    def resetar(self) -> None:
        """Reseta após sucesso (ex: Mário alcançou a meta)."""
        self.contador = 0
        self.tentativas_resistencia = 0

    @property
    def deve_acionar_teimosia(self) -> bool:
        """3 interrupções consecutivas disparam a teimosia (manifesto §1.4)."""
        return self.contador >= 3


# ─── Agência (Cérebro do Mário) ──────────────────────────────────────────────

class Agencia:
    """Cérebro soberano do Mário: decide o que ele quer fazer.

    Orquestra desejos → metas → ações. Opera independentemente de estímulos
    externos, mas pode ser influenciado por eles (interrupções, interações).

    Parâmetros
    ----------
    seed : int ou None
        Semente para reprodutibilidade em testes.
    """

    def __init__(self, *, seed: int | None = None) -> None:
        """Inicializa o estado interno de humor, metas e teimosia."""
        self._rng = random.Random(seed)
        self._agora = time.monotonic()

        # Estado emocional
        self.humor: Humor = Humor.CALMO
        self._humor_tempo: dict[Humor, float] = {}
        for h in Humor:
            self._humor_tempo[h] = 0.0

        # Metas ativas
        self._metas: list[Meta] = []
        self.meta_ativa: Meta | None = None

        # Desejos pendentes
        self._desejos: list[Desejo] = []

        # Interrupções e teimosia
        self.interrupcoes = InterrupcaoRegistro()
        self._teimosia_nivel: float = 0.0  # 0..1
        self._teimosia_ativa: bool = False

        # Histórico de interações (inicia em self._agora para não nascer "entediado")
        self._interacoes_positivas: int = 0  # Carinho, brincadeira
        self._interacoes_negativas: int = 0  # Arraste brusco, impacto
        self._tempo_ultima_interacao: float = self._agora
        self._tempo_ultimo_cursor_movimento: float = self._agora
        self._carinhos_seguidos: int = 0
        self._ultimo_carinho: float = -999.0
        self._ultima_comemoracao: float = -999.0
        self.rancor_arremesso: float = 0.0  # 0..1; sobe em impactos/arremessos, suaviza com carinho
        self.afeicao: float = 0.35          # 0..1; cresce com carinho e brincadeiras

        # Curiosidade: pontos de interesse na tela
        self._pontos_interesse: list[tuple[float, float]] = []

        # Cooldowns
        self._cooldown_nova_meta: float = 0.0
        self._cooldown_desejo: float = 0.0

        # Configuração
        self.intervalo_meta_min: float = 10.0  # Segundos mínimos entre metas
        self.intervalo_meta_max: float = 25.0  # Segundos máximos entre metas
        self.intervalo_desejo_min: float = 6.0
        self.intervalo_desejo_max: float = 18.0
        self._limites_tela: tuple[float, float, float, float] = (0.0, 0.0, 1920.0, 1080.0)

    def definir_limites_tela(self, left: float, top: float, right: float, bottom: float) -> None:
        """Atualiza os limites reais do monitor ativo para geração de metas."""
        if right - left > 200 and bottom - top > 200:
            self._limites_tela = (float(left), float(top), float(right), float(bottom))

    # ── Propriedades de leitura ──────────────────────────────────────────

    @property
    def teimosia_ativa(self) -> bool:
        """True quando Mário está em modo teimosia (manifesto §1.4)."""
        return self._teimosia_ativa

    @property
    def teimosia_nivel(self) -> float:
        """Nível de teimosia (0..1)."""
        return self._teimosia_nivel

    @property
    def humor_atual(self) -> Humor:
        """Humor predominante do Mário."""
        return self.humor

    @property
    def tem_meta_ativa(self) -> bool:
        """True se Mário tem um objetivo ativo."""
        return self.meta_ativa is not None and not self.meta_ativa.esta_expirada(self._agora)

    def definir_posicao_corpo(self, x: float, y: float) -> None:
        """Atualiza a posição atual do mascote no espaço da tela."""
        self._pos_x = x
        self._pos_y = y

    def direcao_para(self, pos_x: float, pos_y: float) -> tuple[float, float] | None:
        """Direção normalizada até a meta ativa a partir de ``(pos_x, pos_y)``."""
        if self.meta_ativa is None:
            return None
        dx = self.meta_ativa.alvo_x - pos_x
        dy = self.meta_ativa.alvo_y - pos_y
        dist = hypot(dx, dy)
        if dist <= 1e-6:
            return None
        return (dx / dist, dy / dist)

    @property
    def direcao_meta(self) -> tuple[float, float] | None:
        """Direção normalizada até a meta ativa (ou None)."""
        return self.direcao_para(getattr(self, "_pos_x", 0.0), getattr(self, "_pos_y", 0.0))

    @property
    def resistencia_ao_arraste(self) -> float:
        """Fator de resistência quando arrastado (0..1).

        Aumenta com teimosia e urgência da meta ativa.
        """
        base = 0.0
        if self._teimosia_ativa:
            base += self._teimosia_nivel * 0.6
        if self.meta_ativa is not None:
            base += self.meta_ativa.urgencia_em(self._agora) * self.meta_ativa.intensidade * 0.45
        return min(1.0, base)

    # ── Atualização principal ────────────────────────────────────────────

    def atualizar(self, dt: float) -> None:
        """Passo principal da agência: atualiza humor, desejos, metas e teimosia."""
        self._agora += dt

        # Cooldowns
        self._cooldown_nova_meta = max(0.0, self._cooldown_nova_meta - dt)
        self._cooldown_desejo = max(0.0, self._cooldown_desejo - dt)

        # Decaimento de desejos
        for d in self._desejos:
            d.decair(dt)
        self._desejos = [d for d in self._desejos if d.esta_ativo]

        # Expiração de metas
        self._metas = [m for m in self._metas if not m.esta_expirada(self._agora)]
        if self.meta_ativa is not None and self.meta_ativa.esta_expirada(self._agora):
            self.meta_ativa = self._metas[0] if self._metas else None

        # Decaimento da teimosia
        if self._teimosia_ativa:
            self._teimosia_nivel = max(0.0, self._teimosia_nivel - dt * 0.1)
            if self._teimosia_nivel <= 0.05:
                self._teimosia_ativa = False
                self._teimosia_nivel = 0.0

        # Geração espontânea de desejos
        if self._cooldown_desejo <= 0:
            self._gerar_desejo_espontaneo()
            self._cooldown_desejo = self._rng.uniform(
                self.intervalo_desejo_min, self.intervalo_desejo_max
            )

        # Conversão de desejos em metas
        if self._cooldown_nova_meta <= 0 and not self.tem_meta_ativa:
            self._tentar_gerar_meta()
            self._cooldown_nova_meta = self._rng.uniform(
                self.intervalo_meta_min, self.intervalo_meta_max
            )

        # Decaimento de rancor pós-arremesso
        if self.rancor_arremesso > 0.0:
            self.rancor_arremesso = max(0.0, self.rancor_arremesso - dt * 0.045)

        # Atualizar humor baseado no histórico
        self._atualizar_humor(dt)

    # ── Interações externas ──────────────────────────────────────────────

    def registrar_interacao_positiva(self, *, carinho: bool = False) -> None:
        """Registra carinho, brincadeira suave, etc."""
        self._interacoes_positivas += 1
        self._tempo_ultima_interacao = self._agora
        self._humor_tempo[Humor.BRINQUEDOIRO] = 14.0
        self.rancor_arremesso = max(0.0, self.rancor_arremesso - (0.45 if carinho else 0.15))
        self.afeicao = min(1.0, self.afeicao + (0.10 if carinho else 0.04))
        if carinho:
            if (self._agora - self._ultimo_carinho) > 12.0:
                self._carinhos_seguidos = 1
            else:
                self._carinhos_seguidos += 1
            self._ultimo_carinho = self._agora

    def registrar_interacao_negativa(self, intensidade: float = 1.0) -> None:
        """Registra arraste brusco, impacto, etc."""
        self._interacoes_negativas += 1
        self._carinhos_seguidos = 0
        self._tempo_ultima_interacao = self._agora
        self._humor_tempo[Humor.INDIGNADO] = 6.5 * intensidade
        if intensidade >= 0.85:
            self.rancor_arremesso = min(1.0, self.rancor_arremesso + 0.38 * intensidade)
            self._humor_tempo[Humor.DESCONFIADO] = max(
                self._humor_tempo[Humor.DESCONFIADO], 11.0 * intensidade
            )
        self.afeicao = max(0.0, self.afeicao - 0.06 * intensidade)

    def registrar_interrupcao(self) -> None:
        """Registra que o usuário interrompeu uma ação do Mário."""
        self.interrupcoes.registrar(self._agora)
        if self.interrupcoes.deve_acionar_teimosia:
            self._acionar_teimosia()

    def registrar_cursor_movimento(self) -> None:
        """Informa que o cursor se moveu (alguém está olhando)."""
        self._tempo_ultimo_cursor_movimento = self._agora

    def registrar_meta_alcançada(self) -> None:
        """Mário alcançou uma meta: reseta interrupções e fica satisfeito."""
        self.interrupcoes.resetar()
        self._humor_tempo[Humor.CURIOSO] = 15.0
        if self.meta_ativa is not None:
            self.meta_ativa = None

    def consumir_vitoria_meta(self, meta: Meta | None) -> bool:
        """Comemora apenas conquistas prioritárias (nunca passeios triviais), com cooldown longo."""
        if meta is None or meta.tipo not in (MetaTipo.CAMINHAR_A_TELEFONE, MetaTipo.PROCURAR_ATENCAO):
            return False
        if meta.prioridade < 0.72 or (self._agora - self._ultima_comemoracao) < 90.0:
            return False
        self._ultima_comemoracao = self._agora
        return True

    def consumir_marco_carinho(self) -> bool:
        """Premia sequência de 3 carinhos/duplos cliques recentes com comemoração."""
        if self._carinhos_seguidos < 3 or (self._agora - self._ultima_comemoracao) < 90.0:
            return False
        self._carinhos_seguidos = 0
        self._ultima_comemoracao = self._agora
        return True

    def adicionar_ponto_interesse(self, x: float, y: float) -> None:
        """Adiciona um ponto de interesse na tela (ex: notificação)."""
        if any(hypot(px - x, py - y) < 24.0 for px, py in self._pontos_interesse):
            return
        self._pontos_interesse.append((x, y))
        if len(self._pontos_interesse) > 16:
            self._pontos_interesse = self._pontos_interesse[-16:]

    @property
    def tempo_sem_cursor_movimento(self) -> float:
        """Tempo desde o último movimento do cursor (para tentáculos contextuais)."""
        return self._agora - self._tempo_ultimo_cursor_movimento

    @property
    def tempo_sem_interacao(self) -> float:
        """Tempo desde a última interação com o usuário."""
        return self._agora - self._tempo_ultima_interacao

    # ── Métodos internos ─────────────────────────────────────────────────

    def _gerar_desejo_espontaneo(self) -> None:
        """Gera um desejo espontâneo baseado no contexto atual."""
        tempo_sem_interacao = self.tempo_sem_interacao
        tempo_sem_cursor = self.tempo_sem_cursor_movimento

        # Tédio após tempo sem interação
        if tempo_sem_interacao > 60:
            self._desejos.append(Desejo(
                tipo=DesejoTipo.TEDIO,
                intensidade=min(1.0, (tempo_sem_interacao - 60) / 120),
                criado_em=self._agora,
            ))

        # Curiosidade se há pontos de interesse
        if self._pontos_interesse and self._rng.random() < 0.45:
            self._desejos.append(Desejo(
                tipo=DesejoTipo.CURIOSIDADE,
                intensidade=0.8,
                criado_em=self._agora,
            ))

        # Fome de atenção após tempo sem brincar
        if tempo_sem_interacao > 45 and self._rng.random() < 0.35:
            self._desejos.append(Desejo(
                tipo=DesejoTipo.FOME_ATENCAO,
                intensidade=0.65,
                criado_em=self._agora,
            ))

        # Exploração natural: Mário é curioso e passeia pelo desktop
        if tempo_sem_cursor > 12 and self._rng.random() < 0.45:
            self._desejos.append(Desejo(
                tipo=DesejoTipo.EXPLORACAO,
                intensidade=0.55,
                criado_em=self._agora,
            ))

    def _tentar_gerar_meta(self) -> None:
        """Tenta converter um desejo em meta concreta."""
        if not self._desejos:
            return

        # Escolhe o desejo mais intenso
        desejo = max(self._desejos, key=lambda d: d.intensidade)

        if desejo.tipo == DesejoTipo.CURIOSIDADE and self._pontos_interesse:
            # Olhar ou caminhar até um ponto de interesse recente na tela
            ponto = self._pontos_interesse.pop(0)
            tipo_meta = (
                MetaTipo.CAMINHAR_A_TELEFONE
                if self._rng.random() < 0.45
                else MetaTipo.OLHAR_PONTO
            )
            self.meta_ativa = Meta(
                tipo=tipo_meta,
                alvo_x=ponto[0],
                alvo_y=ponto[1],
                prioridade=desejo.intensidade,
                criado_em=self._agora,
            )

        elif desejo.tipo == DesejoTipo.TEDIO:
            # Tédio vira passeio lento pela tela e ativa o humor TEDIOSO (não trava outros desejos!)
            self._humor_tempo[Humor.TEDIOSO] = max(self._humor_tempo[Humor.TEDIOSO], 22.0)
            left, top, right, bottom = self._limites_tela
            margem_x = min(180.0, (right - left) * 0.20)
            margem_y = min(120.0, (bottom - top) * 0.18)
            self.meta_ativa = Meta(
                tipo=MetaTipo.EXPLORAR_TELA,
                alvo_x=self._rng.uniform(left + margem_x, right - margem_x),
                alvo_y=self._rng.uniform(top + margem_y, bottom - margem_y),
                prioridade=0.45,
                criado_em=self._agora,
                tempo_maximo=10.0,
            )

        elif desejo.tipo == DesejoTipo.EXPLORACAO:
            # Explorar um ponto aleatório da tela dentro dos limites reais
            left, top, right, bottom = self._limites_tela
            margem_x = min(140.0, (right - left) * 0.15)
            margem_y = min(100.0, (bottom - top) * 0.15)
            self.meta_ativa = Meta(
                tipo=MetaTipo.EXPLORAR_TELA,
                alvo_x=self._rng.uniform(left + margem_x, right - margem_x),
                alvo_y=self._rng.uniform(top + margem_y, bottom - margem_y),
                prioridade=desejo.intensidade,
                criado_em=self._agora,
            )

        elif desejo.tipo == DesejoTipo.FOME_ATENCAO:
            # Procurar atenção: caminhar pela área útil
            left, top, right, bottom = self._limites_tela
            margem_x = min(160.0, (right - left) * 0.18)
            margem_y = min(120.0, (bottom - top) * 0.18)
            self.meta_ativa = Meta(
                tipo=MetaTipo.PROCURAR_ATENCAO,
                alvo_x=self._rng.uniform(left + margem_x, right - margem_x),
                alvo_y=self._rng.uniform(top + margem_y, bottom - margem_y),
                prioridade=desejo.intensidade,
                criado_em=self._agora,
            )

        # Remover o desejo consumido
        if desejo in self._desejos:
            self._desejos.remove(desejo)

    def _acionar_teimosia(self) -> None:
        """Ativa o modo teimosia após 3 interrupções consecutivas."""
        self._teimosia_ativa = True
        self._teimosia_nivel = 1.0
        self._humor_tempo[Humor.TEIMOSO] = 30.0
        self.humor = Humor.TEIMOSO

    def _atualizar_humor(self, dt: float) -> None:
        """Atualiza o humor baseado nos temporizadores de cada estado."""
        # Decaimento dos temporizadores
        for h in Humor:
            self._humor_tempo[h] = max(0.0, self._humor_tempo[h] - dt)

        # Humor predominante é o com maior temporizador
        max_tempo = 0.0
        for h, tempo in self._humor_tempo.items():
            if tempo > max_tempo:
                max_tempo = tempo
                self.humor = h

        # Fallback para CALMO se todos decaíram
        if max_tempo < 1.0:
            self.humor = Humor.CALMO

        # Tédio orgânico após 2 minutos sem interação
        if self.tempo_sem_interacao > 120.0 and max_tempo < 1.0:
            self.humor = Humor.TEDIOSO

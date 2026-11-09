"""Aplica proteções finais à pose composta: crossfade, colisão e clamps.

Extraído de ``AnimationController`` para unificar todas as correções em um único
ponto — crossfade com molas (continuidade de velocidade), anti-atravessamento
dos braços e clamps anatômicos finais. A pose que sai daqui está pronta para o
renderer, que não precisa aplicar mais nenhuma correção.
"""

from __future__ import annotations

from math import radians

from sejoga.animacao import braco_tuning as tun
from sejoga.animacao.colisao_bracos import ResolvedorBracos
from sejoga.animacao.joint_springs import SpringPose
from sejoga.nucleo.model import Model
from sejoga.nucleo.rig import Rotation3

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                       Limites anatômicos (clamps)                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
# Eixos medidos no grafo de cena (tools/oraculo_cena.py --eixos), braço direito
# com eixo longo +X: R (``Rotation3.z``) positivo BAIXA a mão, H (``.y``)
# positivo leva a mão para a FRENTE, P (``.x``) torce. Cotovelo = R do
# antebraço sobre a torção-base: positivo dobra para a frente, negativo seria
# hiperextensão (proibida). Lado esquerdo = espelho (x, -y, -z). Fonte única
# dos limites: braco_tuning. Em radianos.
_CLAMP_RIGHT_ARM_Z_MIN = radians(tun.OMBRO_ELEVACAO_MIN_GRAUS)
_CLAMP_RIGHT_ARM_Z_MAX = radians(tun.OMBRO_ELEVACAO_MAX_GRAUS)
_CLAMP_LEFT_ARM_Z_MIN = -_CLAMP_RIGHT_ARM_Z_MAX
_CLAMP_LEFT_ARM_Z_MAX = -_CLAMP_RIGHT_ARM_Z_MIN
_CLAMP_ARM_Y_MIN = radians(tun.OMBRO_AZIMUTE_MIN_GRAUS)
_CLAMP_ARM_Y_MAX = radians(tun.OMBRO_AZIMUTE_MAX_GRAUS)
_CLAMP_COTOVELO_MIN = radians(tun.COTOVELO_MIN_GRAUS)
_CLAMP_COTOVELO_MAX = radians(tun.COTOVELO_MAX_GRAUS)


class PoseResolver:
    """Aplica crossfade, anti-atravessamento dos braços e clamps à pose composta.

    O controller de animação chama :meth:`resolver` a cada frame, passando a
    pose alvo (saída do LayerStack/compositor). O PoseResolver:

    1. Faz crossfade com molas (continuidade de velocidade entre estados).
    2. Aplica clamps anatômicos e impede os braços de atravessar o corpo.

    A saída é a pose pronta para o renderer, sem correções adicionais.
    """

    def __init__(
        self,
        frequencia_crossfade: float = 2.2,
        amortecimento_crossfade: float = 0.72,
        tensoes_crossfade: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        """Inicializa o resolver.

        Parameters
        ----------
        frequencia_crossfade:
            Frequência default das molas de crossfade.
        amortecimento_crossfade:
            Amortecimento default das molas de crossfade.
        tensoes_crossfade:
            Tensão por junta ``(frequência, amortecimento)``; juntas fora do
            dict usam os defaults.
        """
        self._crossfade = SpringPose(
            frequencia=frequencia_crossfade,
            amortecimento=amortecimento_crossfade,
            tensoes=tensoes_crossfade or {},
        )
        # Frequência-base por junta (regime estável): para devolver a tensão
        # após a aceleração da transição.
        self._frequencia_base = {
            grupo: tensao[0]
            for grupo, tensao in (tensoes_crossfade or {}).items()
        }
        self._frequencia_default = frequencia_crossfade

        self._resolvedor_bracos: ResolvedorBracos | None = None

        self._transitioning = False
        self._transition_from: dict[str, Rotation3] = {}
        self._just_transitioned = False
        self._transition_seconds = 0.55
        self._state_time = 0.0

    # ═══════════════════════════════════════════════════════════════════════
    #                          Interface pública
    # ═══════════════════════════════════════════════════════════════════════

    def iniciar_transicao(
        self,
        pose_atual: dict[str, Rotation3],
        transition_seconds: float = 0.55,
    ) -> None:
        """Marca início de transição de estado.

        Chamado pelo controller quando o estado muda. Guarda a pose atual como
        ponto de partida do crossfade.
        """
        self._transition_from = dict(pose_atual)
        self._crossfade.definir(pose_atual)
        self._just_transitioned = True
        self._transitioning = True
        self._transition_seconds = max(0.0, transition_seconds)
        self._state_time = 0.0

    def resolver(
        self,
        dt: float,
        pose_alvo: dict[str, Rotation3],
        *,
        model: Model | None = None,
        state_time: float | None = None,
    ) -> dict[str, Rotation3]:
        """Resolve a pose final: crossfade → clamps → braços.

        Parameters
        ----------
        dt:
            Delta time em segundos.
        pose_alvo:
            Pose composta do LayerStack/compositor.
        model:
            Modelo para o anti-atravessamento dos braços. Se None, ele fica
            inerte.
        state_time:
            Tempo no estado atual (para acelerar crossfade no início). Se None,
            usa o tempo interno.

        Returns
        -------
        Pose final pronta para o renderer.
        """
        if state_time is not None:
            self._state_time = state_time
        else:
            self._state_time += dt

        # 1. Crossfade (molas por junta)
        pose = self._aplicar_crossfade(dt, pose_alvo)

        # 2. Clamps anatômicos (antes do anti-atravessamento, que parte de uma
        #    pose anatômica) e de novo depois (a correção não pode violá-los).
        pose = self._aplicar_clamps(pose)

        # 3. Braços não atravessam o corpo (FK real, se houver model)
        if model is not None:
            if self._resolvedor_bracos is None or self._resolvedor_bracos.model is not model:
                self._resolvedor_bracos = ResolvedorBracos(model)

            pose = self._aplicar_clamps(self._resolvedor_bracos.resolver(pose))

        return pose

    def definir_pose(self, poses: dict[str, Rotation3]) -> None:
        """Define a pose atual sem velocidade (evita saltos no crossfade)."""
        self._crossfade.definir(poses)

    def pose(self) -> dict[str, Rotation3]:
        """Retorna a pose atual do crossfade."""
        return self._crossfade.pose()

    @property
    def molas(self) -> dict:
        """Acesso às molas do crossfade (para ajustar frequência externamente)."""
        return self._crossfade.molas

    @property
    def frequencia_base(self) -> dict[str, float]:
        """Frequências-base por junta para restaurar após transição."""
        return self._frequencia_base

    @property
    def frequencia_default(self) -> float:
        """Frequência default para juntas sem tensão específica."""
        return self._frequencia_default

    # ═══════════════════════════════════════════════════════════════════════
    #                          Métodos internos
    # ═══════════════════════════════════════════════════════════════════════

    def _aplicar_crossfade(
        self, dt: float, pose_alvo: dict[str, Rotation3]
    ) -> dict[str, Rotation3]:
        """Crossfade com molas por junta (continuidade de velocidade)."""
        if self._transition_seconds == 0.0:
            # Sem crossfade: a pose acompanha o alvo diretamente.
            self._crossfade.definir(pose_alvo)
            self._just_transitioned = False
            return {g: pose_alvo.get(g, Rotation3()) for g in pose_alvo}

        if self._just_transitioned:
            # Primeiro frame após a troca: segura a pose anterior (continuidade
            # de posição e velocidade) antes de a mola começar a perseguir.
            self._crossfade.definir({
                grupo: self._transition_from.get(grupo, Rotation3())
                for grupo in pose_alvo
            })
            self._just_transitioned = False
            return {
                grupo: self._transition_from.get(grupo, Rotation3())
                for grupo in pose_alvo
            }

        # Molas por junta. Durante a janela de transição acelera-se o retargeting.
        em_transicao = self._state_time < self._transition_seconds
        freq_troca = max(0.6, 1.0 / self._transition_seconds) if self._transition_seconds > 0 else 1.0
        for grupo, mola in self._crossfade.molas.items():
            freq_junta = self._frequencia_base.get(grupo, self._frequencia_default)
            frequencia = max(freq_junta, freq_troca) if em_transicao else freq_junta
            mola.x.frequency = mola.y.frequency = mola.z.frequency = frequencia

        return self._crossfade.atualizar(dt, pose_alvo)

    def _aplicar_clamps(self, pose: dict[str, Rotation3]) -> dict[str, Rotation3]:
        """Limites rígidos anatômicos. Aplicados UMA vez, no final.

        Braços não podem dobrar para dentro do corpo além dos limites.
        """
        resultado = dict(pose)

        # Right arm: elevação Z (erguido → um pouco além de reto p/ baixo);
        # azimute Y em faixa ampla (contém só deriva). Limites em braco_tuning.
        if "right-arm" in resultado:
            r = resultado["right-arm"]
            y = max(_CLAMP_ARM_Y_MIN, min(_CLAMP_ARM_Y_MAX, r.y))
            z = max(_CLAMP_RIGHT_ARM_Z_MIN, min(_CLAMP_RIGHT_ARM_Z_MAX, r.z))
            if y != r.y or z != r.z:
                resultado["right-arm"] = Rotation3(r.x, y, z)

        # Left arm: espelho.
        if "left-arm" in resultado:
            r = resultado["left-arm"]
            y = max(_CLAMP_ARM_Y_MIN, min(_CLAMP_ARM_Y_MAX, r.y))
            z = max(_CLAMP_LEFT_ARM_Z_MIN, min(_CLAMP_LEFT_ARM_Z_MAX, r.z))
            if y != r.y or z != r.z:
                resultado["left-arm"] = Rotation3(r.x, y, z)

        # Cotovelo: dobradiça de um lado só (sem hiperextensão), espelhado.
        for grupo, sinal in (("ant-arm", 1.0), ("ant-arm2", -1.0)):
            if grupo in resultado:
                r = resultado[grupo]
                flexao = max(_CLAMP_COTOVELO_MIN, min(_CLAMP_COTOVELO_MAX, sinal * r.z))
                if sinal * flexao != r.z:
                    resultado[grupo] = Rotation3(r.x, r.y, sinal * flexao)

        return resultado

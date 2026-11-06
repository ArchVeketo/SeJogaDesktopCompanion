"""Aplica proteções finais à pose composta: crossfade, colisão e clamps.

Extraído de ``AnimationController`` para unificar todas as correções em um único
ponto — crossfade com molas (continuidade de velocidade), correção pontual de
colisão e clamps anatômicos finais. A pose que sai daqui está pronta para o
renderer, que não precisa aplicar mais nenhuma correção.
"""

from __future__ import annotations

from math import radians

from sejoga.animacao.joint_springs import SpringPose
from sejoga.nucleo.model import Model
from sejoga.nucleo.rig import Rotation3
from sejoga.rig_mapa import colisao_membros as colisao
from sejoga.rig_mapa import rig_medidas as medidas


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                       Limites anatômicos (clamps)                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
# Convenção de elevação do braço (Z/roll) PÓS-IK, verificada por FK sobre a
# geometria real (o eixo longo do bone é +X, não -Y — ver ``arm_ik``):
#   Z=-90 → BAIXADO (reto para baixo, ao lado do quadril)
#   Z=-86 → repouso natural de idle (quase reto para baixo)
#   Z=0   → LATERAL/T-pose (braço na horizontal, apontando +X)
#   Z=+90 → ERGUIDO (reto para CIMA)
# O left-arm usa o espelho (-Z). A convenção MUDOU com a migração para IK: antes
# Z=0 era "baixo" e Z=180 "cima" (base antiga ~28°, errada — deixava o braço
# aberto/lateral); agora Z mede a elevação a partir de +X. Os limites cobrem de
# reto para baixo (com folga para overshoot de crossfade) até um pouco além de
# reto para cima, acomodando wave/dance/flourish (que erguem a mão). Em radianos.
_CLAMP_RIGHT_ARM_Z_MIN = radians(-100)
_CLAMP_RIGHT_ARM_Z_MAX = radians(120)
_CLAMP_LEFT_ARM_Z_MIN = radians(-120)
_CLAMP_LEFT_ARM_Z_MAX = radians(100)


class PoseResolver:
    """Aplica crossfade, colisões e clamps à pose composta.

    O controller de animação chama :meth:`resolver` a cada frame, passando a
    pose alvo (saída do LayerStack/compositor). O PoseResolver:

    1. Faz crossfade com molas (continuidade de velocidade entre estados).
    2. Corrige colisões, empurrando só o excedente de forma suave.
    3. Aplica clamps anatômicos finais.

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

        # Correção pontual suave de colisão (FEAT-B): só ativa quando Model é
        # injetado. A mola persegue o alvo corrigido por colisao.resolver_colisoes.
        self._correcao_colisao = SpringPose(
            frequencia=colisao.CORRECAO_FREQUENCIA_HZ,
            amortecimento=colisao.CORRECAO_AMORTECIMENTO,
        )

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
        """Resolve a pose final: crossfade → colisão → clamps.

        Parameters
        ----------
        dt:
            Delta time em segundos.
        pose_alvo:
            Pose composta do LayerStack/compositor.
        model:
            Modelo para detecção de colisão. Se None, a correção de colisão fica
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

        # 2. Correção de colisão (se houver model)
        pose = self._resolver_colisoes_suave(pose, dt, model)

        # 3. Clamps anatômicos finais
        pose = self._aplicar_clamps(pose)

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

    def _resolver_colisoes_suave(
        self,
        pose: dict[str, Rotation3],
        dt: float,
        model: Model | None,
    ) -> dict[str, Rotation3]:
        """Correção pontual suave (FEAT-B): empurra só o EXCEDENTE, amortecido.

        Mede as partes da pose exibida, pede a ``colisao.resolver_colisoes`` o
        alvo com o PISO ESTRUTURAL já descontado (só o excedente dirigido pela
        pose) e persegue esse alvo por molas por junta, de modo que a correção
        entre GRADUAL, sem tranco.
        """
        if model is None:
            return pose

        partes = medidas.medir_todas_as_partes(pose, model)
        alvo = colisao.resolver_colisoes(pose, partes)

        # Juntas que o resolvedor empurrou (diferem da pose crua neste frame).
        corrigidas = {
            grupo: alvo[grupo]
            for grupo in alvo
            if grupo in pose and alvo[grupo] != pose[grupo]
        }

        molas = self._correcao_colisao.molas
        # Conjunto ativo = juntas com excedente agora + juntas com mola viva de
        # uma correção recente (ainda relaxando). As demais nem entram no laço.
        ativas = set(corrigidas) | set(molas)

        resultado = dict(pose)
        for grupo in ativas:
            if grupo not in pose:
                molas.pop(grupo, None)
                continue

            if grupo in corrigidas:
                # Primeira correção desta junta: semeia a mola na pose crua do
                # frame para a correção entrar gradual, sem salto.
                if grupo not in molas:
                    self._correcao_colisao._mola(grupo).definir(pose[grupo])
                alvo_mola = corrigidas[grupo]
            else:
                # Sem excedente: relaxa de volta à pose autoral (sem tranco).
                alvo_mola = pose[grupo]

            suavizado = self._correcao_colisao._mola(grupo).atualizar(dt, alvo_mola)

            if grupo not in corrigidas and self._mola_assentou(grupo, pose[grupo]):
                # Relaxou até a pose crua: descarta a mola e deixa a junta
                # passar intacta, para não filtrar o movimento autoral depois.
                molas.pop(grupo, None)
                continue

            resultado[grupo] = suavizado

        return resultado

    def _mola_assentou(self, grupo: str, alvo: Rotation3) -> bool:
        """Diz se a mola da junta já relaxou até ``alvo`` (posição e velocidade)."""
        mola = self._correcao_colisao.molas.get(grupo)
        if mola is None:
            return True

        tol_pos = colisao.CORRECAO_ASSENTA_POS
        tol_vel = colisao.CORRECAO_ASSENTA_VEL
        return (
            abs(mola.x.value - alvo.x) < tol_pos
            and abs(mola.y.value - alvo.y) < tol_pos
            and abs(mola.z.value - alvo.z) < tol_pos
            and abs(mola.x.velocity) < tol_vel
            and abs(mola.y.velocity) < tol_vel
            and abs(mola.z.velocity) < tol_vel
        )

    def _aplicar_clamps(self, pose: dict[str, Rotation3]) -> dict[str, Rotation3]:
        """Limites rígidos anatômicos. Aplicados UMA vez, no final.

        Braços não podem dobrar para dentro do corpo além dos limites.
        """
        resultado = dict(pose)

        # Right arm: z in [-75°, 180°] (dobra-interna protegida → erguido)
        if "right-arm" in resultado:
            r = resultado["right-arm"]
            z = max(_CLAMP_RIGHT_ARM_Z_MIN, min(_CLAMP_RIGHT_ARM_Z_MAX, r.z))
            if z != r.z:
                resultado["right-arm"] = Rotation3(r.x, r.y, z)

        # Left arm: z in [-180°, 75°] (espelho: erguido → dobra-interna protegida)
        if "left-arm" in resultado:
            r = resultado["left-arm"]
            z = max(_CLAMP_LEFT_ARM_Z_MIN, min(_CLAMP_LEFT_ARM_Z_MAX, r.z))
            if z != r.z:
                resultado["left-arm"] = Rotation3(r.x, r.y, z)

        return resultado

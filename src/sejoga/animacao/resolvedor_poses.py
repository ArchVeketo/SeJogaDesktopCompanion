"""Transições autorais, colisão dos braços e limites articulares."""

from __future__ import annotations

from math import pi, radians, tanh, tau

from sejoga.animacao import braco_tuning as tun
from sejoga.animacao.colisao_bracos import ResolvedorBracos
from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.nucleo.esqueleto import Rotation3
from sejoga.nucleo.modelo import Model

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                       Limites anatômicos (clamps)                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
# Eixos medidos no grafo de cena (tools/gerar_oraculo_cena.py --eixos), braço direito
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


def limitar_suave(
    valor: float,
    minimo: float,
    maximo: float,
    fracao_margem: float = tun.FRACAO_MARGEM_CLAMP_SUAVE,
    *,
    suavizar_minimo: bool = True,
) -> float:
    """Aproxima ``valor`` dos limites com tangente hiperbólica sem parada seca.

    Preserva inclinação 1.0 exata no trecho central da faixa e aplica ``tanh``
    apenas nas margens finais (``fracao_margem`` da largura total), seguido do
    clamp rígido ``max/min`` como segurança final (estudo §4.7).
    """
    largura = maximo - minimo
    if largura <= 0.0 or fracao_margem <= 0.0:
        return max(minimo, min(maximo, valor))
    margem = largura * min(0.5, fracao_margem)
    limite_inf = minimo + margem
    limite_sup = maximo - margem
    if valor > limite_sup:
        valor = limite_sup + margem * tanh((valor - limite_sup) / margem)
    elif suavizar_minimo and valor < limite_inf:
        valor = limite_inf - margem * tanh((limite_inf - valor) / margem)
    return max(minimo, min(maximo, valor))


_VEL_MAX_RAD_S = 10.0


def _delta_angular_curto(alvo: float, origem: float) -> float:
    """Retorna o menor arco angular em ``[-pi, pi]`` de ``origem`` até ``alvo``."""
    return ((alvo - origem + pi) % tau) - pi


def _clamp_vel(valor: float) -> float:
    return max(-_VEL_MAX_RAD_S, min(_VEL_MAX_RAD_S, valor))


class PoseResolver:
    """Interpola poses com preservação de momento angular e aplica limites do rig."""

    def __init__(self) -> None:
        """Inicia sem transição ativa."""
        self._resolvedor_bracos: ResolvedorBracos | None = None
        self._transition_from: dict[str, Rotation3] = {}
        self._transition_vel: dict[str, Rotation3] = {}
        self._ultima_pose: dict[str, Rotation3] = {}
        self._velocidades: dict[str, Rotation3] = {}
        self._transition_seconds = 0.0
        self._state_time = 0.0

    def iniciar_transicao(
        self,
        pose_atual: dict[str, Rotation3],
        transition_seconds: float = 0.55,
    ) -> None:
        """Guarda a pose e a velocidade angular de saída para inertialização."""
        self._transition_from = dict(pose_atual)
        self._transition_vel = dict(self._velocidades)
        self._transition_seconds = max(0.0, transition_seconds)
        self._state_time = 0.0

    def _interpolar_transicao(
        self, pose_alvo: dict[str, Rotation3]
    ) -> dict[str, Rotation3]:
        """Interpola a pose alvo usando transição quíntica e impulso de velocidade."""
        dur = self._transition_seconds
        u = max(0.0, min(1.0, self._state_time / dur))
        peso = suavizar_quintico(u)
        impulso_vel = dur * u * (1.0 - u) ** 2
        pose: dict[str, Rotation3] = {}
        for grupo, alvo in pose_alvo.items():
            origem = self._transition_from.get(grupo, alvo)
            vel = self._transition_vel.get(grupo, Rotation3())
            pose[grupo] = Rotation3(
                origem.x + _delta_angular_curto(alvo.x, origem.x) * peso + vel.x * impulso_vel,
                origem.y + _delta_angular_curto(alvo.y, origem.y) * peso + vel.y * impulso_vel,
                origem.z + _delta_angular_curto(alvo.z, origem.z) * peso + vel.z * impulso_vel,
            )
        return pose

    def _atualizar_velocidades(
        self, dt: float, pose: dict[str, Rotation3]
    ) -> None:
        """Registra velocidades angulares do quadro atual para o próximo blend."""
        if dt > 1e-5 and self._ultima_pose:
            novas_vels: dict[str, Rotation3] = {}
            for grupo, rot in pose.items():
                prev = self._ultima_pose.get(grupo)
                if prev is not None:
                    novas_vels[grupo] = Rotation3(
                        _clamp_vel(_delta_angular_curto(rot.x, prev.x) / dt),
                        _clamp_vel(_delta_angular_curto(rot.y, prev.y) / dt),
                        _clamp_vel(_delta_angular_curto(rot.z, prev.z) / dt),
                    )
            self._velocidades = novas_vels
        self._ultima_pose = dict(pose)

    def resolver(
        self,
        dt: float,
        pose_alvo: dict[str, Rotation3],
        *,
        model: Model | None = None,
        state_time: float | None = None,
    ) -> dict[str, Rotation3]:
        """Resolve a pose composta e preserva as restrições anatômicas."""
        if state_time is not None:
            self._state_time = state_time

        if self._state_time < self._transition_seconds and self._transition_seconds > 1e-6:
            pose = self._interpolar_transicao(pose_alvo)
        else:
            pose = dict(pose_alvo)
        self._state_time += dt

        pose = self._aplicar_clamps(pose)
        if model is not None:
            if self._resolvedor_bracos is None or self._resolvedor_bracos.model is not model:
                self._resolvedor_bracos = ResolvedorBracos(model)
            pose = self._aplicar_clamps(self._resolvedor_bracos.resolver(pose))

        self._atualizar_velocidades(dt, pose)
        return pose

    def _aplicar_clamps(self, pose: dict[str, Rotation3]) -> dict[str, Rotation3]:
        """Limites rígidos anatômicos. Aplicados UMA vez, no final.

        Braços não podem dobrar para dentro do corpo além dos limites.
        """
        resultado = dict(pose)

        # Right arm: elevação Z (erguido → um pouco além de reto p/ baixo);
        # azimute Y em faixa ampla (contém só deriva). Limites em braco_tuning.
        if "right-arm" in resultado:
            r = resultado["right-arm"]
            y = limitar_suave(r.y, _CLAMP_ARM_Y_MIN, _CLAMP_ARM_Y_MAX)
            z = limitar_suave(r.z, _CLAMP_RIGHT_ARM_Z_MIN, _CLAMP_RIGHT_ARM_Z_MAX)
            if y != r.y or z != r.z:
                resultado["right-arm"] = Rotation3(r.x, y, z)

        # Left arm: espelho.
        if "left-arm" in resultado:
            r = resultado["left-arm"]
            y = limitar_suave(r.y, _CLAMP_ARM_Y_MIN, _CLAMP_ARM_Y_MAX)
            z = limitar_suave(r.z, _CLAMP_LEFT_ARM_Z_MIN, _CLAMP_LEFT_ARM_Z_MAX)
            if y != r.y or z != r.z:
                resultado["left-arm"] = Rotation3(r.x, y, z)

        # Cotovelo: dobradiça de um lado só (sem hiperextensão), espelhado.
        # O mínimo (0°) é parada anatômica reta; suaviza-se a flexão máxima.
        for grupo, sinal in (("ant-arm", 1.0), ("ant-arm2", -1.0)):
            if grupo in resultado:
                r = resultado[grupo]
                flexao = limitar_suave(
                    sinal * r.z,
                    _CLAMP_COTOVELO_MIN,
                    _CLAMP_COTOVELO_MAX,
                    suavizar_minimo=False,
                )
                if sinal * flexao != r.z:
                    resultado[grupo] = Rotation3(r.x, r.y, sinal * flexao)

        return resultado

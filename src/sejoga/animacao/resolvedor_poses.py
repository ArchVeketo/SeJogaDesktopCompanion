"""Transições autorais, colisão dos braços e limites articulares."""

from __future__ import annotations

from math import pi, radians, tanh, tau

from sejoga.animacao import braco_tuning as tun
from sejoga.animacao.colisao_bracos import ResolvedorBracos
from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.ritmo_humano import MAX_FATOR_CASCATA, fator_cascata_grupo
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


def _medir_velocidades_grupos(
    dt: float,
    atual: dict[str, Rotation3],
    anterior: dict[str, Rotation3],
) -> dict[str, Rotation3]:
    """Mede velocidades angulares por junta respeitando o menor arco em ``[-pi, pi]``."""
    novas_vels: dict[str, Rotation3] = {}
    for grupo, rot in atual.items():
        prev = anterior.get(grupo)
        if prev is not None:
            novas_vels[grupo] = Rotation3(
                _clamp_vel(_delta_angular_curto(rot.x, prev.x) / dt),
                _clamp_vel(_delta_angular_curto(rot.y, prev.y) / dt),
                _clamp_vel(_delta_angular_curto(rot.z, prev.z) / dt),
            )
    return novas_vels


class PoseResolver:
    """Resolve transições por inertialização quíntica, colisão dos braços e limites do rig."""

    def __init__(self) -> None:
        """Inicia sem transição ativa."""
        self._resolvedor_bracos: ResolvedorBracos | None = None
        self._transition_from: dict[str, Rotation3] = {}
        self._transition_vel: dict[str, Rotation3] = {}
        self._ultima_pose: dict[str, Rotation3] = {}
        self._ultima_pose_alvo: dict[str, Rotation3] = {}
        self._velocidades: dict[str, Rotation3] = {}
        self._vel_alvo: dict[str, Rotation3] = {}
        self._vel_relativa: dict[str, Rotation3] = {}
        self._transition_seconds = 0.0
        self._state_time = 0.0

    @property
    def velocidades_saida(self) -> dict[str, Rotation3]:
        """Últimas velocidades angulares da pose resolvida (pós-clamps e colisão)."""
        return dict(self._velocidades)

    @property
    def velocidades_alvo(self) -> dict[str, Rotation3]:
        """Últimas velocidades angulares estimadas da pose alvo de entrada."""
        return dict(self._vel_alvo)

    @property
    def velocidades_relativas(self) -> dict[str, Rotation3]:
        """Velocidade angular relativa ``saida - alvo`` para diagnóstico em alvo móvel."""
        return dict(self._vel_relativa)

    def iniciar_transicao(
        self,
        pose_atual: dict[str, Rotation3],
        transition_seconds: float = 0.55,
    ) -> None:
        """Guarda a pose e a velocidade angular de saída (inertialização Hermite quíntica)."""
        if self._resolvedor_bracos is not None:
            # ``pose_atual`` já traz qualquer recuo aplicado anteriormente; zerar
            # evita somar duas vezes o deslocamento no primeiro frame da transição.
            self._resolvedor_bracos.zerar()
        self._transition_from = dict(pose_atual)
        self._transition_vel = dict(self._velocidades)
        self._transition_seconds = max(0.0, transition_seconds)
        self._state_time = 0.0

    def _interpolar_transicao(
        self, pose_alvo: dict[str, Rotation3]
    ) -> dict[str, Rotation3]:
        """Interpolação Hermite quíntica em cascata orgânica por região do rig (v2.0).

        Tronco e quadril lideram, cabeça/braços seguem e mãos/antenas assentam por último.
        """
        dur_base = self._transition_seconds
        pose: dict[str, Rotation3] = {}
        for grupo, alvo in pose_alvo.items():
            dur_g = max(1e-5, dur_base * fator_cascata_grupo(grupo))
            u = max(0.0, min(1.0, self._state_time / dur_g))
            if u >= 1.0:
                pose[grupo] = alvo
                continue
            peso = suavizar_quintico(u)
            impulso_vel = dur_g * u * (1.0 - u) ** 2
            origem = self._transition_from.get(grupo, alvo)
            vel = self._transition_vel.get(grupo, Rotation3())
            pose[grupo] = Rotation3(
                origem.x + _delta_angular_curto(alvo.x, origem.x) * peso + vel.x * impulso_vel,
                origem.y + _delta_angular_curto(alvo.y, origem.y) * peso + vel.y * impulso_vel,
                origem.z + _delta_angular_curto(alvo.z, origem.z) * peso + vel.z * impulso_vel,
            )
        return pose

    def _atualizar_velocidades(
        self,
        dt: float,
        pose: dict[str, Rotation3],
        pose_alvo: dict[str, Rotation3],
    ) -> None:
        """Registra velocidades da saída, do alvo e a velocidade relativa entre os dois lados."""
        if dt > 1e-5:
            if self._ultima_pose:
                self._velocidades = _medir_velocidades_grupos(
                    dt, pose, self._ultima_pose
                )
            if self._ultima_pose_alvo:
                self._vel_alvo = _medir_velocidades_grupos(
                    dt, pose_alvo, self._ultima_pose_alvo
                )
            self._vel_relativa = {
                grupo: Rotation3(
                    self._velocidades[grupo].x - self._vel_alvo.get(grupo, Rotation3()).x,
                    self._velocidades[grupo].y - self._vel_alvo.get(grupo, Rotation3()).y,
                    self._velocidades[grupo].z - self._vel_alvo.get(grupo, Rotation3()).z,
                )
                for grupo in self._velocidades
            }
        self._ultima_pose = dict(pose)
        self._ultima_pose_alvo = dict(pose_alvo)

    def resolver(
        self,
        dt: float,
        pose_alvo: dict[str, Rotation3],
        *,
        model: Model | None = None,
        state_time: float | None = None,
        peso_colisao: float = 1.0,
        aplicar_colisao: bool = True,
        leg_pose: object | None = None,
        caixas_isentas_por_lado: dict[str, set[str]] | None = None,
    ) -> dict[str, Rotation3]:
        """Resolve a pose por inertialização quíntica, clamps anatômicos e colisão."""
        if state_time is not None:
            self._state_time = state_time

        if (
            self._state_time < self._transition_seconds * MAX_FATOR_CASCATA
            and self._transition_seconds > 1e-6
        ):
            pose = self._interpolar_transicao(pose_alvo)
        else:
            pose = dict(pose_alvo)
        self._state_time += dt

        if aplicar_colisao:
            if model is not None:
                if self._resolvedor_bracos is None or self._resolvedor_bracos.model is not model:
                    self._resolvedor_bracos = ResolvedorBracos(model)
                pose = self._resolvedor_bracos.resolver(
                    pose,
                    peso=peso_colisao,
                    dt=dt,
                    leg_pose=leg_pose,
                    caixas_isentas_por_lado=caixas_isentas_por_lado,
                )
            elif self._resolvedor_bracos is not None:
                self._resolvedor_bracos.relaxar_suave(dt)
        pose = self._aplicar_clamps(pose)

        self._atualizar_velocidades(dt, pose, pose_alvo)
        return pose

    def resolver_colisao_bracos(
        self,
        pose: dict[str, Rotation3],
        *,
        model: Model | None,
        dt: float,
        peso_colisao: float = 1.0,
        leg_pose: object | None = None,
        caixas_isentas_por_lado: dict[str, set[str]] | None = None,
    ) -> dict[str, Rotation3]:
        """Executa passe único de colisão pós-camadas secundárias + clamps finais."""
        if model is None:
            if self._resolvedor_bracos is not None:
                self._resolvedor_bracos.relaxar_suave(dt)
            return dict(pose)
        if self._resolvedor_bracos is None or self._resolvedor_bracos.model is not model:
            self._resolvedor_bracos = ResolvedorBracos(model)
        corrigida = self._resolvedor_bracos.resolver(
            pose,
            peso=peso_colisao,
            dt=dt,
            leg_pose=leg_pose,
            caixas_isentas_por_lado=caixas_isentas_por_lado,
        )
        corrigida = self._aplicar_clamps(corrigida)
        self._ultima_pose = dict(corrigida)
        return corrigida

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

"""Articula as pernas e botas do GLTF com pivôs encadeados."""

from panda3d.core import Mat4, Vec3

from sejoga.animacao.interpolacao import suavizar_quintico
from sejoga.animacao.movimento_pernas import apoiar_passada
from sejoga.render.pernas_tecido import PernasTecido

#: (lado da LegPose, coxa, joelho, canela, bota).
LADOS = (
    ("left", "coxa-esquerda", "joelho-esquerdo", "canela-esquerda", "left-feet"),
    ("right", "coxa-direita", "joelho-direito", "canela-direita", "right-feet"),
)
#: Fração do ângulo do joelho aplicada à peça ``joelho-*`` (rótula / bissetriz).
FRACAO_PECA_JOELHO = 0.5
_EIXO_X = Vec3(1, 0, 0)
_EIXO_Y = Vec3(0, 1, 0)
_EIXO_Z = Vec3(0, 0, 1)


def _rotacao_em_torno(pivo: Vec3, graus: float, eixo: Vec3 = _EIXO_X) -> Mat4:
    """Rotação (vetor-linha do Panda) de ``graus`` em ``eixo`` em torno de ``pivo``."""
    return (
        Mat4.translateMat(-pivo)
        * Mat4.rotateMat(graus, eixo)
        * Mat4.translateMat(pivo)
    )


class LowerBody:
    """Quadril, joelhos e botas aplicados com cinemática conectada e squash/stretch."""

    def __init__(self, renderer):
        """Mede os pivôs de repouso das pernas no referencial do modelo."""
        self.renderer = renderer
        r = renderer
        self._lados = []
        self.joints = []
        self.ground_offset = 0.0
        self.pelvis = r.model_np.find("**/pelvis")
        self._quadril = r.model_np.find("**/legs")
        self._quadril_repouso_inverso = Mat4(self._quadril.getMat(r.model_np))
        self._quadril_repouso_inverso.invertInPlace()
        for lado, coxa, joelho, canela, bota in LADOS:
            nos = {n: r.model_np.find("**/" + n) for n in (coxa, joelho, canela, bota)}
            if any(no.isEmpty() for no in nos.values()):
                continue
            dados = {
                "lado": lado,
                "nomes": (coxa, joelho, canela, bota),
                "quadril": Vec3(nos[coxa].getPos(r.model_np)),
                "joelho": Vec3(nos[joelho].getPos(r.model_np)),
                "tornozelo": Vec3(nos[bota].getPos(r.model_np)),
                "repouso_mundo": {n: Mat4(nos[n].getMat(r.model_np)) for n, no in nos.items()},
                "sola": nos[bota].getTightBounds(r.model_np)[0].z,
            }
            self._lados.append(dados)
            self.joints.extend((nos[coxa], nos[joelho]))
        self.pernas_tecido = PernasTecido(renderer, self._lados)

    def apply(self, pose, grounded, dt: float = 1 / 60):  # noqa: PLR0915
        """Dobra a cadeia conectada ponta-a-ponta e mede a correção de chão para o corpo."""
        r = self.renderer
        apoios = []
        movimento_quadril = self._quadril_repouso_inverso * self._quadril.getMat(r.model_np)
        controller = getattr(r.showbase, "animation_controller", None)
        estado = controller.state.value if controller and controller.state else ""
        marcha = grounded and estado in ("walk", "run")
        sentado = estado == "sleep" and controller.modo_sono == "sentado"
        speaker = getattr(r, "music_speaker", None)
        entrada = 1.0
        if (
            speaker
            and controller
            and controller.state
            and controller.state.value == "dance"
            and controller.dance_motion.style == "head_bob"
        ):
            entrada = suavizar_quintico(speaker.jump_progress)

        for dados in self._lados:
            coxa, joelho, canela, bota = dados["nomes"]
            lado = dados["lado"]
            ang_quadril = getattr(pose, lado) * entrada
            ang_joelho = getattr(pose, lado + "_knee") * entrada
            ang_yaw = getattr(pose, lado + "_yaw", 0.0) * entrada
            ang_roll = getattr(pose, lado + "_roll", 0.0) * entrada
            lift = getattr(pose, lado + "_lift")

            if marcha:
                # Amortecimento apenas durante a elevação do passo para manter a perna de apoio firme.
                ang_quadril, ang_joelho = apoiar_passada(
                    ang_quadril,
                    ang_joelho,
                    dados["quadril"].z - dados["joelho"].z,
                    dados["joelho"].z - dados["tornozelo"].z,
                    lift,
                )

            p_quadril = dados["quadril"]
            p_joelho = dados["joelho"]
            p_tornozelo = dados["tornozelo"]

            # 1. Rotação 3D da Coxa em torno do quadril (sagital X + roll Y + yaw Z)
            mat_quadril_3d = (
                _rotacao_em_torno(p_quadril, ang_roll, _EIXO_Y)
                * _rotacao_em_torno(p_quadril, ang_yaw, _EIXO_Z)
            )
            mat_quadril = _rotacao_em_torno(p_quadril, ang_quadril) * mat_quadril_3d

            # Ponto e eixo locais da junta do joelho após a coxa rotacionar em 3D
            j_atual = mat_quadril.xformPoint(p_joelho)
            eixo_joelho = mat_quadril_3d.xformVec(_EIXO_X)

            # A rótula se alonga na bissetriz, sem mudar o alcance da canela.
            flexao = suavizar_quintico(abs(ang_joelho) / 85.0)
            alongar_joelho = (
                Mat4.translateMat(-p_joelho)
                * Mat4.scaleMat(1.0, 1.0 + 0.25 * flexao, 1.0 + 0.50 * flexao)
                * Mat4.translateMat(p_joelho)
            )
            rot_joelho_meia = _rotacao_em_torno(j_atual, ang_joelho * FRACAO_PECA_JOELHO, eixo_joelho)
            mat_joelho_total = alongar_joelho * mat_quadril * rot_joelho_meia

            mat_canela_total = mat_quadril * _rotacao_em_torno(j_atual, ang_joelho, eixo_joelho)

            # 4. Bota (Cravada no tornozelo e nivelando sola no chão)
            torn_atual = mat_canela_total.xformPoint(p_tornozelo)
            pitch_bota = ang_quadril + ang_joelho
            nivelar_bota = 1.0 if marcha else suavizar_quintico((abs(pitch_bota) - 35.0) / 35.0)
            ajuste_bota = -pitch_bota * nivelar_bota
            if marcha and lift > 0.002:
                # Articula o tornozelo no balanço aéreo (ponta cai na saída e prepara calcanhar à frente).
                peso_balanco = min(1.0, lift / 0.045)
                ajuste_bota += max(-12.0, min(14.0, -ang_quadril * 0.45)) * peso_balanco
            if sentado:
                ajuste_bota += 5.0 * suavizar_quintico((abs(ang_quadril) - 45.0) / 55.0)

            rot_ajuste_bota = _rotacao_em_torno(torn_atual, ajuste_bota, eixo_joelho)
            mat_bota_total = mat_canela_total * rot_ajuste_bota

            # As botas são irmãs de "legs" no asset e recebem seu movimento aqui.
            transformacoes = (
                (coxa, mat_quadril),
                (joelho, mat_joelho_total),
                (canela, mat_canela_total),
                (bota, mat_bota_total),
            )
            for nome, transformacao in transformacoes:
                no = r._rig_nodes[nome]
                final = dados["repouso_mundo"][nome] * transformacao * movimento_quadril
                no.setMat(r.model_np, final)
                contorno = r._outline_nodes.get(nome)
                if contorno is not None:
                    contorno.setMat(no.getMat())

            if grounded:
                sola = r._rig_nodes[bota].getTightBounds(r.model_np)[0].z
                apoios.append((lift, dados["sola"] - sola))

        self.ground_offset = (
            min(apoios, default=(0, 0))[1]
            if marcha
            else max((apoio for _, apoio in apoios), default=0.0)
        )
        if getattr(self, "pernas_tecido", None) is not None:
            self.pernas_tecido.apply(self.renderer, pose, dt)

"""Articula as pernas separadas do rig (coxa, joelho, canela) e as botas.

O asset tem as pernas fatiadas em grupos próprios (``coxa-*``, ``joelho-*``,
``canela-*``) dentro de ``legs``; as botas (``left-feet``/``right-feet``) são
raízes irmãs. Nada de deformar vértices: cada peça recebe uma transformação
rígida calculada no referencial de ``model_np``:

- quadril: rotação em X em torno do pivô de ``coxa-*``;
- joelho: rotação em X em torno do pivô de ``joelho-*`` (ponto médio do short),
  aplicada à canela e à bota; a peça do joelho recebe metade do ângulo para
  tampar a dobra.

A convenção de sinal é a mesma do IK antigo (``setP`` no referencial de
``model_np``), então ``LegMotion`` não muda de significado.
"""

from panda3d.core import Mat4, TransformState, Vec3

from sejoga.nucleo.esqueleto import Rotation3

#: (lado da LegPose, coxa, joelho, canela, bota).
LADOS = (
    ("left", "coxa-esquerda", "joelho-esquerdo", "canela-esquerda", "left-feet"),
    ("right", "coxa-direita", "joelho-direito", "canela-direita", "right-feet"),
)
#: Fração do ângulo do joelho aplicada à peça ``joelho-*`` (tampa a dobra).
FRACAO_PECA_JOELHO = 0.5
_EIXO_X = Vec3(1, 0, 0)


def _rotacao_em_torno(pivo: Vec3, graus: float) -> Mat4:
    """Rotação (vetor-linha do Panda) de ``graus`` em X em torno de ``pivo``."""
    return (
        Mat4.translateMat(-pivo)
        * Mat4.rotateMat(graus, _EIXO_X)
        * Mat4.translateMat(pivo)
    )


class LowerBody:
    """Quadril, joelhos e botas aplicados sobre os nós do renderer."""

    def __init__(self, renderer):
        """Mede os pivôs de repouso das pernas no referencial do modelo."""
        self.renderer = renderer
        r = renderer
        self._lados = []
        self.joints = []
        for lado, coxa, joelho, canela, bota in LADOS:
            nos = {n: r.model_np.find("**/" + n) for n in (coxa, joelho, canela, bota)}
            if any(no.isEmpty() for no in nos.values()):
                continue
            dados = {
                "lado": lado,
                "nomes": (coxa, joelho, canela, bota),
                "quadril": Vec3(nos[coxa].getPos(r.model_np)),
                "joelho": Vec3(nos[joelho].getPos(r.model_np)),
                # Transformação local de repouso de cada peça (pai imediato).
                "repouso_local": {n: Mat4(no.getMat()) for n, no in nos.items()},
            }
            self._lados.append(dados)
            self.joints.extend((nos[coxa], nos[joelho]))

    def _local_com_pose(self, nome: str, local_repouso: Mat4) -> Mat4:
        """Repouso local + rotação vinda da pose do rig (clipes), se houver."""
        pose = getattr(self.renderer, "_ultima_pose", None) or {}
        rot = pose.get(nome)
        if rot is None:
            return Mat4(local_repouso)
        if isinstance(rot, Rotation3):
            x, y, z = rot.x, rot.y, rot.z
        else:
            x, y, z = rot
        if abs(x) + abs(y) + abs(z) < 1e-6:
            return Mat4(local_repouso)
        import math

        extra = TransformState.makeHpr(
            Vec3(math.degrees(y), math.degrees(x), math.degrees(z))
        ).getMat()
        return extra * local_repouso

    def _matrizes_da_perna(self, dados, pecas, quadril):
        r = self.renderer
        finais = {}
        for nome, local_dobra in pecas:
            no = r._rig_nodes.get(nome)
            if no is None:
                no = r.model_np.find("**/" + nome)
            if no.isEmpty():
                continue
            local = self._local_com_pose(nome, dados["repouso_local"][nome])
            pai_modelo = no.getParent().getMat(r.model_np)
            repouso_modelo = local * pai_modelo
            # A coxa gira em torno do próprio pivô; o resto dobra no joelho.
            final = repouso_modelo * local_dobra * quadril
            finais[nome] = (no, repouso_modelo, final)
        return finais

    def apply(self, pose, grounded):
        """Aplica a pose das pernas, mantendo as botas no chão quando apoiado."""
        r = self.renderer
        for dados in self._lados:
            coxa, joelho, canela, bota = dados["nomes"]
            lado = dados["lado"]
            ang_quadril = getattr(pose, lado)
            ang_joelho = getattr(pose, lado + "_knee")
            lift = getattr(pose, lado + "_lift")
            quadril = _rotacao_em_torno(dados["quadril"], ang_quadril)
            dobra = _rotacao_em_torno(dados["joelho"], ang_joelho)
            meia_dobra = _rotacao_em_torno(
                dados["joelho"], ang_joelho * FRACAO_PECA_JOELHO
            )
            pecas = (
                (coxa, Mat4.identMat()),
                (joelho, meia_dobra),
                (canela, dobra),
                (bota, dobra),
            )
            finais = self._matrizes_da_perna(dados, pecas, quadril)
            correcao = Mat4.identMat()
            if (
                grounded and bota in finais
                and abs(ang_quadril) < 40.0 and abs(ang_joelho) < 50.0
            ):
                # Mantém a sola onde estava em repouso (mais o passo) e leva a
                # canela/joelho junto, para o short não descolar da bota.
                no, repouso_modelo, final = finais[bota]
                no.setMat(r.model_np, repouso_modelo)
                antes = no.getTightBounds(r.model_np)[0].z
                no.setMat(r.model_np, final)
                depois = no.getTightBounds(r.model_np)[0].z
                correcao = Mat4.translateMat(0, 0, antes - depois + lift)
            for nome, (no, _repouso, final) in finais.items():
                if nome != coxa:
                    final = final * correcao
                no.setMat(r.model_np, final)
                contorno = r._outline_nodes.get(nome)
                if contorno is not None:
                    contorno.setMat(no.getMat())

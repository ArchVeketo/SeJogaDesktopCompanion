"""Additional runtime joints around the existing skinless asset hierarchy.

Os pivôs (coluna, pescoço, ombros) ficam sob ``soft-spine-facing``, um nó com a
MESMA transformação do nó raiz do asset (que gira o mascote de frente). Assim o
``setHpr`` dos pivôs vale no referencial de AUTORIA (+X direita, +Y frente,
+Z cima), o mesmo das juntas do rig e de ``movimento_corpo``: pitch negativo inclina
o tronco para a FRENTE, roll positivo tomba o topo para a DIREITA do mascote
(medido em ``tests/test_tronco_quadro.py``). Antes os pivôs moravam em
``model_np`` sem esse giro, e o pitch/roll saíam invertidos em relação ao resto.
"""

from math import sin

from sejoga.animacao import movimento_corpo_tuning as tune
from sejoga.animacao.movimento_corpo import Spring, clamp


def no_de_facing(root):
    """Nó raiz do asset: carrega o giro de frente do mascote.

    Usa o pai de ``legs``, que o FlexibleRig nunca re-parenta (antes e depois
    da montagem dos pivôs ele continua filho direto do nó raiz).
    """
    return root.find("**/legs").getParent()


def _recapturar_bases(renderer) -> None:
    """Recaptura a pose base dos nós do rig depois do re-parent.

    Os offsets de autoria continuam relativos ao pai imediato. O wrtReparentTo
    embute no HPR local a orientação do pai antigo; sem recapturar, o
    apply_rig_pose sobrescreve esse HPR a cada frame.
    """
    for name, node in renderer._rig_nodes.items():
        renderer._rig_base_pos[name] = node.getPos()
        hpr = node.getHpr()
        renderer._rig_base_hpr[name] = (float(hpr.x), float(hpr.y), float(hpr.z))
        renderer._rig_base_scale[name] = node.getScale()
        renderer._rig_base_mat[name] = node.getMat()


def _anexar_cadeia_flexivel(root):
    facing = root.attachNewNode("soft-spine-facing")
    facing.setMat(no_de_facing(root).getMat(root))
    spine = facing.attachNewNode("soft-spine-pivot")
    spine.setPos(0, 0, tune.TRONCO_PIVO_Z)
    body = root.find("**/body")
    body.wrtReparentTo(spine)
    peitoral = root.find("**/peitoral")
    chest_parent = peitoral if not peitoral.isEmpty() else spine
    head = root.find("**/head")
    head.wrtReparentTo(chest_parent)
    neck = chest_parent.attachNewNode("soft-neck-pivot")
    neck.setPos(head.getPos(chest_parent))
    head.wrtReparentTo(neck)
    shoulders = []
    for name in ("right-arm", "left-arm"):
        arm = root.find("**/" + name)
        arm.wrtReparentTo(chest_parent)
        pivot = chest_parent.attachNewNode("soft-" + name + "-pivot")
        pivot.setPos(arm.getPos(chest_parent))
        arm.wrtReparentTo(pivot)
        shoulders.append(pivot)
    return spine, neck, shoulders


class FlexibleRig:
    """Molas da coluna, do pescoço e dos ombros sobre os nós do renderer."""

    def __init__(self, renderer):
        """Cria as cadeias flexíveis a partir dos nós do renderer."""
        self.renderer = renderer
        self.chains = [
            _anexar_cadeia_flexivel(root)
            for root in (renderer.model_np, renderer.outline_np)
        ]
        _recapturar_bases(renderer)
        self.spine = Spring(1.4, 0.55)
        self.spine_pitch = Spring(1.8, 0.50)
        self.neck = Spring(1.8, 0.48)
        self.neck_pitch = Spring(2.1, 0.46)
        self.shoulder = Spring(1.3, 0.42)
        self._air_clock = 0.0

    def _impulso_aereo(self, dt: float, motion) -> tuple[float, float, float, float]:
        airborne = (
            getattr(motion, "hanging", 0.0) > 0.1
            or abs(getattr(motion, "pitch", 0.0)) > 0.5
            or abs(getattr(motion, "stretch", 0.0)) > 0.06
        )
        if not airborne:
            self._air_clock = 0.0
            return (0.0, 0.0, 0.0, 0.0)
        self._air_clock += dt
        hang = clamp(getattr(motion, "hanging", 0.0), 0.0, 1.2)
        # Inércia aérea viva mesmo em queda vertical pura (sem drift lateral).
        air_roll = sin(self._air_clock * 4.4) * (2.6 + 1.8 * hang)
        air_pitch = -2.4 * hang + sin(self._air_clock * 5.6 + 0.7) * 2.2
        return (air_roll, air_pitch, -air_roll * 0.65, -air_pitch * 0.75 + 1.5 * hang)

    def update(self, dt, motion):
        """Avança as molas um passo de ``dt`` seguindo o movimento do corpo."""
        dt = max(0, min(0.05, dt))
        air_roll, air_pitch, air_neck_roll, air_neck_pitch = self._impulso_aereo(dt, motion)

        limb_swing = getattr(motion, "limb_swing", 0.0)
        pitch = getattr(motion, "pitch", 0.0)
        neck_pitch = getattr(motion, "neck_pitch", 0.0)
        arm_lag = getattr(motion, "arm_lag", 0.0)
        self.spine.update(
            dt, clamp(limb_swing * 0.12 + air_roll, -5.5, 5.5)
        )
        self.spine_pitch.update(
            dt, clamp(-pitch * 0.14 + air_pitch, -6.0, 6.0)
        )
        self.neck.update(
            dt, clamp(-limb_swing * 0.18 + air_neck_roll, -7.0, 7.0)
        )
        self.neck_pitch.update(
            dt, clamp(neck_pitch * 0.18 + air_neck_pitch, -7.0, 7.0)
        )
        self.shoulder.update(
            dt, clamp(arm_lag * 0.6 + air_roll * 0.5, -5.5, 5.5)
        )
        for spine, neck, shoulders in self.chains:
            spine.setPos(0, 0, tune.TRONCO_PIVO_Z)
            spine.setHpr(0, self.spine_pitch.value, self.spine.value)
            neck.setHpr(0, self.neck_pitch.value, self.neck.value)
            # arm_lag vem da velocidade do ROLL (tombo lateral): os dois braços
            # atrasam para o MESMO lado, em roll. Antes era P com sinal oposto
            # por lado (tesoura frente/trás), sem relação com o tombo lateral.
            for shoulder in shoulders:
                shoulder.setR(self.shoulder.value)

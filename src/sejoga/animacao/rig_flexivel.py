"""Additional runtime joints around the existing skinless asset hierarchy.

Os pivôs (coluna, pescoço, ombros) ficam sob ``soft-spine-facing``, um nó com a
MESMA transformação do nó raiz do asset (que gira o mascote de frente). Assim o
``setHpr`` dos pivôs vale no referencial de AUTORIA (+X direita, +Y frente,
+Z cima), o mesmo das juntas do rig e de ``body_motion``: pitch negativo inclina
o tronco para a FRENTE, roll positivo tomba o topo para a DIREITA do mascote
(medido em ``tests/test_tronco_quadro.py``). Antes os pivôs moravam em
``model_np`` sem esse giro, e o pitch/roll saíam invertidos em relação ao resto.
"""
from sejoga.animacao import body_motion_tuning as tune
from sejoga.animacao.body_motion import Spring, clamp


def no_de_facing(root):
    """Nó raiz do asset: carrega o giro de frente do mascote.

    Usa o pai de ``legs``, que o FlexibleRig nunca re-parenta (antes e depois
    da montagem dos pivôs ele continua filho direto do nó raiz).
    """
    return root.find('**/legs').getParent()


class FlexibleRig:
    def __init__(self, renderer):
        self.renderer = renderer
        model = renderer.model_np
        self.chains = []
        for root in (model, renderer.outline_np):
            facing = root.attachNewNode('soft-spine-facing')
            facing.setMat(no_de_facing(root).getMat(root))
            spine = facing.attachNewNode('soft-spine-pivot')
            spine.setPos(0, 0, tune.TRONCO_PIVO_Z)
            for name in ('body', 'head', 'right-arm', 'left-arm'):
                root.find('**/'+name).wrtReparentTo(spine)
            head = root.find('**/head')
            neck = spine.attachNewNode('soft-neck-pivot')
            neck.setPos(head.getPos(spine))
            head.wrtReparentTo(neck)
            shoulders = []
            for name in ('right-arm', 'left-arm'):
                arm = root.find('**/'+name)
                pivot = spine.attachNewNode('soft-'+name+'-pivot')
                pivot.setPos(arm.getPos(spine))
                arm.wrtReparentTo(pivot)
                shoulders.append(pivot)
            self.chains.append((spine, neck, shoulders))
        # Authored pose offsets remain relative to their immediate parent.
        # O wrtReparentTo embute no HPR local a orientação do pai antigo. A base
        # precisa ser recapturada depois do re-parent, senão apply_rig_pose
        # sobrescreve esse HPR a cada frame.
        for name, node in renderer._rig_nodes.items():
            renderer._rig_base_pos[name] = node.getPos()
            hpr = node.getHpr()
            renderer._rig_base_hpr[name] = (float(hpr.x), float(hpr.y), float(hpr.z))
            renderer._rig_base_scale[name] = node.getScale()
            renderer._rig_base_mat[name] = node.getMat()
        self.spine = Spring(1.4, .55)
        self.neck = Spring(1.8, .48)
        self.shoulder = Spring(1.3, .42)

    def update(self, dt, motion):
        dt = max(0, min(.05, dt))
        self.spine.update(dt, clamp(motion.limb_swing*.10, -3, 3))
        self.neck.update(dt, clamp(-motion.limb_swing*.16, -5, 5))
        self.shoulder.update(dt, clamp(motion.arm_lag*.6, -4, 4))
        for spine, neck, shoulders in self.chains:
            spine.setPos(0, 0, tune.TRONCO_PIVO_Z)
            spine.setHpr(0,0,self.spine.value)
            neck.setHpr(0,0,self.neck.value)
            # arm_lag vem da velocidade do ROLL (tombo lateral): os dois braços
            # atrasam para o MESMO lado, em roll. Antes era P com sinal oposto
            # por lado (tesoura frente/trás), sem relação com o tombo lateral.
            for shoulder in shoulders:
                shoulder.setR(self.shoulder.value)

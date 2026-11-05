"""Additional runtime joints around the existing skinless asset hierarchy."""
from .body_motion import Spring, clamp


class FlexibleRig:
    def __init__(self, renderer):
        self.renderer = renderer
        model = renderer.model_np
        self.chains = []
        for root in (model, renderer.outline_np):
            spine = root.attachNewNode('soft-spine-pivot')
            spine.setPos(0, 0, .44)
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
        for name, node in renderer._rig_nodes.items():
            renderer._rig_base_pos[name] = node.getPos()
        self.spine = Spring(1.4, .55)
        self.neck = Spring(1.8, .48)
        self.shoulder = Spring(1.3, .42)

    def update(self, dt, motion):
        dt = max(0, min(.05, dt))
        self.spine.update(dt, clamp(motion.limb_swing*.10, -3, 3))
        self.neck.update(dt, clamp(-motion.limb_swing*.16, -5, 5))
        self.shoulder.update(dt, clamp(motion.arm_lag*.6, -4, 4))
        for spine, neck, shoulders in self.chains:
            spine.setPos(0,0,.44)
            spine.setHpr(0,0,self.spine.value)
            neck.setHpr(0,0,self.neck.value)
            for side, shoulder in zip((1,-1), shoulders):
                shoulder.setP(self.shoulder.value*side)

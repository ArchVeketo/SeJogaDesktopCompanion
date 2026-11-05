"""Runtime pivots for the existing block fingers; original asset stays intact."""
from math import exp

GESTURES = {
    'hang_loose': (0, 75, 75, 75, 0),
    'thumbs_up': (0, 80, 80, 80, 80),
    'rock': (65, 0, 80, 80, 0),
    'finger_gun': (0, 0, 80, 80, 80),
}


class FingerGestures:
    def __init__(self, renderer):
        self.renderer = renderer
        self.presentation = 0.0
        self.pivots = []
        self.amounts = [0.0]*5
        for root in (renderer.model_np, renderer.outline_np):
            fingers = []
            # Right hand: thumb followed by index through little finger.
            for mesh_index in (25, 26, 27, 28, 29):
                mesh = root.find('**/mesh'+str(mesh_index))
                if mesh.isEmpty():
                    fingers.append(None)
                    continue
                parent = mesh.getParent()
                low, high = mesh.getTightBounds(parent)
                pivot = parent.attachNewNode('gesture-finger-'+str(mesh_index))
                pivot.setPos(low.x, (low.y+high.y)*.5, (low.z+high.z)*.5)
                mesh.wrtReparentTo(pivot)
                fingers.append(pivot)
            self.pivots.append(fingers)

    def update(self, dt, gesture):
        target = GESTURES.get(gesture, (0,0,0,0,0))
        blend = 1-exp(-max(0,min(.05,dt))*10)
        self.presentation += ((1.0 if gesture in GESTURES else 0.0)-self.presentation)*blend
        if self.presentation > .001:
            # Resolve the wrist in model space: elbow rotations must not turn
            # the palm edge-on to the fixed frontal camera.
            renderer = self.renderer
            hand = renderer._rig_nodes['hand']
            current = hand.getHpr(renderer.model_np)
            desired = (0, 180, 90 if gesture != 'finger_gun' else 0)
            values = [a + ((b-a+180)%360-180)*self.presentation
                      for a,b in zip(current, desired)]
            hand.setHpr(renderer.model_np, *values)
            renderer._outline_nodes['hand'].setHpr(renderer.outline_np, *values)
        self.amounts = [a+(b-a)*blend for a,b in zip(self.amounts,target)]
        for fingers in self.pivots:
            for pivot, angle in zip(fingers, self.amounts):
                if pivot is not None:
                    pivot.setR(angle)

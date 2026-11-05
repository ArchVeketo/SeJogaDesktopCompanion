"""Audio-driven dance phrasing with smoothed energy and style dwell time."""
from math import cos, exp, sin, tau


class DanceMotion:
    def __init__(self):
        self.phase = 0.0
        self.energy = self.bass = 0.0
        self.style = 'head_bob'
        self.dwell = 0.0
        self.pose = {}
        self.dt = 0.0

    def update(self, dt, level, bass, bpm=None, beat=False):
        self.dt = dt
        blend = 1-exp(-max(0,dt)*3)
        self.energy += (max(0,min(1,level))-self.energy)*blend
        self.bass += (max(0,min(1,bass))-self.bass)*blend
        tempo = max(55,min(180,bpm or 90))
        self.phase += dt*tempo/60*tau
        if beat:
            # Soft phase correction avoids a discontinuity in the joints.
            error = (self.phase+tau/2)%tau-tau/2
            self.phase -= error*.25
        self.dwell += dt
        desired = ('breakdance' if self.energy > .65 and self.bass > .3
                   else 'hip_hop' if self.bass > .12 and self.energy > .25
                   else 'head_bob')
        if desired != self.style and self.dwell > 3:
            self.style, self.dwell = desired, 0.0

    def apply(self, rig):
        p = self.phase
        pulse = (1-cos(p))*.5
        amount = .4+self.energy*.6
        rig.set_rotation('door', y=0)
        if self.style == 'head_bob':
            rig.set_rotation('head', x=-2-pulse*7, z=sin(p*.5)*2)
            rig.set_rotation('body', x=-pulse*2, z=sin(p*.5)*1.5)
            rig.set_rotation('right-arm', z=60-sin(p)*3)
            rig.set_rotation('left-arm', z=-62+sin(p)*3)
        else:
            power = 1.6 if self.style == 'breakdance' else 1
            rig.set_rotation('body', x=-pulse*7*amount, z=sin(p*.5)*10*power*amount,
                             y=sin(p*.5)*14*power*amount)
            rig.set_rotation('head', x=-pulse*10, z=-sin(p*.5)*6)
            rig.set_rotation('right-arm', x=sin(p)*16, z=48-24*pulse*power)
            rig.set_rotation('left-arm', x=-sin(p)*16, z=-48+24*(1-pulse)*power)
        rig.set_rotation('ant-arm', z=-20-pulse*12)
        rig.set_rotation('ant-arm2', z=20+(1-pulse)*12)
        target = rig.pose()
        blend = 1-exp(-self.dt*7)
        from .rig import Rotation3
        for group, rotation in target.items():
            previous = self.pose.get(group, rotation)
            self.pose[group] = Rotation3(*(a+(b-a)*blend for a,b in zip(
                (previous.x, previous.y, previous.z), (rotation.x, rotation.y, rotation.z))))
        rig.current = dict(self.pose)

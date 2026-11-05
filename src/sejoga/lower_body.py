"""Deform the joined shorts and articulate existing boots without editing GLTF."""
from panda3d.core import GeomVertexReader, GeomVertexWriter, Mat4, Vec3, Point3


class LowerBody:
    def __init__(self, renderer):
        self.renderer = renderer
        mesh = renderer.model_np.find('**/mesh30')
        self.mesh = mesh
        geom = mesh.node().modifyGeom(0)
        self.data = geom.modifyVertexData()
        reader = GeomVertexReader(self.data, 'vertex')
        self.vertices = [Point3(reader.getData3()) for _ in range(self.data.getNumRows())]
        reader = GeomVertexReader(self.data, 'normal')
        self.normals = [Vec3(reader.getData3()) for _ in self.vertices]
        self.to_model = mesh.getMat(renderer.model_np)
        self.from_model = renderer.model_np.getMat(mesh)

    @staticmethod
    def rotate(pivot, angle):
        return Mat4.translateMat(-pivot)*Mat4.rotateMat(angle, Vec3(1, 0, 0))*Mat4.translateMat(pivot)

    def apply(self, pose, grounded):
        r = self.renderer
        hips = [Vec3(-.125, 0, .4375), Vec3(.125, 0, .4375)]
        angles = (pose.left, pose.right)
        thighs = [self.rotate(p, a) for p, a in zip(hips, angles)]
        writer = GeomVertexWriter(self.data, 'vertex')
        normals = GeomVertexWriter(self.data, 'normal')
        for vertex, normal in zip(self.vertices, self.normals):
            point = self.to_model.xformPoint(vertex)
            n = self.to_model.xformVec(normal)
            # Blend at the crotch and fade to the original waistband. Shared
            # vertices receive identical weights, so no seam opens in shorts.
            side = max(0, min(1, (point.x+.045)/.09))
            weight = max(0, min(1, (.44-point.z)/.12))
            moved = thighs[0].xformPoint(point)*(1-side)+thighs[1].xformPoint(point)*side
            turned = thighs[0].xformVec(n)*(1-side)+thighs[1].xformVec(n)*side
            writer.setData3(self.from_model.xformPoint(point*(1-weight)+moved*weight))
            normals.setData3(self.from_model.xformVec(n*(1-weight)+turned*weight).normalized())
        # Mirror the deformed shorts into the optional outline's own vertex data.
        outline = r.outline_np.find('**/mesh30')
        if not outline.isEmpty():
            outline.node().modifyGeom(0).setVertexData(self.data)
        for i, name in enumerate(('left-feet', 'right-feet')):
            foot = r._rig_nodes[name]
            original = foot.getMat(r.model_np)
            knee = Vec3(hips[i].x, 0, .25)
            bend = (pose.left_knee, pose.right_knee)[i]
            transform = original*self.rotate(knee, bend)*thighs[i]
            if grounded:
                before = foot.getTightBounds(r.model_np)[0].z
                foot.setMat(r.model_np, transform)
                after = foot.getTightBounds(r.model_np)[0].z
                lift = (pose.left_lift, pose.right_lift)[i]
                transform *= Mat4.translateMat(0, 0, before-after+lift)
            foot.setMat(r.model_np, transform)
            r._outline_nodes[name].setMat(r.outline_np, transform)

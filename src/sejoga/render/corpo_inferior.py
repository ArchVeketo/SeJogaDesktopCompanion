"""Deform the joined shorts and articulate existing boots without editing GLTF."""

from panda3d.core import GeomVertexReader, GeomVertexWriter, Mat4, Point3, Vec3


class LowerBody:
    """IK do quadril e dos joelhos sobre os nós do renderer."""

    def __init__(self, renderer):
        """Cria os pivôs do quadril e dos joelhos."""
        self.renderer = renderer
        mesh = renderer.model_np.find("**/mesh30")
        self.mesh = mesh
        geom = mesh.node().modifyGeom(0)
        self.data = geom.modifyVertexData()
        reader = GeomVertexReader(self.data, "vertex")
        self.vertices = [
            Point3(reader.getData3()) for _ in range(self.data.getNumRows())
        ]
        reader = GeomVertexReader(self.data, "normal")
        self.normals = [Vec3(reader.getData3()) for _ in self.vertices]
        self.to_model = mesh.getMat(renderer.model_np)
        self.from_model = renderer.model_np.getMat(mesh)
        self.hip_joints = []
        self.knee_joints = []
        self.hip_inverse_rest = []
        self.knee_inverse_rest = []
        for side, x in (("left", -0.125), ("right", 0.125)):
            hip = renderer.model_np.attachNewNode(side + "-hip-pivot")
            hip.setPos(x, 0, 0.4375)
            knee = hip.attachNewNode(side + "-knee-pivot")
            knee.setPos(0, 0, -0.1875)
            self.hip_joints.append(hip)
            self.knee_joints.append(knee)
            for joint, collection in (
                (hip, self.hip_inverse_rest),
                (knee, self.knee_inverse_rest),
            ):
                inverse = Mat4(joint.getMat(renderer.model_np))
                inverse.invertInPlace()
                collection.append(inverse)
        self.joints = self.hip_joints + self.knee_joints

    @staticmethod
    def rotate(pivot, angle):
        """Gira o pivô no ângulo dado."""
        return (
            Mat4.translateMat(-pivot)
            * Mat4.rotateMat(angle, Vec3(1, 0, 0))
            * Mat4.translateMat(pivot)
        )

    def apply(self, pose, grounded):  # noqa: PLR0915  # TODO convenção: fatiar sem prova visual na GPU arrisca mudar o movimento; lote próprio com caracterização
        """Aplica a pose das pernas, apoiada no chão ou não."""
        r = self.renderer
        angles = (pose.left, pose.right)
        for index in range(2):
            self.hip_joints[index].setP(angles[index])
            self.knee_joints[index].setP((pose.left_knee, pose.right_knee)[index])
        thighs = [
            inverse * joint.getMat(r.model_np)
            for inverse, joint in zip(
                self.hip_inverse_rest, self.hip_joints, strict=True
            )
        ]
        writer = GeomVertexWriter(self.data, "vertex")
        normals = GeomVertexWriter(self.data, "normal")
        for vertex, normal in zip(self.vertices, self.normals, strict=True):
            point = self.to_model.xformPoint(vertex)
            n = self.to_model.xformVec(normal)
            # Blend at the crotch and fade to the original waistband. Shared
            # vertices receive identical weights, so no seam opens in shorts.
            side = max(0, min(1, (point.x + 0.045) / 0.09))
            weight = max(0, min(1, (0.44 - point.z) / 0.12))
            moved = (
                thighs[0].xformPoint(point) * (1 - side)
                + thighs[1].xformPoint(point) * side
            )
            turned = thighs[0].xformVec(n) * (1 - side) + thighs[1].xformVec(n) * side
            writer.setData3(
                self.from_model.xformPoint(point * (1 - weight) + moved * weight)
            )
            normals.setData3(
                self.from_model.xformVec(
                    n * (1 - weight) + turned * weight
                ).normalized()
            )
        # Mirror the deformed shorts into the optional outline's own vertex data.
        outline = r.outline_np.find("**/mesh30")
        if not outline.isEmpty():
            outline.node().modifyGeom(0).setVertexData(self.data)
        for i, name in enumerate(("left-feet", "right-feet")):
            foot = r._rig_nodes[name]
            original = foot.getMat(r.model_np)
            transform = (
                original
                * self.knee_inverse_rest[i]
                * self.knee_joints[i].getMat(r.model_np)
            )
            if grounded:
                before = foot.getTightBounds(r.model_np)[0].z
                foot.setMat(r.model_np, transform)
                after = foot.getTightBounds(r.model_np)[0].z
                lift = (pose.left_lift, pose.right_lift)[i]
                transform *= Mat4.translateMat(0, 0, before - after + lift)
            foot.setMat(r.model_np, transform)
            r._outline_nodes[name].setMat(r.outline_np, transform)

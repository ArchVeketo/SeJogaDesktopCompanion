"""Renderiza o modelo isolado para conferir espessura, facetas e ventosas."""
from pathlib import Path

from panda3d.core import loadPrcFileData

loadPrcFileData('', 'window-type offscreen\nwin-size 512 512\naudio-library-name null\nload-display pandagl')
import gltf
import simplepbr
from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, DirectionalLight, Filename, NodePath, OrthographicLens

root = Path(__file__).resolve().parents[1]
base = ShowBase(windowType='offscreen')
base.setBackgroundColor(.035, .05, .12, 1)
model = NodePath(gltf.load_model(str(root / 'assets/model/tentacle.gltf')))
model.reparentTo(base.render)
lens = OrthographicLens()
lens.setFilmSize(.65, .65)
lens.setNearFar(.01, 10)
base.cam.node().setLens(lens)
base.cam.setPos(.8, 1.5, .47)
base.cam.lookAt(.03, 0, .23)
ambient = AmbientLight('ambient')
ambient.setColor((.55, .55, .55, 1))
base.render.setLight(base.render.attachNewNode(ambient))
key = DirectionalLight('key')
key.setColor((.85, .85, .85, 1))
light = base.render.attachNewNode(key)
light.setHpr(-30, -45, 0)
base.render.setLight(light)
simplepbr.init(use_normal_maps=False, use_emission_maps=False)
for _ in range(4):
    base.taskMgr.step()
    base.graphicsEngine.renderFrame()
path = root / '.local/tentacle-model-preview.png'
path.parent.mkdir(exist_ok=True)
assert base.win.getScreenshot().write(Filename.fromOsSpecific(str(path)))
print(path)
base.destroy()

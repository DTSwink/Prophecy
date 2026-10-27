"""Read the supplied FBX into a lightweight lab cache; never modify the source.

Full render geometry, atlas-sampled triangle colors, and the nine authored UCX
hulls. Coordinates stay in the FBX's metre-scale, grip-centred weapon space.
"""
import hashlib, json
from pathlib import Path
import fbx
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parents[1] / 'Exports/ImperialSpear/SM_ImperialSpear.fbx'
manager = fbx.FbxManager.Create()
scene = fbx.FbxScene.Create(manager, 'ReadOnlySpear')
loader = fbx.FbxImporter.Create(manager, 'import')
assert loader.Initialize(str(SOURCE), -1, manager.GetIOSettings())
assert loader.Import(scene)
# These exports use metres, +Z along the shaft, with an identity mesh transform.
assert scene.GetGlobalSettings().GetSystemUnit().GetScaleFactor() == 100
root = scene.GetRootNode()
nodes = [root.GetChild(i) for i in range(root.GetChildCount())]
render = next(n for n in nodes if n.GetName() == 'SM_ImperialSpear')
def points(node):
    mesh = node.GetMesh()
    matrix = node.EvaluateGlobalTransform()
    return np.array([list(matrix.MultT(mesh.GetControlPointAt(i)))[:3]
                     for i in range(mesh.GetControlPointsCount())])
vertices = points(render)
mesh = render.GetMesh()
assert all(mesh.GetPolygonSize(i) == 3 for i in range(mesh.GetPolygonCount()))
triangles = np.array([[mesh.GetPolygonVertex(i,j) for j in range(3)] for i in range(mesh.GetPolygonCount())])
uv = mesh.GetElementUV(0)
assert uv.GetMappingMode() == fbx.FbxLayerElement.EMappingMode.eByPolygonVertex
assert uv.GetReferenceMode() == fbx.FbxLayerElement.EReferenceMode.eIndexToDirect
coords = np.array([list(uv.GetDirectArray().GetAt(uv.GetIndexArray().GetAt(i))) for i in range(triangles.size)]).reshape(-1,3,2)
texture_path = SOURCE.parent / 'Textures/T_ImperialSpear_BaseColor.png'
texture = np.asarray(Image.open(texture_path).convert('RGB')) / 255
# Barycentric samples retain atlas regions without a 4K texture/GPU dependency.
samples = np.stack([coords.mean(1),coords[:,0]*.6+coords[:,1]*.2+coords[:,2]*.2,
                    coords[:,1]*.6+coords[:,0]*.2+coords[:,2]*.2,
                    coords[:,2]*.6+coords[:,0]*.2+coords[:,1]*.2],axis=1)
x = np.clip((samples[:,:,0] * texture.shape[1]).astype(int),0,texture.shape[1]-1)
y = np.clip(((1-samples[:,:,1]) * texture.shape[0]).astype(int),0,texture.shape[0]-1)
colors = texture[y,x].mean(1)
hulls = [points(n) for n in nodes if n.GetName().startswith('UCX_')]
assert len(hulls) == 9 and abs(np.ptp(vertices[:,2])-2.2) < 1e-6
objects_path = ROOT / 'data/objects.json'
objects = json.loads(objects_path.read_text(encoding='utf-8'))
# Initially line up the spear with the established sword grip. No mirroring or
# scaling: weapon-space axes remain orthonormal for the local editor gizmos.
sword = np.array(objects['sword']['vertices'])
_,basis = np.linalg.eigh(np.cov(sword.T))
z = basis[:,-1]; z *= np.sign(sword[np.linalg.norm(sword,axis=1).argmax()] @ z)
xaxis = np.array([1.,0,0]); xaxis -= z*(xaxis@z); xaxis /= np.linalg.norm(xaxis)
bind_q = Rotation.from_matrix(np.column_stack([xaxis,np.cross(z,xaxis),z])).as_quat()
objects['spear'] = dict(name='Imperial Spear',vertices=np.round(vertices,8).tolist(),triangles=triangles.flatten().tolist(),
    colors=np.round(colors,5).tolist(),collision=np.round(np.concatenate(hulls),8).tolist(),
    hulls=[np.round(h,8).tolist() for h in hulls],mass=1.2,longAxis=[0,0,1],
    bind=objects['sword'].get('bind',dict(position=[.07126077,.02707669,-.00062174],rotation=bind_q.tolist())),
    source=dict(file=str(SOURCE),sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                textureSha256=hashlib.sha256(texture_path.read_bytes()).hexdigest(),lengthMetres=2.2,
                colors='BaseColor atlas sampled per triangle; lab lighting',collision='Nine authored UCX hulls; cosmetic tassel excluded'))
objects_path.write_text(json.dumps(objects,separators=(',',':')),encoding='utf-8')
manager.Destroy()
print(json.dumps(dict(vertices=len(vertices),triangles=len(triangles),hulls=len(hulls),length=2.2,source=objects['spear']['source']),indent=2))

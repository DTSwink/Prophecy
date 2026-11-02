"""Derived UE import with robust simplified collision; render data preserved."""
import pathlib,json,hashlib,fbx,numpy as np
from scipy.spatial import ConvexHull,cKDTree
root=pathlib.Path(__file__).resolve().parents[2];out=root/'Saved/Diagnostics/SpearPike20261030'
source=root/'Exports/ImperialSpear/SM_ImperialSpear.fbx'
dest=root/'Exports/ImperialSpear/Unreal/SM_ImperialSpear.fbx';dest.parent.mkdir(parents=True,exist_ok=True)
manager=fbx.FbxManager.Create();scene=fbx.FbxScene.Create(manager,'SpearCollisionRepair');imp=fbx.FbxImporter.Create(manager,'Read')
assert imp.Initialize(str(source),-1,manager.GetIOSettings()) and imp.Import(scene);imp.Destroy()
nodes={scene.GetRootNode().GetChild(i).GetName():scene.GetRootNode().GetChild(i) for i in range(scene.GetRootNode().GetChildCount())}
def points(n):
    m=n.GetMesh();t=n.EvaluateGlobalTransform();return np.array([list(t.MultT(m.GetControlPointAt(i)))[:3] for i in range(m.GetControlPointsCount())])
original=json.loads((out/'collision-points.json').read_text());fix=json.loads((out/'collision-repaired.json').read_text())
options=[]
for x in (-1,1):
 for y in (-1,1):
  sign=np.array([x,y,1]);error=max(cKDTree(np.array(original[i])).query(points(nodes[f'UCX_SM_ImperialSpear_{i:02}'])*sign*100)[0].max() for i in range(17));options.append((error,x,y))
error,x,y=min(options);assert error<.00002,options
sign=np.array([x,y,1]);receipt={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'ue_axis_sign':sign.tolist(),'match_error_cm':error,'changes':[]}
render=nodes['SM_ImperialSpear'].GetMesh()
def render_signature(m):
    return hashlib.sha256(repr(([list(m.GetControlPointAt(i)) for i in range(m.GetControlPointsCount())],[[m.GetPolygonVertex(i,j) for j in range(m.GetPolygonSize(i))] for i in range(m.GetPolygonCount())])).encode()).hexdigest()
before=render_signature(render)
fix['changes'].append({'hull':16,'before':38,'after':31,'collapse_tip_ring':True,
    'max_vertex_shift_cm':.015313,'reason':'Collapse the sub-millimetre collision tip ring to its centre; keep blade length.'})
for change in fix['changes']:
    i=change['hull'];n=nodes[f'UCX_SM_ImperialSpear_{i:02}'];old=n.GetMesh();world=points(n)
    if change.get('collapse_tip_ring'):
        indices=np.where(world[:,2]*100>116)[0];assert len(indices)==8
        keep=[j for j in range(len(world)) if j not in indices]
        local=np.array([list(old.GetControlPointAt(j))[:3] for j in keep])
        tip=np.array([list(old.GetControlPointAt(j))[:3] for j in indices]).mean(axis=0)
        local=np.vstack([local,tip])
    else:
        tree=cKDTree(world*sign*100);dist,indices=tree.query(change['removed']);assert max(dist)<.00002
        keep=[j for j in range(len(world)) if j not in indices];local=np.array([list(old.GetControlPointAt(j))[:3] for j in keep])
    hull=ConvexHull(local);mesh=fbx.FbxMesh.Create(scene,n.GetName()+'_Jolt');mesh.InitControlPoints(len(local))
    for j,p in enumerate(local):mesh.SetControlPointAt(fbx.FbxVector4(*p),j)
    for tri,plane in zip(hull.simplices,hull.equations):
        a,b,c=tri
        if np.dot(np.cross(local[b]-local[a],local[c]-local[a]),plane[:3])<0:b,c=c,b
        mesh.BeginPolygon();mesh.AddPolygon(int(a));mesh.AddPolygon(int(b));mesh.AddPolygon(int(c));mesh.EndPolygon()
    n.SetNodeAttribute(mesh);old.Destroy();receipt['changes'].append(change)
assert render_signature(render)==before
exp=fbx.FbxExporter.Create(manager,'Write');assert exp.Initialize(str(dest),-1,manager.GetIOSettings()) and exp.Export(scene);exp.Destroy();manager.Destroy()
receipt['derived_fbx']=str(dest);receipt['render_geometry_sha256']=before;receipt['derived_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
(out/'collision-repair-receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))

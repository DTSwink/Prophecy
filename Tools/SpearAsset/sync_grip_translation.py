"""Prepare a verified main FBX for saved grip/blade transforms in a snapshot.

Reads the saved Blender geometry snapshot without touching the open scene.
Refuses other geometry changes. Keeps FBX topology, UVs, colors and materials;
transforms blade normals, recentres the grip pivot and updates collision and
sockets. Writes a candidate, not source. Does not export LODs or GLB.
"""
import hashlib,json
from pathlib import Path
import fbx
import numpy as np
from scipy.spatial import cKDTree

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/ThrowLab/SpearGripSync20261028'
SOURCE=ROOT/'Exports/ImperialSpear/SM_ImperialSpear.fbx'
snapshot=json.loads((OUT/'source-geometry.json').read_text(encoding='utf-8'))
assert hashlib.sha256(Path(snapshot['file']).read_bytes()).hexdigest()==snapshot['sha256'],'Saved Blender source changed'
old_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
old_grip=1.235
moving=[m for m in snapshot['meshes'] if m['name'].startswith(('03 ', 'Grip '))]
blade=next(m for m in snapshot['meshes'] if m['name'].startswith('06 '))
assert len(moving)==3
deltas=[np.array(m['matrix'])[:3,3] for m in moving]
delta=deltas[0]
assert all(np.max(np.abs(d-delta))<1e-9 for d in deltas)
assert abs(delta[0])+abs(delta[1])<1e-9 and -.4<delta[2]<-.01
assert all(np.max(np.abs(np.array(m['matrix'])[:3,:3]-np.eye(3)))<1e-9 for m in moving)
leather=next(m for m in moving if m['name'].startswith('03 '))
new_grip=float((np.min(leather['vertices'],axis=0)[2]+np.max(leather['vertices'],axis=0)[2])/2)
assert abs(new_grip-old_grip-delta[2])<1e-6
shift=new_grip-old_grip

def load(path):
    manager=fbx.FbxManager.Create();scene=fbx.FbxScene.Create(manager,'Spear')
    importer=fbx.FbxImporter.Create(manager,'Read')
    assert importer.Initialize(str(path),-1,manager.GetIOSettings())
    assert importer.Import(scene);importer.Destroy()
    root=scene.GetRootNode()
    nodes={root.GetChild(i).GetName():root.GetChild(i) for i in range(root.GetChildCount())}
    return manager,scene,nodes

def points(node):
    mesh=node.GetMesh();matrix=node.EvaluateGlobalTransform()
    return np.array([list(matrix.MultT(mesh.GetControlPointAt(i)))[:3] for i in range(mesh.GetControlPointsCount())])

def set_points(node,vertices):
    matrix=node.EvaluateGlobalTransform().Inverse();mesh=node.GetMesh()
    for i,p in enumerate(vertices):mesh.SetControlPointAt(matrix.MultT(fbx.FbxVector4(*map(float,p))),i)

def surface(node):
    mesh=node.GetMesh()
    result={'triangles':[[mesh.GetPolygonVertex(i,j) for j in range(mesh.GetPolygonSize(i))] for i in range(mesh.GetPolygonCount())]}
    for label,count,get in [('uv',mesh.GetElementUVCount(),mesh.GetElementUV),('color',mesh.GetElementVertexColorCount(),mesh.GetElementVertexColor)]:
        result[label]=[]
        for i in range(count):
            e=get(i);d=e.GetDirectArray();ind=e.GetIndexArray()
            values=[list(d.GetAt(j)) if label!='color' else [getattr(d.GetAt(j),'m'+c) for c in ('Red','Green','Blue','Alpha')] for j in range(d.GetCount())]
            result[label].append([str(e.GetMappingMode()),str(e.GetReferenceMode()),values,[ind.GetAt(j) for j in range(ind.GetCount())]])
    return hashlib.sha256(json.dumps(result,separators=(',',':')).encode()).hexdigest()

manager,scene,nodes=load(SOURCE)
render=nodes['SM_ImperialSpear'];before=points(render);old_surface=surface(render)
assert scene.GetGlobalSettings().GetSystemUnit().GetScaleFactor()==100
baseline=[];current=[];labels=[];blade_labels=[]
for item in snapshot['meshes']:
    now=np.array(item['vertices'])
    old=(np.column_stack([now,np.ones(len(now))])@np.linalg.inv(np.array(item['matrix'])).T)[:,:3] if item in moving or item is blade else now
    baseline.extend((old-[0,0,old_grip])*[-1,-1,1])
    current.extend((now-[0,0,new_grip])*[-1,-1,1])
    labels.extend([item in moving]*len(now))
    blade_labels.extend([item is blade]*len(now))
baseline=np.array(baseline);current=np.array(current);labels=np.array(labels)
assert len(baseline)==len(before)
dist,index=cKDTree(baseline).query(before)
assert dist.max()<2e-6,('Other source geometry differs from FBX',float(dist.max()))
assert cKDTree(before).query(baseline)[0].max()<2e-6
move_mask=labels[index]
blade_mask=np.array(blade_labels)[index]
assert int(move_mask.sum())==sum(len(m['vertices']) for m in moving)
assert int(blade_mask.sum())==len(blade['vertices'])
after=before.copy();after[move_mask,2]+=float(delta[2]);after[:,2]-=shift
blade_matrix=np.array(blade['matrix']);flip=np.array([-1,-1,1])
def transform_blade(p):
    source=p*flip+[0,0,old_grip]
    world=(np.column_stack([source,np.ones(len(source))])@blade_matrix.T)[:,:3]
    return (world-[0,0,new_grip])*flip
after[blade_mask]=transform_blade(before[blade_mask])
assert cKDTree(current).query(after)[0].max()<2e-6
set_points(render,after)
# Only the scaled blade requires changed normals. Append transformed normals
# and retarget its corners, keeping any entries shared by other parts intact.
mesh=render.GetMesh();normal=mesh.GetElementNormal(0)
assert mesh.GetElementNormalCount()==1
assert normal.GetMappingMode()==fbx.FbxLayerElement.EMappingMode.eByPolygonVertex
assert normal.GetReferenceMode()==fbx.FbxLayerElement.EReferenceMode.eIndexToDirect
normal_indices=np.array([normal.GetIndexArray().GetAt(i) for i in range(normal.GetIndexArray().GetCount())])
normals=np.array([list(normal.GetDirectArray().GetAt(int(i)))[:3] for i in normal_indices])
corners=np.array([mesh.GetPolygonVertex(i,j) for i in range(mesh.GetPolygonCount()) for j in range(mesh.GetPolygonSize(i))])
normal_mask=blade_mask[corners];expected_normals=normals.copy()
expected_normals[normal_mask]=(normals[normal_mask]*flip)@np.linalg.inv(blade_matrix[:3,:3])*flip
expected_normals[normal_mask]/=np.linalg.norm(expected_normals[normal_mask],axis=1)[:,None]
new_indices={}
for i in np.flatnonzero(normal_mask):
    old_index=int(normal_indices[i])
    if old_index not in new_indices:new_indices[old_index]=normal.GetDirectArray().Add(fbx.FbxVector4(*map(float,expected_normals[i])))
    normal.GetIndexArray().SetAt(int(i),new_indices[old_index])
expected={'SM_ImperialSpear':after};hull_report=[]
for name,node in nodes.items():
    if not name.startswith('UCX_'):continue
    p=points(node);old_bounds=[p.min(0).tolist(),p.max(0).tolist()]
    if name.endswith('_00'):p[np.isclose(p[:,2],p[:,2].max(),atol=1e-7),2]+=float(delta[2])
    elif name.endswith('_01'):p[:,2]+=float(delta[2])
    elif name.endswith('_02'):p[np.isclose(p[:,2],p[:,2].min(),atol=1e-7),2]+=float(delta[2])
    if int(name.rsplit('_',1)[1])>=13:p=transform_blade(p)
    else:p[:,2]-=shift
    set_points(node,p);expected[name]=p
    hull_report.append({'name':name,'before':old_bounds,'after':[p.min(0).tolist(),p.max(0).tolist()]})
sockets={}
for name,node in nodes.items():
    if name.startswith('SOCKET_'):
        loc=list(node.LclTranslation.Get())
        if name.endswith('_BladeTip'):loc=transform_blade(np.array([loc]))[0].tolist()
        elif not name.endswith('_Grip'):loc[2]-=shift
        node.LclTranslation.Set(fbx.FbxDouble3(*loc));sockets[name]=loc
prop=render.FindProperty('Grip_reference_m')
if prop.IsValid():fbx.FbxPropertyDouble1(prop).Set(new_grip)
length=float(np.ptp(after[:,2]))
prop=render.FindProperty('Length_m')
if prop.IsValid():fbx.FbxPropertyDouble1(prop).Set(length)
assert surface(render)==old_surface
candidate=OUT/'SM_ImperialSpear.fbx'
exporter=fbx.FbxExporter.Create(manager,'Write')
assert exporter.Initialize(str(candidate),manager.GetIOPluginRegistry().GetNativeWriterFormat(),manager.GetIOSettings())
assert exporter.Export(scene);exporter.Destroy();manager.Destroy()
manager,scene,nodes=load(candidate)
assert surface(nodes['SM_ImperialSpear'])==old_surface
read_normal=nodes['SM_ImperialSpear'].GetMesh().GetElementNormal(0)
read_normals=np.array([list(read_normal.GetDirectArray().GetAt(read_normal.GetIndexArray().GetAt(i)))[:3] for i in range(read_normal.GetIndexArray().GetCount())])
assert np.max(np.abs(read_normals-expected_normals))<1e-8
errors={name:float(np.max(np.abs(points(nodes[name])-vertices))) for name,vertices in expected.items()}
assert max(errors.values())<1e-8
for name,loc in sockets.items():assert max(abs(a-b) for a,b in zip(nodes[name].LclTranslation.Get(),loc))<1e-8
manager.Destroy()
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==old_hash
assert hashlib.sha256(Path(snapshot['file']).read_bytes()).hexdigest()==snapshot['sha256']
report={'source_blend':snapshot['file'],'source_blend_sha256':snapshot['sha256'],'before_fbx_sha256':old_hash,'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'grip_shift_metres':shift,'old_grip_source_z':old_grip,'new_grip_source_z':new_grip,'moved_vertices':int(move_mask.sum()),'blade_vertices':int(blade_mask.sum()),'blade_transform':blade['matrix'],'length_metres':length,'source_match_max_error_metres':float(dist.max()),'readback_max_error_metres':max(errors.values()),'surface_digest_preserved':old_surface,'hulls':hull_report,'sockets':sockets}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('hulls','sockets')},indent=2))

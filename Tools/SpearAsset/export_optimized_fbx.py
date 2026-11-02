"""Replace only the render mesh in the already corrected main FBX.

Collision hulls, socket transforms, pivot/axis metadata and material bindings
come from the current verified FBX, never historical procedural constants.
"""
import fbx,json,hashlib
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];O=R/'Saved/Diagnostics/ImperialSpear/Optimization20261028'
surface=json.loads((O/'Optimized_Surface.json').read_text(encoding='utf-8'))
def load(path):
 manager=fbx.FbxManager.Create();scene=fbx.FbxScene.Create(manager,'Spear');imp=fbx.FbxImporter.Create(manager,'Read')
 assert imp.Initialize(str(path),-1,manager.GetIOSettings());assert imp.Import(scene);imp.Destroy()
 root=scene.GetRootNode();return manager,scene,{root.GetChild(i).GetName():root.GetChild(i) for i in range(root.GetChildCount())}
def matrix(n):return [list(n.EvaluateGlobalTransform().GetRow(i)) for i in range(4)]
def protected(nodes):
 result={}
 for name,n in nodes.items():
  if name=='SM_ImperialSpear':continue
  d={'matrix':matrix(n),'location':list(n.LclTranslation.Get()),'rotation':list(n.LclRotation.Get()),'scale':list(n.LclScaling.Get())}
  m=n.GetMesh()
  if m:d['vertices']=[list(m.GetControlPointAt(i)) for i in range(m.GetControlPointsCount())];d['faces']=[[m.GetPolygonVertex(i,j) for j in range(m.GetPolygonSize(i))] for i in range(m.GetPolygonCount())]
  result[name]=d
 return result
manager,scene,nodes=load(O/'Before_UserFinal.fbx');render=nodes['SM_ImperialSpear'];before=protected(nodes)
assert len([n for n in nodes if n.startswith('UCX_')])==17
assert len([n for n in nodes if n.startswith('SOCKET_')])==4
assert render.GetMaterialCount()==1 and render.GetMaterial(0).GetName()=='M_ImperialSpear_PBR'
# Existing FBX render rotation is the established Blender -Y-forward conversion.
assert np.max(np.abs(np.array(matrix(render))[:3,:3]-np.diag([-1.,-1.,1.])))<1e-6
mesh=fbx.FbxMesh.Create(scene,'SM_ImperialSpear_Optimized');mesh.InitControlPoints(len(surface['vertices']))
for i,p in enumerate(surface['vertices']):mesh.SetControlPointAt(fbx.FbxVector4(*p),i)
for tri in surface['triangles']:
 mesh.BeginPolygon(0)
 for index in tri:mesh.AddPolygon(index)
 mesh.EndPolygon()
def element(kind,name,values,ctor):
 e=getattr(mesh,'CreateElement'+kind)(name) if kind=='UV' else getattr(mesh,'CreateElement'+kind)()
 if kind!='UV':e.SetName(name)
 e.SetMappingMode(fbx.FbxLayerElement.EMappingMode.eByPolygonVertex);e.SetReferenceMode(fbx.FbxLayerElement.EReferenceMode.eDirect)
 for value in values:e.GetDirectArray().Add(ctor(*value))
 return e
element('Normal','Normals',surface['normals'],fbx.FbxVector4)
element('UV','UV0_SurfaceAtlas',surface['uv0'],fbx.FbxVector2)
element('UV','UV1_Lightmap',surface['uv1'],fbx.FbxVector2)
color_element=element('VertexColor','PommelCavity',surface['colors'],fbx.FbxColor)
mesh.GetLayer(0).SetVertexColors(color_element)
mat=mesh.CreateElementMaterial();mat.SetMappingMode(fbx.FbxLayerElement.EMappingMode.eByPolygon);mat.SetReferenceMode(fbx.FbxLayerElement.EReferenceMode.eIndexToDirect)
for tri in surface['triangles']:mat.GetIndexArray().Add(0)
mesh.GetLayer(0).SetMaterials(mat)
mesh.BuildMeshEdgeArray()
smooth=mesh.CreateElementSmoothing();smooth.SetMappingMode(fbx.FbxLayerElement.EMappingMode.eByEdge);smooth.SetReferenceMode(fbx.FbxLayerElement.EReferenceMode.eDirect)
for i in range(mesh.GetMeshEdgeCount()):smooth.GetDirectArray().Add(0)
assert mesh.GenerateTangentsData(0,True,False),'Tangent generation failed'
old=render.GetMesh();render.SetNodeAttribute(mesh);old.Destroy()
candidate=O/'SM_ImperialSpear.fbx';exp=fbx.FbxExporter.Create(manager,'Write')
assert exp.Initialize(str(candidate),manager.GetIOPluginRegistry().GetNativeWriterFormat(),manager.GetIOSettings());assert exp.Export(scene);exp.Destroy();manager.Destroy()
manager,scene,nodes=load(candidate);assert protected(nodes)==before,'Collision/socket change'
n=nodes['SM_ImperialSpear'];m=n.GetMesh();assert n.GetMaterial(0).GetName()=='M_ImperialSpear_PBR'
assert m.GetPolygonCount()==len(surface['triangles']);assert m.GetControlPointsCount()==len(surface['vertices'])
assert [[m.GetPolygonVertex(i,j) for j in range(3)] for i in range(m.GetPolygonCount())]==surface['triangles']
errors={'positions':float(np.max(np.abs(np.array([list(m.GetControlPointAt(i))[:3] for i in range(m.GetControlPointsCount())])-surface['vertices'])))}
def values(e,width,color=False):
 d=e.GetDirectArray();idx=e.GetIndexArray();indexed=e.GetReferenceMode()==fbx.FbxLayerElement.EReferenceMode.eIndexToDirect
 vals=[d.GetAt(idx.GetAt(i) if indexed else i) for i in range(len(surface['triangles'])*3)]
 return np.array([[getattr(v,'m'+c) for c in ('Red','Green','Blue','Alpha')] if color else list(v)[:width] for v in vals])
errors['normals']=float(np.max(np.abs(values(m.GetElementNormal(0),3)-surface['normals'])))
for i,key in enumerate(('uv0','uv1')):errors[key]=float(np.max(np.abs(values(m.GetElementUV(i),2)-surface[key])))
errors['linear_colors']=float(np.max(np.abs(values(m.GetElementVertexColor(0),4,True)-surface['colors'])))
assert max(errors.values())<1e-7,errors
assert m.GetElementTangentCount()>0
collision=[];sockets=[];flip=np.array([-1,-1,1])
for name,n in nodes.items():
 if name.startswith('UCX_'):
  m=n.GetMesh();world=n.EvaluateGlobalTransform()
  collision.append({'name':name,'vertices':[(np.array(list(world.MultT(m.GetControlPointAt(i)))[:3])*flip).tolist() for i in range(m.GetControlPointsCount())],'faces':[[m.GetPolygonVertex(i,j) for j in range(m.GetPolygonSize(i))] for i in range(m.GetPolygonCount())]})
 elif name.startswith('SOCKET_'):
  p=n.EvaluateGlobalTransform().GetT();sockets.append({'name':name,'position':(np.array(list(p)[:3])*flip).tolist()})
(O/'Collision_Sockets.json').write_text(json.dumps({'hulls':collision,'sockets':sockets},separators=(',',':')),encoding='utf-8')
manager.Destroy()
report={'candidate':str(candidate),'sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'vertices':len(surface['vertices']),'triangles':len(surface['triangles']),'readback_maximum_error':errors,'collision_hulls':17,'sockets':4,'collision_and_socket_data_exactly_preserved':True,'material_name':'M_ImperialSpear_PBR','uv_layers':['UV0_SurfaceAtlas','UV1_Lightmap'],'tangents_generated_from_uv0':True,'grip_reference_z':surface['grip']}
(O/'FBX_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

"""Broader real casting shoulders, correct named UV, and reseated relief.

Changes only housing depth, its UV and relief depth. The accepted blade and
all silhouette X/Z coordinates remain unchanged. Works from a retained mesh
backup so the profile is repeatable without accumulating deformation.
"""
import bpy,bmesh,math,ast,json,hashlib,shutil
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene']; bpy.context.window.scene=s; art=bpy.data.collections['SPEAR • editable components']
body=next(o for o in art.objects if o.name.startswith('07 •')); blade=next(o for o in art.objects if o.name.startswith('06 •'))
backup=ROOT/'Saved/Diagnostics/ImperialSpear/BeforeBeveledHousing.blend'
if not backup.exists(): shutil.copy2(bpy.data.filepath,backup)
def signature(ob): return hashlib.sha256(str([(tuple(v.co)) for v in ob.data.vertices]).encode()).hexdigest()
blade_before=signature(blade)
AX,AY=.798,.603; norm=math.hypot(AX,AY); AX/=norm;AY/=norm;S=.00096
tree=ast.parse((ROOT/'Tools/SpearAsset/rebuild_reference_gold.py').read_text(encoding='utf-8'))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'ref','cubic','smooth_polygon'}],type_ignores=[]),'helpers','exec'))
outline=[(537,285),(550,279),(571,266),(590,267),(604,271),(612,277),(615,285),(613,296),(610,304),(615,313),(627,321),(619,333),(610,348),(602,362),(584,352),(573,347),(565,349),(560,355),(556,371),(548,362),(542,351),(539,335),(538,316)]
rim=[ref(p) for p in smooth_polygon(outline,{10,13,18},4)]; eye=ref((604,287))
def edge_distance(p):
 d=100
 for a,b in zip(rim,rim[1:]+rim[:1]):
  delta=b-a;t=max(0,min(1,(p-a).dot(delta)/delta.length_squared));d=min(d,(p-a-t*delta).length)
 return max(0,min(d,(p-eye).length-.008))
original_name='Housing before broad shoulders'
if original_name not in bpy.data.meshes:
 original=body.data.copy();original.name=original_name;original.use_fake_user=True
else:
 body.data=bpy.data.meshes[original_name].copy()
surface=BVHTree.FromObject(body,bpy.context.evaluated_depsgraph_get())
reliefs=[o for o in art.objects if o.name.startswith('Socket • continuous cast inverted S')]
offsets={}
for ob in reliefs:
 key='Before broad shoulders '+ob.name
 if key not in bpy.data.meshes:
  original=ob.data.copy();original.name=key;original.use_fake_user=True
 else: ob.data=bpy.data.meshes[key].copy()
 side=-1 if ob.data.vertices[0].co.y<0 else 1; values=[]
 for v in ob.data.vertices:
  hit=surface.ray_cast(Vector((v.co.x,side*.1,v.co.z)),Vector((0,-side,0)),.2)[0]
  values.append(abs(v.co.y)-(abs(hit.y) if hit else .0115))
 offsets[ob.name]=(side,values)
before_xz=[(v.co.x,v.co.z) for v in body.data.vertices]
original_y=[abs(v.co.y) for v in body.data.vertices]
def face_depth(x,z):
 d=edge_distance(Vector((x,z)));t=max(0,min(1,(d-.0006)/.0042))
 return .0086+.0045*t+.00045*(1-math.exp(-(max(0,d-.0048)/.016)**2))
for v in body.data.vertices:
 d=edge_distance(Vector((v.co.x,v.co.z))); old=abs(v.co.y)
 # Broad 4.2mm shoulder with a small eased transition into the face.
 t=max(0,min(1,(d-.0006)/.0042)); bevel=8.6e-3+4.5e-3*t
 bow=.00045*(1-math.exp(-(max(0,d-.0048)/.016)**2))
 target=bevel+bow
 v.co.y=math.copysign(target*min(1,old/.0115),v.co.y)
body.data.update()
bm=bmesh.new();bm.from_mesh(body.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(body.data);bm.free()
body.data.normals_split_custom_set([(0,0,0)]*len(body.data.loops))
for p in body.data.polygons:p.use_smooth=True
body.data.set_sharp_from_angle(angle=math.radians(55))
# Analytic cap normals avoid reflection ripples from long Boolean triangles.
# The depth field defines the real bevel; only its shading interpolation is
# analytic. Existing sidewall/bevel normals stay geometric.
custom=[];step=.00015
for p in body.data.polygons:
 for li in p.loop_indices:
  vi=body.data.loops[li].vertex_index;v=body.data.vertices[vi]
  if original_y[vi]>=.011499:
   dx=(face_depth(v.co.x+step,v.co.z)-face_depth(v.co.x-step,v.co.z))/(2*step)
   dz=(face_depth(v.co.x,v.co.z+step)-face_depth(v.co.x,v.co.z-step))/(2*step)
   custom.append(tuple(Vector((-dx,1 if v.co.y>0 else -1,-dz)).normalized()))
  else:custom.append(tuple(v.normal))
body.data.normals_split_custom_set(custom)
# The Boolean cylinder inserted UVMap at index0. Address the real render UV by
# name and remove that unused layer so future exporters cannot choose it.
uv=body.data.uv_layers.get('UV0_SurfaceAtlas') or body.data.uv_layers.new(name='UV0_SurfaceAtlas')
for loop in body.data.loops:
 co=body.data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(.5+.25*(co.x+.06)/.12,.5+.25*(co.z-1.64)/.13)
for layer in list(body.data.uv_layers):
 if layer.name!='UV0_SurfaceAtlas':body.data.uv_layers.remove(layer)
body.data.uv_layers.active_index=0;body.data.uv_layers[0].active_render=True
bpy.context.view_layer.update();surface=BVHTree.FromObject(body,bpy.context.evaluated_depsgraph_get())
for ob in reliefs:
 side,values=offsets[ob.name]
 for v,height in zip(ob.data.vertices,values):
  hit=surface.ray_cast(Vector((v.co.x,side*.1,v.co.z)),Vector((0,-side,0)),.2)[0]
  v.co.y=side*((abs(hit.y) if hit else .0115)+height)
 ob.data.update()
bm=bmesh.new();bm.from_mesh(body.data);closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);bm.free()
assert closed and volume>0
assert before_xz==[(v.co.x,v.co.z) for v in body.data.vertices]
assert blade_before==signature(blade)
body['Reference_broad_beveled_shoulders']=True
report={'closed':closed,'volume_m3':volume,'shoulder_width_mm':4.2,'shoulder_depth_mm':4.5,'face_bow_mm':.45,'silhouette_preserved':True,'blade_unchanged':True,'uv_fix':'Removed Boolean UVMap; mapped active UV0_SurfaceAtlas','source_housing_triangles':sum(len(p.vertices)-2 for p in body.data.polygons)}
(OUT/'Housing_Bevel_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
s.render.filepath=str(OUT/'Comparison_Current.png');bpy.ops.render.render(write_still=True)
print(json.dumps(report))

"""Import audited explicit casting rings and reseat the retained reference relief."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;art=bpy.data.collections['SPEAR • editable components'];old=next(o for o in art.objects if o.name.startswith('07 •'));name=old.name;mat=old.data.materials[0]
payload=json.loads((ROOT/'Saved/Diagnostics/ImperialSpear/ChamferCastingMesh.json').read_text(encoding='utf-8'))
data=bpy.data.meshes.new('Explicit casting with broad bevels');data.from_pydata(payload['vertices'],[],payload['faces']);data.update()
bm=bmesh.new();bm.from_mesh(data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True)
if volume<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces));volume=-volume
assert closed and volume>0,(closed,volume)
bm.to_mesh(data);bm.free();data.update();assert all(math.isfinite(c) for v in data.vertices for c in v.co)
body=bpy.data.objects.new('TEMP • explicit casting',data);art.objects.link(body);data.materials.append(mat)
uv=data.uv_layers.new(name='UV0_SurfaceAtlas');uv.active_render=True
for loop in data.loops:
 co=data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(.5+.25*(co.x+.06)/.12,.5+.25*(co.z-1.64)/.13)
cap_polygons=set()
for p in data.polygons:
 ys=[data.vertices[i].co.y for i in p.vertices]
 is_cap=max(ys)-min(ys)<1e-7 and abs(abs(ys[0])-.0125)<1e-7
 p.use_smooth=not is_cap
 if is_cap:cap_polygons.add(p.index)
data.set_sharp_from_angle(angle=math.radians(70))
bpy.context.view_layer.update()
normals=[]
for p in data.polygons:
 for li in p.loop_indices:
  vi=data.loops[li].vertex_index
  if payload.get('corner_normals'):
   original_corner=payload['faces'][p.index].index(vi)
   normals.append(tuple(payload['corner_normals'][p.index][original_corner]))
  elif payload.get('vertex_normals'):
   normals.append(tuple(payload['vertex_normals'][vi]))
  elif p.index in cap_polygons:
   v=data.vertices[data.loops[li].vertex_index];normals.append((0,1 if v.co.y>0 else -1,0))
  else:normals.append(tuple(data.corner_normals[li].vector))
data.normals_split_custom_set(normals);data.update()
surface=BVHTree.FromObject(body,bpy.context.evaluated_depsgraph_get())
baseline=bpy.data.meshes['Housing before broad shoulders'];baseline_tree=BVHTree.FromPolygons([v.co for v in baseline.vertices],[tuple(p.vertices) for p in baseline.polygons])
for ob in art.objects:
 if not ob.name.startswith('Socket • continuous cast inverted S'):continue
 retained=bpy.data.meshes['Before broad shoulders '+ob.name];assert len(retained.vertices)==len(ob.data.vertices)
 for v,source in zip(ob.data.vertices,retained.vertices):
  side=-1 if source.co.y<0 else 1;origin=Vector((source.co.x,side*.1,source.co.z));direction=Vector((0,-side,0))
  prior=baseline_tree.ray_cast(origin,direction,.2)[0];now=surface.ray_cast(origin,direction,.2)[0]
  offset=abs(source.co.y)-(abs(prior.y) if prior else .0115)
  v.co=source.co;v.co.y=side*((abs(now.y) if now else .0125)+offset)
 ob.data.update()
bpy.data.objects.remove(old,do_unlink=True);body.name=name;body['Reference_explicit_bevel']=True
s['Spear_revision']='06 WIP: broad 45-degree chamfer, flat socket seating, round bead and subtle gold chasing; accepted blade preserved'
s['GoldDetailCollisionVersion']=2
s['Appearance_accepted']=False
report={'construction':payload.get('report',{}).get('construction','Explicit chamfer bands'),'closed':closed,'volume_m3':volume,'triangles':sum(len(p.vertices)-2 for p in data.polygons),'generator_report':payload.get('report',{}),'blade_modified':False}
(OUT/'Housing_Bevel_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print(json.dumps(report))

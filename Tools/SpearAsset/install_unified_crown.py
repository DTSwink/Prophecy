"""Single solid crown: planar blade clearance and an actually buried guard foot."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;art=bpy.data.collections['SPEAR • editable components'];blade=next(o for o in art.objects if o.name.startswith('06 •'));mat=blade.data.materials[0]
payload=json.loads((ROOT/'Saved/Diagnostics/ImperialSpear/UnifiedCrownMesh.json').read_text(encoding='utf-8'))
depsgraph=bpy.context.evaluated_depsgraph_get()
surface=BVHTree.FromObject(blade,depsgraph);depths=[]
guard=next(o for o in art.objects if o.name.startswith('07 •'))
guard_surface=BVHTree.FromObject(guard,depsgraph)
for x,y,z in payload['vertices']:
 side=1 if y>0 else -1
 hit=surface.ray_cast(Vector((x,side*.1,z)),Vector((0,-side,0)),.2)[0]
 if hit:depths.append(abs(hit.y))
cap_depth=max(.0088,max(depths,default=0)+.0009)
vertices=[];blade_clearances=[];terminal_burials=[];foot_samples=[]
overlap=payload['report']['guard_overlap_m']
for i,(x,y,z) in enumerate(payload['vertices']):
 side=1 if y>0 else -1;layer=payload['layer_depth'][i];distance=payload['body_signed_distance_m'][i]
 # Keep the cap planar. The former 6 mm fade depressed interior cap triangles
 # below the steel, even though the traced silhouette covered those pixels.
 # The 1.8 mm hidden foot ends beyond the point where the guard bevel rises
 # over the crown, so its terminal wall disappears inside the actual housing.
 depth=cap_depth-(.003-layer)
 origin=Vector((x,side*.1,z));direction=Vector((0,-side,0))
 blade_hit=surface.ray_cast(origin,direction,.2)[0]
 guard_hit=guard_surface.ray_cast(origin,direction,.2)[0]
 if blade_hit:
  clearance=depth-abs(blade_hit.y);blade_clearances.append(clearance)
  assert clearance>=.00019,('Crown below blade clearance floor',i,clearance)
 if distance<0 and guard_hit:
  burial=abs(guard_hit.y)-depth
  foot_samples.append({'vertex':i,'guard_half_depth_m':abs(guard_hit.y),'crown_half_depth_m':depth,'burial_m':burial})
 if distance<=-overlap+.000015:
  assert guard_hit is not None,('Foot misses actual guard',i,distance)
  burial=abs(guard_hit.y)-depth
  assert burial>.00005,('Terminal foot is not buried',i,burial)
  terminal_burials.append(burial)
 vertices.append((x,side*depth,z))
assert terminal_burials,'No terminal overlap samples audited'
data=bpy.data.meshes.new('Unified solid gold crown');data.from_pydata(vertices,[],payload['faces']);data.update()
bm=bmesh.new();bm.from_mesh(data);closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);bm.free();assert closed and volume>0
body=bpy.data.objects.new('TEMP • unified crown',data);art.objects.link(body);data.materials.append(mat)
uv=data.uv_layers.new(name='UV0_SurfaceAtlas');uv.active_render=True
xmin=min(v[0] for v in vertices);xmax=max(v[0] for v in vertices);zmin=min(v[2] for v in vertices);zmax=max(v[2] for v in vertices)
normals=[]
for p in data.polygons:
 p.use_smooth=True
 for li in p.loop_indices:
  vi=data.loops[li].vertex_index;v=data.vertices[vi].co;uv.data[li].uv=(.503+.244*(v.x-xmin)/(xmax-xmin),.753+.244*(v.z-zmin)/(zmax-zmin))
  j=payload['faces'][p.index].index(vi);n=Vector(payload['corner_normals'][p.index][j])
  normals.append(tuple(n.normalized()))
data.normals_split_custom_set(normals);data.update()
removed=[]
for old in list(art.objects):
 if old.name.startswith('Blade • flame and compact'):
  removed.append(old.name);bpy.data.objects.remove(old,do_unlink=True)
body.name='Blade • flame and compact unified casting'
report={'replaced_objects':removed,'single_closed_casting':True,'closed':closed,'volume_m3':volume,'triangles':len(data.polygons),'cap_half_depth_m':cap_depth,'maximum_blade_depth_under_crown_m':max(depths,default=0),'minimum_vertex_blade_clearance_m':min(blade_clearances,default=None),'minimum_terminal_burial_in_actual_guard_m':min(terminal_burials),'guard_overlap_m':overlap,'foot_construction':'Planar crown over blade; terminal wall buried under actual guard bevel, with no outside-guard depth fade','actual_guard_foot_samples':foot_samples,'generator_report':payload['report']}
(OUT/'Unified_Crown_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print(json.dumps(report))

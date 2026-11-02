"""Save the reviewed optimized copy without touching the user's open source."""
import bpy,bmesh,json,hashlib
from pathlib import Path
from mathutils import Vector
import numpy as np
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');O=R/'Saved/Diagnostics/ImperialSpear/Optimization20261028';D=R/'Exports/ImperialSpear'
assert json.loads((O/'Blender_FBX_Readback.json').read_text())['status']=='PASS'
report=json.loads((O/'Source_Audit.json').read_text());grip=report['grip_reference_z']
s=bpy.data.scenes['Scene'];game=bpy.data.scenes['GAME • Unreal export'];art=bpy.data.collections['SPEAR • editable components']
collision=json.loads((O/'Collision_Sockets.json').read_text())
planes=[]
for h in collision['hulls']:
 points=np.array(h['vertices']);pp=[]
 for f in h['faces']:
  a,b,c=points[f[:3]];n=np.cross(b-a,c-a);n/=np.linalg.norm(n);pp.append([*n,-np.dot(n,a)])
 planes.append(np.array(pp))
def outside(points):
 pts=np.array(points);nearest=np.full(len(pts),np.inf)
 for ps in planes:nearest=np.minimum(nearest,np.max(pts@ps[:,:3].T+ps[:,3],axis=1))
 return float(max(0,np.max(nearest))*1000),int(np.sum(nearest>1e-5))
# Compare existing simple-hull coverage. Decorative tassel deliberately excluded.
coverage=[]
for o in art.objects:
 if o.type!='MESH' or o.name.startswith('Tassel'):continue
 ref=bpy.data.objects.get('OPTREF '+o.name);base=ref.data if ref else o.data
 values=[]
 for m in (base,o.data):
  m.calc_loop_triangles();coords=[v.co for v in m.vertices]+[sum((m.vertices[i].co for i in t.vertices),Vector())/3 for t in m.loop_triangles]
  values.append(outside([tuple(o.matrix_world@p-Vector((0,0,grip))) for p in coords]))
 assert values[1][0]<=values[0][0]+.04,(o.name,values)
 coverage.append({'name':o.name,'before_max_outside_mm':values[0][0],'after_max_outside_mm':values[1][0]})
(O/'Collision_Regression.json').write_text(json.dumps({'status':'PASS','method':'Source vertices and triangle centroids against union of existing convex hulls; no coverage regression over0.04mm','components':coverage},indent=2))
source_collision=bpy.data.collections['SPEAR • UCX collision']
for o in list(source_collision.objects):bpy.data.objects.remove(o,do_unlink=True)
for h in collision['hulls']:
 m=bpy.data.meshes.new(h['name']);m.from_pydata(h['vertices'],[],h['faces']);m.update();ob=bpy.data.objects.new(h['name'],m);game.collection.objects.link(ob);ob.hide_render=True;ob.display_type='WIRE'
 src=bpy.data.objects.new('SOURCE_'+h['name'],m.copy());source_collision.objects.link(src);src.location.z=grip;src.hide_render=True;src.display_type='WIRE'
for e in collision['sockets']:
 ob=bpy.data.objects.new(e['name'],None);game.collection.objects.link(ob);ob.location=e['position'];ob.empty_display_type='PLAIN_AXES';ob.empty_display_size=.02
 for collection in bpy.data.collections:
  if 'attachment' in collection.name:
   for old in collection.objects:
    if old.name.endswith(e['name'].rsplit('_',1)[-1]):old.location=Vector(e['position'])+Vector((0,0,grip))
refs=bpy.data.collections.get('OPTIMIZATION • original comparison')
for o in list(refs.objects):o.data.use_fake_user=False;bpy.data.objects.remove(o,do_unlink=True)
bpy.data.collections.remove(refs)
for m in bpy.data.meshes:
 if m.name.endswith('trial') or 'optimized' in m.name:m.use_fake_user=False
for m in list(bpy.data.meshes):
 if m.users==0:bpy.data.meshes.remove(m)
for mat in list(bpy.data.materials):
 if mat.users==0:bpy.data.materials.remove(mat)
for p in (D/'Textures').glob('*.png'):assert hashlib.sha256(p.read_bytes()).hexdigest()==report['texture_hashes'][p.name]
assert hashlib.sha256((O/'Before_UserFinal.blend').read_bytes()).digest()==hashlib.sha256((R/'Saved/Diagnostics/ImperialSpear/PommelLotus/Working.blend').read_bytes()).digest(),'User saved a newer version during optimization'
s['Optimization']='Selective topology pass, October28. Original user saved transforms and atlas preserved. Before59,460 / after43,494 triangles.'
s['Optimization_report']=str(O/'Reduction_Trials.json')
bpy.context.window.scene=s;bpy.ops.object.select_all(action='DESELECT')
for o in source_collision.objects:o.hide_set(True)
source_collision.hide_render=True
assert sum(len(o.data.loop_triangles) for o in art.objects if o.type=='MESH')==43494
path=D/'ImperialSpear_Optimized.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
print('SAVED',path)

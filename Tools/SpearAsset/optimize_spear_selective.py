"""Reversible component-level reduction in the isolated optimization scene."""
import bpy,bmesh,math,json,time
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
OUT=ROOT/'Saved/Diagnostics/ImperialSpear/Optimization20261028'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s
art=bpy.data.collections['SPEAR • editable components']
OPT_BASE={o.name:(bpy.data.objects['OPTREF '+o.name].data if bpy.data.objects.get('OPTREF '+o.name) else o.data) for o in art.objects if o.type=='MESH'}
for m in OPT_BASE.values():m.use_fake_user=True
refs=bpy.data.collections.get('OPTIMIZATION • original comparison')
if refs is None:refs=bpy.data.collections.new('OPTIMIZATION • original comparison');s.collection.children.link(refs)
refs.hide_render=True

def active(o):
 bpy.ops.object.select_all(action='DESELECT');o.hide_set(False);o.select_set(True);bpy.context.view_layer.objects.active=o
def triangles(m):m.calc_loop_triangles();return len(m.loop_triangles)
def topology(m):
 bm=bmesh.new();bm.from_mesh(m)
 r={'boundary':sum(e.is_boundary for e in bm.edges),'nonmanifold':sum(not e.is_manifold for e in bm.edges),'volume':bm.calc_volume(),'degenerate':sum(f.calc_area()<1e-14 for f in bm.faces)};bm.free();return r
def tree(m):
 m.calc_loop_triangles()
 return BVHTree.FromPolygons([v.co for v in m.vertices],[list(t.vertices) for t in m.loop_triangles],all_triangles=True,epsilon=0)
def samples(m):
 yield from (v.co for v in m.vertices)
 for e in m.edges:yield (m.vertices[e.vertices[0]].co+m.vertices[e.vertices[1]].co)*.5
 for t in m.loop_triangles:yield sum((m.vertices[i].co for i in t.vertices),Vector())/3
def deviation(a,b):
 ta,tb=tree(a),tree(b);dist=[]
 for m,t in ((a,tb),(b,ta)):
  dist.extend(t.find_nearest(p)[3] for p in samples(m))
 dist.sort();return {'max_mm':1000*dist[-1],'p99_mm':1000*dist[int(.99*(len(dist)-1))],'samples':len(dist)}
def uv_health(m):
 uv=m.uv_layers.get('UV0_SurfaceAtlas');assert uv
 vals=[p.uv for p in uv.data]
 assert all(math.isfinite(c) for p in vals for c in p)
 return {'min':[min(p[i] for p in vals) for i in range(2)],'max':[max(p[i] for p in vals) for i in range(2)]}

def exact_tri_copy(base):
 # Preserve the exact rendered diagonal of non-planar source quads.
 base.calc_loop_triangles();ts=list(base.loop_triangles)
 m=bpy.data.meshes.new(base.name+' trial')
 m.from_pydata([v.co for v in base.vertices],[],[t.vertices for t in ts]);m.update()
 for mat in base.materials:m.materials.append(mat)
 idx=[i for t in ts for i in t.loops]
 for u in base.uv_layers:
  layer=m.uv_layers.new(name=u.name)
  layer.data.foreach_set('uv',[c for i in idx for c in u.data[i].uv]);layer.active_render=u.active_render
 for a in base.color_attributes:
  layer=m.color_attributes.new(name=a.name,type=a.data_type,domain='CORNER')
  layer.data.foreach_set('color',[c for i in idx for c in a.data[i].color])
 for p,t in zip(m.polygons,ts):p.use_smooth=base.polygons[t.polygon_index].use_smooth;p.material_index=base.polygons[t.polygon_index].material_index
 m.normals_split_custom_set([base.corner_normals[i].vector for i in idx]);m.update()
 for axis in range(3):
  a=m.attributes.new(name='_OPT_N'+str(axis),type='FLOAT',domain='CORNER')
  a.data.foreach_set('value',[base.corner_normals[i].vector[axis] for i in idx])
 return m

report=[];start=time.time()
for o in list(art.objects):
 if o.type!='MESH':continue
 base=OPT_BASE[o.name];o.data=base
 n=triangles(base)
 # Shaft/steel, scored sleeve, ribbons and fine tassel strands already efficient.
 eligible=n>=1000 and not o.name.startswith('06 ')
 if not eligible:continue
 ref=bpy.data.objects.get('OPTREF '+o.name)
 if ref is None:ref=bpy.data.objects.new('OPTREF '+o.name,base);refs.objects.link(ref);ref.matrix_world=o.matrix_world;ref.hide_render=True
 is_pommel=bool(base.color_attributes.get('PommelCavity'))
 max_error=.025 if is_pommel else (.04 if 'housing' in o.name else .035)
 ratios=[.30,.45,.60,.75,.90] if not is_pommel else [.40,.55,.70,.85]
 before_top=topology(base);before_uv=uv_health(base);trials=[];chosen=None
 for ratio in ratios:
  o.data=exact_tri_copy(base);active(o)
  dec=o.modifiers.new('Selective bounded reduction','DECIMATE');dec.ratio=ratio;dec.use_collapse_triangulate=True
  bpy.ops.object.modifier_apply(modifier=dec.name)
  # Carry split normals as per-face-corner attributes through collapse. Nearest
  # surface transfer can choose the other side of a crease and round the chamfer.
  attrs=[o.data.attributes['_OPT_N'+str(i)] for i in range(3)]
  ns=[Vector([a.data[j].value for a in attrs]).normalized() for j in range(len(o.data.loops))]
  o.data.normals_split_custom_set(ns)
  for a in attrs:o.data.attributes.remove(a)
  m=o.data;m.update();after_top=topology(m);after_uv=uv_health(m);dev=deviation(base,m)
  normals_ok=all(c.vector.length>.9 and all(math.isfinite(v) for v in c.vector) for c in m.corner_normals)
  c=m.color_attributes.get('PommelCavity');color_correction=0.
  if c:
   for item in c.data:
    v=list(item.color);shade=max(.45,min(1.,sum(v[:3])/3));color_correction=max(color_correction,max(abs(v[k]-shade) for k in range(3)),abs(v[3]-1));item.color=(shade,shade,shade,1)
  # Atlas boundaries cannot drift to a neighbouring material tile.
  uv_bounds_error=max(abs(before_uv[k][i]-after_uv[k][i]) for k in ('min','max') for i in range(2))
  ok=dev['max_mm']<=max_error and after_top['nonmanifold']==before_top['nonmanifold'] and after_top['degenerate']<=before_top['degenerate'] and after_top['volume']*before_top['volume']>0 and normals_ok and uv_bounds_error<1e-5 and color_correction<.015
  row={'ratio':ratio,'triangles':triangles(m),'deviation':dev,'topology':after_top,'uv_bounds_error':uv_bounds_error,'cavity_color_roundoff_correction':color_correction,'passed':ok};trials.append(row)
  if ok:chosen=row;break
  o.data=base;bpy.data.meshes.remove(m)
 if chosen:
  o.data.name=base.name+' • optimized';o['Optimization_source_triangles']=n;o['Optimization_max_deviation_mm']=chosen['deviation']['max_mm']
 else:o.data=base
 row={'name':o.name,'before':n,'after':triangles(o.data),'max_allowed_deviation_mm':max_error,'trials':trials,'accepted':chosen is not None};report.append(row)
 print(json.dumps({k:v for k,v in row.items() if k!='trials'},ensure_ascii=False),flush=True)
result={'before_triangles':sum(triangles(m) for m in OPT_BASE.values()),'after_triangles':sum(triangles(o.data) for o in art.objects if o.type=='MESH'),'elapsed_seconds':time.time()-start,'components':report}
(OUT/'Reduction_Trials.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('TOTAL',result['before_triangles'],result['after_triangles'])

"""Refine actual casting curvature, edge channels and restrained material contrast."""
import bpy,bmesh,math,ast,json,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
art=bpy.data.collections['SPEAR • editable components']; blade=next(o for o in art.objects if o.name.startswith('06 •')); mat=blade.data.materials[0]
regions={'gold':(.5,.75,.5,1),'gold_shadow':(.75,.8125,.5,1),'cord':(.8125,.875,.5,.75),'silk':(.75,1,0,.5)}
AX,AY=.798,.603; norm=math.hypot(AX,AY); AX/=norm; AY/=norm; S=.00096
for filename,names in [('build_spear.py',{'atlas','mesh','activate','tube','path'}),('rebuild_reference_gold.py',{'ref','r3','cubic','bezier_chain','smooth_polygon','extrude','boolean','finish_bevel'})]:
 tree=ast.parse((ROOT/'Tools/SpearAsset'/filename).read_text(encoding='utf-8'))
 exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'helpers','exec'))
body=next(o for o in art.objects if o.name.startswith('07 •'))
assert not body.get('Reference_surface_finished'),'Already applied; do not accumulate deformation'
outline=[(537,285),(550,279),(571,266),(590,267),(604,271),(612,277),(615,285),(613,296),(610,304),(615,313),(627,321),(619,333),(610,348),(602,362),(584,352),(573,347),(565,349),(560,355),(556,371),(548,362),(542,351),(539,335),(538,316)]
rim=[ref(p) for p in smooth_polygon(outline,{10,13,18},4)]; eye=ref((604,287))
def edge_distance(p):
 dist=100.
 for a,b in zip(rim,rim[1:]+rim[:1]):
  v=b-a; t=max(0,min(1,(p-a).dot(v)/v.length_squared))
  dist=min(dist,(p-a-t*v).length)
 return max(0,min(dist,(p-eye).length-.008))
bm=bmesh.new(); bm.from_mesh(body.data)
front=[f for f in bm.faces if all(abs(abs(v.co.y)-.0115)<1e-6 for v in f.verts)]
bmesh.ops.triangulate(bm,faces=front)
edges=[e for e in bm.edges if all(abs(abs(v.co.y)-.0115)<1e-6 for v in e.verts) and e.calc_length()>.006]
bmesh.ops.subdivide_edges(bm,edges=edges,cuts=3,use_grid_fill=True)
max_bow=0.
for v in bm.verts:
 if abs(abs(v.co.y)-.0115)<1e-6:
  d=edge_distance(Vector((v.co.x,v.co.z))); bow=.0015*(1-math.exp(-(d/.012)**2))
  v.co.y=math.copysign(.0115+bow,v.co.y); max_bow=max(max_bow,bow)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(body.data); bm.free()
for p in body.data.polygons: p.use_smooth=True
body.data.normals_split_custom_set([(0,0,0)]*len(body.data.loops))
body.data.set_sharp_from_angle(angle=math.radians(65))
bpy.context.view_layer.update(); surface=BVHTree.FromObject(body,bpy.context.evaluated_depsgraph_get())
def depth(p,side):
 hit=surface.ray_cast(Vector((p.x,side*.1,p.z)),Vector((0,-side,0)),.2)[0]
 return abs(hit.y) if hit else .0115
groove_results=[]
for ob in list(art.objects):
 if not ob.name.startswith('Socket • continuous cast inverted S'): continue
 n=9; rows=len(ob.data.vertices)//n; side=-1 if ob.data.vertices[0].co.y<0 else 1
 for i in range(rows):
  centre=(ob.data.vertices[i*n].co+ob.data.vertices[i*n+6].co)*.5
  for j in range(n):
   v=ob.data.vertices[i*n+j]; h=side*v.co.y-.01055
   v.co.x=centre.x+(v.co.x-centre.x)*1.15; v.co.z=centre.z+(v.co.z-centre.z)*1.15
   v.co.y=side*(depth(v.co,side)+h)
 # Real shallow half-round cuts on both edges, narrow enough to avoid the
 # overlapping filled-polygon cutter that invalidated the initial attempt.
 for edge_col,sign in []:  # Border chasing is baked into the dedicated housing atlas.
  points=[]
  for i in range(rows):
   left=ob.data.vertices[i*n].co; right=ob.data.vertices[i*n+6].co
   outward=Vector((right.x-left.x,0,right.z-left.z)).normalized()*sign
   p=ob.data.vertices[i*n+edge_col].co.copy()+outward*.0006
   p.y=side*(depth(p,side)-.0003); points.append(tuple(p))
  cutter=tube('TEMP • rounded chasing cutter',points,.0010,'gold_shadow',8)
  backup=body.data.copy(); before=len(body.data.polygons)
  activate(body); mod=body.modifiers.new('Actual chased border channel','BOOLEAN'); mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.object=cutter; mod.use_self=True
  bpy.ops.object.modifier_apply(modifier=mod.name); bpy.data.objects.remove(cutter,do_unlink=True)
  test=bmesh.new(); test.from_mesh(body.data); closed=bool(test.faces) and all(e.is_manifold for e in test.edges); volume=test.calc_volume(signed=True) if test.faces else 0; test.free()
  if not closed or volume<=0:
   failed=body.data; body.data=backup; bpy.data.meshes.remove(failed); raise RuntimeError('Chased channel rejected; intact body restored')
  bpy.data.meshes.remove(backup)
  groove_results.append({'side':side,'edge':edge_col,'faces_before':before,'faces_after':len(body.data.polygons),'closed':closed})
body['Reference_surface_finished']=True

# Broaden the compact upper coil toward its interior, leaving its outer trace.
for ob in list(art.objects):
 if ob.name.startswith('Blade • flame and compact'): bpy.data.objects.remove(ob,do_unlink=True)
stalk=[(466,218),(474,227),(487,232),(494,233),(496,225),(498,234),(509,235),(519,241),(525,252),(520,258),(515,246),(508,241),(498,239),(493,243),(492,238),(479,235),(470,229)]
spiral=bezier_chain((548,249),[
 ((558,245),(568,251),(569,261)),((570,273),(558,283),(547,285)),((532,288),(521,279),(520,267)),
 ((518,258),(522,252),(531,252)),((537,251),(543,256),(543,262)),((543,267),(538,269),(534,266)),
 ((531,264),(532,261),(534,260)),((535,260),(536,261),(537,262)),((535,262),(535,264),(537,264)),
 ((540,265),(540,260),(537,258)),((532,254),(526,256),(526,263)),((526,268),(532,273),(541,274)),
 ((550,275),(558,268),(558,260)),((559,255),(554,251),(548,249))],1.6)[:-1]
blade_surface=BVHTree.FromObject(blade,bpy.context.evaluated_depsgraph_get())
for side in [-1,1]:
 crown=extrude('Blade • flame and compact cast spiral',spiral,side*.0084,side*.0125)
 branch=extrude('TEMP • forked flame',smooth_polygon(stalk,{0,4,9,13},3),side*.0084,side*.0125)
 boolean(crown,branch,'UNION'); finish_bevel(crown,.0012,3)
 for v in crown.data.vertices:
  hit=blade_surface.ray_cast(Vector((v.co.x,side*.1,v.co.z)),Vector((0,-side,0)),.2)[0]
  base=abs(hit.y) if hit else .0083; v.co.y=side*(abs(v.co.y)-.0084+base-.00015)
# Broader main ring and a more oval first bead.
ring=next(o for o in art.objects if o.name.startswith('Socket • broad asymmetrical'))
centre=ref((681,395)).y
for v in ring.data.vertices: v.co.z=centre+(v.co.z-centre)*1.17
axis=(r3((702,316))-r3((632,295))).normalized(); cross=axis.cross(Vector((0,1,0))).normalized(); up=axis.cross(cross).normalized()
small=next(o for o in art.objects if o.name.startswith('Tassel • pierced small')); centre=r3((644,298),-.010)
for v in small.data.vertices:
 delta=v.co-centre; v.co+=axis*delta.dot(axis)*(1.30/1.08-1)
path('Tassel • second leather leg to first bead',[r3(p,y) for p,y in [((605,291),-.014),((615,294),-.013),((628,297),-.011),((638,299),-.010)]],.0011,'cord')
for ob in list(art.objects):
 if ob.name.startswith('Tassel • tight throat binding'): bpy.data.objects.remove(ob,do_unlink=True)
neck=r3((703,317),-.010)
for i in range(3):
 c=neck+axis*((i-1)*.00155); points=[tuple(c+(cross*math.cos(j*math.tau/24)+up*math.sin(j*math.tau/24))*(.0031+.00015*i)) for j in range(25)]
 tube('Tassel • tied throat wrap',points,.00065,'cord',6)
for j,end in enumerate([(875,329),(884,337),(880,340)]):
 pixels=bezier_chain((706,315+j),[((760,318+j),(826,336+j),end)],9)
 tube('Tassel • loose upper wisp',[r3(p,-.011-j*.0003) for p in pixels],.00022,'silk',5)

# Correct packed-alpha interpretation; shader alpha remains fully opaque.
for image in bpy.data.images:
 if image.source=='FILE' and image.name.startswith('T_ImperialSpear_'):
  image.filepath=str(OUT/'Textures'/(image.name.split('.png')[0]+'.png')); image.reload()
  if '_ORM' in image.name: image.alpha_mode='CHANNEL_PACKED'; image.colorspace_settings.name='Non-Color'
nodes=mat.node_tree.nodes; links=mat.node_tree.links; p=nodes.get('Principled BSDF'); orm=nodes.get('Atlas_orm')
links.new(orm.outputs['Alpha'],p.inputs['Specular IOR Level']); p.inputs['Alpha'].default_value=1
report=json.loads((OUT/'Reference_Rebuild_Verification.json').read_text(encoding='utf-8'))
report['surface_refinement']={'maximum_housing_bow_mm':max_bow*1000,'border_channels':'dedicated normal/roughness atlas pending','broad_ring_width_scale':1.17,'first_bead_elongation':1.30,'specular_from_orm_alpha':True}
report['status']='Further visual comparison required; game exports/collision still pending.'
(OUT/'Reference_Rebuild_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
scene.render.filepath=str(OUT/'Comparison_Current.png'); bpy.ops.render.render(write_still=True)
print(json.dumps(report['surface_refinement']))

"""Replace field-deformed shoulders with weighted, explicit machined bevels."""
import bpy,bmesh,math,ast,json,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;art=bpy.data.collections['SPEAR • editable components'];blade=next(o for o in art.objects if o.name.startswith('06 •'));mat=blade.data.materials[0]
old=next(o for o in art.objects if o.name.startswith('07 •'));original_name=old.name;oldsurface=BVHTree.FromObject(old,bpy.context.evaluated_depsgraph_get())
regions={'gold':(.5,.75,.75,1)};AX,AY=.798,.603;norm=math.hypot(AX,AY);AX/=norm;AY/=norm;S=.00096
for filename,names in [('build_spear.py',{'atlas','mesh','activate'}),('rebuild_reference_gold.py',{'ref','cubic','smooth_polygon','extrude','boolean'})]:
 tree=ast.parse((ROOT/'Tools/SpearAsset'/filename).read_text(encoding='utf-8'))
 exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'helpers','exec'))
offsets={}
for ob in art.objects:
 if not ob.name.startswith('Socket • continuous cast inverted S'):continue
 side=-1 if ob.data.vertices[0].co.y<0 else 1;values=[]
 for v in ob.data.vertices:
  hit=oldsurface.ray_cast(Vector((v.co.x,side*.1,v.co.z)),Vector((0,-side,0)),.2)[0]
  values.append(abs(v.co.y)-(abs(hit.y) if hit else .0115))
 offsets[ob.name]=(side,values)
outline=[(537,285),(550,279),(571,266),(590,267),(604,271),(612,277),(615,285),(613,296),(610,304),(615,313),(627,321),(619,333),(610,348),(602,362),(584,352),(573,347),(565,349),(560,355),(556,371),(548,362),(542,351),(539,335),(538,316)]
rim_pixels=smooth_polygon(outline,{10,13,18},4);rim2=[ref(p) for p in rim_pixels]
body=extrude('TEMP • clean bevel housing',rim_pixels,.0125,-.0125)
eye=ref((604,287));bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=.008,depth=.065,location=(eye.x,0,eye.y),rotation=(math.pi/2,0,0));boolean(body,bpy.context.object)
# Resolve the Boolean's concave holed caps before variable-width beveling.
# Leaving those as n-gons lets the bevel reconnect incompatible cap diagonals.
bm=bmesh.new();bm.from_mesh(body.data)
bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if abs(f.normal.y)>.99])
bm.to_mesh(body.data);bm.free();body.data.update()
# Cap-to-wall perimeter edges only: broad outside shoulder, small pierced-eye lip.
weights=body.data.attributes.get('bevel_weight_edge') or body.data.attributes.new('bevel_weight_edge','FLOAT','EDGE')
edge_faces={e.index:[] for e in body.data.edges};edge_index={tuple(sorted(e.vertices)):e.index for e in body.data.edges}
for p in body.data.polygons:
 for pair in p.edge_keys:edge_faces[edge_index[tuple(sorted(pair))]].append(p)
count=0
def rim_distance(p):
 result=100
 for a,b in zip(rim2,rim2[1:]+rim2[:1]):
  delta=b-a;t=max(0,min(1,(p-a).dot(delta)/delta.length_squared));result=min(result,(p-a-delta*t).length)
 return result
tips=[ref(outline[i]) for i in (10,13,18)]
for e in body.data.edges:
 faces=edge_faces[e.index];value=0
 if any(abs(p.normal.y)>.99 for p in faces) and any(abs(p.normal.y)<.2 for p in faces):
  mid=(body.data.vertices[e.vertices[0]].co+body.data.vertices[e.vertices[1]].co)*.5;distance=(Vector((mid.x,mid.z))-eye).length
  p2=Vector((mid.x,mid.z))
  if abs(distance-.008)<.0003:
   value=min(.28,max(.02,rim_distance(p2)*.32/.0042))
  else:
   value=min(1,max(.02,(distance-.008)*.32/.0042))
   # Fade actual width into the three pointed corners instead of globally
   # clamping every shoulder to the shortest edge in the dense outline.
   value*=min(1,max(.015,min((p2-tip).length for tip in tips)/.018))
  count+=1
 weights.data[e.index].value=value
activate(body);mod=body.modifiers.new('Broad cast bevel with restrained pierced lip','BEVEL');mod.width=.0042;mod.segments=4;mod.limit_method='WEIGHT';mod.use_clamp_overlap=False;mod.harden_normals=True
bpy.ops.object.modifier_apply(modifier=mod.name)
for p in body.data.polygons:p.use_smooth=abs(p.normal.y)<.9999
body.data.set_sharp_from_angle(angle=math.radians(60))
normal=body.modifiers.new('Stable planar casting normals','WEIGHTED_NORMAL');normal.keep_sharp=True;normal.weight=50;bpy.ops.object.modifier_apply(modifier=normal.name)
uv=body.data.uv_layers.get('UV0_SurfaceAtlas') or body.data.uv_layers.new(name='UV0_SurfaceAtlas')
for loop in body.data.loops:
 co=body.data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(.5+.25*(co.x+.06)/.12,.5+.25*(co.z-1.64)/.13)
for layer in list(body.data.uv_layers):
 if layer.name!='UV0_SurfaceAtlas':body.data.uv_layers.remove(layer)
body.data.uv_layers.active_index=0;body.data.uv_layers[0].active_render=True
bm=bmesh.new();bm.from_mesh(body.data);closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);bm.free()
assert closed and volume>0,(closed,volume)
# Keep the unsuccessful field construction as a data backup; never render it.
backup=old.data.copy();backup.name='Housing field bevel superseded';backup.use_fake_user=True
bpy.data.objects.remove(old,do_unlink=True);body.name=original_name
bpy.context.view_layer.update();surface=BVHTree.FromObject(body,bpy.context.evaluated_depsgraph_get())
for name,(side,values) in offsets.items():
 ob=bpy.data.objects[name]
 for v,height in zip(ob.data.vertices,values):
  hit=surface.ray_cast(Vector((v.co.x,side*.1,v.co.z)),Vector((0,-side,0)),.2)[0]
  v.co.y=side*((abs(hit.y) if hit else .0125)+height)
 ob.data.update()
body['Reference_clean_weighted_bevel']=True
report={'construction':'Explicit weighted bevel, flat caps, rounded shoulders; supersedes depth field','nominal_outer_bevel_mm':4.2,'eye_bevel_weight':.28,'segments':4,'closed':closed,'positive_volume_m3':volume,'weighted_edges':count,'triangles':sum(len(p.vertices)-2 for p in body.data.polygons),'blade_modified':False}
(OUT/'Housing_Bevel_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print(json.dumps(report))

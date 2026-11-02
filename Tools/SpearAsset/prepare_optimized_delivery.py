"""Validate source and create an exact triangulated export snapshot."""
import bpy,bmesh,math,json,hashlib
from pathlib import Path
from mathutils import Vector
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=R/'Saved/Diagnostics/ImperialSpear/Optimization20261028'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;art=bpy.data.collections['SPEAR • editable components']
initial=json.loads((OUT/'Initial_Inspection.json').read_text(encoding='utf-8'))
initials={x['name']:x for x in initial['meshes']}
leather=next(o for o in art.objects if o.name.startswith('03 '))
zs=[(leather.matrix_world@v.co).z for v in leather.data.vertices];grip=(min(zs)+max(zs))/2
rows=[];vertices=[];faces=[];normals=[];uvs=[];colors=[]
def inspect(m):
 m.calc_loop_triangles();uv=m.uv_layers['UV0_SurfaceAtlas'];bad_uv=0;bad_area=0;inward=0
 for t in m.loop_triangles:
  a,b,c=[uv.data[i].uv for i in t.loops]
  bad_uv+=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))<1e-14
  bad_area+=t.area<1e-14
  for i in t.loops:inward+=m.corner_normals[i].vector.dot(t.normal)<-.001
 bm=bmesh.new();bm.from_mesh(m)
 row={'triangles':len(m.loop_triangles),'degenerate_uv':bad_uv,'degenerate_geometry':bad_area,'inward_corners':inward,'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'volume':bm.calc_volume()};bm.free();return row
for o in art.objects:
 if o.type!='MESH':continue
 m=o.data;ref=bpy.data.objects.get('OPTREF '+o.name);base=ref.data if ref else m
 before,after=inspect(base),inspect(m)
 assert after['degenerate_geometry']<=before['degenerate_geometry'],o.name
 assert after['degenerate_uv']<=before['degenerate_uv'],(o.name,'new degenerate UV',before,after)
 assert after['nonmanifold_edges']==before['nonmanifold_edges'],o.name
 assert after['inward_corners']<=before['inward_corners'],(o.name,'inverted normals',before,after)
 assert max(abs(o.matrix_world[i][j]-initials[o.name]['matrix'][i][j]) for i in range(4) for j in range(4))<1e-10,o.name
 assert [ma.name for ma in m.materials]==['M_ImperialSpear_PBR']
 offset=len(vertices);matrix=o.matrix_world;nm=matrix.to_3x3().inverted().transposed()
 vertices.extend([tuple(matrix@v.co-Vector((0,0,grip))) for v in m.vertices])
 uv=m.uv_layers['UV0_SurfaceAtlas'];col=m.color_attributes.get('PommelCavity')
 for t in m.loop_triangles:
  faces.append([offset+i for i in t.vertices])
  for i in t.loops:
   n=(nm@m.corner_normals[i].vector).normalized();assert n.length>.99
   normals.append(tuple(n));uvs.append(tuple(uv.data[i].uv));colors.append(tuple(col.data[i].color) if col else (1.,1.,1.,1.))
 rows.append({'name':o.name,'before':before,'after':after,'unchanged':m==base,'transform_preserved':True})
snapshot={'vertices':vertices,'triangles':faces,'normals':normals,'uv0':uvs,'colors':colors,'grip':grip}
# Pack an independent lightmap layer on the export mesh only.
game=bpy.data.scenes.get('GAME • Unreal export')
if game:
 for o in list(game.objects):bpy.data.objects.remove(o,do_unlink=True)
else:game=bpy.data.scenes.new('GAME • Unreal export')
mesh=bpy.data.meshes.new('SM_ImperialSpear_Optimized');mesh.from_pydata(vertices,[],faces);mesh.materials.append(bpy.data.materials['M_ImperialSpear_PBR']);mesh.update()
ob=bpy.data.objects.new('SM_ImperialSpear',mesh);game.collection.objects.link(ob)
for p in mesh.polygons:p.use_smooth=True
uv=mesh.uv_layers.new(name='UV0_SurfaceAtlas');uv.data.foreach_set('uv',[v for p in uvs for v in p]);uv.active_render=True
col=mesh.color_attributes.new(name='PommelCavity',type='FLOAT_COLOR',domain='CORNER');col.data.foreach_set('color',[v for p in colors for v in p])
mesh.uv_layers.new(name='UV1_Lightmap');mesh.uv_layers.active_index=1
bpy.context.window.scene=game;ob.select_set(True);bpy.context.view_layer.objects.active=ob
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.008,area_weight=.3,correct_aspect=True,scale_to_bounds=True);bpy.ops.object.mode_set(mode='OBJECT')
mesh.uv_layers.active_index=0;mesh.uv_layers['UV0_SurfaceAtlas'].active_render=True
for e in mesh.edges:e.use_edge_sharp=True
mesh.normals_split_custom_set(normals);mesh.update()
snapshot['uv1']=[tuple(x.uv) for x in mesh.uv_layers['UV1_Lightmap'].data]
assert max(abs(v-uvs[i][j]) for i,p in enumerate(mesh.uv_layers['UV0_SurfaceAtlas'].data) for j,v in enumerate(p.uv))<1e-8
normal_dot=min(c.vector.dot(Vector(normals[i])) for i,c in enumerate(mesh.corner_normals))
assert normal_dot>.9999,('Export corner normal preservation',normal_dot)
ob['Grip_reference_m']=grip;ob['Length_m']=max(p[2] for p in vertices)-min(p[2] for p in vertices);ob['Optimization']='Selective component reduction; original atlas and authored split normals'
report={'before_triangles':sum(x['before']['triangles'] for x in rows),'after_triangles':len(faces),'vertices':len(vertices),'grip_reference_z':grip,'length':ob['Length_m'],'components':rows,'texture_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'Exports/ImperialSpear/Textures').glob('*.png')}}
(OUT/'Optimized_Surface.json').write_text(json.dumps(snapshot,separators=(',',':')),encoding='utf-8')
(OUT/'Source_Audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.context.window.scene=s
print(json.dumps({k:v for k,v in report.items() if k not in ('components','texture_hashes')}))

import bpy,bmesh,math,ast,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene; art=bpy.data.collections['SPEAR • editable components']
blade=next(o for o in art.objects if o.name.startswith('06 •')); body=next(o for o in art.objects if o.name.startswith('07 •')); mat=blade.data.materials[0]
regions={'gold':(.5,.75,.75,1)}; AX,AY=.798,.603; norm=math.hypot(AX,AY); AX/=norm; AY/=norm; S=.00096
for filename,names in [('build_spear.py',{'atlas','mesh','activate'}),('rebuild_reference_gold.py',{'ref','r3','cubic','bezier_chain','smooth_polygon','extrude','boolean','finish_bevel'}),('make_cast_body_atlas.py',{'arch_factor'})]:
 tree=ast.parse((ROOT/'Tools/SpearAsset'/filename).read_text(encoding='utf-8'))
 exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'helpers','exec'))
surface=BVHTree.FromObject(body,bpy.context.evaluated_depsgraph_get())
def depth(p,side):
 hit=surface.ray_cast(Vector((p.x,side*.1,p.z)),Vector((0,-side,0)),.2)[0]
 return abs(hit.y) if hit else .0115
for ob in art.objects:
 if not ob.name.startswith('Socket • continuous cast inverted S') or ob.get('Reference_arch_mass_adjusted'): continue
 n=9; rows=len(ob.data.vertices)//n; side=-1 if ob.data.vertices[0].co.y<0 else 1
 for i in range(rows):
  centre=(ob.data.vertices[i*n].co+ob.data.vertices[i*n+6].co)*.5; factor=arch_factor(i/(rows-1))
  for j in range(n):
   v=ob.data.vertices[i*n+j]; height=side*v.co.y-depth(v.co,side)
   v.co.x=centre.x+(v.co.x-centre.x)*factor; v.co.z=centre.z+(v.co.z-centre.z)*factor
   v.co.y=side*(depth(v.co,side)+height)
 ob['Reference_arch_mass_adjusted']=True
for ob in list(art.objects):
 if ob.name.startswith('Blade • flame and compact'): bpy.data.objects.remove(ob,do_unlink=True)
stalk=[(466,218),(474,227),(487,232),(494,233),(496,225),(498,234),(509,235),(519,241),(525,252),(520,258),(515,246),(508,241),(498,239),(493,243),(492,238),(479,235),(470,229)]
spiral=bezier_chain((548,249),[
 ((558,245),(568,251),(569,261)),((570,273),(558,283),(547,285)),((532,288),(521,279),(520,267)),
 ((518,258),(522,252),(531,252)),((537,251),(543,256),(543,262)),((543,267),(538,269),(534,266)),
 ((531,264),(532,261),(534,260)),((535,260),(536,261),(537,262)),((535,262),(535,264),(537,264)),
 ((540,265),(540,260),(537,258)),((532,254),(526,256),(526,263)),((528,267),(533,270),(541,270)),
 ((549,271),(554,266),(554,260)),((556,255),(553,251),(548,249))],1.6)[:-1]
surface_blade=BVHTree.FromObject(blade,bpy.context.evaluated_depsgraph_get())
for side in [-1,1]:
 crown=extrude('Blade • flame and compact cast spiral',spiral,side*.0084,side*.0125)
 branch=extrude('TEMP • forked flame',smooth_polygon(stalk,{0,4,9,13},3),side*.0084,side*.0125)
 boolean(crown,branch,'UNION'); finish_bevel(crown,.0012,3)
 for v in crown.data.vertices:
  hit=surface_blade.ray_cast(Vector((v.co.x,side*.1,v.co.z)),Vector((0,-side,0)),.2)[0]
  base=abs(hit.y) if hit else .0083; v.co.y=side*(abs(v.co.y)-.0084+base-.00015)
axis=(r3((702,316))-r3((632,295))).normalized(); cross=axis.cross(Vector((0,1,0))).normalized()
small=next(o for o in art.objects if o.name.startswith('Tassel • pierced small')); centre=r3((644,298),-.010)
if not small.get('Reference_bead_axes_corrected'):
 for v in small.data.vertices:
  delta=v.co-centre; v.co+=axis*delta.dot(axis)*(.0092/(.0094*1.30)-1)+cross*delta.dot(cross)*(.0122/.0094-1)
 small['Reference_bead_axes_corrected']=True
for image in bpy.data.images:
 if image.source=='FILE' and image.name.startswith('T_ImperialSpear_'):
  image.filepath=str(OUT/'Textures'/(image.name.split('.png')[0]+'.png')); image.reload()
  if '_ORM' in image.name: image.alpha_mode='CHANNEL_PACKED'; image.colorspace_settings.name='Non-Color'
print('Local scroll mass corrected; first bead oval is perpendicular to the cord. View look:',scene.view_settings.look)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
scene.render.filepath=str(OUT/'Comparison_Current.png'); bpy.ops.render.render(write_still=True)

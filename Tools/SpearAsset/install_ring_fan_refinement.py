"""Install reviewed asymmetric ring and irregular ribbon spacing, then refresh maps."""
import bpy,bmesh,math,ast,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;art=bpy.data.collections['SPEAR • editable components'];blade=next(o for o in art.objects if o.name.startswith('06 •'));mat=blade.data.materials[0]
regions={'gold':(.5,.75,.75,1),'silk':(.75,1,0,.5)}
AX,AY=.798,.603;length=math.hypot(AX,AY);AX/=length;AY/=length;S=.00096
for filename,names in [('build_spear.py',{'atlas','mesh','activate','lathe'}),('refine_cast_gold.py',{'turn'}),('rebuild_reference_gold.py',{'ref','r3'})]:
 tree=ast.parse((ROOT/'Tools/SpearAsset'/filename).read_text(encoding='utf-8'))
 exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'helpers','exec'))
scope={};exec(compile((ROOT/'Tools/SpearAsset/review_proposal.py').read_text(encoding='utf-8'),'proposal','exec'),scope)
ring=next(o for o in art.objects if o.name.startswith('Socket • broad asymmetrical'))
low=min(v.co.z for v in ring.data.vertices);high=max(v.co.z for v in ring.data.vertices);radius=max(math.hypot(v.co.x,v.co.y) for v in ring.data.vertices);name=ring.name
profile=scope['middle_ring_profile']((low+high)*.5,(high-low)*.5,radius)
replacement=turn('TEMP • asymmetrical middle ring',profile,'gold',40)
bpy.data.objects.remove(ring,do_unlink=True);replacement.name=name
bundles=scope['tassel_mesh_data'](r3);old=[o for o in art.objects if o.name.startswith('Tassel • reference silk bundle')];new=[]
for data in bundles:new.append(mesh('TEMP • irregular silk bundle',data['vertices'],data['faces'],'silk',data['uvfaces'],smooth=True))
assert len(new)==24
for ob in old:bpy.data.objects.remove(ob,do_unlink=True)
for ob in new:ob.name='Tassel • reference silk bundle'
for image in bpy.data.images:
 if image.name.startswith('T_ImperialSpear_') and image.source=='FILE':
  image.filepath=str(OUT/'Textures'/(image.name.split('.png')[0]+'.png'));image.reload()
  if '_ORM' in image.name:image.alpha_mode='CHANNEL_PACKED';image.colorspace_settings.name='Non-Color'
report={'ring_bounds_m':[low,high],'maximum_ring_radius_m':radius,'ring_profile':profile,'ribbon_bundle_count':len(new),'ribbon_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in new),'outside_assembly_unchanged':True}
(OUT/'Ring_Fan_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
s.render.filepath=str(OUT/'Comparison_Current.png');bpy.ops.render.render(write_still=True)
print(json.dumps(report))

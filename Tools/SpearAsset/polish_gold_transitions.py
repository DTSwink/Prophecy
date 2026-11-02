"""Finish the ring-to-sleeve transitions and collar shading without contour edits."""
import bpy,math,ast,json,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
art=bpy.data.collections['SPEAR • editable components']
mat=next(o for o in art.objects if o.name.startswith('06 •')).data.materials[0]
regions={'gold':(.5,.75,.5,1),'gold_shadow':(.75,.8125,.5,1),'gold_etched':(.875,1,.5,1)}
import bmesh
for filename,names in [('build_spear.py',{'atlas','mesh','activate','lathe'}),('refine_cast_gold.py',{'turn','fingerprint'})]:
    tree=ast.parse((ROOT/'Tools/SpearAsset'/filename).read_text(encoding='utf-8'))
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'helpers','exec'))
report=json.loads((OUT/'Gold_Detail_Verification.json').read_text(encoding='utf-8'))
for ob in list(art.objects):
    if ob.name.startswith(('Socket • broad domed','Socket • shallow ring shoulder')):
        bpy.data.objects.remove(ob,do_unlink=True)
profiles={
 'lower':[(1.603,.0157),(1.605,.0175),(1.608,.0205),(1.611,.0231),(1.614,.0247),(1.617,.0252),(1.620,.0249),(1.6225,.0234),(1.6245,.0213),(1.626,.0195)],
 'upper':[(1.6855,.0195),(1.687,.0215),(1.689,.0240),(1.692,.0257),(1.695,.0262),(1.698,.0259),(1.701,.0244),(1.703,.0220),(1.7045,.0195)]}
for label,profile in profiles.items(): turn('Socket • broad domed '+label+' ring',profile,'gold',40)
plate=next(o for o in art.objects if o.name.startswith('07 •'))
before=fingerprint(plate)
plate.data.set_sharp_from_angle(angle=math.radians(36))
activate(plate)
mod=plate.modifiers.new('Cast metal weighted corner normals','WEIGHTED_NORMAL')
mod.keep_sharp=True; mod.weight=40; mod.mode='FACE_AREA_WITH_ANGLE'
bpy.ops.object.modifier_apply(modifier=mod.name)
assert before==fingerprint(plate),'Collar topology changed'
for name,digest in report['protected_geometry_sha256'].items():
    assert fingerprint(bpy.data.objects[name])==digest,('Protected geometry changed',name)
report['ring_profiles_m']=profiles
report['ring_specs']=[{'name':name,'centre_m':max(profile,key=lambda p:p[1])[0], 'axial_width_mm':(profile[-1][0]-profile[0][0])*1000,'foot_radius_mm':min(p[1] for p in profile)*1000,'crown_radius_mm':max(p[1] for p in profile)*1000} for name,profile in profiles.items()]
report['lower_ring_tapers_into_shaft']=True
report['separate_ring_shoulder_strips_removed']=True
report['collar_weighted_normals_only']=True
(OUT/'Gold_Detail_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Ring bases blended; collar weighted normals applied; all75 protected components unchanged.')

"""Rebuild just the pierced casting after the concave groove Boolean failed."""
import bpy,bmesh,math,json,ast,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
art=bpy.data.collections['SPEAR • editable components']; blade=next(o for o in art.objects if o.name.startswith('06 •')); mat=blade.data.materials[0]
regions={'gold':(.5,.75,.5,1),'gold_shadow':(.75,.8125,.5,1)}
AX,AY=.798,.603; norm=math.hypot(AX,AY); AX/=norm; AY/=norm; S=.00096
for filename,names in [('build_spear.py',{'atlas','mesh','activate'}),('rebuild_reference_gold.py',{'ref','cubic','smooth_polygon','extrude','boolean','finish_bevel'})]:
 tree=ast.parse((ROOT/'Tools/SpearAsset'/filename).read_text(encoding='utf-8'))
 exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'helpers','exec'))
for o in list(art.objects):
 if o.name.startswith('07 •'): bpy.data.objects.remove(o,do_unlink=True)
outline=[(537,285),(550,279),(571,266),(590,267),(604,271),(612,277),(615,285),(613,296),(610,304),(615,313),(627,321),(619,333),(610,348),(602,362),(584,352),(573,347),(565,349),(560,355),(556,371),(548,362),(542,351),(539,335),(538,316)]
body=extrude('07 • reference cast housing with pierced eye',smooth_polygon(outline,{10,13,18},4),.0115,-.0115)
initial=len(body.data.polygons); eye=ref((604,287))
bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=.0080,depth=.065,location=(eye.x,0,eye.y),rotation=(math.pi/2,0,0))
boolean(body,bpy.context.object); after_eye=len(body.data.polygons)
assert after_eye>0
finish_bevel(body,.00135,3)
bm=bmesh.new(); bm.from_mesh(body.data); closed=all(e.is_manifold for e in bm.edges); volume=bm.calc_volume(signed=True); bm.free()
assert closed and volume>0,(closed,volume)
report=json.loads((OUT/'Reference_Rebuild_Verification.json').read_text(encoding='utf-8'))
report['housing_mesh']={'initial_faces':initial,'after_eye_faces':after_eye,'final_faces':len(body.data.polygons),'closed':closed,'volume_m3':volume}
report['visual_status']='Incomplete: compare materials, relief and housing against reference; rework pending.'
(OUT/'Reference_Rebuild_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report['housing_mesh']))

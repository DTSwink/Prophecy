import bpy,pathlib,json,math
from mathutils import Vector
r=pathlib.Path(__file__).resolve().parents[2];out=r/'Saved/Diagnostics/HolsterStrap20261013'
bpy.ops.wm.open_mainfile(filepath=r'C:/Users/singerie/Downloads/HolsterStrap/HolsterStrap.blend')
arm=bpy.data.objects['HolsterStrapRig'];strap=bpy.data.objects['HolsterStrap'];rigid=bpy.data.objects['HolsterRigid']
original=[v.co.copy()/100 for v in strap.data.vertices]
def evaluated():
    bpy.context.view_layer.update();obj=strap.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=obj.to_mesh();vertices=[v.co.copy()/100 for v in mesh.vertices];obj.to_mesh_clear();return vertices
rest=evaluated();rest_error=max((a-b).length for a,b in zip(original,rest));assert rest_error<1e-6
for i in range(1,6):
    bone=arm.pose.bones[f'strap_{i:02d}'];bone.rotation_mode='XYZ';bone.rotation_euler.x=.13
bent=evaluated();fixed=[i for i,v in enumerate(original) if v.y<=.045]
root_error=max((original[i]-bent[i]).length for i in fixed);assert root_error<1e-6
tip_move=max((a-b).length for a,b in zip(original,bent));assert tip_move>.015
assert len(strap.data.polygons)+len(rigid.data.polygons)==9326
report={'rest_deformation_error_m':rest_error,'fixed_base_error_m':root_error,'posed_tip_displacement_m':tip_move,'fixed_vertices':len(fixed),'strap_vertices':len(original),'triangles_total':9326}
(out/'rig-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

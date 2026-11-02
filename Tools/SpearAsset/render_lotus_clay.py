"""Neutral grazing illumination exposes cavity topology and transition quality."""
import bpy,math
from mathutils import Vector
from pathlib import Path
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');W=R/'Saved/Diagnostics/ImperialSpear/PommelLotus'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
state=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples)
ls=[(o,o.location.copy(),o.rotation_euler.copy()) for o in s.objects if o.type=='LIGHT']
clay=bpy.data.materials.get('TEMP_Lotus_Clay') or bpy.data.materials.new('TEMP_Lotus_Clay');clay.use_nodes=True
pr=next(n for n in clay.node_tree.nodes if n.type=='BSDF_PRINCIPLED');pr.inputs['Base Color'].default_value=(.24,.27,.31,1);pr.inputs['Metallic'].default_value=.15;pr.inputs['Roughness'].default_value=.30
parts=[o for o in bpy.data.collections['SPEAR • editable components'].objects if o.type=='MESH' and o.name.startswith(('02 •','Pommel •'))]
savedm=[(o,o.data.materials[0]) for o in parts]
try:
    for o,m in savedm:o.data.materials[0]=clay
    aim=Vector((0,0,.057))
    for o,loc,rot in ls:o.location.z-=1.65;o.rotation_euler=(aim-o.location).to_track_quat('-Z','Y').to_euler()
    cam.location=aim+Vector((.27,-.85,-.08));cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.rotation_euler.rotate_axis('Z',math.radians(-40))
    cam.data.ortho_scale=.215;s.render.resolution_x=1100;s.render.resolution_y=1100;s.render.resolution_percentage=100
    s.cycles.device='CPU';s.cycles.samples=32;s.render.threads_mode='FIXED';s.render.threads=3
    s.render.filepath=str(W/'Clay_Oblique.png');bpy.ops.render.render(write_still=True)
finally:
    for o,m in savedm:o.data.materials[0]=m
    cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples=state
    for o,loc,rot in ls:o.location=loc;o.rotation_euler=rot
print('Clay inspection saved; materials and accepted camera restored.')

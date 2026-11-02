import bpy
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene']; bpy.context.window.scene=s
key=bpy.data.objects['Key • soft silver']; key.data.energy=65; key.data.size=1.3; key.data.size_y=.35
key.location=(-1.4,-.9,2.3); key.rotation_euler=(Vector((0,0,1.3))-key.location).to_track_quat('-Z','Y').to_euler()
bpy.data.objects['Fill • long strip'].data.energy=10
bpy.data.objects['Rim • warm gold'].data.energy=45
for node in s.world.node_tree.nodes:
 if node.type=='BACKGROUND' and node.name=='Background': node.inputs['Strength'].default_value=.08
s['Reference_lighting_pass']='Grazing key(-1.4,-.9,2.3),65W 1.3x.35m; fill10W; rim45W; world.08; unchanged AgX/exposure.'
s.render.filepath=str(OUT/'Comparison_Current.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
bpy.ops.render.render(write_still=True)
print(s['Reference_lighting_pass'])

import bpy, math
from mathutils import Vector
from pathlib import Path
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
s=bpy.context.scene
s.camera.location=(.22,-4,1.16)
s.camera.rotation_euler=(Vector((.04,0,1.10))-s.camera.location).to_track_quat('-Z','Y').to_euler()
s.camera.rotation_euler.rotate_axis('Z',math.radians(-43))
s.camera.data.ortho_scale=2.58
s.render.film_transparent=False
w=s.world.node_tree; bg=w.nodes.get('Background'); out=w.nodes.get('World Output')
dark=w.nodes.new('ShaderNodeBackground'); dark.inputs[0].default_value=(.008,.012,.018,1); dark.inputs[1].default_value=.5
lp=w.nodes.new('ShaderNodeLightPath'); mix=w.nodes.new('ShaderNodeMixShader')
w.links.new(lp.outputs['Is Camera Ray'],mix.inputs[0]); w.links.new(bg.outputs[0],mix.inputs[1]); w.links.new(dark.outputs[0],mix.inputs[2]); w.links.new(mix.outputs[0],out.inputs[0])
s.render.resolution_x=1400; s.render.resolution_y=1000; s.cycles.samples=24
s.render.filepath=str(OUT/'Preview_Full.png')
bpy.ops.render.render(write_still=True)
print('Preview saved:',s.render.filepath)

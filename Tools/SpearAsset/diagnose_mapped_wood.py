import bpy,math,json
from pathlib import Path
from mathutils import Vector
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');s=bpy.data.scenes['Scene'];cam=s.camera
m=bpy.data.materials['M_ImperialSpear_PBR'];n=m.node_tree.nodes;links=m.node_tree.links
out=n['Material Output'];savedlink=[(l.from_socket,l.to_socket) for l in out.inputs['Surface'].links]
print('persistent',s.render.use_persistent_data)
print('images',[(x.name,x.projection,x.interpolation,x.extension) for x in n if x.type=='TEX_IMAGE'])
saved=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples,s.cycles.use_denoising,s.render.use_persistent_data)
e=n.new('ShaderNodeEmission');e.inputs['Strength'].default_value=1
try:
 s.render.use_persistent_data=False;s.cycles.use_denoising=False;s.cycles.samples=1;s.render.resolution_x=700;s.render.resolution_y=700
 aim=Vector((0,0,1.435));cam.location=aim+Vector((0,-3,0));cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.14
 links.new(n['Atlas_normal'].outputs['Color'],e.inputs['Color']);links.new(e.outputs[0],out.inputs['Surface'])
 s.render.filepath=str(R/'Exports/ImperialSpear/Diagnostic_Mapped_Normal.png');bpy.ops.render.render(write_still=True)
finally:
 n.remove(e)
 for a,b in savedlink:links.new(a,b)
 cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples,s.cycles.use_denoising,s.render.use_persistent_data=saved

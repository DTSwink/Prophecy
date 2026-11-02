"""One small raw crop to distinguish material detail from denoiser smoothing."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
saved=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples,s.cycles.use_denoising)
try:
    aim=Vector((0,0,1.413));cam.location=aim+Vector((0,-3,.02))
    cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.rotation_euler.rotate_axis('Z',math.radians(-43))
    cam.data.ortho_scale=.14;s.render.resolution_x=900;s.render.resolution_y=700;s.cycles.samples=128;s.cycles.use_denoising=False
    s.render.filepath=str(OUT/'Diagnostic_FinalWood_Raw.png');bpy.ops.render.render(write_still=True)
finally:
    cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples,s.cycles.use_denoising=saved
nodes=bpy.data.materials['M_ImperialSpear_PBR'].node_tree.nodes
normal=nodes['Normal Map'];image=nodes['Atlas_normal'].image
print(json.dumps({'normal_space':normal.space,'uv_map':normal.uv_map,'strength':normal.inputs['Strength'].default_value,'image_color_space':image.colorspace_settings.name,'normal_output_links':[l.to_socket.name for l in normal.outputs[0].links]}))

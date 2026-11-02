"""Full-length context with accepted scene lighting and restored camera."""
import bpy,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
saved=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,
       s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples)
try:
    s.render.threads_mode='FIXED';s.render.threads=3;s.cycles.device='CPU';s.cycles.samples=24
    aim=Vector((.04,0,1.1));cam.location=aim+Vector((0,-3,.025))
    cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.rotation_euler.rotate_axis('Z',math.radians(-43));cam.data.ortho_scale=2.58
    s.render.resolution_x,s.render.resolution_y=1400,1000;s.render.filepath=str(OUT/'Preview_Full.png')
    bpy.ops.render.render(write_still=True)
finally:
    cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples=saved
print('Full preview refreshed; accepted camera restored.')

"""Render a lower-end inspection through MCP; never save or change the asset."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');O=R/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
state=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples)
light_state=[(o,o.location.copy(),o.rotation_euler.copy()) for o in s.objects if o.type=='LIGHT']
try:
 aim=Vector((0,0,.105))
 for o,loc,rot in light_state:
  o.location.z-=1.65;o.rotation_euler=(aim-o.location).to_track_quat('-Z','Y').to_euler()
 cam.location=aim+Vector((.24,-.85,-.14));cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.rotation_euler.rotate_axis('Z',math.radians(-43))
 cam.data.ortho_scale=.255;s.render.resolution_x=1100;s.render.resolution_y=900;s.render.resolution_percentage=100
 s.cycles.device='CPU';s.cycles.samples=40;s.render.threads_mode='FIXED';s.render.threads=3
 s.render.filepath=str(O/'Preview_Pommel.png');bpy.ops.render.render(write_still=True)
finally:
 cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples=state
 for o,loc,rot in light_state:o.location=loc;o.rotation_euler=rot
print('Pommel preview saved; asset and source files unchanged.')
bpy.app.timers.register(lambda:bpy.ops.wm.quit_blender(),first_interval=2)

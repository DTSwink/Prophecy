"""Bounded sequential CPU inspection still, restore accepted setup afterwards."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');O=R/'Saved/Diagnostics/ImperialSpear/PommelLeaf'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
state=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples)
lights=[(o,o.location.copy(),o.rotation_euler.copy()) for o in s.objects if o.type=='LIGHT']
front=globals().get('LEAF_VIEW')=='front'
try:
    aim=Vector((0,0,.084))
    for o,loc,rot in lights:
        o.location.z-=1.65;o.rotation_euler=(aim-o.location).to_track_quat('-Z','Y').to_euler()
    cam.location=aim+Vector((0,-.85,0) if front else (.20,-.85,-.11));cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.rotation_euler.rotate_axis('Z',math.radians(-40))
    cam.data.ortho_scale=.215;s.render.resolution_x=1000;s.render.resolution_y=1000;s.render.resolution_percentage=100
    s.cycles.device='CPU';s.cycles.samples=32;s.render.threads_mode='FIXED';s.render.threads=3
    s.render.filepath=str(O/('Leaf_Front.png' if front else 'Leaf_ThreeQuarter.png'));bpy.ops.render.render(write_still=True)
finally:
    cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples=state
    for o,loc,rot in lights:o.location=loc;o.rotation_euler=rot
print('Leaf inspection render saved; accepted camera restored.')

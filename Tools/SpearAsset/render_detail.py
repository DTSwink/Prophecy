import bpy, math
from mathutils import Vector
from pathlib import Path
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
s=bpy.context.scene; cam=s.camera
cam.location=(.28,-3,1.94); target=Vector((.055,0,1.91))
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler(); cam.rotation_euler.rotate_axis('Z',math.radians(-30))
cam.data.ortho_scale=.71
s.render.resolution_x=1200; s.render.resolution_y=1200; s.cycles.samples=32
s.render.filepath=str(OUT/'Preview_Head.png')
bpy.ops.render.render(write_still=True)
print('Head preview saved')

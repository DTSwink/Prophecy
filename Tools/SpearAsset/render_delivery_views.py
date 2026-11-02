"""Refresh the full asset and reverse/oblique inspection views, three CPU threads."""
import bpy,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
saved=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,
       s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples)
jobs=[('Preview_ThreeQuarter',48,(.055,0,1.89),.76,-30,(1000,1000)),
      ('Preview_Back',180,(.055,0,1.90),.76,30,(1000,1000)),
      ('Preview_Recess_Detail',35,(0,0,1.95),.105,-25,(1000,800)),
      ('Preview_Full',0,(.04,0,1.1),2.58,-43,(1400,1000))]
try:
    s.render.threads_mode='FIXED';s.render.threads=3;s.cycles.device='CPU';s.cycles.samples=24
    for name,azimuth,target,scale,roll,size in jobs:
        aim=Vector(target);a=math.radians(azimuth)
        cam.location=aim+Vector((3*math.sin(a),-3*math.cos(a),.025))
        cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler()
        cam.rotation_euler.rotate_axis('Z',math.radians(roll));cam.data.ortho_scale=scale
        s.render.resolution_x,s.render.resolution_y=size;s.render.filepath=str(OUT/(name+'.png'))
        bpy.ops.render.render(write_still=True);print('Rendered',name,flush=True)
finally:
    cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples=saved
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print('Delivery views refreshed; matched camera restored.')

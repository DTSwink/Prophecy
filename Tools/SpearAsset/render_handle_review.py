"""Two bounded CPU views explicitly showing wood/gold/leather together."""
import bpy,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
for image in bpy.data.images:
    if image.name.startswith('T_ImperialSpear_') and image.source=='FILE':
        image.filepath=str(OUT/'Textures'/(image.name.split('.png')[0]+'.png'));image.reload()
        if '_ORM' in image.name:image.alpha_mode='CHANNEL_PACKED';image.colorspace_settings.name='Non-Color'
saved=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples)
try:
    s.cycles.device='CPU';s.render.threads_mode='FIXED';s.render.threads=3
    for name,z,scale,size,offset,samples in [
        ('Candidate_Handle_Transition.png',1.360,.18,(1000,1000),(0,-3,.02),48),
        ('Candidate_Handle_Full.png',1.260,.50,(1200,900),(.18,-.65,.035),32)]:
        aim=Vector((0,0,z));cam.location=aim+Vector(offset)
        cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.rotation_euler.rotate_axis('Z',math.radians(-43))
        cam.data.ortho_scale=scale;s.render.resolution_x,s.render.resolution_y=size;s.cycles.samples=samples
        s.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True);print('Rendered',name,flush=True)
finally:
    cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples=saved
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print('Handle reviews saved; accepted matched camera restored.')

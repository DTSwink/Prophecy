"""Bounded, sequential CPU detail views with exact main-camera restoration."""
import bpy,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
saved=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples)
ax,ay=s['Reference_camera_axis'];scale=.00096
def target(cx,cy):return Vector((((cx-172)*ay-(cy-9)*ax)*scale,0,2.2-((cx-172)*ax+(cy-9)*ay)*scale))
try:
 s.cycles.samples=24
 for name,cx,cy,width,resx,resy,offset in [
  ('Comparison_DetailMacro.png',700,335,520,1300,700,(0,-3,0)),
  ('Comparison_WoodDetail.png',811,483,245,980,640,(0,-3,0)),
  ('Comparison_GoldOblique.png',623,344,310,1050,850,(.14,-.45,.06))]:
  aim=target(cx,cy);cam.location=aim+Vector(offset);cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.rotation_euler.rotate_axis('Z',-math.atan2(ax,ay))
  cam.data.ortho_scale=width*scale;s.render.resolution_x=resx;s.render.resolution_y=resy;s.render.filepath=str(OUT/name)
  bpy.ops.render.render(write_still=True);print('Rendered',name)
finally:
 cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples=saved
 bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print('Detail views completed; matched main camera restored.')

"""Fixed camera calibration from the screenshot's tip and straight shaft axis."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
s=bpy.data.scenes['Scene']; bpy.context.window.scene=s; cam=s.camera
scale=.00096; cx,cy=600,336.5; tx,ty=172,9
# Normalized axis measured from blade tip to the long shaft in the reference.
ax,ay=.798,.603; norm=(ax*ax+ay*ay)**.5; ax/=norm; ay/=norm
x=((cx-tx)*ay-(cy-ty)*ax)*scale
z=2.2-((cx-tx)*ax+(cy-ty)*ay)*scale
cam.location=(x,-3,z); target=Vector((x,0,z))
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
cam.rotation_euler.rotate_axis('Z',-math.atan2(ax,ay)); cam.data.type='ORTHO'; cam.data.ortho_scale=1200*scale
s.render.resolution_x=1200; s.render.resolution_y=673; s.render.resolution_percentage=100
s.render.engine='CYCLES'; s.cycles.device='CPU'; s.cycles.samples=24; s.cycles.use_denoising=True
s.render.threads_mode='FIXED'; s.render.threads=3; s.render.film_transparent=False
# Only the camera background is black; environment remains the present baseline.
world=s.world.node_tree
for node in world.nodes:
    if node.type=='BACKGROUND' and node.name!='Background': node.inputs['Color'].default_value=(0,0,0,1)
s['Reference_camera_pixel_scale_m']=scale
s['Reference_camera_target']=[x,0,z]
s['Reference_camera_axis']=[ax,ay]
s.render.filepath=str(OUT/'Comparison_Before.png'); bpy.ops.render.render(write_still=True)
(OUT/'Reference_Camera.json').write_text(json.dumps({'source_size':[1200,673],'tip_px':[172,9],'axis':[ax,ay],'metres_per_pixel':scale,'target':[x,0,z],'roll_degrees':-math.degrees(math.atan2(ax,ay))},indent=2),encoding='utf-8')
print('Reference camera calibrated; comparison baseline rendered.')

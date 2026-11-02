import bpy,math,json
from mathutils import Vector
from pathlib import Path
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
source=bpy.data.scenes['Scene']; game=bpy.data.scenes['GAME • Unreal export']
cam=source.camera; cam.location=(.22,-4,1.16)
cam.rotation_euler=(Vector((.04,0,1.1))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.rotation_euler.rotate_axis('Z',math.radians(-43)); cam.data.ortho_scale=2.58
source.render.resolution_x=1400; source.render.resolution_y=1000
source.render.filepath=str(OUT/'Preview_Full.png')
for scene,centre,filename in [(game,(.04,0,-.135),'ImperialSpear_Game.blend'),(source,(.04,0,1.1),'ImperialSpear_Source.blend')]:
    bpy.context.window.scene=scene
    bpy.ops.object.select_all(action='DESELECT')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                sp=area.spaces.active; sp.region_3d.view_location=centre; sp.region_3d.view_distance=2.55
                sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion(); sp.region_3d.view_perspective='ORTHO'
                sp.shading.type='SOLID'; sp.overlay.show_floor=False
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/filename))
print('Both blend files saved with framed views; owned Blender closing.')
def close_owned():
    bpy.ops.wm.quit_blender()
bpy.app.timers.register(close_owned,first_interval=2)

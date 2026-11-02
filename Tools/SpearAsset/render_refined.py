import bpy,math,json
from pathlib import Path
from mathutils import Vector
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene; cam=scene.camera
view=json.loads((OUT/'render_request.json').read_text()) if (OUT/'render_request.json').exists() else {'name':'Preview_Head_Refined','azimuth':0,'target':[.055,0,1.81],'scale':.95,'roll':-43,'size':[1400,1000]}
target=Vector(view['target']); a=math.radians(view['azimuth'])
cam.location=target+Vector((3*math.sin(a),-3*math.cos(a),view.get('elevation',.025)))
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler(); cam.rotation_euler.rotate_axis('Z',math.radians(view.get('roll',0)))
cam.data.type='ORTHO'; cam.data.ortho_scale=view['scale']; scene.render.resolution_x,scene.render.resolution_y=view['size']
scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=view.get('samples',32); scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED'; scene.render.threads=3; scene.render.film_transparent=False
scene.render.filepath=str(OUT/(view['name']+'.png')); bpy.ops.render.render(write_still=True)
print('Rendered '+view['name'])

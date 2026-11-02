"""A dedicated, neutral material inspection light rig; never saved into source."""
import bpy,math
from pathlib import Path
from mathutils import Vector
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
saved=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples)
lights=[(o,o.hide_render) for o in s.objects if o.type=='LIGHT'];added=[]
try:
 for o,_ in lights:o.hide_render=True
 for name,loc,energy,size,sizey in [('WoodInspectionKey',(-.45,-.75,1.43),30,.20,.55),('WoodInspectionFill',(.5,-.8,1.62),5,.7,.7),('WoodInspectionRim',(.5,.1,1.40),10,.35,.55)]:
  data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.shape='RECTANGLE';data.size=size;data.size_y=sizey
  o=bpy.data.objects.new(name,data);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.36))-o.location).to_track_quat('-Z','Y').to_euler();added.append(o)
 aim=Vector((0,0,1.36));cam.location=aim+Vector((0,-3,.02));cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.rotation_euler.rotate_axis('Z',math.radians(-43));cam.data.ortho_scale=.18
 s.render.resolution_x=1000;s.render.resolution_y=1000;s.cycles.samples=48;s.cycles.device='CPU';s.render.threads=3
 s.render.filepath=str(R/'Exports/ImperialSpear/Diagnostic_Wood_InspectionLight.png');bpy.ops.render.render(write_still=True)
finally:
 for o in added:
  data=o.data;bpy.data.objects.remove(o,do_unlink=True);bpy.data.lights.remove(data)
 for o,hide in lights:o.hide_render=hide
 cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples=saved
print('Material comparison rendered; source lighting and camera restored.')

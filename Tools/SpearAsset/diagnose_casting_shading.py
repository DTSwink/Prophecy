"""Constant metal diagnostic isolates actual geometry and interpolation."""
import bpy,math
from pathlib import Path
from mathutils import Vector
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
art=bpy.data.collections['SPEAR • editable components'];mat=next(o for o in art.objects if o.name.startswith('06 •')).data.materials[0]
p=mat.node_tree.nodes['Principled BSDF'];links=mat.node_tree.links;removed=[(l.from_socket,l.to_socket) for l in links if l.to_node==p and l.to_socket.name in ['Base Color','Roughness','Metallic','Normal']]
values={name:p.inputs[name].default_value[:] if name=='Base Color' else p.inputs[name].default_value for name in ['Base Color','Roughness','Metallic']}
state=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.cycles.samples,s.render.filepath)
ax,ay=s['Reference_camera_axis'];cx,cy=588,321;scale=.00096
try:
 for a,b in removed:
  for l in list(b.links):links.remove(l)
 p.inputs['Base Color'].default_value=(.36,.24,.10,1);p.inputs['Roughness'].default_value=.42;p.inputs['Metallic'].default_value=1
 cam.location=(((cx-172)*ay-(cy-9)*ax)*scale,-3,2.2-((cx-172)*ax+(cy-9)*ay)*scale);cam.data.ortho_scale=185*scale
 s.render.resolution_x=740;s.render.resolution_y=600;s.cycles.samples=48;s.render.filepath=str(OUT/'Diagnostic_CastingConstantMetal.png');bpy.ops.render.render(write_still=True)
finally:
 for name,value in values.items():p.inputs[name].default_value=value
 for a,b in removed:links.new(a,b)
 cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.cycles.samples,s.render.filepath=state
print('Constant-metal casting diagnostic rendered; material and camera restored.')

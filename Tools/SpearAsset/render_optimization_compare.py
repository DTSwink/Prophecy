"""Identical-camera before/after renders; restore every temporary scene change."""
import bpy,math,json
from mathutils import Vector
from pathlib import Path
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=R/'Saved/Diagnostics/ImperialSpear/Optimization20261028'
request=json.loads((OUT/'render_request.json').read_text());view=request['view']
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
art=bpy.data.collections['SPEAR • editable components'];objects=[o for o in art.objects if o.type=='MESH']
meshes={o:o.data for o in objects}
state=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.resolution_percentage,s.render.filepath,s.cycles.samples,s.cycles.seed,s.cycles.use_denoising)
lights=[(o,o.hide_render) for o in s.objects if o.type=='LIGHT'];old_world=s.world;temporary=[]
try:
 if view=='head':
  aim=Vector((.015,0,1.744));offset=Vector((.14,-.55,.06));scale=.27
  s.render.resolution_x=1000;s.render.resolution_y=900
 else:
  aim=Vector((0,0,.055));offset=Vector((.23,-.85,-.09));scale=.175
  s.render.resolution_x=950;s.render.resolution_y=1000
  for o,h in lights:o.hide_render=True
  world=bpy.data.worlds.new('TEMP optimization world');world.use_nodes=True;n=world.node_tree.nodes;l=world.node_tree.links;n.clear()
  out=n.new('ShaderNodeOutputWorld');mix=n.new('ShaderNodeMixShader');path=n.new('ShaderNodeLightPath');ambient=n.new('ShaderNodeBackground');ambient.inputs['Color'].default_value=(.22,.23,.25,1);ambient.inputs['Strength'].default_value=.24
  black=n.new('ShaderNodeBackground');black.inputs['Color'].default_value=(0,0,0,1);l.new(path.outputs['Is Camera Ray'],mix.inputs[0]);l.new(ambient.outputs[0],mix.inputs[1]);l.new(black.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],out.inputs[0]);s.world=world
  for name,ofs,energy,size,sy in [('Key',(-.22,-.28,.20),3.,.075,.28),('Fill',(.24,-.18,.1),.9,.18,.3),('Rim',(.16,.16,.12),2.7,.055,.24)]:
   d=bpy.data.lights.new('TEMP optimization '+name,'AREA');d.energy=energy;d.shape='RECTANGLE';d.size=size;d.size_y=sy;o=bpy.data.objects.new(d.name,d);s.collection.objects.link(o);o.location=aim+Vector(ofs);o.rotation_euler=(aim-o.location).to_track_quat('-Z','Y').to_euler();temporary.append(o)
 cam.location=aim+offset;cam.rotation_euler=(-offset).to_track_quat('-Z','Y').to_euler();cam.rotation_euler.rotate_axis('Z',math.radians(-40));cam.data.ortho_scale=scale
 s.render.resolution_percentage=100;s.cycles.device='CPU';s.cycles.samples=48;s.cycles.seed=121;s.cycles.use_denoising=True;s.render.threads_mode='FIXED';s.render.threads=3
 for label in request.get('labels',['Before','After']):
  for o,m in meshes.items():
   ref=bpy.data.objects.get('OPTREF '+o.name);o.data=ref.data if label=='Before' and ref else m
  s.render.filepath=str(OUT/(view+'_'+label+'.png'));bpy.ops.render.render(write_still=True)
finally:
 for o,m in meshes.items():o.data=m
 cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.resolution_percentage,s.render.filepath,s.cycles.samples,s.cycles.seed,s.cycles.use_denoising=state
 for o,h in lights:o.hide_render=h
 for o in temporary:d=o.data;bpy.data.objects.remove(o,do_unlink=True);bpy.data.lights.remove(d)
 s.world=old_world
 if 'world' in globals():bpy.data.worlds.remove(world)
print('Comparison saved:',view)

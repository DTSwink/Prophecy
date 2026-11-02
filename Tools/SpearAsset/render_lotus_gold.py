"""One bounded PBR inspection frame with restored camera and light setup."""
import bpy,math
from mathutils import Vector
from pathlib import Path
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');W=R/'Saved/Diagnostics/ImperialSpear/PommelLotus'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;cam=s.camera
state=(cam.location.copy(),cam.rotation_euler.copy(),cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples)
ls=[(o,o.location.copy(),o.rotation_euler.copy()) for o in s.objects if o.type=='LIGHT']
old_world=s.world;temporary=[];visibility=[(o,o.hide_render) for o,loc,rot in ls]
art_visibility=[]
view=globals().get('LOTUS_VIEW','oblique')
try:
    aim=Vector((0,0,.058 if view=='end' else (.097 if view=='root' else (.026 if view=='reference' else (.056 if view!='detail' else .023)))))
    if view=='end':
        art_visibility=[(o,o.hide_render) for o in bpy.data.collections['SPEAR • editable components'].objects]
        for o,hidden in art_visibility:o.hide_render=o.name!='02 • carved lotus pommel body'
    for o,loc,rot in ls:o.hide_render=True
    world=bpy.data.worlds.new('TEMP Lotus inspection world');world.use_nodes=True;n=world.node_tree.nodes;l=world.node_tree.links;n.clear()
    out=n.new('ShaderNodeOutputWorld');mix=n.new('ShaderNodeMixShader');path=n.new('ShaderNodeLightPath')
    ambient=n.new('ShaderNodeBackground');ambient.inputs['Color'].default_value=(.22,.23,.25,1);ambient.inputs['Strength'].default_value=.24
    black=n.new('ShaderNodeBackground');black.inputs['Color'].default_value=(0,0,0,1)
    l.new(path.outputs['Is Camera Ray'],mix.inputs[0]);l.new(ambient.outputs[0],mix.inputs[1]);l.new(black.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],out.inputs[0]);s.world=world
    for name,offset,energy,size,sy in [('Key',(-.22,-.28,.20),3.0,.075,.28),('Fill',(.24,-.18,.10),.9,.18,.30),('Rim',(.16,.16,.12),2.7,.055,.24)]:
        if view=='end':offset=(offset[0],offset[1],-.20 if name!='Rim' else .15)
        data=bpy.data.lights.new('TEMP Lotus '+name,'AREA');data.energy=energy;data.shape='RECTANGLE';data.size=size;data.size_y=sy
        ob=bpy.data.objects.new(data.name,data);s.collection.objects.link(ob);ob.location=aim+Vector(offset);ob.rotation_euler=(aim-ob.location).to_track_quat('-Z','Y').to_euler();temporary.append(ob)
    offset={'oblique':(.23,-.85,-.09),'front':(0,-.85,0),'detail':(.30,-.85,-.14),'reference':(.23,-.85,-.09),'back':(-.30,.85,-.08),'root':(.23,-.85,-.09),'diagonal':(.60,-.60,-.06),'end':(0,0,-.8)}[view]
    cam.location=aim+Vector(offset);cam.rotation_euler=(aim-cam.location).to_track_quat('-Z','Y').to_euler();cam.rotation_euler.rotate_axis('Z',math.radians(0 if view=='end' else -40))
    cam.data.ortho_scale=.065 if view in ('root','end') else (.21 if view!='detail' else .137);s.render.resolution_x=1000 if view in ('root','end') else 1200;s.render.resolution_y=s.render.resolution_x;s.render.resolution_percentage=100
    if view=='reference':
        cam.data.ortho_scale=.128;s.render.resolution_x=1388;s.render.resolution_y=1134
    s.cycles.device='CPU';s.cycles.samples=96;s.render.threads_mode='FIXED';s.render.threads=3
    s.render.filepath=str(W/('Gold_'+view+'.png'));bpy.ops.render.render(write_still=True)
finally:
    cam.location,cam.rotation_euler,cam.data.ortho_scale,s.render.resolution_x,s.render.resolution_y,s.render.filepath,s.cycles.samples=state
    for o,loc,rot in ls:o.location=loc;o.rotation_euler=rot
    for o,hidden in visibility:o.hide_render=hidden
    for o,hidden in art_visibility:o.hide_render=hidden
    for o in temporary:
        data=o.data;bpy.data.objects.remove(o,do_unlink=True);bpy.data.lights.remove(data)
    s.world=old_world
    if 'world' in globals():bpy.data.worlds.remove(world)
print('Gold '+view+' inspection saved; accepted camera restored.')

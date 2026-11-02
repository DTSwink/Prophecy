"""Controlled glass reflection study, without changing the accepted liquid."""
import unreal as u,runpy,time,traceback
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
w=ed.get_editor_world();actors=u.get_editor_subsystem(u.EditorActorSubsystem)
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Shell'
r=runpy.run_path(str(Path(u.Paths.project_dir()).resolve()/'Tools/Oil/BottleMaterials.py'))
for a in actors.get_all_level_actors():
 if a.get_actor_label().startswith('OilReflectionStudy'):actors.destroy_actor(a)
b=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewBottle')
b.bottle.set_static_mesh(u.load_asset('/Game/_mygame/Tests/Oil/Studio/SM_FabSurfaceReview'))
liquid=b.get_component_by_class(u.ProphecyOilLiquid);locked=liquid.get_material(0)
g=u.load_asset('/Game/_mygame/OilBottle/Materials/M_OilBottleGlass');b.bottle.set_material(0,g)
mid=b.bottle.create_dynamic_material_instance(0)
for k,v in [('Specular',.5),('Roughness',.15),('EdgeCoverage',1)]:mid.set_scalar_parameter_value(k,v)
cam=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewCamera');c=cam.get_component_by_class(u.SceneCaptureComponent2D)
base=b.get_actor_location();target=base+u.Vector(0,0,14)
c.texture_target=u.RenderingLibrary.create_render_target2d(w,1200,1200,u.TextureRenderTargetFormat.RTF_RGBA8)
lights=[]
for label,offset,width,power in [('Left',(-25,-8,14),18,1500),('Right',(20,5,14),13,1500)]:
 p=base+u.Vector(*offset);a=actors.spawn_actor_from_class(u.RectLight,p,u.MathLibrary.find_look_at_rotation(p,target));a.set_actor_label('OilReflectionStudy'+label)
 lc=a.light_component;lc.set_mobility(u.ComponentMobility.MOVABLE)
 for k,v in {'intensity':power,'source_width':width,'source_height':65.,'attenuation_radius':200.,'cast_shadows':False,'diffuse_scale':0.,'specular_scale':1.}.items():lc.set_editor_property(k,v)
 lights.append(a)
bg=u.new_object(u.Material);bg.set_editor_property('shading_model',u.MaterialShadingModel.MSM_UNLIT)
r['wire'](r['color'](bg,'Gray',(40,40,40)),u.MaterialProperty.MP_EMISSIVE_COLOR);r['compile'](bg)
card=actors.spawn_actor_from_class(u.StaticMeshActor,base+u.Vector(-10,20,15));card.set_actor_label('OilReflectionStudyBackdrop')
card.set_actor_scale3d(u.Vector(2,.002,2));card.set_actor_rotation(u.Rotator(0,29,0),False)
sc=card.static_mesh_component;sc.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'));sc.set_material(0,bg);sc.set_cast_shadow(False);sc.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
floor=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='Oil_MeshFloor')
cases=[('full-response',False,False,True),('edge-lights',True,False,True),('studio-empty',True,True,False),('studio-filled',True,True,True)]
s={'n':0,'i':0,'start':time.monotonic(),'refs':[bg,mid,g,card,lights]}
def setup():
 _,lit,gray,fill=cases[s['i']]
 for a in lights:a.light_component.set_visibility(lit)
 card.set_is_temporarily_hidden_in_editor(not gray);floor.set_is_temporarily_hidden_in_editor(gray)
 liquid.set_visibility(fill);c.capture_every_frame=True
def tick(_):
 try:
  if time.monotonic()-s['start']>120:raise TimeoutError('glass light study')
  s['n']+=1
  if s['n']<40:return
  assert liquid.get_material(0)==locked
  u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),cases[s['i']][0]+'.png')
  s['i']+=1;s['n']=0
  if s['i']<len(cases):setup();return
  c.capture_every_frame=False;liquid.set_visibility(True);floor.set_is_temporarily_hidden_in_editor(False);card.set_is_temporarily_hidden_in_editor(True)
  u.unregister_slate_post_tick_callback(s['handle']);print('OIL_REFLECTION_STUDY_DONE')
 except Exception:
  c.capture_every_frame=False;u.unregister_slate_post_tick_callback(s['handle']);(out/'error.txt').write_text(traceback.format_exc())
setup();s['handle']=u.register_slate_post_tick_callback(tick)

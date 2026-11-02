"""Owned, unsaved optical comparison. No physics, scene saves or material saves."""
import unreal as u, runpy, time, traceback, json
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
w=ed.get_editor_world();actors=u.get_editor_subsystem(u.EditorActorSubsystem)
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Transmission'
out.mkdir(parents=True,exist_ok=True)
r=runpy.run_path(str(Path(u.Paths.project_dir()).resolve()/'Tools/Oil/BottleMaterials.py'))
for name in ['node','scalar','color','wire','custom','compile']:globals()[name]=r[name]
for a in actors.get_all_level_actors():
 if a.get_actor_label().startswith('OilTransmission'):actors.destroy_actor(a)
bottle=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewBottle')
cam=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewCamera')
c=cam.get_component_by_class(u.SceneCaptureComponent2D)
c.texture_target=u.RenderingLibrary.create_render_target2d(w,1000,1000,u.TextureRenderTargetFormat.RTF_RGBA8)
liquid=bottle.get_component_by_class(u.ProphecyOilLiquid)
original=u.load_asset('/Game/_mygame/OilBottle/Materials/M_OilBottleLiquid')
candidate=r['build_liquid'](u.new_object(u.Material))
liquid.set_material(0,candidate);mid=liquid.create_dynamic_material_instance(0)
# A neutral card behind the bottle makes actual transmitted detail measurable.
m=u.new_object(u.Material);m.set_editor_property('shading_model',u.MaterialShadingModel.MSM_UNLIT)
uv=node(m,u.MaterialExpressionTextureCoordinate)
pattern=custom(m,'return lerp(float3(8,8,8),float3(100,100,100),step(.38,frac(UV.x*6)));',{'UV':uv},u.CustomMaterialOutputType.CMOT_FLOAT3)
wire(pattern,u.MaterialProperty.MP_EMISSIVE_COLOR);compile(m)
card=actors.spawn_actor_from_class(u.StaticMeshActor,bottle.get_actor_location()+u.Vector(-3,5,18))
card.set_actor_label('OilTransmissionCard');card.set_actor_scale3d(u.Vector(.5,.004,.5))
card.set_actor_rotation(u.Rotator(0,29,0),False)
sc=card.static_mesh_component;sc.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'));sc.set_material(0,m)
sc.set_collision_enabled(u.CollisionEnabled.NO_COLLISION);sc.set_cast_shadow(False)
cases=[('volume-card',(.72,.32,.012),.45,True,1.005),('volume-clear-card',(1,1,1),0,True,1.005),
       ('volume-plain',(.72,.32,.012),.45,False,1.005),('volume-no-refract',(.72,.32,.012),.45,False,1.)]
study={'i':0,'n':0,'start':time.monotonic(),'refs':[m,mid,card,original,candidate]}
def setup():
 name,tint,spec,visible,refraction=cases[study['i']]
 mid.set_vector_parameter_value('Transmission',u.LinearColor(*tint,1));mid.set_scalar_parameter_value('Specular',spec)
 mid.set_scalar_parameter_value('Refraction',refraction)
 card.set_is_temporarily_hidden_in_editor(not visible);c.capture_every_frame=True
def capture(_):
 try:
  if time.monotonic()-study['start']>150:raise TimeoutError('optical study')
  study['n']+=1
  if study['n']<30:return
  name=cases[study['i']][0];u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),name+'.png')
  study['i']+=1;study['n']=0
  if study['i']<len(cases):setup();return
  c.capture_every_frame=False;liquid.set_material(0,original);card.set_is_temporarily_hidden_in_editor(True)
  u.unregister_slate_post_tick_callback(study['handle']);print('OIL_TRANSMISSION_STUDY_DONE')
 except Exception:
  c.capture_every_frame=False;u.unregister_slate_post_tick_callback(study['handle'])
  (out/'error.txt').write_text(traceback.format_exc())
setup();study['handle']=u.register_slate_post_tick_callback(capture)

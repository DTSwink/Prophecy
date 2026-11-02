"""Unsaved front/oblique optical review with a neutral checker behind the oil."""
import unreal as u,runpy,time,traceback,json
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
w=ed.get_editor_world();actors=u.get_editor_subsystem(u.EditorActorSubsystem)
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Transmission'
out.mkdir(parents=True,exist_ok=True)
r=runpy.run_path(str(Path(u.Paths.project_dir()).resolve()/'Tools/Oil/BottleMaterials.py'))
for a in actors.get_all_level_actors():
 if a.get_actor_label().startswith('OilTransmission'):actors.destroy_actor(a)
bottle=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewBottle')
cam=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewCamera')
c=cam.get_component_by_class(u.SceneCaptureComponent2D)
base=bottle.get_actor_location();eye=base+u.Vector(36,-65,27);target=base+u.Vector(0,0,14)
cam.set_actor_location(eye,False,True);cam.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye,target),False)
c.fov_angle=24;c.texture_target=u.RenderingLibrary.create_render_target2d(w,1200,1200,u.TextureRenderTargetFormat.RTF_RGBA8)
liq=bottle.get_component_by_class(u.ProphecyOilLiquid)
material=r['build_liquid'](u.new_object(u.Material));liq.set_material(0,material)
card=actors.spawn_actor_from_class(u.StaticMeshActor,base+u.Vector(-3,5,16))
card.set_actor_label('OilTransmissionCard');card.set_actor_scale3d(u.Vector(.55,.002,.55));card.set_actor_rotation(u.Rotator(0,29,0),False)
cm=u.new_object(u.Material);cm.set_editor_property('shading_model',u.MaterialShadingModel.MSM_UNLIT)
uv=r['node'](cm,u.MaterialExpressionTextureCoordinate)
pattern=r['custom'](cm,'float k=fmod(floor(UV.x*10)+floor(UV.y*10),2); return lerp(float3(90,90,90),float3(240,240,240),k);',{'UV':uv},u.CustomMaterialOutputType.CMOT_FLOAT3)
r['wire'](pattern,u.MaterialProperty.MP_EMISSIVE_COLOR);r['compile'](cm)
sc=card.static_mesh_component;sc.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'));sc.set_material(0,cm);sc.set_cast_shadow(False);sc.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
s={'n':0,'i':0,'start':time.monotonic(),'refs':[material,cm,card]}
cases=['front-transmission','front-plain','oblique-transmission']
def setup():
 card.set_is_temporarily_hidden_in_editor(s['i']==1)
 if s['i']==2:
  eye=base+u.Vector(-40,-65,30);cam.set_actor_location(eye,False,True);cam.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye,target),False)
 c.capture_every_frame=True
def tick(_):
 try:
  if time.monotonic()-s['start']>120:raise TimeoutError('portrait')
  s['n']+=1
  if s['n']<40:return
  u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),cases[s['i']]+'.png')
  s['i']+=1;s['n']=0
  if s['i']<len(cases):setup();return
  c.capture_every_frame=False;card.set_is_temporarily_hidden_in_editor(True)
  u.unregister_slate_post_tick_callback(s['handle']);print('OIL_TRANSMISSION_PORTRAIT_DONE')
 except Exception:
  c.capture_every_frame=False;u.unregister_slate_post_tick_callback(s['handle']);(out/'error.txt').write_text(traceback.format_exc())
setup();s['handle']=u.register_slate_post_tick_callback(tick)

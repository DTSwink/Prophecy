"""Unsaved hero fixture; real raster capture under the saved studio lighting."""
import unreal as u,json,time,traceback
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
w=ed.get_editor_world();actors=u.get_editor_subsystem(u.EditorActorSubsystem)
for cmd in ['r.RefractionQuality 2','r.AntiAliasingMethod 2','r.PostProcessAAQuality 6','r.ScreenPercentage 100']:
 u.SystemLibrary.execute_console_command(w,cmd)
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Studio'
for a in actors.get_all_level_actors():
 if a.get_actor_label().startswith('StudioReview'):actors.destroy_actor(a)
base=u.Vector(-980,-380,.5)
a=actors.spawn_actor_from_class(u.load_asset('/Game/_mygame/OilBottle/BP_OilBottle').generated_class(),base)
a.set_actor_label('StudioReviewBottle');a.tags=['StudioReviewBottle'];a.launch_on_play=False
a.bottle.set_simulate_physics(False);a.bottle.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
a.get_component_by_class(u.ProphecyOilLiquid).refresh_liquid()
actual_liquid=a.get_component_by_class(u.ProphecyOilLiquid).get_material(0)
assert actual_liquid and actual_liquid.get_path_name()=='/Game/_mygame/OilBottle/Materials/M_OilBottleLiquid.M_OilBottleLiquid',str(actual_liquid)
eye=base+u.Vector(62,-42,31);target=base+u.Vector(0,0,14)
camera=actors.spawn_actor_from_class(u.SceneCapture2D,eye,u.MathLibrary.find_look_at_rotation(eye,target));camera.set_actor_label('StudioReviewCamera')
c=camera.get_component_by_class(u.SceneCaptureComponent2D)
c.capture_every_frame=True;c.capture_on_movement=False;c.always_persist_rendering_state=True
c.capture_source=u.SceneCaptureSource.SCS_FINAL_COLOR_LDR;c.fov_angle=24
c.set_editor_property('show_flag_settings',[u.EngineShowFlagsSetting(show_flag_name=n,enabled=True) for n in ['AntiAliasing','TemporalAA','SkyLighting','ReflectionEnvironment','Lighting','Specular']])
ps=c.post_process_settings
ps.override_reflection_method=True;ps.reflection_method=u.ReflectionMethod.SCREEN_SPACE
ps.override_dynamic_global_illumination_method=True;ps.dynamic_global_illumination_method=u.DynamicGlobalIlluminationMethod.NONE
ps.override_indirect_lighting_intensity=True;ps.indirect_lighting_intensity=1.
c.post_process_settings=ps;c.post_process_blend_weight=1.
c.texture_target=u.RenderingLibrary.create_render_target2d(w,1200,1200,u.TextureRenderTargetFormat.RTF_RGBA8)
photo={'n':0,'camera':camera,'capture':c,'bottle':a,'start':time.monotonic()}
def photograph(_):
 try:
  photo['n']+=1
  if photo['n']<40:return
  u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),'hero.png')
  c.capture_every_frame=False
  u.unregister_slate_post_tick_callback(photo['handle'])
  print('OIL_STUDIO_PHOTO_DONE')
 except Exception:
  u.unregister_slate_post_tick_callback(photo['handle']);(out/'photo-error.txt').write_text(traceback.format_exc())
photo['handle']=u.register_slate_post_tick_callback(photograph)

"""Glass-only isolation; the accepted liquid material and geometry stay fixed."""
import unreal as u,time,traceback,json
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
w=ed.get_editor_world();actors=u.get_editor_subsystem(u.EditorActorSubsystem)
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/GlassBase';out.mkdir(parents=True,exist_ok=True)
bottle=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewBottle')
cam=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewCamera')
c=cam.get_component_by_class(u.SceneCaptureComponent2D)
base=bottle.get_actor_location();eye=base+u.Vector(36,-65,27);target=base+u.Vector(0,0,14)
cam.set_actor_location(eye,False,True);cam.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye,target),False)
c.fov_angle=24;c.texture_target=u.RenderingLibrary.create_render_target2d(w,1200,1200,u.TextureRenderTargetFormat.RTF_RGBA8)
liquid=bottle.get_component_by_class(u.ProphecyOilLiquid);locked=liquid.get_material(0)
assert locked.get_path_name()=='/Game/_mygame/OilBottle/Materials/M_OilBottleLiquid.M_OilBottleLiquid'
original=bottle.bottle.get_material(0);mid=bottle.bottle.create_dynamic_material_instance(0)
cases=[('baseline',.01,.2,1),('no-refraction',0,.2,1),('glass-hidden',0,.2,0),('soft-edge',.01,0,1),('low-refraction',.001,.2,1)]
s={'n':0,'i':0,'start':time.monotonic(),'refs':[mid,original,locked]}
def setup():
 name,ref,edge,fade=cases[s['i']]
 for k,v in [('RefractionStrength',ref),('EdgeCoverage',edge),('FragmentOpacity',fade)]:mid.set_scalar_parameter_value(k,v)
 c.capture_every_frame=True
def tick(_):
 try:
  if time.monotonic()-s['start']>120:raise TimeoutError('glass base study')
  s['n']+=1
  if s['n']<40:return
  assert liquid.get_material(0)==locked
  u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),cases[s['i']][0]+'.png')
  s['i']+=1;s['n']=0
  if s['i']<len(cases):setup();return
  c.capture_every_frame=False;bottle.bottle.set_material(0,original)
  u.unregister_slate_post_tick_callback(s['handle']);print('OIL_GLASS_BASE_STUDY_DONE')
 except Exception:
  c.capture_every_frame=False;u.unregister_slate_post_tick_callback(s['handle']);(out/'error.txt').write_text(traceback.format_exc())
setup();s['handle']=u.register_slate_post_tick_callback(tick)

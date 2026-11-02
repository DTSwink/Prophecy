"""Apply the tested glass-only offset; preserve accepted liquid and all geometry."""
import unreal as u,json,hashlib,shutil,time,traceback
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
w=ed.get_editor_world();actors=u.get_editor_subsystem(u.EditorActorSubsystem)
root=Path(u.Paths.project_dir()).resolve();out=root/'Saved/Diagnostics/Oil/Bottle/GlassBase';out.mkdir(parents=True,exist_ok=True)
folder=root/'Content/_mygame/OilBottle'
protected=[folder/'Materials/M_OilBottleLiquid.uasset',folder/'Materials/M_OilBottleCork.uasset']+list((folder/'Meshes').glob('*.uasset'))+list((folder/'Debris').glob('*.uasset'))
def hashes():return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=hashes();source=folder/'Materials/M_OilBottleGlass.uasset'
if not (out/'before-glass.uasset').exists():shutil.copy2(source,out/'before-glass.uasset')
g=u.load_asset('/Game/_mygame/OilBottle/Materials/M_OilBottleGlass')
params=[o for o in u.ObjectIterator(u.MaterialExpressionScalarParameter) if o.get_outer()==g and str(o.get_editor_property('parameter_name'))=='RefractionStrength']
assert len(params)==1
previous=params[0].get_editor_property('default_value');params[0].set_editor_property('default_value',.001)
u.MaterialEditingLibrary.recompile_material(g);assert u.EditorAssetLibrary.save_loaded_asset(g,False)
assert hashes()==before
bottle=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewBottle')
bottle.bottle.set_material(0,g)
cam=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewCamera');c=cam.get_component_by_class(u.SceneCaptureComponent2D)
base=bottle.get_actor_location();target=base+u.Vector(0,0,14)
c.fov_angle=24;c.texture_target=u.RenderingLibrary.create_render_target2d(w,1200,1200,u.TextureRenderTargetFormat.RTF_RGBA8)
audit={'glass_refraction_before':previous,'glass_refraction_after':.001,'liquid_and_geometry_unchanged':True,'protected_sha256':before,'saved_assets':[g.get_path_name()],'map_saved':False,'native_build':False}
s={'n':0,'i':0,'start':time.monotonic()};angles=[('glass-base-fixed',(36,-65,27)),('glass-base-oblique',(-40,-65,35))]
def setup():
 eye=base+u.Vector(*angles[s['i']][1]);cam.set_actor_location(eye,False,True);cam.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye,target),False);c.capture_every_frame=True
def tick(_):
 try:
  if time.monotonic()-s['start']>90:raise TimeoutError('glass review')
  s['n']+=1
  if s['n']<40:return
  u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),angles[s['i']][0]+'.png')
  s['i']+=1;s['n']=0
  if s['i']<len(angles):setup();return
  assert hashes()==before
  c.capture_every_frame=False;u.unregister_slate_post_tick_callback(s['handle'])
  (out/'receipt.json').write_text(json.dumps(audit,indent=2));print('OIL_GLASS_BASE_FIXED')
 except Exception:
  c.capture_every_frame=False;u.unregister_slate_post_tick_callback(s['handle']);(out/'error.txt').write_text(traceback.format_exc())
setup();s['handle']=u.register_slate_post_tick_callback(tick)

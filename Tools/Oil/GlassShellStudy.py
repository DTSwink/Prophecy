"""Isolated source-vs-boolean-shell rendering; approved liquid stays unchanged."""
import unreal as u,json,time,traceback
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
w=ed.get_editor_world();actors=u.get_editor_subsystem(u.EditorActorSubsystem)
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Shell';out.mkdir(parents=True,exist_ok=True)
data=json.loads((out/'source.json').read_text());d=u.DynamicMesh();tri=data['triangles'];verts=data['vertices']
for slot in [0,1]:
 faces=[tri[i*3:i*3+3] for i,s in enumerate(data['slots']) if s==slot]
 used=sorted({j for f in faces for j in f});remap={v:i for i,v in enumerate(used)}
 buffers=u.GeometryScriptSimpleMeshBuffers(
  vertices=[u.Vector(*verts[i][:3]) for i in used],normals=[u.Vector(*verts[i][3:6]) for i in used],
  uv0=[u.Vector2D(*verts[i][6:8]) for i in used],triangles=[u.IntVector(*(remap[j] for j in f)) for f in faces])
 u.GeometryScript_MeshEdits.append_buffers_to_mesh(d,buffers,slot)
source='/Game/_mygame/OilBottle/Meshes/SM_OilBottle';path='/Game/_mygame/Tests/Oil/Studio/SM_FabSurfaceReview'
original=u.load_asset(source)
candidate=u.load_asset(path) if u.EditorAssetLibrary.does_asset_exist(path) else u.EditorAssetLibrary.duplicate_asset(source,path)
options=u.GeometryScriptCopyMeshToAssetOptions(enable_recompute_normals=False,enable_recompute_tangents=True,replace_materials=False)
_,result=u.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(d,candidate,options,u.GeometryScriptMeshWriteLOD());assert result==u.GeometryScriptOutcomePins.SUCCESS
bottle=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewBottle')
liquid=bottle.get_component_by_class(u.ProphecyOilLiquid);locked=liquid.get_material(0)
cam=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewCamera');c=cam.get_component_by_class(u.SceneCaptureComponent2D)
base=bottle.get_actor_location();eye=base+u.Vector(36,-65,27);target=base+u.Vector(0,0,14)
cam.set_actor_location(eye,False,True);cam.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye,target),False)
c.fov_angle=24;c.texture_target=u.RenderingLibrary.create_render_target2d(w,1200,1200,u.TextureRenderTargetFormat.RTF_RGBA8)
cases=[('added-shell',original,True),('fab-surface',candidate,True),('fab-empty',candidate,False),('added-empty',original,False)]
s={'n':0,'i':0,'start':time.monotonic(),'refs':[d,candidate,original,locked]}
def setup():
 _,mesh,visible=cases[s['i']];bottle.bottle.set_static_mesh(mesh);liquid.set_visibility(visible);c.capture_every_frame=True
def tick(_):
 try:
  if time.monotonic()-s['start']>120:raise TimeoutError('shell study')
  s['n']+=1
  if s['n']<40:return
  assert liquid.get_material(0)==locked
  u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),cases[s['i']][0]+'.png')
  s['i']+=1;s['n']=0
  if s['i']<len(cases):setup();return
  c.capture_every_frame=False;liquid.set_visibility(True);bottle.bottle.set_static_mesh(original)
  u.unregister_slate_post_tick_callback(s['handle']);print('OIL_SHELL_STUDY_DONE',d.get_triangle_count())
 except Exception:
  c.capture_every_frame=False;u.unregister_slate_post_tick_callback(s['handle']);(out/'error.txt').write_text(traceback.format_exc())
setup();s['handle']=u.register_slate_post_tick_callback(tick)

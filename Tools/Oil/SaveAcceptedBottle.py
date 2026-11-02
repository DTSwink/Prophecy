"""Promote the accepted isolated glass study and shoulder-height fill. One-shot migration."""
import unreal as u,json,hashlib,shutil
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
assert 'M_OilTest' in ed.get_editor_world().get_path_name()
root=Path(u.Paths.project_dir()).resolve();content=root/'Content'
out=root/'Saved/Diagnostics/Oil/Bottle/ShoulderFill';out.mkdir(parents=True,exist_ok=True)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
protected=[content/'_mygame/OilBottle/Materials'/n for n in ['M_OilBottleLiquid.uasset','M_OilBottleCork.uasset']]
protected+=list((content/'_mygame/OilBottle/Debris').glob('*.uasset'))
before={str(p.relative_to(content)):digest(p) for p in protected}
for rel in ['_mygame/OilBottle/Materials/M_OilBottleGlass.uasset','_mygame/OilBottle/Meshes/SM_OilBottle.uasset','_mygame/Tests/Oil/M_OilTest.umap','_mygame/Tests/Oil/Studio/T_OilStudio.uasset']:
 p=content/rel;backup=out/('before-'+p.name)
 if p.exists() and not backup.exists():shutil.copy2(p,backup)
g=u.load_asset('/Game/_mygame/OilBottle/Materials/M_OilBottleGlass')
values={'Specular':.5,'Roughness':.12,'Opacity':.02,'EdgeCoverage':1.,'RefractionStrength':.004}
found=set()
for e in u.ObjectIterator(u.MaterialExpressionScalarParameter):
 if e.get_outer()!=g:continue
 name=str(e.get_editor_property('parameter_name'))
 if name in values:e.set_editor_property('default_value',values[name]);found.add(name)
assert found==set(values)
u.MaterialEditingLibrary.recompile_material(g)
mesh=u.load_asset('/Game/_mygame/OilBottle/Meshes/SM_OilBottle')
body=mesh.get_editor_property('body_setup');collision=body.get_editor_property('agg_geom').export_text()
slots=[m.material_interface.get_path_name() for m in mesh.get_editor_property('static_materials')]
data=json.loads((root/'Saved/Diagnostics/Oil/Bottle/Shell/source.json').read_text())
d=u.DynamicMesh();tri=data['triangles'];verts=data['vertices']
for slot in [0,1]:
 faces=[tri[i*3:i*3+3] for i,s in enumerate(data['slots']) if s==slot]
 used=sorted({j for f in faces for j in f});remap={v:i for i,v in enumerate(used)}
 buffers=u.GeometryScriptSimpleMeshBuffers(vertices=[u.Vector(*verts[i][:3]) for i in used],normals=[u.Vector(*verts[i][3:6]) for i in used],uv0=[u.Vector2D(*verts[i][6:8]) for i in used],triangles=[u.IntVector(*(remap[j] for j in f)) for f in faces])
 u.GeometryScript_MeshEdits.append_buffers_to_mesh(d,buffers,slot)
options=u.GeometryScriptCopyMeshToAssetOptions(enable_recompute_normals=False,enable_recompute_tangents=True,replace_materials=False)
_,result=u.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(d,mesh,options,u.GeometryScriptMeshWriteLOD())
assert result==u.GeometryScriptOutcomePins.SUCCESS and d.get_triangle_count()==3034
assert collision==mesh.get_editor_property('body_setup').get_editor_property('agg_geom').export_text()
assert slots==[m.material_interface.get_path_name() for m in mesh.get_editor_property('static_materials')]
u.EditorAssetLibrary.set_metadata_tag(mesh,'OilIntactSurface','FabOriginal1')
u.EditorAssetLibrary.set_metadata_tag(mesh,'OilWindingVersion','UE-CW-1')
task=u.AssetImportTask();task.filename=str(root/'Tools/Oil/Source/OilStudio.hdr')
task.destination_path='/Game/_mygame/Tests/Oil/Studio';task.destination_name='T_OilStudio';task.automated=True;task.replace_existing=True;task.save=False
u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
cube=u.load_asset('/Game/_mygame/Tests/Oil/Studio/T_OilStudio');assert cube
u.SystemLibrary.execute_console_command(ed.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
for obj in [g,mesh,cube]:assert u.EditorAssetLibrary.save_loaded_asset(obj,False)
# Discard study fixtures and temporary launch/physics edits; reload the saved test map.
levels=u.get_editor_subsystem(u.LevelEditorSubsystem);assert levels.load_level('/Game/_mygame/Tests/Oil/M_OilTest')
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
for a in actors.get_all_level_actors():
 if isinstance(a,(u.SkyLight,u.SphereReflectionCapture)):actors.destroy_actor(a)
sky=actors.spawn_actor_from_class(u.SkyLight,u.Vector(0,0,0));sky.set_actor_label('SkyLight')
sc=sky.light_component;sc.set_mobility(u.ComponentMobility.MOVABLE)
sc.set_editor_property('source_type',u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP);sc.set_cubemap(cube);sc.set_intensity(1000)
for key,value in {'source_cubemap_angle':270.,'lower_hemisphere_is_black':False,'real_time_capture':False,'cast_raytraced_shadow':u.CastRayTracedShadow.DISABLED,'affect_global_illumination':False,'affect_reflection':True}.items():sc.set_editor_property(key,value)
sc.set_indirect_lighting_intensity(1.);sc.recapture_sky()
bottles=[]
for a in actors.get_all_level_actors():
 if isinstance(a,u.ProphecyOilBottle):
  liq=a.get_component_by_class(u.ProphecyOilLiquid)
  bottles.append({'actor':a.get_actor_label(),'old_fill':liq.fill_amount,'launch':a.launch_on_play,'break':a.break_on_hit})
  liq.set_editor_property('fill_amount',.85);liq.refresh_liquid()
  a.modify();liq.modify()
assert bottles
assert levels.save_current_level()
after={str(p.relative_to(content)):digest(p) for p in protected};assert before==after
receipt={'fill':.85,'upright_height_cm':18.394,'glass':values,'original_fab_triangles':3034,'collision_unchanged':True,'protected_assets':after,'map_bottles':bottles,'saved':True}
(out/'saved.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('OIL_ACCEPTED_SAVED',json.dumps(receipt))

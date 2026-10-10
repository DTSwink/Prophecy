import unreal,pathlib,json,shutil
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SwordDraw20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(out.parent/'SwordThigh/BlueprintGraph.txt',out/'graph-before.txt')
rows=[]
for a in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.ProphecyAgent):
 row={'actor':a.get_path_name(),'components':[]}
 for c in a.get_components_by_class(unreal.SceneComponent):
  r={'name':c.get_name(),'class':c.get_class().get_name(),'parent':str(c.get_attach_parent()),'relative':str(c.get_relative_transform()),'world':str(c.get_world_transform())}
  if isinstance(c,unreal.ChildActorComponent):
   ch=c.get_editor_property('child_actor');r['child']=str(ch)
   if ch:r['child_components']=[{'name':x.get_name(),'world':str(x.get_world_transform()),'mesh':str(x.get_editor_property('static_mesh')) if isinstance(x,unreal.StaticMeshComponent) else ''} for x in ch.get_components_by_class(unreal.SceneComponent)]
  if isinstance(c,unreal.StaticMeshComponent):r['mesh']=str(c.get_editor_property('static_mesh'))
  row['components'].append(r)
 rows.append(row)
result={'play':bool(ed.get_game_world()),'dirty':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],'agents':rows}
(out/'before.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))


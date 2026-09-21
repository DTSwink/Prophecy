import unreal,json,pathlib
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=sub.get_game_world() or sub.get_editor_world()
rows=[]
for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent):
    rows.append({'actor':a.get_path_name(),'class':a.get_class().get_path_name(),
      'components':[{'name':c.get_name(),'class':c.get_class().get_path_name()} for c in a.get_components_by_class(unreal.SkeletalMeshComponent)]})
result={'pie':bool(sub.get_game_world()),'actors':rows,
 'dirty':[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]}
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/ForceNodes'
out.mkdir(parents=True,exist_ok=True)
(out/'inspection.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))

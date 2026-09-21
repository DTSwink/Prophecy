import unreal,json,pathlib
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=sub.get_game_world() or sub.get_editor_world()
rows=[]
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    row={'name':a.get_name(),'properties':{}}
    for name in ['Bool Codex','BoolCodex','bool_codex','bool codex','bBoolCodex']:
        try:row['properties'][name]=a.get_editor_property(name)
        except Exception as e:row['properties'][name]=str(e)
    rows.append(row)
r={'pie':bool(sub.get_game_world()),'actors':rows,'dirty':[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]}
print(json.dumps(r,indent=2))
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/WideWrist/bool_inspection.json').write_text(json.dumps(r,indent=2))

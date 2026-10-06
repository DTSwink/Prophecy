import unreal,json,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'DefenseIntegration/CheckpointUpdates/Parry1149700-20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
playing=ed.get_game_world() is not None
d={'play':playing,'world':ed.get_editor_world().get_path_name(),
   'dirty_content':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
   'dirty_maps':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
(p/'editor-state.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
if not playing:
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.Defense.CheckpointUpdate20261005')
 print('INSTALLED_MODEL_NATIVE_TEST_REQUESTED')

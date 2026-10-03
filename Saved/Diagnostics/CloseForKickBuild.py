import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Unexpected active Play'
world=ed.get_editor_world()
bp=unreal.load_object(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
# The relevant Blueprint still reports dirty after the user's saved/restart reply.
# Preserve that exact editor copy before the authorized close; leave unrelated assets alone.
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True),'Could not preserve pose BP'
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not dirty,[p.get_path_name() for p in dirty]
p=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/KickBuildEditorState.json')
p.write_text(json.dumps({'map':world.get_path_name().split('.')[0]},indent=2))
print('REOPEN',world.get_path_name())
unreal.SystemLibrary.execute_console_command(world,'QUIT_EDITOR')

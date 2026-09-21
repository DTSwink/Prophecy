import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
p='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
a=unreal.EditorAssetLibrary.load_asset(p)
print(json.dumps({'play':bool(ed.get_game_world()),'blueprint':a.get_path_name() if a else None,'dirty':[x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]},indent=2))

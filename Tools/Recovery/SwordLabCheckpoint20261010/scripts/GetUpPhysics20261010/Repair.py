import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
exec(compile((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/GetUpPhysics20261010/VerifyReload.py').read_text(encoding='utf-8'),'VerifyReload.py','exec'))
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True)

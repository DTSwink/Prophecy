import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve Play'
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
report=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in report and 'native_properties=0' in report and 'pin_types=0' in report,report
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True)
print('PELVIS_ONLY_BLUEPRINT_SAVED')

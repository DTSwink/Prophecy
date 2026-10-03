import unreal,pathlib,json,gc
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve Play'
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
capture=json.loads((folder/'FootEntryInertia-runtime.json').read_text())
assert capture['reason']=='Complete'
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
report=(folder/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in report and 'native_properties=0' in report and 'pin_types=0' in report,report
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True)
gc.collect()
unreal.SystemLibrary.collect_garbage()
print('FOOT_ENTRY_BLUEPRINT_SAVED_AND_VERIFIED',len(capture['rows']))

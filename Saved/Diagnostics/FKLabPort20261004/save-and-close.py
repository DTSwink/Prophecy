import unreal,json,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FKLabPort20261004'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
assert json.loads((p/'graph-verification.json').read_text())['verified']
scene=json.loads((p/'scene.json').read_text());assert scene['error']=='' and scene['pose_samples']==450
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
report=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in report and 'native_properties=0 pin_types=0' in report,report
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(),'Unexpected dirty map: preserve it'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(),'Unexpected dirty content: preserve it'
(p/'save-receipt.json').write_text(json.dumps({'saved':bp.get_path_name(),'map_saved':False,'compile':report},indent=2))
unreal.SystemLibrary.quit_editor()

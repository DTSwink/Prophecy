import json, pathlib, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
root=pathlib.Path(unreal.Paths.project_dir()).resolve()
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert bp
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
audit=root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt'
before=audit.read_bytes()
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
inspection=(root/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in inspection and 'native_properties=0 pin_types=0' in inspection,inspection
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
assert before==audit.read_bytes(),'Graph changed during compile/save'
receipt={'saved':bp.get_path_name(),'graph_unchanged':True,'inspection':inspection,
 'dirty_content':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
 'dirty_maps':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
(root/'Saved/Diagnostics/NNEntry20261003/save-for-push.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))

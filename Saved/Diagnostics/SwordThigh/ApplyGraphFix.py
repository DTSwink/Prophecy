import unreal,pathlib,builtins,re
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
path='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
dirty=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
assert path not in dirty,'User edits became unsaved; preserve them before saving the repair.'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.RepairAttachedCollisionGraph')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
raw=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes()
report=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
assert re.search(r'K2Node_CallFunction_110 \| Set Collision Response to All Channels\n  execute=[^\n]*\n  then= None -> K2Node_CallFunction_\d+\.execute',report)
assert unreal.EditorAssetLibrary.save_asset(path,only_if_is_dirty=True)
builtins._sword_thigh_force_block=False
print('Saved the attached-sword PhysicsBody Block override.')

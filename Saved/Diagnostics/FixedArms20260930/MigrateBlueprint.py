import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RemoveArmLeeway')
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FixedArms20260930/BlueprintMigration.txt'
assert p.exists(),'Migration command unavailable'
text=p.read_text(encoding='utf-16') if p.read_bytes().startswith(b'\xff\xfe') else p.read_text()
print(text)
assert 'connections_ok=1 status=3' in text,'Blueprint migration must compile before saving'
assert unreal.EditorAssetLibrary.save_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent',only_if_is_dirty=False)
print('MIGRATED_BLUEPRINT_SAVED')
print('DIRTY_CONTENT',[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
print('DIRTY_MAPS',[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])

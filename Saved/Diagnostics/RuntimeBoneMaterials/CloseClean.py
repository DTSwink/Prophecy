import unreal,pathlib
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RuntimeBoneMaterials'
log=(pathlib.Path(unreal.Paths.project_saved_dir())/'Logs/GameAnimationSample3.log').read_text(encoding='utf-8',errors='replace')
(root/'LiveCoding.log').write_text(log[log.rfind('Requested Live Coding compile'):],encoding='utf-8')
print('No unsaved packages or PIE; closing for authorized ordinary build.')
unreal.SystemLibrary.execute_console_command(
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(),
    'CLOSE_SLATE_MAINFRAME')

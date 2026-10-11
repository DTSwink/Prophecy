"""Layout-safe implementation patch; refuses Play or unexpected dirty assets."""
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Existing Play is left untouched.'
assert not list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), 'Preserve unexpected edits before compilation.'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.CompileSync')
print('OVERNIGHT_COMPILE_RETURNED')

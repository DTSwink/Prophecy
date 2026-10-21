"""Layout-safe implementation reload and focused rectangle regression."""
import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
print("INJURY_PROJECTION_PATCH_BEGIN")
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "LiveCoding.CompileSync")
print("INJURY_PROJECTION_PATCH_RETURNED")

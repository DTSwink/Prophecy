"""Layout-safe native implementation reload; no Blueprint or asset writes."""
import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play is active; stop before applying a native patch"
print("SKELETON_PENETRATION_PATCH_BEGIN")
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "LiveCoding.CompileSync")
print("SKELETON_PENETRATION_PATCH_RETURNED")

"""Authorized memory release. Refuses to discard unsaved work or active Play."""
import unreal

sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if sub.get_game_world():
    raise RuntimeError("Active Play; not closing it.")
dirty = (unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
         + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
if dirty:
    raise RuntimeError("Unsaved packages; preserve them before closing: " + str([p.get_name() for p in dirty]))
unreal.SystemLibrary.quit_editor()

"""Run through Saved/RunUnrealRemote.py after an authorized editor restart.

Reject unsaved work and PIE. Use the Slate close path: quit_editor() bypasses
BroadcastEditorClose in UE 5.7.4 and can destroy FSimpleAssetEditor after its
UImportSubsystem is gone (shutdown crash captured on 2026-09-11).
"""
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world():
    raise RuntimeError("Stop PIE before restarting Unreal.")
dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
dirty += list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
if dirty:
    raise RuntimeError("Save your edits before restarting: " + ", ".join(p.get_path_name() for p in dirty))

print("No unsaved packages or PIE; requesting normal Slate editor shutdown.")
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), "CLOSE_SLATE_MAINFRAME")

"""Run the current lab oracle and warm controller benchmark without opening Automation UI."""
import pathlib
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'An existing Play session is left untouched.'
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Sword.VerifyAuthored')
out = pathlib.Path(unreal.Paths.project_dir()) / 'Saved/Diagnostics/SwordPort20261012'
print((out / 'authored-result.txt').read_text(encoding='utf-8-sig'))

import pathlib, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play session'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Prophecy.Editor.BuildGTAttackIdle')
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/GTAttackIdle20260930/BlueprintBuild.txt'
assert p.exists(), 'Editor builder did not run'
print(p.read_text())
assert 'links_ok=1 status=3' in p.read_text(), 'Blueprint compile/wiring failed'

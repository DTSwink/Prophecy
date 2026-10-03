import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RefreshFootLocomotionHandoff')
p=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/FootLocomotionHandoffPins.txt')
report=p.read_text(encoding='utf-8-sig');print(report)
assert 'status=3 ' in report and 'values_and_links_preserved=1' in report and 'new_defaults_correct=1' in report,report

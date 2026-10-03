import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Repair')
p=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LiveAgentTypes-Repair.txt')
print(p.read_text(encoding='utf-8-sig').splitlines()[-1])
unreal.SystemLibrary.execute_console_command(w,'obj list class=Enum name=EProphecyNNInterpolationMode')
unreal.SystemLibrary.execute_console_command(w,'obj dump name=/Script/GameAnimationSample3.EProphecyNNInterpolationMode')
e=unreal.load_object(None,'/Script/GameAnimationSample3.EProphecyNNInterpolationMode')
print('ENUM',e,'VALUES',list(unreal.get_type_from_enum(e)))

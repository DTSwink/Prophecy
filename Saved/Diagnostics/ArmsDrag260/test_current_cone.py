import unreal,re,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
s=(pathlib.Path(unreal.Paths.project_dir())/'Source/GameAnimationSample3/Private/ProphecyArmConeLibrary.cpp').read_text()
names=re.findall(r'IMPLEMENT_SIMPLE_AUTOMATION_TEST\([^,]+,"([^"]+)"',s)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests '+'+'.join(names))
print('Requested',len(names),'current cone tests; excluded stale Live Coding registrations')

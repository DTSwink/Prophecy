import unreal,pathlib,json,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Do not alter test cadence during PIE'
path=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CompilerEditorIdleCap.json'
world=ed.get_editor_world()
if len(sys.argv)>1 and sys.argv[1]=='restore':
    if path.exists():
        before=json.loads(path.read_text())['before']
        current=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
        if current==10:unreal.SystemLibrary.execute_console_command(world,'t.MaxFPS '+str(before))
        path.unlink()
        print('Restored editor frame cap',before)
else:
    if not path.exists():
        before=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
        path.write_text(json.dumps({'before':before}))
        unreal.SystemLibrary.execute_console_command(world,'t.MaxFPS 10')
        print('Temporary idle editor cap 10; saved previous',before)

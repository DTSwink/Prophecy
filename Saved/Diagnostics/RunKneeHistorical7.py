import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'RunKneeHistorical20.py').read_text(encoding='utf-8').replace('KneePlane 20','KneePlane 5').replace('KneeHistorical20','KneeHistorical7').replace('knee_historical20','knee_historical7')
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.KneeReference 1')
src=src.replace("KneePlane 3')", "KneePlane 3');unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Recovery.KneeReference 0')")
exec(compile(src,str(p/'RunKneeHistorical20.py'),'exec'),{'__name__':'knee_historical7'})

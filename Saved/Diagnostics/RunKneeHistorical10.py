import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(p/'RunKneeHistorical7.py').read_text(encoding='utf-8').replace('KneePlane 5','KneePlane 8').replace('KneeHistorical7','KneeHistorical10').replace('knee_historical7','knee_historical10')
src=src.replace('KneeReference 1','KneeReference 0')
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.CleanSource 1')
src=src.replace("KneePlane 3')", "KneePlane 3');unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Recovery.CleanSource 0')")
exec(compile(src,str(p/'RunKneeHistorical7.py'),'exec'),{'__name__':'knee_historical10'})

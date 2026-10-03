import unreal,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
for command in ('Prophecy.Tempering.KneePlane 3','Prophecy.Recovery.CleanSource 1','Prophecy.Tempering.RaisedSource 1'):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),command)
src=(p/'CaptureSimFootFinal.py').read_text(encoding='utf-8').replace('SimFootFinal','KneeRaisedSource').replace('_sim_foot_final','_knee_raised_source')
src=src.replace('clock>=99999','clock>=20').replace('NNInputTraceFrames 480','NNInputTraceFrames 2200').replace('clock>=1600','clock>=950')
src=src.replace("unreal.unregister_slate_post_tick_callback(s['cb'])","unreal.unregister_slate_post_tick_callback(s['cb'])\n unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Tempering.RaisedSource 0')")
exec(compile(src,str(p/'CaptureSimFootFinal.py'),'exec'),{'__name__':'knee_raised_source'})

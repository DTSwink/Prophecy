import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=int(sys.argv[1]);tag='HarnessKnee'+str(mode)
for command in ('Prophecy.Tempering.KneePlane 3','Prophecy.Recovery.CleanSource 1','Prophecy.Tempering.HarnessKnee '+str(mode)):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),command)
src=(p/'CaptureSimFootFinal.py').read_text(encoding='utf-8').replace('SimFootFinal',tag).replace('_sim_foot_final','_harness_knee_'+str(mode))
src=src.replace('clock>=99999','clock>=20').replace('NNInputTraceFrames 480','NNInputTraceFrames 2200').replace('clock>=1600','clock>=950')
src=src.replace("unreal.unregister_slate_post_tick_callback(s['cb'])","unreal.unregister_slate_post_tick_callback(s['cb'])\n unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Tempering.HarnessKnee 0')")
exec(compile(src,str(p/'CaptureSimFootFinal.py'),'exec'),{'__name__':'harness_knee_trial'})

import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
mode=int(sys.argv[1]);sys.argv=['capture','harness-knee-variants-'+str(mode)]
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.HarnessKnee '+str(mode))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.CleanSource 1')
src=(p/'CaptureSupportFollowVariants.py').read_text(encoding='utf-8')
src=src.replace("unreal.unregister_slate_post_tick_callback(s['h'])","unreal.unregister_slate_post_tick_callback(s['h'])\n    unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Tempering.HarnessKnee 0')")
exec(compile(src,str(p/'CaptureSupportFollowVariants.py'),'exec'),{'__name__':'harness_knee_variants'})

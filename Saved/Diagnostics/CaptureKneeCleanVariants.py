import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
mode=int(sys.argv[1]);sys.argv=['capture','knee-clean-variants-'+str(mode)]
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.CleanSource '+str(mode))
src=(p/'CaptureSupportFollowVariants.py').read_text(encoding='utf-8')
src=src.replace("unreal.unregister_slate_post_tick_callback(s['h'])","unreal.unregister_slate_post_tick_callback(s['h'])\n    unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Recovery.CleanSource 1')")
exec(compile(src,str(p/'CaptureSupportFollowVariants.py'),'exec'),{'__name__':'knee_clean_variants'})

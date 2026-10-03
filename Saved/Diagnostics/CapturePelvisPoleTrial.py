import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics';ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'paired';start=320 if mode=='paired' else 1
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.PolePresentation 0')
src=(p/'CaptureSimFootFinal.py').read_text().replace('clock>=99999','clock>=300').replace('clock>=1600','clock>=520').replace('SimFootFinal','PelvisPoleTrial-'+mode)
src=src.replace('  if clock>=20:',"  if clock>="+str(start)+" and not s.get('switched'):\n   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Recovery.PolePresentation 1');s['switched']=True\n  if clock>=20:")
src=src.replace(" unreal.unregister_slate_post_tick_callback(s['cb'])"," unreal.unregister_slate_post_tick_callback(s['cb'])\n unreal.SystemLibrary.execute_console_command(ed.get_game_world() or w0,'Prophecy.Recovery.PolePresentation 0')")
exec(compile(src,'CapturePelvisPoleTrial','exec'))

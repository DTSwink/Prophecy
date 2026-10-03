import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics';ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1];names={'pole':'Prophecy.Tempering.PoleSmoothing','source':'Prophecy.Recovery.CleanSource','length':'Prophecy.Recovery.LocomotionLengthTarget','support':'Prophecy.Tempering.SupportSource'}
n=names[mode]
src=(p/'CaptureSimFootFinal.py').read_text().replace('clock>=99999','clock>=300').replace('clock>=1600','clock>=440').replace('SimFootFinal','PelvisAblation-'+mode)
src=src.replace('  if clock>=20:',"  if clock>=320 and not s.get('switched'):\n   unreal.SystemLibrary.execute_console_command(w,"+repr(n+' 0')+");s['switched']=True\n  if clock>=20:")
src=src.replace(" unreal.unregister_slate_post_tick_callback(s['cb'])"," unreal.unregister_slate_post_tick_callback(s['cb'])\n unreal.SystemLibrary.execute_console_command(ed.get_game_world() or w0,"+repr(n+' 1')+")")
exec(compile(src,'CapturePelvisAblation','exec'))

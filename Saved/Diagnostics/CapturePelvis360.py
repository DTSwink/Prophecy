import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
switch=int(sys.argv[2]) if len(sys.argv)>2 else 0
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.CleanSource '+('1' if mode=='clean' else '0'))
src=(p/'CaptureSimFootFinal.py').read_text().replace('clock>=99999','clock>=340').replace('clock>=1600','clock>=390').replace('SimFootFinal','Pelvis360-'+mode)
src=src.replace("unreal.unregister_slate_post_tick_callback(s['cb'])", "unreal.unregister_slate_post_tick_callback(s['cb'])\n unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.CleanSource 1')")
if switch:
 src=src.replace("  if clock>=20:","  if clock=="+str(switch)+":unreal.SystemLibrary.execute_console_command(w,'Prophecy.Recovery.CleanSource 1')\n  if clock>=20:")
exec(compile(src,'CapturePelvis360','exec'))

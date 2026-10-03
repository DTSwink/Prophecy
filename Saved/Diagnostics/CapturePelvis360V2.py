import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics';ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'final';switch=int(sys.argv[2]) if len(sys.argv)>2 else 0
for n in ('Prophecy.Recovery.CleanSource','Prophecy.Recovery.PoleWindow','Prophecy.Recovery.LocomotionLengthTarget'):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),n+' '+('1' if mode=='final' else '0'))
src=(p/'CaptureSimFootFinal.py').read_text().replace('clock>=99999','clock>=340').replace('clock>=1600','clock>='+('600' if mode=='final' else '390')).replace('SimFootFinal','Pelvis360V2-'+mode)
src=src.replace("unreal.unregister_slate_post_tick_callback(s['cb'])", "unreal.unregister_slate_post_tick_callback(s['cb'])\n for n in ('Prophecy.Recovery.CleanSource','Prophecy.Recovery.PoleWindow','Prophecy.Recovery.LocomotionLengthTarget'):unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),n+' 1')")
if switch:
 names={'length':['Prophecy.Recovery.LocomotionLengthTarget'],'pole':['Prophecy.Recovery.PoleWindow'],'combined':['Prophecy.Recovery.CleanSource','Prophecy.Recovery.PoleWindow','Prophecy.Recovery.LocomotionLengthTarget']}[mode]
 src=src.replace("  if clock>=20:","  if clock=="+str(switch)+":\n   for n in "+repr(names)+":unreal.SystemLibrary.execute_console_command(w,n+' 1')\n  if clock>=20:")
exec(compile(src,'CapturePelvis360V2','exec'))

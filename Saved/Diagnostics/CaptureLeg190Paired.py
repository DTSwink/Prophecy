import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics';ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'paired'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.LengthInterpolation '+('0' if mode=='paired' else '1'))
src=(p/'CaptureSupportingKneeLead.py').read_text().replace('SupportingKneeLead-live','Leg190-'+mode).replace('>=360','>=300')
if mode=='paired':
 src=src.replace("   s['rows'].append(r)","   if 175<=r['tick']<=207:\n    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Recovery.LengthInterpolation 1')\n    r['fixed']={}\n    for b in bones:\n     target=a.get_authored_body_world_target(b)\n     if target:r['fixed'][b]=tr(target[2])\n    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Recovery.LengthInterpolation 0')\n   s['rows'].append(r)")
src=src.replace("print('SUPPORTING_KNEE_CAPTURE_DONE',reason,len(s['rows']))", "print('SUPPORTING_KNEE_CAPTURE_DONE',reason,len(s['rows']))\n unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.LengthInterpolation 1')")
exec(compile(src,'CaptureLeg190Paired','exec'))

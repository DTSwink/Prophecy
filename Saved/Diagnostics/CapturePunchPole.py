import unreal,pathlib,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
frames=int(sys.argv[2]) if len(sys.argv)>2 else 420
switch=int(sys.argv[3]) if len(sys.argv)>3 else 0
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
trace=p/'RecoveryPoleSmoothing.jsonl';trace.write_text('')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.PoleSmoothing '+('1' if mode.endswith('enabled') else '0'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.PoleTrace 2000')
src=(p/'CaptureSupportingKneeLead.py').read_text()
src=src.replace('SupportingKneeLead-live','PunchPole-'+mode+'-live').replace('>=360','>='+str(frames))
src=src.replace("print('SUPPORTING_KNEE_CAPTURE_DONE',reason,len(s['rows']))", "print('SUPPORTING_KNEE_CAPTURE_DONE',reason,len(s['rows']))\n unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.PoleTrace 0')\n unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.PoleSmoothing 1')\n (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PunchPole-"+mode+"-frozen.jsonl').write_text((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RecoveryPoleSmoothing.jsonl').read_text())")
if switch:
 src=src.replace("   r=dict(t=t", "   if int(a.get_editor_property('tick debug'))=="+str(switch)+":unreal.SystemLibrary.execute_console_command(w,'Prophecy.Tempering.PoleSmoothing 1')\n   r=dict(t=t")
if mode.startswith('kick'):
 src=src.replace("   r=dict(t=t", "   state=a.get_nn_attack_state()\n   if state and str(state[0]).lower()=='overr':\n    target=a.get_nn_attack_target()[0];victim=a.get_nn_attack_victim();side='kickL' if s.get('kicks',0)%2==0 else 'kickR';s['kicks']=s.get('kicks',0)+1\n    a.stop_nn_attack();assert a.trigger_nn_attack(side,target,False,victim)\n   r=dict(t=t")
exec(compile(src,'CapturePunchPole','exec'))


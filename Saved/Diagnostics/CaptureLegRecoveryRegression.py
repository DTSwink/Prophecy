import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics';ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'final';old=mode.endswith('old');frames=600
for n in ('Prophecy.Recovery.CleanSource','Prophecy.Recovery.PoleWindow','Prophecy.Recovery.LocomotionLengthTarget'):
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),n+' '+('0' if old else '1'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.PoleSmoothing 1')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.PoleTrace 2000')
(p/'RecoveryPoleSmoothing.jsonl').write_text('')
src=(p/'CaptureSupportingKneeLead.py').read_text().replace('SupportingKneeLead-live','LegRecovery-'+mode+'-live').replace('>=360','>='+str(frames))
src=src.replace("print('SUPPORTING_KNEE_CAPTURE_DONE',reason,len(s['rows']))", "print('SUPPORTING_KNEE_CAPTURE_DONE',reason,len(s['rows']))\n unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.PoleTrace 0')\n for n in ('Prophecy.Recovery.CleanSource','Prophecy.Recovery.PoleWindow','Prophecy.Recovery.LocomotionLengthTarget'):unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),n+' 1')\n (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LegRecovery-"+mode+"-frozen.jsonl').write_text((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RecoveryPoleSmoothing.jsonl').read_text())")
if mode.startswith('kicks'):
 src=src.replace("   r=dict(t=t", "   state=a.get_nn_attack_state()\n   if state and str(state[0]).lower()=='overr':\n    target=a.get_nn_attack_target()[0];victim=a.get_nn_attack_victim();side='kickL' if s.get('kicks',0)%2==0 else 'kickR';s['kicks']=s.get('kicks',0)+1\n    a.stop_nn_attack();assert a.trigger_nn_attack(side,target,False,victim)\n   r=dict(t=t")
exec(compile(src,'CaptureLegRecoveryRegression','exec'))

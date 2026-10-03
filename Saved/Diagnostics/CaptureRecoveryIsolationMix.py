import unreal,pathlib,sys
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics';ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'final'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.PolePresentation '+('0' if mode=='old' else '1'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.PoleTrace 6000')
(p/'RecoveryPoleSmoothing.jsonl').write_text('')
src=(p/'CaptureSimFootFinal.py').read_text().replace('clock>=1600','clock>=900').replace('SimFootFinal','RecoveryIsolationMix-'+mode)
src=src.replace("    a.set_foot_pinning_debug_enabled(True)","    state=a.get_nn_attack_state()\n    if state and state[4]==1 and clock-s.get('last_start',-100)>5:\n     s['last_start']=clock;sequence=['kickL','kickR','overL','overR','slashR','jabL','pike','hookL'];chosen=sequence[s.get('attack_number',0)%len(sequence)];s['attack_number']=s.get('attack_number',0)+1\n     if str(state[0]).lower()!=chosen.lower():\n      target=a.get_nn_attack_target()[0];victim=a.get_nn_attack_victim();a.stop_nn_attack();assert a.trigger_nn_attack(chosen,target,False,victim)\n    a.set_foot_pinning_debug_enabled(True)")
src=src.replace(" unreal.unregister_slate_post_tick_callback(s['cb'])"," unreal.unregister_slate_post_tick_callback(s['cb'])\n unreal.SystemLibrary.execute_console_command(ed.get_game_world() or w0,'Prophecy.Recovery.PolePresentation 1')\n unreal.SystemLibrary.execute_console_command(ed.get_game_world() or w0,'Prophecy.Tempering.PoleTrace 0')\n (folder/'RecoveryIsolationMix-"+mode+"-frozen.jsonl').write_text((folder/'RecoveryPoleSmoothing.jsonl').read_text())")
exec(compile(src,'CaptureRecoveryIsolationMix','exec'))

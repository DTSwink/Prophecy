import pathlib,unreal,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureKnee202.py').read_text().replace("tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'","tag='foot_jiggle_"+mode+"'").replace('clock>=175','clock>=999999').replace("s['frame']>=280","s['frame']>=205").replace('    a.set_foot_pinning_debug_enabled(True)','')
src=src.replace("   s['rows'].append(r)","   r['foot_owner']=str(unreal.ProphecyAttackFootLocomotionLibrary.get_attack_foot_locomotion(a))\n   r['body_states']={b:str(a.get_physical_body_state(b)) for b in ('foot_r','calf_r','thigh_r','pelvis')}\n   s['rows'].append(r)")
if mode=='trace':
 src=src.replace("   r=dict(t=t", "   if clock==160:unreal.SystemLibrary.execute_console_command(w,'Prophecy.PhysicalFoot.TraceFrames 60')\n   r=dict(t=t")
 src=src.replace("   s['rows'].append(r)","   if clock in (173,174):r['profiles']=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyPhysicalProfileLibrary')).call_method('PrintPhysicalBoneProfiles',(a,0.,unreal.LinearColor(1.,1.,1.,1.)))\n   s['rows'].append(r)")
 src=src.replace(" unreal.unregister_slate_post_tick_callback(s['cb'])", " unreal.unregister_slate_post_tick_callback(s['cb'])\n unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.PhysicalFoot.TraceFrames 0')")
if mode=='no_prediction':src=src.replace("   s['rows'].append(r)","   if clock==160:a.set_jolt_joint_limit_prediction_enabled(False)\n   s['rows'].append(r)")
if mode=='no_self':src=src.replace("   s['rows'].append(r)","   if clock==160:a.set_jolt_self_collision_enabled(False)\n   s['rows'].append(r)")
if mode=='no_limits':src=src.replace("   s['rows'].append(r)","   if clock==160:a.set_use_authored_angular_limits(False)\n   s['rows'].append(r)")
if mode=='no_calf_angular':src=src.replace("   s['rows'].append(r)","   if clock>=160:a.set_body_magnetization('calf_r',True,1.,0.)\n   s['rows'].append(r)")
exec(compile(src,'CaptureFootJiggle','exec'))

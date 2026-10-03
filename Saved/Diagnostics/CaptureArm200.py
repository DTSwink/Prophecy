import pathlib,sys,unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
wrapper=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='arm200_"+mode+"'").replace('clock>=140','clock>=999999').replace("s['frame']>=235","s['frame']>=245")
inject="""   if 170<=clock<=225:
    r['profiles']=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyPhysicalProfileLibrary')).call_method('PrintPhysicalBoneProfiles',(a,0.,unreal.LinearColor(1.,1.,1.,1.)))
    r['body_states']={b:str(a.get_physical_body_state(b)) for b in ('hand_r','lowerarm_r','upperarm_r')}
    r['prediction']=a.is_jolt_joint_limit_prediction_enabled()
"""
if mode=='no_self':inject+="   if clock==165:print('SELF_DISABLED',a.set_jolt_self_collision_enabled(False))\n"
if mode=='no_limits':inject+="   if clock==165:print('LIMITS_DISABLED',a.set_use_authored_angular_limits(False))\n"
if mode=='no_prediction':inject+="   if clock==165:a.set_jolt_joint_limit_prediction_enabled(False)\n"
if mode=='no_sword_collision':inject+="   if clock==165:unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordPhysicsLibrary')).call_method('SetSwordCollisionEnabled',(a,False))\n"
if mode=='no_arm_torso':inject+="   if clock==165:\n    for limb in ('upperarm_r','lowerarm_r','hand_r'):\n     for torso in ('pelvis','spine_01','spine_02','spine_03','spine_04','spine_05'):a.set_jolt_body_pair_self_collision_enabled(limb,torso,False)\n"
if mode=='no_grip':inject+="   if clock==165:print('GRIP_BROKEN',unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordPhysicsLibrary')).call_method('BreakSwordGripConstraint',(a,)))\n"
wrapper=wrapper.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\"   s['rows'].append(r)\",inject+\"   s['rows'].append(r)\")\nexec(compile(src,'CaptureHand180','exec'))")
exec(compile(wrapper,'Arm200','exec'))

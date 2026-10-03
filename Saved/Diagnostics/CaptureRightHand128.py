import pathlib,sys,unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
tag='right_hand128' if mode=='baseline' else 'right_hand128_'+mode
wrapper=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='"+tag+"'").replace('clock>=140','clock>=95').replace("s['frame']>=235","s['frame']>=165")
inject="""   if 95<=clock<=150:
    r['profiles']=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyPhysicalProfileLibrary')).call_method('PrintPhysicalBoneProfiles',(a,0.,unreal.LinearColor(1.,1.,1.,1.)))
"""
if mode=='no_arm_self':inject+="   if clock==95:\n    print('ARM_SELF_DISABLED',a.set_jolt_bodies_self_collision_enabled(['upperarm_r','lowerarm_r','hand_r'],False))\n"
if mode=='no_self':inject+="   if clock==95:\n    print('SELF_DISABLED',a.set_jolt_self_collision_enabled(False))\n"
if mode=='zero_forearm_leeway':inject+="   if clock>=95:\n    a.set_locomotion_forearm_clamp(True,0.)\n"
if mode=='no_hand_angular':inject+="   if 95<=clock<139:\n    a.set_body_magnetization('hand_r',True,1.,0.)\n"
if mode=='no_limit_prediction':inject+="   if clock==95:\n    a.set_jolt_joint_limit_prediction_enabled(False)\n"
if mode=='no_sword_collision':inject+="   if clock==95:\n    sword=a.get_held_sword()\n    assert sword\n    for blade in sword.get_components_by_class(unreal.StaticMeshComponent):blade.set_collision_response_to_all_channels(unreal.CollisionResponse.IGNORE)\n"
wrapper=wrapper.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\"   s['rows'].append(r)\",inject+\"   s['rows'].append(r)\")\nexec(compile(src,'CaptureHand180','exec'))")
exec(compile(wrapper,'RightHand128','exec'))

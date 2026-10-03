import pathlib,sys,unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
mode=sys.argv[1]
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
wrapper=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='hand180_"+mode+"'")
inject="""   if clock>=190:
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyHandRecoveryLibrary')).call_method('SetLocomotionHandTempering',(a,True,0.,0.,0.,0.,0.,0.))
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyCoreTemperingLibrary')).call_method('SetLocomotionFKCoreTempering',(a,True,0.))
"""
if mode=='zero_no_return':inject+="    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary')).call_method('SetSlashRightArmReturnToNeutral',(a,False,0.,0.,300.))\n"
if mode=='no_clamps':inject="   if clock>=190:\n    a.set_locomotion_forearm_clamp(False,0.)\n    a.set_locomotion_hand_clamp(False,0.)\n"
if mode=='isolated_exit':inject+="    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary')).call_method('SetAttackUpperBodyInertia',(a,False,.82,0.,.08,.69))\n    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary')).call_method('SetSlashRightArmReturnToNeutral',(a,False,0.,0.,300.))\n    a.set_locomotion_forearm_clamp(False,0.)\n    a.set_locomotion_hand_clamp(False,0.)\n"
wrapper=wrapper.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\"   r=dict(t=t\",inject+\"   r=dict(t=t\")\nexec(compile(src,'CaptureHand180','exec'))")
exec(compile(wrapper,'Hand180Ablation','exec'))

import pathlib,unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
wrapper=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='upper_inertia_isolated'")
inject="""   if clock==190:
    # Same outgoing sample as natural exit, one world tick before the next NN
    # update, allowing us to bypass the Blueprint callbacks before evaluation.
    a.stop_nn_attack()
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyHandRecoveryLibrary')).call_method('SetLocomotionHandTempering',(a,False,1.,1.,1.,1.,1.,1.))
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyCoreTemperingLibrary')).call_method('SetLocomotionFKCoreTempering',(a,False,1.))
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary')).call_method('SetSlashRightArmReturnToNeutral',(a,False,0.,0.,100.))
"""
wrapper=wrapper.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\"   r=dict(t=t\",inject+\"   r=dict(t=t\")\nexec(compile(src,'CaptureHand180','exec'))")
exec(compile(wrapper,'UpperInertiaIsolated','exec'))

import pathlib,sys,unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
wrapper=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='pike_elbow_"+mode+"'").replace("s['frame']>=235","s['frame']>=330")
inject=''
if mode=='no_inertia':
 inject="""   if clock>=140:
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary')).call_method('SetAttackUpperBodyInertia',(a,False,.25,0.,.5,1.,unreal.ProphecyUpperHandInertiaSpace.ROOT_LOCAL,1.))
"""
elif mode=='exit_no_inertia':
 inject="""   if clock==170:
    a.stop_nn_attack()
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary')).call_method('SetAttackUpperBodyInertia',(a,False,.25,0.,.5,1.,unreal.ProphecyUpperHandInertiaSpace.ROOT_LOCAL,1.))
"""
elif mode=='no_return':
 inject="""   if clock>=140:
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary')).call_method('SetSlashRightArmReturnToNeutral',(a,False,0.,0.,100.))
"""
wrapper=wrapper.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\"   r=dict(t=t\",inject+\"   r=dict(t=t\")\nexec(compile(src,'CaptureHand180','exec'))")
exec(compile(wrapper,'PikeElbowCurrent','exec'))


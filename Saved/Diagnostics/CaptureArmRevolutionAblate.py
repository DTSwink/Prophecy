import pathlib,sys,unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
mode=sys.argv[1]
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
wrapper=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='arm_revolution_"+mode+"'").replace("s['frame']>=235","s['frame']>=330")
if mode=='no_cone':
 inject="""   if clock>=188:
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmConeLibrary')).call_method('SetArmRepellantCone',(a,False,60.,1000000.,20.,10000.,.5))
"""
elif mode in ('no_inertia','exit_no_inertia'):
 inject="""   if clock>=188:
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary')).call_method('SetAttackUpperBodyInertia',(a,False,.25,0.,.5,1.,unreal.ProphecyUpperHandInertiaSpace.ROOT_LOCAL,1.))
"""
if mode=='exit_no_inertia':
 inject=inject.replace('if clock>=188:', 'if clock==188:\n    a.stop_nn_attack()')
wrapper=wrapper.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\"   r=dict(t=t\",inject+\"   r=dict(t=t\")\nexec(compile(src,'CaptureHand180','exec'))")
exec(compile(wrapper,'ArmRevolutionAblate','exec'))

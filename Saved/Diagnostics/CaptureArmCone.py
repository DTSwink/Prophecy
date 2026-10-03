import pathlib,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmConeLibrary'))
src=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='arm_cone_default'").replace('clock>=140','clock>=110').replace("s['frame']>=235","s['frame']>=260")
inject="""   if clock>=120 and not s.get('cone_configured'):
    assert lib.call_method('SetArmRepellantCone',(a,True,45.,100.,20.,.3,.5))
    assert lib.call_method('SetAttackArmRepellantConeEnabled',(a,False,True,False,False,False,False,False,False,False,False,False,False,False,False,False,False))
    s['cone_configured']=True
    print('ARM_CONE_CONFIGURED',clock,a.get_path_name(),a.is_actor_tick_enabled())
   if 185<=clock<=215:
    assert lib.call_method('VisualizeArmRepellantCone',(a,30.,0.))
"""
src=src.replace("exec(compile(src,'CaptureHand180','exec'))","src=src.replace(\"   r=dict(t=t,\",inject+\"   r=dict(t=t,\")\nsrc=src.replace(\" unreal.unregister_slate_post_tick_callback(s['cb'])\",\" unreal.unregister_slate_post_tick_callback(s['cb'])\\n unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.ArmCone.Audit 0')\")\nexec(compile(src,'CaptureHand180','exec'))")
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.ArmCone.Audit 1')
exec(compile(src,'CaptureArmCone','exec'))

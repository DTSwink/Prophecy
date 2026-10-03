import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
for name in ('SetArmRepellantCone','SetAttackArmRepellantConeEnabled','VisualizeArmRepellantCone'):
    fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyArmConeLibrary:'+name)
    assert fn,name+' is not reflected'
    print('ARM_CONE_NODE',fn.get_path_name())
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Physics.ArmCone')

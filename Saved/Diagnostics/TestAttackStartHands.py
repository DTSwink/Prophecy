import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
# These two native tests use their own temporary Editor world and agent. They
# neither start/stop PIE nor configure any actor in the user's current world.
print('ENTRY_HAND_TESTS_PRESERVE_PLAY',str(ed.get_game_world()))
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackStartInertiaLibrary'))
print('ENTRY_HAND_NODE_NULL_VALIDATION',lib.call_method('SetAttackStartHandInertia',(None,False,.1,.3,1.,.25,1.,1.,True,True)))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.AttackEntry.Hand')

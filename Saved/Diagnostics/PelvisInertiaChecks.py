import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
assert unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyPelvisInertiaLibrary')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
    'Automation RunTests Prophecy.NN.PelvisInertia+Prophecy.Jolt.Servo')

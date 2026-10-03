import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
checks=['FKCoreSpace','FKCoreClock','FKCoreBoundary','FKCoreNNSeed','FKCoreAttachment',
        'HandReference','HandLifecycle','FootInertia','PelvisRegression']
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests '+
    '+'.join('Prophecy.NN.AttackEntry.'+n for n in checks)+'+Prophecy.Jolt.Special.PhysicalStart')

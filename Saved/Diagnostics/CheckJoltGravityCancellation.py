import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests Prophecy.Jolt.Servo.GravityAndExternalForceAfterVelocityRewrite')
print('Requested isolated native gravity-cancellation regression; no map or PIE changes.')

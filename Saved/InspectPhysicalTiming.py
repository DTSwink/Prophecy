import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
for name in ['t.MaxFPS','t.IdleWhenNotForeground','Slate.bAllowThrottling','p.MaxPhysicsDeltaTime','p.MaxSubsteps','p.Substepping','p.AsyncPhysicsTickEnabled']:
 print('{}={}'.format(name, unreal.SystemLibrary.get_console_variable_string_value(name)))
print('world_dt={} dilation={}'.format(world.get_delta_seconds(), world.get_world_settings().get_editor_property('time_dilation')))

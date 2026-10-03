import unreal


physics = unreal.get_default_object(unreal.PhysicsSettings)
for name, value in (
        ("substepping", True),
        ("max_substep_delta_time", 1.0 / 60.0),
        ("max_substeps", 64),
        ("max_physics_delta_time", 1.0 / 60.0)):
    physics.set_editor_property(name, value)
    print("PHYSICS_TIME", name, physics.get_editor_property(name))

unreal.FixedFrameRateLibrary.set_fixed_frame_rate_runtime(60.0)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "t.MaxFPS 120")
print("FOLLOWER_TIME_CONFIGURED")

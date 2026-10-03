import unreal


physics = unreal.get_default_object(unreal.PhysicsSettings)
physics.set_editor_property("substepping", True)
physics.set_editor_property("max_substep_delta_time", 1.0 / 60.0)
physics.set_editor_property("max_substeps", 64)
physics.set_editor_property("max_physics_delta_time", 1.0 / 60.0)
unreal.FixedFrameRateLibrary.set_fixed_frame_rate_runtime(5.0)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "t.MaxFPS 5")
print("FOLLOWER_TIME_CONFIGURED_5FPS")

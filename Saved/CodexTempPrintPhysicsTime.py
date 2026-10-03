import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, "p.MaxPhysicsDeltaTime")
physics = unreal.get_default_object(unreal.PhysicsSettings)
for name in ("substepping", "max_substep_delta_time", "max_substeps", "max_physics_delta_time"):
    print("PHYSICS_TIME_READ", name, physics.get_editor_property(name))

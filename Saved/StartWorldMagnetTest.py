import unreal


subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if subsystem.is_in_play_in_editor():
    subsystem.editor_request_end_play()

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for command in (
        "t.IdleWhenNotForeground 0",
        "Slate.bAllowThrottling 0",
        "t.MaxFPS 60"):
    unreal.SystemLibrary.execute_console_command(world, command)
unreal.FixedFrameRateLibrary.set_fixed_frame_rate_runtime(60.0)
unreal.SystemLibrary.execute_console_command(world, "prophecy.Physical.LogTrackingError 0")
unreal.SystemLibrary.execute_console_command(world, "prophecy.Physical.LogPelvisError 0")
for manager in unreal.GameplayStatics.get_all_actors_of_class(
        world, unreal.ProphecyNNLocomotionManager):
    manager.set_editor_property("sim_bridge", False)
    manager.set_editor_property("crowd_size", 1)
    manager.set_editor_property("initial_physical_agent_count", 0)
    manager.set_editor_property("initial_physical_agents_use_macd", True)
    manager.set_editor_property("benchmark_seconds", 0.0)
subsystem.editor_request_begin_play()
print("WORLD_MAGNET_TEST_STARTED")

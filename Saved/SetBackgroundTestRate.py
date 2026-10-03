import unreal

world = unreal.EditorLevelLibrary.get_editor_world()
for command in (
    "t.IdleWhenNotForeground 0",
    "Slate.bAllowThrottling 0",
    "t.MaxFPS 60",
):
    unreal.SystemLibrary.execute_console_command(world, command)
unreal.FixedFrameRateLibrary.set_fixed_frame_rate_runtime(60.0)
print("BACKGROUND_TEST_RATE max_fps=60 idle=0 slate_throttle=0 editor_throttle=0")

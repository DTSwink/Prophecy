import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world: raise RuntimeError('No PIE')
unreal.SystemLibrary.execute_console_command(world,'t.MaxFPS 60')
unreal.FixedFrameRateLibrary.set_fixed_frame_rate_runtime(60.0)
print('FPS_SET_60')

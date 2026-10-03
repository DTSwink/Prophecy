import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    print("NO_GAME_WORLD")
else:
    print("time={} paused={} dilation={}".format(
        unreal.GameplayStatics.get_time_seconds(world),
        unreal.GameplayStatics.is_game_paused(world),
        unreal.GameplayStatics.get_global_time_dilation(world),
    ))

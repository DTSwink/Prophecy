import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
assert w
unreal.GameplayStatics.set_global_time_dilation(w,0.05)
unreal.GameplayStatics.set_game_paused(w,False)

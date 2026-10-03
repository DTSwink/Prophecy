import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
print('HALF_GHOST_PLAY',bool(w))
if w:
    a=unreal.GameplayStatics.get_player_pawn(w,0)
    print('HALF_GHOST_AGENT',a.get_path_name() if a else None)
    if isinstance(a,unreal.ProphecyAgent):
        print('HALF_GHOST_STATE',a.get_nn_attack_state())
print('HALF_GHOST_MAP',ed.get_editor_world().get_path_name())

import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
print('PLAY',w)
if w:
 a=unreal.GameplayStatics.get_player_pawn(w,0)
 print('AGENT',a,'TICK',a.get_editor_property('tick debug'))

import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
print('PIE_ACTIVE',bool(w))
if w:
 a=unreal.GameplayStatics.get_player_pawn(w,0)
 print('TICK',a.get_editor_property('tick debug'),'ATTACK',a.get_nn_attack_state(),'DRAG',unreal.ProphecyAttackFootLocomotionLibrary.get_attack_foot_locomotion(a),'WINDOW',unreal.ProphecyRootPhysicsLibrary.get_continuous_locomotion_root_window(a))

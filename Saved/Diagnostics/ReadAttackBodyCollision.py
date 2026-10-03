import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('ATTACK_COLLISION_BRIDGE', unreal.load_class(None, '/Script/ProphecyJolt.ProphecyJoltAttackCollisionLibrary'))
w = ed.get_game_world()
print('PLAY', bool(w))
if w:
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ProphecyAgent):
        print('AGENT', a.get_name(), 'ATTACK', a.get_nn_attack_state())
        for one, two in [('hand_r', 'head'), ('hand_l', 'head'), ('foot_r', 'foot_l')]:
            print('PAIR', one, two, a.get_jolt_body_pair_self_collision_enabled(one, two))

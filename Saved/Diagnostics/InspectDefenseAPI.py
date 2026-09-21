import unreal
for owner,names in [(unreal.ProphecyNNDefenseLibrary,['start_nn_parry','get_nn_defense_status']),
                    (unreal.ProphecyAgent,['get_nn_attack_state','read_nn_future_world_pose','get_authored_body_world_target'])]:
    for name in names: print(name,getattr(owner,name).__doc__)

import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
agents=unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
for a in agents:
 m=a.get_agent_mesh(); p=m.get_socket_transform('pelvis', unreal.RelativeTransformSpace.RTS_WORLD)
 print('SNAP name={} mode={} actor={} mesh={} pelvis={} vel={}'.format(a.get_name(),a.get_simulation_mode(),a.get_actor_location(),m.get_world_location(),p.translation,m.get_physics_linear_velocity('pelvis')))

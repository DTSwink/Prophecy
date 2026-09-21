import unreal
print(unreal.ProphecyAgent.get_physical_body_state.__doc__)
print(unreal.ProphecyAgent.get_jolt_solver_iterations.__doc__)
print(unreal.ProphecyAgent.set_jolt_solver_iterations.__doc__)
print(unreal.ProphecyAgent.get_nn_attack_state.__doc__)
print(unreal.ProphecyAgent.get_nn_pose_data_source.__doc__)
lib=unreal.ConstraintInstanceBlueprintLibrary
print('constraints', [x for x in dir(lib) if x.startswith('get_')])
print('play', [x for x in dir(unreal.LevelEditorSubsystem) if any(k in x for k in ['play','simulate'])])
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
 if isinstance(a,unreal.ProphecyAgent):
  print(a.get_name(),a.get_actor_location(), 'Jolt',a.is_jolt_physical_animation_selected())

import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
 if str(a.get_simulation_mode()).endswith('PHYSICAL: 1>'):
  m=a.get_agent_mesh(); pa=m.get_editor_property("physics_asset_override") or m.get_editor_property("skeletal_mesh").get_editor_property("physics_asset")
  print('BODIES', [b.get_editor_property('bone_name') for b in pa.get_editor_property('skeletal_body_setups')])
  for c in m.get_constraints(False): print('CONSTRAINT',c.constraint_bone1,c.constraint_bone2)

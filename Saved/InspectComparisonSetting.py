import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyNNLocomotionManager):
    print('EDITOR_MANAGER name={} compare={} physical_count={}'.format(a.get_name(), a.get_editor_property('show_physical_kinematic_comparison'), a.get_editor_property('initial_physical_agent_count')))

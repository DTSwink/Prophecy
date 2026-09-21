import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
print('EDITOR_WORLD=' + world.get_path_name())
print('DEBUG_MESH_GETTER=' + str(hasattr(unreal.ProphecyAgent, 'get_kinematic_debug_mesh')))
print('BACKEND_SELECTION_GETTER=' + str(hasattr(unreal.ProphecyAgent, 'is_jolt_physical_animation_selected')))
bp = unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
print('RESTORED_BLUEPRINT=' + (bp.get_path_name() if bp else 'LOAD_FAILED'))
for agent in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    print('BEFORE_PLAY_DEBUG_MESH={} RESULT={}'.format(agent.get_name(), agent.get_kinematic_debug_mesh()))

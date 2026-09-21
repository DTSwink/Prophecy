import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE', bool(ed.get_game_world()))
print('DIRTY', [x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if isinstance(a,unreal.ProphecyNNLocomotionManager):
        print('UPPER_PATH',a.get_editor_property('upper_onnx_model_path'),a.get_editor_property('upper_runtime_contract_path'))

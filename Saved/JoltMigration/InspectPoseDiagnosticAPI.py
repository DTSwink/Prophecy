import unreal
import json
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
print('PIE', unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor())
print('DIRTY', [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()], [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
print(unreal.ProphecyAgent.get_physical_body_state.__doc__)
print(unreal.SkeletalMeshComponent.get_parent_bone.__doc__)
print(unreal.SkeletalMeshComponent.get_bone_names.__doc__)
print(unreal.ProphecyAgent.get_mass_weighted_pose_error.__doc__)

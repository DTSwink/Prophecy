import json
import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
print(json.dumps({'world':world.get_path_name() if world else None,
                 'pie':unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(),
                 'dirty_maps':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
                 'dirty_content':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}))

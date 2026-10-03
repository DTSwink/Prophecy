import json
from pathlib import Path
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
state = {
    'map': world.get_path_name(),
    'pie': unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(),
    'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
    'worlds': [obj.get_path_name() for obj in unreal.ObjectIterator(unreal.World)],
    'ready_jolt_worlds': [obj.get_path_name() for obj in unreal.ObjectIterator(unreal.World)
                          if unreal.ProphecyJoltBlueprintLibrary.is_jolt_world_ready(obj)],
    'active_jolt_agents': [obj.get_path_name() for obj in unreal.ObjectIterator(unreal.ProphecyAgent)
                           if obj.is_jolt_physical_animation_enabled()],
}
folder = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/RuntimeSelfCollision-20260910'
(folder / 'editor-state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
print(json.dumps(state))

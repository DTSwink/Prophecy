import json
from pathlib import Path
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
world = editor.get_editor_world()
rows = []
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    rows.append({"name": actor.get_name(), "label": actor.get_actor_label(), "class": actor.get_class().get_path_name(),
                 "manual": actor.get_editor_property("manual_nn_pose_application"),
                 "mode": str(actor.get_simulation_mode()), "macd": actor.is_macd_enabled()})
report = {"world": world.get_path_name(), "pie": levels.is_in_play_in_editor(), "agents": rows,
          "dirty_maps": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
          "dirty_content": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}
print(json.dumps(report, indent=2))

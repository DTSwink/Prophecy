"""Read-only editor preflight via Tools/RunUnrealRemote.py."""
import json
import pathlib
import unreal

subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = subsystem.get_editor_world()
state = {
    "world": world.get_path_name() if world else None,
    "play": bool(subsystem.get_game_world()),
    "dirty_content": [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
    "dirty_maps": [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
}
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Robotics" / "editor-state.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(state, indent=2), encoding="utf-8")
print(json.dumps(state))

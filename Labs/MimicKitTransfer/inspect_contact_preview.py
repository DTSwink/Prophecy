"""Read-only current map/session check before refreshing our comparison."""
import unreal,json
from pathlib import Path
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
a=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
result=dict(world=e.get_editor_world().get_path_name(),play_world=e.get_game_world().get_path_name() if e.get_game_world() else None,
    dirty=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    actors=[dict(label=x.get_actor_label(),path=x.get_path_name()) for x in a.get_all_level_actors()])
(Path(unreal.Paths.project_dir())/'Saved/MimicKitTransfer/no-armature-3913/contact-preview-before.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))

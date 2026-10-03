import json
from pathlib import Path
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(),'Preserve unsaved assets'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(),'Preserve unsaved maps'
root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/FKReturn/feedback-fix'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(out/'graph-before.txt').write_bytes((root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes())
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
(out/'scene-before.json').write_text(json.dumps({a.get_path_name():str(a.get_actor_transform()) for a in actors},indent=2))
unreal.SystemLibrary.quit_editor()

"""Restore only our unsaved startup actor after the editor crash; preserve the original map backup."""
import hashlib
import json
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
placement = json.loads((root / "Saved/JoltMigration/FightStartup-20260910/placement.json").read_text(encoding="utf-8"))
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name() == "/Game/testNN.testNN"
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert hashlib.sha256(Path(placement["source"]).read_bytes()).hexdigest() == placement["before_sha256"]
actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
assert sorted(a.get_path_name() for a in actors) == placement["before_actors"]
cls = unreal.load_class(None, "/Script/GameAnimationSample3.ProphecyJoltFightSetup")
assert cls
actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(cls, unreal.Vector())
assert actor.get_path_name() == placement["startup_actor"]
actor.set_actor_label("Jolt Fight Setup")
assert actor.get_editor_property("bEnableJolt")
print("RESTORED_UNSAVED_STARTUP_ACTOR " + actor.get_path_name())

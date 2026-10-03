"""Place only the reusable startup actor; save the map after the short startup check."""
import hashlib
import json
import shutil
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
output = root / "Saved/JoltMigration/FightStartup-20260910"
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
assert world.get_path_name() == "/Game/testNN.testNN"
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
dirty_maps = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
assert not dirty_maps or (output.exists() and dirty_maps == ["/Game/testNN"])
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
cls = unreal.load_class(None, "/Script/GameAnimationSample3.ProphecyJoltFightSetup")
assert cls, "Live Coding must finish loading the startup class first"
source = root / "Content/testNN.umap"
existing = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
assert not (output / "placement.json").exists(), "Placement is already recorded"
if output.exists():
    # Resume the exact placement after Python's snake-case lookup failed on the new Live Coding class.
    assert len(existing) == 1 and existing[0].get_name() == "ProphecyJoltFightSetup_0"
    assert (output / "testNN.umap.original").read_bytes() == source.read_bytes()
    actor = existing[0]
else:
    assert not existing
    output.mkdir()
    shutil.copy2(source, output / "testNN.umap.original")
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(cls, unreal.Vector())
before_actors = sorted(a.get_path_name() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if a != actor)
assert actor and actor.get_editor_property("bEnableJolt")
actor.set_actor_label("Jolt Fight Setup")
report = {"source": str(source), "before_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
          "before_actors": before_actors, "startup_actor": actor.get_path_name(), "saved": False}
(output / "placement.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"startup_actor": report["startup_actor"], "saved": False}))

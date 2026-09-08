"""Run one isolated whole-step benchmark, outside PIE, through the editor bridge.

Arguments: cpu|gpu, agent count. Includes native geometry and GPU transfers.
No manager, level or project settings are saved.
"""
import json
import sys
from pathlib import Path
import unreal

gpu = len(sys.argv) > 1 and sys.argv[1].lower() == "gpu"
count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
manager = subsystem.spawn_actor_from_class(unreal.ProphecyNNLocomotionManager, unreal.Vector(), transient=True)
try:
    passed = manager.call_method("BenchmarkSlashRuntime", args=(gpu, count))
finally:
    subsystem.destroy_actor(manager)
path = Path(unreal.Paths.project_saved_dir()) / f"SlashParity/native_{'gpu' if gpu else 'cpu'}_b{count}.json"
print(path.read_text() if path.exists() else "Benchmark did not produce a report; inspect Unreal log")
assert passed, "Whole-step parity failed"

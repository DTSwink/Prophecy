"""Editor-only native NNE parity. Run through the bridge, outside PIE.

Creates/destroys one test manager through the supported editor actor API;
does not save the level or change its existing manager.
"""
import json
from pathlib import Path
import unreal

assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None, "End PIE before this audit"
root = Path(unreal.Paths.project_dir()).resolve()
contract = json.loads((root / "Content/locomotion/NN/prophecy_slash_runtime.json").read_text())
manager = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.ProphecyNNLocomotionManager, unreal.Vector(0, 0, 0), transient=True)
assert manager
try:
    assert manager.call_method("AuditSlashReference", args=(contract["reference_directory"],)), "Native Slash parity failed; inspect the Unreal log"
finally:
    unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(manager)
report = json.loads((root / "Saved/SlashParity/unreal_nne_rollout.json").read_text())
print(json.dumps({key: value for key, value in report.items() if key != "frames"}, indent=2))

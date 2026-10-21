"""Read-only post-repair graph and editor-state verification."""
import hashlib
import json
import pathlib
import unreal

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/SwordSkeletonPenetration"
before = (out / "sword-graph.txt").read_text(encoding="utf-8").encode("utf-8")
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "Prophecy.Sword.AuditCollisionGraph")
source = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/SwordThigh/BlueprintGraph.txt"
raw = source.read_bytes()
text = raw.decode("utf-16" if raw.startswith(b"\xff\xfe") else "utf-8-sig").replace("\r\n", "\n")
after = "\n\n".join(b for b in text.split("\n\n")
                    if b.lstrip().startswith("/Game/_mygame/sword/")).encode("utf-8")
result = {
    "world": ed.get_editor_world().get_path_name(),
    "play": bool(ed.get_game_world()),
    "sword_graph_identical": before == after,
    "sword_graph_sha256": hashlib.sha256(after).hexdigest(),
    "dirty_content": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
    "dirty_maps": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
}
(out / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))

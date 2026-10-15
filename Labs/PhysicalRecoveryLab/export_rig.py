"""Unreal Python commandlet/remote export with source asset fingerprints."""
import hashlib
import json
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
out=root/"Saved/Robotics"
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,"Prophecy.Robotics.ExportRig")
rig=json.loads((out/"rig.json").read_text(encoding="utf-8-sig"))
if not rig.get("success"):
    raise RuntimeError(rig.get("error","rig export failed"))
sources={}
for path in ("Content/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.uasset",
             "Content/_mygame/SKM_UEFN_Mannequin.uasset"):
    file=root/path
    sources[path]={"sha256":hashlib.sha256(file.read_bytes()).hexdigest(),"bytes":file.stat().st_size}
rig["source_files"]=sources
(out/"rig.json").write_text(json.dumps(rig,indent=2),encoding="utf-8")
print(f"Exported {len(rig['bodies'])} bodies, {len(rig['joints'])} joints")

#!/usr/bin/env python3
"""Export the exact UEFN and fitted MetaHuman reference skeletons from the open editor.

This is intentionally an external Unreal remote-execution client. It keeps the
generated JSON in normal source control while reading authoritative values from
the live Unreal assets.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys
import time
import zlib


DEFAULT_REMOTE_EXECUTION = Path(
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python"
)
DEFAULT_OUTPUT = Path(__file__).with_name("skeleton_snapshots.json")

UEFN_MESH = "/Game/_mygame/SKM_UEFN_Mannequin"
FITTED_BODY_MESH = (
    "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"
)


def _unreal_code() -> str:
    return f'''import base64
import json
import zlib
import unreal

def vector(value):
    return [float(value.x), float(value.y), float(value.z)]

def quat(value):
    return [float(value.x), float(value.y), float(value.z), float(value.w)]

def transform(value):
    return {{
        "translation_cm": vector(value.translation),
        "rotation_xyzw": quat(value.rotation),
        "scale_xyz": vector(value.scale3d),
    }}

def snapshot(asset_path):
    mesh = unreal.load_asset(asset_path)
    if not mesh:
        raise RuntimeError("Could not load skeletal mesh: " + asset_path)
    modifier = unreal.SkeletonModifier()
    if not modifier.set_skeletal_mesh(mesh):
        raise RuntimeError("Could not inspect skeletal mesh: " + asset_path)
    bones = []
    for name_value in modifier.get_all_bone_names():
        name = str(name_value)
        parent = str(modifier.get_parent_name(name))
        if parent == "None":
            parent = None
        bones.append({{
            "name": name,
            "parent": parent,
            "local": transform(modifier.get_bone_transform(name, False)),
            "global": transform(modifier.get_bone_transform(name, True)),
        }})
    skeleton = mesh.get_editor_property("skeleton")
    return {{
        "skeletal_mesh": mesh.get_path_name(),
        "skeleton": skeleton.get_path_name() if skeleton else None,
        "bone_count": len(bones),
        "bones": bones,
    }}

uefn = snapshot({UEFN_MESH!r})
fitted = snapshot({FITTED_BODY_MESH!r})
uefn_names = {{bone["name"] for bone in uefn["bones"]}}
fitted_names = {{bone["name"] for bone in fitted["bones"]}}

payload = {{
    "schema_version": 1,
    "engine_version": unreal.SystemLibrary.get_engine_version(),
    "units": {{"translation": "centimeters", "rotation": "quaternion_xyzw"}},
    "fit_recipe": {{
        "original_character": "/Game/_mygame/MetaHumans/test",
        "editable_fitted_character": "/Game/_mygame/MetaHumans/test_UEFNFit",
        "joint_carrier": "/Game/_mygame/MetaHumans/SKM_test_UEFNJointCarrier",
        "final_assembly_blueprint": "/Game/MetaHumans/test_UEFNExactFull/BP_test_UEFNExactFull",
        "final_body_mesh": {FITTED_BODY_MESH!r},
        "uefn_reference_mesh": {UEFN_MESH!r},
        "shared_bone_count": len(uefn_names & fitted_names),
        "uefn_only_bones": sorted(uefn_names - fitted_names),
        "metahuman_only_bone_count": len(fitted_names - uefn_names),
        "joint_import_command": "Prophecy.MetaHuman.SetBodyJointsFromCarrier /Game/_mygame/MetaHumans/test_UEFNFit /Game/_mygame/MetaHumans/SKM_test_UEFNJointCarrier",
    }},
    "uefn_reference": uefn,
    "fitted_metahuman_body_reference": fitted,
}}
encoded = base64.b64encode(zlib.compress(json.dumps(payload, separators=(",", ":")).encode("utf-8"), 9)).decode("ascii")
print("PROPHECY_SKELETON_SNAPSHOT_ZLIB=" + encoded)
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--remote-execution-path", type=Path, default=DEFAULT_REMOTE_EXECUTION
    )
    parser.add_argument("--discovery-timeout", type=float, default=10.0)
    args = parser.parse_args()

    sys.path.insert(0, str(args.remote_execution_path))
    import remote_execution  # type: ignore

    remote = remote_execution.RemoteExecution()
    remote.start()
    try:
        deadline = time.monotonic() + args.discovery_timeout
        while not remote.remote_nodes and time.monotonic() < deadline:
            time.sleep(0.25)
        if not remote.remote_nodes:
            raise RuntimeError("No Unreal remote-execution node was discovered")

        remote.open_command_connection(remote.remote_nodes[0]["node_id"])
        result = remote.run_command(
            _unreal_code(),
            unattended=True,
            exec_mode=remote_execution.MODE_EXEC_FILE,
        )
        if not result.get("success"):
            raise RuntimeError(result.get("result", "Unreal snapshot export failed"))

        marker = "PROPHECY_SKELETON_SNAPSHOT_ZLIB="
        encoded = None
        for entry in result.get("output", []):
            output = entry.get("output", "").strip()
            if output.startswith(marker):
                encoded = output[len(marker) :]
                break
        if not encoded:
            raise RuntimeError("Unreal did not return the skeleton snapshot payload")

        payload = json.loads(zlib.decompress(base64.b64decode(encoded)))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
        print(
            f"Wrote {args.output}: "
            f"UEFN={payload['uefn_reference']['bone_count']} bones, "
            f"MetaHuman={payload['fitted_metahuman_body_reference']['bone_count']} bones"
        )
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    raise SystemExit(main())

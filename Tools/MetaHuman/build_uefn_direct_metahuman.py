"""Build and audit the direct-UEFN-skeleton MetaHuman assets inside Unreal Editor.

Run from an open editor with Execute Python Script, or headlessly with:

    UnrealEditor-Cmd.exe GameAnimationSample3.uproject -run=pythonscript \
      -script=Tools/MetaHuman/build_uefn_direct_metahuman.py

Use --reuse-existing to audit assets without rebuilding them. Output asset paths
can be overridden with --body-output and --blueprint-output.
"""

from __future__ import annotations

import argparse
import re
import sys

import unreal


SOURCE_BODY = (
    "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"
)
UEFN_MESH = "/Game/_mygame/SKM_UEFN_Mannequin"
SOURCE_BLUEPRINT = "/Game/MetaHumans/test_UEFNExactFull/BP_test_UEFNExactFull"
FACE_ANIM_BLUEPRINT = "/Game/MetaHumans/Common/Face/Face_AnimBP"
DEFAULT_BODY_OUTPUT = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody"
DEFAULT_BLUEPRINT_OUTPUT = "/Game/_mygame/MetaHumans/BP_test_UEFNDirect"
UEFN_SKELETON = "/Game/_mygame/SK_UEFN_Mannequin.SK_UEFN_Mannequin"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--body-output", default=DEFAULT_BODY_OUTPUT)
    parser.add_argument("--blueprint-output", default=DEFAULT_BLUEPRINT_OUTPUT)
    parser.add_argument("--reuse-existing", action="store_true")
    command_line = unreal.SystemLibrary.get_command_line()
    forwarded = list(sys.argv[1:])
    for name in ("body-output", "blueprint-output"):
        match = re.search(
            rf"(?:^|\s)--{name}=(?:\"([^\"]+)\"|(\S+))", command_line
        )
        if match:
            forwarded.append(f"--{name}={match.group(1) or match.group(2)}")
    if re.search(r"(?:^|\s)--reuse-existing(?:\s|$)", command_line):
        forwarded.append("--reuse-existing")
    args, _ = parser.parse_known_args(forwarded)
    return args


def _asset_exists(path: str) -> bool:
    return unreal.EditorAssetLibrary.does_asset_exist(path)


def _run_console_command(command: str) -> None:
    unreal.log(f"Prophecy MetaHuman build: {command}")
    unreal.SystemLibrary.execute_console_command(None, command)


def _build_if_needed(args: argparse.Namespace) -> None:
    body_exists = _asset_exists(args.body_output)
    blueprint_exists = _asset_exists(args.blueprint_output)
    if not args.reuse_existing and (body_exists or blueprint_exists):
        existing = [
            path
            for path, exists in (
                (args.body_output, body_exists),
                (args.blueprint_output, blueprint_exists),
            )
            if exists
        ]
        raise RuntimeError(
            "Refusing to overwrite generated assets: " + ", ".join(existing)
        )

    if not body_exists:
        _run_console_command(
            "Prophecy.MetaHuman.BuildUEFNBody "
            f"{SOURCE_BODY} {UEFN_MESH} {args.body_output}"
        )
    if not _asset_exists(args.body_output):
        raise RuntimeError("The direct UEFN body was not generated")

    if not blueprint_exists:
        _run_console_command(
            "Prophecy.MetaHuman.BuildUEFNBlueprint "
            f"{SOURCE_BLUEPRINT} {args.body_output} "
            f"{FACE_ANIM_BLUEPRINT} {args.blueprint_output}"
        )
    if not _asset_exists(args.blueprint_output):
        raise RuntimeError("The direct UEFN MetaHuman Blueprint was not generated")


def _component_templates(blueprint: unreal.Blueprint) -> dict[str, object]:
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    templates: dict[str, object] = {}
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
        data = library.get_data(handle)
        name = str(library.get_variable_name(data))
        template = library.get_object_for_blueprint(data, blueprint)
        if template and name not in templates:
            templates[name] = template
    return templates


def _audit(args: argparse.Namespace) -> None:
    body = unreal.load_asset(args.body_output)
    blueprint = unreal.load_asset(args.blueprint_output)
    if not isinstance(body, unreal.SkeletalMesh):
        raise RuntimeError("Generated body is not a SkeletalMesh")
    if not isinstance(blueprint, unreal.Blueprint):
        raise RuntimeError("Generated character is not a Blueprint")

    skeleton = body.get_editor_property("skeleton")
    if not skeleton or skeleton.get_path_name() != UEFN_SKELETON:
        raise RuntimeError(
            "Generated body is not assigned to the authoritative UEFN Skeleton"
        )

    modifier = unreal.SkeletonModifier()
    if not modifier.set_skeletal_mesh(body):
        raise RuntimeError("Could not inspect generated body skeleton")
    body_bones = {str(name) for name in modifier.get_all_bone_names()}

    uefn = unreal.load_asset(UEFN_MESH)
    uefn_modifier = unreal.SkeletonModifier()
    if not uefn_modifier.set_skeletal_mesh(uefn):
        raise RuntimeError("Could not inspect UEFN reference skeleton")
    uefn_bones = {str(name) for name in uefn_modifier.get_all_bone_names()}
    if len(body_bones) != 78 or not body_bones.issubset(uefn_bones):
        raise RuntimeError(
            f"Unexpected direct-body hierarchy: {len(body_bones)} mesh bones"
        )

    lod_count = unreal.get_editor_subsystem(
        unreal.SkeletalMeshEditorSubsystem
    ).get_lod_count(body)
    if lod_count != 3:
        raise RuntimeError(f"Expected 3 regenerated LODs, found {lod_count}")

    templates = _component_templates(blueprint)
    body_template = templates.get("Body")
    face_template = templates.get("Face")
    if not isinstance(body_template, unreal.SkeletalMeshComponent):
        raise RuntimeError("Generated Blueprint has no Body skeletal component")
    if not isinstance(face_template, unreal.SkeletalMeshComponent):
        raise RuntimeError("Generated Blueprint has no Face skeletal component")
    if body_template.get_skinned_asset() != body:
        raise RuntimeError("Generated Blueprint does not use the direct UEFN body")

    face_anim = face_template.get_editor_property("anim_class")
    expected_face_anim = unreal.load_asset(FACE_ANIM_BLUEPRINT).generated_class()
    if face_anim != expected_face_anim:
        raise RuntimeError("Generated Blueprint does not use Face_AnimBP")

    unreal.log(
        "PROPHECY_UEFN_METAHUMAN_AUDIT="
        f"body={body.get_path_name()}|bones={len(body_bones)}|lods={lod_count}|"
        f"skeleton={skeleton.get_path_name()}|"
        f"blueprint={blueprint.get_path_name()}|face_anim={face_anim.get_path_name()}"
    )


def main() -> None:
    args = _arguments()
    _build_if_needed(args)
    _audit(args)


if __name__ == "__main__":
    main()

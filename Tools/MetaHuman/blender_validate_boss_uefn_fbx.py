"""Cold-import the Boss FBX and verify its UEFN skeleton and skin payload."""

import json
from pathlib import Path

import bpy


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
FBX = PROJECT / "Saved" / "BlenderExchange" / "BossUEFN" / "SKM_Boss_UEFN.fbx"
SOURCE_AUDIT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_UEFN_ExportAudit.json"
)
OUTPUT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_UEFN_FBXRoundtripAudit.json"
)


def hierarchy(rig):
    return {
        bone.name: bone.parent.name if bone.parent else None
        for bone in rig.data.bones
    }


def main():
    source = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(
        filepath=str(FBX),
        use_manual_orientation=False,
        global_scale=1.0,
        bake_space_transform=False,
        use_custom_normals=True,
        use_anim=False,
        ignore_leaf_bones=False,
        force_connect_children=False,
        automatic_bone_orientation=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_prepost_rot=True,
        axis_forward="-Z",
        axis_up="Y",
    )
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    empties = [obj for obj in bpy.data.objects if obj.type == "EMPTY"]
    if len(armatures) != 1 or len(meshes) != 1:
        raise RuntimeError(
            f"Unexpected FBX payload: {len(armatures)} rigs, {len(meshes)} meshes; "
            f"objects={[(obj.name, obj.type, obj.parent.name if obj.parent else None) for obj in bpy.data.objects]}"
        )
    rig = armatures[0]
    mesh = meshes[0]
    bone_names = [bone.name for bone in rig.data.bones]
    roundtrip_hierarchy = hierarchy(rig)
    source_names = source["bone_names"]
    if bone_names != source_names:
        raise RuntimeError("FBX bone names/order changed")
    if roundtrip_hierarchy != source["hierarchy"]:
        raise RuntimeError("FBX bone hierarchy changed")
    if len(mesh.data.vertices) != source["weight_audit"]["vertices"]:
        raise RuntimeError("FBX vertex count changed")

    modifier_rigs = [
        modifier.object
        for modifier in mesh.modifiers
        if modifier.type == "ARMATURE" and modifier.object
    ]
    if modifier_rigs != [rig]:
        raise RuntimeError("Roundtrip mesh is not bound to the sole armature")
    if mesh.parent != rig:
        raise RuntimeError("Roundtrip mesh is not parented to the sole armature")

    group_names = {group.index: group.name for group in mesh.vertex_groups}
    zero = 0
    maximum_influences = 0
    maximum_sum_error = 0.0
    unknown = set()
    for vertex in mesh.data.vertices:
        groups = [
            membership
            for membership in vertex.groups
            if membership.weight > 1.0e-8
        ]
        total = sum(membership.weight for membership in groups)
        zero += int(total <= 1.0e-8)
        maximum_influences = max(maximum_influences, len(groups))
        if total > 1.0e-8:
            maximum_sum_error = max(maximum_sum_error, abs(total - 1.0))
        for membership in groups:
            name = group_names[membership.group]
            if name not in source_names:
                unknown.add(name)

    report = {
        "fbx": str(FBX),
        "object_names": sorted(obj.name for obj in bpy.data.objects),
        "armature": rig.name,
        "mesh": mesh.name,
        "armatures": len(armatures),
        "meshes": len(meshes),
        "empties": len(empties),
        "bone_count": len(rig.data.bones),
        "bone_names_match": bone_names == source_names,
        "hierarchy_matches": roundtrip_hierarchy == source["hierarchy"],
        "vertex_count": len(mesh.data.vertices),
        "polygon_count": len(mesh.data.polygons),
        "zero_weight_vertices": zero,
        "maximum_influences": maximum_influences,
        "maximum_weight_sum_error": maximum_sum_error,
        "unknown_groups": sorted(unknown),
        "materials": [
            {
                "index": index,
                "name": slot.material.name if slot.material else slot.name,
                "polygon_count": sum(
                    polygon.material_index == index
                    for polygon in mesh.data.polygons
                ),
            }
            for index, slot in enumerate(mesh.material_slots)
        ],
        "mesh_parent": mesh.parent.name if mesh.parent else None,
        "armature_modifiers": [obj.name for obj in modifier_rigs],
    }
    if (
        zero
        or unknown
        or maximum_influences > 8
        or maximum_sum_error > 1.0e-5
        or len(rig.data.bones) != 87
    ):
        raise RuntimeError("Roundtrip audit failed: " + str(report))
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("BOSS_UEFN_FBX_ROUNDTRIP=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

"""Background-only fitted Boss export with UEFN bone-frame conventions.

Keep the fitted rest shape, joint positions, hierarchy and relative weights.
Convert coordinates with the saved paired native-pose / working-rest rigs;
do not replace fitted orientations with the unrelated native reference pose.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).parent))
from blender_prepare_boss_uefn_export_driver import (
    evaluated_world_positions, normalized_vertex_weights, write_normalized_weights,
    repair_material_regions, weight_audit, position_delta, matrix_delta)
from blender_ue_export import export_skeletal_fbx

SOURCE = Path(r'C:/Users/singerie/Documents/Blender/bossfinalsave.blend')
OUT = Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/BossUEFNCompatible/20260907')

def main():
    assert bpy.app.background, 'Never run in the interactive Blender scene'
    assert Path(bpy.data.filepath).resolve() == SOURCE.resolve()
    repair_shading = '--repair-collar-normals' in sys.argv
    stitch = '--stitch-collar' in sys.argv
    assert not (stitch and repair_shading), 'Stitch includes the collar-normal repair'
    output = (OUT.parent / '20260908_Stitched') if stitch else ((OUT.parent / '20260908_Shading') if repair_shading else OUT)
    output.mkdir(parents=True, exist_ok=True)
    fbx = output / 'SKM_Boss_UEFN_Fitted.fbx'
    assert not fbx.exists(), 'Refusing to overwrite an existing export'
    rig = bpy.data.objects['UEFN_WORKING_CLEAN_RIG.001']
    working = bpy.data.objects['UEFN_WORKING_CLEAN_RIG']
    native = bpy.data.objects['UEFN_NATIVE_EXPORT_RIG']
    mesh = bpy.data.objects['boss']
    assert len(rig.data.bones) == 87 and len(mesh.data.vertices) == 11374
    stitched = None
    if stitch:
        from stitch_boss_collar import stitch_collar
        stitched = stitch_collar(mesh)
    assert rig.parent is None and mesh.parent == rig
    bpy.context.view_layer.update()
    assert all(matrix_delta(pb.matrix_basis, Matrix.Identity(4)) < 1e-7 for pb in rig.pose.bones)
    original_surface = evaluated_world_positions(mesh)
    old = {b.name: b.matrix_local.copy() for b in rig.data.bones}
    hierarchy = {b.name: b.parent.name if b.parent else None for b in rig.data.bones}
    names = set(old)
    assert names == set(working.data.bones.keys()) == set(native.data.bones.keys())
    # These two retained rigs describe the same physical pose in different
    # bone coordinates. This is the authoritative coordinate conversion.
    paired_head_error = max(((working.matrix_world @ working.data.bones[n].matrix_local).translation -
                            (native.matrix_world @ native.pose.bones[n].matrix).translation).length for n in names)
    assert paired_head_error < 1e-5, ('Saved reference pair no longer matches', paired_head_error)
    corrections = {n: (working.data.bones[n].matrix_local.to_quaternion().inverted() @
                       native.pose.bones[n].matrix.to_quaternion()).normalized().to_matrix().to_4x4() for n in names}
    desired = {n: old[n] @ corrections[n] for n in names}

    rig.animation_data_clear()
    bpy.ops.object.select_all(action='DESELECT')
    rig.hide_set(False)
    rig.hide_viewport = False
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    # Connection flags constrain head to parent tail. Converted tails encode
    # axes, not child-joint endpoints, so disconnect only the export rig.
    for bone in rig.data.edit_bones:
        bone.use_connect = False
    for n, transform in desired.items():
        rig.data.edit_bones[n].matrix = transform
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    assert {b.name: b.parent.name if b.parent else None for b in rig.data.bones} == hierarchy
    heads_error = max((rig.data.bones[n].head_local - old[n].translation).length for n in names)
    axes_error = max(matrix_delta(rig.data.bones[n].matrix_local, desired[n]) for n in names)
    assert heads_error < 1e-3 and axes_error < 1e-3
    # Rebinding at identity must not reshape the skin.
    write_normalized_weights(mesh, normalized_vertex_weights(mesh, names), names)
    shading = None
    if repair_shading:
        from boss_collar_normals import repair_collar_normals
        shading = repair_collar_normals(mesh)
    materials = repair_material_regions(mesh)
    bpy.context.view_layer.update()
    surface_error = position_delta(original_surface, evaluated_world_positions(mesh))
    assert surface_error['maximum_m'] < 1e-5, surface_error

    # Coordinate-change invariant for arbitrary pose rotations/translations:
    # (P*C) * inverse(S*C) == P * inverse(S), for every skinning influence.
    invariance = 0.0
    for n in names:
        s = old[n]
        c = corrections[n]
        for angle in (-0.85, 0.31, 1.20):
            p = Matrix.Translation((1.3, -0.7, 2.1)) @ Matrix.Rotation(angle, 4, 'X') @ s
            invariance = max(invariance, matrix_delta((p @ c) @ desired[n].inverted(), p @ s.inverted()))
    assert invariance < 1e-3

    assert bpy.data.objects.get('root') is None, 'Avoid FBX root.001 collision'
    rig.name = 'root'
    mesh.name = 'SKM_Boss_UEFN_Fitted'
    mesh.hide_set(False)
    mesh.hide_viewport = False
    rig.scale = tuple(v * 100 for v in rig.scale)
    bpy.context.view_layer.update()
    rest_world_cm = {n: [list(row) for row in rig.matrix_world @ rig.data.bones[n].matrix_local] for n in names}
    export_skeletal_fbx(str(fbx), rig, [mesh])
    report = {'source': str(SOURCE), 'source_saved': False, 'fbx': str(fbx),
        'method': 'fitted_rest_times_inverse_working_rest_rotation_times_paired_native_pose_rotation',
        'paired_joint_error_m': paired_head_error, 'fitted_joint_change_cm': heads_error,
        'fitted_surface_change': surface_error, 'matrix_invariance_error': invariance,
        'converted_rest_world_cm': rest_world_cm, 'hierarchy': hierarchy,
        'coordinate_corrections': {n: [list(row) for row in c] for n,c in corrections.items()},
        'materials': materials, 'weights': weight_audit(mesh, names),
        'collar_shading_repair': shading,
        'collar_stitch': stitched,
        'top_level_root_name': rig.name}
    (output / 'export_audit.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print('BOSS_FITTED_UEFN_AXES_EXPORTED', fbx, 'surface', surface_error, 'heads_cm', heads_error)

if __name__ == '__main__':
    main()

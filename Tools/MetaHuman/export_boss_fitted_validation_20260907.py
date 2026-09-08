"""Background-only exact fitted bind export. Does not save the source .blend."""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).parent))
from blender_prepare_boss_uefn_export_driver import (
    evaluated_world_positions, normalized_vertex_weights, write_normalized_weights,
    repair_material_regions, weight_audit, position_delta)
from blender_ue_export import export_skeletal_fbx

assert bpy.app.background, 'Run in a separate background Blender, not the user scene'
SOURCE = Path(r'C:/Users/singerie/Documents/Blender/bossfinalsave.blend')
assert Path(bpy.data.filepath).resolve() == SOURCE.resolve()
OUT = Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/BossBindAudit/20260907')
OUT.mkdir(parents=True, exist_ok=True)
FBX = OUT / 'SKM_Boss_Fitted_Test.fbx'
assert not FBX.exists(), 'Refusing to overwrite diagnostic output'
rig = bpy.data.objects['UEFN_WORKING_CLEAN_RIG.001']
mesh = bpy.data.objects['boss']
assert len(rig.data.bones) == 87 and len(mesh.data.vertices) == 11374
assert rig.parent is None and mesh.parent == rig
assert all(max(abs(pb.matrix_basis[i][j] - Matrix.Identity(4)[i][j]) for i in range(4) for j in range(4)) < 1e-7
           for pb in rig.pose.bones), 'Saved source must already be in fitted rest'
before = evaluated_world_positions(mesh)
rest_before = {b.name: [list(row) for row in rig.matrix_world @ b.matrix_local] for b in rig.data.bones}
names = set(rest_before)
write_normalized_weights(mesh, normalized_vertex_weights(mesh, names), names)
material_report = repair_material_regions(mesh)
bpy.context.view_layer.update()
weight_only_delta = position_delta(before, evaluated_world_positions(mesh))
assert weight_only_delta['maximum_m'] < 1e-6
rig.animation_data_clear()
rig.name = 'root'
mesh.name = 'SKM_Boss_Fitted_Test'
rig.hide_set(False)
rig.hide_viewport = False
mesh.hide_set(False)
mesh.hide_viewport = False
rig.scale = tuple(s * 100 for s in rig.scale)
bpy.context.view_layer.update()
export_skeletal_fbx(str(FBX), rig, [mesh])
(OUT / 'fitted_export.json').write_text(json.dumps({
    'source': str(SOURCE), 'fbx': str(FBX), 'source_saved': False,
    'changed_joint_rest_matrices': False, 'reshaped_geometry': False,
    'source_world_bone_matrices_m': rest_before, 'normalization_surface_delta': weight_only_delta,
    'weights': weight_audit(mesh, names), 'materials': material_report}, indent=2))
print('FITTED_EXPORT_OK', FBX, weight_only_delta)

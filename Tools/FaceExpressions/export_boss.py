import bpy, numpy as np, sys
sys.path.insert(0, '/mnt/user-data/uploads/Prophecy/Tools/MetaHuman')
from blender_ue_export import export_skeletal_fbx
F = '/home/claude/face/'
SRC = '/mnt/user-data/uploads/Prophecy/Saved/BossUEFNCompatible/20260908_Stitched/SKM_Boss_UEFN_Fitted.fbx'
OUT = F + 'out/SKM_Boss_UEFN_Fitted_Expressions.fbx'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
o = [x for x in bpy.data.objects if x.type == 'MESH'][0]; arm = [x for x in bpy.data.objects if x.type == 'ARMATURE'][0]
me = o.data
assert arm.name == 'root' and o.name == 'SKM_Boss_UEFN_Fitted' and len(me.vertices) == 11331
print('mods', [(m.type, m.object.name if getattr(m, 'object', None) else None) for m in o.modifiers], 'arm scale', tuple(arm.scale))
D = np.load(F + 'boss_deltas.npz'); names = list(D['names'])
inv = np.linalg.inv(np.array(o.matrix_world)[:3, :3])
n = len(me.vertices); base = np.zeros(n * 3); me.vertices.foreach_get('co', base); base = base.reshape(-1, 3)
o.shape_key_add(name='Basis', from_mix=False)
for nm in names:
    k = o.shape_key_add(name=nm, from_mix=False)
    co = base.copy(); co[D[nm + '_idx']] += (inv @ D[nm + '_d'].T).T
    k.data.foreach_set('co', co.ravel())
# match the established export: cm scene, rig scale x100
arm.scale = tuple(v * 100 for v in arm.scale)
bpy.context.view_layer.update()
export_skeletal_fbx(OUT, arm, [o])
print('EXPORTED', OUT)

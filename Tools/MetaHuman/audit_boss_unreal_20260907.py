"""Read-only mesh source and mesh-reference-skeleton capture in the live editor."""
import json
from pathlib import Path
import unreal

OUT = Path(unreal.Paths.project_saved_dir()) / 'BossBindAudit' / '20260907'
OUT.mkdir(parents=True, exist_ok=True)

def capture(path, label):
    mesh = unreal.load_asset(path)
    sk = unreal.SkeletonModifier()
    assert sk.set_skeletal_mesh(mesh)
    bones = {}
    for name in sk.get_all_bone_names():
        t = sk.get_bone_transform(name, True)
        bones[str(name)] = {'parent': str(sk.get_parent_name(name)), 'position': list(t.translation.to_tuple()),
                            'rotation': [t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w],
                            'scale': list(t.scale3d.to_tuple())}
    dm = unreal.DynamicMesh()
    _, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(mesh, dm,
        unreal.GeometryScriptCopyMeshFromAssetOptions(),
        unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL, lod_index=0))
    assert outcome == unreal.GeometryScriptOutcomePins.SUCCESS
    sw = unreal.SkinWeightModifier()
    assert sw.set_skeletal_mesh(mesh)
    positions, weights = [], []
    for i in range(sw.get_num_vertices()):
        p, valid = unreal.GeometryScript_MeshQueries.get_vertex_position(dm, i)
        assert valid
        positions.append([p.x, p.y, p.z])
        weights.append({str(k): float(v) for k, v in sw.get_vertex_weights(i).items()})
    result = {'path': path, 'bones': bones, 'positions': positions, 'weights': weights,
              'skeleton': mesh.get_editor_property('skeleton').get_path_name(),
              'sources': list(mesh.get_editor_property('asset_import_data').extract_filenames())}
    (OUT / (label + '.json')).write_text(json.dumps(result), encoding='utf8')
    print('CAPTURE', label, len(bones), len(positions), result['sources'])

if __name__ == '__main__':
    capture('/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN', 'unreal_current')

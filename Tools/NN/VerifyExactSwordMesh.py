"""Verify every baked vertex against the original training matrix; save only the new copy."""
import unreal,json,math
from pathlib import Path
root=Path(unreal.Paths.project_saved_dir()).resolve()
job=json.loads((root/'Sword/exact_mesh_job.json').read_text())
source=unreal.load_asset('/Game/_mygame/sword/geometry/Sword_GL01')
baked=unreal.load_asset('/Game/_mygame/sword/geometry/Sword_GL01_Training')
assert source and baked
sd=source.get_static_mesh_description(0);bd=baked.get_static_mesh_description(0)
assert sd.get_vertex_count()==bd.get_vertex_count()
data=job['source']
grip=unreal.Transform(location=unreal.Vector(*data['location_cm']),rotation=unreal.Quat(*data['quaternion_xyzw']).rotator(),scale=unreal.Vector(*data['scale']))
matrix=data['local_to_hand_source'];axes=data['mesh_to_source_axes'];offset=data['mesh_to_source_offset_cm']
worst=0.;basis_error=0.
for i in range(sd.get_vertex_count()):
    v=unreal.VertexID(i)
    if not sd.is_vertex_valid(v):continue
    p=sd.get_vertex_position(v);q=bd.get_vertex_position(v)
    orig=[p.x,p.y,p.z];actual=[q.x,q.y,q.z]
    expected_bake=[sum(orig[k]*job['basis'][k][j] for k in range(3)) for j in range(3)]
    basis_error=max(basis_error,math.dist(expected_bake,actual))
    src=[sum(orig[k]*axes[k][j] for k in range(3))+offset[j] for j in range(3)]
    target=[sum(src[k]*matrix[k*4+j] for k in range(3))+matrix[12+j]*100 for j in range(3)]
    target[1]*=-1
    got=grip.transform_location(q)
    worst=max(worst,math.dist([got.x,got.y,got.z],target))
assert basis_error<.0001 and worst<.0001,(basis_error,worst)
result={'passed':True,'vertices':sd.get_vertex_count(),'bake_error_cm':basis_error,'source_transform_error_cm':worst,'original_mesh_unchanged':True}
(root/'Sword/exact_mesh_audit.json').write_text(json.dumps(result,indent=2))
assert unreal.EditorAssetLibrary.save_loaded_asset(baked,only_if_is_dirty=True)
print(result)

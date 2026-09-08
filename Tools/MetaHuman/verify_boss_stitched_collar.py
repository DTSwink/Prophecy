"""Numerically verify the imported neck join and skinning invariants."""
import json
from pathlib import Path
import numpy as np

out=Path(__file__).resolve().parents[2]/'Saved/BossUEFNCompatible/20260908_Stitched'
export=json.loads((out/'export_audit.json').read_text())
bind=json.loads((out/'bind_after.json').read_text())
shade=json.loads((out/'unreal_stitched.json').read_text())
targets=np.asarray(export['collar_stitch']['collar_world_m'])*[100,-100,100]
positions=np.asarray(shade['positions']);bindpos=np.asarray(bind['positions'])
corners={}
for c in shade['corners']:corners.setdefault(c[0],[]).append(np.asarray(c[2]))
max_gap=0.;max_angle=0.;max_bind_error=0.;max_pose_gap=0.
rng=np.random.default_rng(734)
bones=list(bind['bones'])
# Arbitrary affine bone motions stress the shared-weight LBS invariant. These
# are numerical synthetic deformations, not a claim of animation visual QA.
transforms=rng.normal(size=(20,len(bones),3,4))
bone_index={n:i for i,n in enumerate(bones)}
for point in targets:
    near=np.flatnonzero(np.linalg.norm(positions-point,axis=1)<.002)
    assert len(near)>0
    max_bind_error=max(max_bind_error,float(np.min(np.linalg.norm(positions-point,axis=1))))
    max_gap=max(max_gap,float(np.max(np.linalg.norm(positions[near]-positions[near[0]],axis=1))))
    ns=np.asarray([n for v in near for n in corners.get(int(v),[])])
    ns/=np.linalg.norm(ns,axis=1,keepdims=True)
    max_angle=max(max_angle,float(np.degrees(np.arccos(np.clip((ns@ns.T).min(),-1,1)))))
    ids=np.flatnonzero(np.linalg.norm(bindpos-point,axis=1)<.002)
    assert len(ids)>0
    posed=[]
    for i in ids:
        weights=bind['weights'][int(i)]
        p=np.r_[bindpos[i],1.]
        posed.append(sum(w*(transforms[:,bone_index[name]]@p) for name,w in weights.items()))
    posed=np.asarray(posed)
    max_pose_gap=max(max_pose_gap,float(np.linalg.norm(posed-posed[:1],axis=-1).max()))
assert max_bind_error<.002 and max_gap<.0001 and max_angle<.1 and max_pose_gap<.0001
assert len(bind['positions'])==11331
result={'passed':True,'collar_vertices_checked':len(targets),'source_vertices_after':len(bind['positions']),
        'max_imported_collar_gap_cm':max_gap,'max_target_import_error_cm':max_bind_error,
        'max_geometric_normal_difference_degrees':max_angle,'synthetic_skinning_cases':20,
        'max_synthetic_skinning_gap_cm':max_pose_gap,
        'limits':'Mesh/source normals and shared skin weights verified; final normal-map shading still needs user visual check'}
(out/'verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))

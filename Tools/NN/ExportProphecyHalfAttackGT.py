"""Read original GT controller rows; bake Armed-1/Armed half-attack lower seeds.

Writes a small runtime data file, never modifies source NPZs, training or weights.
"""
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from ExportProphecySlashPolicy import PROJECT,prepare,slash,torch,sha,CHECKPOINT_SHA

def main():
    torch.set_num_threads(2)
    rt,_,_,_=prepare(1)
    native=json.loads((PROJECT/'Content/locomotion/NN/prophecy_slash_native.json').read_text())
    names=native['bone_names'];mirror=np.diag([1,-1,1])
    source=Path(rt.recipe.gt_dir)
    rows={}
    with rt.policy_context(),torch.inference_mode():
        for family in slash.ATTACK_LABELS:
            path=next(p for p in source.glob('*.npz') if p.stem.lower()==family)
            original=source.parent/'final_gt_attack_dataset_npz'/path.name
            gt=slash.load_controller_target_arrays(path)
            with np.load(path,allow_pickle=False) as z:
                armed=float(z['attack_armed_frame']);target=np.array(z['attack_target_world_m'],np.float32)
                fps=float(z['fps'])
            with np.load(original,allow_pickle=False) as z:
                assert armed==float(z['attack_armed_frame']) and fps==float(z['fps'])
            assert armed.is_integer() and 1<=armed<gt.frame_count and fps==30
            indices=np.array([int(armed)-1,int(armed)])
            # Both conditioning frames share the GT Armed root, retaining the
            # original GT velocity instead of importing a real runner's history.
            root_p=gt.visible_global_pos_m[int(armed),gt.root_index]
            root_r=gt.source_global_rot[int(armed),gt.root_index]
            p=torch.from_numpy(np.repeat(root_p[None],2,0));r=torch.from_numpy(np.repeat(root_r[None],2,0))
            lower=slash.target_codec.lower_target_frame_to_root(rt.lower_store,
                torch.from_numpy(gt.lower_hybrid_state[indices]),p,r,
                torch.from_numpy(np.repeat(target[None],2,0)),torch.from_numpy(gt.pelvis_target_heading[indices]))
            keep=[gt.names.index(n) for n in names]
            pos=(gt.visible_global_pos_m[indices][:,keep]-root_p)@root_r.T@mirror*100
            rot=mirror@gt.controller_global_rot[indices][:,keep]@root_r.T@mirror
            quat=Rotation.from_matrix(rot.reshape(-1,3,3).transpose(0,2,1)).as_quat().reshape(2,25,4)
            poses=np.concatenate((pos,quat),axis=-1)
            rows[family]={'armed_frame':int(armed),'previous_frame':int(armed)-1,'fps':fps,
                'original_gt_file':str(original),'original_gt_sha256':sha(original),
                'controller_gt_file':str(path),'controller_gt_sha256':sha(path),
                'lower_previous':lower[0].tolist(),'lower_current':lower[1].tolist(),
                'pose_previous':poses[0].tolist(),'pose_current':poses[1].tolist()}
    payload={'schema':1,'checkpoint_sha256':CHECKPOINT_SHA,'bone_names':names,'families':rows}
    dest=PROJECT/'Content/locomotion/NN/prophecy_slash_half_gt.json'
    dest.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps({'file':str(dest),'bytes':dest.stat().st_size,'families':{k:[v['previous_frame'],v['armed_frame']] for k,v in rows.items()}},indent=2))

if __name__=='__main__':main()

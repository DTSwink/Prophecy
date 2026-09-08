"""Convert the immutable reference to UE bone tracks with the existing Slash codec."""
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = Path(r"C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260907_good_pt_continuous_random_30_hits_unreal_handoff")

def main():
    data = json.loads((HANDOFF / "unreal_interchange.json").read_text())
    source = HANDOFF / data['authoritativeSource']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == data['sourceSha256']
    z = np.load(source,allow_pickle=False)
    c = json.loads((ROOT / "Content/locomotion/NN/prophecy_slash_runtime.json").read_text())
    r = np.array(c['root_rotation']); p = np.array(c['root_position_m']); mirror = np.diag([1,-1,1])
    world_p = (z['rollout_global_joint_pos_m']-p) @ r.T @ mirror * 100
    world_r = mirror @ z['rollout_global_rot'] @ r.T @ mirror
    tracks=[]
    for i, name in enumerate(data['boneNames']):
        parent=data['parents'][i]
        if parent < 0:
            local_p=world_p[:,i]; local_r=world_r[:,i]
        else:
            inv=world_r[:,parent].transpose(0,2,1)
            local_p=np.einsum('fi,fij->fj',world_p[:,i]-world_p[:,parent],inv)
            local_r=world_r[:,i] @ inv
        q=Rotation.from_matrix(local_r.transpose(0,2,1)).as_quat()
        tracks.append({'name':name,'positions':np.concatenate((local_p,local_p[-1:])).tolist(),
                       'rotations':np.concatenate((q,q[-1:])).tolist()})
    payload={'source_sha256':data['sourceSha256'],'tracks':tracks,'world_positions_cm':world_p.tolist(),
             'world_quaternions':Rotation.from_matrix(world_r.reshape(-1,3,3).transpose(0,2,1)).as_quat().reshape(455,25,4).tolist(),
             'parents':data['parents'],'bone_names':data['boneNames']}
    dest=ROOT / 'Saved/SlashChain/animation_tracks.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(payload))
    print(dest)

if __name__=='__main__': main()

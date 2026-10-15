"""Independently reconstruct a captured Run LR's weighted errors and guides."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
from replay import WORLD_TO_VIEW,convert

p=argparse.ArgumentParser();p.add_argument('recording',type=Path);p.add_argument('geometry',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
with np.load(a.recording,allow_pickle=False) as z:
    meta=json.loads(str(z['metadata']));pose=z['pose'];target=z['reference_pose'];vel=z['world_velocities'];terms=z['loss_terms'];data=z['data']
rot=R.from_quat(pose[:,:,3:].reshape(-1,4)).as_matrix().reshape(*pose.shape[:2],3,3)
trot=R.from_quat(target[:,:,3:].reshape(-1,4)).as_matrix().reshape(*pose.shape[:2],3,3)
raw=np.stack([((pose[:,:,:3]-target[:,:,:3])**2).mean((1,2)),
              ((vel[:,:,:3]-vel[:,:,6:9])**2).mean((1,2)),
              ((rot-trot)**2).mean((1,2,3)),
              ((vel[:,:,3:6]-vel[:,:,9:12])**2).mean((1,2))],-1)
weighted=raw*np.array([meta['loss_weights'][k] for k in meta['loss_term_names']])
np.testing.assert_allclose(weighted[1:],terms[1:],rtol=3e-5,atol=1e-5)
np.testing.assert_allclose(np.exp(-weighted[1:].sum(-1)),data[1:,2],rtol=4e-5,atol=1e-6)
payload=convert(a.recording,json.loads(a.geometry.read_text()),'verification_only')
vpos=np.array(payload['mse_target_positions'][0]);axes=np.array(payload['mse_target_basis'][0])
distances={}
for point in meta['target_deviation']['points']:
    i=meta['names'].index(point['body']);offset=np.array(point['offset'])
    actual=pose[:,i,:3]+rot[:,i]@offset;expected=target[:,i,:3]+trot[:,i]@offset
    rendered=vpos[:,i]+np.einsum('j,njk->nk',offset,axes[:,i])
    np.testing.assert_allclose(rendered,expected@WORLD_TO_VIEW.T,atol=1e-10,rtol=1e-10)
    distances[point['body']]=np.linalg.norm(actual-expected,axis=-1).tolist()
phase=np.array(meta['frame_phase'])
np.testing.assert_allclose(phase[:-1,4:6],phase[1:,:2],rtol=1e-5,atol=3e-6)
result=dict(passed=True,iteration=meta['iteration'],frames=len(pose),weighted_loss_max_error=float(abs(weighted[1:]-terms[1:]).max()),
    target_spheres_exact=True,phase_next_tick_verified=True,collider_count=len(payload['metadata']['physical_colliders']),
    terminal_flag=meta['terminal_flag'],last_collider_distance_m={k:v[-1] for k,v in distances.items()},
    training_noise=meta['training_action_noise_std'],replay_noise=meta['rollout_action_noise_std'])
a.output.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

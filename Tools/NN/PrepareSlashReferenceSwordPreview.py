"""Prepare forearm-length-only presentation and the existing sword's grip.

Does not modify the immutable rollout, viewer, NN, or sword mesh.
"""
import base64
import itertools
import json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/SlashChain'
HANDOFF=Path(r'C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260907_good_pt_continuous_random_30_hits_unreal_handoff')

def main():
    text=(HANDOFF/'variant_viewer.html').read_text(encoding='utf-8')
    payload=json.JSONDecoder().raw_decode(text[text.index('const payload = ')+len('const payload = '):])[0]
    sword=payload['sword']
    info=json.loads((OUT/'sword_mesh_info.json').read_text())
    source=np.frombuffer(base64.b64decode(sword['vertices_b64']),dtype='<f4').reshape(-1,3)*100
    mesh=np.array(info['vertices_cm'])
    source_center=(source.min(0)+source.max(0))/2
    mesh_center=(mesh.min(0)+mesh.max(0))/2
    tree=cKDTree(source)
    candidates=[]
    # Axis/unit conversion of the same FBX geometry, not a guessed hand offset.
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((-1,1),repeat=3):
            a=np.eye(3)[:,perm]*np.array(signs)
            b=source_center-mesh_center@a
            distances=tree.query(mesh@a+b)[0]
            candidates.append((float(np.mean(distances**2)),a,b))
    candidates.sort(key=lambda item:item[0])
    print('Best mesh/source axis fits:',[(round(score**.5,6),a.tolist()) for score,a,b in candidates[:4]],flush=True)
    score,a,b=candidates[0]
    assert score**.5<.6, 'Sword asset does not match reference geometry'
    m=np.array(sword['local_to_hand']).reshape(4,4)
    mirror=np.diag([1.,-1.,1.])
    linear=a@m[:3,:3]@mirror
    location=(b@m[:3,:3]+m[3,:3]*100)@mirror
    scale=np.linalg.norm(linear,axis=1)
    rotation=linear/scale[:,None]
    if np.linalg.det(rotation)<0:
        scale[0]*=-1; rotation[0]*=-1
    # An attached UE mesh has a TRS transform, not an arbitrary sheared matrix.
    # Preserve the grip translation and long blade axis exactly. Remove only
    # the source FBX's small transverse shear (not its authored scale).
    original_linear=linear.copy()
    rotation[0]-=np.dot(rotation[0],rotation[2])*rotation[2]
    rotation[0]/=np.linalg.norm(rotation[0])
    rotation[1]=np.cross(rotation[2],rotation[0])
    assert np.max(abs(rotation@rotation.T-np.eye(3)))<1e-5
    shear_residual_mm=float(np.max(np.linalg.norm(mesh@(original_linear-scale[:,None]*rotation),axis=1))*10)
    quaternion=Rotation.from_matrix(rotation.T).as_quat()
    data=json.loads((OUT/'animation_tracks.json').read_text())
    clamp_report={}
    for track in data['tracks']:
        name=track['name']
        if name not in info['hand_rest_local_cm']: continue
        original=np.array(track['positions'])
        rest=np.array(info['hand_rest_local_cm'][name])
        # The forearm decoder already aims its bone axis at the hand. Fixing the
        # child's local translation keeps that exact length even between keys.
        direction=original/np.linalg.norm(original,axis=1)[:,None]
        alignment=direction@(rest/np.linalg.norm(rest))
        assert alignment.min()>.99999, 'Unexpected forearm axis; do not rotate the arm silently'
        track['positions']=[rest.tolist()]*456
        clamp_report[name]={'rest_cm':float(np.linalg.norm(rest)),
            'original_min_cm':float(np.linalg.norm(original,axis=1).min()),
            'original_max_cm':float(np.linalg.norm(original,axis=1).max()),
            'minimum_direction_dot':float(alignment.min())}
    preview={'source_sha256':data['source_sha256'],'tracks':data['tracks'],'clamp':clamp_report,
             'sword':{'mesh':info['sword_mesh'],'bone':sword['hand_node'],
                 'location_cm':location.tolist(),'quaternion_xyzw':quaternion.tolist(),'scale':scale.tolist(),
                 'mesh_to_source_axes':a.tolist(),'mesh_to_source_offset_cm':b.tolist(),
                 'local_to_hand_source':sword['local_to_hand'],'mesh_fit_rms_cm':score**.5,
                 'source_shear_residual_mm':shear_residual_mm}}
    (OUT/'sword_preview.json').write_text(json.dumps(preview))
    print(json.dumps({k:v for k,v in preview.items() if k!='tracks'},indent=2))

if __name__=='__main__': main()

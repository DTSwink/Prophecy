"""Verify trim alignment, native completeness, source integrity and split isolation."""
import json, pickle
from pathlib import Path
import numpy as np
from prepare import OUT, DATASET, NATIVE, FOLDERS, ROOT, sha, atomic_json, load_dataset, read_motion


def main():
    collection=json.loads((OUT/'collection.json').read_text())
    assert sha(DATASET)==collection['dataset_sha256']
    before=json.loads((OUT/'dataset-before.json').read_text())
    _,after=load_dataset(DATASET)
    assert len(before['clips'])==12 and len(after)==474
    for old,new in zip(before['clips'],after[:12]):
        source=read_motion(DATASET.parent/old['file'],decode=False)
        trimmed=read_motion(Path(new['source']),decode=False)
        assert source.sha256==old['sha256']
        assert source.rows[420:]==trimmed.rows and source.dt==trimmed.dt
        src=pickle.loads(Path(old['robot_motion']).read_bytes())
        dst=pickle.loads(Path(new['robot_motion']).read_bytes())
        np.testing.assert_array_equal(src['frames'][420:],dst['frames'])
        assert src['fps']==dst['fps']==new['fps'] and dst['loop_mode']==0
        overlay=read_motion(Path(new['retargeted_from']),decode=False)
        assert overlay.count==trimmed.count and overlay.sha256==new['retarget_source_sha256']
    expected={str(p.resolve()) for folder in FOLDERS for p in (NATIVE/folder).glob('*.npz')}
    assert expected=={str(Path(c['native_npz']).resolve()) for c in after[12:]}
    for c in after[12:]:assert sha(c['native_npz'])==c['native_sha256']
    data=OUT/'data';manifest=json.loads((data/'dataset.json').read_text())
    assert sha(data/'features.npz')==manifest['features_sha256']
    counts={s:0 for s in ('train','validation','test')}
    with np.load(data/'features.npz') as arrays:
        for clip in manifest['clips']:
            used=[];i=clip['id']
            for s in counts:
                starts=arrays[f'{s}_starts_{i}'];assert len(starts)>0
                poses=set((starts[:,None]+np.arange(3)[None,:]).flatten().tolist())
                assert not any(poses&prev for prev in used);used.append(poses)
                x=arrays[f'{s}_{i}'];assert x.shape==(len(starts),405) and np.isfinite(x).all()
                counts[s]+=len(x)
            assert sha(clip['robot_motion'])==clip['robot_sha256']
        training=np.concatenate([arrays[f'train_{i}'] for i in range(474)])
        np.testing.assert_allclose(training.mean(0,dtype=np.float64),arrays['mean'],atol=2e-7)
    assert sha(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml')==collection['model_sha256']
    result=dict(passed=True,clips=474,trimmed_clips=12,removed_frames_each=420,native_clips=462,
        original_files_unchanged=True,bvh_robot_overlay_alignment=True,all_four_native_folders_complete=True,
        disjoint_pose_frames_per_clip=True,train_only_normalization=True,windows=counts,
        total_duration_seconds=collection['duration_seconds'],model_unchanged=True)
    atomic_json(OUT/'verification.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()

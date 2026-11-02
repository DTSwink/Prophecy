"""Apply the explicitly user-approved editor pose; preserve other native clips."""
import json,pickle,hashlib,shutil
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitSlowLoco'; P=OUT/'package'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    saved=OUT/'pose-editor/current.json'; choice=json.loads(saved.read_text())
    assert choice['saved_utc']=='2026-10-31T17:53:22.817861+00:00'
    f=np.asarray(choice['frame'],dtype=np.float64)
    assert f.shape==(40,) and np.isfinite(f).all()
    dest=OUT/'user-pose-20261031';dest.mkdir(exist_ok=True)
    shutil.copy2(saved,dest/'approved-pose.json')
    manifest=json.loads((OUT/'retarget-repair-20261031/before/manifest.json').read_text())
    for row in manifest['motions']:
        name=row['id'];original=OUT/'retarget-repair-20261031/before/motions'/(name+'.pkl')
        target=P/'motions'/(name+'.pkl')
        if name=='sitting':
            motion=pickle.loads(original.read_bytes());motion['frames']=np.tile(f,(len(motion['frames']),1));motion['loop_mode']=1
            target.write_bytes(pickle.dumps(motion))
            assert np.array_equal(pickle.loads(target.read_bytes())['frames'],np.tile(f,(50,1)))
            row['user_pose']={'receipt':str(dest/'approved-pose.json'),'sha256':sha(saved),'static_pose':True}
        else:
            shutil.copy2(original,target);assert sha(target)==sha(original)
        row['training_sha256']=sha(target)
        row.pop('retarget_repair',None)
    (P/'prepared/manifest.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'prepared/manifest.json').write_text(json.dumps(manifest,indent=2).replace('/workspace/mimickit_trial',P.resolve().as_posix()))
    receipt=dict(approved_pose_sha256=sha(saved),saved_utc=choice['saved_utc'],exact_saved_pose_all_50_frames=True,other_seven_byte_identical=True,
                 saved_pose_validation=choice['validation'],motions={r['id']:r['training_sha256'] for r in manifest['motions']})
    (dest/'application.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps({k:v for k,v in receipt.items() if k!='saved_pose_validation'}))
if __name__=='__main__':main()

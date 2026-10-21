"""Isolated crawl package from the deployed loco snapshot. Never alters loco/Unreal."""
from pathlib import Path
import hashlib
import json
import pickle
import shutil
import sys
import zipfile
import numpy as np
from scipy.spatial.transform import Rotation as R
import yaml

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitCrawl'
PACKAGE=OUT/'package'
REMOTE='/workspace/mimickit_trial'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2),encoding='utf-8')

from current_phat import sync_current_phat


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if PACKAGE.exists():raise RuntimeError('Package already exists; inspect before rebuilding')
    baseline=ROOT/'Saved/MimicKitEquipment/source.zip'
    with zipfile.ZipFile(baseline) as archive:
        for name in archive.namelist():
            # Copy code/assets and configuration, not the 50 locomotion clips.
            if name.startswith(('MimicKit/','pipeline/','assets/','prepared/')):
                destination=(PACKAGE/name).resolve()
                assert destination.is_relative_to(PACKAGE.resolve())
                destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes(archive.read(name))
    asset=PACKAGE/'assets/uefn';meta=sync_current_phat(asset)
    from patch_runtime import patch,patch_contact_capacity
    patch(PACKAGE);patch_contact_capacity(PACKAGE)
    pointer=json.loads((ROOT/'Saved/RoboticCrawlAE/current-run.json').read_text(encoding='utf-8-sig'))
    ae_run=Path(pointer['run']);done=json.loads((ae_run/'completed.json').read_text())
    assert done['clip_count']==4 and done['state']=='complete'
    manifest=json.loads((ae_run/'data/dataset.json').read_text(encoding='utf-8'))
    names=manifest['body_names'];motions=PACKAGE/'motions';motions.mkdir()
    rows=[]
    corrections=json.loads((OUT/'corrected-references/report.json').read_text())
    assert [r['id'] for r in corrections['motions']]==['crawl','crawl_idle']
    for i,correction in enumerate(corrections['motions']):
        clip=manifest['clips'][i+2]
        assert correction['original_sha256']==clip['robot_sha256']
        original=Path(correction['file']);assert sha(original)==correction['sha256']
        motion=pickle.loads(original.read_bytes());frames=np.array(motion['frames'],copy=True)
        # One global rigid transform removes arbitrary source heading/location.
        # All articulated poses, movement and internal turns remain unchanged.
        forward=-(R.from_rotvec(frames[0,3:6]).as_matrix()[:2,0])
        yaw=float(np.arctan2(forward[1],forward[0]));turn=R.from_euler('z',-yaw)
        start=frames[0,:3].copy();start[2]=0
        frames[:,:3]=turn.apply(frames[:,:3]-start)
        frames[:,3:6]=(turn*R.from_rotvec(frames[:,3:6])).as_rotvec()
        motion.update(frames=frames,loop_mode=1)
        label=correction['id']
        dest=motions/(label+'.pkl');dest.write_bytes(pickle.dumps(motion))
        rows.append(dict(id=label,file=REMOTE+'/motions/'+dest.name,label=clip['label'],
            gait=-1 if label=='crawl_idle' else 0,direction=[1.,0.],sword_drawn=False,phase_offset=0.,
            duration=(len(frames)-1)/motion['fps'],source=str(original),source_sha256=sha(original),
            frames=len(frames),fps=motion['fps'],initial_yaw_removed_rad=yaw,loop_mode='WRAP'))
    prepared=PACKAGE/'prepared'
    configs={n:yaml.safe_load((prepared/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')}
    configs['env'].update(crawl_task=True,idle_row_fraction=.04,arm_injuries_enabled=False,
        contact_bodies=[],pose_termination=False,enable_early_termination=False)
    configs['env'].pop('adaptive_motion_rows',None)
    # Only Omni's 27cm collider-target failure and ordinary timeout; both clips loop.
    write(prepared/'manifest.json',dict(body_names=names,motions=rows))
    (prepared/'motions.yaml').write_text(yaml.safe_dump(dict(motions=[dict(file=r['file'],weight=1.) for r in rows])))
    for n,c in configs.items():(prepared/(n+'_config.yaml')).write_text(yaml.safe_dump(c,sort_keys=False))
    shutil.copy2(Path(__file__).with_name('crawl_env.py'),PACKAGE/'pipeline/crawl_env.py')
    train=PACKAGE/'pipeline/train.py';text=train.read_text()
    assert "from omni_walk import OmniWalkEnv" in text
    text=text.replace("from omni_walk import OmniWalkEnv","from crawl_env import CrawlEnv as OmniWalkEnv")
    text=text.replace("assert config['idle_row_fraction']==.06 and agent_config['model']['auto_phase_unit_output']",
                      "assert config['crawl_task'] and config['idle_row_fraction']==.04 and agent_config['model']['auto_phase_unit_output']")
    train.write_text(text)
    recorder=PACKAGE/'pipeline/observe_many.py';text=recorder.read_text()
    text=text.replace("auto_phase_feedback=False))","auto_phase_feedback=False,limb_enabled=self.env._limb_enabled[w].cpu().tolist(),crawl_task=True))")
    recorder.write_text(text)
    from replay_selection import patch as patch_replay
    patch_replay(PACKAGE)
    local=OUT/'prepared';local.mkdir()
    for n,c in configs.items():
        payload=yaml.safe_dump(c,sort_keys=False).replace(REMOTE,PACKAGE.as_posix())
        (local/(n+'_config.yaml')).write_text(payload)
    # Local configs use the same motion/manifest documents with rewritten paths.
    for name in ('motions.yaml','manifest.json'):
        (local/name).write_text((prepared/name).read_text().replace(REMOTE,PACKAGE.as_posix()))
    env=yaml.safe_load((local/'env_config.yaml').read_text())
    env.update(motion_file=(local/'motions.yaml').as_posix(),omni_manifest=(local/'manifest.json').as_posix())
    (local/'env_config.yaml').write_text(yaml.safe_dump(env,sort_keys=False))
    shutil.copy2(ROOT/'Saved/MimicKitEquipment/geometry.json',OUT/'geometry.json')
    write(OUT/'preparation.json',dict(baseline_source=str(baseline),baseline_sha256=sha(baseline),
        ae_run=str(ae_run),ae_used_for_reward=False,motions=rows,only_two_uefn_clips=True,policy_lafan_clips=0,
        limbs='four constant enabled flags; no disabling',observations=153,motors=34,
        idle_worlds=20,crawl_worlds=492,requested_idle_fraction=.04,actual_idle_fraction=20/512,
        fresh_policy=True,local_preparation_only=True))
    # Read-only admissibility audit, never clamp the user's reference motions.
    sys.path[:0]=[str(ROOT/'Labs/LafanCutter')]
    import retarget_crawls as rt
    model=rt.MJCFCharModel('cpu');model.load(str(asset/'humanoid_uefn.xml'))
    audit=[]
    for row in rows:
        frames=pickle.loads((motions/(row['id']+'.pkl')).read_bytes())['frames']
        joints=[]
        for joint in meta['joints']:
            coords,_=rt.sampled_coordinates(model,joint,frames,1)
            joints.append(dict(body=joint['body'],outside_frames=int(rt.violation(coords,joint).sum()),frames=len(frames)))
        audit.append(dict(id=row['id'],joints=joints))
    write(OUT/'reference-limit-audit.json',audit)
    print(json.dumps(dict(prepared=str(local),current_phat=True,motions=len(rows),audit=audit)))

if __name__=='__main__':main()

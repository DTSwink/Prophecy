"""Build an isolated unperturbed slow-loco package on the retained current runtime."""
from pathlib import Path
import json, pickle, shutil, re, hashlib, zipfile
import yaml
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitSlowLoco'
P=OUT/'package'
REMOTE='/workspace/mimickit_trial'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    old=ROOT/'Saved/MimicKitCrawl/package'
    prepared=P/'prepared';prepared.mkdir(exist_ok=False)
    motions=P/'motions';motions.mkdir(exist_ok=True)
    source=ROOT/'Saved/RoboticMotionAE/20261031_slowloco/data/dataset.json'
    dataset=json.loads(source.read_text());rows=[]
    repair_dir=OUT/'retarget-repair-20261031'
    accepted=json.loads((repair_dir/'accepted.json').read_text()) if (repair_dir/'accepted.json').exists() else None
    if accepted and not accepted.get('automatic_reuse_allowed',False):accepted=None
    prior_manifest=json.loads((repair_dir/'before/manifest.json').read_text()) if accepted else None
    labels=['crawl','crawl_idle','agonising','agonising_idle','limpL','limpR','lying','sitting']
    for label,entry in zip(labels,dataset['clips'][2:]):
        path=Path(entry['robot_motion']);assert sha(path)==entry['robot_sha256']
        motion=pickle.loads(path.read_bytes());assert motion['loop_mode']==0
        repair_info=None
        if accepted:
            original=next(r for r in prior_manifest['motions'] if r['id']==label)
            assert sha(path)==original['source_sha256'],'Native source changed; collision-aware retarget must be rebuilt'
            candidate=repair_dir/'candidates'/(label+'.pkl')
            verified=next(r for r in accepted['motions'] if r['id']==label)
            assert sha(candidate)==verified['sha256']
            motion=pickle.loads(candidate.read_bytes());repair_info=dict(receipt=str(repair_dir/'accepted.json'),sha256=sha(candidate))
        motion['loop_mode']=1
        dest=motions/(label+'.pkl');dest.write_bytes(pickle.dumps(motion))
        rows.append(dict(id=label,label=label,file=REMOTE+'/motions/'+dest.name,
            gait=-1 if label in ('crawl_idle','agonising_idle','lying','sitting') else 0,
            direction=[1.,0.],sword_drawn=False,phase_offset=0.,duration=(len(motion['frames'])-1)/motion['fps'],
            frames=len(motion['frames']),fps=motion['fps'],source=str(path),source_sha256=sha(path),loop_mode='WRAP'))
        if repair_info:rows[-1]['retarget_repair']=repair_info
        rows[-1]['training_sha256']=sha(dest)
    configs={n:yaml.safe_load((old/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','agent','engine')}
    configs['env'].update(slow_loco_task=True,idle_row_fraction=.5,crawl_task=False)
    configs['agent'].update(iters_per_output=100,iters_per_log=10)
    # Fresh simple tracking policy: original crawl objective/optimizer; current optimized simulator.
    for n,c in configs.items():(prepared/(n+'_config.yaml')).write_text(yaml.safe_dump(c,sort_keys=False))
    (prepared/'manifest.json').write_text(json.dumps(dict(body_names=dataset['body_names'],motions=rows),indent=2))
    (prepared/'motions.yaml').write_text(yaml.safe_dump(dict(motions=[dict(file=r['file'],weight=1.) for r in rows])))
    shutil.copy2(Path(__file__).with_name('slow_loco_env.py'),P/'pipeline/slow_loco_env.py')
    shutil.copy2(old/'pipeline/omni_policy.py',P/'pipeline/omni_policy.py')
    path=P/'pipeline/train.py';t=path.read_text();anchor='        from omni_walk import OmniWalkEnv\n'
    assert t.count(anchor)==1
    t=t.replace(anchor,anchor+'        if config.get("slow_loco_task"):\n            from slow_loco_env import SlowLocoEnv as OmniWalkEnv\n')
    path.write_text(t)
    path=P/'pipeline/omni_walk.py';t=path.read_text()
    a='idle_layout(config, self.get_num_envs())[0]/self.get_num_envs()'
    assert a in t
    path.write_text(t.replace(a,"(config['idle_row_fraction'] if config.get('slow_loco_task') else "+a+")"))
    # Per-world torque bounds enter the actual coupled motor solve and every residual check.
    folder=P/'assets/MimicKitTransfer'
    p=folder/'contact_manifolds_gpu.py';t=p.read_text()
    assert 'if p.size[w,g]>4:error[w]=7' in t
    p.write_text(t.replace('if p.size[w,g]>4:error[w]=7','if p.size[w,g]>p.contact_ids.shape[1]:error[w]=7'))
    for filename in ('sequential_contact_gpu.py','block_contact_gpu.py','coupled_contact_gpu.py'):
        p=folder/filename;t=p.read_text()
        t=re.sub(r'\b([pq])\.caps\[(a|index)\]',r'(\1.caps[\2]*\1.motor_enabled[w,\2])',t)
        if filename=='sequential_contact_gpu.py':
            t=t.replace('    caps: wp.array(dtype=float)','    caps: wp.array(dtype=float)\n    motor_enabled: wp.array2d(dtype=float)')
        p.write_text(t)
    p=folder/'sequential_contact_adapter.py';t=p.read_text();a='p.caps=motor.upper'
    assert t.count(a)==1
    t=t.replace(a,a+'\n        p.motor_enabled=wp.ones((n,len(motor.ids)),dtype=float,device=data.qvel.device)')
    p.write_text(t)
    local=OUT/'prepared';local.mkdir(exist_ok=True)
    for p in prepared.iterdir():
        (local/p.name).write_text(p.read_text().replace(REMOTE,P.resolve().as_posix()))
    env=yaml.safe_load((local/'env_config.yaml').read_text())
    env.update(motion_file=(local/'motions.yaml').resolve().as_posix(),omni_manifest=(local/'manifest.json').resolve().as_posix())
    (local/'env_config.yaml').write_text(yaml.safe_dump(env,sort_keys=False))
    shutil.copy2(ROOT/'Saved/MimicKitCrawl/geometry.json',OUT/'geometry.json')
    (OUT/'preparation.json').write_text(json.dumps(dict(policy_clips=labels,observations=160,worlds=2048,
        fresh=True,perturbations=False,ae_reward=False,per_clip_rows=256,disabled={'limpL':'left leg','limpR':'right leg'},
        reference_policy='Original frame data with WRAP playback; random reference-frame starts; standard locomotion cycle translation',
        source_dataset=str(source)),indent=2))
    print('prepared isolated slow loco')

if __name__=='__main__':main()

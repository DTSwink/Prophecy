"""Verified corrected-crawl/limp-radius continuation on the retained slow-loco pod."""
import json,sys,shutil,time,zipfile,io
import deploy_contact_cleanup as c
from deploy_saved_sitting import remote
d=c.d;OUT=d.OUT;P=d.P;D=OUT/'reference-upper-deploy-20261101';c.D=D
write=d.write

def snapshot():
    D.mkdir(exist_ok=True)
    assert not (D/'previous-run.json').exists(),'Snapshot exists; reconcile it'
    active=json.loads((OUT/'active_run.json').read_text());assert active['pod']=='5xs589fdlcb7nr'
    pod=d.cloud.rp.request_json('GET','/pods/'+active['pod'])
    assert pod['desiredStatus']=='RUNNING' and float(pod['costPerHr'])<=.28
    inv=json.loads(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/source-inventory.json').read_text())"))
    assert {n:d.sha(P/n) for n in inv}==inv,'Local package has unaccounted changes'
    write(D/'previous-run.json',active);write(D/'previous-inventory.json',inv)
    for rel in ['pipeline/slow_loco_env.py','motions/crawl.pkl','prepared/manifest.json']:
        dst=D/'before-package'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/rel,dst)
    for name in ['source-receipt.json','preflight.json']:
        shutil.copy2(OUT/name,D/('previous-'+name))
    write(D/'provider-before.json',{k:pod.get(k) for k in ['id','desiredStatus','costPerHr','gpuDisplayName']})
    print('Current run and exact deployed package captured; GPU/trainer unchanged',flush=True)

def promote():
    validation=json.loads((c.REVIEW/'validation.json').read_text())
    physics=json.loads((c.REVIEW/'physics-reset-check-after.json').read_text())
    assert validation['contact_checks_passed']
    changes=[]
    for name in c.NAMES:
        src=c.REVIEW/'candidates'/f'{name}.pkl'
        assert d.sha(src)==validation['motions'][name]['candidate_sha256']==physics['input_sha256'][name]
        changes.append(dict(motion=name,sha256=d.sha(src)))
        if d.sha(src)!=d.sha(P/'motions'/src.name):shutil.copy2(src,P/'motions'/src.name)
    for manifest_path in [P/'prepared/manifest.json',OUT/'prepared/manifest.json']:
        manifest=json.loads(manifest_path.read_text())
        for row in manifest['motions']:
            row['training_sha256']=d.sha(P/'motions'/(row['id']+'.pkl'))
            if row['id']=='crawl':row['contact_cleanup']='20261101_reference_hands_head'
        write(manifest_path,manifest)
    shutil.copy2(d.ROOT/'Labs/RoboticMotionAE/slow_loco_env.py',P/'pipeline/slow_loco_env.py')
    write(D/'motion-promotion.json',dict(motions=changes,prepared_unix=time.time()))
    print('Validated motion files and limp-foot radius code promoted locally',flush=True)

def stage():
    old=json.loads((D/'previous-inventory.json').read_text());new={n:d.sha(P/n) for n in old}
    diff={n for n in old if old[n]!=new[n]}
    assert diff=={'motions/crawl.pkl','prepared/manifest.json','pipeline/slow_loco_env.py','pipeline/observe.py'},diff
    check=json.loads((D/'preflight-verified.json').read_text())
    assert check['approved_motion_hashes']=={n:d.sha(P/'motions'/f'{n}.pkl') for n in c.NAMES}
    assert json.loads((OUT/'limp-radius-termination-test.json').read_text())['passed']
    d.bundle();shutil.copy2(OUT/'source-receipt.json',D/'source-receipt.json')
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'source.zip',c.REMOTE+'/contact-source.zip',timeout=90)
    assert remote("import hashlib;print(hashlib.sha256(open('/workspace/mimickit_trial/contact-source.zip','rb').read()).hexdigest())").strip()==d.sha(OUT/'source.zip')
    write(D/'staged.json',dict(source_sha256=d.sha(OUT/'source.zip'),changed_files=sorted(diff),staged_unix=time.time()))
    print('Source archive staged, persistent and remote hashes verified',flush=True)

def verify():
    import torch
    result=c.audit();history=json.loads((D/'advancing-statuses.json').read_text())
    assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
    assert result['status']['worlds']==2048 and result['status']['state']=='training'
    saved=json.loads((D/'resume-checkpoint.json').read_text())
    with zipfile.ZipFile(saved['local']) as z:state=torch.load(io.BytesIO(z.read('resume_state.pt')),map_location='cpu',weights_only=False)
    assert result['resume']['prior_samples']==state['samples']
    assert result['resume']['iteration_offset']==state['completed_iteration']+1
    assert result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
    assert result['model']['_obs_norm._mean']==[160]
    assert all(result['model'][k][1]==160 for k in ['_model._actor_layers.0.weight','_model._critic_layers.0.weight'])
    assert {r['motion_name'] for r in result['replay_rows']}==set(c.NAMES)
    for row in result['replay_rows']:
        assert row['capture_source']=='actual_newton_physics' and row['motion_loop_modes']=={n:1 for n in c.NAMES}
        expected=[1.,1.,0.,1.] if row['motion_name']=='limpR' else [1.,1.,1.,0.] if row['motion_name']=='limpL' else [1.]*4
        assert row['limb_enabled']==expected
    termination=json.loads(remote(f"import json;from pathlib import Path;e=json.loads(Path('/workspace/mimickit_trial/runs/{result['run']}/evaluation.json').read_text());print(json.dumps([dict(motion=r['motion_name'],rule=r['target_deviation']) for r in e['replay']['replay_rows']]))"))
    for row in termination:
        expected=row['rule']['radius_by_motion_m'][row['motion']]
        assert {p['body']:p['radius_m'] for p in row['rule']['points']}=={b:r for b,r in expected.items() if r is not None}
    write(D/'live-termination-metadata.json',termination)
    d.verify()
    write(D/'deployment-verified.json',dict(verified=True,run=result['run'],resume_checkpoint=saved['local'],source_sha256=json.loads((D/'staged.json').read_text())['source_sha256'],motion_hashes=result['motion_hashes'],status=result['status'],advancing_statuses=history,persistent_backup_verified=True,verified_unix=time.time()))
    print('Corrected crawl continuation fully verified',flush=True)

preflight=c.preflight
stop=c.stop
preserve=c.preserve
launch=c.launch
audit=c.audit
status=c.status
if __name__=='__main__':globals()[sys.argv[1]]()

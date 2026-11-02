"""Temporary equal limpL/limpR curriculum, retained GPU continuation."""
import json,sys
import deploy_limp_strength as s
from deploy_saved_sitting import remote
D=s.OUT/'limps-only-deploy-20261101';s.D=D;s.r.D=D;s.c.D=D
snapshot=s.snapshot
preflight=s.preflight
stop=s.stop
launch=s.launch
status=s.status
audit=s.audit


def stage():
    import shutil
    d=s.r.d
    old=json.loads((D/'previous-inventory.json').read_text())
    diff={n for n in old if old[n]!=d.sha(s.P/n)}
    assert diff=={'pipeline/slow_loco_env.py','pipeline/observe_many.py','prepared/env_config.yaml','pipeline/train.py'},diff
    check=json.loads((D/'preflight-verified.json').read_text())
    assert check['passed'] and check['replay_rows']==2
    assert check['metadata']['motion_sampling']['counts']==dict(crawl=0,crawl_idle=0,agonising=0,agonising_idle=0,limpL=32,limpR=32,lying=0,sitting=0)
    d.bundle();shutil.copy2(s.OUT/'source-receipt.json',D/'source-receipt.json')
    d.cloud.rp.scp(d.cloud.state()['connection'],s.OUT/'source.zip',s.c.REMOTE+'/contact-source.zip',timeout=90)
    assert remote("import hashlib;print(hashlib.sha256(open('/workspace/mimickit_trial/contact-source.zip','rb').read()).hexdigest())").strip()==d.sha(s.OUT/'source.zip')
    s.write(D/'staged.json',dict(source_sha256=d.sha(s.OUT/'source.zip'),changed_files=sorted(diff)))
    print('Limp-only source staged and verified; GPU/trainer unchanged',flush=True)

def verify():
    import torch,zipfile,io,time
    c=s.c;d=s.r.d;OUT=s.OUT;P=s.P;write=s.write
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
    assert {r['motion_name'] for r in result['replay_rows']}=={'limpL','limpR'}
    for row in result['replay_rows']:
        assert row['capture_source']=='actual_newton_physics' and row['motion_loop_modes']=={n:1 for n in c.NAMES}
        expected=[1.,1.,0.,1.] if row['motion_name']=='limpR' else [1.,1.,1.,0.] if row['motion_name']=='limpL' else [1.]*4
        assert row['limb_enabled']==expected
    termination=json.loads(remote(f"import json;from pathlib import Path;e=json.loads(Path('/workspace/mimickit_trial/runs/{result['run']}/evaluation.json').read_text());print(json.dumps([dict(motion=r['motion_name'],rule=r['target_deviation']) for r in e['replay']['replay_rows']]))"))
    for row in termination:
        expected=row['rule']['radius_by_motion_m'][row['motion']]
        assert {p['body']:p['radius_m'] for p in row['rule']['points']}=={b:r for b,r in expected.items() if r is not None}
    write(D/'live-termination-metadata.json',termination)
    extra=json.loads(remote(f"import json;from pathlib import Path;e=json.loads(Path('/workspace/mimickit_trial/runs/{result['run']}/evaluation.json').read_text());print(json.dumps([dict(sampling=x['motion_sampling'],strength=x['limp_support_strength'],mask=x['disabled_leg_mse']) for x in e['replay']['replay_rows']]))"))
    expected=json.loads((D/'preflight-verified.json').read_text())['metadata']
    assert len(extra)==2
    for row in extra:
        assert row['sampling']['counts']==dict(crawl=0,crawl_idle=0,agonising=0,agonising_idle=0,limpL=1024,limpR=1024,lying=0,sitting=0)
        assert row['sampling']['preserved_motion_onehot_order']==expected['motion_onehot_order']
        assert row['strength']==expected['limp_support_strength']
        assert row['mask']==expected['disabled_leg_mse']
    write(D/'live-sampling-metadata.json',extra)
    d.verify()
    write(D/'deployment-verified.json',dict(verified=True,run=result['run'],resume_checkpoint=saved['local'],source_sha256=json.loads((D/'staged.json').read_text())['source_sha256'],motion_hashes=result['motion_hashes'],status=result['status'],advancing_statuses=history,persistent_backup_verified=True,verified_unix=time.time()))
    print('Limp-only continuation fully verified; GPU retained',flush=True)

def preserve():
 import zipfile
 d=s.r.d;OUT=s.OUT;P=s.P;REMOTE=s.c.REMOTE;write=s.write
 old=json.loads((D/'previous-run.json').read_text())['run']
 info=json.loads(remote(f'''import json,hashlib
from pathlib import Path
r=Path('{REMOTE}');name={old!r};p=r/'runs'/name;x=json.loads((r/(name+'-launch.json')).read_text());cmd=Path('/proc')/str(x['pid'])/'cmdline'
assert not cmd.exists() or name.encode() not in cmd.read_bytes(),'Old trainer still running'
assert (p/'finished.json').exists()
b=json.loads((p/'backup_status.json').read_text());cp=p/b['key'].split('/')[-1]
assert cp.name.endswith('_final.zip'),cp
assert hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256']
print(json.dumps(dict(backup=b,path=str(cp),finished=json.loads((p/'finished.json').read_text()))))
'''))
 b=info['backup'];folder=OUT/'preserved-latest'/old;folder.mkdir(parents=True,exist_ok=True);cp=folder/b['key'].split('/')[-1]
 stream=d.cloud.s3().get_object(Bucket=d.cloud.rp.VOLUME_ID,Key=b['key'])['Body'];temp=cp.with_suffix('.zip.part')
 with temp.open('wb') as f:
  for block in iter(lambda:stream.read(1024*1024),b''):f.write(block)
 stream.close();assert d.sha(temp)==b['sha256'];temp.replace(cp)
 with zipfile.ZipFile(cp) as z:
  assert z.testzip() is None and {'model.pt','resume_state.pt'}<=set(z.namelist())
  import yaml
  for n in ['env_config.yaml','engine_config.yaml','agent_config.yaml']:
   previous=yaml.safe_load(z.read(n));current=yaml.safe_load((P/'prepared'/n).read_text())
   if n=='env_config.yaml':
    assert current.pop('slow_loco_motion_subset')==['limpL','limpR']
    previous.pop('slow_loco_motion_subset',None)
   assert previous==current,n
 write(D/'resume-checkpoint.json',dict(**info,local=str(cp),sha256=d.sha(cp),verified=True))
 print('Latest final checkpoint preserved locally and persistent:',cp.name,flush=True)
 return info

s.c.preserve=preserve

if __name__=='__main__':globals()[sys.argv[1]]()

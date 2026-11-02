"""Promote reviewed slow-loco targets and continue latest on the retained GPU."""
import json,pickle,shutil,sys,time,zipfile,hashlib,shlex
from pathlib import Path
import deploy_slow_policy as d
from deploy_saved_sitting import remote

OUT=d.OUT; P=d.P; REVIEW=OUT/'contact-cleanup-20261031'
D=OUT/'contact-cleanup-deploy-20261031'; REMOTE='/workspace/mimickit_trial'
NAMES=['crawl','crawl_idle','agonising','agonising_idle','limpL','limpR','lying','sitting']
write=d.write

def prepare():
 D.mkdir(exist_ok=True)
 active=json.loads((OUT/'active_run.json').read_text());assert active['pod']=='5xs589fdlcb7nr'
 assert not (D/'previous-run.json').exists(),'Already prepared; reconcile receipt instead of overwriting'
 pod=d.cloud.rp.request_json('GET','/pods/'+active['pod'])
 assert pod['desiredStatus']=='RUNNING' and float(pod['costPerHr'])<=.28
 oldinv=json.loads(remote(f"from pathlib import Path;print(Path('{REMOTE}/source-inventory.json').read_text())"))
 local={n:d.sha(P/n) for n in oldinv}
 assert local==oldinv,'Local source differs from running package before target promotion'
 validation=json.loads((REVIEW/'validation.json').read_text());physics=json.loads((REVIEW/'physics-reset-check-after.json').read_text())
 assert validation['contact_checks_passed']
 changes=[]
 for name in NAMES:
  path=REVIEW/'candidates'/f'{name}.pkl';j=validation['motions'][name]
  assert d.sha(path)==j['candidate_sha256']==physics['input_sha256'][name]
  assert d.sha(P/'motions'/path.name)==j['source_sha256']
  m=pickle.loads(path.read_bytes());assert m['loop_mode']==1 and m['frames'].shape[1]==40
  changes.append(dict(motion=name,old_sha256=j['source_sha256'],new_sha256=d.sha(path),frames=len(m['frames']),fps=m['fps'],duration=(len(m['frames'])-1)/m['fps']))
 write(D/'previous-run.json',active);write(D/'previous-inventory.json',oldinv)
 write(D/'provider-before.json',{k:pod.get(k) for k in ['id','desiredStatus','costPerHr','gpuDisplayName']})
 for rel in [f'motions/{n}.pkl' for n in NAMES]+['prepared/manifest.json']:
  target=D/'before-package'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/rel,target)
 shutil.copy2(OUT/'source-receipt.json',D/'previous-source-receipt.json')
 shutil.copy2(OUT/'preflight.json',D/'previous-preflight.json')
 shutil.copy2(OUT/'prepared/manifest.json',D/'previous-local-manifest.json')
 for name in NAMES:shutil.copy2(REVIEW/'candidates'/f'{name}.pkl',P/'motions'/f'{name}.pkl')
 for path in [P/'prepared/manifest.json',OUT/'prepared/manifest.json']:
  manifest=json.loads(path.read_text());assert [x['id'] for x in manifest['motions']]==NAMES
  for row,change in zip(manifest['motions'],changes):
   row.update(training_sha256=change['new_sha256'],frames=change['frames'],fps=change['fps'],duration=change['duration'],contact_cleanup='20261031_cycle_ik_approved')
  write(path,manifest)
 write(D/'motion-promotion.json',dict(previous_run=active['run'],motions=changes,prepared_unix=time.time(),source_settings_unchanged=True))
 print(json.dumps(dict(pod=active['pod'],cost_per_hour=pod['costPerHr'],promoted=changes)),flush=True)

def refresh():
 """Refresh the prepared package after a correction during a held handover."""
 assert json.loads((OUT/'active_run.json').read_text())['state']=='trainer_stopped_gpu_retained'
 validation=json.loads((REVIEW/'validation.json').read_text())
 physics=json.loads((REVIEW/'physics-reset-check-after.json').read_text())
 assert validation['contact_checks_passed']
 promotion=json.loads((D/'motion-promotion.json').read_text())
 changes=[]
 for name in NAMES:
  path=REVIEW/'candidates'/f'{name}.pkl';j=validation['motions'][name]
  assert d.sha(path)==j['candidate_sha256']==physics['input_sha256'][name]
  m=pickle.loads(path.read_bytes());assert m['loop_mode']==1 and m['frames'].shape[1]==40
  changes.append(dict(motion=name,old_sha256=j['source_sha256'],new_sha256=d.sha(path),frames=len(m['frames']),fps=m['fps'],duration=(len(m['frames'])-1)/m['fps']))
 for name in NAMES:shutil.copy2(REVIEW/'candidates'/f'{name}.pkl',P/'motions'/f'{name}.pkl')
 for path in [P/'prepared/manifest.json',OUT/'prepared/manifest.json']:
  manifest=json.loads(path.read_text());assert [x['id'] for x in manifest['motions']]==NAMES
  for row,change in zip(manifest['motions'],changes):
   row.update(training_sha256=change['new_sha256'],frames=change['frames'],fps=change['fps'],duration=change['duration'],contact_cleanup='20261031_cycle_ik_head_fixed')
  write(path,manifest)
 promotion.update(motions=changes,head_correction_unix=time.time())
 write(D/'motion-promotion.json',promotion)
 print('Validated eight review candidates promoted, including corrected crawl head',flush=True)

def preflight():
 import preflight_slow_policy as p
 target=D/'preflight';(target/'prepared').mkdir(parents=True,exist_ok=True)
 for x in (OUT/'prepared').iterdir():
  if x.is_file():shutil.copy2(x,target/'prepared'/x.name)
 shutil.copy2(OUT/'geometry.json',target/'geometry.json');p.out=target;p.main()
 report=json.loads((target/'preflight.json').read_text());assert report['passed']
 report['approved_motion_hashes']={n:d.sha(P/'motions'/f'{n}.pkl') for n in NAMES}
 write(OUT/'preflight.json',report);write(D/'preflight-verified.json',report)

def stage():
 old=json.loads((D/'previous-inventory.json').read_text())
 new={n:d.sha(P/n) for n in old};diff={n for n in old if old[n]!=new[n]}
 assert diff=={f'motions/{n}.pkl' for n in NAMES}|{'prepared/manifest.json'},diff
 check=json.loads((D/'preflight-verified.json').read_text())
 assert check['approved_motion_hashes']=={n:d.sha(P/'motions'/f'{n}.pkl') for n in NAMES}
 d.bundle();shutil.copy2(OUT/'source-receipt.json',D/'source-receipt.json')
 d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'source.zip',REMOTE+'/contact-source.zip',timeout=90)
 assert remote(f"import hashlib;print(hashlib.sha256(open('{REMOTE}/contact-source.zip','rb').read()).hexdigest())").strip()==d.sha(OUT/'source.zip')
 write(D/'staged.json',dict(source_sha256=d.sha(OUT/'source.zip'),changed_files=sorted(diff),staged_unix=time.time()))
 print('Corrected targets staged and remote SHA verified; trainer state unchanged',flush=True)

def stop():
 assert (D/'staged.json').exists();old=json.loads((D/'previous-run.json').read_text())
 code=f'''import json,os,signal,time
from pathlib import Path
r=Path('{REMOTE}');name={old['run']!r};x=json.loads((r/(name+'-launch.json')).read_text())
assert name.encode() in (Path('/proc')/str(x['pid'])/'cmdline').read_bytes()
g=Path('/proc')/str(x['exit_guard_pid'])/'cmdline'
if g.exists() and name.encode() in g.read_bytes():os.kill(x['exit_guard_pid'],signal.SIGTERM)
c=json.loads((r/'runtime_control.json').read_text());c.update(hard_stop_unix=time.time()+1200,setup_watchdog=True,until_stopped=False)
(r/'runtime_control.json').write_text(json.dumps(c))
(r/'runs'/name/'stop.request').write_text('User approved corrected contact targets; graceful final checkpoint, retain GPU')
print(json.dumps(dict(run=name,trainer=x['pid'],graceful_stop_requested=True,gpu_retained=True)))
'''
 result=json.loads(remote(code));write(D/'handover.json',dict(**result,requested_unix=time.time()));print(json.dumps(result),flush=True)

def status():
 from deploy_saved_sitting import status as check
 check()

def preserve():
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
   assert yaml.safe_load(z.read(n))==yaml.safe_load((P/'prepared'/n).read_text()),n
 write(D/'resume-checkpoint.json',dict(**info,local=str(cp),sha256=d.sha(cp),verified=True))
 print('Latest final checkpoint preserved locally and persistent:',cp.name,flush=True)
 return info

def launch():
 info=preserve()
 expected=json.loads((D/'staged.json').read_text())['source_sha256']
 print(remote(f'''import json,zipfile,hashlib
from pathlib import Path
r=Path('{REMOTE}');assert hashlib.sha256((r/'contact-source.zip').read_bytes()).hexdigest()=={expected!r}
with zipfile.ZipFile(r/'contact-source.zip') as z:z.extractall(r)
for n,h in json.loads((r/'source-inventory.json').read_text()).items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
print('Corrected targets installed; complete source inventory verified')
'''),flush=True)
 d.launch(info['path']);d.observe();shutil.copy2(OUT/'active_run.json',D/'launched-run.json')

def audit():
 active=json.loads((OUT/'active_run.json').read_text());name=active['run']
 assert name==json.loads((D/'launched-run.json').read_text())['run']
 code=f'''import json,hashlib,time
from pathlib import Path
r=Path('{REMOTE}');p=r/'runs'/{name!r}
def read(n):return json.loads((p/n).read_text()) if (p/n).exists() else None
s=read('status.json');e=read('evaluation.json');model=None
if (p/'model.pt').exists():
 import torch
 m=torch.load(p/'model.pt',map_location='cpu',weights_only=True)
 model={{k:list(m[k].shape) for k in ['_model._actor_layers.0.weight','_model._critic_layers.0.weight','_obs_norm._mean']}}
rep=e.get('replay',{{}}) if e else {{}}
rows=[{{k:row.get(k) for k in ['motion_name','limb_enabled','observation_contract','motion_loop_modes','capture_source','iteration']}} for row in rep.get('replay_rows',[])]
print(json.dumps(dict(run={name!r},checked_unix=time.time(),status={{k:s.get(k) for k in ['state','iteration','samples','updated_unix','worlds']}} if s else None,resume=read('resume.json'),backup=read('backup_status.json'),model=model,replay_rows=rows,provenance=read('provenance.json'),motion_hashes={{n:hashlib.sha256((r/'motions'/(n+'.pkl')).read_bytes()).hexdigest() for n in {NAMES!r}}})))
'''
 result=json.loads(d.cloud.ssh(REMOTE+'/venv/bin/python -c '+shlex.quote(code),timeout=45))
 assert result['motion_hashes']=={n:d.sha(P/'motions'/f'{n}.pkl') for n in NAMES}
 record=D/'advancing-statuses.json';history=json.loads(record.read_text()) if record.exists() else []
 if result['status'] and (not history or result['status']['iteration']>history[-1]['iteration']):
  history.append(dict(**result['status'],checked_unix=result['checked_unix']));write(record,history)
 write(D/'runtime-audit.json',result)
 print(json.dumps(dict(status=result['status'],model=result['model'],replay_rows=len(result['replay_rows']),backup=bool(result['backup']),advancing_statuses=len(history))),flush=True)
 return result

def verify():
 result=audit();history=json.loads((D/'advancing-statuses.json').read_text())
 assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
 assert result['status']['worlds']==2048 and result['status']['state']=='training'
 assert result['resume']['prior_samples']==173867008 and result['resume']['iteration_offset']==2653
 assert result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
 assert result['model']['_obs_norm._mean']==[160]
 assert all(result['model'][k][1]==160 for k in ['_model._actor_layers.0.weight','_model._critic_layers.0.weight'])
 assert {r['motion_name'] for r in result['replay_rows']}==set(NAMES)
 for row in result['replay_rows']:
  assert row['capture_source']=='actual_newton_physics' and row['observation_contract'].endswith('= 160')
  assert row['motion_loop_modes']=={n:1 for n in NAMES}
  expected=[1.,1.,0.,1.] if row['motion_name']=='limpR' else [1.,1.,1.,0.] if row['motion_name']=='limpL' else [1.]*4
  assert row['limb_enabled']==expected
 d.verify()
 write(D/'deployment-verified.json',dict(verified=True,run=result['run'],resume_checkpoint='checkpoint_0002652_final.zip',source_sha256=json.loads((D/'staged.json').read_text())['source_sha256'],motion_hashes=result['motion_hashes'],status=result['status'],advancing_statuses=history,persistent_backup_verified=True,verified_unix=time.time()))
 print('Corrected-motion continuation fully verified',flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()

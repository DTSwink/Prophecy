"""Multiply active-leg linear/angular velocity MSE by five and resume on the retained pod."""
import json,sys
import deploy_limp_strength as s
from deploy_saved_sitting import remote
D=s.OUT/'activeleg-velocity5-deploy-20261101';s.D=D;s.r.D=D;s.c.D=D
snapshot=s.snapshot

stop=s.stop
launch=s.launch
status=s.status
audit=s.audit


def preflight():
    import zipfile,shlex
    d=s.r.d
    with zipfile.ZipFile(D/'preflight-input.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('slow_loco_env.py','head_strength.py','train.py'):
            z.write(s.P/'pipeline'/name,'package/pipeline/'+name)
        for name in ('env_config.yaml','engine_config.yaml','agent_config.yaml'):
            z.write(s.P/'prepared'/name,'report/prepared/'+name)
        z.write(s.OUT/'geometry.json','report/geometry.json')
        z.write(D/'preflight_remote.py','preflight_remote.py')
    d.cloud.rp.scp(d.cloud.state()['connection'],D/'preflight-input.zip',s.c.REMOTE+'/activeleg-velocity5-preflight.zip',timeout=60)
    code="from pathlib import Path;import shutil,zipfile;r=Path('/workspace/mimickit_trial');t=r/'activeleg-velocity5-preflight';(t/'package').mkdir(parents=True,exist_ok=True);shutil.copytree(r/'pipeline',t/'package/pipeline',dirs_exist_ok=True);m=t/'package/MimicKit';m.symlink_to(r/'MimicKit',target_is_directory=True) if not m.exists() else None;z=zipfile.ZipFile(r/'activeleg-velocity5-preflight.zip');z.extractall(t);z.close()"
    remote(code)
    command='cd /workspace/mimickit_trial; timeout 180s venv/bin/python -u activeleg-velocity5-preflight/preflight_remote.py > activeleg-velocity5-preflight/preflight.log 2>&1'
    try:d.cloud.ssh(command,timeout=210)
    except Exception:
        print(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/activeleg-velocity5-preflight/preflight.log').read_text()[-7000:])"));raise
    report=json.loads(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/activeleg-velocity5-preflight/report/preflight.json').read_text())"))
    tests=json.loads(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/activeleg-velocity5-preflight/report/strength-test.json').read_text())"))
    assert report['passed'] and tests['passed']
    report['approved_motion_hashes']={n:d.sha(s.P/'motions'/f'{n}.pkl') for n in s.c.NAMES}
    s.write(s.OUT/'preflight.json',report);s.write(D/'preflight-verified.json',report);s.write(D/'strength-test.json',tests)
    print(json.dumps(dict(passed=True,replay_rows=report['replay_rows'],strength=tests)),flush=True)


def stage():
    import shutil
    d=s.r.d
    old=json.loads((D/'previous-inventory.json').read_text())
    diff={n for n in old if old[n]!=d.sha(s.P/n)}
    assert diff=={'pipeline/slow_loco_env.py'},diff
    assert (s.P/'pipeline/head_strength.py').exists()
    check=json.loads((D/'preflight-verified.json').read_text())
    assert check['passed'] and check['replay_rows']==8
    assert check['metadata']['motion_sampling']['counts']=={n:8 for n in s.c.NAMES}
    assert check['metadata']['loco_failure_penalty']==100.
    assert json.loads((D/'strength-test.json').read_text())['passed']
    d.bundle();shutil.copy2(s.OUT/'source-receipt.json',D/'source-receipt.json')
    d.cloud.rp.scp(d.cloud.state()['connection'],s.OUT/'source.zip',s.c.REMOTE+'/contact-source.zip',timeout=90)
    assert remote("import hashlib;print(hashlib.sha256(open('/workspace/mimickit_trial/contact-source.zip','rb').read()).hexdigest())").strip()==d.sha(s.OUT/'source.zip')
    s.write(D/'staged.json',dict(source_sha256=d.sha(s.OUT/'source.zip'),changed_files=sorted(diff)))
    print('Active-leg velocity multiplier staged and verified; GPU/trainer unchanged',flush=True)

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
    assert {r['motion_name'] for r in result['replay_rows']}==set(c.NAMES)
    for row in result['replay_rows']:
        assert row['capture_source']=='actual_newton_physics' and row['motion_loop_modes']=={n:1 for n in c.NAMES}
        expected=[1.,1.,0.,1.] if row['motion_name']=='limpR' else [1.,1.,1.,0.] if row['motion_name']=='limpL' else [1.]*4
        assert row['limb_enabled']==expected
    termination=json.loads(remote(f"import json;from pathlib import Path;e=json.loads(Path('/workspace/mimickit_trial/runs/{result['run']}/evaluation.json').read_text());print(json.dumps([dict(motion=r['motion_name'],rule=r['target_deviation']) for r in e['replay']['replay_rows']]))"))
    for row in termination:
        expected=row['rule']['radius_by_motion_m'][row['motion']]
        disabled='left_foot' if row['motion']=='limpL' else 'right_foot' if row['motion']=='limpR' else None
        assert expected=={b:(None if b==disabled else .40 if b=='pelvis' else .54 if row['motion'] in ('limpL','limpR') else .27) for b in ('head','left_hand','right_hand','left_foot','right_foot','pelvis')}
        assert {p['body']:p['radius_m'] for p in row['rule']['points']}=={b:r for b,r in expected.items() if r is not None}
    write(D/'live-termination-metadata.json',termination)
    extra=json.loads(remote(f"import json;from pathlib import Path;e=json.loads(Path('/workspace/mimickit_trial/runs/{result['run']}/evaluation.json').read_text());print(json.dumps([dict(sampling=x['motion_sampling'],strength=x['limp_support_strength'],head_mse=x['head_velocity_mse'],static_yaw=x['static_yaw_invariance'],controller=x['head_height_strength'],mask=x['disabled_leg_mse'],leeway=x['active_leg_position_leeway'],rotation_leeway=x['active_leg_rotation_leeway'],leg_velocity=x['active_leg_velocity_mse']) for x in e['replay']['replay_rows']]))"))
    expected=json.loads((D/'preflight-verified.json').read_text())['metadata']
    assert len(extra)==8
    for row in extra:
        assert row['sampling']['counts']=={n:256 for n in c.NAMES}
        assert row['sampling']['preserved_motion_onehot_order']==expected['motion_onehot_order']
        assert row['strength']==expected['limp_support_strength']
        assert row['controller']==expected['head_height_strength']
        assert row['head_mse']==expected['head_velocity_mse']
        assert row['static_yaw']==expected['static_yaw_invariance']
        assert row['static_yaw']['flat_com_velocity_disabled']
        assert row['head_mse']['linear_velocity_multiplier']==row['head_mse']['angular_velocity_multiplier']==3.
        assert row['mask']==expected['disabled_leg_mse']
        assert row['leeway']==expected['active_leg_position_leeway']
        assert row['leeway']['radius_m']==.1
        assert row['rotation_leeway']==expected['active_leg_rotation_leeway']
        assert row['rotation_leeway']['angle_degrees']==15.
        assert row['leg_velocity']==expected['active_leg_velocity_mse']
        assert row['leg_velocity']['linear_velocity_multiplier']==row['leg_velocity']['angular_velocity_multiplier']==5.
    write(D/'live-sampling-metadata.json',extra)
    reward_code="import json,numpy as np\nfrom pathlib import Path\np=Path('/workspace/mimickit_trial/runs/RUNNAME')\nwith np.load(p/'replay.npz',allow_pickle=False) as z:\n meta=json.loads(str(z['metadata']));checks=[]\n for i,row in enumerate(meta['replay_rows']):\n  suffix='' if i==0 else '_'+str(i)\n  data=z['data'+suffix][1:];terms=z['loss_terms'+suffix][1:]\n  assert row['loco_failure_penalty']==100.\n  target=np.asarray(row['frame_world_pelvis_target'])\n  pose=z['pose'+suffix];pelvis=row['names'].index('pelvis')\n  assert target.shape==(len(pose),3) and np.isfinite(target).all()\n  assert np.linalg.norm(target[0]-pose[0,pelvis,:3])<1e-4\n  point=next(x for x in row['target_deviation']['points'] if x['body']=='pelvis')\n  assert point['target_space']=='periodic_world_reference' and point['radius_m']==.40 and point['shape']=='sphere'\n  err=np.linalg.norm(target[1:]-pose[1:,pelvis,:3],axis=-1)\n  reference=z['reference_pose'+suffix]\n  squared=((pose[1:,:,:3]-reference[1:,:,:3])**2).sum(-1)\n  for body in row['active_leg_position_leeway']['affected_bodies_by_motion'].get(row['motion_name'],[]):\n   j=row['names'].index(body);squared[:,j]=np.maximum(np.sqrt(squared[:,j])-.1,0)**2\n  for body in row['disabled_leg_mse']['excluded_bodies_by_motion'].get(row['motion_name'],[]):squared[:,row['names'].index(body)]=0\n  position_expected=squared.mean(-1)/3*row['loss_weights']['position_mse']\n  assert np.allclose(terms[:,0],position_expected,atol=2e-5,rtol=1e-4),(row['motion_name'],float(np.max(np.abs(terms[:,0]-position_expected))))\n  actual_q=pose[1:,:,3:7].astype(np.float64);reference_q=reference[1:,:,3:7].astype(np.float64)\n  dot=np.abs((actual_q*reference_q).sum(-1)/(np.linalg.norm(actual_q,axis=-1)*np.linalg.norm(reference_q,axis=-1)))\n  angle=2*np.arccos(np.clip(dot,0,1))\n  for body in row['active_leg_rotation_leeway']['affected_bodies_by_motion'].get(row['motion_name'],[]):\n   j=row['names'].index(body);angle[:,j]=np.maximum(angle[:,j]-np.deg2rad(15),0)\n  rotation_error=8*np.sin(angle/2)**2\n  for body in row['disabled_leg_mse']['excluded_bodies_by_motion'].get(row['motion_name'],[]):rotation_error[:,row['names'].index(body)]=0\n  rotation_expected=rotation_error.mean(-1)/9*row['loss_weights']['rotation_mse']\n  assert np.allclose(terms[:,2],rotation_expected,atol=3e-5,rtol=2e-4),(row['motion_name'],float(np.max(np.abs(terms[:,2]-rotation_expected))))\n  velocities=z['world_velocities'+suffix][1:].astype(np.float64)\n  multipliers=np.ones(len(row['names']))\n  multipliers[row['names'].index('head')]=3.\n  for body in row['active_leg_velocity_mse']['affected_bodies_by_motion'].get(row['motion_name'],[]):multipliers[row['names'].index(body)]=5.\n  for body in row['disabled_leg_mse']['excluded_bodies_by_motion'].get(row['motion_name'],[]):multipliers[row['names'].index(body)]=0.\n  for col,actual_start,target_start,weight in [(1,0,6,'linear_velocity_mse'),(3,3,9,'angular_velocity_mse')]:\n   error=(velocities[:,:,actual_start:actual_start+3]-velocities[:,:,target_start:target_start+3])**2\n   reconstructed=(error*multipliers[None,:,None]).mean((1,2))*row['loss_weights'][weight]\n   assert np.allclose(terms[:,col],reconstructed,atol=3e-5,rtol=2e-4),(row['motion_name'],weight,float(np.max(np.abs(terms[:,col]-reconstructed))))\n  window=np.asarray(row['frame_pelvis_window'])[1:]\n  assert window.shape==(len(pose)-1,3) and np.isfinite(window).all()\n  ticks=row['target_deviation']['world_pelvis']['steps_by_motion'][row['motion_name']]\n  assert np.array_equal(window[:,2],np.arange(1,len(pose)))\n  assert np.all(window[:,1]==1) and ticks==70\n  assert np.all(window[:,0]>=.39999)\n  assert np.allclose(window[:,0],.40,atol=1e-6)\n  for t in range(ticks,len(pose),ticks):assert np.allclose(target[t,:2],pose[t,pelvis,:2],atol=1e-5)\n  assert row['target_deviation']['world_pelvis']['base_radius_m']==.40\n  delta=target[1:]-pose[1:,pelvis,:3]\n  horizontal=np.linalg.norm(delta[:,:2],axis=-1)\n  continued=data[:,0]==0\n  assert np.all(err[continued & (window[:,1]>0)]<=window[continued & (window[:,1]>0),0]+1e-5)\n  assert np.all(np.abs(delta[continued & (window[:,1]==0),2])<=window[continued & (window[:,1]==0),0]+1e-5)\n  assert row['target_deviation']['world_pelvis']['reset_every_ticks']==70\n  fail=data[:,0]==1\n  if row['motion_name'] in row['static_yaw_invariance']['motions']:\n   assert np.all(terms[:,row['loss_term_names'].index('flat_com_velocity')]==0)\n  reward_columns=[j for j,name in enumerate(row['loss_term_names']) if name!='auto_phase']\n  expected=np.exp(-terms[:,reward_columns].sum(-1))-100.*fail\n  assert np.allclose(data[:,2],expected,atol=1e-5)\n  checks.append(dict(motion=row['motion_name'],failure_ticks=int(fail.sum()),rolling_active_ticks=int((window[:,1]>0).sum()),window_ticks=int(ticks),terminal_reward=float(data[-1,2]),max_reward_error=float(np.max(np.abs(data[:,2]-expected)))))\n assert len(checks)==8\n print(json.dumps(checks))\n"
    reward_checks=json.loads(remote(reward_code.replace('RUNNAME',result['run'])))
    write(D/'live-terminal-reward-checks.json',reward_checks)
    checkpoint=json.loads(remote(f"import json,zipfile,hashlib;from pathlib import Path;p=Path('/workspace/mimickit_trial/runs/{result['run']}');b=json.loads((p/'backup_status.json').read_text());z=zipfile.ZipFile(p/b['key'].split('/')[-1]);print(json.dumps(dict(controller=json.loads(z.read('actuation_controller.json')),source_sha256=hashlib.sha256(z.read('head_strength.py')).hexdigest(),env_source_sha256=hashlib.sha256(z.read('slow_loco_env.py')).hexdigest())))"))
    assert checkpoint['controller']==expected['head_height_strength']
    assert checkpoint['source_sha256']==d.sha(P/'pipeline/head_strength.py')
    assert checkpoint['env_source_sha256']==d.sha(P/'pipeline/slow_loco_env.py')
    write(D/'checkpoint-controller-verified.json',checkpoint)
    d.verify()
    write(D/'deployment-verified.json',dict(verified=True,run=result['run'],resume_checkpoint=saved['local'],source_sha256=json.loads((D/'staged.json').read_text())['source_sha256'],motion_hashes=result['motion_hashes'],status=result['status'],advancing_statuses=history,persistent_backup_verified=True,verified_unix=time.time()))
    print('Active-leg velocity multiplier continuation verified; GPU retained',flush=True)

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
    assert current['slow_loco_failure_penalty']==previous['slow_loco_failure_penalty']==100.
    assert 'slow_loco_motion_subset' not in current and 'slow_loco_motion_subset' not in previous
   assert previous==current,n
 write(D/'resume-checkpoint.json',dict(**info,local=str(cp),sha256=d.sha(cp),verified=True))
 print('Latest final checkpoint preserved locally and persistent:',cp.name,flush=True)
 return info

s.c.preserve=preserve

if __name__=='__main__':globals()[sys.argv[1]]()

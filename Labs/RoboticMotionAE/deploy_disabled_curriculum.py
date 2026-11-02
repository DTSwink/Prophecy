"""Latest-checkpoint, same-pod handover for the user-approved disabled curriculum."""
import sys,json,shutil,zipfile,shlex,time,hashlib
from pathlib import Path
import deploy_limp_strength as s
from deploy_saved_sitting import remote
D=s.OUT/'disabled-curriculum-deploy-20261102';s.D=D;s.r.D=D;s.c.D=D
d=s.r.d;P=s.P;OUT=s.OUT
s.c.NAMES += ['limpL_idle','limpR_idle']
status=s.status;stop=s.stop;audit=s.audit

def prepare():
    import yaml
    report=json.loads((D/'init-report.json').read_text());assert report['passed']
    assert report['source_motion_sha256']=={n:d.sha(P/'motions'/f'{n}.pkl') for n in s.c.NAMES}
    assert report['limits_sha256']==d.sha(P/'assets/uefn/limits.json')
    for folder in (P/'prepared',OUT/'prepared'):
        shutil.copy2(D/'disabled_inits.npz',folder/'disabled_inits.npz')
        path=folder/'env_config.yaml';cfg=yaml.safe_load(path.read_text())
        cfg['slow_loco_disabled_curriculum']=dict(version=1,fractions=[.1,.3,.3,.3],
            crawl_mixed_rule='slower_factor',init_bank='disabled_inits.npz',init_bank_sha256=report['bank_sha256'])
        path.write_text(yaml.safe_dump(cfg,sort_keys=False))
    for name in ('slow_loco_disabled.py','disabled_limb_rules.py'):
        shutil.copy2(d.ROOT/'Labs/RoboticMotionAE'/name,P/'pipeline'/name)
    print('Local curriculum package prepared; live trainer untouched',flush=True)

def preflight():
    with zipfile.ZipFile(D/'preflight-input.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(D/'preflight-resume.json','preflight_resume.json')
        for name in ('slow_loco_disabled.py','disabled_limb_rules.py','slow_loco_env.py','train.py','observe.py','observe_many.py','replay.py'):
            z.write(P/'pipeline'/name,'package/pipeline/'+name)
        for name in ('env_config.yaml','engine_config.yaml','agent_config.yaml','manifest.json','motions.yaml','disabled_inits.npz'):
            z.write(P/'prepared'/name,'report/prepared/'+name)
        z.write(OUT/'geometry.json','report/geometry.json')
        z.write(d.ROOT/'Labs/RoboticMotionAE/preflight_disabled_remote.py','preflight_remote.py')
        z.write(d.ROOT/'Labs/RoboticMotionAE/verify_disabled_replay.py','verify_disabled_replay.py')
    d.cloud.rp.scp(d.cloud.state()['connection'],D/'preflight-input.zip',s.c.REMOTE+'/disabled-preflight.zip',timeout=60)
    remote("from pathlib import Path;import shutil,zipfile;r=Path('/workspace/mimickit_trial');t=r/'disabled-preflight';(t/'package').mkdir(parents=True,exist_ok=True);shutil.copytree(r/'pipeline',t/'package/pipeline',dirs_exist_ok=True);m=t/'package/MimicKit';m.symlink_to(r/'MimicKit',target_is_directory=True) if not m.exists() else None;z=zipfile.ZipFile(r/'disabled-preflight.zip');z.extractall(t);z.close()")
    command='cd /workspace/mimickit_trial; timeout 600s venv/bin/python -u disabled-preflight/preflight_remote.py > disabled-preflight/preflight.log 2>&1'
    try:d.cloud.ssh(command,timeout=630)
    except Exception:
        print(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/disabled-preflight/preflight.log').read_text()[-8000:])"));raise
    report=json.loads(remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/disabled-preflight/report/preflight.json').read_text())"))
    assert report['passed'] and report['replay_rows'] in (33,34,40)
    s.write(D/'preflight-verified.json',report);s.write(OUT/'preflight.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='metadata'}),flush=True)

def stage():
    old=json.loads((D/'previous-inventory.json').read_text())
    changed={n for n in old if old[n]!=d.sha(P/n)}
    added={p.relative_to(P).as_posix() for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}-set(old)-{'source-inventory.json'}
    assert changed=={'pipeline/train.py','pipeline/observe.py','pipeline/observe_many.py','pipeline/replay.py','prepared/env_config.yaml','prepared/agent_config.yaml','pipeline/failure_stop.py'},changed
    assert added=={'pipeline/slow_loco_disabled.py','pipeline/disabled_limb_rules.py','prepared/disabled_inits.npz'},added
    report=json.loads((D/'preflight-verified.json').read_text());assert report['passed'] and report['worlds']==2048 and report['resumed_checkpoint']==14765
    d.bundle();shutil.copy2(OUT/'source-receipt.json',D/'source-receipt.json')
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'source.zip',s.c.REMOTE+'/contact-source.zip',timeout=90)
    assert remote("import hashlib;print(hashlib.sha256(open('/workspace/mimickit_trial/contact-source.zip','rb').read()).hexdigest())").strip()==d.sha(OUT/'source.zip')
    s.write(D/'staged.json',dict(source_sha256=d.sha(OUT/'source.zip'),changed_files=sorted(changed),added_files=sorted(added)))
    print('Source staged and verified; trainer still unchanged',flush=True)

def preserve():
    import yaml
    replacement=D/'replacement-resume-verified.json'
    if replacement.exists() and json.loads(replacement.read_text())['pod']==d.cloud.state()['pod_id']:
        info=json.loads((D/'resume-checkpoint.json').read_text())
        assert info['verified'] and d.sha(info['local'])==info['sha256']
        assert remote('import hashlib;print(hashlib.sha256(open('+repr(info['path'])+',"rb").read()).hexdigest())').strip()==info['sha256']
        stream=d.cloud.s3().get_object(Bucket=d.cloud.rp.VOLUME_ID,Key=info['backup']['key'])['Body']
        h=hashlib.sha256()
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
        stream.close();assert h.hexdigest()==info['sha256']
        print('Replacement resume14765 verified locally, remotely and persistently',flush=True)
        return info
    old=json.loads((D/'previous-run.json').read_text())['run']
    info=json.loads(remote(f'''import json,hashlib
from pathlib import Path
r=Path('/workspace/mimickit_trial');name={old!r};p=r/'runs'/name;x=json.loads((r/(name+'-launch.json')).read_text());cmd=Path('/proc')/str(x['pid'])/'cmdline'
assert not cmd.exists() or name.encode() not in cmd.read_bytes(),'Old trainer still running'
assert (p/'finished.json').exists()
b=json.loads((p/'backup_status.json').read_text());cp=p/b['key'].split('/')[-1]
assert cp.name.endswith('_final.zip') and hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256']
print(json.dumps(dict(backup=b,path=str(cp),finished=json.loads((p/'finished.json').read_text()))))
'''))
    b=info['backup'];folder=OUT/'preserved-latest'/old;folder.mkdir(parents=True,exist_ok=True);cp=folder/b['key'].split('/')[-1]
    stream=d.cloud.s3().get_object(Bucket=d.cloud.rp.VOLUME_ID,Key=b['key'])['Body'];temp=cp.with_suffix('.zip.part')
    with temp.open('wb') as f:
        for block in iter(lambda:stream.read(1024*1024),b''):f.write(block)
    stream.close();assert d.sha(temp)==b['sha256'];temp.replace(cp)
    with zipfile.ZipFile(cp) as z:
        assert z.testzip() is None and {'model.pt','resume_state.pt'}<=set(z.namelist())
        for name in ('env_config.yaml','engine_config.yaml','agent_config.yaml'):
            before=yaml.safe_load(z.read(name));after=yaml.safe_load((P/'prepared'/name).read_text())
            if name=='env_config.yaml':after.pop('slow_loco_disabled_curriculum')
            if name=='agent_config.yaml':
                assert after['critic_optimizer']['grad_clip']==100.
                before['critic_optimizer']['grad_clip']=100.
            assert before==after,name
    s.write(D/'resume-checkpoint.json',dict(**info,local=str(cp),sha256=d.sha(cp),verified=True))
    print('Latest final preserved:',cp.name,flush=True);return info

def launch():
    info=preserve();expected=json.loads((D/'staged.json').read_text())['source_sha256']
    print(remote("import zipfile,hashlib,json;from pathlib import Path;r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'contact-source.zip').read_bytes()).hexdigest()=="+repr(expected)+";z=zipfile.ZipFile(r/'contact-source.zip');z.extractall(r);z.close();assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in json.loads((r/'source-inventory.json').read_text()).items());print('Disabled curriculum installed and verified')"))
    d.launch(info['path'],replay_rows=40,run_kind='disabled_curriculum');d.observe()
    shutil.copy2(OUT/'active_run.json',D/'launched-run.json')
    history=D/'advancing-statuses.json'
    if history.exists():history.replace(D/('previous-advancing-statuses-'+str(int(time.time()))+'.json'))

def verify():
    result=s.c.audit();history=json.loads((D/'advancing-statuses.json').read_text())
    assert len(history)>=2 and history[-1]['samples']>history[0]['samples']
    assert result['status']['worlds']==2048 and result['status']['state']=='training'
    assert result['resume']['optimizer_restored'] and result['resume']['normalizer_restored']
    assert result['resume']['prior_samples']==967704576 and result['resume']['iteration_offset']==14766
    assert result['resume']['disabled_arm_flag_normalization']['new_std']==[1.,1.]
    assert result['model']['_obs_norm._mean']==[160]
    name=result['run']
    rows=json.loads(remote(f"import json;from pathlib import Path;e=json.loads(Path('/workspace/mimickit_trial/runs/{name}/evaluation.json').read_text());print(json.dumps(e['replay']['replay_rows']))"))
    assert len(rows)==40 and {(r['motion_name'],r['cohort_index']) for r in rows}=={(n,c) for n in s.c.NAMES for c in range(4)}
    from disabled_limb_rules import valid_codes,limb_bodies,crawl_rate
    for row in rows:
        count=row['cohort_index'];code=row['disabled_limb_code'];motion=row['motion_name']
        assert row['loco_failure_penalty']==100.
        assert row['limb_enabled']==[0. if code&(1<<l) else 1. for l in range(4)]
        assert code in valid_codes(motion,count) if count else code==(8 if motion.startswith('limpL') else 4 if motion.startswith('limpR') else 0)
        assert abs(row['motion_playback_rate']-(crawl_rate(code) if count and motion.startswith('crawl') else 1.))<1e-6
        expected={b:r for b,r in row['row_target_radii_m'].items() if r is not None}
        assert {p['body']:p['radius_m'] for p in row['target_deviation']['points']}==expected
        assert row['excluded_mse_bodies']==[b for l in range(4) if code&(1<<l) for b in limb_bodies(l)]
        assert row['motion_sampling']['cohort_counts']=={'vanilla':205,'perturbed_1':615,'perturbed_2':614,'perturbed_3':614}
    s.write(D/'live-rows-verified.json',rows)
    code=f'''import sys,json,torch,yaml,hashlib
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'runs'/{name!r}
sys.path.insert(0,str(r/'disabled-preflight'))
from verify_disabled_replay import verify
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in json.loads((r/'source-inventory.json').read_text()).items())
assert yaml.safe_load((r/'prepared/agent_config.yaml').read_text())['critic_optimizer']['grad_clip']==100.
model=torch.load(p/'model.pt',map_location='cpu',weights_only=True)
assert all(torch.isfinite(v).all() for v in model.values() if torch.is_tensor(v))
assert model['_obs_norm._std'][154:156].tolist()==[1.,1.]
print(json.dumps(verify(p/'replay.npz')))
'''
    independent=json.loads(d.cloud.ssh('/workspace/mimickit_trial/venv/bin/python -c '+shlex.quote(code),timeout=45))
    s.write(D/'live-independent-replay-checks.json',independent)
    d.verify()
    s.write(D/'deployment-verified.json',dict(verified=True,run=name,resume=json.loads((D/'resume-checkpoint.json').read_text()),advancing_statuses=history,
        persistent_backup_verified=True,source_sha256=json.loads((D/'staged.json').read_text())['source_sha256'],replay_rows=40))
    print('Verified disabled curriculum,40 replay rows,persistent backup; runs until stopped',flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()

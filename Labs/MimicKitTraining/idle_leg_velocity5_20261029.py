"""Pinned-source, same-GPU idle leg velocity MSE adjustment."""
import json, hashlib, zipfile, pickle, sys, textwrap, io
from pathlib import Path
import yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
OUT=d.OUT/'idle-leg-vel5-20261029'
BLOCK='''        # Preserve the all-body/component denominator; add four extra leg copies.
        idle_leg_rows = (self._gaits[self._motion_ids] == -1) & ~self._recovery_rows
        leg_ids = self._idle_velocity_leg_ids
        factor = (self._idle_leg_velocity_scale - 1.) / (vel.shape[1] * vel.shape[2])
        linear_extra = (vel[:, leg_ids] - target_vel[:, leg_ids]).square().sum((1, 2))
        angular_extra = (ang[:, leg_ids] - target_ang[:, leg_ids]).square().sum((1, 2))
        terms[:, 1] += torch.where(idle_leg_rows, linear_extra * factor * self._loss_weights[1], 0.)
        terms[:, 3] += torch.where(idle_leg_rows, angular_extra * factor * self._loss_weights[3], 0.)
'''

def save(name,obj): (OUT/(name+'.json')).write_text(json.dumps(obj,indent=2))
def one(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b)

def prepare():
    OUT.mkdir(exist_ok=True)
    old=json.loads((d.OUT/'getup-success-prepared.json').read_text());save('previous-plan',old)
    assert old['source']['sha256']=='a757d51c66b09a5a50bdaaabe5df12f81def79fa352bde02a760761773f5f979'
    with zipfile.ZipFile(old['source']['local']) as z: entries={n:z.read(n) for n in z.namelist()}
    s=entries['pipeline/perturbed_omni.py'].decode()
    anchor="        self._leg_reversal = LegReversal(n, self._device)"
    s=one(s,anchor,"        self._idle_velocity_leg_ids = torch.cat((self._leg_ids, self._walking_foot_ids))\n        self._idle_leg_velocity_scale = float(cfg.get('idle_leg_velocity_mse_multiplier', 1.))\n"+anchor)
    s=one(s,'        terms[:, :4] *= mse_mix[:, None]',BLOCK+'        terms[:, :4] *= mse_mix[:, None]')
    anchor="        result['leg_reversal'] = self._perturb_cfg['leg_reversal']['description']"
    s=one(s,anchor,anchor+"\n        result['idle_leg_velocity_mse'] = dict(multiplier=self._idle_leg_velocity_scale, bodies=['right_thigh', 'right_shin', 'right_foot', 'left_thigh', 'left_shin', 'left_foot'], scope='All idle cohorts; linear and angular world-body velocity MSE; existing handoff retained')")
    compile(s,'perturbed_omni.py','exec');entries['pipeline/perturbed_omni.py']=s.encode()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml']);cfg['perturbed_motion']['idle_leg_velocity_mse_multiplier']=5.
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    source=OUT/'source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in entries.items():z.writestr(n,b)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    plan=dict(old,source=dict(local=str(source),sha256=sha,key='mimickit/pipeline_20261014/idle-leg-vel5/source_'+sha[:12]+'.zip'),run_suffix='uefn_locomotion_idle_legvel5_4000ada_2048')
    save('prepared',plan)
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(OUT/'overlay.zip','w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl',pickle.dumps(z.infolist()))
        for n in ['pipeline/perturbed_omni.py','prepared/env_config.yaml']:delta.writestr(n,entries[n])
    # Execute the production block against an independently body-weighted oracle.
    test='''import torch,json
from types import SimpleNamespace
torch.manual_seed(5)
device=DEVICE
n,b=8,15
vel,ang,target_vel,target_ang=[torch.randn(n,b,3,device=device) for _ in range(4)]
self=SimpleNamespace(_gaits=torch.tensor([-1,-1,-1,-1,0,1,-1,0],device=device),_motion_ids=torch.arange(n,device=device),_recovery_rows=torch.tensor([False]*6+[True,False],device=device),_idle_velocity_leg_ids=torch.tensor([9,10,12,13,11,14],device=device),_idle_leg_velocity_scale=5.,_loss_weights=torch.tensor([2.,3.,4.,5.],device=device))
base=torch.randn(n,4,device=device)
base[:,1]=(vel-target_vel).square().mean((1,2))*3
base[:,3]=(ang-target_ang).square().mean((1,2))*5
def compute():
 terms=base.clone()
PRODUCTION
 return terms
expected=base.clone()
weights=torch.ones(n,b,3,device=device);weights[:4,9:]=5
expected[:,1]=((vel-target_vel).square()*weights).mean((1,2))*3
expected[:,3]=((ang-target_ang).square()*weights).mean((1,2))*5
torch.testing.assert_close(compute(),expected)
for mix in [0.,.010628431805636024,.5,1.]:torch.testing.assert_close(compute()*mix,expected*mix)
if device=='cuda':
 stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
 with torch.cuda.stream(stream):
  for _ in range(3):compute()
 torch.cuda.current_stream().wait_stream(stream)
 graph=torch.cuda.CUDAGraph()
 with torch.cuda.graph(graph):actual=compute()
 graph.replay();torch.cuda.synchronize();torch.testing.assert_close(actual,expected)
print(json.dumps(dict(passed=True,device=device,scope='four idle cohorts; locomotion/recovery excluded; other channels unchanged; handoff and graph checked')))
'''.replace('PRODUCTION',textwrap.indent(textwrap.dedent(BLOCK),' '))
    (OUT/'test.py').write_text(test.replace('DEVICE',repr('cpu')))
    exec(compile(test.replace('DEVICE',repr('cpu')),'test','exec'),{})
    (OUT/'test-gpu.py').write_text(test.replace('DEVICE',repr('cuda')))
    print(json.dumps(plan['source']))

def stage():
    plan=json.loads((OUT/'prepared.json').read_text());old=json.loads((OUT/'previous-plan.json').read_text())
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'overlay.zip','/workspace/mimickit_trial/idle-leg-overlay.zip',timeout=35)
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'test-gpu.py','/workspace/mimickit_trial/test-idle-leg.py',timeout=35)
    code='''from pathlib import Path
import zipfile,pickle,hashlib,json,subprocess,boto3
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD
with zipfile.ZipFile(r/'source.zip') as current,zipfile.ZipFile(r/'idle-leg-overlay.zip') as delta,zipfile.ZipFile(r/'idle-leg-source.zip','w') as z:
 for info in pickle.loads(delta.read('infos.pkl')):z.writestr(info,delta.read(info.filename) if info.filename in delta.namelist() else current.read(info.filename))
data=(r/'idle-leg-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
subprocess.run([str(r/'venv/bin/python'),str(r/'test-idle-leg.py')],check=True)
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('Source and GPU checks verified')
'''.replace('OLD',repr(old['source']['sha256'])).replace('SHA',repr(plan['source']['sha256'])).replace('KEY',repr(plan['source']['key']))
    result=r.remote(code,timeout=55);save('staged',dict(passed=True,output=result));print(result)

def stop():
    assert json.loads((OUT/'staged.json').read_text())['passed']
    active=json.loads((d.OUT/'active_run.json').read_text());plan=json.loads((OUT/'prepared.json').read_text())
    d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']));r.stop()

def capture():
    r.capture();plan=json.loads((OUT/'prepared.json').read_text());cp=json.loads((d.OUT/'ae30-switch.json').read_text())['checkpoint'];plan['checkpoint']=cp;save('prepared',plan)
    save('checkpoint-state',dict(iteration=cp['finished']['iteration']-1,samples=cp['finished']['samples']))

def launch():
    plan=json.loads((OUT/'prepared.json').read_text());cp=plan['checkpoint']
    code='''from pathlib import Path
import hashlib,json,zipfile,shutil
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'idle-leg-source.zip').read_bytes()).hexdigest()==SHA
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CPSHA
shutil.copyfile(r/'idle-leg-source.zip',r/'source.zip')
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
p=json.loads((r/'private.json').read_text());p['resume_checkpoint']=CP;(r/'private.json').write_text(json.dumps(p));(r/'stop.request').unlink(missing_ok=True)
'''.replace('CPSHA',repr(cp['sha256'])).replace('SHA',repr(plan['source']['sha256'])).replace('CP',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    r.remote(code);d.save('getup-success-prepared',plan);d.launch()

def verify():
    (d.OUT/'latest-restart-receipt.txt').write_text(str(OUT))
    script=Path(__file__).with_name('verify_loco_unchanged_resume.py').read_text()
    old="  assert yaml.safe_load(cp.read(name))==yaml.safe_load((p/name).read_text()),name"
    new="""  expected=yaml.safe_load(cp.read(name));actual=yaml.safe_load((p/name).read_text())
  if name=='env_config.yaml':expected['perturbed_motion']['idle_leg_velocity_mse_multiplier']=5.
  assert expected==actual,name"""
    script=one(script,old,new)
    script=one(script," assert row['frame_com2_reward_multiplier']"," assert row['frame_com2_reward_multiplier']\n assert row['idle_leg_velocity_mse']['multiplier']==5. and len(row['idle_leg_velocity_mse']['bodies'])==6\n assert 'idle_stop' not in row['loss_term_names'] and 'leg_reversal' in row['loss_term_names']")
    scope={'__name__':'isolated_idle_leg_verification'};exec(compile(script,'idle_leg_live_verify','exec'),scope);scope['main']()
    result=json.loads((OUT/'live-verification.json').read_text())
    if result['ready']:
        print(r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Handoff verified')",timeout=20))

if __name__=='__main__':globals()[sys.argv[1]]()

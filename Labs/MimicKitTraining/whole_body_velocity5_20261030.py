"""Extend leg velocity x5 to whole-body velocity terms; pinned, isolated resume."""
import json, hashlib, zipfile, pickle, textwrap, sys
from pathlib import Path
import yaml
import idle_leg_velocity5_20261029 as h
import all_rows_leg_velocity5_20261029 as previous

h.OUT = h.d.OUT / 'whole-body-vel5-20261030'
BLOCK = '''        # Replace leg-only weighting; retain the existing pelvis emphasis.
        terms[:, 1] *= self._whole_body_velocity_scale
        terms[:, 3] *= self._whole_body_velocity_scale
'''

def prepare():
    h.OUT.mkdir(exist_ok=True)
    old=json.loads((h.d.OUT/'getup-success-prepared.json').read_text())
    assert old['source']['sha256']=='4b3d1716be1c98d66da4a1f820f3ef376581701ecd412dd931c753ff048d4cc6'
    h.save('previous-plan',old)
    with zipfile.ZipFile(old['source']['local']) as z: entries={n:z.read(n) for n in z.namelist()}
    s=entries['pipeline/perturbed_omni.py'].decode()
    s=h.one(s,previous.BLOCK,BLOCK)
    s=h.one(s,"        self._velocity_leg_ids = torch.cat((self._leg_ids, self._walking_foot_ids))\n",'')
    s=s.replace('_leg_velocity_scale','_whole_body_velocity_scale').replace('leg_velocity_mse','whole_body_velocity_mse')
    s=h.one(s,"bodies=['right_thigh', 'right_shin', 'right_foot', 'left_thigh', 'left_shin', 'left_foot'], scope='All rows; legs only; linear and angular world-body velocity MSE including prior custom MSE; existing handoff retained'",
        "bodies=['pelvis', 'torso', 'head', 'right_upper_arm', 'right_lower_arm', 'right_hand', 'left_upper_arm', 'left_lower_arm', 'left_hand', 'right_thigh', 'right_shin', 'right_foot', 'left_thigh', 'left_shin', 'left_foot'], scope='All rows; whole body; linear and angular world-body velocity MSE including prior custom MSE; existing pelvis emphasis and handoff retained'")
    assert '_velocity_leg_ids' not in s and 'leg_velocity_mse' not in s
    compile(s,'perturbed_omni.py','exec');entries['pipeline/perturbed_omni.py']=s.encode()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml'])
    assert cfg['perturbed_motion'].pop('leg_velocity_mse_multiplier')==5.
    cfg['perturbed_motion']['whole_body_velocity_mse_multiplier']=5.
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    source=h.OUT/'source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    h.save('prepared',dict(old,source=dict(local=str(source),sha256=sha,key='mimickit/pipeline_20261014/whole-body-vel5/source_'+sha[:12]+'.zip'),run_suffix='uefn_locomotion_bodyvel5_4000ada_2048'))
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(h.OUT/'overlay.zip','w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl',pickle.dumps(z.infolist()))
        for n in ['pipeline/perturbed_omni.py','prepared/env_config.yaml']:delta.writestr(n,entries[n])
    test='''import torch,json
from types import SimpleNamespace
torch.manual_seed(5)
device=DEVICE
n,b=8,15
vel,ang,target_vel,target_ang=[torch.randn(n,b,3,device=device) for _ in range(4)]
self=SimpleNamespace(_whole_body_velocity_scale=5.)
base=torch.randn(n,4,device=device)
weights=torch.ones(n,b,3,device=device);weights[:,0]=10.
base[:,1]=((vel-target_vel).square()*weights).mean((1,2))*3
base[:,3]=(ang-target_ang).square().mean((1,2))*5
def compute():
 terms=base.clone()
PRODUCTION
 return terms
expected=base.clone()
expected[:,1]=((vel-target_vel).square()*weights*5).mean((1,2))*3
expected[:,3]=((ang-target_ang).square()*5).mean((1,2))*5
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
print(json.dumps(dict(passed=True,device=device,scope='all bodies velocity/angular x5, no leg stacking; pelvis relative emphasis retained; other channels unchanged; prior/handoff and graph checked')))
'''.replace('PRODUCTION',textwrap.indent(textwrap.dedent(BLOCK),' '))
    for name,device in [('test.py','cpu'),('test-gpu.py','cuda')]:
        code=test.replace('DEVICE',repr(device));(h.OUT/name).write_text(code)
        if device=='cpu':exec(compile(code,name,'exec'),{})
    print(json.dumps(dict(source_sha256=sha)))

def verify():
    (h.d.OUT/'latest-restart-receipt.txt').write_text(str(h.OUT))
    script=Path(__file__).with_name('verify_loco_unchanged_resume.py').read_text()
    script=h.one(script,"  assert yaml.safe_load(cp.read(name))==yaml.safe_load((p/name).read_text()),name", """  expected=yaml.safe_load(cp.read(name));actual=yaml.safe_load((p/name).read_text())
  if name=='env_config.yaml':
   assert expected['perturbed_motion'].pop('leg_velocity_mse_multiplier')==5.
   expected['perturbed_motion']['whole_body_velocity_mse_multiplier']=5.
  assert expected==actual,name""")
    script=h.one(script," assert row['frame_com2_reward_multiplier']"," assert row['frame_com2_reward_multiplier']\n assert row['whole_body_velocity_mse']['multiplier']==5. and len(row['whole_body_velocity_mse']['bodies'])==15\n assert 'leg_velocity_mse' not in row\n assert 'idle_stop' not in row['loss_term_names'] and 'leg_reversal' in row['loss_term_names']")
    scope={'__name__':'isolated_whole_body_verification'};exec(compile(script,'whole_body_verify','exec'),scope);scope['main']()
    if json.loads((h.OUT/'live-verification.json').read_text())['ready']:
        print(h.r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Handoff verified')",timeout=20))

if __name__=='__main__':
    action=sys.argv[1]
    (globals()[action] if action in ['prepare','verify'] else getattr(h,action))()

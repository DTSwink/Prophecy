"""Add an isolated, additive perturbed-idle wobble term; preserve all other settings."""
import json,hashlib,zipfile,pickle,sys,ast,tempfile
from pathlib import Path
from types import SimpleNamespace
import yaml
import idle_leg_velocity5_20261029 as h
h.OUT=h.d.OUT/'idle-settle-20261030'

def prepare():
    plan=json.loads((h.d.OUT/'getup-success-prepared.json').read_text());h.save('previous-plan',plan)
    assert plan['source']['sha256']=='e3be9de73445343b32eae01b9ae9654c9395fde9ce30e2beb457500782eb1568'
    with zipfile.ZipFile(plan['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    weight=json.loads((h.OUT/'audit.json').read_text())[0]['calibrated_weight']
    one=h.one
    s=entries['pipeline/perturbed_omni.py'].decode()
    s=one(s,'from leg_reversal import LegReversal','from leg_reversal import LegReversal\nfrom idle_wobble import IdleWobble')
    s=one(s,"        self.loss_weights['leg_reversal'] = 1.","""        self.loss_weights['leg_reversal'] = 1.
        self._idle_wobble = IdleWobble(n, len(names), self._device)
        self._idle_wobble_weight = float(cfg['idle_wobble']['weight'])
        self.loss_term_names = (*self.loss_term_names, 'idle_wobble')
        self.loss_weights['idle_wobble'] = self._idle_wobble_weight""")
    s=one(s,'        self._head_reversal.reset(env_ids,','        self._idle_wobble.reset(env_ids)\n        self._head_reversal.reset(env_ids,')
    s=one(s,'        return torch.cat((terms, foot_terms, leg_cost[:, None]), -1)',"""        idle = (self._gaits[self._motion_ids] == -1) & ~self._recovery_rows
        active = idle & (self._perturbed_rows | self._final.minus)
        wobble = self._idle_wobble.append(vel, ang, self._final.last_kick, active)
        wobble = wobble * self._idle_wobble_weight
        return torch.cat((terms, foot_terms, leg_cost[:, None], wobble[:, None]), -1)""")
    s=one(s,"        result['leg_reversal'] = self._perturb_cfg['leg_reversal']['description']", "        result['idle_wobble'] = self._perturb_cfg['idle_wobble']\n        result['leg_reversal'] = self._perturb_cfg['leg_reversal']['description']")
    compile(s,'perturbed_omni.py','exec');entries['pipeline/perturbed_omni.py']=s.encode()
    s=entries['pipeline/lossless_runtime.py'].decode()
    anchor='            buffers.extend(getattr(e._leg_reversal,n) for n in e._leg_reversal.buffer_names)'
    s=one(s,anchor,anchor+'\n            buffers.extend(getattr(e._idle_wobble,n) for n in e._idle_wobble.buffer_names)')
    entries['pipeline/lossless_runtime.py']=s.encode()
    entries['pipeline/idle_wobble.py']=Path(__file__).with_name('idle_wobble.py').read_bytes()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion']['idle_wobble']=dict(weight=weight,calibration='Fixed coefficient:10% of combined additive loss, equally weighted audited P-minus/P idle episodes318079; observed shares vary. Not a dynamic multiplier.',description='Perturbed idle only (P/P+/P-minus), all ticks, independent of prior fade. All15 world body-origin linear and world angular velocities. EW path-length minus net-displacement rates at0.2/0.7s time constants, times current speed; deadzones0.02m/s,0.1rad/s; angular radius0.3m. Mean over bodies/windows, sum linear/angular. Reset on episode and push; no cost at rest or straight one-direction motion.')
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    # Execute the actual launcher's config validation before touching training.
    tree=ast.parse(entries['pipeline/train.py'])
    loop=next(n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.iter,ast.List) and any(isinstance(x,ast.Constant) and x.value=='engine_config.yaml' for x in n.iter.elts))
    class Args(SimpleNamespace):
        def __getattr__(self,key):return None
    with tempfile.TemporaryDirectory() as tmp,zipfile.ZipFile(plan['checkpoint']['local']) as bundle:
        directory=Path(tmp)
        for name in ['engine_config.yaml','env_config.yaml','agent_config.yaml']:(directory/name).write_bytes(entries['prepared/'+name])
        exec(compile(ast.Module(body=[loop],type_ignores=[]),'actual_resume','exec'),dict(yaml=yaml,bundle=bundle,directory=directory,config=cfg,a=Args(omni_run_lr=True,equipment_omni=True,resume_perturbed_motion=True)))
    source=h.OUT/'source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    h.save('prepared',dict(plan,source=dict(local=str(source),sha256=sha,key='mimickit/pipeline_20261014/idle-wobble/source_'+sha[:12]+'.zip'),run_suffix='uefn_locomotion_idle_wobble_4000ada_2048'))
    changed=['pipeline/perturbed_omni.py','pipeline/lossless_runtime.py','pipeline/idle_wobble.py','prepared/env_config.yaml']
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(h.OUT/'overlay.zip','w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl',pickle.dumps(z.infolist()))
        for n in changed:delta.writestr(n,entries[n])
    test="""import zipfile,sys
from pathlib import Path
r=Path('/workspace/mimickit_trial/idle-wobble-preflight');r.mkdir(exist_ok=True)
with zipfile.ZipFile('/workspace/mimickit_trial/idle-leg-source.zip') as z:z.extractall(r)
sys.path.insert(0,str(r/'pipeline'))
"""+Path(__file__).with_name('test_idle_wobble.py').read_text().replace("run(sys.argv[1] if len(sys.argv)>1 else 'cpu')","run('cuda')")
    (h.OUT/'test-gpu.py').write_text(test)
    h.save('delta',dict(files=changed,weight=weight,actual_resume_guard_passed=True))
    print(json.dumps(dict(source=sha,weight=weight)))

def verify():
    (h.d.OUT/'latest-restart-receipt.txt').write_text(str(h.OUT))
    script=Path(__file__).with_name('verify_loco_unchanged_resume.py').read_text()
    script=h.one(script,"  assert yaml.safe_load(cp.read(name))==yaml.safe_load((p/name).read_text()),name", """  expected=yaml.safe_load(cp.read(name));actual=yaml.safe_load((p/name).read_text())
  if name=='env_config.yaml':expected['perturbed_motion']['idle_wobble']=actual['perturbed_motion']['idle_wobble']
  assert expected==actual,name""")
    script=h.one(script," assert row['frame_com2_reward_multiplier']", """ assert row['frame_com2_reward_multiplier']
 assert 'idle_wobble' in row['loss_term_names']
 if not row['idle_row']:
  assert (z['loss_terms'+('' if i==0 else '_'+str(i))][:,row['loss_term_names'].index('idle_wobble')]==0).all()""")
    scope={'__name__':'idle_wobble_verify'};exec(compile(script,'idle_wobble_verify','exec'),scope);scope['main']()
    if json.loads((h.OUT/'live-verification.json').read_text())['ready']:
        print(h.r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Handoff verified')",timeout=20))

if __name__=='__main__':
    action=sys.argv[1];(globals()[action] if action in ['prepare','verify'] else getattr(h,action))()

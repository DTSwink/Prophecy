"""Extend existing leg velocity-only x5 weighting to all locomotion-branch rows."""
import json,hashlib,zipfile,pickle,textwrap,sys
from pathlib import Path
import yaml
import idle_leg_velocity5_20261029 as h
ORIGINAL_OUT=h.OUT
h.OUT=h.d.OUT/'all-rows-leg-vel5-20261029'
BLOCK='''        # Four extra leg copies, with the original all-body/component denominator.
        leg_ids = self._velocity_leg_ids
        factor = (self._leg_velocity_scale - 1.) / (vel.shape[1] * vel.shape[2])
        linear_extra = (vel[:, leg_ids] - target_vel[:, leg_ids]).square().sum((1, 2))
        angular_extra = (ang[:, leg_ids] - target_ang[:, leg_ids]).square().sum((1, 2))
        terms[:, 1] += linear_extra * factor * self._loss_weights[1]
        terms[:, 3] += angular_extra * factor * self._loss_weights[3]
'''

def prepare():
    h.OUT.mkdir(exist_ok=True)
    old=json.loads((h.d.OUT/'getup-success-prepared.json').read_text());h.save('previous-plan',old)
    assert old['source']['sha256']=='ba917fd77bd047011eda81e2719dfa26e72137894b7e6f2e37373aeee0a04e31'
    with zipfile.ZipFile(old['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    s=entries['pipeline/perturbed_omni.py'].decode();s=h.one(s,h.BLOCK,BLOCK)
    s=s.replace('_idle_velocity_leg_ids','_velocity_leg_ids').replace('_idle_leg_velocity_scale','_leg_velocity_scale').replace('idle_leg_velocity_mse','leg_velocity_mse').replace('All idle cohorts; linear and angular world-body velocity MSE; existing handoff retained','All rows; legs only; linear and angular world-body velocity MSE including prior custom MSE; existing handoff retained')
    compile(s,'perturbed_omni.py','exec');entries['pipeline/perturbed_omni.py']=s.encode()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml']);assert cfg['perturbed_motion'].pop('idle_leg_velocity_mse_multiplier')==5.
    cfg['perturbed_motion']['leg_velocity_mse_multiplier']=5.
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    source=h.OUT/'source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    plan=dict(old,source=dict(local=str(source),sha256=sha,key='mimickit/pipeline_20261014/all-rows-leg-vel5/source_'+sha[:12]+'.zip'),run_suffix='uefn_locomotion_all_legvel5_4000ada_2048')
    h.save('prepared',plan)
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(h.OUT/'overlay.zip','w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl',pickle.dumps(z.infolist()))
        for n in ['pipeline/perturbed_omni.py','prepared/env_config.yaml']:delta.writestr(n,entries[n])
    for filename,device in [('test.py','cpu'),('test-gpu.py','cuda')]:
        test=(ORIGINAL_OUT/filename).read_text()
        test=h.one(test,textwrap.indent(textwrap.dedent(h.BLOCK),' '),textwrap.indent(textwrap.dedent(BLOCK),' '))
        test=test.replace('_idle_velocity_leg_ids','_velocity_leg_ids').replace('_idle_leg_velocity_scale','_leg_velocity_scale').replace('weights[:4,9:]=5','weights[:,9:]=5').replace('four idle cohorts; locomotion/recovery excluded; other channels unchanged; handoff and graph checked','all rows; legs velocity/angular velocity x5 only; position/rotation and upper-body weights unchanged; prior/handoff and graph checked')
        (h.OUT/filename).write_text(test)
        if device=='cpu':exec(compile(test,'all_leg_test','exec'),{})
    print(json.dumps(plan['source']))

def verify():
    (h.d.OUT/'latest-restart-receipt.txt').write_text(str(h.OUT))
    script=Path(__file__).with_name('verify_loco_unchanged_resume.py').read_text()
    script=h.one(script,"  assert yaml.safe_load(cp.read(name))==yaml.safe_load((p/name).read_text()),name","""  expected=yaml.safe_load(cp.read(name));actual=yaml.safe_load((p/name).read_text())
  if name=='env_config.yaml':
   assert expected['perturbed_motion'].pop('idle_leg_velocity_mse_multiplier')==5.
   expected['perturbed_motion']['leg_velocity_mse_multiplier']=5.
  assert expected==actual,name""")
    script=h.one(script," assert row['frame_com2_reward_multiplier']"," assert row['frame_com2_reward_multiplier']\n assert row['leg_velocity_mse']['multiplier']==5. and len(row['leg_velocity_mse']['bodies'])==6\n assert row['leg_velocity_mse']['scope'].startswith('All rows')\n assert 'idle_stop' not in row['loss_term_names'] and 'leg_reversal' in row['loss_term_names']")
    scope={'__name__':'isolated_all_leg_verification'};exec(compile(script,'all_leg_live_verify','exec'),scope);scope['main']()
    result=json.loads((h.OUT/'live-verification.json').read_text())
    if result['ready']:print(h.r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Handoff verified')",timeout=20))

if __name__=='__main__':
    action=sys.argv[1]
    (globals()[action] if action in ['prepare','verify'] else getattr(h,action))()

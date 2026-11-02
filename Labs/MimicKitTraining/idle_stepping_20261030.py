"""Restore only the existing cadence penalty for all idle, without prior fading."""
import ast, hashlib, json, pickle, sys, tempfile, zipfile
from pathlib import Path
from types import SimpleNamespace
import yaml
import idle_vanilla_com2_20261030 as base
h = base.h
h.OUT = h.d.OUT/'idle-stepping-20261030'


def prepare():
    h.OUT.mkdir(exist_ok=True)
    plan=json.loads((h.d.OUT/'getup-success-prepared.json').read_text())
    h.save('previous-plan',plan)
    assert plan['source']['sha256']=='674651d72c0dba38daf9f3bdd4b1115e7b9306dc4403d2aa729d14041242771a'
    with zipfile.ZipFile(plan['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    s=entries['pipeline/perturbed_omni.py'].decode();one=h.one
    s=one(s,"        self._idle_mse_com2_only = bool(cfg.get('idle_vanilla_mse_com2_only', False))", "        self._idle_mse_com2_only = bool(cfg.get('idle_vanilla_mse_com2_only', False))\n        self._idle_excessive_stepping = bool(cfg.get('idle_excessive_stepping', False))")
    s=one(s,"[name == 'com2_velocity' for name in self.loss_term_names[4:]]", "[name == 'com2_velocity' or (self._idle_excessive_stepping and name in ('excessive_stepping', 'leg_reversal')) for name in self.loss_term_names[4:]]")
    s=one(s,"        # Exactly the same fade as AE, including the repeated P-minus idle handoff.\n        foot_terms = torch.cat((raw[:, :1]*(1-self._tracking_mix[:, None]), reversals), -1)*self._foot_loss_weights", """        # Locomotion retains its prior fade; idle has no prior and keeps full cadence cost.
        cadence_mix = 1-self._tracking_mix
        if self._idle_excessive_stepping:
            cadence_mix = torch.where(self._idle_mse_rows, 1., cadence_mix)
        foot_terms = torch.cat((raw[:, :1]*cadence_mix[:, None], reversals), -1)*self._foot_loss_weights""")
    s=one(s,"# Four original calibrated MSEs plus COM2; every other idle term is zero.","# Four original MSEs plus explicitly enabled extras; all other idle terms zero.")
    anchor="            result['whole_body_velocity_mse']['multiplier'] = 1."
    s=one(s,anchor,"""            if self._idle_excessive_stepping:
                result['active_loss_terms'].extend(['excessive_stepping', 'leg_reversal'])
                result['leg_reversal'] = self._perturb_cfg['leg_reversal']['description']
                result['idle_excessive_stepping'] = dict(weight=float(self._foot_loss_weights[0]),
                    period_ticks=self._foot_periods[self._motion_ids[world]].cpu().tolist(),
                    scope='All idle cohorts, all episode ticks, no prior fade; original cadence detector/weight')
                result['reward_definition'] = '1/(1+four original calibrated MSEs+COM2+excessive stepping+leg reversal); existing terminal penalties unchanged'
"""+anchor)
    s=one(s,"original four calibrated MSEs at full strength plus existing COM2; no other losses/multiplier or supervised phase loss.", "original four calibrated MSEs at full strength plus existing COM2 and configured excessive stepping/leg reversal; no other losses/multiplier or supervised phase loss.")
    compile(s,'perturbed_omni.py','exec');entries['pipeline/perturbed_omni.py']=s.encode()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml']);cfg['perturbed_motion']['idle_excessive_stepping']=True
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    # Exercise the launcher's actual resume guard before stopping production.
    tree=ast.parse(entries['pipeline/train.py'])
    loop=next(n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.iter,ast.List) and any(isinstance(x,ast.Constant) and x.value=='engine_config.yaml' for x in n.iter.elts))
    class Args(SimpleNamespace):
        def __getattr__(self,key):return None
    with tempfile.TemporaryDirectory() as tmp,zipfile.ZipFile(plan['checkpoint']['local']) as bundle:
        directory=Path(tmp)
        for n in ['engine_config.yaml','env_config.yaml','agent_config.yaml']:(directory/n).write_bytes(entries['prepared/'+n])
        exec(compile(ast.Module(body=[loop],type_ignores=[]),'actual_resume','exec'),dict(yaml=yaml,bundle=bundle,directory=directory,config=cfg,a=Args(omni_run_lr=True,equipment_omni=True,resume_perturbed_motion=True)))
    source=h.OUT/'source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    h.save('prepared',dict(plan,source=dict(local=str(source),sha256=sha,key='mimickit/pipeline_20261014/idle-stepping/source_'+sha[:12]+'.zip'),run_suffix='uefn_locomotion_idle_mse_com2_steps_legs_4000ada_2048'))
    changed=['pipeline/perturbed_omni.py','prepared/env_config.yaml']
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(h.OUT/'overlay.zip','w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl',pickle.dumps(z.infolist()))
        for n in changed:delta.writestr(n,entries[n])
    (h.OUT/'test-gpu.py').write_text("""from pathlib import Path
import zipfile,py_compile
r=Path('/workspace/mimickit_trial/idle-stepping-preflight');r.mkdir(exist_ok=True)
with zipfile.ZipFile('/workspace/mimickit_trial/idle-leg-source.zip') as z:z.extractall(r)
py_compile.compile(str(r/'pipeline/perturbed_omni.py'),doraise=True)
print('Staged source compiles')
""")
    # Reuse the prior physical rollout oracle, expanding only its expected idle extras.
    test=Path(__file__).with_name('preflight_idle_vanilla_com2_20261030.py').read_text()
    test=test.replace('idle-vanilla-preflight','idle-stepping-preflight').replace("6998)","6997)")
    test=one(test,"n != 'com2_velocity'", "n not in ('com2_velocity','excessive_stepping','leg_reversal')")
    test=one(test,"        valid = idle & (done == 0)","""        step_idx = e.loss_term_names.index('excessive_stepping')
        step_expected = e._foot_regularizers.raw[:,0] * e._foot_loss_weights[0]
        step_expected *= torch.where(idle, 1., 1-e._tracking_mix)
        torch.testing.assert_close(e.loss_terms[:,step_idx], step_expected, rtol=1e-6, atol=1e-6)
        leg_expected = ((e._leg_reversal.raw-e._leg_allowance[e._motion_ids]).clamp_min(0)*e._leg_weights).sum(-1)
        torch.testing.assert_close(e.loss_terms[:,e.loss_term_names.index('leg_reversal')], leg_expected)
        valid = idle & (done == 0)""")
    test=one(test,"+com2[valid])).abs()", "+com2[valid]+step_expected[valid]+leg_expected[valid])).abs()")
    test=one(test,"list(e.loss_term_names[:4])+['com2_velocity']", "list(e.loss_term_names[:4])+['com2_velocity','excessive_stepping','leg_reversal']")
    test=one(test,"report = dict(passed=True", """# Force a too-fast repeated per-foot lift history to verify all idle cohorts are charged.
e._foot_regularizers.interval.fill_(1.);e._foot_regularizers.lift_age.zero_()
with torch.no_grad():e._update_reward()
assert (e.loss_terms[idle,step_idx] > 0).all()
torch.testing.assert_close(e.loss_terms[idle,step_idx], e._foot_regularizers.raw[idle,0]*e._foot_loss_weights[0])
assert (e.loss_terms[idle][:,extras]==0).all()
report = dict(cadence_weight=float(e._foot_loss_weights[0]), forced_cadence_all_idle_positive=True, passed=True""")
    (h.OUT/'preflight.py').write_text(test)
    h.save('delta',dict(files=changed,weight=cfg['perturbed_motion']['foot_regularizers']['weights'][0],actual_resume_guard_passed=True))
    print(json.dumps(dict(source=sha,files=changed,weight=cfg['perturbed_motion']['foot_regularizers']['weights'][0])))


def verify():
    (h.d.OUT/'latest-restart-receipt.txt').write_text(str(h.OUT))
    script=Path(__file__).with_name('verify_loco_unchanged_resume.py').read_text()
    script=h.one(script,"  assert yaml.safe_load(cp.read(name))==yaml.safe_load((p/name).read_text()),name", """  expected=yaml.safe_load(cp.read(name));actual=yaml.safe_load((p/name).read_text())
  if name=='env_config.yaml':expected['perturbed_motion']['idle_excessive_stepping']=True
  assert expected==actual,name""")
    script=h.one(script," assert row['frame_com2_reward_multiplier']", """ assert row['frame_com2_reward_multiplier']
 if row['idle_row']:
  assert row['ae_disabled'] and not row['auto_phase_supervised']
  assert row['whole_body_velocity_mse']['multiplier']==1.
  assert row['active_loss_terms']==row['loss_term_names'][:4]+['com2_velocity','excessive_stepping','leg_reversal']
  assert abs(row['idle_excessive_stepping']['weight']-118.63277437209068)<1e-4
  terms=z['loss_terms'+('' if i==0 else '_'+str(i))]
  extra=[j for j,n in enumerate(row['loss_term_names']) if n not in row['active_loss_terms']]
  assert (terms[:,extra]==0).all()
  assert all(v==1 for v in row['frame_com2_reward_multiplier'])""")
    scope={'__name__':'idle_stepping_verify'};exec(compile(script,'idle_stepping_verify','exec'),scope);scope['main']()
    if json.loads((h.OUT/'live-verification.json').read_text())['ready']:
        print(h.r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Handoff verified')",timeout=20))


if __name__=='__main__':
    action=sys.argv[1]
    (globals()[action] if action in ['prepare','verify'] else base.stop if action=='stop' else getattr(h,action))()

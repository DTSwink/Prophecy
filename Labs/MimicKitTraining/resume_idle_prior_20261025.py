"""Pinned-source P-minus push handoff; no additional early tracking MSE."""
import ast
import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
import torch
import yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
import resume_pushed_idle_penalty as handoff
from prior_handoff import tracking_handoff

OUT = d.OUT / 'idle-prior-handoff-20261025'


def replace_once(source, old, new):
    assert source.count(old) == 1, old[:100]
    return source.replace(old, new, 1)


def patch_env(source):
    line = next(x for x in source.splitlines() if x.startswith('from perturbed_motion import '))
    source = replace_once(source, line, line+'\nfrom prior_handoff import tracking_handoff')
    source = replace_once(source,
        "        self._prior = None if self._mse_only else MotionPrior(cfg['ae_directory'], len(self._prior_ids), self._device)",
        "        self._prior = None  # Construct after the final-phase cohorts are known.")
    source = replace_once(source,
        "            self._final = FinalLocomotion(self, cfg['final_phase'])",
        """            self._final = FinalLocomotion(self, cfg['final_phase'])
        self._pushed_idle_prior_handoff = bool(cfg.get('pushed_idle_prior_handoff', False))
        if self._pushed_idle_prior_handoff:
            if self._mse_only or not hasattr(self, '_final'):
                raise ValueError('P-minus prior handoff requires the prior and final-phase cohorts')
            prior_rows = prior_rows | self._final.minus
            self._prior_ids = torch.where(prior_rows)[0]
            self._prior_index.fill_(-1)
            self._prior_index[self._prior_ids] = torch.arange(len(self._prior_ids), device=self._device)
        self._prior = None if self._mse_only else MotionPrior(cfg['ae_directory'], len(self._prior_ids), self._device)""")
    source = replace_once(source,
        "        self._tracking_mix.copy_(torch.where(self._perturbed_rows, mix, 1.))",
        """        self._tracking_mix.copy_(torch.where(self._perturbed_rows, mix, 1.))
        if self._pushed_idle_prior_handoff:
            self._tracking_mix.copy_(tracking_handoff(torch.round(self._time_buf*30),
                self._perturbed_rows, self._final.minus, self._final.last_kick,
                self._perturb_cfg['ae_ticks'], self._perturb_cfg['blend_ticks']))""")
    return source


def patch_final(source):
    old = "        return result\n"
    new = """        if self.minus[world] and self.env._perturb_cfg.get('pushed_idle_prior_handoff', False):
            result.update(ae_disabled=False, ae_ticks=self.env._perturb_cfg['ae_ticks'],
                blend_ticks=self.env._perturb_cfg['blend_ticks'], ae_mse_weight=0.,
                prior_handoff_clock='last push; full MSE before first push',
                prior_handoff_restart='every push; 30 ticks prior then 30 ticks linear fade')
        return result
"""
    return replace_once(source, old, new)


def check(source):
    class Base:
        def _tracking_losses(self, *args):
            return torch.full((4, 5), 2.)
    method = next(n for c in ast.parse(source).body if isinstance(c, ast.ClassDef)
                  for n in c.body if isinstance(n, ast.FunctionDef) and n.name == '_base_perturbed_tracking_losses')
    scope = dict(torch=torch, Base=Base, tracking_handoff=tracking_handoff,
        tracking_blend=lambda t,a,b:((t-a)/b).clamp(0,1),
        EnvMode=SimpleNamespace(TRAIN=1), q=SimpleNamespace(quat_to_matrix=lambda x:x))
    cls = ast.ClassDef(name='Trial', bases=[ast.Name(id='Base',ctx=ast.Load())], keywords=[],body=[method],decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])), 'actual-reward', 'exec'),scope)
    checks=[]
    for tick in [0,2,29,30,45,59,60,61,89,90,105,119,120,121,150,165,179,180]:
        last = -1 if tick < 60 else (tick//60)*60
        env=scope['Trial']()
        vars(env).update(_perturb_ready=True,_refresh_reward_rotations=lambda:None,
            _perturbed_ids=torch.tensor([0,1]),_prior_ids=torch.tensor([0,1,2]),
            _prior=SimpleNamespace(append=lambda *a:None,cost=lambda:torch.full((3,),5.)),
            _prior_raw=torch.zeros(4),_time_buf=torch.full((4,),tick/30.),_mse_only=False,
            _perturb_cfg=dict(ae_ticks=30,blend_ticks=30,ae_mse_weight=0.),
            _perturbed_getup=torch.zeros(4,dtype=torch.bool),_perturbed_rows=torch.tensor([True,True,False,False]),
            _idle_position_getup=True,_tracking_mix=torch.ones(4),_dispatch_no_getups=True,
            _pushed_idle_prior_handoff=True,_final=SimpleNamespace(minus=torch.tensor([False,False,True,False]),last_kick=torch.tensor([-1,-1,last,-1])),
            _ae_weight=.2,_mode=0,_additive_head_reward=False,
            _append_extremity_speed_loss=lambda terms,*args:terms,_append_walking_airborne_loss=lambda terms,*args:terms,
            loss_term_names=('position_mse','linear_velocity_mse','rotation_mse','angular_velocity_mse','flat_com_velocity','motion_prior'))
        terms=env._base_perturbed_tracking_losses(torch.ones(4,15,3),torch.ones(4,15,4),None,None,None,None)
        regular=max(0.,min(1.,(tick-30)/30))
        minus=1. if last<0 else max(0.,min(1.,(tick-last-30)/30))
        expected=torch.tensor([[2*regular]*4+[0.,1-regular],[2*regular]*4+[0.,1-regular],
                              [2*minus]*4+[2.,1-minus],[2.]*5+[0.]])
        torch.testing.assert_close(terms,expected)
        checks.append(dict(tick=tick,last_push=last,p_mse=regular,minus_mse=minus))
    return checks


def prepare():
    OUT.mkdir(exist_ok=True)
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text());previous=plan['source']
    assert previous['sha256']=='450a177a000a6ed5d8a4523cfac3fcd3a422e57e861e5d55f6c205bb272221a5'
    assert hashlib.sha256(Path(previous['local']).read_bytes()).hexdigest()==previous['sha256']
    (OUT/'previous-plan.json').write_text(json.dumps(plan,indent=2))
    with zipfile.ZipFile(previous['local']) as old:
        cfg=yaml.safe_load(old.read('prepared/env_config.yaml'));before=copy.deepcopy(cfg)
        cfg['perturbed_motion']['ae_mse_weight']=0.
        cfg['perturbed_motion']['pushed_idle_prior_handoff']=True
        check_cfg=copy.deepcopy(cfg);check_cfg['perturbed_motion'].pop('pushed_idle_prior_handoff')
        check_cfg['perturbed_motion']['ae_mse_weight']=before['perturbed_motion']['ae_mse_weight'];assert check_cfg==before
        env=patch_env(old.read('pipeline/perturbed_omni.py').decode())
        final=patch_final(old.read('pipeline/final_locomotion.py').decode())
        overlays={'pipeline/perturbed_omni.py':env.encode(),'pipeline/final_locomotion.py':final.encode(),
            'pipeline/prior_handoff.py':Path(__file__).with_name('prior_handoff.py').read_bytes(),
            'prepared/env_config.yaml':yaml.safe_dump(cfg,sort_keys=False).encode()}
        for name,data in overlays.items():
            p=OUT/'candidate'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            if name.endswith('.py'):compile(data,name,'exec')
        checks=check(env)
        source=OUT/'source-stored.zip'
        with zipfile.ZipFile(source,'w') as new:
            for info in old.infolist():new.writestr(copy.copy(info),overlays.get(info.filename,old.read(info.filename)))
            info=zipfile.ZipInfo('pipeline/prior_handoff.py',(2026,10,25,0,0,0));info.create_system=3;info.external_attr=0o600<<16
            new.writestr(info,overlays[info.filename])
        with zipfile.ZipFile(source) as new:
            changed=[n for n in old.namelist() if old.read(n)!=new.read(n)]
            assert set(changed)==set(overlays)-{'pipeline/prior_handoff.py'}
            assert new.testzip() is None
    sha=hashlib.sha256(source.read_bytes()).hexdigest();key='mimickit/pipeline_20261014/idle-prior-handoff/source_'+sha[:12]+'.zip'
    plan.update(source=dict(local=str(source),key=key,sha256=sha),run_suffix='uefn_locomotion_idle_prior_2048')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2))
    (OUT/'checks.json').write_text(json.dumps(dict(changed=changed,checks=checks,source_sha256=sha),indent=2))
    with zipfile.ZipFile(OUT/'overlay.zip','w') as z:
        for n,data in overlays.items():z.writestr(n,data)
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'overlay.zip','/workspace/mimickit_trial/idle-prior-overlay.zip',timeout=40)
    code='''from pathlib import Path
import copy,hashlib,json,zipfile,boto3
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD
with zipfile.ZipFile(r/'idle-prior-overlay.zip') as z:overlay={n:z.read(n) for n in z.namelist()}
with zipfile.ZipFile(r/'source.zip') as old,zipfile.ZipFile(r/'idle-prior-source.zip','w') as new:
 for info in old.infolist():new.writestr(copy.copy(info),overlay.get(info.filename,old.read(info.filename)))
 info=zipfile.ZipInfo('pipeline/prior_handoff.py',(2026,10,25,0,0,0));info.create_system=3;info.external_attr=0o600<<16
 new.writestr(info,overlay[info.filename])
data=(r/'idle-prior-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('Pinned candidate and persistent readback verified; running source untouched')
'''.replace('OLD',repr(previous['sha256'])).replace('SHA',repr(sha)).replace('KEY',repr(key))
    print(r.remote(code,timeout=60),flush=True)
    active=json.loads((d.OUT/'active_run.json').read_text());assert active['pod']=='w754z82j94t55a'
    d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))
    # The shared environment file belongs to the recovery branch and lacks final-phase
    # cohorts. Keep the complete edited production source in candidate/ and the archive.
    print(json.dumps(dict(source=plan['source'],checks=len(checks),changed=changed)),flush=True)


def verify():
    plan=json.loads((OUT/'prepared.json').read_text())
    active=json.loads((d.OUT/'active_run.json').read_text());name=active['run']
    assert active['pod']=='w754z82j94t55a' and name.endswith(plan['run_suffix'])
    code="""from pathlib import Path
import json,time,hashlib,yaml
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text())
assert s['state']=='training' and time.time()-s['updated_unix']<180
assert s['iteration']>INITIAL+10
assert not (p/'finished.json').exists() and not (p/'backup_errors.json').exists()
assert b['key'].split('/')[-2]==NAME
assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==SHA
cfg=yaml.safe_load((r/'prepared/env_config.yaml').read_text())['perturbed_motion']
assert cfg['pushed_idle_prior_handoff'] and cfg['ae_mse_weight']==0
assert cfg['ae_ticks']==30 and cfg['blend_ticks']==30
assert cfg['com2_loss_weight']==56.41750205477203
dispatch=json.loads((p/'lossless_dispatch.json').read_text())
assert dispatch['worlds']==2048 and dispatch['physics_kernel_intercepts']==dict(velocity=8,derivative=8)
assert dispatch['factor_intercepts']==16 and dispatch['cached_cholesky_intercepts']==16
assert dispatch['cached_cholesky_blocks'] and dispatch['reference_done_graphs'] and dispatch['converged_newton_direction_skip']
ev=json.loads((p/'evaluation.json').read_text())
rows=ev.get('replay',{}).get('replay_rows',[])
minus=[row for row in rows if row.get('final_phase_cohort')=='idle perturbed-']
assert minus and all(row.get('prior_handoff_restart')=='every push; 30 ticks prior then 30 ticks linear fade' and row.get('ae_mse_weight')==0 for row in minus)
print(json.dumps(dict(run=NAME,status=s,backup=b,dispatch=dispatch,pushed_idle_rows=minus)))
""".replace('NAME',repr(name)).replace('INITIAL',str(plan['checkpoint']['finished']['iteration'])).replace('SHA',repr(plan['source']['sha256']))
    result=json.loads(r.remote(code,timeout=30))
    (OUT/'live-verification.json').write_text(json.dumps(result,indent=2))
    print(r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Verified handoff complete')",timeout=20))
    print(json.dumps(dict(run=result['run'],iteration=result['status']['iteration'],samples=result['status']['samples'],backup=result['backup'])),flush=True)


if __name__=='__main__':
    handoff.OUT=OUT
    if sys.argv[1] in ['stop','capture','launch']:getattr(handoff,sys.argv[1])()
    else:globals()[sys.argv[1]]()

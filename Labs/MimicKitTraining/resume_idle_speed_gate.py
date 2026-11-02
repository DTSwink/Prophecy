"""Pinned locomotion change: gated perturbed-idle COM2 amplitude failure."""
import ast,hashlib,json,pickle,sys,zipfile,math
from pathlib import Path
from types import SimpleNamespace as NS
import torch,yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
import resume_pushed_idle_penalty as handoff

OUT=d.OUT/'idle-speed-gate'

def patch_env(s):
    edits=[
    ('        self._com2_targets = torch.tensor(targets, device=self._device)', '''        self._com2_targets = torch.tensor(targets, device=self._device)
        self._idle_speed_ratio = float(cfg.get('idle_speed_walk_f_ratio', 0.))
        self._idle_speed_limits_sq = None
        if self._idle_speed_ratio:
            if not math.isfinite(self._idle_speed_ratio) or self._idle_speed_ratio <= 0:
                raise ValueError('Invalid perturbed idle speed ratio')
            # Reference trunk COM2 mean speed, matching drawn/unarmed equipment.
            limits = [float(entries['M_Neutral_Walk_Loop_F_' +
                ('Drawn' if bool(self._equipment[i]) else 'Unarmed')]['speed_m_s']) * self._idle_speed_ratio
                for i in range(self._motion_lib.get_num_motions())]
            self._idle_speed_limits_sq = torch.tensor(limits, device=self._device).square()'''),
    ("        failed &= (self._gaits[self._motion_ids] != -1) & (ticks > self._perturb_cfg['grace_ticks'])", """        failed &= self._gaits[self._motion_ids] != -1
        idle_speed_failed = torch.zeros_like(failed)
        if self._idle_speed_limits_sq is not None:
            idle_speed_failed = (self._perturbed_rows & ~self._recovery_rows &
                (self._gaits[self._motion_ids] == -1) &
                (velocity.square().sum(-1) > self._idle_speed_limits_sq[self._motion_ids]))
            failed |= idle_speed_failed
        failed &= ticks > self._perturb_cfg['grace_ticks']"""),
    ("            self._reward_buf.sub_(loco_failed.to(self._reward_buf.dtype) * loco_penalty)\n        normal_penalty = float(self._perturb_cfg.get('normal_getup_failure_penalty', 0.))", """            self._reward_buf.sub_(loco_failed.to(self._reward_buf.dtype) * loco_penalty)
        if loco_penalty:
            # Same one-time cost as locomotion, after the common velocity gate.
            self._reward_buf.sub_((idle_speed_failed & failed).to(self._reward_buf.dtype) * loco_penalty)
        normal_penalty = float(self._perturb_cfg.get('normal_getup_failure_penalty', 0.))"""),
    ("        if self._mse_only:\n            result.update(ae_only=False", """        if not loco and not getup and self._idle_speed_limits_sq is not None:
            result.update(timeout_only=False, com2_termination=True,
                com2_termination_mode='speed_only', com2_direction_check=False,
                com2_speed_limit_m_s=float(self._idle_speed_limits_sq[self._motion_ids[world]].sqrt()),
                com2_speed_reference='M_Neutral_Walk_Loop_F_' + ('Drawn' if bool(self._equipment[self._motion_ids[world]]) else 'Unarmed'),
                com2_speed_reference_ratio=self._idle_speed_ratio, com2_speed_ratios=None,
                idle_velocity_failure_penalty=float(self._perturb_cfg.get('loco_failure_penalty', 0.)))
        if self._mse_only:
            result.update(ae_only=False""")]
    for old,new in edits:
        assert s.count(old)==1,old
        s=s.replace(old,new)
    return s

def patch_replay(s):
    old="            expected-=float(meta.get('pushed_idle_failure_penalty',0.))*(data[1:,0]==1)"
    assert s.count(old)==1
    return s.replace(old,old+"\n            expected-=float(meta.get('idle_velocity_failure_penalty',0.))*(data[1:,0]==1)")

def test(source,entries):
    # Execute the actual changed done method, with deterministic physical inputs.
    from perturbed_motion import com2_velocity,com2_failure
    tree=ast.parse(source)
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_update_done')
    class Base:
        def _update_done(self):self._done_buf.copy_(self.initial_done)
    cls=ast.ClassDef(name='E',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=[fn],decorator_list=[])
    flags=NS(**{k:NS(value=v) for k,v in [('NULL',0),('FAIL',1),('SUCC',2),('TIME',3)]})
    scope=dict(Base=Base,torch=torch,DoneFlags=flags,EnvMode=NS(TRAIN=1),com2_velocity=com2_velocity,com2_failure=com2_failure)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),'pinned_changed_done','exec'),scope)
    ticks=torch.tensor([0,8,9,79,80,129,130,149,49,50,50,50,50,50,50,50,150,50,50,50],dtype=torch.float32)
    n=len(ticks);e=scope['E']();e._time_buf=ticks/30;e._episode_length=10;e._perturb_ready=True;e._mode=0
    e._perturbed_rows=torch.ones(n,dtype=torch.bool);e._perturbed_rows[12:14]=False
    e._recovery_rows=torch.zeros(n,dtype=torch.bool);e._perturbed_getup=e._recovery_rows.clone()
    e._motion_ids=torch.zeros(n,dtype=torch.long);e._motion_ids[14:16]=1
    e._gaits=torch.tensor([-1.,0.]);e._head_id=0;e._head_reset_height=torch.tensor([2.,2.])
    e._com2_ids=[0];e._com2_masses=torch.ones(1);e._com2_targets=torch.tensor([[0.,0.],[1.,0.]])
    e._idle_speed_limits_sq=torch.ones(2);e._extremity_speed_enabled=False
    e._perturb_cfg=dict(episode_ticks=150,getup_ticks=180,grace_ticks=8,min_speed_ratio=.7,loco_failure_penalty=100.,pushed_idle_failure_penalty=100.)
    e._reward_buf=torch.full((n,),.5);e._done_buf=torch.zeros(n,dtype=torch.long);e.initial_done=e._done_buf.clone();e.initial_done[12:14]=1
    e._reset_reason=e._done_buf.clone();e._get_char_id=lambda:0
    vel=torch.zeros(n,1,3);vel[:,0,0]=1.1;vel[10,0,0]=1.;vel[11,0,0]=-1.;vel[14,0,0]=.6;vel[15,0,0]=1.;vel[16,0,0]=0.;vel[17,0,0]=0.;vel[17,0,1]=-1.1;vel[18,0,0]=.1;vel[19,0,0]=0;vel[19,0,2]=100
    e._engine=NS(get_body_vel=lambda _:vel,get_body_pos=lambda _:torch.zeros(n,1,3))
    minus=torch.zeros(n,dtype=torch.bool);minus[12]=True
    # Exact existing gate expression: no first-foot observation occurs in this synthetic fixture.
    ft=ast.parse(entries['pipeline/final_locomotion.py']);method=next(n for n in ast.walk(ft) if isinstance(n,ast.FunctionDef) and n.name=='velocity_gate')
    expression=compile(ast.Expression(next(n.value for n in method.body if isinstance(n,ast.Return))),'pinned_gate','eval')
    f=NS(pushed=torch.arange(n)<8,plus=torch.arange(n)>=8,first_foot=torch.zeros(n,dtype=torch.long),cfg={'plus_foot_grace':50},minus=minus)
    e._final=f;f.velocity_gate=lambda t:eval(expression,dict(self=f,ticks=t))
    e._update_done()
    expected=[0,0,1,1,0,0,1,1,0,1,0,0,1,1,1,0,3,1,0,0]
    assert e._done_buf.tolist()==expected,e._done_buf
    expected_reward=[-.0+(-99.5 if flag==1 and i!=13 else .5) for i,flag in enumerate(expected)]
    torch.testing.assert_close(e._reward_buf,torch.tensor(expected_reward))
    return dict(ticks=ticks.tolist(),done=e._done_buf.tolist(),rewards=e._reward_buf.tolist(),
        checks=['0/8 grace;9/79 enabled;80/129 disabled;130 enabled','plus49/50 grace boundary','exact limit allowed;negative direction allowed at limit','nonzeroZ ignored','idle-minus existing100 retained;normal idle untouched','loco existing rules/100 retained','idle timeout unpenalized'])

def prepare():
    OUT.mkdir(exist_ok=True);plan=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    (OUT/'previous-plan.json').write_text(json.dumps(plan,indent=2));previous=plan['source']
    changed={}
    with zipfile.ZipFile(previous['local']) as z:
        for key,patch in [('pipeline/perturbed_omni.py',patch_env),('pipeline/replay.py',patch_replay)]:
            changed[key]=patch(z.read(key).decode().replace('\r\n','\n')).encode();compile(changed[key],key,'exec')
        cfg=yaml.safe_load(z.read('prepared/env_config.yaml'));cfg['perturbed_motion']['idle_speed_walk_f_ratio']=.4
        changed['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
        result=test(changed['pipeline/perturbed_omni.py'],{'pipeline/final_locomotion.py':z.read('pipeline/final_locomotion.py')})
        refs=json.loads(z.read('prepared/com2_targets.json'))['motions']
        result['limits_m_s']={x['id']:.4*x['speed_m_s'] for x in refs if x['id'] in ['M_Neutral_Walk_Loop_F_Unarmed','M_Neutral_Walk_Loop_F_Drawn']}
        source=OUT/'source-stored.zip'
        with zipfile.ZipFile(source,'w') as dst:
            for info in z.infolist():dst.writestr(info,changed.get(info.filename,z.read(info.filename)))
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(OUT/'delta.zip','w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl',pickle.dumps(z.infolist(),protocol=4))
        for key,data in changed.items():delta.writestr(key,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    plan.update(source=dict(local=str(source),key='mimickit/pipeline_20261014/idle-speed-gate/source_'+sha[:12]+'.zip',sha256=sha),run_suffix='uefn_locomotion_idle_speed40_2048')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2));(OUT/'verification.json').write_text(json.dumps(result,indent=2))
    # Apply only this scoped edit to shared source, preserving unrelated recovery work.
    for file,fn in [('perturbed_omni.py',patch_env),('replay.py',patch_replay)]:
        path=Path(__file__).with_name(file);path.write_text(fn(path.read_text()))
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'delta.zip','/workspace/mimickit_trial/idle-speed-delta.zip',timeout=45)
    code="""from pathlib import Path
import json,hashlib,zipfile,pickle,boto3
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD_SHA
with zipfile.ZipFile(r/'source.zip') as old,zipfile.ZipFile(r/'idle-speed-delta.zip') as delta,zipfile.ZipFile(r/'idle-speed-source.zip','w') as new:
 for info in pickle.loads(delta.read('infos.pkl')):new.writestr(info,delta.read(info.filename) if info.filename in delta.namelist() else old.read(info.filename))
data=(r/'idle-speed-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('Idle-speed source persistent readback verified')
""".replace('OLD_SHA',repr(previous['sha256'])).replace('SHA',repr(sha)).replace('KEY',repr(plan['source']['key']))
    print(r.remote(code,timeout=60),flush=True)
    active=json.loads((d.OUT/'active_run.json').read_text());d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))
    print(json.dumps(result),flush=True)

def verify():
    active=json.loads((d.OUT/'active_run.json').read_text());name=active['run'];assert 'idle_speed40_2048' in name
    initial=json.loads((OUT/'prepared.json').read_text())['checkpoint']['finished']['iteration']
    code="""from pathlib import Path
import json,time,yaml
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
end=time.time()+35
while time.time()<end:
 if (p/'status.json').exists() and (p/'backup_status.json').exists() and (p/'evaluation.json').exists():
  if json.loads((p/'status.json').read_text()).get('iteration',0)>INITIAL:break
 if (p/'failure.json').exists():raise RuntimeError((p/'failure.json').read_text())
 time.sleep(3)
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text())
assert s['state']=='training' and s['iteration']>INITIAL and time.time()-s['updated_unix']<180
assert not (p/'finished.json').exists() and not (p/'backup_errors.json').exists()
cfg=yaml.safe_load((p/'env_config.yaml').read_text());assert cfg['perturbed_motion']['idle_speed_walk_f_ratio']==.4
rows=json.loads((p/'evaluation.json').read_text())['replay']['replay_rows']
minus=[x for x in rows if x.get('final_phase_cohort')=='idle perturbed-']
assert minus and all(x['pushed_idle_failure_penalty']==100 and not x['stock_pose_termination'] and x['contact_termination'] for x in minus)
idle=[x for x in rows if x.get('perturbed_row') and x.get('idle_row')]
assert all(x.get('idle_velocity_failure_penalty')==100 and x.get('com2_termination_mode')=='speed_only' and x['com2_direction_check']==False for x in idle)
(r/'loco_ae30_handoff_complete').touch()
print(json.dumps(dict(run=NAME,status={k:s.get(k) for k in ['state','iteration','samples','worlds','training_transitions_per_second']},backup=b,idle_replay_present=bool(idle),idle=[{k:x.get(k) for k in ['final_phase_cohort','terminal_flag','com2_speed_limit_m_s','velocity_gate','idle_velocity_failure_penalty']} for x in idle])))
""".replace('NAME',repr(name)).replace('INITIAL',str(initial))
    result=json.loads(r.remote(code));(OUT/'live-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    handoff.OUT=OUT;action=sys.argv[1]
    if action in ['stop','capture','launch']:getattr(handoff,action)()
    else:globals()[action]()

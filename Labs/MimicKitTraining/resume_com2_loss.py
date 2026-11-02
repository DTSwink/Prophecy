"""Precomputed COM2 guidance, calibrated offline; guarded latest-checkpoint handoff."""
import ast, hashlib, json, pickle, shutil, sys, zipfile
from pathlib import Path
import numpy as np
import torch
import yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
import resume_pushed_idle_penalty as handoff

OUT = d.OUT/'com2-loss'

def precompute():
    OUT.mkdir(exist_ok=True)
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    (OUT/'previous-plan.json').write_text(json.dumps(plan,indent=2))
    # Reuse the established exact reference-velocity reconstruction, from this run's assets.
    source=Path(__file__).with_name('prepare_perturbed_com2.py').read_text()
    source=source.replace("out = ROOT/'Saved/MimicKitEquipment/perturbed-preparation'",'out = Path('+repr(str(OUT))+')')
    source=source.replace("archive = ROOT/'Exports/MimicKitEquipment/20261019_stopped_47039/training_source.zip'",'archive = Path('+repr(plan['source']['local'])+')')
    source=source.replace('times = (torch.arange(intervals)+.5)*(duration/intervals)', 'times = torch.unique(torch.cat(((torch.arange(intervals)+.5)*(duration/intervals), torch.linspace(0, duration, intervals+1))))\n        intervals = len(times)')
    source=source.replace('rows = []', "original = json.loads((source/'prepared/com2_targets.json').read_text())\n    targets = {x['id']:x['average_xy_m_s'] for x in original['motions']}\n    rows = []")
    source=source.replace('entry = entries[name]', '''entry = entries[name]
        target = torch.tensor(targets[name])
        forward = target/target.norm() if target.norm() > 1e-6 else torch.tensor([1., 0.])
        basis = torch.stack((forward, torch.stack((-forward[1], forward[0]))))
        projected = (trunk-target) @ basis.T
        leeway = projected.abs().amax(0) + 1e-6
        assert ((projected.abs()-leeway).clamp_min(0).square().mean(-1)==0).all()''')
    source=source.replace('duration_s=duration, average_xy_m_s=average.tolist()', 'basis_xy=basis.tolist(), leeway_m_s=leeway.tolist(), constant_target_xy_m_s=target.tolist(), authored_max_loss=0., duration_s=duration, average_xy_m_s=average.tolist()')
    source=source.replace("(out/'com2_targets.json')", "(out/'com2_loss_reference.json')")
    source=source.replace("if __name__ == '__main__':", "if True:")
    exec(compile(source,'com2_reference_precompute','exec'),dict(__file__=str(Path(__file__).with_name('prepare_perturbed_com2.py')),__name__='com2_precompute'))

def calibrate():
    import xml.etree.ElementTree as ET
    import device_quaternion as q
    table=json.loads((OUT/'com2_loss_reference.json').read_text());refs={x['id']:x for x in table['motions']}
    run=json.loads((d.OUT/'active_run.json').read_text())['run']
    replay=d.ROOT.parent.parent/'Cursor/stepper/training/runs'/('mimickit_'+run)/'replay.npz'
    # Explicit path: the local bridge has already downloaded the current evaluation.
    replay=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+run)/'replay.npz'
    shutil.copyfile(replay,OUT/'calibration-replay.npz')
    z=np.load(OUT/'calibration-replay.npz');meta=json.loads(str(z['metadata']))
    nodes=list(ET.parse(OUT/'source/assets/uefn/humanoid_uefn.xml').getroot().find('worldbody').iter('body'))
    names=meta['names'];ids=[names.index(x) for x in table['bodies']]
    node_by_name={x.get('name'):x for x in nodes}
    offsets=torch.tensor([[float(v) for v in node_by_name[name].find('inertial').get('pos').split()] for name in names])
    weights=torch.tensor(table['mass_weights']);rows=[]
    captures=[OUT/'calibration-replay.npz', *sorted((OUT/'recent-replays').glob('*.npz'))]
    seen=set();iterations=[]
    for capture in captures:
      z=np.load(capture);meta=json.loads(str(z['metadata']))
      if meta['iteration'] in seen:continue
      seen.add(meta['iteration']);iterations.append(meta['iteration'])
      for i,m in enumerate(meta['replay_rows']):
        suffix='' if i==0 else '_'+str(i)
        p=torch.from_numpy(z['pose'+suffix]);v=torch.from_numpy(z['world_velocities'+suffix])
        com=v[:,:,:3]+torch.cross(v[:,:,3:6],q.quat_rotate(p[:,:,3:],offsets.expand(len(p),-1,-1)),dim=-1)
        velocity=(com[:,ids,:2]*weights[None,:,None]).sum(1)
        ref=refs[Path(m['motion_file']).stem]
        raw=((velocity-torch.tensor(ref['constant_target_xy_m_s']))@torch.tensor(ref['basis_xy']).T).abs().sub(torch.tensor(ref['leeway_m_s'])).clamp_min(0).square().mean(-1)
        terms=z['loss_terms'+suffix];columns=[j for j,k in enumerate(m['loss_term_names']) if k!='auto_phase']
        base=terms[1:,columns].sum(-1)
        rows.append(dict(motion=Path(m['motion_file']).stem,cohort=m['final_phase_cohort'],ticks=len(p)-1,base=float(base.mean()),raw=float(raw[1:].mean())))
    # World/cohort weights, rather than the replay's deliberately skewed viewer allocation.
    allocation={'normal_idle':.07*.30*.5,'idle perturbed-':.07*.30*.5,'normal_loco':.93*.30,
        'perturbed_idle':.07*.70*.30,'plus_idle':.07*.70*.70,'perturbed_loco':.93*.70*.30,'plus_loco':.93*.70*.70}
    groups={}
    for row in rows:
        idle=refs[row['motion']]['gait']==-1;cohort=row['cohort']
        key=('idle perturbed-' if cohort=='idle perturbed-' else
             ('plus' if cohort=='perturbed+' else 'perturbed' if cohort=='perturbed' else 'normal')+('_idle' if idle else '_loco'))
        groups.setdefault(key,[]).append(row)
    # Renormalize observed strata; report any missing strata instead of inventing samples.
    mass=sum(allocation[k] for k in groups)
    base=sum(allocation[k]*np.mean([x['base'] for x in v]) for k,v in groups.items())/mass
    raw=sum(allocation[k]*np.mean([x['raw'] for x in v]) for k,v in groups.items())/mass
    assert raw>1e-8 and np.isfinite(base+raw)
    weight=base/(9*raw)
    report=dict(run=run,iterations=iterations,weight=weight,base_mean=base,raw_mean=raw,
        calibrated_share=weight*raw/(base+weight*raw),observed_population_fraction=mass,
        missing_groups=sorted(set(allocation)-set(groups)),rows=rows,method='Fixed coefficient; population-stratified deterministic replay means, excluding auto-phase and terminal penalties')
    (OUT/'calibration.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

def fetch_replays():
    run=json.loads((d.OUT/'active_run.json').read_text())['run']
    code='''from pathlib import Path
import zipfile,json,boto3
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
with zipfile.ZipFile(r/'com2-calibration-replays.zip','w') as dst:
 for cp in sorted(p.glob('checkpoint*.zip'))[-6:]:
  with zipfile.ZipFile(cp) as src:dst.writestr(cp.stem+'.npz',src.read('replay.npz'))
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3'])
c.upload_file(str(r/'com2-calibration-replays.zip'),'aj7d2jzwuq','mimickit/pipeline_20261014/com2-loss/calibration-replays.zip')
print('Recent calibration replays collected')
'''.replace('NAME',repr(run))
    print(r.remote(code),flush=True)
    d.cloud.s3().download_file(d.cloud.rp.VOLUME_ID,'mimickit/pipeline_20261014/com2-loss/calibration-replays.zip',str(OUT/'recent-replays.zip'))
    with zipfile.ZipFile(OUT/'recent-replays.zip') as z:z.extractall(OUT/'recent-replays')

def patch_env(s):
    if '    def _base_perturbed_tracking_losses' not in s:
        old='    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):'
        assert s.count(old)==1
        s=s.replace(old,'''    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):
        terms = self._base_perturbed_tracking_losses(pos, rot, vel, ang, target_vel, target_ang)
        if not self._perturb_ready:
            return terms
        return terms

    def _base_perturbed_tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):''')
    edits=[
    ('        self._com2_targets = torch.tensor(targets, device=self._device)', '''        self._com2_targets = torch.tensor(targets, device=self._device)
        self._com2_loss_weight = float(cfg.get('com2_loss_weight', 0.))
        if self._com2_loss_weight:
            loss_table = json.loads(Path(cfg['com2_loss_reference']).read_text())
            loss_entries = {row['id']:row for row in loss_table['motions']}
            loss_rows = [loss_entries[Path(self._motion_lib.get_motion_file(i)).stem]
                         for i in range(self._motion_lib.get_num_motions())]
            for i, row in enumerate(loss_rows):
                if hashlib.sha256(Path(self._motion_lib.get_motion_file(i)).read_bytes()).hexdigest() != row['motion_sha256']:
                    raise ValueError('Stale COM2 loss reference')
            self._com2_loss_basis = torch.tensor([row['basis_xy'] for row in loss_rows], device=self._device)
            self._com2_loss_leeway = torch.tensor([row['leeway_m_s'] for row in loss_rows], device=self._device)
            loss_targets = torch.tensor([row['constant_target_xy_m_s'] for row in loss_rows], device=self._device)
            if not torch.allclose(loss_targets, self._com2_targets):
                raise ValueError('COM2 loss target differs from termination target')'''),
    ('        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)', '''        if self._com2_loss_weight:
            self.loss_term_names = (*self.loss_term_names, 'com2_velocity')
            self.loss_weights['com2_velocity'] = self._com2_loss_weight
        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)'''),
    ('        return terms\n\n    def _base_perturbed_tracking_losses', '''        if self._com2_loss_weight:
            velocity = com2_velocity(self._engine.get_body_vel(self._get_char_id())[:, self._com2_ids], self._com2_masses)
            difference = velocity - self._com2_targets[self._motion_ids]
            projected = (self._com2_loss_basis[self._motion_ids] * difference[:, None, :]).sum(-1)
            excess = (projected.abs() - self._com2_loss_leeway[self._motion_ids]).clamp_min(0.)
            # Independent of AE handoff, phase, cohort and termination grace.
            cost = excess.square().mean(-1) * self._com2_loss_weight
            terms = torch.cat((terms, cost[:, None]), -1)
        return terms

    def _base_perturbed_tracking_losses'''),
    ('        result = super().recovery_row_metadata(world)', '''        result = super().recovery_row_metadata(world)
        if self._com2_loss_weight:
            motion = self._motion_ids[world]
            result['com2_loss'] = dict(weight=self._com2_loss_weight,
                target_xy_m_s=self._com2_targets[motion].cpu().tolist(),
                basis_xy=self._com2_loss_basis[motion].cpu().tolist(),
                leeway_m_s=self._com2_loss_leeway[motion].cpu().tolist(), active='all rows, all ticks')''')]
    for old,new in edits:
        assert s.count(old)==1,old
        s=s.replace(old,new)
    return s

def prepare():
    plan=json.loads((OUT/'previous-plan.json').read_text());previous=plan['source']
    weight=json.loads((OUT/'calibration.json').read_text())['weight'];changed={}
    with zipfile.ZipFile(previous['local']) as z:
        changed['pipeline/perturbed_omni.py']=patch_env(z.read('pipeline/perturbed_omni.py').decode().replace('\r\n','\n')).encode()
        compile(changed['pipeline/perturbed_omni.py'],'pinned','exec')
        cfg=yaml.safe_load(z.read('prepared/env_config.yaml'))
        cfg['perturbed_motion'].update(com2_loss_weight=weight,com2_loss_reference='/workspace/mimickit_trial/prepared/com2_loss_reference.json')
        changed['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
        changed['prepared/com2_loss_reference.json']=(OUT/'com2_loss_reference.json').read_bytes()
        source=OUT/'source-stored.zip'
        with zipfile.ZipFile(source,'w') as dst:
            for info in z.infolist():dst.writestr(info,changed.get(info.filename,z.read(info.filename)))
            dst.writestr('prepared/com2_loss_reference.json',changed['prepared/com2_loss_reference.json'])
    test(changed['pipeline/perturbed_omni.py'])
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(OUT/'delta.zip','w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl',pickle.dumps(z.infolist(),protocol=4))
        for key,data in changed.items():delta.writestr(key,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    plan.update(source=dict(local=str(source),key='mimickit/pipeline_20261014/com2-loss/source_'+sha[:12]+'.zip',sha256=sha),run_suffix='uefn_locomotion_com2_2048')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2))
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'delta.zip','/workspace/mimickit_trial/com2-delta.zip',timeout=45)
    code='''from pathlib import Path
import json,hashlib,zipfile,pickle,boto3
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD_SHA
with zipfile.ZipFile(r/'source.zip') as old,zipfile.ZipFile(r/'com2-delta.zip') as delta,zipfile.ZipFile(r/'com2-source.zip','w') as new:
 for info in pickle.loads(delta.read('infos.pkl')):new.writestr(info,delta.read(info.filename) if info.filename in delta.namelist() else old.read(info.filename))
data=(r/'com2-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('COM2 source persistent readback verified')
'''.replace('OLD_SHA',repr(previous['sha256'])).replace('SHA',repr(sha)).replace('KEY',repr(plan['source']['key']))
    print(r.remote(code,timeout=60),flush=True)
    active=json.loads((d.OUT/'active_run.json').read_text());d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))
    shared=Path(__file__).with_name('perturbed_omni.py');shared.write_text(patch_env(shared.read_text()))

def test(source):
    # Run the actual outer tracking method around a stub of existing inner losses.
    from types import SimpleNamespace as NS
    from perturbed_motion import com2_velocity
    tree=ast.parse(source);fn=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=='_tracking_losses')
    cls=ast.ClassDef(name='E',bases=[],keywords=[],body=[fn],decorator_list=[])
    scope=dict(torch=torch,com2_velocity=com2_velocity)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),'exact_com2_method','exec'),scope)
    e=scope['E']();e._perturb_ready=True;e._foot_regularizers_enabled=False;e._pelvis_horizontal_enabled=False
    e._com2_loss_weight=2.;e._com2_ids=[0,1,2];e._com2_masses=torch.tensor([.2,.5,.3])
    e._com2_targets=torch.tensor([[1.,0.],[0.,0.]]);e._com2_loss_basis=torch.eye(2).repeat(2,1,1)
    e._com2_loss_leeway=torch.tensor([[.2,.1],[0.,0.]])
    e._motion_ids=torch.tensor([0,0,0,1]);e._get_char_id=lambda:0
    vel=torch.tensor([[1.,0.,50.],[1.1,.05,0.],[1.5,.5,0.],[.2,.3,0.]])[:,None].repeat(1,3,1)
    e._engine=NS(get_body_vel=lambda _:vel);base=torch.ones(4,3)
    e._base_perturbed_tracking_losses=lambda *args:base
    result=e._tracking_losses(None,None,None,None,None,None)
    torch.testing.assert_close(result[:,:3],base)
    torch.testing.assert_close(result[:,-1],torch.tensor([0.,0.,.25,.13]))
    assert 'self._time_buf' not in ast.unparse(fn)
    (OUT/'verification.json').write_text(json.dumps(dict(exact_method_costs=result[:,-1].tolist(),checks=['zero within directional envelope','vertical ignored','idle target zero','all existing terms preserved','no phase/cohort/timing gates']),indent=2))

def verify():
    name=json.loads((d.OUT/'active_run.json').read_text())['run'];assert 'locomotion_com2_2048' in name
    initial=json.loads((OUT/'prepared.json').read_text())['checkpoint']['finished']['iteration']
    code='''from pathlib import Path
import json,time,numpy as np
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text())
assert s['state']=='training' and s['iteration']>INITIAL and time.time()-s['updated_unix']<180
assert not (p/'finished.json').exists() and not (p/'backup_errors.json').exists()
z=np.load(p/'replay.npz');m=json.loads(str(z['metadata']))
assert all('com2_velocity' in x['loss_term_names'] and x['com2_loss']['active']=='all rows, all ticks' for x in m['replay_rows'])
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
events=EventAccumulator(str(p));events.Reload();values=events.Scalars('loss/com2_velocity');assert values
(r/'loco_ae30_handoff_complete').touch()
print(json.dumps(dict(run=NAME,status={k:s.get(k) for k in ['state','iteration','samples','worlds','training_transitions_per_second']},backup=b,tb_com2=values[-1].value,tb_step=values[-1].step)))
'''.replace('NAME',repr(name)).replace('INITIAL',str(initial))
    result=json.loads(r.remote(code,timeout=45));(OUT/'live-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

def journal():
    live=json.loads((OUT/'live-verification.json').read_text())
    plan=json.loads((OUT/'prepared.json').read_text());cp=plan['checkpoint']
    calibration=json.loads((OUT/'calibration.json').read_text())
    note=f'''## October24 13:01 Warsaw - continuous COM2 loss RUNNING

User approved the discussed continuous COM2 loss and latest-checkpoint resume.
Run {live['run']} on existing L4 w754z82j94t55a,
2048 worlds, <=$0.59/hour until stopped. Latest checkpoint171151_final,
4,174,512,128 samples preserved locally at {cp['local']}
and verified by SHA256/ZIP plus persistent readback. SHA {cp['sha256']}.
Advancing iteration{live['status']['iteration']} at ~22,506 transitions/s;
first new checkpoint171152 persistent readback verified; handoff guard released.

New loss/com2_velocity: mass-weighted pelvis/torso/head body-COM world XY velocity,
constant target equal to existing per-motion time average. Separate forward/sideways
symmetric leeway encloses reference deviations, sampled at240Hz midpoints AND grid
endpoints; all50 animations have exactly zero sampled authored loss. Idle target0,
world XY basis. Cost is mean squared excess beyond these two allowances.
Applied all rows, every tick, independently of AE/MSE fade or termination grace.
Fixed coefficient {calibration['weight']:.12g}, calibrated to10% of combined body loss
on120 recorded episodes across6 current-run evaluations, stratified by actual cohort
proportions. Calibration mean base {calibration['base_mean']:.6g}, rawCOM2 {calibration['raw_mean']:.6g}.
This is a fixed offline calibration, NOT dynamically10% at every tick. Auto-phase
and discrete terminal penalties excluded. Termination rules, all existing loss
terms including legacy flat_com_velocity, optimizer, observations, and sampling unchanged.

Only pinned perturbed_omni.py, env_config.yaml and new com2_loss_reference.json
changed. Shared runtime received scoped optional patch, preserving unrelated recovery
work. Exact-method CPU checks: envelope zero, vertical ignored, idle zero target,
existing terms preserved, no timing/cohort gate. New loss reaches physical reward
through ordinary summed-loss path, full-batch statistics, and recorded replay terms.
TB card loss/com2_velocity verified remotely; local dashboard allowlist extended
and only this run's local dashboard restarted. TB filter13-01-24.
Helper Labs/MimicKitTraining/resume_com2_loss.py;
receipts/calibration/precomputed references: Saved/MimicKitLocomotion/com2-loss.

'''
    for path,marker in [(d.ROOT/'ProjectJournal.md',b'## Resume here'),(d.ROOT/'Docs/MimicKitTraining.md',b'# MimicKit humanoid trial')]:
        data=path.read_bytes();at=data.index(b'\n',data.index(marker))+1
        path.write_bytes(data[:at]+b'\n'+note.encode('utf-8')+data[at:])

if __name__=='__main__':
    handoff.OUT=OUT
    if sys.argv[1] in ['stop','capture','launch']:getattr(handoff,sys.argv[1])()
    else:globals()[sys.argv[1]]()

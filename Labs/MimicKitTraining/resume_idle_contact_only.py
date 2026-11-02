"""Remove legacy pose-distance termination only for normal pushed-idle rows."""
import hashlib,json,pickle,sys,zipfile
from pathlib import Path
import torch
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
import resume_pushed_idle_penalty as handoff

OUT=d.OUT/'idle-contact-only'

def patch_stock(s):
    edits=[('import torch','import torch\nfrom typing import Optional'),
        ('                                         track_root=track_root)',
         "                                         track_root=track_root,\n                                         pose_termination_mask=getattr(self, '_pose_termination_mask', None))"),
        ('                 track_root):','                 track_root, pose_termination_mask=None):'),
        ('Tensor, Tensor, Tensor, bool) -> Tensor','Tensor, Tensor, Tensor, bool, Optional[Tensor]) -> Tensor'),
        ('            failed = torch.logical_or(failed, pose_fail)',
         '            if pose_termination_mask is not None:\n                pose_fail = pose_fail & pose_termination_mask\n            failed = torch.logical_or(failed, pose_fail)')]
    for old,new in edits:
        assert s.count(old)==1,old
        s=s.replace(old,new)
    return s

def patch_final(s):
    old='        self.minus=stratified_subset(idle,env._fixed_motion_ids,round(len(idle)*.5),n,dev)'
    assert s.count(old)==1
    s=s.replace(old,old+'\n        env._pose_termination_mask = ~self.minus')
    old='target_termination_bodies=[],sphere_only=False,pushed_idle_failure_penalty='
    assert s.count(old)==1
    return s.replace(old,'target_termination_bodies=[],sphere_only=False,stock_pose_termination=False,contact_termination=True,pushed_idle_failure_penalty=')

def test():
    sys.path[:0]=[str(d.ROOT/'Saved/MimicKitUEFN/dependencies'),str(d.ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
    from envs.deepmimic_env import compute_done
    n=7;pos=torch.zeros(n,3,3);pos[:6,1,0]=1.1;ref=torch.zeros_like(pos)
    force=torch.zeros_like(pos);force[1,1,2]=1;force[6,1,2]=1
    rot=torch.tensor([[0.,0.,0.,1.]]).repeat(n,1)
    args=dict(done_buf=torch.zeros(n,dtype=torch.long),time=torch.tensor([1.,1.,1.,10.,1.,0.,1.]),ep_len=10.,
        root_rot=rot,body_pos=pos,tar_root_rot=rot,tar_body_pos=ref,ground_contact_force=force,contact_body_ids=torch.tensor([2]),
        pose_termination=True,pose_termination_dist=1.,global_obs=True,enable_early_termination=True,
        motion_times=torch.tensor([0.,0.,0.,0.,2.,0.,0.]),motion_len=torch.ones(n),motion_len_term=torch.tensor([False,False,False,False,True,False,False]),track_root=False)
    mask=torch.tensor([False,False,True,False,False,False,True])
    actual=compute_done(**args,pose_termination_mask=mask)
    assert actual.tolist()==[0,1,1,3,2,0,1],actual
    legacy=compute_done(**args)
    assert legacy.tolist()==[1,1,1,1,1,0,1],legacy
    # A foot contact stays allowed, even with pose checking disabled.
    args['ground_contact_force'].zero_();args['ground_contact_force'][0,2,2]=1
    assert compute_done(**args,pose_termination_mask=mask)[0].item()==0
    # Reproduce the user's exact frame130 pose crossing, without invented contact forces.
    file=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs/mimickit_20261024_001155_uefn_locomotion_pre_push_velocity_1024/debug/rollout_step_00161378.json')
    rec=json.loads(file.read_bytes());p=torch.tensor(rec['positions'][0][129:131]);t=torch.tensor(rec['mse_target_positions'][0][129:131]);q=rot[:2]
    kw=dict(done_buf=torch.zeros(2,dtype=torch.long),time=torch.tensor([129/30,130/30]),ep_len=10.,root_rot=q,body_pos=p,tar_root_rot=q,tar_body_pos=t,
        ground_contact_force=torch.zeros_like(p),contact_body_ids=torch.tensor([11,14]),pose_termination=True,pose_termination_dist=1.,global_obs=True,
        enable_early_termination=True,motion_times=torch.zeros(2),motion_len=torch.ones(2),motion_len_term=torch.zeros(2,dtype=torch.bool),track_root=False)
    before=compute_done(**kw);after=compute_done(**kw,pose_termination_mask=torch.zeros(2,dtype=torch.bool))
    assert before.tolist()==[0,1] and after.tolist()==[0,0]
    result=dict(masked_cases=actual.tolist(),legacy_cases=legacy.tolist(),recorded_frames=[129,130],before=before.tolist(),after=after.tolist(),contact_failure_retained=True,foot_contact_allowed=True,timeout_success_retained=True)
    (OUT/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

def prepare():
    OUT.mkdir(exist_ok=True);plan=json.loads((d.OUT/'final-phase-prepared.json').read_text())
    (OUT/'previous-plan.json').write_text(json.dumps(plan,indent=2));previous=plan['source']
    patches={'MimicKit/mimickit/envs/deepmimic_env.py':(patch_stock,d.ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit/envs/deepmimic_env.py'),
             'pipeline/final_locomotion.py':(patch_final,Path(__file__).with_name('final_locomotion.py'))}
    changed={}
    with zipfile.ZipFile(previous['local']) as z:
        for key,(fn,local) in patches.items():
            s=z.read(key).decode().replace('\r\r\n','\n').replace('\r\n','\n');changed[key]=fn(s).encode()
            compile(changed[key],key,'exec')
            s=local.read_bytes().decode().replace('\r\r\n','\n').replace('\r\n','\n');local.write_bytes(fn(s).encode())
        source=OUT/'source-stored.zip'
        with zipfile.ZipFile(source,'w') as out:
            for info in z.infolist():out.writestr(info,changed.get(info.filename,z.read(info.filename)))
    test()
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(OUT/'delta.zip','w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl',pickle.dumps(z.infolist(),protocol=4))
        for key,data in changed.items():delta.writestr(key,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest();plan.update(source=dict(local=str(source),key='mimickit/pipeline_20261014/idle-contact-only/source_'+sha[:12]+'.zip',sha256=sha),run_suffix='uefn_locomotion_idle_contact_only_1024')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2))
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'delta.zip','/workspace/mimickit_trial/idle-contact-delta.zip',timeout=45)
    code="""from pathlib import Path
import json,hashlib,zipfile,pickle,boto3
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD_SHA
with zipfile.ZipFile(r/'source.zip') as old,zipfile.ZipFile(r/'idle-contact-delta.zip') as delta,zipfile.ZipFile(r/'idle-contact-source.zip','w') as new:
 for info in pickle.loads(delta.read('infos.pkl')):new.writestr(info,delta.read(info.filename) if info.filename in delta.namelist() else old.read(info.filename))
data=(r/'idle-contact-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('Source persistent readback verified')
""".replace('OLD_SHA',repr(previous['sha256'])).replace('SHA',repr(sha)).replace('KEY',repr(plan['source']['key']))
    print(r.remote(code,timeout=60),flush=True)
    active=json.loads((d.OUT/'active_run.json').read_text());d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))

def verify():
    name=json.loads((d.OUT/'active_run.json').read_text())['run'];assert 'idle_contact_only' in name
    initial=json.loads((OUT/'prepared.json').read_text())['checkpoint']['finished']['iteration']
    code="""from pathlib import Path
import json,time
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME;end=time.time()+50
while True:
 s=json.loads((p/'status.json').read_text()) if (p/'status.json').exists() else {}
 if s.get('iteration',0)>INITIAL or time.time()>end:break
 time.sleep(3)
assert s.get('state')=='training' and s['iteration']>INITIAL and time.time()-s['updated_unix']<180, ('not ready',s.get('iteration'))
b=json.loads((p/'backup_status.json').read_text());assert b['key'].split('/')[-2]==NAME
assert not (p/'finished.json').exists() and not (p/'backup_errors.json').exists()
rows=json.loads((p/'evaluation.json').read_text())['replay']['replay_rows']
idle=[{k:v for k,v in row.items() if k in ['final_phase_cohort','terminal_flag','stock_pose_termination','contact_termination','pushed_idle_failure_penalty','target_termination_bodies','duration_seconds']} for row in rows if row.get('final_phase_cohort')=='idle perturbed-']
assert idle and all(row['stock_pose_termination']==False and row['contact_termination'] and row['pushed_idle_failure_penalty']==100 and row['target_termination_bodies']==[] for row in idle)
(r/'loco_ae30_handoff_complete').touch()
print(json.dumps(dict(run=NAME,status={k:s.get(k) for k in ['state','iteration','samples','training_transitions_per_second']},backup=b,pushed_idle=idle)))
""".replace('NAME',repr(name)).replace('INITIAL',str(initial))
    result=json.loads(r.remote(code,timeout=55));(OUT/'live-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    handoff.OUT=OUT;action=sys.argv[1]
    if action in ['stop','capture','launch']:getattr(handoff,action)()
    else:globals()[action]()

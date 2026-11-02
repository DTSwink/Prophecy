"""Add head speed and measure excess relative only to pelvis translation."""
import ast,hashlib,json,sys,zipfile
from pathlib import Path
from types import SimpleNamespace
import torch,yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
from loco_extremity_speed import calibrate

BODIES=['right_foot','left_foot','right_hand','left_hand','head']

def patch(source):
    changes=[
        ("            speed_names = speed_table['bodies']", "            speed_names = speed_table['bodies']\n            self._extremity_speed_names = speed_names\n            if cfg.get('extremity_speed_translation_only', False):\n                assert speed_table['measurement'] == 'body-origin speed relative to pelvis translation only: norm(v-v_p)'"),
        ("        relative = vel[:, ids] - vel[:, :1] - torch.cross(\n            ang[:, :1].expand(-1, 4, -1), pos[:, ids] - pos[:, :1], dim=-1)", "        relative = vel[:, ids] - vel[:, :1]\n        if not self._perturb_cfg.get('extremity_speed_translation_only', False):\n            relative = relative - torch.cross(ang[:, :1].expand_as(relative), pos[:, ids] - pos[:, :1], dim=-1)"),
        ("        relative = vel[:, 1:] - vel[:, :1] - torch.cross(\n            ang[:, :1].expand(-1, 4, -1), pos[:, 1:] - pos[:, :1], dim=-1)", "        relative = vel[:, 1:] - vel[:, :1]\n        if not self._perturb_cfg.get('extremity_speed_translation_only', False):\n            relative = relative - torch.cross(ang[:, :1].expand_as(relative), pos[:, 1:] - pos[:, :1], dim=-1)"),
        ("extremity_speed_bodies=['right_foot','left_foot','right_hand','left_hand']", "extremity_speed_bodies=self._extremity_speed_names"),
        ("extremity_speed_frame='body origins relative to translating and rotating pelvis'", "extremity_speed_frame=('body origins relative to pelvis translation only' if self._perturb_cfg.get('extremity_speed_translation_only', False) else 'body origins relative to translating and rotating pelvis')"),
    ]
    for old,new in changes:
        assert source.count(old)==1,old
        source=source.replace(old,new)
    compile(source,'perturbed_omni.py','exec')
    return source

def check(source):
    node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='_append_extremity_speed_loss')
    scope=dict(torch=torch)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'actual-loss','exec'),scope)
    e=SimpleNamespace(_perturb_cfg=dict(extremity_speed_loss_weight=2.,extremity_speed_translation_only=True),
        _extremity_speed_ids=torch.arange(6),_extremity_speed_limits=torch.ones(1,5),_motion_ids=torch.zeros(4,dtype=torch.long),
        _perturbed_rows=torch.tensor([True,True,False,True]),_recovery_rows=torch.tensor([False,False,False,True]))
    pos=torch.zeros(4,6,3);pos[:,1:,0]=1
    ang=torch.zeros_like(pos);ang[:,:,2]=2
    vel=torch.cross(ang,pos,dim=-1)+torch.tensor([3.,4.,5.])
    terms=torch.randn(4,3)
    f=lambda:scope['_append_extremity_speed_loss'](e,terms,pos,vel,ang)
    # Rigid rotation now costs, translation still cancels; normal/recovery masked.
    torch.testing.assert_close(f()[:,-1],torch.tensor([2.,2.,0.,0.]))
    torch.testing.assert_close(f()[:,:3],terms)
    e._perturb_cfg['extremity_speed_translation_only']=False
    torch.testing.assert_close(f()[:,-1],torch.zeros(4))
    e._perturb_cfg['extremity_speed_translation_only']=True
    vel[:]=torch.tensor([3.,4.,5.]);torch.testing.assert_close(f()[:,-1],torch.zeros(4))
    vel[:,5,0]+=2.;torch.testing.assert_close(f()[:,-1],torch.tensor([.4,.4,0.,0.]))
    vel[:,5,0]-=1.;torch.testing.assert_close(f()[:,-1],torch.zeros(4))
    return dict(rigid_rotation_penalized=True,translation_cancelled=True,head_included=True,threshold=True,mask=True,old_default_preserved=True,other_terms_unchanged=True)

def prepare():
    base=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    active=json.loads((d.OUT/'active_run.json').read_text())
    report=calibrate(base['source']['local'],d.OUT,BODIES,True)
    rows={x['id']:x for x in report['motions']}
    for name,row in rows.items():
        reference=name.replace('Stand_Idle_Loop','Walk_Loop_B') if 'Stand_Idle_Loop' in name else name
        row['reference_id']=reference
        if reference!=name:
            row['own_max_m_s']=row['max_m_s'];row['max_m_s']=rows[reference]['max_m_s'];row['limits_m_s']=rows[reference]['limits_m_s']
    report['idle_reference']='matching equipment Walk_Loop_B'
    d.save('translation-speed-reference',report)
    with zipfile.ZipFile(base['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    after=patch(entries['pipeline/perturbed_omni.py'].decode());tests=check(after)
    entries['pipeline/perturbed_omni.py']=after.encode()
    entries['prepared/extremity_speed_reference.json']=json.dumps(report,indent=2).encode()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml']);c=cfg['perturbed_motion']
    assert c['extremity_speed_termination']==False
    c['extremity_speed_translation_only']=True
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    source=d.OUT/'locomotion-translation-speed-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items():z.writestr(name,data)
    data=source.read_bytes();sha=hashlib.sha256(data).hexdigest();key='mimickit/pipeline_20261014/translation-speed/source_'+sha[:12]+'.zip'
    d.cloud.s3().put_object(Bucket=d.cloud.rp.VOLUME_ID,Key=key,Body=data)
    shared=Path(__file__).with_name('perturbed_omni.py');shared.write_text(patch(shared.read_text()))
    plan=dict(old_run=active['run'],pod=active['pod'],source=dict(local=str(source),key=key,sha256=sha))
    d.save('translation-speed-before-plan',base);d.save('ae30-switch',plan);d.save('translation-speed-switch',plan)
    d.save('translation-speed-tests',tests)
    print(json.dumps(dict(prepared=plan,tests=tests,motions=len(rows),bodies=BODIES,weight=c['extremity_speed_loss_weight'])),flush=True)

def launch():
    p=json.loads((d.OUT/'ae30-switch.json').read_text());source=p['source'];cp=p['checkpoint']
    code='''from pathlib import Path
import json,hashlib,zipfile,io,boto3
r=Path('/workspace/mimickit_trial');p=json.loads((r/'private.json').read_text());c=boto3.client('s3',**p['s3'])
data=c.get_object(Bucket='aj7d2jzwuq',Key=SOURCE['key'])['Body'].read()
assert hashlib.sha256(data).hexdigest()==SOURCE['sha256']
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CHECKPOINT['sha256']
(r/'source.zip').write_bytes(data)
with zipfile.ZipFile(io.BytesIO(data)) as z:z.extractall(r)
p['resume_checkpoint']=CHECKPOINT;(r/'private.json').write_text(json.dumps(p));(r/'stop.request').unlink(missing_ok=True)
print('Persistent source readback and latest checkpoint verified')
'''.replace('SOURCE',repr(source)).replace('CHECKPOINT',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    print(r.remote(code,timeout=60),flush=True)
    base=json.loads((d.OUT/'getup-success-prepared.json').read_text());base.update(source=source,checkpoint=cp,run_suffix='uefn_locomotion_translation_speed_head_1024')
    d.save('getup-success-prepared',base);d.launch()

if __name__=='__main__':
    if sys.argv[1]=='stop':r.stop()
    elif sys.argv[1]=='capture':r.capture()
    else:globals()[sys.argv[1]]()

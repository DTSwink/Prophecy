"""Isolated locomotion restart with a calibrated walking flight-height cost."""
import hashlib,io,json,sys,zipfile,itertools,ast
from pathlib import Path
import numpy as np
import torch,yaml
from scipy.spatial.transform import Rotation
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
from walking_airborne import patch_source,foot_box_bottoms,airborne_cost


def boxes(entries):
    import xml.etree.ElementTree as ET
    tree=ET.fromstring(entries['assets/uefn/humanoid_uefn.xml'])
    result=[]
    for name in ('right_foot','left_foot'):
        geoms=tree.find(f".//body[@name='{name}']").findall('geom')
        assert len(geoms)==1 and geoms[0].get('type')=='box'
        g=geoms[0];half=np.fromstring(g.get('size'),sep=' ')
        axes=Rotation.from_quat(np.roll(np.fromstring(g.get('quat','1 0 0 0'),sep=' '),-1)).as_matrix().T
        result.append(dict(bone=name,center=np.fromstring(g.get('pos','0 0 0'),sep=' ').tolist(),half_axes=(half[:,None]*axes).tolist()))
    return result


def tests(code,geometry):
    rng=np.random.default_rng(100);n=4096
    rot=Rotation.random(n*2,random_state=rng);q=torch.tensor(rot.as_quat().reshape(n,2,4),dtype=torch.float32)
    pos=torch.tensor(rng.normal(size=(n,2,3)),dtype=torch.float32)
    centers=torch.tensor([b['center'] for b in geometry]);axes=torch.tensor([b['half_axes'] for b in geometry])
    signs=np.array(list(itertools.product([-1,1],repeat=3)))
    corners=np.einsum('ci,fij->fcj',signs,axes.numpy())+centers.numpy()[:,None,:]
    world=np.einsum('nfij,fcj->nfci',rot.as_matrix().reshape(n,2,3,3),corners)+pos.numpy()[:,:,None,:]
    actual=foot_box_bottoms(pos,q,centers,axes).numpy();expected=world[:,:,:,2].min(-1)
    np.testing.assert_allclose(actual,expected,atol=8e-7)
    heights=torch.tensor([[.01,.3],[.2,0.],[.02,.04],[.04,.02],[.1,.1],[.1,.1]])
    mask=torch.tensor([True,True,True,True,False,False])
    torch.testing.assert_close(airborne_cost(heights,mask),torch.tensor([0.,0.,.0001,.0001,0.,0.]))
    shifted=pos.clone();shifted[:,:,:2]+=100
    torch.testing.assert_close(foot_box_bottoms(shifted,q,centers,axes),torch.tensor(actual))
    # Execute the actual integration method: walk=0, run=1, idle=-1; normal/perturbed alike.
    cls=next(x for x in ast.parse(code).body if isinstance(x,ast.ClassDef) and any(isinstance(y,ast.FunctionDef) and y.name=='_append_walking_airborne_loss' for y in x.body))
    method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_append_walking_airborne_loss')
    ns=dict(torch=torch,foot_box_bottoms=foot_box_bottoms,airborne_cost=airborne_cost)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'integration','exec'),ns)
    from types import SimpleNamespace
    env=SimpleNamespace(_walking_airborne_weight=2.,_walking_foot_ids=torch.tensor([0,1]),_walking_foot_centers=centers,
        _walking_foot_half_axes=axes,_gaits=torch.tensor([0.,0.,1.,-1.,0.]),_motion_ids=torch.arange(5),_recovery_rows=torch.tensor([False,False,False,False,True]))
    pp=torch.ones(5,2,3);rr=torch.zeros(5,2,4);rr[:,:,-1]=1;terms=torch.ones(5,7)
    result=ns['_append_walking_airborne_loss'](env,terms,pp,rr)
    torch.testing.assert_close(result[:,:-1],terms);assert (result[:2,-1]>0).all() and (result[2:,-1]==0).all()
    return dict(random_foot_boxes_checked=n*2,max_height_error_m=float(np.abs(actual-expected).max()),
        swing_foot_exempt=True,threshold_1cm=True,world_Z_verified=True,normal_and_perturbed_walks_only=True)


def preflight():
    base=json.loads((d.OUT/'getup-success-prepared.json').read_text());active=json.loads((d.OUT/'active_run.json').read_text())
    with zipfile.ZipFile(base['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    assert hashlib.sha256(Path(base['source']['local']).read_bytes()).hexdigest()==base['source']['sha256']
    code=patch_source(entries['pipeline/perturbed_omni.py'].decode());geometry=boxes(entries)
    result=tests(code,geometry);d.save('walking-airborne-tests',result)
    d.save('walking-airborne-before-plan',base);d.save('walking-airborne-old-launch',json.loads((d.OUT/'launch.json').read_text()))
    d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod']))
    print(json.dumps(result),flush=True)


def prepare():
    switch=json.loads((d.OUT/'ae30-switch.json').read_text());cp=switch['checkpoint']
    base=json.loads((d.OUT/'walking-airborne-before-plan.json').read_text())
    with zipfile.ZipFile(base['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    geometry=boxes(entries);centers=torch.tensor([b['center'] for b in geometry]);axes=torch.tensor([b['half_axes'] for b in geometry])
    raw=[];cost=[];rows=[]
    with zipfile.ZipFile(cp['local']) as bundle,np.load(io.BytesIO(bundle.read('replay.npz')),allow_pickle=False) as replay:
        meta=json.loads(str(replay['metadata']));ids=[meta['names'].index(b['bone']) for b in geometry]
        for i,row in enumerate(meta['replay_rows']):
            if '_Walk_' not in row['motion_file'] or row.get('recovery_row'):continue
            suffix='' if i==0 else '_'+str(i);pose=torch.tensor(replay['pose'+suffix][:,ids])
            bottom=foot_box_bottoms(pose[...,:3],pose[...,3:],centers,axes)
            values=airborne_cost(bottom,torch.ones(len(pose),dtype=torch.bool)).numpy()[1:]
            current=replay['loss_terms'+suffix].sum(-1)[1:];raw.extend(values);cost.extend(current)
            rows.append(dict(row=i,motion=Path(row['motion_file']).stem,perturbed=row.get('perturbed_row'),frames=len(values),airborne_frames=int((values>0).sum())))
    raw=np.asarray(raw);cost=np.asarray(cost);assert raw.mean()>0
    weight=float(.08*cost.mean()/raw.mean())
    calibration=dict(weight=weight,target_fraction_of_existing_loss=.08,baseline_mean=float(cost.mean()),raw_mean_m2=float(raw.mean()),
        weighted_mean=float(weight*raw.mean()),frames=len(raw),airborne_frames=int((raw>0).sum()),rows=rows,
        checkpoint=cp['key'],replay_iteration=meta['iteration'],definition='fixed weight * max(min(right/left foot collider bottom world Z)-0.01,0)^2; all walking rows, no fade',
        sampling='Saved deterministic replay walking rows; reset frame excluded; calibration includes airborne and grounded frames')
    d.save('walking-airborne-calibration',calibration)
    code=patch_source(entries['pipeline/perturbed_omni.py'].decode());tests(code,geometry)
    entries['pipeline/perturbed_omni.py']=code.encode();entries['pipeline/walking_airborne.py']=Path(__file__).with_name('walking_airborne.py').read_bytes()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml']);cfg['perturbed_motion'].update(walking_airborne_weight=weight,walking_foot_boxes=geometry)
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode();entries['prepared/walking_airborne_calibration.json']=json.dumps(calibration,indent=2).encode()
    source=d.OUT/'walking-airborne-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items():z.writestr(name,data)
    data=source.read_bytes();sha=hashlib.sha256(data).hexdigest();key='mimickit/pipeline_20261014/walking-airborne/source_'+sha[:12]+'.zip'
    c=d.cloud.s3();c.put_object(Bucket=d.cloud.rp.VOLUME_ID,Key=key,Body=data);d.verified_readback(c,d.cloud.rp.VOLUME_ID,key,sha)
    switch['source']=dict(local=str(source),key=key,sha256=sha);d.save('ae30-switch',switch);d.save('walking-airborne-switch',switch)
    print(json.dumps(calibration),flush=True)


def retune():
    snapshot=json.loads((d.OUT/'walking-airborne-training-calibration.json').read_text())
    status=snapshot['status'];losses=status['losses'];old=json.loads((d.OUT/'walking-airborne-switch.json').read_text())
    with zipfile.ZipFile(old['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    cfg=yaml.safe_load(entries['prepared/env_config.yaml']);previous=cfg['perturbed_motion']['walking_airborne_weight']
    baseline=sum(v for k,v in losses.items() if k not in ('walking_airborne','total','body_total','auto_phase'))
    observed=losses['walking_airborne'];assert observed>0 and baseline>0
    weight=previous*.08*baseline/observed
    calibration=dict(weight=weight,previous_replay_weight=previous,baseline_training_mean=baseline,
        observed_training_penalty=observed,target_fraction_of_existing_loss=.08,calibrated_penalty=.08*baseline,
        calibration_run=json.loads((d.OUT/'active_run.json').read_text())['run'],calibration_iteration=status['iteration'],
        sampling='Actual training loss counters with current exploration noise, full 1024-world batch. Fixed coefficient; ratio can change as the policy learns.',
        definition='weight * max(min(right/left foot collider bottom world Z)-0.01,0)^2; both normal and perturbed walking only, no fade')
    cfg['perturbed_motion']['walking_airborne_weight']=weight;entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    entries['prepared/walking_airborne_calibration.json']=json.dumps(calibration,indent=2).encode()
    source=d.OUT/'walking-airborne-training-calibrated-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items():z.writestr(name,data)
    data=source.read_bytes();sha=hashlib.sha256(data).hexdigest();key='mimickit/pipeline_20261014/walking-airborne/source_'+sha[:12]+'.zip'
    c=d.cloud.s3();c.put_object(Bucket=d.cloud.rp.VOLUME_ID,Key=key,Body=data);d.verified_readback(c,d.cloud.rp.VOLUME_ID,key,sha)
    d.save('walking-airborne-retuned',dict(source=dict(local=str(source),key=key,sha256=sha),calibration=calibration))
    print(json.dumps(calibration),flush=True)


def activate_retuned():
    switch=json.loads((d.OUT/'ae30-switch.json').read_text());tuned=json.loads((d.OUT/'walking-airborne-retuned.json').read_text())
    tuned['calibration']['calibration_run']=switch['old_run']
    switch['source']=tuned['source'];d.save('ae30-switch',switch);d.save('walking-airborne-switch',switch)
    d.save('walking-airborne-calibration-final',tuned['calibration']);launch()


def launch():
    plan=json.loads((d.OUT/'walking-airborne-switch.json').read_text());source=plan['source'];cp=plan['checkpoint']
    code='''import json,hashlib,zipfile,io
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');p=json.loads((r/'private.json').read_text())
c=boto3.client('s3',**p['s3']);data=c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()
assert hashlib.sha256(data).hexdigest()==SHA
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CPSHA
(r/'source.zip').write_bytes(data)
with zipfile.ZipFile(io.BytesIO(data)) as z:z.extractall(r)
p['resume_checkpoint']=CHECKPOINT
(r/'private.json').write_text(json.dumps(p));(r/'stop.request').unlink(missing_ok=True)
print('Latest checkpoint and walking penalty source verified')
'''.replace('CPSHA',repr(cp['sha256'])).replace('KEY',repr(source['key'])).replace('SHA',repr(source['sha256'])).replace('CHECKPOINT',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    print(r.remote(code),flush=True)
    base=json.loads((d.OUT/'walking-airborne-before-plan.json').read_text());base.update(source=source,checkpoint=cp,worlds=1024,run_suffix='uefn_locomotion_walk_ground8_1024')
    d.save('getup-success-prepared',base);d.launch()


if __name__=='__main__':
    if sys.argv[1]=='stop':r.stop()
    elif sys.argv[1]=='capture':r.capture()
    else:globals()[sys.argv[1]]()

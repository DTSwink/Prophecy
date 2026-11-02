"""Offline reference cadence, exact replay audit and fixed-weight calibration."""
import json, sys, zipfile, hashlib
from pathlib import Path
import numpy as np
import torch
import yaml
from scipy.spatial.transform import Rotation
from foot_regularizers import FootRegularizers
from walking_airborne import foot_box_bottoms

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitLocomotion/foot-losses-20261027'
RUN='20261026_192244_uefn_locomotion_prior_mse_restored_2048'
FOLDER=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+RUN)/'debug'
A=np.array([[1,0,0],[0,0,1],[0,-1,0.]])


def references():
    from prepare_perturbed_com2 import MJCFCharModel, MotionLib, mp_util
    torch.set_num_threads(2);mp_util.init(0,1,'cpu',6797)
    plan=json.loads((ROOT/'Saved/MimicKitLocomotion/getup-success-prepared.json').read_text())
    src=OUT/'reference-source';src.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(plan['source']['local']) as z:
        for name in z.namelist():
            if name.startswith(('assets/uefn/','prepared/','motions/')):
                p=src/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
    for p in (src/'prepared').glob('*.yaml'):
        p.write_text(p.read_text().replace('/workspace/mimickit_trial',src.as_posix()))
    cfg=yaml.safe_load((src/'prepared/env_config.yaml').read_text());model=MJCFCharModel('cpu');model.load(cfg['char_file'])
    lib=MotionLib(cfg['motion_file'],model,'cpu')
    boxes=cfg['perturbed_motion']['walking_foot_boxes'];ids=[model.get_body_names().index(b['bone']) for b in boxes]
    centers=torch.tensor([b['center'] for b in boxes]);axes=torch.tensor([b['half_axes'] for b in boxes]);rows={}
    for i in range(lib.get_num_motions()):
        name=Path(lib.get_motion_file(i)).stem
        if '_Idle_' in name:continue
        duration=float(lib.get_motion_length(i));t=torch.arange(0,duration*4,1/30)
        root,rot,_,_,joints,_=lib.calc_motion_frame(torch.full(t.shape,i,dtype=torch.long),t)
        p,q=model.forward_kinematics(root,rot,joints)
        h=foot_box_bottoms(p[:,ids],q[:,ids],centers,axes)
        state=FootRegularizers(1,'cpu');state.reset(torch.tensor([0]),p[:1,ids],q[:1,ids],h[:1]);events=[[],[]];costs=[]
        for k in range(1,len(t)):
            costs.append(state.append(p[k:k+1,ids],q[k:k+1,ids],h[k:k+1],torch.ones(1,2))[0,1:].numpy().copy())
            for f in range(2):
                if state.events[0,f]:events[f].append(k)
        period=[.9*min([duration*30]+np.diff(e).tolist()) for e in events]
        assert min(period)>1
        rows[name]=dict(period_ticks=period,events=events,duration=duration,reversal_allowance=np.max(costs,axis=0).tolist(),
            motion_sha256=hashlib.sha256(Path(lib.get_motion_file(i)).read_bytes()).hexdigest())
    fallback=rows['M_Neutral_Walk_Loop_F_R_20_Unarmed']['period_ticks']
    for i in range(lib.get_num_motions()):
        name=Path(lib.get_motion_file(i)).stem
        if '_Idle_' in name:rows[name]=dict(period_ticks=fallback,reversal_allowance=[0.,0.],fallback='M_Neutral_Walk_Loop_F_R_20_Unarmed')
    (OUT/'cadence-reference.json').write_text(json.dumps(dict(source=plan['source'],motions=rows,
        definition='Per-foot fastest authored liftoff interval (or clip period), minus10% tolerance; 1cm contact/2.5cm liftoff hysteresis; idle uses forward walk'),indent=2))
    print('Reference cadence prepared:',len(rows),flush=True)


def score(a,i,ref):
    e=a['rows'][i]['evaluation'];boxes=e.get('walking_foot_boxes')
    if boxes is None:boxes=yaml.safe_load((OUT/'base/prepared/env_config.yaml').read_text())['perturbed_motion']['walking_foot_boxes']
    ids=[a['joint_names'].index(b['bone']) for b in boxes]
    p=np.asarray(a['positions'][i])@A;r=(np.asarray(a['basis'][i])@A).swapaxes(-1,-2)
    p=torch.tensor(p[:,ids],dtype=torch.float32)
    q=torch.tensor(Rotation.from_matrix(r[:,ids].reshape(-1,3,3)).as_quat().reshape(len(p),2,4),dtype=torch.float32)
    h=foot_box_bottoms(p,q,torch.tensor([b['center'] for b in boxes]),torch.tensor([b['half_axes'] for b in boxes]))
    name=Path(e['motion_file']).stem;period=torch.tensor([ref['motions'][name]['period_ticks']])
    f=FootRegularizers(1,'cpu');f.reset(torch.tensor([0]),p[:1],q[:1],h[:1]);cost=[np.zeros(3)];events=[]
    for t in range(1,len(p)):
        cost.append(f.append(p[t:t+1],q[t:t+1],h[t:t+1],period)[0].numpy().copy())
        for foot in range(2):
            if f.events[0,foot]:events.append([t,foot])
    raw=np.asarray(cost);mix=np.asarray(e['frame_tracking_mix'])
    raw[:,1:]=np.maximum(0,raw[:,1:]-np.array(ref['motions'][name]['reversal_allowance']))
    raw[:,0]*=(1-mix)
    return raw,dict(name=name,idle=bool(e['idle_row']),cohort=e['final_phase_cohort'],
        period_ticks=period[0].tolist(),events=events,bottoms=h.numpy().tolist(),
        base=float(np.mean(e['frame_losses']['total'][1:])),raw_mean=raw[1:].mean(0).tolist(),
        prior_mass=float((1-mix)[1:].mean()),prior_base=float((np.array(e['frame_losses']['total'])*(1-mix))[1:].mean()),
        prior_reversals=(raw[:,1:]*(1-mix)[:,None])[1:].mean(0).tolist())


def audit():
    torch.set_num_threads(2);ref=json.loads((OUT/'cadence-reference.json').read_text())
    exact=FOLDER/'rollout_step_00245159.json'
    files=sorted(set([exact]+sorted(FOLDER.glob('rollout_step_*.json'))[-4:]))
    rows=[];selected={}
    for path in files:
        a=json.loads(path.read_text())
        for i in range(len(a['rows'])):
            raw,row=score(a,i,ref);row.update(step=a['step'],row=i);rows.append(row)
            if path==exact and i in [0,18,7,3]:
                selected[str(i)]=dict(**row,raw=raw.tolist(),base_curve=a['rows'][i]['evaluation']['frame_losses']['total'])
    # Population weighting, not the deliberately unequal replay row counts.
    totals=[]
    for idle,share in [(False,.93),(True,.07)]:
        groups={}
        for x in rows:
            if x['idle']==idle:groups.setdefault(x['cohort'],[]).append(x)
        shares={'normal':.15 if idle else .30,'idle perturbed-':.15,'perturbed':.21,'perturbed+':.49}
        mass=sum(shares[g] for g in groups)
        means=sum(shares[g]*np.mean([[x['base']]+x['raw_mean']+[x['prior_mass'],x['prior_base']]+x['prior_reversals'] for x in xs],axis=0) for g,xs in groups.items())/mass
        totals.append(share*means)
    means=sum(totals);targets=np.array([.15,.10,.05]);weights=np.zeros(3)
    # Calibrate to the user-identified behavior, not catastrophic failed starts.
    idle=selected['0'];turn=selected['18']
    idle_base=np.mean(idle['base_curve'][126:136])
    idle_raw=np.mean(np.array(idle['raw'])[126:136],axis=0)
    weights[1:]=targets[1:]/.85*idle_base/idle_raw[1:]
    turn_base=np.mean(turn['base_curve'][1:41])
    turn_raw=np.mean(np.array(turn['raw'])[1:41],axis=0)
    weights[0]=.15/.85*(turn_base+np.dot(weights[1:],turn_raw[1:]))/turn_raw[0]
    assert np.isfinite(weights).all() and (weights>0).all()
    report=dict(run=RUN,steps=[int(p.stem.split('_')[-1]) for p in files],weights=weights.tolist(),
        terms=['excessive_stepping','foot_linear_reversal','foot_angular_reversal'],target_shares=targets.tolist(),
        base_mean=means[0],raw_means=means[1:4].tolist(),rows=rows,selected=selected,
        method='Fixed coefficients calibrated on requested step245159: idle126-135 gives linear/angular10/5% of resulting additive loss; turnaround1-40 gives stepping15% including other foot costs. Same coefficients on every row. Authored maximum reversal allowance; first term prior-gated. Population summary is diagnostic only because failed starts inflate its mean. No terminal penalties; future percentages may differ.')
    (OUT/'calibration.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['rows','selected']}),flush=True)
    for i in ['18','0','7','3']:
        x=selected[i];raw=np.array(x['raw']);print(i,x['name'],'first40 lifts',[e for e in x['events'] if e[0]<=40],
            'mean raw',raw.mean(0).tolist(),'126:135',raw[126:136].mean(0).tolist(),flush=True)


if __name__=='__main__':globals()[sys.argv[1]]()

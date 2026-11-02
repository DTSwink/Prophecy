"""Offline calibration of the vetted head loss, without changing a running trainer."""
import json,sys
from pathlib import Path
import numpy as np
import torch
from head_reversal import HeadReversal

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitLocomotion/head-reversal-com2-20261025'

def reference(p):
    v=np.zeros_like(p);v[1:]=np.diff(p,axis=0)*30
    smooth=v.copy();smooth[2:]=(v[2:]+v[1:-1])*.5
    speed=np.linalg.norm(smooth,axis=-1)
    u=smooth*np.maximum(0,1-.02/np.maximum(speed,1e-12))[:,None]
    loss=np.zeros(len(p))
    for t in range(8,len(p)):loss[t]=np.maximum(0,-u[t-6:t]@u[t]).mean()
    return loss

def check():
    # Exact recorded geometry, reset isolation, directional invariance and speed independence.
    result=json.loads((ROOT/'Saved/MimicKitLocomotion/idle-jitter-audit-20261025/result.json').read_text())
    a=json.loads(Path(result['replay']).read_text());p=np.asarray(a['positions'][0],dtype=np.float32)
    p=p[:,2]-p[:,0];score=HeadReversal(2,'cpu');ids=torch.arange(2)
    score.reset(ids,torch.from_numpy(np.stack([p[0]]*2)))
    values=[0.]
    for pos in p[1:]:values.append(float(score.append(torch.from_numpy(np.stack([pos]*2)))[0]))
    np.testing.assert_allclose(values,reference(p),rtol=1e-5,atol=2e-7)
    other=score.history[1].clone();score.reset(torch.tensor([0]),torch.tensor([[1.,2.,3.]]))
    assert score.ticks[0]==0 and score.history[0].count_nonzero()==0
    torch.testing.assert_close(score.history[1],other)
    t=np.arange(100)/30
    straight=np.stack([t*t,np.zeros(100),np.zeros(100)],-1)
    assert reference(straight).max()==0
    assert np.allclose(reference(p),reference(p[:,[2,0,1]]))
    report=dict(passed=True,recorded_replay_max_abs=float(np.max(abs(np.array(values)-reference(p)))),
                checks=['full recorded replay parity','per-row reset isolation','aligned acceleration zero','axis permutation invariance'])
    (OUT/'head-checks.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

def calibrate():
    active=json.loads((ROOT/'Saved/MimicKitLocomotion/active_run.json').read_text())
    folder=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+active['run'])/'debug'
    files=sorted(folder.glob('rollout_step_*.json'))[-6:]
    rows=[]
    for path in files:
        a=json.loads(path.read_text())
        for i,row in enumerate(a['rows']):
            p=np.asarray(a['positions'][i]);rel=p[:,2]-p[:,0];loss=reference(rel)
            e=row['evaluation'];idle=bool(e['idle_row'])
            baseline=np.asarray(e['frame_losses']['total'])-np.asarray(e['frame_losses'].get('auto_phase',np.zeros(len(p))))
            rows.append(dict(step=a['step'],name=row['clip_name'],idle=idle,cohort=e.get('final_phase_cohort'),
                ticks=len(p)-1,base=float(baseline[1:].mean()),raw=float(loss[1:].mean())))
    # Same fixed coefficient for all idle rows, another for all locomotion rows.
    # Use cohort mass rather than the intentionally uneven replay viewer selection.
    shares={'normal':.30,'perturbed':.70*.30,'perturbed+':.70*.70,'idle perturbed-':.15}
    weights={};report={}
    for idle,target in [(True,.30),(False,.03)]:
        selected=[x for x in rows if x['idle']==idle];groups={}
        for row in selected:groups.setdefault(row['cohort'],[]).append(row)
        mass={k:(.15 if idle and k=='normal' else shares[k]) for k in groups}
        totalmass=sum(mass.values());base=sum(mass[k]*np.mean([x['base'] for x in v]) for k,v in groups.items())/totalmass
        raw=sum(mass[k]*np.mean([x['raw'] for x in v]) for k,v in groups.items())/totalmass
        assert raw>1e-9 and np.isfinite(base+raw)
        weight=target/(1-target)*base/raw;name='idle' if idle else 'other';weights[name]=weight
        report[name]=dict(weight=weight,base_mean=base,raw_mean=raw,share=weight*raw/(base+weight*raw),
            observed_cohorts=list(groups),observed_population_mass=totalmass)
    report.update(run=active['run'],steps=sorted(set(x['step'] for x in rows)),rows=rows,
        weights=weights,method='Fixed per-category coefficients, cohort-stratified deterministic replay means; fraction of resulting additive body loss, excludes auto-phase and terminal penalties. Missing cohorts not fabricated.')
    (OUT/'calibration.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='rows'}))

if __name__=='__main__':
    OUT.mkdir(exist_ok=True);torch.set_num_threads(2)
    globals()[sys.argv[1]]()

"""Precompute authored reversal allowances and calibrate added legs on recent pushed idles."""
import sys,json,zipfile
from pathlib import Path
import numpy as np
import torch,yaml
from scipy.spatial.transform import Rotation
from leg_reversal import LegReversal
from prepare_perturbed_com2 import MJCFCharModel,MotionLib,mp_util

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitLocomotion/leg-losses-20261028'
BONES=['right_thigh','right_shin','left_thigh','left_shin']

def main():
    torch.set_num_threads(2);mp_util.init(0,1,'cpu',6817)
    plan=json.loads((OUT/'previous-plan.json').read_text())
    src=OUT/'reference';src.mkdir(exist_ok=True)
    with zipfile.ZipFile(plan['source']['local']) as z:
        for name in z.namelist():
            if name.startswith(('assets/uefn/','prepared/','motions/')):
                p=src/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
    for p in (src/'prepared').glob('*.yaml'):p.write_text(p.read_text().replace('/workspace/mimickit_trial',src.as_posix()))
    cfg=yaml.safe_load((src/'prepared/env_config.yaml').read_text());m=MJCFCharModel('cpu');m.load(cfg['char_file']);lib=MotionLib(cfg['motion_file'],m,'cpu')
    ids=[m.get_body_names().index(b) for b in BONES];refs={}
    for i in range(lib.get_num_motions()):
        name=Path(lib.get_motion_file(i)).stem;t=torch.arange(0,float(lib.get_motion_length(i))*4,1/30)
        root,rot,_,_,joints,_=lib.calc_motion_frame(torch.full(t.shape,i,dtype=torch.long),t)
        p,q=m.forward_kinematics(root,rot,joints);p,q=p[:,ids],q[:,ids]
        f=LegReversal(1,'cpu');f.reset(torch.tensor([0]),p[:1],q[:1]);raw=[]
        for k in range(1,len(t)):raw.append(f.append(p[k:k+1],q[k:k+1])[0].numpy().copy())
        refs[name]=np.max(raw,axis=0).tolist()
    (OUT/'reference.json').write_text(json.dumps(refs,indent=2))
    active=json.loads((ROOT/'Saved/MimicKitLocomotion/active_run.json').read_text())
    folder=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+active['run'])/'debug'
    files=sorted(folder.glob('rollout_step_*.json'))[-3:];assert files
    axis=np.array([[1,0,0],[0,0,1],[0,-1,0.]])
    values=[];base=[];records=[]
    for path in files:
        a=json.loads(path.read_text());ids=[a['joint_names'].index(b) for b in BONES]
        for i,row in enumerate(a['rows']):
            e=row['evaluation']
            if e.get('final_phase_cohort')!='idle perturbed-':continue
            p=torch.tensor((np.asarray(a['positions'][i])@axis)[:,ids],dtype=torch.float32)
            mat=(np.asarray(a['basis'][i])@axis).swapaxes(-1,-2)[:,ids]
            q=torch.tensor(Rotation.from_matrix(mat.reshape(-1,3,3)).as_quat().reshape(len(p),4,4),dtype=torch.float32)
            f=LegReversal(1,'cpu');f.reset(torch.tensor([0]),p[:1],q[:1]);raw=[np.zeros(2)]
            for k in range(1,len(p)):raw.append(f.append(p[k:k+1],q[k:k+1])[0].numpy().copy())
            raw=np.maximum(np.array(raw)-refs[Path(e['motion_file']).stem],0)
            # Include ordinary push/recovery periods; omit warmup and terminal frame.
            values.extend(raw[8:-1]);base.extend(e['frame_losses']['total'][8:-1])
            records.append(dict(file=str(path),row=i,ticks=len(p)))
    mean=np.mean(values,axis=0);baseline=float(np.mean(base));assert (mean>0).all()
    # Preserve the established linear/angular relative scaling, then calibrate their sum.
    relative=np.array(cfg['perturbed_motion']['foot_regularizers']['weights'][1:])
    weights=relative*(.07/.93*baseline/np.dot(mean,relative))
    report=dict(bones=BONES,weights=weights.tolist(),raw_mean=mean.tolist(),baseline=baseline,
        calibrated_share=float(np.dot(mean,weights)/(baseline+np.dot(mean,weights))),samples=len(base),rows=records,
        method='Fixed coefficients, combined7% of resulting additive loss on latest3 replay pushed-idle trajectories, ticks8 through penultimate. Existing foot linear/angular relative scaling retained. Per-motion authored maximum allowance; applies all rows all episode. Future shares may vary.')
    (OUT/'calibration.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()

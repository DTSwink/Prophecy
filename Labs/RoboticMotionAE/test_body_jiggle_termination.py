"""Calibrate moderate thresholds; independent recorded/live detector parity."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json,sys,numpy as np,torch
from scipy.spatial.transform import Rotation
from crawl_jiggle_termination import JiggleTermination,SPEC,recorded_detection
from analyze_crawl_jiggle_termination import first_trigger,features,ROOT
OUT=ROOT/'Saved/MimicKitSlowLoco/body-jiggle-audit-20261103'
torch.set_num_threads(1)

def test_sequence(pose):
    expected,streak=recorded_detection(pose,[5,8],0,30.,list(range(9)))
    pos=pose[:,[5,8],:3]-pose[:,0:1,:3];vel=np.diff(pos,axis=0)*30
    r=pose[:,:9,3:7]
    omega=(Rotation.from_quat(r[1:].reshape(-1,4))*Rotation.from_quat(r[:-1].reshape(-1,4)).inv()).as_rotvec().reshape(-1,9,3)*30
    h=JiggleTermination(1,'cpu');actual=[False];counts=[0]
    for v,a in zip(vel,omega):
        actual.append(bool(h.update(torch.tensor(v[None],dtype=torch.float32),torch.tensor(a[None],dtype=torch.float32),torch.tensor([True]))[0]));counts.append(int(h.streak[0]))
    np.testing.assert_array_equal(actual,expected);np.testing.assert_array_equal(counts,streak)
    return np.flatnonzero(expected).tolist()

def main():
    coverage=json.loads((OUT/'coverage-calibration.json').read_text());assert coverage['passed']
    rows=coverage['rows'];counts=coverage['counts']
    known=[]
    with np.load(ROOT/'Saved/MimicKitSlowLoco/jolt-vibration-20261103/replay.npz') as recording:
        for i in (0,2,5,7):
            suffix='' if i==0 else '_'+str(i);pose=recording['pose'+suffix].astype(float)
            hits=test_sequence(pose);assert hits;known.append(dict(row=i,first_frame=hits[0]))
            assert not test_sequence(recording['reference_pose'+suffix].astype(float))
    # Latest capture was not needed to pick the thresholds; test exact torch/NumPy parity too.
    latest=Path(coverage['exact_capture'])
    data=json.loads(latest.read_text());newest=[]
    for i in range(len(data['rows'])):
        pos=np.asarray(data['positions'][i]);basis=np.asarray(data['basis'][i]).swapaxes(-1,-2)
        quat=Rotation.from_matrix(basis.reshape(-1,3,3)).as_quat().reshape(-1,15,4)
        hits=test_sequence(np.concatenate((pos,quat),-1));newest.append(dict(row=i,first_frame=hits[0] if hits else None))
    # Normal smooth gait, constant drift, one shock, and tiny 7.5Hz chatter pass.
    n=120;t=np.arange(n)/30
    for kind in ('constant','smooth','impact','tiny','jiggle','pelvis_jiggle'):
        h=JiggleTermination(2,'cpu');flag=[]
        for f in range(n):
            speed={'constant':.3,'smooth':.5*np.sin(2*np.pi*t[f]),'impact':2. if f==40 else 0.,'tiny':.02*(-1)**f,'jiggle':.3*(-1)**f,'pelvis_jiggle':0.}[kind]
            v=torch.zeros(2,2,3);v[:,:,0]=float(speed);a=torch.zeros(2,9,3)
            if kind=='pelvis_jiggle':a[:,0,0]=3.*(-1)**f
            out=h.update(v,a,torch.tensor([True,False]));flag.append(bool(out[0]));assert not out[1]
        assert any(flag)==(kind in ('jiggle','pelvis_jiggle')),kind
        if kind in ('jiggle','pelvis_jiggle'):assert not any(flag[:34])
    h=JiggleTermination(2,'cpu');h.age[:]=80;h.streak[:]=5;h.linear[:]=1.;h.reset(torch.tensor([0]))
    assert h.age.tolist()==[0,80] and h.streak.tolist()==[0,5] and h.linear[1].all() and not h.linear[0].any()
    assert newest[0]['first_frame']==64
    report=dict(passed=True,spec=SPEC,counts=counts,known_bad=known,latest=str(latest),latest_rows=newest,
                synthetic_constant_gait_impact_small_jitter_pass=True,synthetic_repeated_jiggle_caught=True,
                disabled_scope_and_partial_reset_pass=True,torch_numpy_exact_flags=True,rows=rows)
    (OUT/'termination-calibration.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
if __name__=='__main__':main()

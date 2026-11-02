"""Standalone sparse-factor launch fusion experiment; never modifies production."""
import json,time,traceback
from pathlib import Path
import torch,warp as wp,mujoco,mujoco_warp as mjw
from fused_factor_probe import FusedFactor
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024'

def main():
    torch.set_num_threads(1);wp.init();wp.set_device('cuda:0')
    mm=mujoco.MjModel.from_binary_path(str(OUT/'native-model.mjb'));cpu=mujoco.MjData(mm);mujoco.mj_forward(mm,cpu)
    m=mjw.put_model(mm);d=mjw.put_data(mm,cpu,nworld=2048,nconmax=150,njmax=450);f=FusedFactor(m,d)
    y=wp.zeros_like(d.qvel);x=wp.zeros_like(d.qvel);checks=[]
    def original():f.original(m,d,d.qM,d.qLD,d.qLDiagInv)
    def optimized():f.apply(m,d,d.qM,d.qLD,d.qLDiagInv)
    for trial in range(8):
        pos=wp.to_torch(d.qpos)
        for j,kind in enumerate(mm.jnt_type):
            start=int(mm.jnt_qposadr[j]);width=7 if kind==mujoco.mjtJoint.mjJNT_FREE else 4 if kind==mujoco.mjtJoint.mjJNT_BALL else 1
            if width>1:
                start+=3 if width==7 else 0
                q=torch.randn((2048,4),device='cuda');pos[:,start:start+4]=q/q.norm(dim=1,keepdim=True)
        mjw.kinematics(m,d);mjw.com_pos(m,d);mjw.crb(m,d);wp.to_torch(y).normal_()
        results=[]
        for call in [original,original,optimized]:
            call();mjw.solve_m(m,d,x,y);wp.synchronize()
            results.append(dict(factor=wp.to_torch(d.qLD).clone(),diag=wp.to_torch(d.qLDiagInv).clone(),solved=wp.to_torch(x).clone()))
        row={'trial':trial}
        for key in results[0]:
            a,b,c=[v[key] for v in results];err=float((a-c).abs().max());repeat=float((a-b).abs().max())
            row[key]=dict(max_error=err,reference_repeat=repeat,relative_l2=float(torch.linalg.vector_norm(a-c)/torch.linalg.vector_norm(a)),finite=bool(torch.isfinite(c).all()))
        checks.append(row);(OUT/'factor-fused-checks.json').write_text(json.dumps(checks,indent=2))
        assert all(v['finite'] for k,v in row.items() if k!='trial')
        assert row['solved']['relative_l2']<1e-4,row
    graphs=[]
    for call in [original,optimized]:
        with wp.ScopedCapture() as cap:
            for _ in range(16):call()
        graphs.append(cap.graph)
    times=[]
    for mode in [0,1,1,0]*3:
        wp.capture_launch(graphs[mode]);wp.synchronize();start=time.perf_counter()
        for _ in range(10):wp.capture_launch(graphs[mode])
        wp.synchronize();times.append(dict(optimized=bool(mode),seconds=(time.perf_counter()-start)/160))
    result=dict(checks=checks,timings=times,levels=f.levels,nc=m.nC)
    (OUT/'factor-fused-complete.json').write_text(json.dumps(result,indent=2));print('RESULT'+json.dumps(result),flush=True)

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'factor-fused-failure.txt').write_text(traceback.format_exc());raise

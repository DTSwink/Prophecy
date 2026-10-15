"""Equation-level tests before checkpoint experiments (no environment imports)."""
import json,time
from pathlib import Path
import numpy as np
import scipy.optimize
import warp as wp
from capped_velocity_integrator import inverse_kernel, solve

def main():
    wp.init(); device='cpu'; wp.set_device(device); rng=np.random.default_rng(31913); reports=[]
    for name,n in [('single_axis',2),('coupled_body',40)]:
        worlds=16;h=1/240
        if n==2:
            mass=np.broadcast_to(np.diag([0.006,0.02]),(worlds,n,n)).copy()
        else:
            q=rng.normal(size=(worlds,n,n));mass=q@q.transpose(0,2,1)/n+np.eye(n)*0.02
        damping=np.full((1,n),0.01);gain=np.full(n,40.);cap=np.full(n,90.)
        old=rng.uniform(-40,40,(worlds,n));target=rng.uniform(-6,6,(worlds,n))
        external=rng.normal(size=(worlds,n)) if n==40 else np.zeros_like(old)
        original=np.clip(gain*(target-old),-cap,cap);total=external+original
        array=lambda x,t=float:wp.array(x,dtype=t,device=device)
        M=array(mass);D=array(damping);I=array(np.eye(n));inv=wp.empty_like(M)
        velocity=wp.empty((worlds,n),dtype=float,device=device);torque=wp.empty_like(velocity)
        accel=wp.empty_like(velocity);stats=wp.empty((worlds,2),dtype=float,device=device)
        wp.launch_tiled(inverse_kernel(n),dim=worlds,inputs=[M,D,h,I,inv],block_dim=64)
        wp.launch(solve,dim=worlds,inputs=[n,n,h,256,1e-3,inv,array(old),array(total),array(original),
            array(target),array(np.arange(n),int),array(np.arange(n),int),array(gain),array(-cap),array(cap),
            velocity,torque,accel,stats])
        v=velocity.numpy();t=torque.numpy();status=stats.numpy();A=mass+h*damping[:,:,None]*np.eye(n)
        predicted=np.clip(gain*(target-v),-cap,cap)
        assert np.max(abs(predicted-t))<0.003,(name,status.max(axis=0))
        assert np.max(abs(t))<=90
        momentum_error=float(abs(np.einsum('wij,wj->wi',A,v-old)-h*(external+t)).max())
        # Float32 integration subtracts speeds up to40rad/s across40 coupled
        # coordinates; validate against the independent float64 solution too.
        assert momentum_error<1e-4,(name,momentum_error)
        maxerr=0.
        for w in range(worlds):
            invA=np.linalg.inv(A[w]);free=old[w]+h*invA@external[w]
            H=h*invA+np.diag(1/gain);b=target[w]-free;L=np.linalg.cholesky(H)
            optimum=scipy.optimize.lsq_linear(L.T,np.linalg.solve(L,b),bounds=(-cap,cap),tol=1e-12)
            expected=free+h*invA@optimum.x
            maxerr=max(maxerr,float(np.max(abs(expected-v[w]))))
        assert maxerr<1e-4,(name,maxerr)
        if n==2:
            assert np.all((v-target)*(old-target)>=-1e-5), 'Isolated motor overshot its target'
        reports.append(dict(case=name,worlds=worlds,max_reference_velocity_error=maxerr,
            max_motor_equation_defect_nm=float(abs(predicted-t).max()),momentum_residual=momentum_error,
            max_sweeps=float(status[:,1].max())))
    out=Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913/capped_integrator'
    out.mkdir(exist_ok=True);(out/'equation_tests.json').write_text(json.dumps(reports,indent=2))
    print(json.dumps(reports,indent=2),flush=True)

if __name__=='__main__':main()

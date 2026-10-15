"""Isolated GPU equation prototype. NOT registered with any training engine.

Jolt-style non-associated friction: friction uses the normal impulse from the
previous iteration; normal is solved last. Motors are capped end-step motors.
No CPU transfers or allocations occur inside solve/captured graph replay.
"""
import warp as wp


@wp.struct
class ContactProblem:
    nv: int
    nmotor: int
    relaxation: float
    ncontact: wp.array(dtype=int)
    dt: wp.array(dtype=float)
    inv: wp.array3d(dtype=float)
    free: wp.array2d(dtype=float)
    dofs: wp.array(dtype=int)
    gains: wp.array(dtype=float)
    caps: wp.array(dtype=float)
    commands: wp.array2d(dtype=float)
    friction: wp.array2d(dtype=float)
    J: wp.array4d(dtype=float)
    response: wp.array4d(dtype=float)
    diagonal: wp.array3d(dtype=float)
    velocity: wp.array2d(dtype=float)
    motor_impulse: wp.array2d(dtype=float)
    contact_impulse: wp.array3d(dtype=float)
    stats: wp.array2d(dtype=float)
    nlimit: wp.array(dtype=int)
    limit_J: wp.array3d(dtype=float)
    limit_response: wp.array3d(dtype=float)
    limit_diagonal: wp.array2d(dtype=float)
    limit_target: wp.array2d(dtype=float)
    limit_compliance: wp.array2d(dtype=float)
    limit_bilateral: wp.array2d(dtype=int)
    limit_impulse: wp.array2d(dtype=float)


@wp.kernel(enable_backward=False)
def prepare_response(p: ContactProblem):
    w,c,a,i=wp.tid()
    if c>=p.ncontact[w]: return
    value=float(0.)
    for j in range(p.nv): value+=p.inv[w,i,j]*p.J[w,c,a,j]
    p.response[w,c,a,i]=value


@wp.kernel(enable_backward=False)
def prepare_diagonal(p: ContactProblem):
    w,c,a=wp.tid()
    if c>=p.ncontact[w]: return
    value=float(0.)
    for j in range(p.nv): value+=p.J[w,c,a,j]*p.response[w,c,a,j]
    p.diagonal[w,c,a]=value


@wp.kernel(enable_backward=False)
def prepare_limit_response(p: ContactProblem):
    w,c,i=wp.tid()
    if c>=p.nlimit[w]: return
    value=float(0.)
    for j in range(p.nv): value+=p.inv[w,i,j]*p.limit_J[w,c,j]
    p.limit_response[w,c,i]=value


@wp.kernel(enable_backward=False)
def prepare_limit_diagonal(p: ContactProblem):
    w,c=wp.tid()
    if c>=p.nlimit[w]: return
    value=float(0.)
    for j in range(p.nv): value+=p.limit_J[w,c,j]*p.limit_response[w,c,j]
    p.limit_diagonal[w,c]=value


@wp.kernel(enable_backward=False)
def iterate(p: ContactProblem, iterations: int):
    w=wp.tid(); dt=p.dt[0]
    for j in range(p.nv): p.velocity[w,j]=p.free[w,j]
    for a in range(p.nmotor): p.motor_impulse[w,a]=0.
    for c in range(p.ncontact[w]):
        for a in range(3): p.contact_impulse[w,c,a]=0.
    for it in range(iterations):
        for a in range(p.nmotor):
            dof=p.dofs[a]; compliance=1./(dt*p.gains[a]); old=p.motor_impulse[w,a]
            impulse=wp.clamp(old+(p.commands[w,a]-p.velocity[w,dof]-compliance*old)/(p.inv[w,dof,dof]+compliance),-dt*p.caps[a],dt*p.caps[a])
            for j in range(p.nv): p.velocity[w,j]+=p.inv[w,j,dof]*(impulse-old)
            p.motor_impulse[w,a]=impulse
        for c in range(p.ncontact[w]):
            if p.friction[w,c]>0.:
                v1=float(0.); v2=float(0.)
                for j in range(p.nv):
                    v1+=p.J[w,c,1,j]*p.velocity[w,j]
                    v2+=p.J[w,c,2,j]*p.velocity[w,j]
                old1=p.contact_impulse[w,c,1]; old2=p.contact_impulse[w,c,2]
                t1=old1-v1/p.diagonal[w,c,1]; t2=old2-v2/p.diagonal[w,c,2]
                length=wp.sqrt(t1*t1+t2*t2); bound=p.friction[w,c]*p.contact_impulse[w,c,0]
                scale=wp.min(1.,bound/wp.max(length,1e-30)); t1*=scale; t2*=scale
                for j in range(p.nv):
                    p.velocity[w,j]+=p.response[w,c,1,j]*(t1-old1)+p.response[w,c,2,j]*(t2-old2)
                p.contact_impulse[w,c,1]=t1; p.contact_impulse[w,c,2]=t2
            vn=float(0.)
            for j in range(p.nv): vn+=p.J[w,c,0,j]*p.velocity[w,j]
            old=p.contact_impulse[w,c,0]; normal=wp.max(0.,old-vn/p.diagonal[w,c,0])
            for j in range(p.nv): p.velocity[w,j]+=p.response[w,c,0,j]*(normal-old)
            p.contact_impulse[w,c,0]=normal
    defect=float(0.)
    for a in range(p.nmotor):
        expected=wp.clamp(p.gains[a]*(p.commands[w,a]-p.velocity[w,p.dofs[a]]),-p.caps[a],p.caps[a])
        defect=wp.max(defect,wp.abs(p.motor_impulse[w,a]/dt-expected))
    p.stats[w,0]=defect


class SequentialContactProblem:
    def __init__(self, snapshots, device):
        import numpy as np
        n=len(snapshots); p=ContactProblem(); p.nv=len(snapshots[0]['free']); p.nmotor=len(snapshots[0]['dofs']); p.relaxation=1.
        nc=max(1,max(len(s['J']) for s in snapshots)); self.nworld=n; self.capacity=nc
        arr=lambda x,dtype=float: wp.array(np.asarray(x),dtype=dtype,device=device)
        p.ncontact=arr([len(s['J']) for s in snapshots],int)
        p.dt=arr([float(snapshots[0]['dt'])]); p.dofs=arr(snapshots[0]['dofs'],int)
        p.gains=arr(snapshots[0]['gain']); p.caps=arr(snapshots[0]['caps']/snapshots[0]['dt'])
        for s in snapshots:
            np.testing.assert_array_equal(s['dofs'],snapshots[0]['dofs'])
            np.testing.assert_allclose(s['dt'],snapshots[0]['dt'])
        p.inv=arr([s['inv'] for s in snapshots]); p.free=arr([s['free'] for s in snapshots])
        p.commands=arr([s['command'] for s in snapshots]); p.friction=arr([[s['friction']]*nc for s in snapshots])
        jac=np.zeros((n,nc,3,p.nv),dtype=np.float32)
        for w,s in enumerate(snapshots): jac[w,:len(s['J'])]=s['J']
        p.J=arr(jac)
        zero=lambda shape: wp.zeros(shape,dtype=float,device=device)
        p.response=zero(jac.shape); p.diagonal=zero((n,nc,3)); p.velocity=zero((n,p.nv))
        p.motor_impulse=zero((n,p.nmotor)); p.contact_impulse=zero((n,nc,3)); p.stats=zero((n,1))
        p.nlimit=wp.zeros(n,dtype=int,device=device)
        p.limit_J=zero((n,1,p.nv));p.limit_response=zero((n,1,p.nv))
        p.limit_diagonal=zero((n,1));p.limit_target=zero((n,1));p.limit_compliance=zero((n,1))
        p.limit_bilateral=wp.zeros((n,1),dtype=int,device=device);p.limit_impulse=zero((n,1))
        self.p=p; self.device=device
        self.tiled_kernel=make_tiled_iteration(p.nv,p.nmotor)

    def solve(self, iterations=100, tiled=False):
        p=self.p
        wp.launch(prepare_response,dim=(self.nworld,self.capacity,3,p.nv),inputs=[p],device=self.device)
        wp.launch(prepare_diagonal,dim=(self.nworld,self.capacity,3),inputs=[p],device=self.device)
        if tiled:
            wp.launch_tiled(self.tiled_kernel,dim=self.nworld,inputs=[p,iterations],block_dim=32,device=self.device)
        else:
            wp.launch(iterate,dim=self.nworld,inputs=[p,iterations],device=self.device)


@wp.func
def multiply(a: float,b: float): return a*b


def make_tiled_iteration(nv,nmotor):
    @wp.kernel(module='unique',enable_backward=False)
    def tiled(p: ContactProblem, iterations: int):
        w=wp.tid(); dt=p.dt[0]
        v=wp.tile_load(p.free,shape=(1,nv),offset=(w,0),storage='shared')
        inverse=wp.tile_load(p.inv[w],shape=(nv,nv),storage='shared')
        impulses=wp.tile_zeros(shape=(1,nmotor),dtype=float,storage='shared')
        for c in range(p.ncontact[w]):
            for a in range(3): p.contact_impulse[w,c,a]=0.
        for c in range(p.nlimit[w]): p.limit_impulse[w,c]=0.
        for it in range(iterations):
            for a in range(p.nmotor):
                dof=p.dofs[a]; compliance=1./(dt*p.gains[a]); old=wp.tile_extract(impulses,0,a)
                speed=wp.tile_extract(v,0,dof)
                impulse=wp.clamp(old+(p.commands[w,a]-speed-compliance*old)/(p.inv[w,dof,dof]+compliance),-dt*p.caps[a],dt*p.caps[a])
                impulse=old+p.relaxation*(impulse-old)
                response=wp.tile_view(inverse,offset=(dof,0),shape=(1,nv))
                wp.tile_assign(v,v+response*(impulse-old))
                impulses[0,a]=impulse
            for c in range(p.nlimit[w]):
                jac=wp.tile_reshape(wp.tile_load(p.limit_J[w,c],shape=(nv,)),shape=(1,nv))
                speed=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac,v)),0)
                old=p.limit_impulse[w,c]; compliance=p.limit_compliance[w,c]
                impulse=old+(p.limit_target[w,c]-speed-compliance*old)/(p.limit_diagonal[w,c]+compliance)
                if p.limit_bilateral[w,c]==0: impulse=wp.max(0.,impulse)
                impulse=old+p.relaxation*(impulse-old)
                response=wp.tile_reshape(wp.tile_load(p.limit_response[w,c],shape=(nv,)),shape=(1,nv))
                wp.tile_assign(v,v+response*(impulse-old))
                p.limit_impulse[w,c]=impulse
            for c in range(p.ncontact[w]):
                if p.friction[w,c]>0.:
                    j1=wp.tile_reshape(wp.tile_load(p.J[w,c,1],shape=(nv,)),shape=(1,nv)); j2=wp.tile_reshape(wp.tile_load(p.J[w,c,2],shape=(nv,)),shape=(1,nv))
                    v1=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,j1,v)),0)
                    v2=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,j2,v)),0)
                    old1=p.contact_impulse[w,c,1]; old2=p.contact_impulse[w,c,2]
                    t1=old1-v1/p.diagonal[w,c,1]; t2=old2-v2/p.diagonal[w,c,2]
                    length=wp.sqrt(t1*t1+t2*t2); bound=p.friction[w,c]*p.contact_impulse[w,c,0]
                    scale=wp.min(1.,bound/wp.max(length,1e-30)); t1*=scale; t2*=scale
                    t1=old1+p.relaxation*(t1-old1); t2=old2+p.relaxation*(t2-old2)
                    r1=wp.tile_reshape(wp.tile_load(p.response[w,c,1],shape=(nv,)),shape=(1,nv)); r2=wp.tile_reshape(wp.tile_load(p.response[w,c,2],shape=(nv,)),shape=(1,nv))
                    wp.tile_assign(v,v+r1*(t1-old1)+r2*(t2-old2))
                    p.contact_impulse[w,c,1]=t1; p.contact_impulse[w,c,2]=t2
                jn=wp.tile_reshape(wp.tile_load(p.J[w,c,0],shape=(nv,)),shape=(1,nv))
                vn=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jn,v)),0)
                old=p.contact_impulse[w,c,0]; normal=wp.max(0.,old-vn/p.diagonal[w,c,0])
                normal=old+p.relaxation*(normal-old)
                rn=wp.tile_reshape(wp.tile_load(p.response[w,c,0],shape=(nv,)),shape=(1,nv)); wp.tile_assign(v,v+rn*(normal-old))
                p.contact_impulse[w,c,0]=normal
        velocity_out=p.velocity
        wp.tile_store(velocity_out,v,offset=(w,0))
        motor_out=p.motor_impulse
        wp.tile_store(motor_out,impulses,offset=(w,0))
        defect=float(0.)
        for a in range(p.nmotor):
            speed=wp.tile_extract(v,0,p.dofs[a])
            expected=wp.clamp(p.gains[a]*(p.commands[w,a]-speed),-p.caps[a],p.caps[a])
            defect=wp.max(defect,wp.abs(p.motor_impulse[w,a]/dt-expected))
        p.stats[w,0]=defect
    return tiled


def main():
    import json,time,numpy as np
    from pathlib import Path
    out=Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913/causal_transfer'
    paths=sorted(out.glob('sequential_*_?.npz'))
    assert len(paths)==12
    snapshots=[dict(np.load(p)) for p in paths]
    expected=np.array([np.load(p.with_name(p.stem+'_expected.npy')) for p in paths])
    report=[]; wp.init()
    for device,tiled in [('cpu',False),('cuda:0',False),('cuda:0',True)]:
        problem=SequentialContactProblem(snapshots,device); problem.solve(100,tiled)
        actual=problem.p.velocity.numpy()
        np.testing.assert_allclose(actual,expected,atol=1e-5,rtol=1e-5)
        defect=float(problem.p.stats.numpy().max()); assert defect<.002
        row=dict(device=device,tiled=tiled,max_velocity_error=float(np.max(np.abs(actual-expected))),motor_defect_nm=defect)
        if device.startswith('cuda'):
            batch=SequentialContactProblem([snapshots[i%12] for i in range(512)],device); batch.solve(100,tiled)
            with wp.ScopedCapture(device=device) as capture: batch.solve(100,tiled)
            for _ in range(5): wp.capture_launch(capture.graph)
            wp.synchronize_device(device); start=time.perf_counter()
            for _ in range(50): wp.capture_launch(capture.graph)
            wp.synchronize_device(device)
            row['batch512_solver_ms']=(time.perf_counter()-start)*1000/50
            row['graph_replay_max_error']=float(np.max(np.abs(batch.p.velocity.numpy()-expected[np.arange(512)%12])))
            assert row['graph_replay_max_error']<2e-5
        report.append(row); print(json.dumps(row),flush=True)
    (out/'sequential_gpu.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__': main()

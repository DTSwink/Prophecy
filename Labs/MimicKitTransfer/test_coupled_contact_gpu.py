"""Replay saved constraint equations through the coupled GPU solver and CUDA graph.

Pass one or more solver_capture NPZ files. Checks all captured worlds, float64
reference velocity when present, unsupported-error preservation and NaN rejection.
No engine, asset, policy, replay or training process is modified.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/MimicKitUEFN/dependencies'))
import numpy as np
import warp as wp
from sequential_contact_gpu import ContactProblem
from contact_manifolds_gpu import allocate as manifold_allocate
from coupled_contact_gpu import allocate

def load_problem(path,all_worlds=False):
    data=dict(np.load(path));indices=np.arange(len(data['free'])) if all_worlds else np.flatnonzero(data['errors'])[:1]
    q=ContactProblem();q.nv=data['free'].shape[1];q.nmotor=len(data['dofs']);q.relaxation=.5
    for name in ('dt','gains','caps','dofs'):
        setattr(q,name,wp.array(data[name],dtype=int if name=='dofs' else float,device='cuda:0'))
    for name in ('inv','free','commands','J','diagonal','ncontact','nlimit','limit_J','limit_diagonal','limit_target','limit_compliance','limit_bilateral','friction'):
        setattr(q,name,wp.array(data[name][indices],dtype=int if name in ('ncontact','nlimit','limit_bilateral') else float,device='cuda:0'))
    n=len(indices);nc=data['J'].shape[1];nl=data['limit_J'].shape[1]
    q.manifold=manifold_allocate(n,nc,q.nv,'cuda:0')
    for name in ('count','group','size','radius','J','diagonal'):
        getattr(q.manifold,name).assign(data['manifold_'+name][indices])
    q.velocity=wp.zeros((n,q.nv));q.motor_impulse=wp.zeros((n,q.nmotor));q.contact_impulse=wp.zeros((n,nc,3));q.limit_impulse=wp.zeros((n,nl));q.stats=wp.zeros((n,1));q.warm_state=wp.zeros(n,dtype=int);q.solver_error=wp.full(n,5,dtype=int)
    return q,indices


def main():
    parser=argparse.ArgumentParser();parser.add_argument('captures',nargs='+',type=Path)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    assert not args.out.exists(),'Preserve previous evidence'
    wp.init();wp.set_device('cuda:0');reports=[]
    for path in args.captures:
        q,indices=load_problem(path,True);p,kernel,slots=allocate(q)
        def solve():wp.launch_tiled(kernel,dim=slots,inputs=[q,p,q.free.shape[0]],block_dim=64)
        solve();wp.synchronize()
        np.testing.assert_array_equal(q.solver_error.numpy(),0)
        vel=q.velocity.numpy();assert np.isfinite(vel).all()
        stats=p.result.numpy();assert stats[:,1].max()<1e-10
        report=dict(capture=str(path),worlds=len(indices),max_residual=float(stats[:,1].max()),
                    max_motor_nm=float(q.stats.numpy().max()),max_seeds=int(stats[:,2].max()))
        reference=path.with_name('reference-converged.npy')
        if reference.exists():
            failed=int(np.flatnonzero(np.load(path)['errors'])[0]);expected=np.load(reference)
            np.testing.assert_allclose(vel[failed],expected,atol=1e-5,rtol=1e-6)
            report['reference_max_velocity_error']=float(abs(vel[failed]-expected).max())
        with wp.ScopedCapture() as capture:
            q.solver_error.fill_(5);solve()
        wp.capture_launch(capture.graph);wp.synchronize()
        np.testing.assert_array_equal(q.solver_error.numpy(),0)
        np.testing.assert_array_equal(q.velocity.numpy(),vel)
        for error in (0,1,2,3,4,6,9):
            q.solver_error.fill_(error);solve();wp.synchronize()
            np.testing.assert_array_equal(q.solver_error.numpy(),error)
            np.testing.assert_array_equal(q.velocity.numpy(),vel)
        q.free.fill_(float('nan'));q.solver_error.fill_(5);solve();wp.synchronize()
        np.testing.assert_array_equal(q.solver_error.numpy(),5)
        np.testing.assert_array_equal(q.velocity.numpy(),vel)
        report.update(cuda_graph=True,unsupported_errors_preserved=True,nonfinite_not_committed=True)
        reports.append(report);print(json.dumps(report),flush=True)
    args.out.write_text(json.dumps(reports,indent=2))

if __name__=='__main__':main()

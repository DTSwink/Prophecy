"""Saved opposite-cap cycle: GPU result against independent scalar equations."""
import os,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,mujoco,mujoco_warp as mjw,warp as wp
from coupled_velocity_motors import CoupledVelocityMotors
from sequential_contact_adapter import SequentialContactAdapter
from sequential_contact_gpu import prepare_response,prepare_limit_response
from contact_manifolds_gpu import prepare_response as prepare_manifold_response
from probe_block_failure import Equations
sys.path.insert(0,str(ROOT/'Labs/MimicKitUEFN'))
from runtime import install_limits


def main(graph=False,path=None):
    folder=probe.OUT/'causal_transfer';path=Path(path) if path else folder/('contact_first_solver_failure_graph.npz' if graph else 'contact_first_solver_failure.npz')
    p=dict(np.load(path));e=Equations(path);reference,*_=e.scalar(3000)
    wp.init();wp.set_device('cuda:0')
    m=mujoco.MjModel.from_binary_path(str(folder/'sequential_model.mjb'));m.opt.jacobian=mujoco.mjtJacobian.mjJAC_DENSE
    m.opt.timestep=float(p['dt'][0])
    n=len(p['errors']);wm=mjw.put_model(m);d=mjw.put_data(m,mujoco.MjData(m),nworld=n,nconmax=150,njmax=450)
    install_limits(m,wm);motors=CoupledVelocityMotors(wm,d,m)
    custom=SequentialContactAdapter(wm,d,m,motors,allow_soft_limits=True,hard_limit_control=True,
        relaxation=.5,block_motors=True,manifolds=True)
    q=custom.p
    for name in ('dt','gains','caps','dofs'):
        np.testing.assert_allclose(getattr(q,name).numpy(),p[name],rtol=1e-6,atol=1e-7,err_msg=name)
    for name in ('inv','free','commands','J','diagonal','ncontact','nlimit','limit_J','limit_diagonal',
                 'limit_target','limit_compliance','limit_bilateral','friction'):
        getattr(q,name).assign(p[name])
    for name in ('count','group','size','radius','J','diagonal'):
        getattr(q.manifold,name).assign(p['manifold_'+name])
    q.manifold.response.assign(np.einsum('wiaj,wjk->wiak',p['manifold_J'],p['inv']))
    d.qM.assign(p['mass'])
    def solve(seed):
        custom.error.zero_()
        wp.launch(prepare_response,dim=(n,custom.capacity,3,q.nv),inputs=[q],device='cuda:0')
        wp.launch(prepare_limit_response,dim=(n,q.limit_J.shape[1],q.nv),inputs=[q],device='cuda:0')
        wp.launch(prepare_manifold_response,dim=(n,custom.capacity,3,q.nv),inputs=[q.manifold,q.inv],device='cuda:0')
        wp.launch_tiled(custom.iterate_kernel,dim=n,inputs=[q,seed],block_dim=32,device='cuda:0')
        wp.launch_tiled(custom.block_kernel,dim=n,inputs=[q,d.qM,custom.identity,100,custom.error],block_dim=32,device='cuda:0')
        wp.launch_tiled(custom.fallback_kernel,dim=n,inputs=[q,3000],block_dim=32,device='cuda:0')
    report=[]
    for seed in (50,0):
        solve(seed);np.testing.assert_array_equal(custom.error.numpy(),0)
        actual=q.velocity.numpy()[e.world]
        np.testing.assert_allclose(actual,reference,atol=5e-5,rtol=1e-5)
        with wp.ScopedCapture(device='cuda:0') as capture:solve(seed)
        wp.capture_launch(capture.graph);np.testing.assert_array_equal(custom.error.numpy(),0)
        np.testing.assert_allclose(q.velocity.numpy()[e.world],reference,atol=5e-5,rtol=1e-5)
        report.append(dict(world=e.world,seed_iterations=seed,max_velocity_error=float(abs(actual-reference).max()),
            motor_defect_nm=float(q.stats.numpy().max()),cuda_capture_verified=True,
            fallback_count=int(q.fallback_count.numpy().sum()),fallback_steps=int(q.fallback_steps.numpy().sum())))
    (folder/(path.stem+'_gpu_reference.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':main('--graph' in sys.argv)

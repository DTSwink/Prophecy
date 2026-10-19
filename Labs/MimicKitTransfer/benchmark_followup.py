"""Screen candidates at identical saved impacts, paired GPU graph timings."""
import argparse,json,sys
from pathlib import Path
from benchmark_vanilla_transfer import (ROOT,probe,np,mujoco,mjw,wp,encode,install_limits,CoupledVelocityMotors,SplitLimitProjection,joint_metadata,measure)
from followup_candidates import adapter_class,OUT

def main():
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=['batch','scratch','active']);a=ap.parse_args()
    path=OUT/(a.kind+'-physics.json');assert not path.exists()
    folder=probe.OUT/'causal_transfer';wp.init();wp.set_device('cuda:0')
    source=np.load(folder/'body_velocity_engine_cpu_phase0.5625.npz');steps=np.arange(512)%24+8
    results={};graphs={};objects=[]
    for kind in ['baseline',a.kind]:
        cls=adapter_class(kind)
        m=mujoco.MjModel.from_binary_path(str(folder/'sequential_model.mjb'))
        m.opt.timestep=1/240;m.opt.jacobian=mujoco.mjtJacobian.mjJAC_DENSE
        wm=mjw.put_model(m);d=mjw.put_data(m,mujoco.MjData(m),nworld=512,nconmax=150,njmax=450)
        install_limits(m,wm);motor=CoupledVelocityMotors(wm,d,m);motor.install()
        custom=cls(wm,d,m,motor,iterations=100,seed_iterations=50,allow_soft_limits=True,relaxation=.5,hard_limit_control=True,block_motors=True,manifolds=True,jolt_limit_axes=True)
        custom.install();projection=SplitLimitProjection(m,d,joint_metadata(m),'cuda:0')
        q,v=zip(*(encode(m,s) for s in source['subin'][steps]));q=wp.array(np.asarray(q,np.float32));v=wp.array(np.asarray(v,np.float32))
        ctrl=np.zeros((512,m.nu),np.float32);ctrl[:,motor.ids]=source['actions'][steps//8,0].clip(-2*np.pi,2*np.pi)
        d.ctrl.assign(ctrl);d.xfrc_applied.assign(source['forces'][steps].astype(np.float32))
        def step():
            wp.copy(d.qpos,q);wp.copy(d.qvel,v);d.qacc_warmstart.zero_();mjw.step(wm,d);projection.apply(custom.p.inv,shared=True)
        step()
        with wp.ScopedCapture() as cap:step()
        graphs[kind]=cap.graph;wp.capture_launch(cap.graph)
        np.testing.assert_array_equal(custom.error.numpy(),0)
        results[kind]=dict(qpos=d.qpos.numpy(),qvel=d.qvel.numpy());objects.append((custom,projection,motor,wm,d,q,v))
    delta={k:float(np.max(np.abs(results[a.kind][k]-results['baseline'][k]))) for k in ('qpos','qvel')}
    valid=delta['qpos']<1e-5 and delta['qvel']<2e-4
    report=dict(candidate=a.kind,valid=valid,differences=delta,**measure(graphs,rounds=6,replays=4),shared_bytes={kind:c.block_kernel.module.load('cuda:0',32).get_kernel_hooks(c.block_kernel).forward_smem_bytes for kind,(c,*_) in zip(graphs,objects)})
    for c,*_ in objects:np.testing.assert_array_equal(c.error.numpy(),0)
    path.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':main()

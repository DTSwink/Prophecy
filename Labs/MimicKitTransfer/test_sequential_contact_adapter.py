"""One-step end-to-end GPU test against the independent CPU equation solver."""
import os, sys, json, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np, mujoco, mujoco_warp as mjw, warp as wp
from probe_sequential_contacts import encode
from sequential_contact_adapter import SequentialContactAdapter, contacts
from mujoco_warp._src import types as mjtypes
from coupled_velocity_motors import CoupledVelocityMotors


def inactive_contact_test(custom,device):
    # Nearby candidates can carry stale nonnegative equation addresses. Only
    # the penetrating point inside the active margin may enter the solver.
    p=custom.p;p.ncontact.zero_();p.J.zero_();custom.error.zero_()
    arr=lambda x,dtype=float:wp.array(np.asarray(x),dtype=dtype,device=device)
    zero=lambda shape:wp.zeros(shape,dtype=int,device=device)
    wp.launch(contacts,dim=4,inputs=[p,custom.capacity,False,arr([4],int),arr([0,0,0,0],int),
        arr([3,3,3,1],int),arr([int(mjtypes.ContactType.CONSTRAINT)]*4,int),
        arr([-.001,.001,-.001,-.002]),arr([0,0,-.002,0]),arr([[0,1,2],[0,0,0],[0,0,0],[1,0,0]],int),
        arr(np.ones((custom.data.nworld,3,p.nv))),zero((1,3)),zero((1,3)),zero((1,1,3)),
        arr(np.ones((4,5)),mjtypes.vec5),custom.rowmap,custom.error,custom.contactids],device=device)
    np.testing.assert_array_equal(p.ncontact.numpy(),[2]+[0]*(custom.data.nworld-1))
    np.testing.assert_array_equal(custom.error.numpy(),0)
    np.testing.assert_array_equal(np.sort(p.friction.numpy()[0,:2]),[0,1])


def main():
    sys.path.insert(0,str(ROOT/'Labs/MimicKitUEFN'))
    from runtime import install_hook
    install_hook()
    out=probe.OUT/'causal_transfer'
    modelpath=out/'sequential_model.mjb'
    if not modelpath.exists():
        env,_=probe.setup();m=env._engine._solver.mj_model
        mujoco.mj_saveModel(m,str(modelpath),None)
    else: m=mujoco.MjModel.from_binary_path(str(modelpath))
    data=np.load(out/'reference.npz'); steps=[8,24,48,80,112,160]
    expected=np.array([np.load(out/f'sequential_{step}_1_expected.npy') for step in steps])
    m.opt.timestep=1/240
    m.opt.jacobian=mujoco.mjtJacobian.mjJAC_DENSE
    m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_LIMIT|mujoco.mjtDisableBit.mjDSBL_EQUALITY)
    m.opt.disableflags&=~int(mujoco.mjtDisableBit.mjDSBL_ACTUATION)
    report=[]
    for device in ['cpu','cuda:0']:
        with wp.ScopedDevice(device):
            wm=mjw.put_model(m); wd=mjw.put_data(m,mujoco.MjData(m),nworld=len(steps),nconmax=128,njmax=256)
            wm.uefn_compound_limits=types.SimpleNamespace(equalities=lambda m,d:None,limits=lambda m,d:None)
            motors=CoupledVelocityMotors(wm,wd,m); motors.install()
            custom=SequentialContactAdapter(wm,wd,m,motors); custom.install()
            inactive_contact_test(custom,device)
            initial=[encode(m,data['subin'][step]) for step in steps]
            q=np.array([v[0] for v in initial],dtype='float32'); v=np.array([v[1] for v in initial],dtype='float32')
            f=np.array([data['forces'][step] for step in steps],dtype='float32')
            ctrl=np.zeros((len(steps),m.nu),dtype='float32')
            ctrl[:,motors.ids]=np.array([data['actions'][step//8].clip(-2*np.pi,2*np.pi) for step in steps])
            wd.qpos.assign(q); wd.qvel.assign(v); wd.xfrc_applied.assign(f); wd.ctrl.assign(ctrl)
            try:
                mjw.step(wm,wd)
                np.testing.assert_array_equal(custom.error.numpy(),0)
                actual=wd.qvel.numpy(); error=float(np.max(np.abs(actual-expected)))
                np.testing.assert_allclose(actual,expected,atol=2e-4,rtol=2e-5)
                defect=float(motors.stats.numpy()[:,0].max()); assert defect<.002
                row=dict(device=device,max_velocity_error=error,motor_defect_nm=defect,contacts=custom.p.ncontact.numpy().tolist())
                if device.startswith('cuda'):
                    # Capture performs no advance, replay once from precisely the
                    # same state. Reset assignments deliberately stay outside graph.
                    wd.qpos.assign(q); wd.qvel.assign(v); wd.qacc_warmstart.zero_()
                    with wp.ScopedCapture(device=device) as capture: mjw.step(wm,wd)
                    wp.capture_launch(capture.graph)
                    np.testing.assert_array_equal(custom.error.numpy(),0)
                    np.testing.assert_allclose(wd.qvel.numpy(),expected,atol=2e-4,rtol=2e-5)
                    row['cuda_graph_same_state_verified']=True
                report.append(row); print(json.dumps(row),flush=True)
            finally: custom.restore(); motors.restore()
    (out/'sequential_adapter.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__': main()

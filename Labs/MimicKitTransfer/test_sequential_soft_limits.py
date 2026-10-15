"""Verify the diagnostic limit control against stock MJ and independent CPU PGS."""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import mujoco,mujoco_warp as mjw,warp as wp,numpy as np
from probe_sequential_contacts import encode
from coupled_velocity_motors import CoupledVelocityMotors
from sequential_contact_adapter import SequentialContactAdapter


def independent(p,w):
    # CPU float64 calculation, independent of Warp tile operations.
    inv=p.inv.numpy()[w].astype('float64');v=p.free.numpy()[w].astype('float64')
    dofs=p.dofs.numpy();gain=p.gains.numpy();cap=p.caps.numpy()*p.dt.numpy()[0]
    target=p.commands.numpy()[w];motor=np.zeros(len(dofs));compliance=1/(gain*p.dt.numpy()[0])
    count=p.nlimit.numpy()[w];J=p.limit_J.numpy()[w,:count].astype('float64')
    response=inv@J.T;diag=np.diag(J@response);soft=p.limit_compliance.numpy()[w,:count]
    desired=p.limit_target.numpy()[w,:count];bilateral=p.limit_bilateral.numpy()[w,:count]
    lam=np.zeros(count)
    for iteration in range(3000):
        before=v.copy()
        for a,dof in enumerate(dofs):
            value=np.clip(motor[a]+(target[a]-v[dof]-compliance[a]*motor[a])/(inv[dof,dof]+compliance[a]),-cap[a],cap[a])
            v+=inv[:,dof]*(value-motor[a]);motor[a]=value
        for a in range(count):
            value=lam[a]+(desired[a]-J[a]@v-soft[a]*lam[a])/(diag[a]+soft[a])
            if not bilateral[a]:value=max(0,value)
            v+=response[:,a]*(value-lam[a]);lam[a]=value
        if max(abs(v-before))<1e-10:break
    return v,iteration+1


def main():
    sys.path.insert(0,str(ROOT/'Labs/MimicKitUEFN'))
    from runtime import install_limits
    out=probe.OUT/'causal_transfer';m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'))
    m.opt.timestep=1/240;m.opt.jacobian=mujoco.mjtJacobian.mjJAC_DENSE
    m.opt.disableflags=int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
    metadata=json.loads((ROOT/'Labs/MimicKitUEFN/limits.json').read_text())
    data=np.load(out/'reference.npz');steps=[8,24,48,80,112,160];report=[]
    for device in ['cpu','cuda:0']:
        with wp.ScopedDevice(device):
            wm=mjw.put_model(m);wd=mjw.put_data(m,mujoco.MjData(m),nworld=len(steps),nconmax=128,njmax=256)
            install_limits(m,wm,metadata)
            motors=CoupledVelocityMotors(wm,wd,m);motors.install()
            initial=[encode(m,data['subin'][step]) for step in steps]
            q=np.array([s[0] for s in initial],dtype='float32');v=np.array([s[1] for s in initial],dtype='float32')
            ctrl=np.zeros((len(steps),m.nu),dtype='float32');ctrl[:,motors.ids]=data['actions'][np.array(steps)//8].clip(-2*np.pi,2*np.pi)
            wd.qpos.assign(q);wd.qvel.assign(v);wd.ctrl.assign(ctrl);wd.xfrc_applied.assign(data['forces'][steps])
            mjw.step(wm,wd);stock=wd.qvel.numpy().copy()
            custom=SequentialContactAdapter(wm,wd,m,motors,iterations=300,allow_soft_limits=True);custom.install()
            try:
                wd.qpos.assign(q);wd.qvel.assign(v);wd.qacc_warmstart.zero_()
                mjw.step(wm,wd);np.testing.assert_array_equal(custom.error.numpy(),0)
                actual=wd.qvel.numpy();reference=np.array([independent(custom.p,w)[0] for w in range(len(steps))])
                error=float(abs(actual-reference).max());stock_error=float(abs(actual-stock).max())
                np.testing.assert_allclose(actual,reference,atol=2e-4,rtol=2e-5)
                np.testing.assert_allclose(actual,stock,atol=2e-3,rtol=2e-4)
                row=dict(device=device,max_cpu_equation_error=error,max_stock_mj_error=stock_error,
                         limits=custom.p.nlimit.numpy().tolist(),motor_defect_nm=float(custom.p.stats.numpy().max()))
                report.append(row);print(json.dumps(row),flush=True)
            finally:custom.restore();motors.restore()
    (out/'sequential_soft_limits.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()

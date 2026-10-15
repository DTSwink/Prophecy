"""Same incoming state/action impact controls for the remaining phase-9 failure."""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,mujoco,mujoco_warp as mjw,warp as wp
import native_probe
from native_probe import Native,names
from probe_sequential_contacts import encode,decode
from coupled_velocity_motors import CoupledVelocityMotors
from sequential_contact_adapter import SequentialContactAdapter
sys.path.insert(0,str(ROOT/'Labs/MimicKitUEFN'))
from runtime import install_limits


def main(cases=None):
    out=probe.OUT/'causal_transfer'
    with np.load(out/'body_velocity_engine_cpu_phase0.5625.npz') as z:data={k:z[k] for k in z.files}
    steps=np.arange(8,32);states=data['subin'][steps]
    commands=data['actions'][steps//8,0].clip(-2*np.pi,2*np.pi)
    native_probe.fixture_path=probe.OUT/'point-contact/profile/fixture.exe'
    report=[];traces={}
    wp.init();wp.set_device('cuda:0')
    for case in (cases or ('full','no_contact','no_friction','sequential')):
        m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'))
        m.opt.timestep=1/240;m.opt.jacobian=mujoco.mjtJacobian.mjJAC_DENSE
        if case=='no_contact':m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
        if case=='no_friction':m.geom_condim[:]=1
        if case=='no_limits':m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_LIMIT)
        wm=mjw.put_model(m);wd=mjw.put_data(m,mujoco.MjData(m),nworld=len(steps),nconmax=150,njmax=450)
        install_limits(m,wm);motor=CoupledVelocityMotors(wm,wd,m);motor.install()
        custom=None
        if case in ('sequential','hard_limits','no_limits','block','manifolds','jolt_axes'):
            block=case in ('block','manifolds','jolt_axes')
            custom=SequentialContactAdapter(wm,wd,m,motor,iterations=100 if block else 1000,allow_soft_limits=True,relaxation=.5,
                hard_limit_control=case in ('hard_limits','block','manifolds','jolt_axes'),block_motors=block,
                manifolds=case in ('manifolds','jolt_axes'),jolt_limit_axes=case=='jolt_axes')
            custom.install()
        q,v=zip(*(encode(m,s) for s in states));ctrl=np.zeros((len(steps),m.nu),np.float32);ctrl[:,motor.ids]=commands
        wd.qpos.assign(np.asarray(q,np.float32));wd.qvel.assign(np.asarray(v,np.float32));wd.ctrl.assign(ctrl)
        wd.xfrc_applied.assign(data['forces'][steps].astype(np.float32))
        mjw.step(wm,wd)
        if custom:np.testing.assert_array_equal(custom.error.numpy(),0)
        qp=wd.qpos.numpy();qv=wd.qvel.numpy();pred=[]
        for i in range(len(steps)):
            d=mujoco.MjData(m);d.qpos[:]=qp[i];d.qvel[:]=qv[i];pred.append(decode(m,d))
        pred=np.array(pred);assert np.isfinite(pred).all()
        for key in list(os.environ):
            if key.startswith('TRANSFER_'):del os.environ[key]
        os.environ.update(TRANSFER_TRAINING_CONTACT='1',TRANSFER_FRICTIONLESS_SELF='1',TRANSFER_SUBSTEPS='1',
            TRANSFER_RIG_VELOCITY_STEPS='100',TRANSFER_RIG_POSITION_STEPS='20')
        if case=='no_contact':os.environ['TRANSFER_NO_CONTACT']='1'
        if case=='no_friction':os.environ['TRANSFER_FRICTION']='0'
        if case=='no_limits':os.environ['TRANSFER_NO_LIMITS']='1'
        native=[];impulses=[]
        for state,action in zip(states,commands):
            n=Native(state)
            try:r=n.request('step '+' '.join(map(str,action)))
            finally:n.close()
            native.append(r['bodies']);impulses.append(r['ground_vertical_impulse_ns'])
        native=np.array(native);error=np.linalg.norm(pred[:,:,10:]-native[:,:,10:],axis=-1)
        rows=[dict(step=int(steps[i]),max_angvel_error=float(error[i].max()),worst_body=names[int(error[i].argmax())],
            right_foot_error=float(error[i,names.index('right_foot')]),native_normal_impulse_ns=float(np.sum(impulses[i]))) for i in range(len(steps))]
        entry=dict(case=case,max_angvel_error=float(error.max()),motor_defect_nm=float(motor.stats.numpy()[:,0].max()),rows=rows)
        if case=='full':entry['reference_reproduction_max_velocity_error']=float(abs(pred[:,:,7:]-data['subout'][steps,:,7:]).max())
        report.append(entry);traces[case+'_mj']=pred;traces[case+'_jolt']=native
        print(json.dumps(entry),flush=True)
        if custom:custom.restore()
        motor.restore()
    label='phase9_impact'+('_jolt_axes' if cases==('manifolds','jolt_axes') else '_block' if cases==('block',) else '_limits' if cases else '')
    (out/(label+'.json')).write_text(json.dumps(report,indent=2))
    np.savez_compressed(out/(label+'.npz'),steps=steps,**traces)


if __name__=='__main__':main(('manifolds','jolt_axes') if '--jolt-axes' in sys.argv else ('block',) if '--block' in sys.argv else ('hard_limits','no_limits') if '--limits' in sys.argv else None)

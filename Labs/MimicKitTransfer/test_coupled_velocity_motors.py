"""Verify the existing solver's bounded rows implement the exact motor law."""
import json,types
from pathlib import Path
import numpy as np
import mujoco,mujoco_warp as mjw,warp as wp
from mujoco_warp._src import constraint
from coupled_velocity_motors import CoupledVelocityMotors

def main(device='cpu'):
    from runtime import install_hook
    install_hook()
    wp.init();wp.set_device(device);rows=[]
    for gain,cap,target,initial in [(100,400,6,0),(100,5,6,0),(40,90,-.06,2.912),(40,90,2.77,34.13),(40,90,0,-34.13)]:
        h=1/240
        xml=f'''<mujoco><option timestep="{h}" gravity="0 0 0" integrator="implicitfast" tolerance="1e-10"/>
        <worldbody><body pos="0 0 10"><freejoint/><inertial pos="0 0 0" mass="1" diaginertia="1 1 1"/>
        <body><joint name="j" type="ball"/><inertial pos="0 0 0" mass="1" diaginertia="1 1 1"/>
        </body></body></worldbody><actuator><velocity joint="j" gear="1 0 0 0 0 0" kv="{gain}" forcerange="{-cap} {cap}"/></actuator></mujoco>'''
        m=mujoco.MjModel.from_xml_string(xml);d=mujoco.MjData(m);d.ctrl[0]=target;d.qvel[6]=initial
        wm=mjw.put_model(m);wd=mjw.put_data(m,d,nworld=1,nconmax=8,njmax=16)
        ext=types.SimpleNamespace(equalities=lambda m,d:None,limits=lambda m,d:None)
        wm.uefn_compound_limits=ext
        if not getattr(constraint.make_constraint,'_uefn_compound_hook',False):wm.phat_extension=ext
        motor=CoupledVelocityMotors(wm,wd,m);motor.install()
        try:
            mjw.step(wm,wd)
            expected_torque=float(np.clip(gain*(target-initial)/(1+2*h*gain),-cap,cap))
            expected=initial+2*h*expected_torque
            actual=float(wd.qvel.numpy()[0,6]);tau=float(motor.torque.numpy()[0,0])
            np.testing.assert_allclose(actual,expected,atol=5e-6)
            np.testing.assert_allclose(tau,expected_torque,atol=1e-3)
            np.testing.assert_allclose(wd.actuator_force.numpy()[0,0],tau,atol=1e-6)
            assert float(motor.stats.numpy()[0,0])<1e-3
            graph_checked=False
            if device.startswith('cuda'):
                with wp.ScopedCapture() as capture:mjw.step(wm,wd)
                wp.capture_launch(capture.graph)
                next_expected=actual+2*h*float(np.clip(gain*(target-actual)/(1+2*h*gain),-cap,cap))
                np.testing.assert_allclose(float(wd.qvel.numpy()[0,6]),next_expected,atol=1e-5)
                graph_checked=True
            rows.append(dict(gain=gain,cap=cap,target=target,initial=initial,expected=expected,actual=actual,torque=tau,
                device=device,cuda_graph_replay_checked=graph_checked))
        finally:motor.restore()
    out=Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913/capped_integrator'
    out.mkdir(exist_ok=True);(out/('coupled_scalar_tests_gpu.json' if device.startswith('cuda') else 'coupled_scalar_tests.json')).write_text(json.dumps(rows,indent=2))
    print(json.dumps(rows,indent=2),flush=True)

def lifecycle():
    """Two owned models, out-of-order release, disabled motors and live dt."""
    from runtime import install_hook
    install_hook();wp.set_device('cpu')
    xml='''<mujoco><option timestep="0.0041666666667" gravity="0 0 0" integrator="implicitfast"/>
    <worldbody><body><freejoint/><inertial pos="0 0 0" mass="1" diaginertia="1 1 1"/>
    <body><joint name="j" type="ball"/><inertial pos="0 0 0" mass="1" diaginertia="1 1 1"/>
    </body></body></worldbody><actuator><velocity joint="j" gear="1 0 0 0 0 0" kv="100" forcerange="-400 400"/></actuator></mujoco>'''
    models=[]
    for _ in range(2):
        m=mujoco.MjModel.from_xml_string(xml);d=mujoco.MjData(m);d.ctrl[0]=6
        wm=mjw.put_model(m);wd=mjw.put_data(m,d,nworld=1,nconmax=8,njmax=16)
        wm.uefn_compound_limits=types.SimpleNamespace(equalities=lambda m,d:None,limits=lambda m,d:None)
        motor=CoupledVelocityMotors(wm,wd,m);motor.install();models.append((wm,wd,motor))
    try:
        a,ad,am=models[0];b,bd,bm=models[1]
        am.restore() # Must not detach the second model or retain the first.
        mjw.step(a,ad);mjw.step(b,bd)
        np.testing.assert_allclose(ad.qvel.numpy()[0,6],10/3,atol=1e-5)
        np.testing.assert_allclose(bd.qvel.numpy()[0,6],30/11,atol=1e-5)
        # Newton changes the live dt after construction; the rows must follow.
        bd.qvel.zero_();bd.qacc_warmstart.zero_();b.opt.timestep.fill_(1/120)
        mjw.step(b,bd)
        np.testing.assert_allclose(bd.qvel.numpy()[0,6],3.75,atol=1e-5)
        bd.qvel.zero_();bd.qacc_warmstart.zero_();b.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_ACTUATION)
        mjw.step(b,bd)
        np.testing.assert_allclose(bd.qvel.numpy(),0,atol=1e-6)
        np.testing.assert_allclose(bd.actuator_force.numpy(),0,atol=1e-6)
        print('LIFECYCLE passed: model isolation, release order, live dt, disabled actuation, torque reporting',flush=True)
    finally:
        for _,_,motor in models:motor.restore()

if __name__=='__main__':main()

"""Compare MuJoCo's implicit velocity actuator to the native motor response law.

Two unit-inertia bodies, coincident COM/joint anchors, no gravity/contact/limits.
The native unsaturated law is separately exercised by fixture --motor-test.
This diagnostic deliberately includes actuator saturation.
"""
import json
import numpy as np
import mujoco
import mujoco_warp as mjw
import warp as wp
from probe import OUT

def main():
    wp.set_device('cpu')
    rows=[];h=1/240
    for gain,cap,target in [(10,100,1),(100,400,6),(100,300,6),(100,200,6),(100,5,6),(10,1,6),(100,.1,6)]:
        xml=f'''<mujoco><option timestep="{h}" gravity="0 0 0" integrator="implicitfast"/>
        <worldbody><body pos="0 0 10"><freejoint/><inertial pos="0 0 0" mass="1" diaginertia="1 1 1"/>
        <body><joint name="j" type="ball"/><inertial pos="0 0 0" mass="1" diaginertia="1 1 1"/>
        </body></body></worldbody><actuator><velocity joint="j" gear="1 0 0 0 0 0" kv="{gain}" forcerange="{-cap} {cap}"/></actuator></mujoco>'''
        m=mujoco.MjModel.from_xml_string(xml);d=mujoco.MjData(m);d.ctrl[0]=target;mujoco.mj_step(m,d)
        initial=mujoco.MjData(m);initial.ctrl[0]=target
        wm=mjw.put_model(m);wd=mjw.put_data(m,initial,nworld=1,nconmax=8,njmax=8)
        mjw.step(wm,wd);warp_velocity=float(wd.qvel.numpy()[0,6])
        np.testing.assert_allclose(warp_velocity,d.qvel[6],rtol=2e-5,atol=1e-6)
        unclamped=2*gain*h*target/(1+2*gain*h)
        native_expected=min(unclamped,2*cap*h)
        row=dict(gain=gain,cap_nm=cap,target_rad_s=target,mujoco_relative_velocity=float(d.qvel[6]),
                 native_implicit_motor_expected=native_expected,mujoco_actuator_force_nm=float(d.actuator_force[0]),
                 mujoco_warp_relative_velocity=warp_velocity,
                 ratio=float(d.qvel[6])/native_expected)
        rows.append(row)
    (OUT/'motor-response-comparison.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
if __name__=='__main__':main()

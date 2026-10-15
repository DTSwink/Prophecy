"""CPU-only comparison of training's motor equation with native Jolt motors.

Single ball at its COM: isolate motor integration from contacts, limits, body
speed caps and connector translation. This is not a full-rig parity test.
"""
import csv
import json
import os
from pathlib import Path
import subprocess
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation as R
from joint_pd import motor_gains_for

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/Robotics'


def main():
    rig=json.loads((OUT/'rig.json').read_text())
    cases=[]
    for name in ('hand_r','neck_02','thigh_r'):
        body=next(b for b in rig['bodies'] if b['name']==name)
        kp,kd,cap=motor_gains_for(name)
        for relative,vector in ((0,[.08,0,0]),(0,[.5,-.3,.2]),(1,[.1,-.06,.04])):
            cases.append(dict(id=len(cases),name=name,relative=relative,inertia=np.array(body['jolt_inertia_kg_cm2'])*1e-4,
                              kp=kp,kd=kd,cap=cap/np.sqrt(3),vector=vector))
    source=OUT/'native-motor-cases.csv';destination=OUT/'native-motor-jolt.csv'
    with source.open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['case','relative','ix','iy','iz','kp','kd','cap','rx','ry','rz'])
        for c in cases:writer.writerow([c['id'],c['relative'],*c['inertia'],c['kp'],c['kd'],c['cap'],*c['vector']])
    process_env=dict(os.environ);process_env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+process_env['PATH']
    subprocess.run([str(OUT/'jolt_probe.exe'),'--motors',str(source),str(destination)],env=process_env,check=True)
    native=np.genfromtxt(destination,delimiter=',',names=True);reports=[]
    for c in cases:
        actuators=''.join(f'<general joint="joint" gear="{int(i==0)} {int(i==1)} {int(i==2)} 0 0 0" gainprm="1" biastype="affine" biasprm="0 0 {-c["kd"]}" forcelimited="true" forcerange="{-c["cap"]} {c["cap"]}"/>' for i in range(3))
        model=mujoco.MjModel.from_xml_string(f'''<mujoco><option timestep="{1/240}" gravity="0 0 0" integrator="implicitfast"/>
          <worldbody><body pos="0 0 1"><inertial pos="0 0 0" mass="1" diaginertia="{' '.join(map(str,c['inertia']))}"/>
          <joint name="joint" type="ball"/></body></worldbody><actuator>{actuators}</actuator></mujoco>''')
        data=mujoco.MjData(model);quats=[];velocities=[];saturated=0
        delta=R.from_rotvec(c['vector'])
        for tick in range(241):
            q=R.from_quat(data.qpos[[1,2,3,0]])
            quats.append(q.as_quat());velocities.append(data.qvel.copy())
            target=q*delta if c['relative'] else delta
            error=(q.inv()*target).as_rotvec();data.ctrl[:]=c['kp']*error
            saturated+=int(np.any(abs(data.ctrl-c['kd']*data.qvel)>c['cap']))
            data.xfrc_applied[1,3:]=q.apply(np.cross(data.qvel,c['inertia']*data.qvel))
            if tick<240:mujoco.mj_step(model,data)
        for mode in range(2):
            rows=native[(native['case']==c['id'])&(native['mode']==mode)]
            jq=np.column_stack([rows[x] for x in ('qx','qy','qz','qw')]);jw=np.column_stack([rows[x] for x in ('wx','wy','wz')])
            error=np.rad2deg((R.from_quat(jq).inv()*R.from_quat(quats)).magnitude())
            velocity=np.linalg.norm(jw-np.asarray(velocities),axis=1)
            reports.append({'body':c['name'],'relative':bool(c['relative']),'target_rotvec':c['vector'],
                'native_mode':'position' if mode==0 else 'damped_velocity_target',
                'max_rotation_error_deg':float(error.max()),'first_step_rotation_error_deg':float(error[1]),
                'max_velocity_error_rad_s':float(velocity.max()),'final_rotation_error_deg':float(error[-1]),
                'sampled_saturated_steps':saturated})
    result={'scope':'Unconstrained COM ball joints; production body inertias and gains; no gyro, gravity, contacts or production speed cap.',
            'physics_hz':240,'seconds':1,'cases':reports,'full_rig_parity_verified':False}
    (OUT/'native-motor-calibration.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()

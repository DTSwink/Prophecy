"""Replay captured native MuJoCo state/force without policy or optimization."""
import sys,json
from pathlib import Path
import numpy as np
import mujoco

base=Path(sys.argv[1]);a=np.load(base.with_suffix('.npz'));reports=[]
for integrator,freq,zero,free in [(3,240,False,False),(3,480,False,False),(1,240,False,False),(3,240,True,False),(1,240,True,False),(3,240,True,True),(1,240,True,True)]:
    m=mujoco.MjModel.from_binary_path(str(base.with_suffix('.mjb')))
    m.opt.integrator=integrator;m.opt.timestep=1/freq
    if free:m.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_CONSTRAINT)|int(mujoco.mjtDisableBit.mjDSBL_GRAVITY)
    d=mujoco.MjData(m);d.qpos[:]=a['0_mj_qpos'];d.qvel[:]=a['0_mj_qvel']
    mujoco.mj_forward(m,d);mujoco.mj_energyPos(m,d);mujoco.mj_energyVel(m,d)
    initial_energy=d.energy.copy().tolist()
    rows=[]
    for k in range(6):
        force=a[f'{k}_mj_applied'];d.qfrc_applied[:]=0 if zero else force
        for _ in range(freq//30):mujoco.mj_step(m,d)
        mujoco.mj_forward(m,d)
        mujoco.mj_energyPos(m,d);mujoco.mj_energyVel(m,d)
        row=dict(frame=k,max_velocity=float(np.abs(d.qvel).max()),energy=d.energy.tolist(),
                 warnings=d.warning.number.tolist(),finite=bool(np.isfinite(d.qvel).all()),max_force=float(np.abs(force).max()))
        if k<5:
            delta=np.zeros(m.nv);mujoco.mj_differentiatePos(m,delta,1,d.qpos,a[f'{k+1}_mj_qpos'].astype(np.float64))
            row['gpu_pose_error']=float(np.max(np.abs(delta)))
            row['gpu_qvel_error']=float(np.max(np.abs(d.qvel-a[f'{k+1}_mj_qvel'])))
        rows.append(row)
    reports.append(dict(integrator=integrator,frequency=freq,zero_force=zero,no_contacts_limits_gravity=free,initial_energy=initial_energy,steps=rows))
out=base.with_name('pose-torque-cpu.json');out.write_text(json.dumps(reports,indent=2));print(json.dumps(reports))

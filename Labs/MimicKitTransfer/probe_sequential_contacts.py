"""Diagnostic generalized-coordinate Jolt contact law, never installed in training.

Uses the same articulated mass matrix as MJ, but Jolt's sequential motor,
friction-disc and unilateral-normal impulse equations. This separates the
contact law from maximal-vs-minimal articulation and contact geometry.
"""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT'] = str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import json, numpy as np, mujoco
from scipy.spatial.transform import Rotation as R
import native_probe
from native_probe import Native, names, parents, local


def encode(m, state):
    bodies = [next(i for i in range(1, m.nbody) if m.body(i).name.endswith(n)) for n in names]
    q = m.qpos0.copy(); v = np.zeros(m.nv); rot = R.from_quat(state[:, 3:7])
    q[:3] = state[0, :3]; q[3:7] = np.roll(state[0, 3:7], 1)
    v[:3] = state[0, 7:10] - np.cross(state[0, 10:13], rot[0].apply(m.body_ipos[bodies[0]]))
    v[3:6] = rot[0].inv().apply(state[0, 10:13])
    for i in range(1, len(bodies)):
        j = m.body_jntadr[bodies[i]]; qa = m.jnt_qposadr[j]; va = m.jnt_dofadr[j]
        rel = local[i].inv()*rot[parents[i]].inv()*rot[i]
        vel = rot[i].inv().apply(state[i, 10:13] - state[parents[i], 10:13])
        if m.jnt_type[j] == 1:
            q[qa:qa+4] = np.roll(rel.as_quat(), 1); v[va:va+3] = vel
        else:
            q[qa] = rel.as_rotvec()[2]; v[va] = vel[2]
    return q, v


def decode(m, d):
    mujoco.mj_kinematics(m, d); mujoco.mj_comPos(m, d)
    rows = []
    for name in names:
        b = next(i for i in range(1, m.nbody) if m.body(i).name.endswith(name))
        jp = np.zeros((3, m.nv)); jr = jp.copy()
        mujoco.mj_jacBodyCom(m, d, jp, jr, b)
        rows.append(np.r_[d.xpos[b], np.roll(d.xquat[b], -1), jp@d.qvel, jr@d.qvel])
    return np.array(rows)


def solve(m, d, motor, command, iterations, friction, capture=None):
    dt = m.opt.timestep
    mass = np.zeros((m.nv, m.nv)); mujoco.mj_fullM(m, mass, d.qM)
    inv = np.linalg.inv(mass)
    velocity = d.qvel + dt*d.qacc_smooth
    free = velocity.copy()
    dofs = motor.dof_ids; gain = motor.gains.numpy(); caps = motor.upper.numpy()*dt
    motor_impulse = np.zeros(len(dofs))
    contacts = []
    for c in d.contact:
        if c.dist > 0: continue
        j = np.zeros((3, m.nv))
        for sign, geom in [(-1, c.geom[0]), (1, c.geom[1])]:
            jp = np.zeros_like(j); jr = np.zeros_like(j)
            mujoco.mj_jac(m, d, jp, jr, c.pos, m.geom_bodyid[geom])
            j += sign * c.frame.reshape(3, 3) @ jp
        contacts.append((j, inv@j.T, np.diag(j@inv@j.T), np.zeros(3)))
    if capture is not None:
        np.savez_compressed(capture, inv=inv, free=free, dofs=dofs, gain=gain, caps=caps,
                            command=command, dt=dt, friction=friction,
                            J=np.array([c[0] for c in contacts]).reshape(-1,3,m.nv))
    previous = velocity.copy()
    residual = 0.
    for it in range(iterations):
        for a, dof in enumerate(dofs):
            compliance = 1/(dt*gain[a])
            new = np.clip(motor_impulse[a]+(command[a]-velocity[dof]-compliance*motor_impulse[a])/(inv[dof,dof]+compliance), -caps[a], caps[a])
            velocity += inv[:,dof]*(new-motor_impulse[a]); motor_impulse[a] = new
        for j, response, diagonal, lam in contacts:
            tangent = lam[1:]-(j@velocity)[1:]/diagonal[1:]
            length = np.linalg.norm(tangent); bound = friction*lam[0]
            if length > bound: tangent *= bound/max(length, 1e-30)
            velocity += response[:,1:]@(tangent-lam[1:]); lam[1:] = tangent
            normal = max(0., lam[0]-(j[0]@velocity)/diagonal[0])
            velocity += response[:,0]*(normal-lam[0]); lam[0] = normal
        residual = float(np.max(np.abs(velocity-previous))); previous[:] = velocity
        if residual < 1e-10: break
    return velocity, dict(normal_impulse=float(sum(c[3][0] for c in contacts)),
                         iterations=it+1, residual=residual, contacts=len(contacts),
                         motor_defect=float(np.max(np.abs(motor_impulse/dt-np.clip(gain*(command-velocity[dofs]),-caps/dt,caps/dt)))))


def main(point_contact=False):
    from coupled_velocity_motors import CoupledVelocityMotors
    env, _ = probe.setup(); s = env._engine._solver; m = s.mj_model
    motor = CoupledVelocityMotors(s.mjw_model, s.mjw_data, m)
    native_probe.fixture_path = probe.OUT/('point-contact/fixture.exe' if point_contact else 'contact-observation.exe')
    data = np.load(probe.OUT/'causal_transfer/reference.npz')
    m.opt.timestep = 1/240
    m.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_ACTUATION | mujoco.mjtDisableBit.mjDSBL_LIMIT)
    reports = []
    for step in [8,24,48,80,112,160]:
        state = data['subin'][step]; command = data['actions'][step//8].clip(-2*np.pi,2*np.pi)
        for friction in [0., 1.]:
            for k in list(os.environ):
                if k.startswith('TRANSFER_'): del os.environ[k]
            os.environ.update(TRANSFER_SUBSTEPS='1', TRANSFER_NO_LIMITS='1', TRANSFER_HIGH_ITERATIONS='1',
                TRANSFER_NO_SPECULATIVE='1', TRANSFER_FRICTION=str(friction), TRANSFER_RESTITUTION='0')
            if point_contact: os.environ.pop('TRANSFER_NO_SPECULATIVE')
            native = Native(state)
            try: result = native.request('step '+' '.join(map(str,command)))
            finally: native.close()
            actual = np.array(result['bodies'])
            for it in [10,100,1000]:
                d = mujoco.MjData(m); d.qpos[:],d.qvel[:] = encode(m,state)
                d.xfrc_applied[:] = data['forces'][step]
                mujoco.mj_forward(m,d)
                np.testing.assert_allclose(decode(m,d),state,atol=2e-5)
                prefix=probe.OUT/'causal_transfer'/f'sequential_{step}_{int(friction)}'
                d.qvel[:], stats = solve(m,d,motor,command,it,friction, str(prefix)+'.npz' if it==1000 else None)
                if it==1000: np.save(str(prefix)+'_expected.npy', d.qvel)
                mujoco.mj_integratePos(m,d.qpos,d.qvel,m.opt.timestep)
                predicted=decode(m,d)
                row=dict(step=step,friction=friction,requested_iterations=it,**stats,
                    native_normal_impulse=sum(result['ground_vertical_impulse_ns']),
                    angvel_error=float(np.linalg.norm(predicted[:,10:]-actual[:,10:],axis=1).max()),
                    velocity_error=float(np.linalg.norm(predicted[:,7:10]-actual[:,7:10],axis=1).max()),
                    angle_error_deg=float(np.rad2deg((R.from_quat(predicted[:,3:7])*R.from_quat(actual[:,3:7]).inv()).magnitude()).max()))
                reports.append(row); print(json.dumps(row),flush=True)
    name='sequential_point_contacts.json' if point_contact else 'sequential_contacts.json'
    (probe.OUT/'causal_transfer'/name).write_text(json.dumps(reports,indent=2),encoding='utf-8')


if __name__ == '__main__':
    import sys
    main('--point-contact' in sys.argv)

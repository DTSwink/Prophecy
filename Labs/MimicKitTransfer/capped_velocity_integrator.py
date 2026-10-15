"""Isolated implicit bounded-velocity-motor experiment; never installed globally.

Solves M dv = h (external + motor(v_next) - D dv), where each motor is
clip(k*(target-v_next), lo, hi). The existing constraint solve supplies external
forces, just as for stock implicitfast. This DOES NOT jointly re-solve contacts.
All runtime work is Warp/device resident. Model validation is setup-only.
"""
import numpy as np
import warp as wp
from mujoco_warp._src import forward

wp.set_module_options({'enable_backward': False})

@wp.kernel
def unpack_mass(packed: wp.array3d(dtype=float), rows: wp.array(dtype=int),
                cols: wp.array(dtype=int), dense: wp.array3d(dtype=float)):
    w,k=wp.tid()
    i=rows[k];j=cols[k]
    dense[w,i,j]=packed[w,0,k]
    dense[w,j,i]=packed[w,0,k]

def inverse_kernel(nv):
    @wp.kernel(module='unique', enable_backward=False)
    def invert(mass: wp.array3d(dtype=float), damping: wp.array2d(dtype=float),
               dt: float, eye: wp.array2d(dtype=float), inv: wp.array3d(dtype=float)):
        w = wp.tid()
        a = wp.tile_load(mass[w], shape=(nv, nv))
        damp = wp.tile_load(damping[w % damping.shape[0]], shape=(nv,))
        a = wp.tile_diag_add(a, damp * dt)
        chol = wp.tile_cholesky(a)
        identity = wp.tile_load(eye, shape=(nv, nv))
        result = wp.tile_cholesky_solve(chol, identity)
        wp.tile_store(inv[w], result)
    return invert

@wp.kernel
def solve(nv: int, nu: int, dt: float, iterations: int, tolerance: float,
          inv: wp.array3d(dtype=float), oldv: wp.array2d(dtype=float),
          total_force: wp.array2d(dtype=float), oldmotor: wp.array2d(dtype=float),
          ctrl: wp.array2d(dtype=float), dofs: wp.array(dtype=int), acts: wp.array(dtype=int),
          gains: wp.array(dtype=float), lower: wp.array(dtype=float), upper: wp.array(dtype=float),
          velocity: wp.array2d(dtype=float), torque: wp.array2d(dtype=float),
          accel: wp.array2d(dtype=float), stats: wp.array2d(dtype=float)):
    w = wp.tid()
    # Zero impulse initial guess. Coordinates are exact minimizers of the
    # positive-definite motor impulse QP, including all articulated coupling.
    for i in range(nv):
        value = oldv[w, i]
        for j in range(nv):
            value += dt * inv[w, i, j] * (total_force[w, j] - oldmotor[w, j])
        velocity[w, i] = value
    for a in range(nu):
        torque[w, a] = 0.0
    defect = float(0.0)
    used = int(0)
    for sweep in range(iterations):
        for a in range(nu):
            j = dofs[a]
            old = torque[w, a]
            residual = ctrl[w, acts[a]] - velocity[w, j] - old / gains[a]
            new = wp.clamp(old + residual / (dt * inv[w, j, j] + 1.0 / gains[a]), lower[a], upper[a])
            torque[w, a] = new
            for i in range(nv):
                velocity[w, i] += dt * inv[w, i, j] * (new - old)
        defect = float(0.0)
        for a in range(nu):
            expected = wp.clamp(gains[a] * (ctrl[w, acts[a]] - velocity[w, dofs[a]]), lower[a], upper[a])
            defect = wp.max(defect, wp.abs(torque[w, a] - expected))
        used = sweep + 1
        if defect <= tolerance:
            break
    for i in range(nv):
        accel[w, i] = (velocity[w, i] - oldv[w, i]) / dt
    stats[w, 0] = defect
    stats[w, 1] = float(used)

class CappedVelocityIntegrator:
    def __init__(self, model, data, cpu_model, iterations=256, tolerance=1e-3):
        m = cpu_model
        assert m.ntendon == 0 and np.all(m.dof_damping >= 0)
        assert np.all(m.dof_frictionloss == 0)
        self.nv = m.nv
        self.dt = float(model.opt.timestep.numpy()[0])
        ids=[]; dofs=[]; gains=[]; bounds=[];direct=[]
        for a in range(m.nu):
            gain = m.actuator_gainprm[a]
            bias = m.actuator_biasprm[a]
            if np.all(gain == 0) and np.all(bias == 0):
                continue
            if gain[0]==1 and np.all(gain[1:]==0) and np.all(bias==0):
                direct.append(a)
                continue
            assert m.actuator_dyntype[a] == 0 and m.actuator_gaintype[a] == 0
            assert m.actuator_biastype[a] == 1 and gain[0] > 0
            np.testing.assert_allclose(bias[:3], [0, 0, -gain[0]], atol=1e-8)
            assert m.actuator_trntype[a] == 0
            gear = m.actuator_gear[a]
            assert np.count_nonzero(gear) == 1 and np.max(gear) == 1
            joint = m.actuator_trnid[a, 0]
            dof = m.jnt_dofadr[joint] + int(np.argmax(gear[:3]))
            assert m.jnt_type[joint] in (1, 3)
            bound=m.actuator_forcerange[a].copy() if m.actuator_forcelimited[a] else np.array([-np.inf,np.inf])
            if m.jnt_actfrclimited[joint]:
                assert m.jnt_type[joint]==3, 'Non-scalar joint-level force cap needs separate treatment'
                bound[0]=max(bound[0],m.jnt_actfrcrange[joint,0])
                bound[1]=min(bound[1],m.jnt_actfrcrange[joint,1])
            assert np.isfinite(bound).all(), 'Prototype requires an existing finite actuator or scalar joint cap'
            ids.append(a); dofs.append(dof); gains.append(gain[0]); bounds.append(bound)
        assert len(set(dofs)) == len(dofs)
        self.ids = np.array(ids); self.dof_ids = np.array(dofs)
        self.direct_ids=np.array(direct,dtype=int)
        device=data.qvel.device
        arr=lambda v,dtype:wp.array(v,dtype=dtype,device=device)
        self.dofs=arr(dofs,int); self.acts=arr(ids,int);self.gains=arr(gains,float)
        self.lower=arr(np.array(bounds)[:,0],float);self.upper=arr(np.array(bounds)[:,1],float)
        self.eye=arr(np.eye(m.nv),float)
        self.inverse=wp.empty((data.nworld,m.nv,m.nv),dtype=float,device=device)
        self.dense_mass=wp.zeros_like(self.inverse) if model.is_sparse else None
        self.velocity=wp.empty_like(data.qvel);self.accel=wp.empty_like(data.qvel)
        self.torque=wp.empty((data.nworld,len(ids)),dtype=float,device=device)
        self.stats=wp.zeros((data.nworld,3),dtype=float,device=device)
        self.invert=inverse_kernel(m.nv)
        self.iterations=iterations;self.tolerance=tolerance
        self.original=None

    def integrate(self,m,d):
        # No transfers, host convergence checks or allocations during stepping.
        mass=d.qM
        if self.dense_mass is not None:
            wp.launch(unpack_mass,dim=(d.nworld,m.qM_fullm_i.size),
                inputs=[d.qM,m.qM_fullm_i,m.qM_fullm_j,self.dense_mass])
            mass=self.dense_mass
        wp.launch_tiled(self.invert, dim=d.nworld,
            inputs=[mass,m.dof_damping,self.dt,self.eye,self.inverse],block_dim=64)
        wp.launch(solve,dim=d.nworld,inputs=[self.nv,len(self.ids),self.dt,self.iterations,self.tolerance,
            self.inverse,d.qvel,d.efc.Ma,d.qfrc_actuator,d.ctrl,self.dofs,self.acts,self.gains,
            self.lower,self.upper,self.velocity,self.torque,self.accel,self.stats])
        forward._advance(m,d,self.accel)

    def install(self):
        assert self.original is None
        self.original=forward.implicit
        forward.implicit=self.integrate

    def restore(self):
        if self.original is not None:
            forward.implicit=self.original;self.original=None

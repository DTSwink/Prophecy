"""Body COM velocities for the UEFN Newton/MuJoCo coordinate convention.

Newton stores root COM velocity in world axes and copies MJ ball-joint angular
velocities in child axes. Its generic FK assumes parent axes for the latter.
Reconstruct velocities without changing joint state, transforms or dynamics.
"""
import numpy as np
import warp as wp


@wp.kernel(enable_backward=False)
def reconstruct(q: wp.array2d(dtype=wp.transform), qd: wp.array2d(dtype=float),
                parents: wp.array(dtype=int), dofs: wp.array(dtype=int), kinds: wp.array(dtype=int),
                axes: wp.array(dtype=wp.vec3), com: wp.array(dtype=wp.vec3), anchors: wp.array(dtype=wp.vec3),
                output: wp.array2d(dtype=wp.spatial_vector)):
    w = wp.tid()
    output[w, 0] = wp.spatial_vector(wp.vec3(qd[w, 0], qd[w, 1], qd[w, 2]),
                                    wp.vec3(qd[w, 3], qd[w, 4], qd[w, 5]))
    for b in range(1, parents.shape[0]):
        parent = parents[b]
        pose = q[w, b]
        dof = dofs[b]
        local = axes[b] * qd[w, dof]
        if kinds[b] == 1:
            local = wp.vec3(qd[w, dof], qd[w, dof+1], qd[w, dof+2])
        parent_omega = wp.spatial_bottom(output[w, parent])
        omega = parent_omega + wp.quat_rotate(wp.transform_get_rotation(pose), local)
        anchor = wp.transform_point(pose, anchors[b])
        center = wp.transform_point(pose, com[b])
        parent_center = wp.transform_point(q[w, parent], com[parent])
        velocity = (wp.spatial_top(output[w, parent])
                    + wp.cross(parent_omega, anchor-parent_center) + wp.cross(omega, center-anchor))
        output[w, b] = wp.spatial_vector(velocity, omega)


class BodyVelocity:
    def __init__(self, solver):
        model = solver.mj_model
        newton = solver.model
        self.worlds = solver.mjw_data.nworld
        self.bodies = model.nbody - 1
        # This adapter is intentionally restricted to the owned single character.
        assert self.bodies == 15 and newton.body_count == self.worlds*self.bodies
        ids = np.arange(1, model.nbody)
        assert np.all(model.body_jntnum[ids] == 1)
        joints = model.body_jntadr[ids]
        kinds = model.jnt_type[joints]
        assert kinds[0] == 0 and set(kinds[1:]).issubset({1, 3})
        parents = model.body_parentid[ids] - 1
        assert np.all(parents[1:] < np.arange(1, self.bodies))
        self.nv = model.nv
        np.testing.assert_array_equal(newton.joint_qd_start.numpy()[:self.bodies], model.jnt_dofadr[joints])
        np.testing.assert_allclose(newton.body_com.numpy()[:self.bodies], model.body_ipos[ids], atol=2e-6)
        self.args = [wp.array(values, dtype=dtype, device=newton.device) for values, dtype in (
            (parents, int), (model.jnt_dofadr[joints], int), (kinds, int),
            (model.jnt_axis[joints], wp.vec3), (model.body_ipos[ids], wp.vec3),
            (model.jnt_pos[joints], wp.vec3))]
        self.device = newton.device

    def update(self, state):
        # Read current Newton state, not the MJ cache: resets are synchronized
        # into MJ only inside SolverMuJoCo.step. This also supports partial resets.
        wp.launch(reconstruct, dim=self.worlds,
                  inputs=[state.body_q.reshape((self.worlds, self.bodies)),
                          state.joint_qd.reshape((self.worlds, self.nv)), *self.args],
                  outputs=[state.body_qd.reshape((self.worlds, self.bodies))], device=self.device)

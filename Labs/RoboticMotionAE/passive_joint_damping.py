"""Implicit internal viscous damping, solved together with contacts and motors.

M_eff = M + dt D; v_free_eff = solve(M_eff, M v_free).
Only rotational joint DOFs have D>0, so there is no world/root drag or spring.
Motor torque caps remain caps on active motors, independently of passive torque.
"""
import numpy as np
import warp as wp

COEFFICIENTS = dict(torso=20., head=5., right_upper_arm=20.,
                    right_lower_arm=20., right_hand=20., left_upper_arm=20.,
                    left_lower_arm=20., left_hand=20.)


def coefficients(model):
    values = np.zeros(model.nv, dtype=np.float32)
    found = {}
    for body, value in COEFFICIENTS.items():
        ids = [i for i in range(1, model.nbody) if model.body(i).name.endswith(body)]
        assert len(ids) == 1, (body, ids)
        b = ids[0]
        dofs = []
        for j in range(model.body_jntadr[b], model.body_jntadr[b]+model.body_jntnum[b]):
            # MuJoCo: BALL=1 (three relative angular DOFs), HINGE=3 (one).
            kind = int(model.jnt_type[j])
            assert kind in (1, 3), (body, kind)
            first = int(model.jnt_dofadr[j]); count = 3 if kind == 1 else 1
            values[first:first+count] = value
            dofs.extend(range(first, first+count))
        assert dofs and min(dofs) >= 6
        found[body] = dict(coefficient_nm_s_per_rad=value, dofs=dofs)
    assert not values[:6].any()
    return values, dict(law='tau=-c*relative_joint_angular_velocity',
                       integration='implicit coupled motor/contact solve', bodies=found,
                       root_drag=False, leg_damping=False, active_motor_caps_unchanged=True)


def make_prepare(nv):
    @wp.kernel(module='unique', enable_backward=False)
    def prepare(mass: wp.array3d(dtype=float), damping: wp.array(dtype=float),
                dt: wp.array(dtype=float), original_free: wp.array2d(dtype=float),
                effective_mass: wp.array3d(dtype=float), inverse: wp.array3d(dtype=float),
                free: wp.array2d(dtype=float), identity: wp.array2d(dtype=float)):
        w = wp.tid()
        m = wp.tile_load(mass[w], shape=(nv, nv))
        v = wp.tile_reshape(wp.tile_load(original_free[w], shape=(nv,)), shape=(nv, 1))
        rhs = wp.tile_matmul(m, v)
        for j in range(nv):
            m[j, j] = wp.tile_extract(m, j, j)+dt[0]*damping[j]
        wp.tile_store(effective_mass[w], m)
        wp.tile_cholesky_inplace(m)
        eye = wp.tile_load(identity, shape=(nv, nv))
        wp.tile_store(inverse[w], wp.tile_cholesky_solve(m, eye))
        wp.tile_store(free[w], wp.tile_reshape(wp.tile_cholesky_solve(m, rhs), shape=(nv,)))
    return prepare

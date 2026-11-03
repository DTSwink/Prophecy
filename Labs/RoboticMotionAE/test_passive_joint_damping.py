"""GPU kernel vs independent NumPy implicit dynamics, then actual rig checks."""
import json
from pathlib import Path
import numpy as np
import warp as wp


def check_damping(env,out):
    import passive_joint_damping as module
    adapter=env._engine.transfer_contact
    assert '/disabled-preflight/package/' in module.__file__,module.__file__
    metadata=adapter.passive_damping_metadata
    assert len(metadata['bodies'])==8 and not metadata['root_drag']
    coefficients=adapter.passive_damping.numpy()
    assert not coefficients[:6].any()
    model=env._engine._solver.mj_model
    for b in range(1,model.nbody):
        if any(s in model.body(b).name for s in ('thigh','shin','foot')):
            for j in range(model.body_jntadr[b],model.body_jntadr[b]+model.body_jntnum[b]):
                first=model.jnt_dofadr[j];count=3 if model.jnt_type[j]==1 else 1
                assert not coefficients[first:first+count].any()
    # Production-size kernel, random SPD inertia couples root and joint DOFs.
    n=8;nv=model.nv;rng=np.random.default_rng(714)
    a=rng.normal(size=(n,nv,nv));mass=(a@a.transpose(0,2,1)+np.eye(nv)*2).astype(np.float32)
    velocity=rng.normal(size=(n,nv)).astype(np.float32)
    eye=np.eye(nv,dtype=np.float32);dt=1/240
    M=wp.array(mass,device='cuda:0');V=wp.array(velocity,device='cuda:0')
    E=wp.zeros((n,nv,nv),device='cuda:0');I=wp.zeros_like(E);F=wp.zeros((n,nv),device='cuda:0')
    kernel=module.make_prepare(nv);errors=[]
    for damping in (np.zeros(nv,dtype=np.float32),coefficients):
        wp.launch_tiled(kernel,dim=n,inputs=[M,wp.array(damping,device='cuda:0'),
            wp.array(np.array([dt],dtype=np.float32),device='cuda:0'),V,E,I,F,
            wp.array(eye,device='cuda:0')],block_dim=32,device='cuda:0')
        effective=mass.astype(float)+dt*np.diag(damping)
        expected=np.linalg.solve(effective,(mass@velocity[...,None]).astype(float))[...,0]
        actual=F.numpy();error=float(np.max(np.abs(actual-expected)));errors.append(error)
        np.testing.assert_allclose(actual,expected,atol=2e-5,rtol=2e-5)
        np.testing.assert_allclose(I.numpy(),np.linalg.inv(effective),atol=2e-6,rtol=2e-5)
        np.testing.assert_allclose(E.numpy(),effective,atol=1e-5,rtol=1e-6)
        before=np.einsum('bi,bij,bj->b',velocity,mass,velocity)/2
        after=np.einsum('bi,bij,bj->b',actual,mass,actual)/2
        assert np.all(after<=before+1e-3),(before,after)
        # No external/root impulse, despite coupled generalized inertia.
        momentum=np.einsum('bij,bj->bi',mass.astype(float),actual-velocity)
        np.testing.assert_allclose(momentum[:,:6],0,atol=2e-4)
    # Uncoupled inertia has exact v'=v/(1+dt*c/I), no over-damping sign flip.
    diagonal=np.broadcast_to(eye,(n,nv,nv)).copy()
    wp.copy(M,wp.array(diagonal,device='cuda:0'))
    wp.launch_tiled(kernel,dim=n,inputs=[M,adapter.passive_damping,adapter.p.dt,V,E,I,F,
        adapter.identity],block_dim=32,device='cuda:0')
    np.testing.assert_allclose(F.numpy(),velocity/(1+dt*coefficients),atol=1e-6,rtol=1e-6)
    np.testing.assert_array_equal(F.numpy()[:,:6],velocity[:,:6])
    report=dict(passed=True,maximum_velocity_error=max(errors),metadata=metadata,
                no_root_drag=True,legs_undamped=True,energy_dissipative=True,
                kernel_source=module.__file__,zero_damping_equivalence=True)
    (out/'damping-check.json').write_text(json.dumps(report,indent=2))
    print('PASS passive damping analytical checks',max(errors),flush=True)

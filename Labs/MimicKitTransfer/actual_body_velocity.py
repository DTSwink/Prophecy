"""Exact COM velocities from MJ joint velocities and current body transforms.

MJ ball qvel is expressed in the moving child frame. Newton's compound-joint FK
uses parent-frame components instead. This diagnostic kernel uses the actual MJ
convention without changing qvel, body transforms, observation layout or dynamics.
"""
import warp as wp


@wp.kernel(enable_backward=False)
def body_velocity(q: wp.array2d(dtype=wp.transform), qvel: wp.array2d(dtype=float),
                  parents: wp.array(dtype=int), dofs: wp.array(dtype=int), kinds: wp.array(dtype=int),
                  axes: wp.array(dtype=wp.vec3), com: wp.array(dtype=wp.vec3), anchors: wp.array(dtype=wp.vec3),
                  output: wp.array2d(dtype=wp.spatial_vector)):
    w=wp.tid()
    root=q[w,0]; rot=wp.transform_get_rotation(root)
    angular=wp.quat_rotate(rot,wp.vec3(qvel[w,3],qvel[w,4],qvel[w,5]))
    linear=wp.vec3(qvel[w,0],qvel[w,1],qvel[w,2])+wp.cross(angular,wp.quat_rotate(rot,com[0]))
    output[w,0]=wp.spatial_vector(linear,angular)
    for b in range(1,parents.shape[0]):
        parent=parents[b]; pose=q[w,b]; rotation=wp.transform_get_rotation(pose); dof=dofs[b]
        local=axes[b]*qvel[w,dof]
        if kinds[b]==1: local=wp.vec3(qvel[w,dof],qvel[w,dof+1],qvel[w,dof+2])
        parent_omega=wp.spatial_bottom(output[w,parent])
        omega=parent_omega+wp.quat_rotate(rotation,local)
        anchor=wp.transform_point(pose,anchors[b])
        center=wp.transform_point(pose,com[b]); parent_center=wp.transform_point(q[w,parent],com[parent])
        velocity=wp.spatial_top(output[w,parent])+wp.cross(parent_omega,anchor-parent_center)+wp.cross(omega,center-anchor)
        output[w,b]=wp.spatial_vector(velocity,omega)


def main():
    import json,time,numpy as np
    from pathlib import Path
    from probe_sequential_contacts import encode,probe,names
    import mujoco
    out=probe.OUT/'causal_transfer'; m=mujoco.MjModel.from_binary_path(str(out/'sequential_model.mjb'))
    states=np.load(out/'reference.npz')['subin']
    bids=[next(i for i in range(1,m.nbody) if m.body(i).name.endswith(name)) for name in names]
    joints=[m.body_jntadr[b] for b in bids]
    parents=[-1]+[bids.index(m.body_parentid[b]) for b in bids[1:]]
    dofs=m.jnt_dofadr[joints]; kinds=m.jnt_type[joints]; axes=m.jnt_axis[joints]
    assert kinds[0]==0 and set(kinds[1:]).issubset({1,3})
    velocities=np.array([encode(m,s)[1] for s in states],dtype='float32')
    reports=[]
    for device in ['cpu','cuda:0']:
        with wp.ScopedDevice(device):
            arg=[wp.array(states[:,:,:7],dtype=wp.transform),wp.array(velocities),wp.array(parents,dtype=int),
                 wp.array(dofs,dtype=int),wp.array(kinds,dtype=int),wp.array(axes,dtype=wp.vec3),
                 wp.array(m.body_ipos[bids],dtype=wp.vec3),wp.array(m.jnt_pos[joints],dtype=wp.vec3)]
            output=wp.zeros((len(states),15),dtype=wp.spatial_vector)
            wp.launch(body_velocity,dim=len(states),inputs=arg,outputs=[output])
            error=float(np.max(np.abs(output.numpy()-states[:,:,7:])))
            np.testing.assert_allclose(output.numpy(),states[:,:,7:],atol=8e-5,rtol=2e-5)
            row=dict(device=device,states=len(states),max_velocity_error=error)
            if device.startswith('cuda'):
                with wp.ScopedCapture() as capture: wp.launch(body_velocity,dim=len(states),inputs=arg,outputs=[output])
                wp.capture_launch(capture.graph); wp.synchronize()
                start=time.perf_counter()
                for _ in range(100):wp.capture_launch(capture.graph)
                wp.synchronize()
                row['batch256_ms']=(time.perf_counter()-start)*10
                np.testing.assert_allclose(output.numpy(),states[:,:,7:],atol=8e-5,rtol=2e-5)
            reports.append(row);print(json.dumps(row),flush=True)
    (out/'actual_body_velocity.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')


if __name__=='__main__':main()

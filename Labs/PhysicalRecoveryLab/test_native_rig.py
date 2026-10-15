"""Verify reconstructed native mass, inertia, shape bounds and pose conversion."""
import json
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation as R
from native_rig import NativeRig,initial_states,OUT


def main():
    reports=[];momentum_error=0.;flat_momentum_error=0.;friction_bound_excess=0.;flat_samples=0
    for standing in (False,True):
        states,rig,meta=initial_states(standing)
        with NativeRig(states,'native-standing-test' if standing else 'native-floor-test') as native:
            actual=np.asarray(native.current)
            position_error=float(abs(actual[:,:3]-states[:,:3]).max())
            rotation_error=float((R.from_quat(actual[:,3:7]).inv()*R.from_quat(states[:,3:7])).magnitude().max())
            assert position_error<1e-6 and rotation_error<1e-6,(position_error,rotation_error)
            props=np.asarray(native.send('inspect')['body_properties'])
            errors={'mass_kg':0.,'com_m':0.,'inverse_inertia_relative':0.,'bounds_m':0.}
            for i,b in enumerate(rig['bodies']):
                errors['mass_kg']=max(errors['mass_kg'],abs(props[i,0]-b['jolt_mass_kg']))
                errors['com_m']=max(errors['com_m'],float(abs(props[i,1:4]-np.array(b['mass_frame']['position_cm'])*.01).max()))
                basis=R.from_quat(b['jolt_inertia_rotation_xyzw']).as_matrix()
                expected=basis@np.diag(1/(np.array(b['jolt_inertia_kg_cm2'])*1e-4))@basis.T
                errors['inverse_inertia_relative']=max(errors['inverse_inertia_relative'],float(np.linalg.norm(props[i,4:13].reshape(3,3)-expected)/np.linalg.norm(expected)))
                shape=b['shapes'][0];rot=R.from_quat(states[i,3:7]);sr=rot*R.from_quat(shape['local']['rotation_xyzw'])
                center=states[i,:3]+rot.apply(np.array(shape['local']['position_cm'])*.01)
                if shape['kind']=='box':extent=abs(sr.as_matrix())@(np.array(shape['half_extent_cm'])*.01)
                elif shape['kind']=='capsule':extent=abs(sr.apply([0,0,shape['cylinder_length_cm']*.005]))+shape['radius_cm']*.01
                else:extent=np.full(3,shape['radius_cm']*.01)
                errors['bounds_m']=max(errors['bounds_m'],float(abs(props[i,13:19]-np.r_[center-extent,center+extent]).max()))
            assert errors['mass_kg']<2e-6 and errors['com_m']<1e-6 and errors['inverse_inertia_relative']<2e-6 and errors['bounds_m']<2e-6,errors
            initial_q,_=native.coordinates()
            if standing:
                expected=np.asarray(meta['reference_qpos']);quats=initial_q[7:].reshape(-1,4);ref=expected[7:].reshape(-1,4)
                assert np.max(1-abs((quats*ref).sum(1)))<1e-6
            peak=0.;masses=np.asarray([b['jolt_mass_kg'] for b in rig['bodies']])
            previous_vertical_momentum=float(masses@actual[:,9]);total_impulse=0.
            for _ in range(240):
                state=native.step(np.zeros(54));assert np.isfinite(state).all()
                vertical_momentum=float(masses@state[:,9])
                expected_impulse=vertical_momentum-previous_vertical_momentum-native.external_vertical_impulse
                balance_error=abs(native.ground_impulses.sum()-expected_impulse)
                momentum_error=max(momentum_error,balance_error)
                # The contact observer exposes normal impulses. For a tilted
                # solved normal, friction can also have a vertical component.
                # Bound that missing component with the actual Coulomb cone.
                sine=native.ground_normal_tilt
                friction_bound=.7*abs(native.ground_impulses.sum())*sine/np.sqrt(1-sine*sine)
                friction_bound_excess=max(friction_bound_excess,balance_error-friction_bound)
                if sine<1e-6:
                    flat_samples+=1;flat_momentum_error=max(flat_momentum_error,balance_error)
                previous_vertical_momentum=vertical_momentum;total_impulse+=native.ground_impulses.sum()
                peak=max(peak,float(np.linalg.norm(state[:,10:13],axis=1).max()))
                assert native.observation().shape==(218,)
            assert peak<=62.83186,peak
            reports.append({'initial':'standing' if standing else 'floor','position_error_m':position_error,
                'rotation_error_rad':rotation_error,**errors,'zero_action_seconds':8,'peak_body_angular_rad_s':peak,
                'measured_vertical_ground_impulse_ns':float(total_impulse),
                'final_pelvis_height_m':float(state[0,2])})
    # Check the solved contact measurement against independent whole-body
    # momentum balance, and ensure a nearby-looking airborne foot is no support.
    assert flat_momentum_error<.001,(flat_samples,flat_momentum_error)
    assert friction_bound_excess<.001,friction_bound_excess
    states,_,_=initial_states(True);states[:,2]+=3.
    with NativeRig(states,'native-airborne-support-test') as native:
        for _ in range(3):
            native.step(np.zeros(54));np.testing.assert_array_equal(native.ground_impulses,np.zeros(len(states)))
    # Independently reconstruct policy coordinates from native body velocities,
    # including global root rotation and connector frames, before any stepping.
    model=mujoco.MjModel.from_xml_path(str(OUT/'uefn.xml'));data=mujoco.MjData(model);rng=np.random.default_rng(187)
    velocity_error=0.;joint_rotation_error=0.
    for trial in range(12):
        data.qpos[:]=meta['reference_qpos'];data.qpos[2]+=2
        qv=rng.normal(0,.4,model.nv);data.qvel[:]=qv
        mujoco.mj_integratePos(model,data.qpos,rng.normal(0,.3,model.nv),1.)
        mujoco.mj_forward(model,data);states=[]
        for body in rig['bodies']:
            i=model.body(body['name']).id;s=model.site(body['name']+'_bone').id
            angular=data.cvel[i,:3]
            linear=data.cvel[i,3:]+np.cross(angular,data.xipos[i]-data.subtree_com[model.body_rootid[i]])
            states.append(np.r_[data.site_xpos[s],R.from_matrix(data.site_xmat[s].reshape(3,3)).as_quat(),linear,angular])
        with NativeRig(np.asarray(states),'native-observation-test') as native:
            q,v=native.coordinates();velocity_error=max(velocity_error,float(abs(v-qv).max()))
            actual=R.from_quat(q[7:].reshape(-1,4)[:,[1,2,3,0]])
            expected=R.from_quat(data.qpos[7:].reshape(-1,4)[:,[1,2,3,0]])
            joint_rotation_error=max(joint_rotation_error,float((actual.inv()*expected).magnitude().max()))
    assert velocity_error<1e-6 and joint_rotation_error<1e-6,(velocity_error,joint_rotation_error)
    states,_,_=initial_states(False)
    with NativeRig(states,'native-requested-history-test',requested_action_history=True) as requested,NativeRig(states,'native-applied-history-test') as applied:
        a=requested.step(np.full(54,8.));b=applied.step(np.full(54,5.))
        np.testing.assert_allclose(a,b,atol=1e-9,rtol=0)
        np.testing.assert_array_equal(requested.observation()[-54:],np.full(54,8.))
        np.testing.assert_array_equal(applied.observation()[-54:],np.full(54,4.))
    report={'passed':True,'rig_sha256':meta['rig_sha256'],'cases':reports,
        'requested_history_preserves_raw_commands_with_identical_bounded_motion':True,
        'ground_impulse_verified':True,'normal_only_momentum_balance_max_difference_ns':momentum_error,
        'flat_contact_momentum_balance_error_ns':flat_momentum_error if flat_samples else None,'flat_contact_samples':flat_samples,
        'momentum_residual_beyond_coulomb_friction_bound_ns':friction_bound_excess,'airborne_contact_impulse_zero':True,
        'independent_observation_mapping_cases':12,'qvel_mapping_max_error':velocity_error,
        'joint_quaternion_mapping_max_error_rad':joint_rotation_error,
        'motor':'Damped velocity target; saturation mismatch retained and recorded in native-motor-calibration.json',
        'full_rig_cross_engine_parity_verified':False}
    (OUT/'native-rig-tests.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()

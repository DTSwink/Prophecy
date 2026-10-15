"""Same state and fixed command: isolate removed armature from motor chatter."""
import os,json,time,types,sys,itertools,xml.etree.ElementTree as ET
from pathlib import Path
os.environ['MIMICKIT_TRANSFER_OUT']=str(Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np
import torch,mujoco,warp as wp

def main():
    start=time.perf_counter();env,agent=probe.setup();e=env._engine
    m=e._solver.mj_model;wm=e._solver.mjw_model
    original_pre=e._pre_sim_step;flags=wm.opt.disableflags
    nodes=list(ET.parse(probe.SOURCE/'assets/uefn/humanoid_uefn.xml').getroot().find('worldbody').iter('body'))
    names=[n.attrib['name'] for n in nodes];foot=names.index('right_foot')
    arm_by_body={n.attrib['name']:float(n.find('joint').attrib['armature']) for n in nodes if n.find('joint') is not None}
    restored=np.zeros(m.nv);ankle_dofs=[]
    for i in range(6,m.nv):
        body=m.body(m.jnt_bodyid[m.dof_jntid[i]]).name
        matches=[name for name in arm_by_body if body==name or body.endswith('/'+name) or body.endswith('_'+name)]
        assert len(matches)==1,(body,matches)
        restored[i]=arm_by_body[matches[0]]
        if matches[0]=='right_foot':ankle_dofs.append(i)
    assert np.count_nonzero(restored)==34 and len(ankle_dofs)==3
    original_mass=m.body_mass.copy();original_inertia=m.body_inertia.copy()
    def armature(values):
        m.dof_armature[:]=values
        wm.dof_armature.assign(np.broadcast_to(values,wm.dof_armature.numpy().shape).copy().astype(np.float32))
    # Snapshot all solver arrays (including warm starts/contact history), then
    # replay fixed controls directly. Repeated environment resets retain tiny
    # solver-history differences and are unsuitable for this causal comparison.
    def snapshot(obj):
        result=[]
        for key,value in vars(obj).items():
            if isinstance(value,wp.array):result.append((value,value.numpy().copy()))
            elif key in ('contact','efc'):result.extend(snapshot(value))
        return result
    env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long),torch.zeros(n))
    onset='--onset' in sys.argv
    obs,info=env.reset()
    with torch.no_grad():action,_=agent._decide_action(obs,info)
    if not onset:
        obs,_,_,info=env.step(action)
        with torch.no_grad():action,_=agent._decide_action(obs,info)
    command=action[0].numpy().clip(-2*np.pi,2*np.pi)
    frozen={}
    baseline_physical=[]
    original_mjw_step=e._solver._mujoco_warp_step
    def freeze_synced():
        # First reset's Newton velocities are not yet mirrored in mjw_data at
        # pre_sim_step. Snapshot AFTER the ordinary solver state/control sync,
        # immediately before integration; do not invent a zero-velocity start.
        if 'solver' not in frozen:
            frozen['solver']=snapshot(e._solver.mjw_data)
            frozen['physical']=probe.physical_state(env).copy()
        original_mjw_step()
        baseline_physical.append(probe.physical_state(env).copy())
    def freeze(self,raw,control):
        if not frozen:
            if not onset:frozen['solver']=snapshot(e._solver.mjw_data)
            frozen['raw']={key:getattr(raw,key).numpy().copy() for key in ('body_q','body_qd','body_f','joint_q','joint_qd')}
            frozen['step']=e._solver._step;frozen['control']=control
            if not onset:frozen['physical']=probe.physical_state(env).copy()
        original_pre(raw,control)
    if onset:e._solver._mujoco_warp_step=freeze_synced
    e._pre_sim_step=types.MethodType(freeze,e);env.step(action);e._pre_sim_step=original_pre
    e._solver._mujoco_warp_step=original_mjw_step
    systematic='--systematic' in sys.argv
    coupled_test='--coupled' in sys.argv
    capped_test='--capped' in sys.argv or coupled_test
    capped=None
    if capped_test:
        if coupled_test:
            from coupled_velocity_motors import CoupledVelocityMotors as Integrator
        else:
            from capped_velocity_integrator import CappedVelocityIntegrator as Integrator
        capped=Integrator(wm,e._solver.mjw_data,m)
    cases=[dict(label=label) for label in ('removed','restore_ankle_only','restore_all','removed_motors_off')]
    if systematic:
        cases=[dict(label='removed',disabled=())]
        for bits in itertools.product((False,True),repeat=3):
            disabled=tuple(k for k,v in zip(('CONTACT','GRAVITY','LIMIT'),bits) if v)
            if disabled:cases.append(dict(label='no_'+'_'.join(disabled).lower(),disabled=disabled))
        cases.extend([dict(label='no_floor',collision='no_floor'),dict(label='no_self',collision='no_self')])
        for mode in ('ankle_off','restore_ankle','others_off'):
            for suffix,disabled in (('running',()),('no_contacts',('CONTACT',)),('free',('CONTACT','GRAVITY','LIMIT'))):
                cases.append(dict(label=mode+'_'+suffix,motor=mode,disabled=disabled,restore=mode=='restore_ankle'))
        cases.append(dict(label='all_motors_off_free',disabled=('CONTACT','GRAVITY','LIMIT','ACTUATION')))
        if onset:
            for intervention in ('ankle_gain_half','ankle_uncapped'):
                for suffix,disabled in (('running',()),('free',('CONTACT','GRAVITY','LIMIT'))):
                    cases.append(dict(label=intervention+'_'+suffix,motor=intervention,disabled=disabled))
    if capped_test:
        cases=[dict(label='removed',disabled=()),
               dict(label='original_free',disabled=('CONTACT','GRAVITY','LIMIT')),
               dict(label='capped_running',disabled=(),capped=True),
               dict(label='capped_free',disabled=('CONTACT','GRAVITY','LIMIT'),capped=True)]
    gains=wm.actuator_gainprm.numpy().copy();bias=wm.actuator_biasprm.numpy().copy()
    force_limited=wm.actuator_forcelimited.numpy().copy()
    contype=wm.geom_contype.numpy().copy();conaff=wm.geom_conaffinity.numpy().copy()
    pairs=wm.nxn_geom_pair_filtered;pairids=wm.nxn_pairid_filtered
    pair_values=pairs.numpy();pairid_values=pairids.numpy()
    ankle_actuators=np.flatnonzero(np.isin(m.actuator_trnid[:,0],m.dof_jntid[ankle_dofs])).tolist()
    assert len(ankle_actuators)>0
    floor=np.flatnonzero(m.geom_type==int(mujoco.mjtGeom.mjGEOM_PLANE))
    assert len(floor)==1 and m.npair==0,'Explicit collision pairs require separate masking'
    reports=[]
    for case in cases:
        label=case['label']
        if capped is not None:
            capped.restore()
            if case.get('capped'):capped.install()
        armature(np.zeros(m.nv));wm.opt.disableflags=flags
        wm.actuator_gainprm.assign(gains);wm.actuator_biasprm.assign(bias)
        wm.actuator_forcelimited.assign(force_limited)
        wm.geom_contype.assign(contype);wm.geom_conaffinity.assign(conaff)
        wm.nxn_geom_pair_filtered=pairs;wm.nxn_pairid_filtered=pairids
        for array,value in frozen['solver']:array.assign(value)
        e._solver._step=frozen['step']
        raw=e._sim_model.state();dest=e._sim_model.state()
        for key,value in frozen['raw'].items():getattr(raw,key).assign(value)
        np.testing.assert_array_equal(probe.physical_state(env),frozen['physical'])
        values=np.zeros(m.nv)
        if label=='restore_all':values[:]=restored
        if label=='restore_ankle_only' or case.get('restore'):values[ankle_dofs]=restored[ankle_dofs]
        armature(values)
        if label=='removed_motors_off':wm.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_ACTUATION)
        for flag in case.get('disabled',()):wm.opt.disableflags|=int(getattr(mujoco.mjtDisableBit,'mjDSBL_'+flag))
        mode=case.get('motor')
        if mode=='ankle_gain_half':
            gain=gains.copy();b=bias.copy();gain[...,ankle_actuators,:]*=0.5;b[...,ankle_actuators,:]*=0.5
            wm.actuator_gainprm.assign(gain);wm.actuator_biasprm.assign(b)
        if mode=='ankle_uncapped':
            limited=force_limited.copy();limited[ankle_actuators]=False
            wm.actuator_forcelimited.assign(limited)
        if mode in ('ankle_off','others_off'):
            ids=ankle_actuators if mode=='ankle_off' else [i for i in range(m.nu) if i not in ankle_actuators]
            gain=gains.copy();b=bias.copy();gain[...,ids,:]=0;b[...,ids,:]=0
            wm.actuator_gainprm.assign(gain);wm.actuator_biasprm.assign(b)
        collision=case.get('collision')
        if collision:
            assert int(wm.opt.broadphase)==0,'Pair filtering here requires NXN broadphase'
            ct=contype.copy();ca=conaff.copy()
            if collision=='no_floor':ct[...,floor]=0;ca[...,floor]=0
            else:ct[:]=2;ca[:]=1;ct[...,floor]=1;ca[...,floor]=2
            wm.geom_contype.assign(ct);wm.geom_conaffinity.assign(ca)
            floor_pair=np.any(np.isin(pair_values,floor),axis=1)
            keep=~floor_pair if collision=='no_floor' else floor_pair
            wm.nxn_geom_pair_filtered=wp.array(pair_values[keep],dtype=wp.vec2i,device=e._device)
            wm.nxn_pairid_filtered=wp.array(pairid_values[keep],dtype=wp.vec2i,device=e._device)
        rows=[]
        def capture():
            state=probe.physical_state(env)
            rows.append(dict(foot_world_angvel=state[foot,10:13].tolist(),
                ankle_joint_velocity=e._solver.mjw_data.qvel.numpy()[0,ankle_dofs].tolist(),
                actuator_force=e._solver.mjw_data.actuator_force.numpy()[0].tolist()))
        def solved():
            d=e._solver.mjw_data;count=int(d.nefc.numpy()[0]);t=d.efc.type.numpy()[0,:count];force=d.efc.force.numpy()[0,:count]
            contacts={}
            n=int(d.nacon.numpy()[0]);geom=d.contact.geom.numpy()
            for a,b in geom[:n]:
                kind='floor' if int(a) in floor or int(b) in floor else 'self'
                contacts[kind]=contacts.get(kind,0)+1
            return dict(ankle_actuator_torque=d.qfrc_actuator.numpy()[0,ankle_dofs].tolist(),
                ankle_constraint_torque=d.qfrc_constraint.numpy()[0,ankle_dofs].tolist(),
                ankle_acceleration=d.qacc.numpy()[0,ankle_dofs].tolist(),active_contacts=contacts,
                constraint_rows={str(int(k)):dict(count=int(np.sum(t==k)),max_abs_force=float(np.max(np.abs(force[t==k])))) for k in np.unique(t)})
        for tick in range(8):
            capture();original_pre(raw,frozen['control'])
            e._solver.step(raw,dest,frozen['control'],e._contacts,e._sim_timestep)
            if systematic:
                sample=solved();rows[-1]['following_step']=sample
                if case.get('capped'):
                    assert np.all(e._solver.mjw_data.ctrl.numpy()[:,capped.direct_ids]==0), 'Unexpected external torque actuator input'
                    sample['implicit_motor_torque']=capped.torque.numpy()[0].tolist()
                    sample['implicit_residual_nm']=float(capped.stats.numpy()[0,0])
                    sample['implicit_sweeps']=int(capped.stats.numpy()[0,1])
                if 'CONTACT' in case.get('disabled',()):assert not sample['active_contacts'],sample
                if collision=='no_floor':assert not sample['active_contacts'].get('floor'),sample
                if collision=='no_self':assert not sample['active_contacts'].get('self'),sample
                if 'LIMIT' in case.get('disabled',()):
                    assert not any(int(k) in (3,4) for k in sample['constraint_rows']),sample
                if mode=='ankle_off' or 'ACTUATION' in case.get('disabled',()):
                    assert max(abs(x) for x in sample['ankle_actuator_torque'])<1e-6,sample
            raw,dest=dest,raw
        capture();assert len(rows)==9
        velocity=np.array([r['foot_world_angvel'] for r in rows])
        joint=np.array([r['ankle_joint_velocity'] for r in rows])
        row=dict(case=label,intervention=case,ankle_armature_kg_m2=values[ankle_dofs].tolist(),
            world_x_sign_changes=int(np.sum(velocity[:-1,0]*velocity[1:,0]<0)),
            joint_sign_changes_per_axis=np.sum(joint[:-1]*joint[1:]<0,axis=0).tolist(),
            peak_foot_angular_speed_rad_s=float(np.linalg.norm(velocity,axis=1).max()),
            peak_joint_step_change_rad_s=float(np.abs(np.diff(joint,axis=0)).max()),samples=rows)
        reports.append(row);print(json.dumps({k:v for k,v in row.items() if k!='samples'}),flush=True)
        if systematic:(probe.OUT/('coupled-integrator-onset-partial.json' if coupled_test else 'capped-integrator-onset-partial.json' if capped_test else 'reversal-onset-partial.json' if onset else 'reversal-systematic-partial.json')).write_text(json.dumps(reports,indent=2))
    if capped is not None:capped.restore()
    if onset:
        original_series=np.array([frozen['physical'][foot,10:13]]+[x[foot,10:13] for x in baseline_physical])
        reference=np.load(probe.OUT/'newton_phase_0.000.npz')['physical'][1]
        np.testing.assert_allclose(baseline_physical[-1],reference,atol=1e-4,rtol=1e-5)
    else:
        expected=json.loads((probe.OUT/'contact-substeps.json').read_text())
        original_series=np.array([expected['inputs'][0][foot][10:13]]+[x['actual'][foot][10:13] for x in expected['outputs']])
    np.testing.assert_allclose(np.array([r['foot_world_angvel'] for r in reports[0]['samples']]),original_series,atol=2e-4,rtol=1e-5)
    np.testing.assert_array_equal(m.body_mass,original_mass);np.testing.assert_array_equal(m.body_inertia,original_inertia)
    result=dict(seconds=time.perf_counter()-start,physics_dt=1/240,policy_dt=1/30,
        ankle_dofs=ankle_dofs,full_command=command.tolist(),identical_initial_state=True,
        reproduces_recorded_oscillation=True,body_mass_inertia_unchanged=True,cases=reports)
    filename='coupled-integrator-onset.json' if coupled_test else 'capped-integrator-onset.json' if capped_test else 'reversal-onset-audit.json' if onset else 'reversal-systematic-audit.json' if systematic else 'armature-reversal-audit.json'
    (probe.OUT/filename).write_text(json.dumps(result,indent=2))
    print('Saved '+filename,flush=True)

if __name__=='__main__':main()

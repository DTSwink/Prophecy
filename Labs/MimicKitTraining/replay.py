"""Convert recorded Newton body transforms to the existing local Stepper viewer."""

import json

from datetime import datetime, timezone

from pathlib import Path

import numpy as np

from scipy.spatial.transform import Rotation



WORLD_TO_VIEW=np.array([[1,0,0],[0,0,1],[0,-1,0]])





def neutral_replay_message(meta,episode_mse):

    losses=meta.get('losses',{})

    def value(number,precision=6):

        return 'not recorded' if number is None else f'{number:.{precision}f}'

    if meta.get('task')=='timed_best_pose_tail':
        v=meta.get('rollout_losses',{})
        detail=' | '.join(f'{"velocity" if k=="joint_velocity" and meta.get("velocity_includes_pelvis") else k}: {v.get(k,float("nan")):.4e}' for k in ('early_pose','tail_mse','joint_velocity','total'))
        velocity_label='joint + pelvis linear/angular velocity' if meta.get('velocity_includes_pelvis') else 'joint velocity'
        return f'Rollout loss: {detail}. Early pose is negative improvement times timing bonus (4 to 1). Weighted tail: pose MSE x{meta.get("loss_weights",{}).get("tail_mse",1):g} + squared {velocity_label} x{meta.get("loss_weights",{}).get("joint_velocity",1):g}. Noise sigma: {meta.get("training_action_noise_std",0):.0e}. Actual training; test disabled. 45+5 frames (1.667s); ending is not recovery.'
    noise=meta.get('training_action_noise_std')

    applied=meta.get('rollout_action_noise_std')

    noise_text=value(noise,3)

    if meta.get('training_action_noise_distribution')=='uniform_fixed_per_agent':

        low,high=meta['training_action_noise_range']

        noise_text=f'U({low:.0e}, {high:.0e}), fixed per agent'

    # Historical captures have no noise metadata: never silently label them

    # with the current run's configured noise.

    label='Best episode MSE' if meta.get('task')=='best_neutral_pose_mse' else 'MSE'

    return (f"{label} (m², lower is better) — train: {value(losses.get('train_mse_m2'))} | "

            f"test: {'disabled' if meta.get('evaluation_disabled') else value(losses.get('test_mse_m2'))} | this rollout: {value(episode_mse)}. "

            f"Action noise σ — training: {noise_text} | this rollout: {value(applied,3)} "

            f"({meta.get('mode','deterministic evaluation')}). Horizon: 1.5s; ending does not mean recovery.")



def geometry(xml):

    import mujoco

    model=mujoco.MjModel.from_xml_path(str(xml))

    ids=list(range(1,model.nbody))

    names=[model.body(i).name for i in ids]

    mapping={b:i for i,b in enumerate(ids)}

    bones=[[mapping[int(model.body_parentid[i])],mapping[i]] for i in ids if int(model.body_parentid[i]) in mapping]

    shapes=[]

    for i in range(model.ngeom):

        body=int(model.geom_bodyid[i])

        if body not in mapping:continue

        shape=dict(bone=names[mapping[body]],position=model.geom_pos[i].tolist(),

                   axes=Rotation.from_quat(model.geom_quat[i][[1,2,3,0]]).as_matrix().T.tolist())

        kind=int(model.geom_type[i])

        if kind==int(mujoco.mjtGeom.mjGEOM_SPHERE):

            shape.update(kind='sphere',radius=float(model.geom_size[i,0]))

        elif kind==int(mujoco.mjtGeom.mjGEOM_CAPSULE):

            shape.update(kind='capsule',radius=float(model.geom_size[i,0]),length=float(2*model.geom_size[i,1]))

        elif kind==int(mujoco.mjtGeom.mjGEOM_BOX):

            shape.update(kind='box',dimensions=(2*model.geom_size[i]).tolist())

        else:raise ValueError(f'Unsupported geometry {kind}')

        shapes.append(shape)

    return dict(names=names,bones=bones,shapes=shapes,
                body_mass_properties=[dict(mass=float(model.body_mass[i]),
                                           com_local=model.body_ipos[i].tolist()) for i in ids])



def convert(recording, geom, run):

    with np.load(recording,allow_pickle=False) as z:

        meta=json.loads(str(z['metadata']));pose=z['pose'];data=z['data']
        frame_terms=z['loss_terms'] if 'loss_terms' in z else None

    result=convert_arrays(meta,pose,data,frame_terms,geom,run)
    reference = None
    with np.load(recording,allow_pickle=False) as z:
        if 'reference_pose' in z:
            reference = z['reference_pose']
            provenance = dict(source='exact recorded loss target' if meta.get('task') in ('absolute_walk_mse','uefn_omni_absolute_walk') else 'recorded DeepMimic reward reference')
    if reference is None:
        from replay_reference import recover_walk_reference
        recovered = recover_walk_reference(meta,pose,data,run)
        if recovered is not None:
            reference, provenance = recovered
    if reference is not None:
        assert reference.shape == pose.shape and np.isfinite(reference).all()
        result['mse_target_positions'] = [(reference[:,:,:3] @ WORLD_TO_VIEW.T).tolist()]
        reference_axes=Rotation.from_quat(reference[:,:,3:].reshape(-1,4)).as_matrix().reshape(*reference.shape[:2],3,3).swapaxes(-1,-2)@WORLD_TO_VIEW.T
        result['mse_target_basis']=[reference_axes.tolist()]
        result['metadata']['deepmimic_reference'] = provenance
    if meta.get('replay_rows'):
        with np.load(recording,allow_pickle=False) as z:
            result['rows'][0]['evaluation']=result['metadata']['evaluation']
            if meta['replay_rows'][0].get('motion_file'):
                result['rows'][0]['clip_name']=Path(meta['replay_rows'][0]['motion_file']).stem
            for i,row_meta in enumerate(meta['replay_rows'][1:],1):
                item=convert_arrays(row_meta,z[f'pose_{i}'],z[f'data_{i}'],z[f'loss_terms_{i}'],geom,run)
                for key in ('positions','basis','controller_root_pos','controller_root_rot','frozen_root_pos','frozen_root_rot','source_frame','source_clip_name'):
                    result[key].extend(item[key])
                entry=item['rows'][0];entry['row']=i;entry['evaluation']=item['metadata']['evaluation']
                if row_meta.get('motion_file'):entry['clip_name']=Path(row_meta['motion_file']).stem
                result['rows'].append(entry)
                target_key=f'reference_pose_{i}'
                if target_key in z:
                    target=z[target_key]
                    assert target.shape==z[f'pose_{i}'].shape and np.isfinite(target).all()
                    result['mse_target_positions'].append((target[:,:,:3]@WORLD_TO_VIEW.T).tolist())
                    axes=Rotation.from_quat(target[:,:,3:].reshape(-1,4)).as_matrix().reshape(*target.shape[:2],3,3).swapaxes(-1,-2)@WORLD_TO_VIEW.T
                    result['mse_target_basis'].append(axes.tolist())
    return result


def convert_arrays(meta,pose,data,frame_terms,geom,run):
    assert meta['complete_episode'] and meta['names']==geom['names']

    assert data[-1,0]!=0 and np.all(data[1:-1,0]==0)

    assert np.isfinite(pose).all()

    pos=pose[:,:,:3]@WORLD_TO_VIEW.T

    axes=Rotation.from_quat(pose[:,:,3:].reshape(-1,4)).as_matrix().reshape(*pose.shape[:2],3,3).swapaxes(-1,-2)@WORLD_TO_VIEW.T

    n=len(pose)
    if meta.get('task') in (None, 'deepmimic_walk') and frame_terms is None:
        meta['frame_rewards'] = data[:,2].tolist()
        meta['episode_return'] = float(data[1:,2].sum())
    if frame_terms is not None:
        # The existing recorder stores the exact weighted terms for each tick.
        # Legacy captures list their columns in rollout_losses insertion order.
        names=meta.get('loss_term_names') or [key for key in meta['rollout_losses'] if key != 'total']
        assert frame_terms.shape == (n,len(names)) and np.isfinite(frame_terms).all()
        if meta.get('reward_from_loss') in ('exp_negative_sum','reciprocal_sum','reciprocal_tracking_minus_termination_remaining'):
            # Auto-phase supervises the prediction head; it is displayed in the
            # total loss but is not part of the environment's physical reward.
            remaining_penalty=meta['reward_from_loss']=='reciprocal_tracking_minus_termination_remaining'
            reward_columns=[i for i,key in enumerate(names)
                            if not (key=='auto_phase' and meta.get('auto_phase_scope'))
                            and not (remaining_penalty and key=='termination_remaining')]
            total=frame_terms[1:,reward_columns].sum(axis=1)
            expected=(1./(1.+total) if meta['reward_from_loss']!='exp_negative_sum'
                      else np.exp(-total))
            if remaining_penalty:
                expected-=frame_terms[1:,names.index('termination_remaining')]
            assert np.allclose(expected,data[1:,2],atol=1e-6), 'Recorded reward does not match '+meta['reward_from_loss']
        else:
            assert np.allclose(-frame_terms.sum(axis=1),data[:,2],atol=1e-6)
        meta['frame_losses']={key:frame_terms[:,i].tolist() for i,key in enumerate(names)}
        meta['frame_losses']['total']=frame_terms.sum(axis=1).tolist()

    combined=meta.get('task')=='pelvis_head_height'

    minimum=meta.get('task')=='minimum_height_peaks'

    world_mse=meta.get('task')=='world_pose_mse'

    neutral=meta.get('task') in ('neutral_pose_mse','continuous_neutral_pose_mse','best_neutral_pose_mse','timed_best_pose_tail')

    if neutral: meta['episode_mse_m2']=-float(data[1:,2].sum())
    if meta.get('task')=='timed_best_pose_tail':
        meta['episode_total_loss']=meta.pop('episode_mse_m2')

    if meta.get('task')=='continuous_neutral_pose_mse':meta['loss_aggregation']='mean over all 45 frames'

    pure=meta.get('task') in ['head_height','pelvis_head_height','minimum_height_peaks']

    score=pose[:,meta['names'].index('head'),2]

    if combined: score=score+pose[:,meta['names'].index('pelvis'),2]

    measured_score=min(score.max(),pose[:,meta['names'].index('pelvis'),2].max()) if minimum else score.max()

    label='minimum of head/pelvis episode peaks' if minimum else 'pelvis + head' if combined else 'head'

    return dict(schema_version=2,computed_at=datetime.fromtimestamp(meta['generated_unix'],timezone.utc).isoformat(),

        run_id=run,step=meta['iteration'],fps=meta['fps'],joint_names=meta['names'],bones=geom['bones'],

        positions=[pos.tolist()],basis=[axes.tolist()],controller_root_pos=[pos[:,0].tolist()],

        controller_root_rot=[axes[:,0].tolist()],frozen_root_pos=[pos[:,0].tolist()],frozen_root_rot=[axes[:,0].tolist()],

        source_frame=[list(range(n))],source_clip_name=[['Newton '+meta.get('mode','evaluation')+f' world {meta.get("world",0)}']*n],

        rows=[dict(row=0,clip_id=0,clip_name=(f"AMP {meta.get('cohort','floor')} start - world {meta.get('world',0)}" if meta.get('task')=='amp_standing' else 'MimicKit AMP humanoid spinkick' if meta.get('task')=='amp_spinkick' else 'Pure RL fixed-heading world pose MSE' if world_mse else 'Pure RL upright neutral body MSE' if neutral else ('Pure RL '+label) if pure else 'MimicKit humanoid walk · complete evaluation'),clip_path='',start=0,

                   effective_k=n-1,virtual=False,noisy=meta.get('mode')=='actual training episode',has_sword=False,locomotion_category='physical_walk',gaze_normalized=[0,0])],

        metadata=dict(body_mode='full',checkpoint_kind='mimickit',has_sword=False,physical_colliders=geom['shapes'],
            body_mass_properties=geom.get('body_mass_properties'),

            capture_source='actual_newton_physics',physics_hz=240,policy_hz=30,step_unit='PPO iteration',

            training_progress=dict(training_transitions=meta['samples'],num_envs=meta.get('worlds')),evaluation=meta,

            display_geometry='Stock MimicKit humanoid collider surfaces'),

        message=(f"{meta.get('objective','Fixed-heading world pose MSE')}. Averaged over 60 ticks. No AMP reward. Noise training .05, replay zero." if world_mse else f"AMP static standing reference; displayed floor start {meta.get('start_side')}. Negative imitation reward is shown per tick. Upright cohort 102/512; only that cohort can terminate early. Timeout is not recovery success." if meta.get('task')=='amp_standing' else f"AMP spinkick · actual physics · episode {meta['duration_seconds']:.2f}s. Action noise σ: training {meta.get('training_action_noise_std',0.05):.0e}; displayed evaluation 0. Imitation reward and discriminator loss are in TensorBoard; no upright-pose MSE." if meta.get('task')=='amp_spinkick' else neutral_replay_message(meta,meta.get('episode_mse_m2')) if neutral else f"Pure RL complete 1.5s episode; {label} {measured_score:.3f}m. End flag is horizon, NOT recovery success." if pure else f"Complete deterministic episode: {meta['duration_seconds']:.2f}s; terminal flag {meta['terminal_flag']} (1=failure,3=timeout). Actual physics, not reference animation."))



if __name__=='__main__':

    import sys

    Path(sys.argv[2]).write_text(json.dumps(geometry(sys.argv[1])))


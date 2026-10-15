"""Shared, explicit contract for the authorized fresh Run LR test."""
from pathlib import Path

PHASE_WEIGHT=.1

def configure(env, engine, agent, root):
    root=Path(root)
    asset=root/'assets/uefn'
    env.update(char_file=str(asset/'humanoid_uefn.xml'),init_pose=None,
               motion_file=str(root/'motions/M_Neutral_Run_Loop_LR.pkl'),
               omni_manifest=str(root/'motions/manifest.json'),
               visualize_ref_char=False,enable_tar_obs=False,tar_obs_steps=[],enable_phase_obs=False,
               target_radius_m=.27)
    engine.update(control_mode='vel',uefn_asset_directory=str(asset),sim_freq=240,control_freq=30,
                  uefn_bounded_velocity_motors=True)
    agent['model'].update(actor_net='fc_1024_512_512',critic_net='fc_1024_512_512')
    agent['phase_prediction_weight']=PHASE_WEIGHT

"""Checkpoint loading shared by evaluation, physical viewer and export."""
import copy
import json
from pathlib import Path
import torch
from rsl_rl.models import MLPModel

def load_policy(checkpoint,env,allow_physics_override=False):
    checkpoint=Path(checkpoint)
    state=torch.load(checkpoint,map_location=env.device,weights_only=False)
    contract=state["infos"]["physical_recovery"]
    if contract["rig_sha256"]!=env.metadata["rig_sha256"]:
        raise ValueError("Checkpoint and current original-PHAT export differ; regenerate or select matching rig")
    if contract["controller"]!=env.controller.contract:
        raise ValueError("Checkpoint PD/observation controller contract changed")
    if contract.get('previous_action_observation','applied')!=env.cfg.get('previous_action_observation','applied'):
        raise ValueError('Previous-action observation must match the checkpoint')
    if not allow_physics_override:
        for key,default in (('integrator','implicitfast'),('solver','newton'),('ccd_iterations',50),('gyroscopic_forces',True)):
            if contract.get(key,default)!=env.cfg.get(key,default):
                raise ValueError(f'Checkpoint physics setting differs: {key}')
    config=json.loads((checkpoint.parent/"config.json").read_text())["ppo"]
    allowed=("hidden_dims","activation","obs_normalization","distribution_cfg")
    cfg={k:copy.deepcopy(v) for k,v in config["actor"].items() if k in allowed}
    policy=MLPModel(env.get_observations(),config["obs_groups"],"actor",env.num_actions,**cfg).to(env.device)
    policy.load_state_dict(state["actor_state_dict"]);policy.eval()
    return policy,state

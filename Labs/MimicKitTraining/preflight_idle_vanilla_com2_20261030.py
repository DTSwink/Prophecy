"""Disposable idle objective oracle and unchanged locomotion/graph checks; no training."""
import sys, os, json
from pathlib import Path
root = Path('/workspace/mimickit_trial/idle-vanilla-preflight')
sys.path[:0] = [str(root/'pipeline'), str(root/'MimicKit/mimickit')]
os.chdir(root)
import torch, warp as wp, yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from absolute_walk import AbsoluteWalkEnv
from omni_policy import OmniPPOAgent
from resume import restore
from lossless_runtime import install, REWARD_BUFFERS
from util import torch_util as q

torch.set_num_threads(1); torch.set_num_interop_threads(1)
torch.backends.cuda.matmul.allow_tf32 = False
torch.set_float32_matmul_precision('highest')
wp.init(); mp_util.init(0, 1, 'cuda:0', 6998)
cfg, ec, ac = [yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env', 'engine', 'agent']]
cfg['idle_row_fraction'] = .5  # Allocation-only test coverage, never deployed.
e = PerturbedOmniEnv(cfg, ec, 128, 'cuda:0', False)
a = OmniPPOAgent(ac, e, 'cuda:0')
restore(a, Path('/workspace/mimickit_trial/resume.zip'))
a._init_train(); a._sample_count = 14000000000; a.eval(); a.set_mode(AgentMode.TRAIN)
install(a, e); obs, info = a._reset_envs()
idle = e._idle_mse_rows
assert not idle[e._prior_ids].any()
assert (e._phase_supervision_mask[idle] == 0).all()
com = e.loss_term_names.index('com2_velocity')
extras = [i for i, n in enumerate(e.loss_term_names) if i >= 4 and n != 'com2_velocity']
groups = dict(normal=idle & ~e._perturbed_rows & ~e._final.minus,
              minus=idle & e._final.minus, plus=idle & e._final.plus,
              perturbed=idle & e._perturbed_rows & ~e._final.plus)
assert all(v.any() for v in groups.values())
errors = []; steps = 150; parity_checks = 0

def reward_state():
    buffers = [getattr(e, n) for n in REWARD_BUFFERS]
    buffers.extend(getattr(e._prior, n) for n in ['positions', 'rotations', 'valid'])
    for obj in [e._head_reversal, e._foot_regularizers, e._leg_reversal, e._idle_wobble]:
        buffers.extend(getattr(obj, n) for n in obj.buffer_names)
    return buffers, [v.clone() for v in buffers]

def restore_state(buffers, saved):
    for v, s in zip(buffers, saved): v.copy_(s)

with torch.no_grad():
    for t in range(steps):
        action, _ = a._decide_action(obs, info)
        obs, reward, done, info = e.step(action)
        char = e._get_char_id()
        pos = e._engine.get_body_pos(char); rot = e._engine.get_body_rot(char)
        ang = e._engine.get_body_ang_vel(char)
        vel = e._engine.get_body_vel(char)-torch.cross(ang, q.quat_rotate(rot, e._body_com), dim=-1)
        # Original calibrated MSE implementation, before all subclass boosts/mixing.
        expected = AbsoluteWalkEnv._tracking_losses(e, pos, rot, vel, ang, e.reward_target_vel, e.reward_target_ang)
        torch.testing.assert_close(e.loss_terms[idle, :4], expected[idle], rtol=1e-5, atol=1e-5)
        assert (e.loss_terms[idle][:, extras] == 0).all()
        assert (e._com2_reward_values[idle, 0] == 1).all()
        assert (e._prior_raw[idle] == 0).all() and (e._tracking_mix[idle] == 1).all()
        body_velocity = e._engine.get_body_vel(char)[:, e._com2_ids, :2]
        trunk = (body_velocity * e._com2_masses[None, :, None]).sum(1)/e._com2_masses.sum()
        delta = trunk-e._com2_targets[e._motion_ids]
        projected = (e._com2_loss_basis[e._motion_ids]*delta[:, None]).sum(-1)
        com2 = (projected.abs()-e._com2_loss_leeway[e._motion_ids]).clamp_min(0).square().mean(-1)*e._com2_loss_weight
        torch.testing.assert_close(e.loss_terms[:, com], com2, rtol=1e-5, atol=1e-5)
        valid = idle & (done == 0)
        if valid.any():
            errors.append(float((reward[valid]-1/(1+expected[valid].sum(-1)+com2[valid])).abs().max()))
        assert torch.isfinite(e.loss_terms).all()
        if t in [0, 60, 149]:
            buffers, saved = reward_state()
            e._update_reward(); graph_terms = e.loss_terms.clone(); graph_reward = e._reward_buf.clone()
            restore_state(buffers, saved)
            e._update_reward.original()
            torch.testing.assert_close(graph_terms, e.loss_terms, atol=1e-5, rtol=1e-5)
            torch.testing.assert_close(graph_reward, e._reward_buf, atol=1e-6, rtol=1e-5)
            restore_state(buffers, saved)
            e._idle_mse_com2_only = False
            e._update_reward.original()
            torch.testing.assert_close(graph_terms[~idle], e.loss_terms[~idle], atol=0, rtol=0)
            torch.testing.assert_close(graph_reward[~idle], e._reward_buf[~idle], atol=0, rtol=0)
            e._idle_mse_com2_only = True
            restore_state(buffers, saved)
            parity_checks += 1
        obs, info = a._reset_done_envs(done)
assert max(errors) < 2e-6
for mask in groups.values():
    row = e.recovery_row_metadata(int(torch.where(mask)[0][0]))
    assert row['ae_disabled'] and not row['auto_phase_supervised']
    assert row['whole_body_velocity_mse']['multiplier'] == 1
    assert row['active_loss_terms'] == list(e.loss_term_names[:4])+['com2_velocity']
report = dict(passed=True, worlds=128, frames=steps, idle_groups={k:int(v.sum()) for k,v in groups.items()},
    original_four_mse_oracle=True, unchanged_com2_oracle=True, idle_extra_terms_zero=True,
    idle_ae_inference_excluded=True, idle_auxiliary_phase_disabled=True, reward_error=max(errors),
    graph_eager_checks=parity_checks, locomotion_bit_exact=True, metadata_verified=True)
(root/'preflight.json').write_text(json.dumps(report, indent=2)); print(json.dumps(report), flush=True)

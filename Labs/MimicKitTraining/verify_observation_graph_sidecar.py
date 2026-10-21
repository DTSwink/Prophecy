"""Bounded, isolated observation optimization audit; no live trainer mutation."""
import sys, json, time, types
from pathlib import Path
ROOT = Path('/workspace/mimickit_trial')
OUT = ROOT/'perf-observations-20261020'
OUT.mkdir(exist_ok=True)
sys.path[:0] = ['/tmp', str(ROOT/'pipeline'), str(ROOT/'MimicKit/mimickit')]
import torch, warp as wp, yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
from graphed_observations import install
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
wp.init()
wp.set_device('cuda:0')
mp_util.init(0, 1, 'cuda:0', 6796)
cfg, ec, ac = [yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text())
               for n in ('env', 'engine', 'agent')]
env = PerturbedOmniEnv(cfg, ec, 512, 'cuda:0', False)
agent = OmniPPOAgent(ac, env, 'cuda:0')
r = ROOT/'runs'/sys.argv[1]
b = json.loads((r/'backup_status.json').read_text())
restore(agent, r/Path(b['key']).name)
agent._init_train()
agent.set_mode(AgentMode.TRAIN)
agent._curr_obs, agent._curr_info = agent._reset_envs()
original = env._compute_obs
import importlib.util
model = env._kin_char_model
fast_conversion = model.dof_to_rot
fast_inverse = model.rot_to_dof
spec = importlib.util.spec_from_file_location('baseline_conversion', ROOT/'pipeline/batched_joint_conversion.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
model._batched_joint_conversion = False
baseline.install(model)
old_conversion = model.dof_to_rot
old_inverse = model.rot_to_dof
model.dof_to_rot = fast_conversion
model.rot_to_dof = fast_inverse
for count in (0, 1, 7, 512):
    values = torch.randn(count, model.get_dof_size(), device='cuda')*10
    if count: values[0] = 0
    a, b = old_conversion(values), fast_conversion(values)
    torch.testing.assert_close(a, b, atol=2e-6, rtol=2e-6)
    torch.testing.assert_close(old_inverse(a), fast_inverse(a), atol=2e-6, rtol=2e-6)
install(env)
fast = env._compute_obs
errors = []
# Full and mixed reset subsets, including stale-output/alias protection.
for ids in (None, torch.arange(0, 512, 3, device='cuda'),
            torch.tensor([0, 511, 25, 201, 3], device='cuda'),
            torch.empty(0, device='cuda', dtype=torch.long)):
    model.dof_to_rot = old_conversion
    expected = original(ids)
    model.dof_to_rot = fast_conversion
    actual = fast(ids)
    torch.testing.assert_close(actual, expected, atol=1e-6, rtol=1e-6)
    errors.append(float((actual-expected).abs().max()) if actual.numel() else 0.)
old = fast().clone()
held = fast()
env._engine.get_dof_pos(0).add_(.01)
actual = fast()
torch.testing.assert_close(actual, original(), atol=1e-6, rtol=1e-6)
torch.testing.assert_close(held, old, atol=0, rtol=0)
agent._curr_obs, agent._curr_info = agent._reset_envs()
micro = []
for use_fast in (False, True, True, False):
    f = fast if use_fast else original
    model.dof_to_rot = fast_conversion if use_fast else old_conversion
    model.rot_to_dof = fast_inverse if use_fast else old_inverse
    for _ in range(3): f()
    torch.cuda.synchronize()
    t = time.perf_counter()
    for _ in range(50): f()
    torch.cuda.synchronize()
    micro.append(dict(fast=use_fast, seconds=time.perf_counter()-t, calls=50))
full = []
for use_fast in (False, True, True, False):
    env._compute_obs = fast if use_fast else original
    model.dof_to_rot = fast_conversion if use_fast else old_conversion
    model.rot_to_dof = fast_inverse if use_fast else old_inverse
    agent._train_iter()
    torch.cuda.synchronize()
    t = time.perf_counter()
    agent._train_iter()
    torch.cuda.synchronize()
    full.append(dict(fast=use_fast, seconds=time.perf_counter()-t))
report = dict(errors=errors, output_ownership=True, observations=micro,
              ppo=full, concurrent_with_live_training=True)
(OUT/'result.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report), flush=True)
env._compute_obs = fast
model.dof_to_rot = fast_conversion
model.rot_to_dof = fast_inverse
from profile_training import run_profiled_update
run_profiled_update(agent, agent._train_iter, OUT, 1)

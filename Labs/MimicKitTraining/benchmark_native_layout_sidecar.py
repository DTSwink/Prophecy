"""Isolated native solver matrix-layout test; physical settings unchanged."""
import sys, json, time, copy, gc
from pathlib import Path
ROOT = Path('/workspace/mimickit_trial')
OUT = ROOT/'perf-layout-20261020'
OUT.mkdir(exist_ok=True)
sys.path[:0] = [str(ROOT/'pipeline'), str(ROOT/'MimicKit/mimickit')]
import torch, warp as wp, yaml, mujoco, mujoco_warp as mjw
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
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
agent.eval()
agent._rollout_train(12)
solver = env._engine._solver
source = solver.mjw_data
fields = ['qpos', 'qvel', 'act', 'ctrl', 'qacc', 'qacc_warmstart', 'qfrc_applied',
          'xfrc_applied', 'time']
initial = {n: wp.clone(getattr(source, n)) for n in fields}
results = []
positions = {}
for index, variant in enumerate(('existing', 'dense', 'dense', 'existing')):
    model = copy.copy(solver.mj_model)
    if variant == 'dense':
        model.opt.jacobian = mujoco.mjtJacobian.mjJAC_DENSE
    m = mjw.put_model(model)
    d = mjw.make_data(model, nworld=512, nconmax=150, njmax=450)
    def reset():
        mjw.reset_data(m, d)
        for n, value in initial.items():
            wp.copy(getattr(d, n), value)
    reset()
    mjw.step(m, d)
    with wp.ScopedCapture() as capture:
        mjw.step(m, d)
    for _ in range(3):
        wp.capture_launch(capture.graph)
    wp.synchronize()
    reset()
    wp.synchronize()
    started = time.perf_counter()
    for _ in range(32):
        wp.capture_launch(capture.graph)
    wp.synchronize()
    elapsed = time.perf_counter()-started
    pos = wp.to_torch(d.xpos).clone()
    vel = wp.to_torch(d.qvel).clone()
    if index == 0:
        positions['position'] = pos
        positions['velocity'] = vel
    error = (pos-positions['position']).abs()
    result = dict(variant=variant, seconds=elapsed, steps=32, worlds=512,
                  jacobian=int(model.opt.jacobian),
                  position_max_m=float(error.max()),
                  position_rms_m=float(error.square().mean().sqrt()),
                  velocity_max=float((vel-positions['velocity']).abs().max()))
    results.append(result)
    (OUT/'result.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(result), flush=True)
    del m, d, capture, model
    gc.collect()
print('LAYOUT_COMPLETE', flush=True)

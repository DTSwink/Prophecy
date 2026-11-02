"""Opt-in dispatch optimization for the pinned locomotion workload.

Learning math, precision, physics settings and episode logic are unchanged.
Physics reductions retain the backend's existing floating-point nondeterminism.
"""
import importlib.metadata
import torch
import warp as wp
from envs.base_env import EnvMode
from sparse_actuator_runtime import SparseActuators
from fused_factor_runtime import FusedFactor
from graphed_kicks_runtime import GraphKicks

REWARD_BUFFERS=['loss_terms','_reward_buf','reward_target_pos','reward_target_rot',
    'reward_target_vel','reward_target_ang','_completed_loss_totals','_prior_raw',
    '_tracking_mix','_ae_diagnostics','_head_height_reward','_reward_diagnostics']

class TrainingRewardGraph:
    def __init__(self,e):
        self.e=e;self.original=e._update_reward;self.graph=None
    def __call__(self):
        # Evaluation has different diagnostic accounting. Keep its eager path.
        if self.e._mode!=EnvMode.TRAIN:return self.original()
        if self.graph is None:
            e=self.e;buffers=[getattr(e,n) for n in REWARD_BUFFERS]
            buffers.extend(getattr(e._prior,n) for n in ['positions','rotations','valid'])
            saved=[v.clone() for v in buffers]
            stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream):
                for _ in range(4):self.original()
            torch.cuda.current_stream().wait_stream(stream)
            graph=torch.cuda.CUDAGraph()
            with torch.cuda.graph(graph,stream=stream):self.original()
            for v,s in zip(buffers,saved):v.copy_(s)
            self.graph=graph
        self.graph.replay()

def install(agent,e):
    versions={n:importlib.metadata.version(n) for n in ['mujoco-warp','warp-lang','torch']}
    if versions['mujoco-warp']!='3.5.0.2' or versions['warp-lang']!='1.12.1':
        raise RuntimeError('Dispatch optimization requires its validated MJWarp/Warp versions')
    if len(e._recovery_ids) or bool(e._perturbed_getup.any()) or not e._idle_position_getup:
        raise RuntimeError('Dispatch optimization is limited to the validated locomotion-only configuration')
    if torch.get_float32_matmul_precision()!='highest' or torch.backends.cuda.matmul.allow_tf32:
        raise RuntimeError('Dispatch optimization requires unchanged highest FP32 precision')
    eng=e._engine;s=eng._solver
    if s.mj_model.nv!=40 or s.mj_model.nu!=68 or eng._sim_steps!=8:
        raise RuntimeError('Unexpected physics topology or substeps')
    sp=SparseActuators(s.mj_model,s.mjw_model,s.mjw_data)
    factor=FusedFactor(s.mjw_model,s.mjw_data)
    # Compilation uses scratch outputs, never advances the simulation.
    sp.velocity(wp.zeros_like(s.mjw_data.actuator_velocity))
    sp.deriv(wp.zeros_like(s.mjw_data.actuator_velocity),wp.zeros_like(s.mjw_data.qM))
    factor.apply(s.mjw_model,s.mjw_data,s.mjw_data.qM,wp.zeros_like(s.mjw_data.qLD),wp.zeros_like(s.mjw_data.qLDiagInv))
    with sp.capture(),factor.capture():eng._build_graphs()
    if sp.hits!=dict(velocity=8,derivative=8) or factor.hits!=16:
        raise RuntimeError('Unexpected captured physics kernel count')
    # Retain every array referenced by the captured graph.
    eng._dispatch_resources=(sp,factor)
    e._dispatch_no_getups=True
    e._dispatch_empty_getup_ids=torch.empty(0,device=e._device,dtype=torch.long)
    e._update_reward=TrainingRewardGraph(e)
    e._final.kicker=GraphKicks(eng)
    return dict(versions=versions,worlds=e.get_num_envs(),physics_hz=240,policy_hz=30,
        precision='FP32 highest; TF32 disabled',physics_kernel_intercepts=sp.hits,
        factor_intercepts=factor.hits,optimizer_and_kl='unchanged eager execution',
        evaluation_reward='unchanged eager path',initialization='lazy graphs preserve state')

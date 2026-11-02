"""Isolated CUDA-graph experiment; no learning or episode-rule changes."""
import torch
from contextlib import contextmanager, nullcontext
from envs.base_env import EnvMode
from envs import deepmimic_env
from omni_walk import OmniWalkEnv, centre_distances, DoneFlags
from capturable_done_probe import compute_done_capturable


def omni_done_capturable(self):
    super(OmniWalkEnv, self)._update_done()
    ids = self._termination_ids
    char = self._get_char_id()
    self.target_distances_sq.copy_(centre_distances(self._engine.get_body_pos(char)[:, ids],
        self._engine.get_body_rot(char)[:, ids], self.reward_target_pos[:, ids],
        self.reward_target_rot[:, ids], self._termination_offsets))
    failed = (self.target_distances_sq > self._target_radius_sq).any(-1) & (self._time_buf > 0)
    if hasattr(self, '_final'):
        failed &= ~self._final.minus
    self._done_buf.masked_fill_(failed, DoneFlags.FAIL.value)


@contextmanager
def capturable_rules():
    original = deepmimic_env.compute_done
    omni_original = OmniWalkEnv._update_done
    try:
        deepmimic_env.compute_done = compute_done_capturable
        OmniWalkEnv._update_done = omni_done_capturable
        yield
    finally:
        deepmimic_env.compute_done = original
        OmniWalkEnv._update_done = omni_original

REF_NAMES = ['_ref_root_pos', '_ref_root_rot', '_ref_root_vel', '_ref_root_ang_vel',
             '_ref_joint_rot', '_ref_dof_vel', '_ref_body_pos', '_ref_body_rot']
DONE_NAMES = ['_done_buf', '_reward_buf', 'target_distances_sq', '_reset_reason',
              '_outcome_ends', '_outcome_failures', '_outcome_head_resets']


class MethodGraph:
    def __init__(self, env, method, names, extra=()):
        self.env = env
        self.method = method
        self.original = getattr(env, method)
        self.buffers = [getattr(env, n) for n in names] + list(extra)
        self.names = names + ['extra_' + str(i) for i in range(len(extra))]
        self.graph = None
        self.audit = True
        self.comparisons = 0
        self.elements = 0
        self.pointers = None

    def inputs(self):
        e = self.env
        c = e._get_char_id()
        result = [e._time_buf, e._motion_ids, e._feedback_phase,
                  e._engine.get_body_pos(c), e._engine.get_body_rot(c),
                  e._engine.get_body_vel(c), e._engine.get_ground_contact_forces(c)]
        return tuple(v.data_ptr() for v in result)

    def restore(self, saved):
        for target, value in zip(self.buffers, saved):
            target.copy_(value)

    @torch.no_grad()
    def __call__(self):
        if self.env._mode != EnvMode.TRAIN:
            return self.original()
        if self.graph is None:
            saved = [v.clone() for v in self.buffers]
            self.pointers = self.inputs()
            stream = torch.cuda.Stream()
            stream.wait_stream(torch.cuda.current_stream())
            context = capturable_rules() if self.method == '_update_done' else nullcontext()
            with context:
                with torch.cuda.stream(stream):
                    for _ in range(4):
                        self.original()
                torch.cuda.current_stream().wait_stream(stream)
                graph = torch.cuda.CUDAGraph()
                with torch.cuda.graph(graph, stream=stream):
                    self.original()
            self.restore(saved)
            self.graph = graph
        if self.inputs() != self.pointers:
            raise RuntimeError('Graph input allocation changed: ' + self.method)
        if not self.audit:
            self.graph.replay()
            return
        saved = [v.clone() for v in self.buffers]
        self.original()
        expected = [v.clone() for v in self.buffers]
        self.restore(saved)
        self.graph.replay()
        for name, actual, wanted in zip(self.names, self.buffers, expected):
            if not torch.equal(actual, wanted):
                error = (actual.to(torch.float64) - wanted.to(torch.float64)).abs().max().item()
                raise AssertionError((self.method, name, error))
            self.elements += actual.numel()
        self.comparisons += 1


def make(env):
    assert not len(env._recovery_ids)
    assert not env._enable_ref_char()
    return [MethodGraph(env, '_update_ref_motion', REF_NAMES),
            MethodGraph(env, '_update_done', DONE_NAMES, [env._final.first_foot])]

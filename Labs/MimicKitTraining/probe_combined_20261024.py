"""Reuse the bounded PPO harness for the combined disposable candidates."""
import sys
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
from graphed_ppo_probe import GraphedLoss
from sparse_actuator_probe import SparseActuators
from fused_factor_probe import FusedFactor
from probe_reward_graph_20261024 import optimize_empty_getups,RewardGraph
from probe_kick_graph_20261024 import GraphKicks
from final_locomotion import ArticulatedKicks
import absolute_walk,perturbed_omni
import torch,warp as wp,mujoco_warp as mjw

class CombinedLoss(GraphedLoss):
    shared=None
    def __init__(self,fn,optimizer,batch,key):
        super().__init__(fn,optimizer,batch,key)
        self.agent=fn.__self__
    def install(self):
        if self.key=='actor_loss':
            if self.shared is None:type(self).shared=CombinedEnvironment(self.agent._env)
            self.shared.select(True)
        return super().install()
    def uninstall(self):
        if self.key=='actor_loss' and self.shared is not None:self.shared.select(False)
        return super().uninstall()

class CombinedEnvironment:
    def __init__(self,e):
        self.e=e;eng=e._engine;s=eng._solver
        self.physics=eng._graph
        self.sparse=SparseActuators(s.mj_model,s.mjw_model,s.mjw_data)
        self.factor=FusedFactor(s.mjw_model,s.mjw_data)
        self.sparse.velocity(wp.zeros_like(s.mjw_data.actuator_velocity))
        self.sparse.deriv(wp.zeros_like(s.mjw_data.actuator_velocity),wp.zeros_like(s.mjw_data.qM))
        self.factor.apply(s.mjw_model,s.mjw_data,s.mjw_data.qM,s.mjw_data.qLD,s.mjw_data.qLDiagInv)
        with self.sparse.capture(),self.factor.capture():eng._build_graphs()
        self.fast_physics=eng._graph
        assert self.sparse.hits==dict(velocity=8,derivative=8)
        assert self.factor.hits==16,self.factor.hits
        names=['_update_reward','_base_perturbed_tracking_losses','_refresh_reward_rotations','_target_positions']
        self.original={n:getattr(e,n) for n in names};self.original_alignment=absolute_walk.aligned_positions
        optimize_empty_getups(e);self.optimized={n:getattr(e,n) for n in names};self.fast_alignment=absolute_walk.aligned_positions
        self.optimized['_update_reward']=RewardGraph(e)
        self.kicker=ArticulatedKicks(eng);self.fast_kicker=GraphKicks(eng)
        eng._sim_state.pre_step_update();s._update_mjc_data(s.mjw_data,eng._sim_model,eng._sim_state.raw_state)
        for f in [mjw.kinematics,mjw.com_pos,mjw.crb,mjw.factor_m]:f(s.mjw_model,s.mjw_data)
        self.fast_kicker.basis()
    def select(self,mode):
        self.e._engine._graph=self.fast_physics if mode else self.physics
        for k,v in (self.optimized if mode else self.original).items():setattr(self.e,k,v)
        absolute_walk.aligned_positions=self.fast_alignment if mode else self.original_alignment
        perturbed_omni.aligned_positions=absolute_walk.aligned_positions
        self.e._final.kicker=self.fast_kicker if mode else self.kicker

source=(ROOT/'probe_graphed_ppo_20261024.py').read_text()
source=source.replace('from graphed_ppo_probe import GraphedLoss','from __main__ import CombinedLoss as GraphedLoss')
source=source.replace('ppo-graph','combined-lossless')
source=source.replace("assert time.time()-start<50", "assert time.time()-start<50\n        from profile_training import run_profiled_update\n        for mode in [False,True]:\n            select(mode);run_profiled_update(a,a._train_iter,OUT,10+int(mode))")
exec(compile(source,str(ROOT/'probe_combined_20261024.py')+':harness','exec'),dict(__name__='__main__'))

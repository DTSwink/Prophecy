"""Isolated no-get-up reward dispatch audit, including all stateful AE buffers."""
import inspect,json,os,sys,textwrap,time,traceback,types
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024'
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')];os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from recovery_omni import RecoveryOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
import absolute_walk,perturbed_omni

@torch.jit.script
def aligned_device(actual:torch.Tensor,reference:torch.Tensor):
    shift=actual[:,:1]-reference[:,:1]
    shift=torch.cat((shift[...,:2],shift[...,2:]*0.),dim=-1)
    return reference+shift

NAMES=['loss_terms','_reward_buf','reward_target_pos','reward_target_rot','reward_target_vel','reward_target_ang','_completed_loss_totals','_prior_raw','_tracking_mix','_ae_diagnostics','_head_height_reward','_reward_diagnostics']
def buffers(e):
    result={n:getattr(e,n) for n in NAMES}
    result.update({'prior.'+n:getattr(e._prior,n) for n in ['positions','rotations','valid']})
    return result
def snap(e):return {n:t.clone() for n,t in buffers(e).items()}
def restore_buffers(e,old):
    for n,t in buffers(e).items():t.copy_(old[n])
def compare(e,expected):
    differences={}
    for n,t in buffers(e).items():
        differences[n]=float((t-expected[n]).abs().max()) if t.numel() else 0
        torch.testing.assert_close(t,expected[n],rtol=0,atol=0)
    return differences

def optimize_empty_getups(e):
    assert not e._perturbed_getup.any() and not len(e._recovery_ids)
    assert e._idle_position_getup
    e._empty_getup_ids=torch.empty(0,dtype=torch.long,device=e._device)
    # Preserve every nonempty-row operation and floating-point arithmetic.
    source=textwrap.dedent(inspect.getsource(PerturbedOmniEnv._base_perturbed_tracking_losses))
    source=source.replace('super()._tracking_losses','super(PerturbedOmniEnv, self)._tracking_losses')
    source=source.replace('    terms[self._perturbed_getup] = 0.\n','')
    source=source.replace("terms[ids, self.loss_term_names.index('flat_com_velocity')] = 0.","terms[:, self.loss_term_names.index('flat_com_velocity')].index_fill_(0, ids, 0.)")
    start=source.index('    if self._idle_position_getup:\n')
    end=source.index('    ae = ',start)
    source=source[:start]+source[end:]
    scope=dict(perturbed_omni.__dict__);exec(source,scope)
    e._base_perturbed_tracking_losses=types.MethodType(scope['_base_perturbed_tracking_losses'],e)
    e._refresh_reward_rotations=types.MethodType(lambda self:self.reward_target_rot.copy_(self._ref_body_rot),e)
    e._target_positions=types.MethodType(RecoveryOmniEnv._target_positions,e)
    source=textwrap.dedent(inspect.getsource(PerturbedOmniEnv._update_reward))
    source=source.replace('super()._update_reward()','super(PerturbedOmniEnv, self)._update_reward()')
    source=source.replace('rows = self._perturbed_getup','rows = self._empty_getup_ids')
    exec(source,scope);e._update_reward=types.MethodType(scope['_update_reward'],e)
    absolute_walk.aligned_positions=aligned_device;perturbed_omni.aligned_positions=aligned_device

class RewardGraph:
    def __init__(self,e):
        self.e=e;self.original=e._update_reward
        previous=snap(e);stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(stream):
            for _ in range(4):self.original()
        torch.cuda.current_stream().wait_stream(stream)
        self.graph=torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph,stream=stream):self.original()
        restore_buffers(e,previous)
    def __call__(self):self.graph.replay()

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6821)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    e=PerturbedOmniEnv(cfg,ec,2048,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];b=json.loads((run/'backup_status.json').read_text());restore(a,run/Path(b['key']).name)
    a._init_train();a.set_mode(AgentMode.TRAIN);a._curr_obs,a._curr_info=a._reset_envs()
    # Preserve model topology for a separate capacity proof; no capacity changes here.
    m=e._engine._solver.mj_model;wm=e._engine._solver.mjw_model
    import mujoco
    mujoco.mj_saveModel(m,str(OUT/'native-model.mjb'))
    topology={k:getattr(wm,k).numpy().tolist() for k in ['nxn_geom_pair_filtered','nxn_pairid_filtered']}
    topology.update(neq=m.neq,ntendon=m.ntendon,njnt=m.njnt)
    (OUT/'collision-topology.json').write_text(json.dumps(topology))
    original=e._update_reward
    for _ in range(2):a._train_iter()
    previous=snap(e);original();baseline=snap(e);restore_buffers(e,previous)
    optimize_empty_getups(e);optimized=e._update_reward;optimized()
    report=dict(checkpoint=b,empty_getup_exact=compare(e,baseline));restore_buffers(e,previous)
    (OUT/'reward-empty-getup-exact.json').write_text(json.dumps(report,indent=2))
    graph=RewardGraph(e);graph();report['capture_exact']=compare(e,baseline)
    restore_buffers(e,previous)
    checks=[]
    for tick in [1,29,30,31,45,60,80,130,150]:
        a._curr_obs,a._curr_info=a._reset_envs();e._time_buf.fill_(tick/30)
        previous=snap(e);optimized();expected=snap(e);restore_buffers(e,previous)
        graph();checks.append(dict(tick=tick,differences=compare(e,expected)));restore_buffers(e,previous)
    report['timeline_checks']=checks
    timings=[]
    for mode in [False,True,True,False]:
        torch.cuda.synchronize();start=time.perf_counter()
        for _ in range(50):(graph if mode else optimized)()
        torch.cuda.synchronize();timings.append(dict(graph=mode,seconds=(time.perf_counter()-start)/50))
    report['reward_times']=timings
    (OUT/'reward-graph-basis.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(timings=timings)),flush=True)
    a._curr_obs,a._curr_info=a._reset_envs()
    updates=[]
    for mode in [False,True,True,False]:
        e._update_reward=graph if mode else optimized
        for _ in range(2):
            torch.cuda.synchronize();start=time.perf_counter();a._train_iter();torch.cuda.synchronize()
            updates.append(dict(graph=mode,seconds=time.perf_counter()-start));print(json.dumps(updates[-1]),flush=True)
    report['updates']=updates
    (OUT/'reward-graph-complete.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'reward-graph-failure.txt').write_text(traceback.format_exc());raise

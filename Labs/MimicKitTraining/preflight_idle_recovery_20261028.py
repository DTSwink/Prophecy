"""Bounded isolated GPU reward/reset/recorder check, running trainer untouched."""
import os,sys,json,traceback,hashlib
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'idle-recovery-check'
sys.path[:0]=[str(OUT/'pipeline'),str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from lossless_runtime import TrainingRewardGraph,REWARD_BUFFERS
from observe_many import MultiRecorder
from com2_reward_gate import com2_reward_gate

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6843)
    cfg=yaml.safe_load((OUT/'prepared/env_config.yaml').read_text())
    ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ['engine','agent']]
    e=PerturbedOmniEnv(cfg,ec,128,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    a._init_train();a.set_mode(AgentMode.TRAIN);a._curr_obs,a._curr_info=a._reset_envs()
    e._dispatch_no_getups=True;e._dispatch_empty_getup_ids=torch.empty(0,device=e._device,dtype=torch.long)
    e._update_reward();e._update_reward()
    graph=TrainingRewardGraph(e)
    buffers=[getattr(e,n) for n in REWARD_BUFFERS]+[getattr(e._prior,n) for n in ['positions','rotations','valid']]+[getattr(e._head_reversal,n) for n in e._head_reversal.buffer_names]+[getattr(e._foot_regularizers,n) for n in e._foot_regularizers.buffer_names]+[getattr(e._leg_reversal,n) for n in e._leg_reversal.buffer_names]
    checks=[]
    for tick,last in [(2,-1),(8,-1),(59,-1),(60,60),(69,60),(80,60),(90,60),(105,60),(120,120),(150,120)]:
        e._time_buf.fill_(tick/30.);e._final.last_kick[e._final.minus]=last
        saved=[v.clone() for v in buffers];e._update_reward();expected=[v.clone() for v in buffers]
        for v,s in zip(buffers,saved):v.copy_(s)
        graph()
        for j,(v,s) in enumerate(zip(buffers,expected)):torch.testing.assert_close(v,s,rtol=0,atol=0,equal_nan=True,msg=lambda m:str((tick,j))+m)
        expected_reward=torch.where(e._idle_objective_rows, (1-e.loss_terms.sum(-1)).clamp(0,1),torch.reciprocal(1+e.loss_terms.sum(-1))*e._com2_reward_values[:,0])
        torch.testing.assert_close(e._reward_buf,expected_reward)
        assert (e._com2_reward_values[e._idle_objective_rows,0]==1).all()
        assert (e.loss_terms[~e._idle_objective_rows,-6:]==0).all()
        assert (e.loss_terms[e._idle_objective_rows,:-6]==0).all()
        assert torch.isfinite(e._reward_buf).all()
        assert torch.isfinite(e.loss_terms).all()
        assert (e.loss_terms[e._tracking_mix==1, e.loss_term_names.index('excessive_stepping')]==0).all()
        checks.append(dict(tick=tick,graph_exact=True))
    assert int(e._final.minus.sum()) >= __import__('math').ceil(128*.03)
    assert e.loss_term_names[-1]=='idle_posture'
    # History reset for one row must not discard another agent's history.
    leg_before=e._leg_reversal.history[1].clone()
    foot_before=e._foot_regularizers.history[1].clone()
    ids=torch.tensor([0],device=e._device);before=e._head_reversal.history[1].clone();e._reset_envs(ids)
    assert e._head_reversal.ticks[0]==0 and e._head_reversal.raw[0]==0
    torch.testing.assert_close(e._head_reversal.history[1],before)
    assert e._foot_regularizers.ticks[0]==0 and (e._foot_regularizers.raw[0]==0).all()
    torch.testing.assert_close(e._foot_regularizers.history[1],foot_before)
    assert e._leg_reversal.ticks[0]==0 and (e._leg_reversal.raw[0]==0).all()
    torch.testing.assert_close(e._leg_reversal.history[1],leg_before)
    # Exercise both batched capture and shared per-row export, including actual reward telemetry.
    rec=MultiRecorder(e,OUT/'recorder',rows=4);(OUT/'recorder').mkdir(exist_ok=True)
    rec.start();e._time_buf.fill_(1/30);e._update_reward();e._done_buf.fill_(2);rec.capture()
    meta=rec.finish(0,0)
    assert len(meta['replay_rows'])==4
    for row in meta['replay_rows']:
        assert 'idle_stop' in row['loss_term_names']
        assert 'head_reversal' in row['loss_term_names']
        if row['final_phase_cohort']=='idle perturbed-': assert row['reward_from_loss']=='idle_recovery_bounded'
        elif not row['idle_row']: assert row['reward_from_loss']=='reciprocal_sum'
        assert len(row['frame_com2_reward_multiplier'])==2 and len(row['frame_rewards'])==2
        assert row['com2_reward_gate']['require_both'] is False
    # Perturbed idle gets new reward; normal and locomotion retain old reward.
    assert e._idle_objective_rows.any() and (~e._idle_objective_rows).any()
    # Check failure cost survives shaping unchanged.
    idle_ids=torch.where(e._final.minus)[0]
    assert len(idle_ids)>0
    from recovery_omni import RecoveryOmniEnv
    original_done=RecoveryOmniEnv._update_done
    def forced_base_done(env):
        env._done_buf.zero_();env._done_buf[idle_ids]=1
    before=e._reward_buf.clone()
    try:
        RecoveryOmniEnv._update_done=forced_base_done
        e._update_done()
    finally: RecoveryOmniEnv._update_done=original_done
    failed=idle_ids[e._done_buf[idle_ids]==1]
    assert len(failed)==len(idle_ids)>0
    torch.testing.assert_close(e._reward_buf[failed],before[failed]-100)

    import numpy as np
    z=np.load(OUT/'recorder/replay.npz')
    for i,row in enumerate(meta['replay_rows']):
        suffix='' if i==0 else '_'+str(i)
        terms=z['loss_terms'+suffix]
        names=row['loss_term_names'];keep=[j for j,n in enumerate(names) if n!='auto_phase']
        total=terms[1:,keep].sum(-1)
        expected=(1-total).clip(0,1) if row['reward_from_loss']=='idle_recovery_bounded' else 1/(1+total)
        expected*=np.asarray(row['frame_com2_reward_multiplier'])[1:]
        assert np.allclose(expected,np.asarray(row['frame_rewards'])[1:],atol=1e-6)
    # Exact boundaries: either violation suffices; idle ignores direction.
    v=torch.tensor([[3.,0.],[0.,1.],[1.,0.],[0.,0.]],device='cuda');target=torch.tensor([[1.,0.]]*4,device='cuda')
    f,_,_=com2_reward_gate(v,target,torch.eye(2,device='cuda').repeat(4,1,1),torch.zeros(4,2,device='cuda'),torch.tensor([False,False,False,True],device='cuda'))
    torch.testing.assert_close(f,torch.tensor([.001,.001,1.,1.],device='cuda'),atol=1e-7,rtol=1e-5)
    result=dict(passed=True,source_sha256=hashlib.sha256((ROOT/'idle-recovery-source.zip').read_bytes()).hexdigest(),checks=checks,reset_isolation=True,recorder_rows=4,terminal_penalty_rows=len(failed),gate_endpoints=f.cpu().tolist(),
        weights=cfg['perturbed_motion']['leg_reversal']['weights'],idle_minus=int(e._final.minus.sum()))
    (OUT/'complete.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'failure.txt').write_text(traceback.format_exc());raise

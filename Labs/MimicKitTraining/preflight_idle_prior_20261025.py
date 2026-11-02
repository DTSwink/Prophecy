"""Small isolated live-device check of P-minus history and captured reward timing."""
import os,sys,json,traceback
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'idle-prior-check'
sys.path[:0]=[str(OUT/'pipeline'),str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from lossless_runtime import TrainingRewardGraph,REWARD_BUFFERS
from prior_handoff import tracking_handoff

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6841)
    cfg=yaml.safe_load((OUT/'prepared/env_config.yaml').read_text())
    ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ['engine','agent']]
    e=PerturbedOmniEnv(cfg,ec,128,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    a._init_train();a.set_mode(AgentMode.TRAIN);a._curr_obs,a._curr_info=a._reset_envs()
    assert e._final.minus.any() and (e._prior_index[e._final.minus]>=0).all()
    assert cfg['perturbed_motion']['ae_mse_weight']==0
    e._dispatch_no_getups=True
    e._dispatch_empty_getup_ids=torch.empty(0,device=e._device,dtype=torch.long)
    # Materialize lazy engine state before comparing eager and captured rewards.
    e._update_reward();e._update_reward()
    graph=TrainingRewardGraph(e);checks=[]
    buffers=[getattr(e,n) for n in REWARD_BUFFERS]+[getattr(e._prior,n) for n in ['positions','rotations','valid']]
    for tick,last in [(2,-1),(59,-1),(60,60),(90,60),(105,60),(119,60),(120,120),(150,120),(165,120),(180,180)]:
        e._time_buf.fill_(tick/30.);e._final.last_kick[e._final.minus]=last
        saved=[v.clone() for v in buffers];e._update_reward();expected=[v.clone() for v in buffers]
        for v,s in zip(buffers,saved):v.copy_(s)
        graph()
        for name,v,s in zip(REWARD_BUFFERS+["prior_positions","prior_rotations","prior_valid"],buffers,expected):
            torch.testing.assert_close(v,s,rtol=0,atol=0,equal_nan=True,msg=lambda m: str((tick,last,name))+"\n"+m)
        mix=tracking_handoff(torch.round(e._time_buf*30),e._perturbed_rows,e._final.minus,e._final.last_kick,30,30)
        torch.testing.assert_close(e._tracking_mix,mix,rtol=0,atol=0)
        assert torch.isfinite(e._reward_buf).all()
        if last>=0 and tick-last<=30:assert (e.loss_terms[e._final.minus,:4]==0).all()
        checks.append(dict(tick=tick,last_push=last,minus_mix=float(e._tracking_mix[e._final.minus][0]),graph_exact=True))
    result=dict(passed=True,checks=checks,prior_rows=len(e._prior_ids),minus_rows=int(e._final.minus.sum()),com2_weight=e._com2_loss_weight)
    (OUT/'complete.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'failure.txt').write_text(traceback.format_exc());raise

"""Isolated A/B of exact math dispatch changes; production stays untouched."""
import sys,json,time,os,traceback,types
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024'
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')];os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
import absolute_walk,perturbed_omni,kl_guard

@torch.jit.script
def aligned_device(actual:torch.Tensor,reference:torch.Tensor):
    shift=actual[:,:1]-reference[:,:1]
    shift=torch.cat((shift[...,:2],shift[...,2:]*0.),dim=-1)
    return reference+shift

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6818)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    e=PerturbedOmniEnv(cfg,ec,2048,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];b=json.loads((run/'backup_status.json').read_text());restore(a,run/Path(b['key']).name)
    a._init_train();a.set_mode(AgentMode.TRAIN);a._curr_obs,a._curr_info=a._reset_envs()
    for i in range(2):a._iter=i;a._train_iter()
    original=absolute_walk.aligned_positions
    # Both callsites, including the unused get-up alignment, use identical arithmetic.
    for n in [0,1,7,2048]:
        x=torch.randn(n,15,3,device='cuda');y=torch.randn_like(x)
        torch.testing.assert_close(aligned_device(x,y),original(x,y),atol=0,rtol=0)
    rows=[]
    for mode in [False,True,True,False]:
        absolute_walk.aligned_positions=aligned_device if mode else original
        perturbed_omni.aligned_positions=absolute_walk.aligned_positions
        for _ in range(2):
            torch.cuda.synchronize();start=time.perf_counter();a._train_iter();torch.cuda.synchronize()
            rows.append(dict(device_alignment=mode,seconds=time.perf_counter()-start));print(json.dumps(rows[-1]),flush=True)
    (OUT/'alignment-ab.json').write_text(json.dumps(dict(measurements=rows,exact_alignment=True),indent=2))
    # Save the reference implementation's source for the next graph investigation.
    import inspect
    import mujoco_warp._src.smooth as smooth
    (OUT/'solve_m_source.txt').write_text(inspect.getsource(smooth._solve_LD_sparse))
    (OUT/'ab-complete.json').write_text(json.dumps(dict(checkpoint=b,complete=True)))

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'ab-failure.txt').write_text(traceback.format_exc());raise

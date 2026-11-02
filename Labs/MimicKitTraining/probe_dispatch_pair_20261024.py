"""Controlled, bounded timing. Main trainer is resumed even if this probe dies."""
import json,os,signal,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024'
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')];os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
from probe_reward_graph_20261024 import optimize_empty_getups,RewardGraph
from probe_kick_graph_20261024 import GraphKicks
from final_locomotion import ArticulatedKicks
import absolute_walk,perturbed_omni

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6822)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    e=PerturbedOmniEnv(cfg,ec,2048,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];b=json.loads((run/'backup_status.json').read_text());restore(a,run/Path(b['key']).name)
    a._init_train();a.set_mode(AgentMode.TRAIN);a._curr_obs,a._curr_info=a._reset_envs()
    for _ in range(2):a._train_iter()
    names=['_update_reward','_base_perturbed_tracking_losses','_refresh_reward_rotations','_target_positions']
    original={n:getattr(e,n) for n in names};original_alignment=absolute_walk.aligned_positions
    optimize_empty_getups(e);optimized={n:getattr(e,n) for n in names};optimized_alignment=absolute_walk.aligned_positions
    optimized['_update_reward']=RewardGraph(e)
    k=ArticulatedKicks(e._engine);g=GraphKicks(e._engine)
    s=e._engine._solver
    e._engine._sim_state.pre_step_update();s._update_mjc_data(s.mjw_data,e._engine._sim_model,e._engine._sim_state.raw_state)
    import mujoco_warp as mjw
    for f in [mjw.kinematics,mjw.com_pos,mjw.crb,mjw.factor_m]:f(s.mjw_model,s.mjw_data)
    g.basis()
    def select(mode):
        for n,v in (optimized if mode else original).items():setattr(e,n,v)
        absolute_walk.aligned_positions=optimized_alignment if mode else original_alignment
        perturbed_omni.aligned_positions=absolute_walk.aligned_positions
        e._final.kicker=g if mode else k
    select(True)
    for _ in range(2):a._train_iter()
    torch.cuda.synchronize()
    mainpid=2180;proc=Path('/proc')/str(mainpid)/'cmdline'
    assert sys.argv[1].encode() in proc.read_bytes() and b'pipeline/train.py' in proc.read_bytes()
    status=json.loads((run/'status.json').read_text());assert status['state']=='training' and time.time()-status['updated_unix']<180
    backup=json.loads((run/'backup_status.json').read_text());assert time.time()-backup['verified_unix']<600
    assert not (run/'finished.json').exists()
    guardcode="import os,signal,time;from pathlib import Path;time.sleep(60);p=Path('/proc/2180/cmdline');"+f"\nif p.exists() and {sys.argv[1]!r}.encode() in p.read_bytes():os.kill(2180,signal.SIGCONT)"
    guard=subprocess.Popen([sys.executable,'-c',guardcode],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    paused=False;rows=[];start=time.time()
    try:
        os.kill(mainpid,signal.SIGSTOP);paused=True
        (OUT/'controlled-main-pause.json').write_text(json.dumps(dict(pid=mainpid,guard=guard.pid,started=start,maximum_seconds=60)))
        time.sleep(.3)
        for mode in [False,True,True,False]:
            select(mode)
            for _ in range(2):
                torch.cuda.synchronize();t=time.perf_counter();a._train_iter();torch.cuda.synchronize()
                rows.append(dict(optimized=mode,seconds=time.perf_counter()-t));print(json.dumps(rows[-1]),flush=True)
                assert time.time()-start<50,'Bounded measurement window exceeded'
    finally:
        if paused:os.kill(mainpid,signal.SIGCONT)
        guard.terminate();guard.wait(timeout=5)
        (OUT/'controlled-main-resumed.json').write_text(json.dumps(dict(pid=mainpid,resumed=time.time(),pause_seconds=time.time()-start)))
    (OUT/'controlled-dispatch-complete.json').write_text(json.dumps(dict(checkpoint=b,main_checkpoint=backup,measurements=rows,pause_seconds=time.time()-start),indent=2))

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'controlled-dispatch-failure.txt').write_text(traceback.format_exc());raise

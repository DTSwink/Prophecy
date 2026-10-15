"""Bounded threshold/accounting, physical reconstruction and graph overhead tests."""
import os,sys,io,json,zipfile,time,tempfile
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(ROOT/'impact_test/MimicKit/mimickit'))
import torch,numpy as np,yaml
import run as upstream
from learning.ppo_agent import PPOAgent
from learning.base_agent import AgentMode
from amp_standing import register_network
from world_pose import WorldPoseEnv
from observe import Recorder
from util import torch_util

def load(path):
    with zipfile.ZipFile(path) as z:
        cfg,ecfg,acfg=[yaml.safe_load(z.read(n+'_config.yaml')) for n in ('env','engine','agent')]
        model=torch.load(io.BytesIO(z.read('model.pt')),map_location='cuda:0',weights_only=True)
        with np.load(io.BytesIO(z.read('replay.npz'))) as a:recorded=a['pose'].copy()
    cfg['floor_impact_limit_n']=2000.;ecfg['track_ground_contact_peaks']=True
    return cfg,ecfg,acfg,model,recorded

def main():
    started=time.perf_counter();report={}
    torch.set_num_threads(1);upstream.mp_util.init(0,1,'cuda:0',6746);register_network();os.chdir(ROOT/'MimicKit')
    cfg,ecfg,acfg,model,recorded=load(sys.argv[1])
    env=WorldPoseEnv(cfg,ecfg,1,'cuda:0',False);engine=env._engine;char=env._get_char_id();kin=env._kin_char_model
    agent=PPOAgent(acfg,env,'cuda:0');agent.load_state_dict(model);agent.eval();agent.set_mode(AgentMode.TEST)
    first=torch.tensor(recorded[0],device='cuda:0');q=first[:,3:]
    joint=torch.stack([torch_util.quat_mul(torch_util.quat_conjugate(kin._local_rotation[j]),torch_util.quat_mul(torch_util.quat_conjugate(q[kin.get_parent_id(j)]),q[j])) for j in range(1,kin.get_num_joints())])[None]
    dofs=kin.rot_to_dof(joint);original_reset=env._reset_char
    def reset(ids):
        original_reset(ids);engine.set_root_pos(ids,char,first[None,0,:3]);engine.set_root_rot(ids,char,first[None,0,3:]);engine.set_dof_pos(ids,char,dofs)
    env._reset_char=reset
    with torch.no_grad():
        obs,info=env.reset();poses=[torch.cat((engine.get_body_pos(char),engine.get_body_rot(char)),-1)[0].cpu().numpy().copy()];peaks=[];reasons=[]
        for _ in range(len(recorded)-1):
            action,_=agent._decide_action(obs,info);obs,_,_,info=env.step(action)
            poses.append(torch.cat((engine.get_body_pos(char),engine.get_body_rot(char)),-1)[0].cpu().numpy().copy())
            peaks.append(engine.get_ground_contact_peak_forces(char)[0].cpu().numpy().copy());reasons.append(int(env.failure_reason[0]))
    peaks=np.stack(peaks);poses=np.stack(poses);names=list(engine.get_obj_body_names(char));arm=names.index('right_lower_arm')
    error=float(np.linalg.norm(poses[:,:,:3]-recorded[:,:,:3],axis=-1).max())
    assert error<.0001,error
    assert abs(float(peaks[:,arm].max())-2759.942)<2,peaks[:,arm]
    assert int(peaks[:,arm].argmax())+1==5 and reasons[4]&2
    report['reconstruction']=dict(max_position_error_m=error,forearm_peak_N=float(peaks[:,arm].max()),peak_tick=5,reason_by_tick=reasons,graph_enabled=engine._graph is not None)
    del agent,env,engine
    cfg,ecfg,acfg,model,_=load(sys.argv[2]);env=WorldPoseEnv(cfg,ecfg,512,'cuda:0',False);engine=env._engine;char=env._get_char_id()
    agent=PPOAgent(acfg,env,'cuda:0');agent.load_state_dict(model);agent.eval();agent.set_mode(AgentMode.TEST)
    obs,info=env.reset();assert obs.shape==(512,140)
    names=list(engine.get_obj_body_names(char));li,ri=env._left_foot_id,env._right_foot_id;arm=names.index('right_lower_arm');hand=names.index('right_hand')
    gp,gr,gpeak=engine.get_body_pos,engine.get_body_rot,engine.get_ground_contact_peak_forces
    pos=gp(char).clone();rot=gr(char).clone();pos[:,li]=0.;pos[:,ri]=0.;pos[5,ri,0]=env._feet_max_width+.01
    fake=torch.zeros((512,len(names)),device='cuda:0');fake[0,arm]=1999.9;fake[1,arm]=2000.;fake[2,arm]=2000.1
    fake[3,li]=100000.;fake[3,ri]=100000.;fake[4,hand]=2001.;fake[5,arm]=3000.
    engine.get_body_pos=lambda _:pos;engine.get_body_rot=lambda _:rot;engine.get_ground_contact_peak_forces=lambda _:fake
    try:
        for tick in (1,30,60):
            env._timestep_buf[:]=tick;env._time_buf[:]=tick/30;env._update_reward();env._update_done()
            assert env.failure_reason[:6].tolist()==[0,0,2,0,2,3]
            torch.testing.assert_close(env.loss_terms[:,-1],torch.where(env.failure_reason>0,env.loss_terms[:,:3].sum(-1)*(60-tick),0.))
            torch.testing.assert_close(env._reward_buf,-env.loss_terms.sum(-1))
            assert env._done_buf[[2,4,5]].tolist()==[1,1,1]
        assert env.floor_peak_body[2]==arm and env.floor_peak_body[4]==hand
    finally:engine.get_body_pos=gp;engine.get_body_rot=gr;engine.get_ground_contact_peak_forces=gpeak
    env.reset(torch.tensor([2],device='cuda:0'));assert env.failure_reason[2]==0 and env.floor_peak_body[2]==-1 and env.failure_reason[5]==3
    report['contract']=dict(strict_threshold=True,feet_exempt=True,hand_included=True,both_failures_charged_once=True,remaining_ticks=[1,30,60],partial_reset=True,observations=140)
    # Rebuild the same graph with/without sensor work; identical reset seed/actions.
    timings={};endposes={}
    with torch.no_grad():
        for enabled in (False,True,False,True):
            engine._track_ground_contact_peaks=enabled;engine._build_graphs();env._reset_rng.manual_seed(20261015);obs,info=env.reset()
            action,_=agent._decide_action(obs,info)
            for _ in range(10):engine.step()
            torch.cuda.synchronize();t=time.perf_counter()
            for _ in range(100):engine.step()
            torch.cuda.synchronize();elapsed=time.perf_counter()-t
            timings.setdefault(str(enabled),[]).append(elapsed/100)
            endposes[str(enabled)]=gp(char).clone()
        assert torch.isfinite(endposes['True']).all()
        report['benchmark']=dict(control_tick_seconds=timings,overhead_ratio=float(np.mean(timings['True'])/np.mean(timings['False'])),worlds=512,graph_enabled=engine._graph is not None)
        obs,info=env.reset();rec=Recorder(env,Path(sys.argv[3]).parent,filename='floor-impact-test-replay.npz');rec.start()
        for _ in range(60):
            action,_=agent._decide_action(obs,info);obs,_,done,info=env.step(action)
            if bool(done[0]):break
        rec.finish(0,0)
        with np.load(rec.directory/rec.filename) as a:
            m=json.loads(str(a['metadata']));terms=a['loss_terms'];imp=a['floor_impacts']
            assert len(m['frame_floor_peak_n'])==len(a['pose']) and np.isfinite(imp).all()
            assert m['frame_failure_reason'][-1] in (1,2,3)
            n=len(terms)-1
            assert abs(terms[-1,-1]-terms[-1,:3].sum()*(60-n))<1e-5
            report['replay']=dict(ticks=n,reason=m['frame_failure_reason'][-1],peak_N=m['frame_floor_peak_n'][-1],body=names[m['frame_floor_peak_body'][-1]],loss_names=m['loss_term_names'])
    report['elapsed_seconds']=time.perf_counter()-started;Path(sys.argv[3]).write_text(json.dumps(report,indent=2));print('IMPACT_TEST',json.dumps(report),flush=True)

if __name__=='__main__':main()

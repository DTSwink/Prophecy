"""Verify the 2.2kN arms/head-only mask and real resumed-policy episodes."""
import os,sys,io,json,zipfile,time
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

def main():
    started=time.perf_counter();archive=Path(sys.argv[1]);dest=Path(sys.argv[2])
    with zipfile.ZipFile(archive) as z:
        cfg,ecfg,acfg=[yaml.safe_load(z.read(n+'_config.yaml')) for n in ('env','engine','agent')]
        model=torch.load(io.BytesIO(z.read('model.pt')),map_location='cuda:0',weights_only=True)
    selected=['head','right_upper_arm','right_lower_arm','right_hand','left_upper_arm','left_lower_arm','left_hand']
    cfg.update(floor_impact_limit_n=2200.,floor_impact_bodies=selected)
    torch.set_num_threads(1);upstream.mp_util.init(0,1,'cuda:0',6747);register_network();os.chdir(ROOT/'MimicKit')
    env=WorldPoseEnv(cfg,ecfg,512,'cuda:0',False);engine=env._engine;char=env._get_char_id()
    agent=PPOAgent(acfg,env,'cuda:0');agent.load_state_dict(model);agent.eval();agent.set_mode(AgentMode.TEST)
    obs,info=env.reset();assert obs.shape==(512,140)
    names=list(engine.get_obj_body_names(char));gp,gpeak=engine.get_body_pos,engine.get_ground_contact_peak_forces
    pos=gp(char).clone();pos[:,env._left_foot_id]=0;pos[:,env._right_foot_id]=0
    fake=torch.zeros((512,len(names)),device='cuda:0')
    for i in range(len(names)):fake[i,i]=2500.
    h=names.index('head');fake[20,h]=2199.9;fake[21,h]=2200.;fake[22,h]=2200.1
    fake[23,h]=2300.;pos[23,env._right_foot_id,0]=env._feet_max_width+.01
    engine.get_body_pos=lambda _:pos;engine.get_ground_contact_peak_forces=lambda _:fake
    try:
        env._timestep_buf[:]=5;env._time_buf[:]=5/30;env._update_reward();env._update_done()
        expected=[2 if n in selected else 0 for n in names]
        assert env.failure_reason[:len(names)].tolist()==expected
        assert env.failure_reason[20:24].tolist()==[0,0,2,3]
        torch.testing.assert_close(env.loss_terms[:,-1],torch.where(env.failure_reason>0,env.loss_terms[:,:3].sum(-1)*55,0.))
        torch.testing.assert_close(env._reward_buf,-env.loss_terms.sum(-1))
    finally:engine.get_body_pos=gp;engine.get_ground_contact_peak_forces=gpeak
    obs,info=env.reset();rec=Recorder(env,dest.parent,filename='arms-head-test-replay.npz');rec.start();counts=[0,0,0,0]
    with torch.no_grad():
        for _ in range(60):
            action,_=agent._decide_action(obs,info);obs,_,done,info=env.step(action)
            assert torch.isfinite(obs).all() and torch.isfinite(env.loss_terms).all()
            ended=(done!=0).nonzero().flatten()
            for k in range(1,4):counts[k]+=int((env.failure_reason[ended]==k).sum())
            if len(ended):
                obs,info=env.reset(ended)
    rec.finish(0,0)
    with np.load(rec.directory/rec.filename) as a:
        m=json.loads(str(a['metadata']));terms=a['loss_terms'];n=len(terms)-1
        assert m['floor_impact_limit_n']==2200 and m['floor_impact_bodies']==selected
        for b in m['frame_floor_peak_body']:
            assert b==-1 or names[b] in selected
        assert abs(terms[-1,-1]-terms[-1,:3].sum()*(60-n))<1e-5
    report=dict(selected=selected,excluded=[n for n in names if n not in selected],strict_threshold=True,
        unchanged_inputs=140,single_remaining_charge=True,worlds=512,finite_policy_ticks=60,failures_by_reason=counts,
        replay_ticks=n,replay_peak_N=m['frame_floor_peak_n'][-1],replay_body=(names[m['frame_floor_peak_body'][-1]] if m['frame_floor_peak_body'][-1]>=0 else None),
        replay_reason=m['frame_failure_reason'][-1],seconds=time.perf_counter()-started)
    dest.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()

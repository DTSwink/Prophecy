"""Bounded local checkpoint rollout with corrected wrists; never updates weights."""
import argparse, json, hashlib
import preflight as s
import torch, numpy as np, yaml
from resume import restore
from util import torch_util as q

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--test-ticks',type=int,default=301);parser.add_argument('--train-ticks',type=int,default=160);args=parser.parse_args()
    assert args.test_ticks>=110 and args.train_ticks>=60
    s.os.chdir(s.PACKAGE/'MimicKit')
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    s.wp.init();s.wp.set_device('cuda:0');s.mp_util.init(0,1,'cuda:0',6748)
    torch.manual_seed(20261017);np.random.seed(20261017)
    cfg,ec,ac=[yaml.safe_load((s.OUT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    env=s.CrawlEnv(cfg,ec,16,'cuda:0',False)
    agent=s.OmniPPOAgent(ac,env,'cuda:0')
    checkpoint=s.Path(json.loads((s.OUT/'resume-checkpoint.json').read_text())['local_path'])
    resumed=restore(agent,checkpoint);agent._init_train();agent.eval()
    geometry=json.loads((s.OUT/'geometry.json').read_text())
    specs=[]
    for name in ('right_hand','left_hand'):
        j=env._kin_char_model.get_body_names().index(name)
        shape=next(x for x in geometry['shapes'] if x['bone']==name)
        t=lambda x:torch.tensor(x,device='cuda:0',dtype=torch.float32)
        specs.append((j,t(shape['position']),t(shape['axes']),t(shape['dimensions'])/2))
    reports=[]
    preview=s.OUT/'contact-cleanup-preview';preview.mkdir(exist_ok=True)
    recorder=s.MultiRecorder(env,preview,12);recorder.phase_agent=agent
    for mode in (s.AgentMode.TEST,s.AgentMode.TRAIN):
        agent.set_mode(mode);obs,info=agent._reset_envs();heights=[]
        ticks=args.test_ticks if mode==s.AgentMode.TEST else args.train_ticks
        if mode==s.AgentMode.TEST:recorder.start()
        for tick in range(ticks):
            with torch.no_grad():action,_=agent._decide_action(obs,info)
            obs,reward,done,info=env.step(action)
            assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
            pos=env._engine.get_body_pos(env._get_char_id())
            rot=q.quat_to_matrix(env._engine.get_body_rot(env._get_char_id()))
            heights.append(torch.stack([pos[:,j,2]+(rot[:,j]@p)[:,2]-(rot[:,j]@axes)[:,2,:].abs()@half for j,p,axes,half in specs],-1).cpu().numpy())
            ids=torch.nonzero(done!=0).flatten()
            if len(ids):obs,info=agent._reset_envs(ids)
            if tick%100==0:print(json.dumps(dict(stage='checkpoint_rollout',mode=str(mode),tick=tick,total_ticks=ticks)),flush=True)
        env._engine.validate_transfer_solver()
        if mode==s.AgentMode.TEST:
            recorder.finish(resumed['iteration_offset']-1,resumed['prior_samples'],dict(worlds=16,training_action_noise_std=.05,rollout_action_noise_std=0.,local_validation=True))
            from replay import convert
            converted=convert(preview/'replay.npz',geometry,'mimickit_crawl_cleaned_contacts_preview')
            target=s.Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs/mimickit_crawl_cleaned_contacts_preview/debug')
            target.mkdir(parents=True,exist_ok=True)
            (target/'last_batch_rollout.json').write_text(json.dumps(converted))
        h=np.array(heights)
        reports.append(dict(mode=str(mode),ticks=ticks,hand_minimum_m=h.min(axis=(0,1)).tolist(),idle_minimum_m=h[:,:env._idle_rows].min(axis=(0,1)).tolist(),crawl_minimum_m=h[:,env._idle_rows:].min(axis=(0,1)).tolist(),fraction_below_2cm=float((h<-.02).mean())))
    result=dict(resumed=resumed,checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),limits_sha256=hashlib.sha256((s.PACKAGE/'assets/uefn/limits.json').read_bytes()).hexdigest(),motion_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (s.PACKAGE/'motions').glob('*.pkl')},worlds=16,weight_updates=0,reports=reports,finite_and_solver_checks_passed=True)
    (s.OUT/'resume-validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':main()

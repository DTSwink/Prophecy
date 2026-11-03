"""Isolated adaptation trial. Same checkpoint, PPO/sample budget and evaluation seeds."""
import os,sys,json,time,argparse,hashlib,shutil,xml.etree.ElementTree as ET
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'crawl-traction-20261102'
sys.path[:0]=[str(OUT),str(OUT/'pipeline'),str(ROOT/'MimicKit/mimickit'),str(OUT/'assets/MimicKitTransfer')]
import numpy as np,torch,warp as wp,yaml
from probe import grip
from slow_loco_disabled import DisabledSlowLocoEnv
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util
from resume import restore

def write(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(path)

def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--grip',type=float,default=1.);p.add_argument('--mass',type=float,default=1.);p.add_argument('--arm',type=float,default=1.);p.add_argument('--updates',type=int,default=100);p.add_argument('--seed',type=int,default=601);a=p.parse_args()
    assert a.name.replace('_','').isalnum()
    dest=OUT/'adaptation'/a.name;dest.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(a.seed)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6796);os.chdir(ROOT/'MimicKit')
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    cfg.update(motion_file=str(ROOT/'prepared/motions.yaml'),omni_manifest=str(ROOT/'prepared/manifest.json'))
    assets=OUT/'assets'
    if a.mass!=1:
        assets=dest/'assets';shutil.copytree(OUT/'assets',assets,dirs_exist_ok=True)
        xml=assets/'uefn/humanoid_uefn.xml';tree=ET.parse(xml);phys=assets/'uefn/physics.json';data=json.loads(phys.read_text())
        for b in tree.findall('.//body'):
            name=b.get('name','')
            if not any(w in name for w in ('thigh','shin','foot')):continue
            inert=b.find('inertial');assert inert is not None
            for k in ('mass','diaginertia'):inert.set(k,' '.join(str(float(v)*a.mass) for v in inert.get(k).split()))
            for k in ('mass','inertia','drag_mass','drag_first','drag_second'):data['bodies'][name][k]=(np.asarray(data['bodies'][name][k])*a.mass).tolist()
        tree.write(xml,encoding='utf-8',xml_declaration=True);data['asset_sha256']=hashlib.sha256(xml.read_bytes()).hexdigest();phys.write_text(json.dumps(data))
        cfg['char_file']=str(xml)
    ec['uefn_asset_directory']=str(assets/'uefn')
    N=2048;factor=wp.full(N,a.grip,dtype=float,device='cuda:0')
    import contact_manifolds_gpu as manifold
    previous=manifold.prepare
    def prepare(p,ncontact,friction,model,data,inverse,error,mass,inertia):
        wp.launch(grip,(N,friction.shape[1]),inputs=[ncontact,p.contact_ids,data.contact.geom,model.geom_bodyid,friction,factor],device='cuda:0')
        return previous(p,ncontact,friction,model,data,inverse,error,mass,inertia)
    manifold.prepare=prepare
    env=DisabledSlowLocoEnv(cfg,ec,N,'cuda:0',False);eng=env._engine;char=env._get_char_id()
    assert (env._codes==12).all() and (env._rates==.5).all()
    old=env._update_head_strength
    def strength():old();env._motor_mask[:,6:20].mul_(a.arm)
    env._update_head_strength=strength
    agent=OmniPPOAgent(ac,env,'cuda:0');restored=restore(agent,OUT/'checkpoint_0020426.zip')
    assert restored['optimizer_restored'] and restored['normalizer_restored']
    write(dest/'settings.json',dict(**vars(a),worlds=N,checkpoint=20426,resume=restored,mass_kg=float(eng._sim_model.body_mass.numpy().reshape(N,15)[0].sum()),reward_unchanged=True,training_noise=.05))
    def evaluate(label):
        agent.eval();agent.set_mode(AgentMode.TEST);torch.manual_seed(271828)
        obs,info=env.reset();start=eng.get_body_pos(char)[:,0].clone();alive=torch.ones(N,dtype=torch.bool,device='cuda:0')
        first=torch.full((N,),300,device='cuda:0',dtype=torch.long);terminal=start.clone();last=start.clone();travel=torch.zeros(N,device='cuda:0')
        paths=[];live=[];footage=[];losses=[]
        for t in range(300):
            with torch.no_grad():act,_=agent._decide_action(obs,info);obs,r,done,info=env.step(act)
            pos=eng.get_body_pos(char)[:,0];ended=alive&(done!=0);first[ended]=t+1;terminal[alive]=pos[alive]
            if t>=30:travel+=torch.where(alive,pos[:,0]-last[:,0],0.)
            last=pos.clone();alive &= done!=1
            if t%30==29:paths.append((pos-start).cpu().numpy());live.append(alive.cpu().numpy())
            footage.append(eng.get_body_pos(char)[:8].cpu().numpy().copy());losses.append(env.loss_terms[:8].cpu().numpy().copy())
        duration=(first-30).clamp_min(1)/30.;speed=travel/duration
        final=terminal-start
        # Multiple positive one-second windows after the inherited initial velocity dissipates.
        path=np.array(paths);valid=np.array(live);dx=np.diff(path[:,:,0],axis=0)
        sustained=(valid[7] & (dx[3:8]>.05).all(0))
        result=dict(mean_progress_m=float(final[:,0].mean()),median_progress_m=float(final[:,0].median()),mean_late_speed_m_s=float(speed.mean()),median_late_speed_m_s=float(speed.median()),mean_first_episode_ticks=float(first.float().mean()),survive_8s_fraction=float(valid[7].mean()),survive_10s_fraction=float(valid[-1].mean()),sustained_crawl_fraction=float(sustained.mean()),mean_lateral_displacement_m=float(final[:,1].abs().mean()),mean_terminal_pelvis_z=float(terminal[:,2].mean()),policy_noise=0,episodes=N)
        write(dest/(label+'.json'),result);np.savez_compressed(dest/(label+'.npz'),path=path,alive=valid,first_failure=first.cpu().numpy(),late_speed=speed.cpu().numpy(),pose=np.array(footage),loss=np.array(losses))
        print('EVALUATION',label,json.dumps(result),flush=True)
        return result
    before=evaluate('before')
    agent._init_train();torch.manual_seed(a.seed)
    agent._curr_obs,agent._curr_info=agent._reset_envs();started=time.time();history=[]
    for i in range(a.updates):
        agent._iter=i;stats=agent._train_iter();agent._sample_count=agent._update_sample_count()
        assert all(torch.isfinite(v).all() for v in agent.parameters())
        eng.validate_transfer_solver();assert float(eng._dof_forces[0][:,20:].abs().max())<1e-7
        if i%10==9:
            row=dict(update=i+1,samples=(i+1)*N*32,elapsed_seconds=time.time()-started,mean_return=float(stats['mean_return']),mean_episode_seconds=float(stats['mean_ep_len'])/30)
            history.append(row);write(dest/'progress.json',history);agent.save(str(dest/'model.pt'));print('UPDATE',json.dumps(row),flush=True)
    train_seconds=time.time()-started;agent.save(str(dest/'model.pt'));after=evaluate('after')
    write(dest/'complete.json',dict(settings=vars(a),before=before,after=after,updates=a.updates,samples=a.updates*N*32,training_seconds=train_seconds,passed=True))
    print('COMPLETE',a.name,flush=True)

if __name__=='__main__':main()

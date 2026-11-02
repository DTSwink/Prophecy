"""CPU-only diagnostic of restored network on real precomputed reset poses."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import sys,json,zipfile,io,pickle,copy,types
from pathlib import Path
import numpy as np
import torch
import gymnasium.spaces as spaces
ROOT=Path(__file__).resolve().parents[2];P=ROOT/'Saved/MimicKitSlowLoco/package';D=ROOT/'Saved/MimicKitSlowLoco/disabled-curriculum-deploy-20261102'
sys.path[:0]=[str(P/'pipeline'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
from learning.ppo_model import PPOModel
from learning.nets import net_builder
def build_net(inputs,activation):
    size=sum(np.prod(v.shape) for v in inputs.values());layers=[]
    for width in (1024,1024,512):
        layers.extend((torch.nn.Linear(int(size),width),activation()));size=width
    return torch.nn.Sequential(*layers),{}
net_builder.fc_1024_1024_512=types.SimpleNamespace(build_net=build_net)
class OmniPPOModel(PPOModel):
    def __init__(self,config,env):
        super().__init__(config,env);self._phase_out=torch.nn.Linear(512,2)

from device_quaternion import physical_observations
from repair_slow_targets import Geometry
from disabled_limb_rules import valid_codes,migrate_disabled_arm_flags
import yaml

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    cp=json.loads((D/'resume-checkpoint.json').read_text())['local']
    with zipfile.ZipFile(cp) as z:
        state=torch.load(io.BytesIO(z.read('resume_state.pt')),map_location='cpu',weights_only=False)
        model=torch.load(io.BytesIO(z.read('model.pt')),map_location='cpu',weights_only=True)
        ac=yaml.safe_load(z.read('agent_config.yaml'));ec=yaml.safe_load(z.read('env_config.yaml'))
    env=types.SimpleNamespace(get_obs_space=lambda:spaces.Box(-np.inf,np.inf,(160,),dtype=np.float32),
        get_action_space=lambda:spaces.Box(-np.inf,np.inf,(34,),dtype=np.float32))
    net=OmniPPOModel(ac['model'],env);net.load_state_dict({k[len('_model.'):]:v for k,v in model.items() if k.startswith('_model.')})
    g=Geometry();kin=g.k;names=[r['id'] for r in json.loads((P/'prepared/manifest.json').read_text())['motions']]
    bank=np.load(D/'disabled_inits.npz');obs=[];groups=[]
    for m,name in enumerate(names):
        clip=pickle.load(open(P/'motions'/f'{name}.pkl','rb'));frames=clip['frames']
        for c in sorted({c for k in (1,2,3) for c in valid_codes(name,k)}):
            for sample in (3,19,35,51):
                f=frames[round(float(bank['times'][m,c,sample])*clip['fps'])].astype(np.float32).copy()
                f[6:]=bank['dof_pos'][m,c,sample]
                dof=torch.from_numpy(f[6:])[None];joints=kin.dof_to_rot(dof)
                from util import torch_util as q
                root=torch.from_numpy(f[:3])[None];rot=q.exp_map_to_quat(torch.from_numpy(f[3:6])[None])
                pos,_=kin.forward_kinematics(root,rot,joints)
                key=pos[:,[g.names.index(n) for n in ec['key_bodies']]]
                physical=physical_observations(root,rot,torch.zeros_like(root),torch.zeros_like(root),joints,torch.zeros_like(dof),key,True,True)
                command=torch.zeros((1,8));command[0,m if m<8 else m-4]=1. if m<8 else -1.
                flags=torch.tensor([[0. if c&(1<<l) else 1. for l in range(4)]])
                phase=torch.tensor([[1.,0.]])
                obs.append(torch.cat((physical,command,flags,phase),-1));groups.append((name,c))
    obs=torch.cat(obs);mean=model['_obs_norm._mean'];std=model['_obs_norm._std']
    result=dict(checkpoint=14765,reset_states=len(obs),note='Synthetic terminal-target stress diagnostic, not a physics rollout')
    for fix in (False,True):
        scale=std.clone()
        if fix:scale[154:156]=1.
        x=((obs-mean)/scale).clamp(-10,10)
        net.load_state_dict({k[len('_model.'):]:v for k,v in model.items() if k.startswith('_model.')})
        with torch.no_grad():
            critic=net.eval_critic(x);action=net.eval_actor(x).mode
            desc=dict(normalized_arm_flags=x[:,154:156].unique().tolist(),critic_min=float(critic.min()),critic_max=float(critic.max()),action_abs_max=float(action.abs().max()))
        for clip in (100.,1000.):
            net.load_state_dict({k[len('_model.'):]:v for k,v in model.items() if k.startswith('_model.')})
            opt=torch.optim.SGD(net.get_critic_params(),lr=1e-4,momentum=.9);opt.load_state_dict(copy.deepcopy(state['critic_optimizer']))
            losses=[];norms=[]
            for step in range(32):
                pred=net.eval_critic(x).squeeze(-1);loss=((pred+100.)**2).mean()
                opt.zero_grad();loss.backward()
                norm=torch.nn.utils.clip_grad_norm_(net.get_critic_params(),clip or float('inf'))
                losses.append(float(loss));norms.append(float(norm));opt.step()
                if not all(torch.isfinite(p).all() for p in net.get_critic_params()):break
            desc['grad_clip_'+str(clip)]=dict(updates=len(losses),finite=all(torch.isfinite(p).all().item() for p in net.get_critic_params()),losses=losses,gradient_norms=norms)
        result['unit_arm_scales' if fix else 'original_scales']=desc
    norm=types.SimpleNamespace(_mean=mean.clone(),_std=std.clone(),_mean_sq=mean.double().square()+std.double().square())
    migration=migrate_disabled_arm_flags(types.SimpleNamespace(_obs_norm=norm))
    vanilla=obs.clone();vanilla[:,154:156]=1.
    assert torch.equal(((vanilla-mean)/std).clamp(-10,10),((vanilla-norm._mean)/norm._std).clamp(-10,10))
    assert torch.equal(norm._std[:154],std[:154]) and torch.equal(norm._std[156:],std[156:])
    result['migration']=migration;result['vanilla_normalized_input_identical']=True
    (D/'resume-cpu-clipping-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()

"""Read-only frozen crawl-policy test in the installed Jolt DLL, no Unreal UI."""
import os,sys,json,time,subprocess,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitSlowLoco/jolt-vibration-20261103'
P=ROOT/'Saved/MimicKitSlowLoco/package'
os.environ['OMP_NUM_THREADS']='1';os.environ['PYGLET_HEADLESS']='true'
sys.path[:0]=[str(P/'pipeline'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit'),str(ROOT/'Saved/MimicKitUEFN/dependencies')]
import numpy as np,torch,yaml,gymnasium.spaces as spaces
from scipy.spatial.transform import Rotation as R
from omni_policy import OmniPPOModel
from envs.char_env import compute_char_obs
torch.set_num_threads(1)
nodes=list(ET.parse(P/'assets/uefn/humanoid_uefn.xml').getroot().find('worldbody').iter('body'))
names=[n.get('name') for n in nodes]
limits=json.loads((P/'assets/uefn/limits.json').read_text())
props=json.loads((P/'assets/uefn/physics.json').read_text())['bodies']
parents=[-1]+[names.index(next(j['parent'] for j in limits['joints'] if j['body']==n)) for n in names[1:]]
local=[R.from_quat(np.roll(np.fromstring(n.get('quat','1 0 0 0'),sep=' '),-1)) for n in nodes]
com=np.array([props[n]['com'] for n in names])
keys=[names.index(n) for n in yaml.safe_load((OUT/'env_config.yaml').read_text())['key_bodies']]
data=np.load(OUT/'replay.npz');meta=json.loads(str(data['metadata']))
t=lambda a:torch.tensor(np.asarray(a),dtype=torch.float32)

def states(row):
    suf='' if row==0 else '_'+str(row)
    pose=data['pose'+suf].copy();v=data['world_velocities'+suf][:,:,:6].copy()
    off=R.from_quat(pose[:,:,3:].reshape(-1,4)).apply(np.tile(com,(len(pose),1))).reshape(-1,15,3)
    v[:,:,:3]+=np.cross(v[:,:,3:],off)
    return np.concatenate((pose,v),-1)

def obs(state,phase):
    rot=R.from_quat(state[:,3:7]);joints=[];vel=[]
    for i in range(1,15):
        joints.append((local[i].inv()*rot[parents[i]].inv()*rot[i]).as_quat())
        w=rot[i].inv().apply(state[i,10:13]-state[parents[i],10:13])
        vel.extend(w if len(nodes[i].findall('joint'))==3 else [w[2]])
    physical=compute_char_obs(t(state[None,0,:3]),t(state[None,0,3:7]),t(state[None,0,7:10]),t(state[None,0,10:13]),t(np.array(joints)[None]),t(np.array(vel)[None]),t(state[None,keys,:3]),True,True)
    command=np.zeros(14);command[meta['motion_onehot_order'].index('crawl')]=1;command[8:12]=[1,1,0,0];command[12:]=phase
    return torch.cat((physical,t(command[None])),-1)

class Policy:
    def __init__(self):
        class Space:
            def get_obs_space(self):return spaces.Box(-np.inf,np.inf,(160,),dtype=np.float32)
            def get_action_space(self):return spaces.Box(-np.inf,np.inf,(34,),dtype=np.float32)
        self.s=torch.load(OUT/'model.pt',map_location='cpu',weights_only=True)
        self.m=OmniPPOModel(yaml.safe_load((OUT/'agent_config.yaml').read_text())['model'],Space())
        self.m.load_state_dict({k[7:]:v for k,v in self.s.items() if k.startswith('_model.')});self.m.eval()
        self.bounds=t(json.loads((OUT/'velocity_command_bounds.json').read_text())['command_bound_rad_s'])
    @torch.no_grad()
    def __call__(self,state,phase):
        x=((obs(state,phase)-self.s['_obs_norm._mean'])/self.s['_obs_norm._std']).clamp(-10,10)
        h=self.m._actor_layers(x);a=self.m._action_dist(h).mode*self.s['_a_norm._std']+self.s['_a_norm._mean']
        pred=torch.nn.functional.normalize(self.m._phase_out(h),dim=-1,eps=1e-6)
        return a.clamp(-self.bounds,self.bounds)[0].numpy(),pred[0].numpy()

class Jolt:
    def __init__(self,state,stock):
        env={k:v for k,v in os.environ.items() if not k.startswith(('TRANSFER_','CAND_','CRAWL_'))}
        env.update(TRANSFER_RIG_VELOCITY_STEPS='100',TRANSFER_RIG_POSITION_STEPS='20',TRANSFER_TRAINING_CONTACT='1',TRANSFER_FRICTIONLESS_SELF='1')
        if stock:env['CRAWL_STOCK_CONTACT']='1'
        env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env.get('PATH','')
        with tempfile.NamedTemporaryFile(mode='w',suffix='.txt',dir=OUT,delete=False) as f:np.savetxt(f,state,fmt='%.12g')
        self.err=open(OUT/'stderr.log','a')
        self.p=subprocess.Popen([str(OUT/'fixture.exe'),f.name],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
        self.initial=self.read();Path(f.name).unlink()
        np.testing.assert_allclose(self.initial['bodies'],state,atol=1e-5,rtol=1e-5)
        properties=self.request('inspect')['body_properties']
        for i,n in enumerate(names):
            np.testing.assert_allclose(properties[i][0],props[n]['mass'],rtol=2e-5)
            np.testing.assert_allclose(properties[i][1:4],com[i],atol=2e-6)
            np.testing.assert_allclose(np.array(properties[i][4:13]).reshape(3,3),np.linalg.inv(props[n]['inertia']),atol=2e-3,rtol=2e-5)
    def read(self):
        line=self.p.stdout.readline()
        if not line:raise RuntimeError('Jolt fixture exited')
        return json.loads(line)
    def request(self,s):self.p.stdin.write(s+'\n');self.p.stdin.flush();return self.read()
    def close(self):
        if self.p.poll() is None:self.p.stdin.write('quit\n');self.p.stdin.flush();self.p.wait(5)
        self.err.close()

def metrics(s):
    v=np.diff(s[:,:,:3]-s[:,:1,:3],axis=0)*30
    h=v[:,[5,8]]
    cancel=np.array([np.linalg.norm(h[i-6:i],axis=-1).mean(0)-np.linalg.norm(h[i-6:i].mean(0),axis=-1) for i in range(6,len(h)+1)])
    return dict(forward_m=float(s[-1,0,0]-s[0,0,0]),sideways_m=float(s[-1,0,1]-s[0,0,1]),pelvis_end_height_m=float(s[-1,0,2]),
                hand_cancellation_m_s=cancel.mean(0).tolist(),hand_velocity_reversals=np.count_nonzero(np.sum(h[1:]*h[:-1],-1)<0,axis=0).tolist())

def main():
    pol=Policy();errors=[]
    for row in (0,2,5,7):
        ss=states(row);ph=np.array(meta['replay_rows'][row]['frame_phase'])
        for k in (1,2,69,150,187,229):
            a,p=pol(ss[k],ph[k,:2]);errors.append(float(np.max(abs(p-ph[k,2:4]))))
    (OUT/'observation-check.json').write_text(json.dumps({'max_phase_error':max(errors),'errors':errors},indent=2));print('MAPPING',max(errors),flush=True)
    assert max(errors)<.001,errors
    results=[]
    for row in (0,2,5,7):
      original=states(row);ph=np.array(meta['replay_rows'][row]['frame_phase'])
      for start in (1,150):
       ticks=300-start
       for stock in (False,True):
        state=original[start].copy();sim=Jolt(state,stock);history=[state.copy()];actions=[];contact=[]
        try:
          for tick in range(ticks):
            a,_=pol(state,ph[start+tick,:2]);o=sim.request('step '+' '.join(map(str,a)));state=np.array(o['bodies']);assert np.isfinite(state).all()
            history.append(state);actions.append(a);contact.append(o['ground_vertical_impulse_ns'])
        finally:sim.close()
        ss=np.array(history);label=f'row{row}-start{start}-'+('stock' if stock else 'training-contact')
        np.savez_compressed(OUT/(label+'.npz'),states=ss,actions=actions,contact_impulse=contact)
        a=150-start;b=230-start
        r=dict(label=label,row=row,start=start,ticks=ticks,stock_speculative_contacts=stock,whole=metrics(ss),window=metrics(ss[a:b+1]),reference=metrics(original[150:231]),
               no_reset=True,training_unchanged=True)
        results.append(r);print(json.dumps(r),flush=True);(OUT/'results.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()

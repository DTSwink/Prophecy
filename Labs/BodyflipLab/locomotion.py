"""Contained CPU inference using the installed Run/Upper checkpoints and original decoder.
No training, GPU, Unreal, cache writes, or physical feedback into the policies.
The requested finite run is generated on demand, then simulated in Jolt in the client.
"""
import sys, json, math, time, hashlib
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
STEPPER=Path(r'C:/Users/singerie/Documents/Cursor/stepper')
sys.path.insert(0,str(STEPPER))
import torch
torch.set_num_threads(1)
from training.ik import train_upper_pose_controller as runtime_data
from training.ik import train_upper_pose_controller_pelvis as upper_ctl
from training.ik import train_upper_pose_autoencoder as upper_data
from training.ik import upper_cached_lower as cached_data
from training.ik import visualize
from training.ik import ik_core as tl

class Locomotion:
    def __init__(self,gait="run"):
        if gait not in ("run","walk"): raise ValueError("Unknown gait")
        self.gait=gait
        self.device=torch.device('cpu')
        self.lower_path=ROOT/('models/'+gait+'.pt'); self.upper_path=ROOT/'models/upper.pt'
        self.provenance=json.loads((ROOT/'models/provenance.json').read_text(encoding='utf-8'))
        for key,path in [(gait,self.lower_path),('upper',self.upper_path)]:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=self.provenance[key]['sha256']:
                raise RuntimeError('Checkpoint hash changed: '+key)
        lower=torch.load(self.lower_path,map_location='cpu',weights_only=False)
        cfg=runtime_data.apply_checkpoint_config(lower,self.device)
        source=ROOT/('models/'+gait+'.npz'); drawn=ROOT/('models/'+gait+'-drawn.npz')
        probe=tl.MotionClip(source,cfg,cyclic_animation=True)
        model=visualize.load_model(lower,probe,cfg,self.device).eval().requires_grad_(False)
        self.runtime=runtime_data.CategoryRuntime(gait,lower,cfg,model,[gait+'_omni/M_Neutral_'+gait.title()+'_Loop_F.npz'],self.device,
            lower_source_paths=[source],full_source_paths_by_mode={-1.0:[source],1.0:[drawn]},cyclic_flags=[True])
        upper=torch.load(self.upper_path,map_location='cpu',weights_only=False)
        self.agent=upper_ctl.UpperCachedLowerAgent().eval()
        self.agent.load_state_dict(upper['model']); self.agent.requires_grad_(False)
        self.cache=None; self.calls=0

    @torch.inference_mode()
    def generate(self,duration=1,phase=0,drawn=False):
        duration=float(duration);phase=float(phase)
        if not math.isfinite(duration) or not .1<=duration<=5 or not math.isfinite(phase) or not 0<=phase<=1:
            raise ValueError('Run duration .1–5 s; phase 0–1 required')
        begin=time.perf_counter(); runtime=self.runtime; mode=1.0 if drawn else -1.0
        # One continuous actual lower NN rollout, including enough successors for any phase + 5 s.
        if self.cache is None:
            payload=cached_data.build_category_cache(runtime,self.lower_path,maximum_k=260)
            self.cache=cached_data.CachedLowerCategory(payload,runtime,self.lower_path,self.device)
        cache=self.cache; full=runtime.full_by_mode[mode]; period=int(full.cyclic_period)
        # Accepted Run F full-stride cut: 38 game ticks = 19 policy frames.
        # Begin after 2 seconds of lower NN settling. The upper also gets one warm-up stride.
        stride=19 if self.gait=="run" else 29
        start=60+int(round((phase%1)*stride));warm=start-stride
        count=math.ceil(duration*float(full.fps))+2; ids=torch.zeros(1,dtype=torch.long);gaze=torch.zeros((1,2))
        def gather(name,index):return cache.gather(name,ids,torch.tensor([index]))
        def base(index):return cache.base_upper(mode,ids,torch.tensor([index]))
        seed=runtime_data.upper_overlay_runtime_rows(runtime,mode,ids.repeat(2),torch.tensor([warm-1,warm]),gaze.repeat(2,1),self.device)
        previous,current=seed.split(1); rows=[]; roots=[]
        offsets=runtime.full_geometry_by_mode[mode]['local_offsets'][0:1]
        lengths=runtime.full_geometry_by_mode[mode]['ik_limb_lengths'][0:1]
        for index in range(warm,start+count):
            if index>warm:
                k=index-1
                prior=upper_data.clean_upper_state(base(index)+current-base(k))
                inp=torch.cat((previous,prior,gather('pelvis_heading',k-1),gather('pelvis_heading',k),gather('pelvis_heading',index),
                    gather('root_features',k),torch.full((1,1),mode),gather('feet_heading',k),gather('feet_heading',index),gaze),dim=-1)
                nxt=upper_data.clean_upper_state(prior+self.agent(inp));self.calls+=1
                nxt=upper_ctl.clamp_viewer_forearm_lengths(full,nxt,gather('pelvis_heading',index),offsets,lengths)
                previous,current=current,nxt
            if index<start: continue
            p,r=upper_ctl.decode_rows(runtime,mode,gather('lower_vector',index),current,gather('pelvis_heading',index),
                gather('root_position',index),gather('root_rotation',index),gather('heading',index),ids)
            # Python motion geometry is already right-handed Y-up, metres, with local X,Y,Z axes.
            rows.append({'points':p[0].tolist(),'axes':r[0].tolist()})
            roots.append(gather('root_position',index)[0].tolist())
        return dict(names=list(full.body_names),fps=float(full.fps),poses=rows,roots=roots,duration=duration,phase=phase,
            periodSeconds=stride/float(full.fps),gait=self.gait,source=('Run 181751' if self.gait=='run' else 'Walk July5')+' + Upper 82500',upperInferences=count-1+stride,
            lowerSource='continuous autoregressive '+self.gait.title()+' NN',seconds=time.perf_counter()-begin,provenance=self.provenance)

if __name__=='__main__':
    if '--request' in sys.argv:
        request=json.loads(sys.stdin.read())
        result=Locomotion(request.pop("gait","run")).generate(**request)
        print(json.dumps(result,separators=(',',':'),allow_nan=False))
        raise SystemExit(0)
    result=Locomotion().generate()
    (ROOT/'data/run-default.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('poses','roots','provenance')}))
    print('root',result['roots'][0],result['roots'][-1],'pelvis',result['poses'][0]['points'][0])

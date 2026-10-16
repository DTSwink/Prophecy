"""Package deterministic Run LR inference for Unreal, without loading the editor."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import torch
import native_probe
from native_probe import ROOT,OUT,names,parents,nodes

class Actor(torch.nn.Module):
    def __init__(self,model,checkpoint):
        super().__init__()
        self.layers=model._actor_layers
        self.motor=model._action_dist._mean_net
        self.phase=model._phase_out
        for key,value in [('obs_mean',checkpoint['_obs_norm._mean']),('obs_std',checkpoint['_obs_norm._std']),
                          ('action_mean',checkpoint['_a_norm._mean']),('action_std',checkpoint['_a_norm._std'])]:
            self.register_buffer(key,value)
    def forward(self,observations):
        normalized=((observations-self.obs_mean)/self.obs_std).clamp(-10.,10.)
        hidden=self.layers(normalized)
        velocities=(self.motor(hidden)*self.action_std+self.action_mean).clamp(-2*np.pi,2*np.pi)
        return velocities,self.phase(hidden)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',type=Path,default=OUT/'checkpoint/model.pt')
    parser.add_argument('--observations',type=Path)
    parser.add_argument('--output',type=Path,default=OUT/'runLR_actor.onnx')
    args=parser.parse_args()
    import onnxruntime as ort
    native_probe.load_actor(args.model)
    model,checkpoint=native_probe.model,native_probe.checkpoint
    torch.manual_seed(3913)
    output=args.output;assert not output.exists(),'Preserve prior inference export'
    output.parent.mkdir(parents=True,exist_ok=True)
    wrapper=Actor(model,checkpoint).eval()
    torch.onnx.export(wrapper,torch.zeros(1,151),str(output),dynamo=False,opset_version=17,
        input_names=['observations'],output_names=['joint_velocity_rad_s','phase_estimate'],
        dynamic_axes={n:{0:'batch'} for n in ('observations','joint_velocity_rad_s','phase_estimate')})
    options=ort.SessionOptions();options.intra_op_num_threads=options.inter_op_num_threads=1
    session=ort.InferenceSession(str(output),sess_options=options,providers=['CPUExecutionProvider'])
    samples=[]
    if args.observations:
        samples.append(np.load(args.observations)['obs'].reshape(-1,151))
    else:
        for path in (ROOT/'Saved/MimicKitTransfer').glob('newton_phase_*.npz'):
            samples.append(np.load(path)['obs'][:,0])
    recorded=np.concatenate(samples);errors=np.zeros(2)
    cases=[recorded]+[np.random.default_rng(3913+b).normal(size=(b,151)).astype('float32')*100 for b in (1,7,64)]
    with torch.inference_mode():
        for obs in cases:
            obs=np.asarray(obs,dtype='float32');t=torch.from_numpy(obs)
            norm=((t-checkpoint['_obs_norm._mean'])/checkpoint['_obs_norm._std']).clamp(-10,10)
            expected=[(model.eval_actor(norm).mode*checkpoint['_a_norm._std']+checkpoint['_a_norm._mean']).clamp(-2*np.pi,2*np.pi).numpy(),model.eval_phase(norm).numpy()]
            actual=session.run(None,{'observations':obs})
            for i,(a,b) in enumerate(zip(actual,expected)):
                np.testing.assert_allclose(a,b,atol=2e-5,rtol=2e-5)
                errors[i]=max(errors[i],float(np.max(np.abs(a-b))))
    batches={}
    for size in (1,32):
        obs=np.tile(recorded[:1],(size,1));session.run(None,{'observations':obs});times=[]
        for _ in range(100):
            start=time.perf_counter();session.run(None,{'observations':obs});times.append(time.perf_counter()-start)
        batches[str(size)]={'median_ms':float(np.median(times)*1000),'p95_ms':float(np.percentile(times,95)*1000)}
    action_map=[]
    for i,node in enumerate(nodes[1:],1):
        for axis in (range(3) if len(node.findall('joint'))==3 else [2]):
            action_map.append(dict(index=len(action_map),body=names[i],parent=names[parents[i]],child_local_axis=axis))
    report=dict(passed=True,checkpoint_model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
        onnx_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),max_output_errors=errors.tolist(),
        recorded_observations=len(recorded),tested_batches=[len(recorded),1,7,64],cpu_timings=batches,
        input_width=151,outputs={'joint_velocity_rad_s':34,'phase_estimate':2},action_map=action_map,
        contract={'normalization':'Embedded, including observation clamp +/-10 and action unnormalization',
                  'actuation':'Child-local angular velocities, bounded +/-2pi rad/s; velocity gains and torque caps from frozen asset',
                  'phase':'Prediction only; independent 30Hz animation clock remains authoritative',
                  'physics':'240Hz, eight substeps per policy tick; no action noise',
                  'observations':'Exact compute_char_obs/global_obs/root_height_obs;146 physical + gait1 + world direction2 + phase cos/sin2',
                  'scope':'Inference parity only. Does not certify physical transfer or modify Unreal.'})
    output.with_suffix('.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('action_map','contract')},indent=2))
if __name__=='__main__':main()

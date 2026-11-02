"""Frozen Foot IK NN boundary: current/history + actual future root headings.

Build time only. Runtime uses in-process UE NNE/ORT, no Python workers. Four
Run181751 directional contexts serve both command gaits; Upper82500 is unarmed
as in surface_nn.Stream. All seed/feature/rebase/decode math is inside ONNX.
"""
import argparse, hashlib, inspect, json, math, sys, time, warnings
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[2]
LAB=PROJECT/'Labs/FootIKLab'
sys.dont_write_bytecode=True
sys.path.insert(0,str(LAB));sys.path.insert(1,str(PROJECT/'Labs/BodyflipLab'))
sys.path.insert(2,str(PROJECT/'Saved/Diagnostics/BodyflipPort20261030/python'))
from nn_worker import ResumeLocomotion,PolicyStep,encode_lower,inference_execution
from directional_nn import configure_direction,command_seed,decode_policy_rows,STRIDE_TICKS
from surface_nn import Stream
from locomotion import torch,runtime_data,upper_data,tl
import onnx,onnxruntime as ort
OUT=PROJECT/'Content/FootIKLab/NN'
WIDTHS=(41,41,90,90,9,9,90)

class Context(torch.nn.Module):
 def __init__(self,owner):
  super().__init__();self.owner=owner;self.runtime=owner.runtime
  _,self.basis,self.heading=runtime_data.root_state(owner.runtime,torch.zeros(1,dtype=torch.long))
  self.inverse=owner.course_axes.T
 def window(self,packed,origin):
  roots=packed[:,:30].reshape(10,3)@self.inverse-origin
  angles=packed[:,30:40].reshape(10)*math.pi/180
  bases=self.basis@tl.yaw_to_row_matrix(-angles)
  yaws=tl.heading_yaw_from_root(bases);headings=tl.yaw_to_row_matrix(yaws)
  pose_headings=self.heading@tl.yaw_to_row_matrix(-angles)
  return roots,bases,yaws,headings,pose_headings

class Encoder(Context):
 def forward(self,packed):
  native=(packed[:,600:630].reshape(10,3)@self.inverse)
  origin=native[1:2]*packed[:,640:641]
  roots,bases,_,_,headings=self.window(packed[:,600:640],origin)
  positions=packed[:,:150].reshape(2,25,3)@self.inverse-origin[:,None]
  rotations=packed[:,150:600].reshape(2,25,3,3)@self.inverse
  r=self.runtime;full=r.full_by_mode[-1.]
  previous,current=encode_lower(r.lower_clip,positions,rotations,roots[:2],bases[:2]).split(1)
  pu,cu=upper_data.upper_state_from_global_pose_and_heading(full,positions,rotations,roots[:2],headings[:2]).split(1)
  pp=runtime_data.pelvis_heading_features(previous,bases[:1],headings[:1])
  cp=runtime_data.pelvis_heading_features(current,bases[1:2],headings[1:2])
  base=runtime_data.base_upper_from_lower(current,roots[1:2],bases[1:2],headings[1:2],full,r.rest_offsets_by_mode[-1.][0:1])
  return torch.cat((previous,current,pu,cu,pp,cp,base,origin),-1)

class Step(Context):
 def __init__(self,owner,direct_root=False):
  super().__init__(owner);self.policy=PolicyStep(owner,-1.,self.basis,self.heading);self.direct_root=direct_root
 def forward(self,packed):
  previous,current,pu,cu,pp,cp,base=torch.split(packed[:,:370],WIDTHS,-1)
  origin=packed[:,410:413]
  roots,bases,yaws,headings,pose_headings=self.window(packed[:,370:410],origin)
  cfg=self.runtime.store.cfg
  delta=(roots[1:2]-roots[0:1])@headings[0]
  first=torch.stack((delta[:,0]/cfg.max_speed_scale_final,delta[:,2]/cfg.max_speed_scale_final,tl.wrap_angle(yaws[1:2]-yaws[:1])/cfg.max_turn_rate_scale_final),-1)
  steps=torch.arange(1,9);command=(roots[2:10]-roots[1])@headings[1]
  yaw_delta=tl.wrap_angle(yaws[2:10]-yaws[1]);scale=steps*cfg.max_speed_scale_final
  window=torch.stack(((command[:,0]/scale).clamp(-2,2),(command[:,2]/scale).clamp(-2,2),torch.cos(yaw_delta),torch.sin(yaw_delta)),-1)
  features=torch.cat((first,window.reshape(1,-1)),-1)
  next_root=roots[2:3] if self.direct_root else roots[1:2]+torch.stack((window[0,0]*cfg.max_speed_scale_final,roots[2,1]-roots[1,1],window[0,1]*cfg.max_speed_scale_final))[None]@headings[1].T
  lower,upper,pelvis,next_base,pins=self.policy(previous,current,pu,cu,pp,base,roots[1:2],next_root,features,bases[1:2],pose_headings[1:2],bases[2:3],pose_headings[2:3])
  p,r=decode_policy_rows(self.owner,self.runtime,-1.,lower,upper,pelvis,next_root,bases[2:3],pose_headings[2:3],torch.zeros(1,dtype=torch.long))
  p=(p+origin[:,None])@self.owner.course_axes;r=r@self.owner.course_axes
  root=(next_root+origin)@self.owner.course_axes
  return torch.cat((current,lower,cu,upper,cp,pelvis,next_base,root,p.reshape(1,-1),r.reshape(1,-1),pins,features),-1)

def export_graph(model,sample,path):
 from torch.onnx._internal.torchscript_exporter import symbolic_helper as sh
 reshape=sh._reshape_helper
 def exact_reshape(g,value,shape,allowzero=0):
  sizes=sh._maybe_get_const(shape,'is');before=sh._get_tensor_sizes(value)
  if isinstance(sizes,(list,tuple)):
   sizes=list(sizes)
   if before is not None and 0 in before and sizes.count(-1)==1:sizes[sizes.index(-1)]=0
   if 0 in sizes and all(isinstance(n,int) and n>=0 for n in sizes):
    return g.op('Constant',value_t=torch.empty(sizes,dtype=sh._type_utils.JitScalarType.from_value(value).dtype()))
  return reshape(g,value,shape,allowzero)
 sh._reshape_helper=exact_reshape
 try:
  with warnings.catch_warnings():
   warnings.simplefilter('ignore');torch.onnx.export(model.eval(),sample,str(path),input_names=['input'],output_names=['output'],opset_version=17,do_constant_folding=True,dynamo=False)
 finally:sh._reshape_helper=reshape
 # Fixed input shapes are known at export. Retain their inferred metadata so
 # ORT can remove repeated shape plumbing without changing graph arithmetic.
 graph=onnx.load(path)
 onnx.save(onnx.shape_inference.infer_shapes(graph,strict_mode=True,data_prop=True),path)
 onnx.checker.check_model(str(path))
 opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
 return ort.InferenceSession(str(path),opts,providers=['CPUExecutionProvider'])

def command_window(seed,speed,index=0,yaw=0):
 current=torch.tensor(seed['roots'][1]);roots=[seed['roots'][0]]+[(current+torch.tensor([0.,0.,speed*k/30])).tolist() for k in range(index+12)]
 return dict(roots=roots[index:index+10],rootYawDegrees=[yaw*(index+k)/30 for k in range(10)])
def pack_seed(seed,window,normalize=False):
 return torch.cat((torch.tensor([p['points'][1:] for p in seed]).reshape(1,-1),torch.tensor([p['axes'][1:] for p in seed]).reshape(1,-1),torch.tensor(window['roots'][:10]).reshape(1,-1),torch.tensor(window['rootYawDegrees'][:10]).reshape(1,-1),torch.tensor([[float(normalize)]])),-1)
def pack_window(window):return torch.cat((torch.tensor(window['roots'][:10]).reshape(1,-1),torch.tensor(window['rootYawDegrees'][:10]).reshape(1,-1)),-1)

def main(directions):
 OUT.mkdir(parents=True,exist_ok=True)
 receipt_path=OUT/'Receipt.json';receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else {'schema':1,'graphs':{}}
 receipt.update(seedInput=641,seedOutput=373,stepInput=413,stateWidth=370,rootRows=10,future=8,policy='Run181751',upper='Upper82500',mode=-1)
 for direction in directions:
  begin=time.perf_counter();print('load',direction,flush=True)
  owner=ResumeLocomotion('run');configure_direction(owner,'run',direction);owner.runtime.install_policy()
  assert owner.runtime.store.cfg.future_window==8
  seed=command_seed(owner);names=['root',*seed['names']]
  full_seeds=[dict(points=[seed['roots'][i],*seed['poses'][i]['points']],axes=[torch.eye(3).tolist(),*seed['poses'][i]['axes']]) for i in (0,1)]
  bank=dict(names=seed['names'],seeds=full_seeds,roots=seed['roots'][:2],directionMeta=owner.direction_info,strideTicks={g:STRIDE_TICKS[g][direction] for g in ('walk','run')},walkSpeed={'forward':2.,'backward':1.5,'left':1.8,'right':1.8}[direction],provenance=owner.provenance)
  stem='run-'+direction;bankpath=OUT/(stem+'-seed.json');bankpath.write_text(json.dumps(bank,separators=(',',':')))
  window=command_window(seed,owner.direction_info['commandSpeed']);request=dict(window,seeds=full_seeds,names=names)
  encoder=Encoder(owner).eval();sample=pack_seed(full_seeds,window);expected=encoder(sample)
  enc=export_graph(encoder,sample,OUT/(stem+'-seed.onnx'));actual=torch.tensor(enc.run(None,{'input':sample.numpy()})[0]);torch.testing.assert_close(actual,expected,rtol=2e-5,atol=4e-6)
  step=Step(owner).eval();packed=torch.cat((actual[:,:370],pack_window(window),actual[:,370:373]),-1)
  native=export_graph(step,packed,OUT/(stem+'-step.onnx'))
  max_error=0.;max_pose=0.;frame_count=0
  for speed,yaw in [(owner.direction_info['commandSpeed'],0),(bank['walkSpeed'],75),(bank['walkSpeed'],-120)]:
   stream=Stream(owner);state=None
   for i in range(24):
    window=command_window(seed,speed,i,yaw);request=dict(window,seeds=full_seeds,names=names)
    if state is None:state=torch.tensor(enc.run(None,{'input':pack_seed(full_seeds,window).numpy()})[0])[:,:370]
    packed=torch.cat((state,pack_window(window),torch.zeros(1,3)),-1)
    a=torch.tensor(native.run(None,{'input':packed.numpy()})[0]);e=step(packed)
    torch.testing.assert_close(a,e,rtol=5e-4,atol=3e-5);max_error=max(max_error,float((a-e).abs().max()))
    original=stream.step(request);p=torch.tensor(original['pose']['points']);q=torch.tensor(original['pose']['axes'][1:]);outp=torch.cat((a[:,370:373].reshape(1,3),a[:,373:448].reshape(25,3)))
    max_pose=max(max_pose,float((outp-p).abs().max()),float((a[:,448:673].reshape(25,3,3)-q).abs().max()))
    torch.testing.assert_close(outp,p,rtol=7e-4,atol=1e-4);torch.testing.assert_close(a[:,448:673].reshape(25,3,3),q,rtol=7e-4,atol=1e-4)
    state=a[:,:370];frame_count+=1
  receipt['stepOutput']=int(a.shape[1]);receipt['pinWidth']=int(a.shape[1]-673-35)
  row=dict(frames=frame_count,maxGraphError=max_error,maxStreamPoseError=max_pose,seconds=time.perf_counter()-begin,sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [bankpath,OUT/(stem+'-seed.onnx'),OUT/(stem+'-step.onnx')]})
  receipt['graphs'][direction]=row;receipt_path.write_text(json.dumps(receipt,indent=2)+'\n');print(direction,json.dumps(row),flush=True)
 if len(receipt['graphs'])==4:print('all four directional graph pairs ready',flush=True)

def export_resume(directions):
 """Additional exact /resume decoder; leave validated surface graphs intact."""
 from directional_nn import resume_in_course
 receipt_path=OUT/'Receipt.json';receipt=json.loads(receipt_path.read_text());receipt.setdefault('resumeGraphs',{})
 for direction in directions:
  begin=time.perf_counter();print('load resume',direction,flush=True)
  owner=ResumeLocomotion('run');configure_direction(owner,'run',direction);owner.runtime.install_policy()
  bank=json.loads((OUT/('run-'+direction+'-seed.json')).read_text());seeds=bank['seeds']
  opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
  encoder=ort.InferenceSession(str(OUT/('run-'+direction+'-seed.onnx')),opts,providers=['CPUExecutionProvider'])
  seed=command_seed(owner);window=command_window(seed,bank['walkSpeed']);encoded=torch.tensor(encoder.run(None,{'input':pack_seed(seeds,window,True).numpy()})[0])
  step=Step(owner,True).eval();packed=torch.cat((encoded[:,:370],pack_window(window),encoded[:,370:373]),-1)
  path=OUT/('run-'+direction+'-resume.onnx');native=export_graph(step,packed,path)
  count=18;current=torch.tensor(seed['roots'][1]);roots=[seed['roots'][0]]+[(current+torch.tensor([0.,0.,bank['walkSpeed']*i/30])).tolist() for i in range(count+8)]
  request=dict(gait='walk',policy='run',direction=direction,names=['root',*bank['names']],seeds=seeds,frames=count,roots=roots,rootYawDegrees=[75*i/30 for i in range(len(roots))])
  expected=resume_in_course(owner,request);encoded=torch.tensor(encoder.run(None,{'input':pack_seed(seeds,request,True).numpy()})[0]);state=encoded[:,:370];origin=encoded[:,370:373];maximum=0.
  for i in range(count-1):
   window=dict(roots=roots[i:i+10],rootYawDegrees=request['rootYawDegrees'][i:i+10]);packed=torch.cat((state,pack_window(window),origin),-1)
   output=torch.tensor(native.run(None,{'input':packed.numpy()})[0]);state=output[:,:370]
   for actual,key,shape in [(output[:,373:448],'points',(25,3)),(output[:,448:673],'axes',(25,3,3))]:
    reference=torch.tensor(expected['poses'][i+1][key]);difference=float((actual.reshape(shape)-reference).abs().max());maximum=max(maximum,difference);torch.testing.assert_close(actual.reshape(shape),reference,rtol=7e-4,atol=1e-4)
  receipt['resumeGraphs'][direction]=dict(frames=count,maxPoseError=maximum,seconds=time.perf_counter()-begin,sha256={path.name:hashlib.sha256(path.read_bytes()).hexdigest()})
  receipt_path.write_text(json.dumps(receipt,indent=2)+'\n');print(direction,json.dumps(receipt['resumeGraphs'][direction]),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--direction',action='append',choices=['forward','backward','left','right']);parser.add_argument('--resume-only',action='store_true');args=parser.parse_args()
 with torch.inference_mode():(export_resume if args.resume_only else main)(args.direction or ['forward','backward','left','right'])

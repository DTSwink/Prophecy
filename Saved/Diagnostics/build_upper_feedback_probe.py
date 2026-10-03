import pathlib,sys,json,importlib.util,torch,onnx,hashlib
root=pathlib.Path.cwd();stepper=pathlib.Path(r'C:\Users\singerie\Documents\Cursor\stepper');sys.path.insert(0,str(stepper))
from training.ik import ik_core as tl
from training.ik import train_upper_pose_autoencoder as data
from training.ik import train_upper_pose_controller_pelvis as ctl
c=json.loads((root/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
model=ctl.UpperCachedLowerAgent();model.load_state_dict(torch.load(c['checkpoint_path'],map_location='cpu',weights_only=False)['model']);model.eval()
clip=tl.MotionClip(c['reference_clip_path'],data.motion_config(),cyclic_animation=True)
t=clip.tensors(torch.device('cpu'));lengths=t['ik_limb_lengths'];offsets=clip.local_offsets
print('GEOMETRY',lengths.shape,offsets.shape)
class Probe(torch.nn.Module):
 def __init__(self):
  super().__init__();self.agent=model;self.register_buffer('offsets',offsets);self.register_buffer('lengths',lengths.unsqueeze(0).expand(100,-1,-1))
 def forward(self,x):
  if len(sys.argv)>1 and sys.argv[1]=='zero_gaze':
   return self.agent(torch.cat((x[:,:279],torch.zeros_like(x[:,279:281])),dim=1))
  if len(sys.argv)>1 and sys.argv[1]=='sheathed':
   return self.agent(torch.cat((x[:,:242],-torch.ones_like(x[:,242:243]),x[:,243:]),dim=1))
  prior=x[:,90:180];upper=prior+self.agent(x)
  return ctl.clamp_viewer_forearm_lengths(clip,upper,x[:,198:207],self.offsets,self.lengths)-prior
p=root/'Saved/Diagnostics/RunHandThigh'/((sys.argv[1] if len(sys.argv)>1 else 'feedback')+'_probe');p.mkdir(exist_ok=True)
probe=Probe().eval();x=torch.zeros(100,281)
with torch.no_grad():torch.onnx.export(probe,(x,),p/'prophecy_upper_body_b100.onnx',input_names=['controller_input'],output_names=['upper_pose_delta'],opset_version=18,dynamo=False)
onnx.checker.check_model(onnx.load(p/'prophecy_upper_body_b100.onnx'))
audit=torch.tensor(c['startup_audit']['input']).unsqueeze(0).expand(100,-1)
with torch.no_grad():c['startup_audit']['expected_output']=probe(audit)[0].tolist()
c['onnx_sha256']=hashlib.sha256((p/'prophecy_upper_body_b100.onnx').read_bytes()).hexdigest().upper()
(p/'prophecy_upper_body_runtime.json').write_text(json.dumps(c,indent=2)+'\n')
print('FEEDBACK_PROBE_EXPORTED',p)

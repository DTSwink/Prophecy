"""Add static ONNX tensor metadata; refuse any changed computation or output.

Uses existing build dependencies. One CPU thread, bounded sessions, no retraining,
graph rewrite, numerical approximation or extra runtime model copy. The receipt
retains original hashes; the stripped graph reproduces its original computation.
"""
import argparse,copy,gc,hashlib,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/Diagnostics/BodyflipPort20261030/python'))
import onnx,onnxruntime as ort
FOLDER=ROOT/'Content/FootIKLab/NN'
OUT=ROOT/'Saved/Diagnostics/FootIKPort20261030'

def sha(data):return hashlib.sha256(data).hexdigest()
def computational_bytes(model):
 m=copy.deepcopy(model)
 def strip(g):
  g.ClearField('value_info')
  for v in [*g.input,*g.output]:v.type.tensor_type.ClearField('shape')
  for node in g.node:
   for a in node.attribute:
    if a.type==onnx.AttributeProto.GRAPH:strip(a.g)
    elif a.type==onnx.AttributeProto.GRAPHS:
     for sub in a.graphs:strip(sub)
 strip(m.graph);return m.SerializeToString()
def session(data):
 o=ort.SessionOptions();o.intra_op_num_threads=1;o.inter_op_num_threads=1;o.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
 o.add_session_config_entry('session.intra_op.allow_spinning','0');o.add_session_config_entry('session.inter_op.allow_spinning','0')
 return ort.InferenceSession(data,o,providers=['CPUExecutionProvider'])
def seed_input(bank,roots,yaws,normalize=True):
 return np.concatenate((np.asarray([s['points'][1:] for s in bank['seeds']],np.float32).ravel(),np.asarray([s['axes'][1:] for s in bank['seeds']],np.float32).ravel(),roots[:10].ravel(),yaws[:10],np.array([normalize],np.float32)))[None]
def courses(bank):
 for speed,yaw,vertical in [(bank['walkSpeed'],120.,0.),(bank['directionMeta']['commandSpeed'],-90.,0.),(-1.5,220.,.3)]:
  roots=[np.asarray(bank['roots'][0],np.float32),np.asarray(bank['roots'][1],np.float32)]
  for i in range(82):
   v=speed if i<22 else 0. if i<29 else -speed if i<44 else speed
   roots.append(roots[-1]+np.array([0,vertical,v/30],np.float32))
  yaws=np.asarray([yaw*max(0,min(i-5,50))/30 for i in range(len(roots))],np.float32)
  yield np.asarray(roots,np.float32),yaws
def verify(original,candidate,bank,kind,encoder):
 ref=session(original);new=session(candidate);frames=0;cpu=[0.,0.];wall=[0.,0.]
 def pair(x):
  nonlocal frames
  results=[]
  for i,s in enumerate((ref,new)):
   t=time.perf_counter();c=time.process_time();results.append(s.run(None,{'input':x})[0]);cpu[i]+=time.process_time()-c;wall[i]+=time.perf_counter()-t
  a,b=results
  if not np.array_equal(a.view(np.uint32),b.view(np.uint32)):raise RuntimeError(f'Nonexact {kind} output at {frames}: {np.max(np.abs(a-b))}')
  frames+=1;return a
 for roots,yaws in courses(bank):
  if kind=='seed':
   for normalize in (False,True):
    for k in (0,12,30,50):pair(seed_input(bank,roots[k:],yaws[k:],normalize))
  else:
   encoded=encoder.run(None,{'input':seed_input(bank,roots,yaws,kind=='resume')})[0];state=encoded[0,:370];origin=encoded[0,370:373]
   for k in range(72):
    x=np.concatenate((state,roots[k:k+10].ravel(),yaws[k:k+10],origin))[None];a=pair(x);state=a[0,:370]
 del ref,new;gc.collect()
 return dict(exactFrames=frames,originalCpuMs=cpu[0]*1000/frames,annotatedCpuMs=cpu[1]*1000/frames,originalWallMs=wall[0]*1000/frames,annotatedWallMs=wall[1]*1000/frames)
def main(apply):
 receipt_path=FOLDER/'Receipt.json';receipt=json.loads(receipt_path.read_text());evidence={}
 for direction in ('forward','backward','left','right'):
  bank=json.loads((FOLDER/f'run-{direction}-seed.json').read_text());encoder=None
  for kind in ('seed','step','resume'):
   name=f'run-{direction}-{kind}.onnx';path=FOLDER/name;before=path.read_bytes()
   retained=receipt.get('shapeMetadata',{}).get(name)
   if retained and retained['annotatedSha256']==sha(before):
    evidence[name]=retained;print(name,'already verified',flush=True)
    if kind=='seed':encoder=session(before)
    continue
   model=onnx.load_from_string(before)
   inferred=onnx.shape_inference.infer_shapes(model,strict_mode=True,data_prop=True)
   if computational_bytes(model)!=computational_bytes(inferred):raise RuntimeError('Shape inference changed computation: '+name)
   after=inferred.SerializeToString();onnx.checker.check_model(inferred)
   row=verify(before,after,bank,kind,encoder);row.update(originalSha256=sha(before),annotatedSha256=sha(after),bytesBefore=len(before),bytesAfter=len(after),computationSha256=sha(computational_bytes(model)))
   evidence[name]=row;print(name,json.dumps(row),flush=True)
   if apply:
    path.write_bytes(after)
    section='resumeGraphs' if kind=='resume' else 'graphs';receipt[section][direction]['sha256'][name]=sha(after)
    receipt.setdefault('shapeMetadata',{})[name]=row;receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
   if kind=='seed':encoder=session(after)
   (OUT/'nn-shapes-proof.json').write_text(json.dumps(dict(applied=apply,ort=ort.__version__,cases=evidence),indent=2)+'\n')
  del encoder;gc.collect()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args();main(args.apply)

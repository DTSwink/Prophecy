"""Saved-only fixed-index layout experiment. Float arithmetic is never rewritten."""
import os,sys,json,time,copy,math,hashlib,threading,importlib.util,collections
from pathlib import Path
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='1'
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/Diagnostics/FootIKPort20261030';FOLDER=ROOT/'Content/FootIKLab/NN'
sys.path.insert(0,str(ROOT/'Saved/Diagnostics/BodyflipPort20261030/python'))
import numpy as np
import onnx,onnxruntime as ort
LAYOUT={'Identity','Reshape','Flatten','Transpose','Slice','Gather','Unsqueeze','Squeeze','Concat','Expand'}
def sha(data):return hashlib.sha256(data).hexdigest()
def shape(v):
 t=v.type.tensor_type
 if not t.HasField('shape') or any(not d.HasField('dim_value') for d in t.shape.dim):return None
 return tuple(d.dim_value for d in t.shape.dim)
def rewrite(model):
 g=model.graph;shapes={};types={};constants={};maps={};replacements={};initializers=[];flat_names={};stats=collections.Counter()
 for v in (*g.input,*g.output,*g.value_info):
  s=shape(v)
  if s is not None:shapes[v.name]=s;types[v.name]=v.type.tensor_type.elem_type
 for v in g.initializer:
  shapes[v.name]=tuple(v.dims);types[v.name]=v.data_type
  if math.prod(v.dims)<=4096:constants[v.name]=onnx.numpy_helper.to_array(v)
 nodes=list(g.node)
 def mapping(name):
  if name in maps:return maps[name]
  s=shapes.get(name)
  if s is None or math.prod(s)>4096 or types.get(name)!=onnx.TensorProto.FLOAT or name in constants:return None
  return name,s,np.arange(math.prod(s),dtype=np.int64).reshape(s),frozenset()
 def attrs(n):return {a.name:onnx.helper.get_attribute_value(a) for a in n.attribute}
 def execute(op,arrays,n,a):
  x=arrays[0]
  if op=='Identity':return x
  if op=='Transpose':return np.transpose(x,axes=a.get('perm',list(reversed(range(x.ndim)))))
  if op=='Flatten':axis=a.get('axis',1);axis=axis+x.ndim if axis<0 else axis;return x.reshape(math.prod(x.shape[:axis]),math.prod(x.shape[axis:]))
  if op=='Reshape':
   dims=[int(v) for v in constants[n.input[1]].reshape(-1)]
   if not a.get('allowzero',0):dims=[x.shape[i] if v==0 else v for i,v in enumerate(dims)]
   return x.reshape(dims)
  if op=='Slice':
   starts,ends=(constants[v].reshape(-1) for v in n.input[1:3]);axes=constants[n.input[3]].reshape(-1) if len(n.input)>3 and n.input[3] else np.arange(len(starts));steps=constants[n.input[4]].reshape(-1) if len(n.input)>4 and n.input[4] else np.ones(len(starts),dtype=np.int64);slices=[slice(None)]*x.ndim
   for start,end,axis,step in zip(starts,ends,axes,steps):slices[int(axis)]=slice(int(start),int(end),int(step))
   return x[tuple(slices)]
  if op=='Gather':return np.take(x,constants[n.input[1]],axis=a.get('axis',0))
  if op=='Unsqueeze':
   axes=tuple(int(v) for v in (constants[n.input[1]].reshape(-1) if len(n.input)>1 else a['axes']));return np.expand_dims(x,axes)
  if op=='Squeeze':
   axes=tuple(int(v) for v in (constants[n.input[1]].reshape(-1) if len(n.input)>1 else a.get('axes',[])));return np.squeeze(x,axis=axes or None)
  if op=='Expand':return np.broadcast_to(x,tuple(int(v) for v in constants[n.input[1]].reshape(-1)))
  if op=='Concat':return np.concatenate(arrays,axis=a['axis'])
  raise KeyError(op)
 for index,n in enumerate(nodes):
  a=attrs(n)
  if n.op_type=='Constant' and 'value' in a:
   v=onnx.numpy_helper.to_array(a['value'])
   if v.size<=4096:constants[n.output[0]]=v
   continue
  if n.op_type=='Shape' and n.input[0] in shapes:
   dims=shapes[n.input[0]];constants[n.output[0]]=np.asarray(dims[a.get('start',0):a.get('end',len(dims))],np.int64);continue
  if n.op_type not in LAYOUT or len(n.output)!=1:continue
  data_inputs=list(n.input) if n.op_type=='Concat' else list(n.input[:1])
  try:
   if all(v in constants for v in data_inputs):
    value=execute(n.op_type,[constants[v] for v in data_inputs],n,a)
    if value.size<=4096:constants[n.output[0]]=value
    continue
   rows=[mapping(v) for v in data_inputs]
   if any(r is None for r in rows) or len({r[0] for r in rows})!=1:continue
   base,base_shape=rows[0][:2];value=execute(n.op_type,[r[2] for r in rows],n,a)
   if value.size>4096 or (n.output[0] in shapes and value.shape!=shapes[n.output[0]]):continue
   chain=frozenset().union(*(r[3] for r in rows),{index});maps[n.output[0]]=(base,base_shape,value,chain)
   shapes[n.output[0]]=value.shape;types[n.output[0]]=onnx.TensorProto.FLOAT
   if len(chain)<5:continue
   prefix='footik_layout_'+str(index);replacement=[];dims_name=prefix+'_shape';initializers.append(onnx.numpy_helper.from_array(np.asarray(value.shape,np.int64),dims_name))
   if value.size==math.prod(base_shape) and np.array_equal(value.reshape(-1),np.arange(value.size)):
    replacement.append(onnx.helper.make_node('Reshape',[base,dims_name],list(n.output),name=prefix+'_reshape'))
   else:
    if base not in flat_names:
     flat_name=prefix+'_flat';flat_dims=prefix+'_flat_shape';initializers.append(onnx.numpy_helper.from_array(np.asarray([-1],np.int64),flat_dims));flat_names[base]=(flat_name,flat_dims)
     replacement.append(onnx.helper.make_node('Reshape',[base,flat_dims],[flat_name],name=prefix+'_flatten'))
    flat_name=flat_names[base][0];indices=prefix+'_indices';initializers.append(onnx.numpy_helper.from_array(value.reshape(-1).copy(),indices));gathered=prefix+'_gathered'
    replacement.append(onnx.helper.make_node('Gather',[flat_name,indices],[gathered],name=prefix+'_gather',axis=0));replacement.append(onnx.helper.make_node('Reshape',[gathered,dims_name],list(n.output),name=prefix+'_reshape'))
   replacements[index]=replacement;stats['replacementOutputs']+=1
  except (KeyError,ValueError,IndexError,TypeError):continue
 # All floating-point arithmetic nodes and their operands are retained verbatim.
 rewritten=[]
 for i,n in enumerate(nodes):rewritten.extend(replacements.get(i,[n]))
 needed={o.name for o in g.output}
 def captured(node):
  found=set()
  for attr in node.attribute:
   if attr.type==onnx.AttributeProto.GRAPH:
    for child in attr.g.node:found.update(child.input);found.update(captured(child))
    found.update(v.name for v in attr.g.output)
  return found
 for n in rewritten:needed.update(captured(n))
 kept=[]
 for n in reversed(rewritten):
  if n.op_type not in LAYOUT|{'Constant'} or any(v in needed for v in n.output):kept.append(n);needed.update(n.input)
 kept.reverse();del g.node[:];g.node.extend(kept);g.initializer.extend(v for v in initializers if v.name in needed)
 # Stale metadata for eliminated values is harmless but needlessly increases load.
 names={v for n in kept for v in (*n.input,*n.output)}|{v.name for v in g.input}|{v.name for v in g.output}
 info=[v for v in g.value_info if v.name in names];del g.value_info[:];g.value_info.extend(info)
 stats.update(originalNodes=len(nodes),candidateNodes=len(kept),addedIntegerInitializers=sum(v.name in needed for v in initializers));return stats
def session(data):
 o=ort.SessionOptions();o.intra_op_num_threads=1;o.inter_op_num_threads=1;o.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;o.log_severity_level=3
 o.add_session_config_entry('session.intra_op.allow_spinning','0');o.add_session_config_entry('session.inter_op.allow_spinning','0');c=time.process_time();t=time.perf_counter();s=ort.InferenceSession(data,o,providers=['CPUExecutionProvider']);return s,dict(cpuMs=(time.process_time()-c)*1000,wallMs=(time.perf_counter()-t)*1000)
def main():
 data=(FOLDER/'run-forward-resume.onnx').read_bytes();original=onnx.load_from_string(data);candidate=copy.deepcopy(original);stats=rewrite(candidate)
 onnx.checker.check_model(candidate)
 arithmetic=lambda m:[n.SerializeToString() for n in m.graph.node if n.op_type not in LAYOUT|{'Constant'}]
 assert arithmetic(original)==arithmetic(candidate),'Arithmetic node changed'
 old_init={v.name:v.SerializeToString() for v in original.graph.initializer};new_init={v.name:v.SerializeToString() for v in candidate.graph.initializer};assert all(new_init.get(k)==v for k,v in old_init.items())
 packed=candidate.SerializeToString();target=OUT/'run-forward-resume-layout-candidate.onnx';target.write_bytes(packed);print('layout rewrite',dict(stats),'bytes',len(packed),flush=True)
 spec=importlib.util.spec_from_file_location('annotation',ROOT/'Tools/FootIK/annotate-nn-shapes.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
 bank=json.loads((FOLDER/'run-forward-seed.json').read_text());encoder,_=session(str(FOLDER/'run-forward-seed.onnx'));ref,ref_init=session(data);new,new_init=session(packed);print('initialized',ref_init,new_init,flush=True)
 cpu=[0.,0.];wall=[0.,0.];frames=0;count=0
 for roots,yaws in a.courses(bank):
  encoded=encoder.run(None,{'input':a.seed_input(bank,roots,yaws,True)})[0];state=encoded[0,:370];origin=encoded[0,370:373]
  for k in range(72):
   inp=np.concatenate((state,roots[k:k+10].ravel(),yaws[k:k+10],origin))[None];outputs=[None,None]
   for i in ((0,1) if frames%2==0 else (1,0)):
    c=time.process_time();t=time.perf_counter();outputs[i]=(ref,new)[i].run(None,{'input':inp})[0];dt=time.perf_counter()-t;dc=time.process_time()-c
    if k>=4:cpu[i]+=dc;wall[i]+=dt
   if not np.array_equal(outputs[0].view(np.uint32),outputs[1].view(np.uint32)):raise RuntimeError('Non-bitwise layout result at '+str(frames)+' max '+str(float(np.max(np.abs(outputs[0]-outputs[1])))))
   state=outputs[0][0,:370];frames+=1;count+=outputs[0].size
 n=frames-12;report=dict(passed=True,ort=ort.__version__,sourceSha256=sha(data),candidateSha256=sha(packed),sourceBytes=len(data),candidateBytes=len(packed),stats=dict(stats),arithmeticNodesUnchanged=True,originalInitializerBytesUnchanged=True,exactFrames=frames,exactFloat32Values=count,originalInit=ref_init,candidateInit=new_init,originalCpuMs=cpu[0]*1000/n,candidateCpuMs=cpu[1]*1000/n,originalWallMs=wall[0]*1000/n,candidateWallMs=wall[1]*1000/n,contentUnchanged=(FOLDER/'run-forward-resume.onnx').read_bytes()==data)
 (OUT/'nn-layout-candidate-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':
 timer=threading.Timer(90,lambda:(print('90-second layout probe watchdog',flush=True),os._exit(124)));timer.daemon=True;timer.start()
 try:main()
 except Exception as error:(OUT/'nn-layout-candidate-error.json').write_text(json.dumps(dict(error=str(error)),indent=2));raise
 finally:timer.cancel()

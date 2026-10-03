"""Extract unchanged attack MLP layers; retain original models and geometry oracles."""
from pathlib import Path
import sys,json,hashlib,copy
import numpy as np,onnx,torch
from onnx import helper,TensorProto
ROOT=Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT/'Saved/SlashPythonDependencies'))
import onnxruntime as ort

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=[]
for suffix in ('','Attack160664','Attack184064'):
 folder=ROOT/'Content/locomotion/NN'/suffix
 contract=json.loads((folder/'prophecy_slash_native.json').read_text(encoding='utf8'))
 runtime=json.loads((folder/'prophecy_slash_runtime.json').read_text(encoding='utf8'))
 checkpoint=torch.load(runtime['checkpoint_path'],map_location='cpu',weights_only=False)
 cone=checkpoint['pelvis_foot_cone'];hand=checkpoint['hand_clamp']
 assert cone['sha256']=='659cd1c8d2a5e27628fbbb04024a71b599ad183ec684281d9f903f6ce866a772'
 assert hand['sha256']=='f58ff4058f9cfe78cdebcc393d106e9251f71eb82a19dd98aeba35a98cb13e4d'
 source=folder/contract['networks']['upper']['file'];assert sha(source)==contract['networks']['upper']['sha256']
 model=onnx.load(str(source));heads=['/network/delta_head/Gemm_output_0','/network/Sigmoid_output_0']
 producer={out:n for n in model.graph.node for out in n.output};keep=set()
 def visit(v):
  n=producer.get(v)
  if n is None or n.name in keep:return
  keep.add(n.name)
  for i in n.input:visit(i)
 for h in heads:visit(h)
 nodes=[copy.deepcopy(n) for n in model.graph.node if n.name in keep]
 nodes.append(helper.make_node('Concat',heads,['output'],axis=1,name='RawAttackHeads'))
 used={i for n in nodes for i in n.input}
 graph=helper.make_graph(nodes,'AttackRawUpper',[copy.deepcopy(model.graph.input[0])],[helper.make_tensor_value_info('output',TensorProto.FLOAT,['agents',92])],[copy.deepcopy(t) for t in model.graph.initializer if t.name in used])
 raw=helper.make_model(graph,opset_imports=list(model.opset_import),ir_version=model.ir_version)
 path=folder/'prophecy_slash_upper_neural.onnx';onnx.checker.check_model(raw);onnx.save(raw,str(path))
 oracle=copy.deepcopy(model)
 for h,n in zip(heads,[90,2]):oracle.graph.output.append(helper.make_tensor_value_info(h,TensorProto.FLOAT,['agents',n]))
 opt=ort.SessionOptions();opt.intra_op_num_threads=1;opt.inter_op_num_threads=1
 full=ort.InferenceSession(oracle.SerializeToString(),opt,providers=['CPUExecutionProvider']);fast=ort.InferenceSession(raw.SerializeToString(),opt,providers=['CPUExecutionProvider'])
 errors=[]
 for batch in (1,3,100):
  x=np.random.default_rng(1234).normal(0,.2,(batch,217)).astype(np.float32)
  expected=np.concatenate(full.run(heads,{'input':x}),axis=1);actual=fast.run(None,{'input':x})[0]
  error=float(np.max(np.abs(actual-expected)));assert error<1e-6,(suffix,batch,error);errors.append(error)
 manifest=dict(schema='native_attack_geometry_v1',checkpoint_sha256=runtime['checkpoint_sha256'],source_upper_sha256=sha(source),upper_file=path.name,upper_sha256=sha(path),cone_program_sha256=cone['sha256'],hand_program_sha256=hand['sha256'],node_count=len(nodes))
 (folder/'prophecy_slash_fast.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
 report.append(dict(suffix=suffix,original_nodes=len(model.graph.node),neural_nodes=len(nodes),max_errors=errors,manifest=manifest))
 print(suffix or 'current',len(model.graph.node),'->',len(nodes),'nodes',errors,flush=True)
(ROOT/'Saved/Diagnostics/AttackPerformance20261002/neural-extraction.json').write_text(json.dumps(report,indent=2),encoding='utf8')

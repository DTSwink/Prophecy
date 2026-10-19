"""Actual skeleton, random poses, sliced batches, CUDA graph and output ownership."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
import torch,warp as wp,yaml
from anim.mjcf_char_model import MJCFCharModel
from fused_kinematics import FusedKinematics

torch.set_num_threads(1);wp.init();torch.manual_seed(169)
config=yaml.safe_load((ROOT/'Saved/MimicKitEquipment/recovery-preflight/env_config.yaml').read_text())
model=MJCFCharModel('cuda:0');model.load(config['char_file']);fast=FusedKinematics(model)
n=model.get_num_joints();reports=[]
for batch in (0,1,7,25,512,4096):
    root=torch.randn(batch,3,device='cuda');rot=torch.randn(batch,4,device='cuda');rot=rot/rot.norm(dim=-1,keepdim=True)
    joint=torch.randn(batch,n-1,4,device='cuda');joint=joint/joint.norm(dim=-1,keepdim=True)
    expected=model.forward_kinematics(root,rot,joint);actual=fast(root,rot,joint)
    for a,b in zip(actual,expected):torch.testing.assert_close(a,b,atol=3e-6,rtol=3e-6)
    if batch:
        reports.append(dict(batch=batch,max_position_error=float((actual[0]-expected[0]).abs().max()),max_rotation_error=float((actual[1]-expected[1]).abs().max())))
        sliced=fast(root[::2],rot[::2],joint[::2])
        for a,b in zip(sliced,expected):torch.testing.assert_close(a,b[::2],atol=3e-6,rtol=3e-6)
        saved=actual[0].clone();fast(root+1,rot,joint);torch.testing.assert_close(actual[0],saved,atol=0,rtol=0)
        graph=torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph):graph_out=fast(root,rot,joint)
        root.add_(.25);graph.replay()
        for a,b in zip(graph_out,model.forward_kinematics(root,rot,joint)):torch.testing.assert_close(a,b,atol=3e-6,rtol=3e-6)
        if batch in (25,512):
            timing={}
            for name,fn in [('reference',model.forward_kinematics),('fused',fast),('fused_repeat',fast),('reference_repeat',model.forward_kinematics)]:
                for _ in range(5):fn(root,rot,joint)
                torch.cuda.synchronize();start=time.perf_counter()
                for _ in range(100):fn(root,rot,joint)
                torch.cuda.synchronize();timing[name+'_ms']=(time.perf_counter()-start)*10
            reports[-1]['timings']=timing
path=ROOT/'Saved/MimicKitEquipment/floor-recovery/fused-kinematics.json';path.write_text(json.dumps(reports,indent=2))
print(json.dumps(reports,indent=2));print('PASS')

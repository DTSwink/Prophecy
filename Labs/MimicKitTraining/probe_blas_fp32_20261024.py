"""Actual checkpoint MLPs, alternative FP32 BLAS, no environment startup."""
import io,json,sys,time,traceback,zipfile
from pathlib import Path
import torch
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024'

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    torch.set_float32_matmul_precision('highest');torch.backends.cuda.matmul.allow_tf32=False
    run=ROOT/'runs'/sys.argv[1];backup=json.loads((run/'backup_status.json').read_text())
    with zipfile.ZipFile(run/Path(backup['key']).name) as z:state=torch.load(io.BytesIO(z.read('model.pt')),map_location='cpu',weights_only=True)
    all_results=[]
    for part,count,backward in [('actor',2048,False),('actor',8192,True),('critic',4096,True)]:
        prefix='_model._'+part+'_layers.';layers=[]
        keys=sorted([k for k in state if k.startswith(prefix) and k.endswith('.weight')],key=lambda k:int(k[len(prefix):].split('.')[0]))
        for key in keys:
            weight=state[key];layer=torch.nn.Linear(weight.shape[1],weight.shape[0]);layer.weight.data.copy_(weight);layer.bias.data.copy_(state[key.replace('.weight','.bias')]);layers.extend([layer,torch.nn.ReLU()])
        model=torch.nn.Sequential(*layers).cuda();x=torch.randn((count,layers[0].in_features),device='cuda')
        def call():
            if backward:
                model.zero_grad(set_to_none=True);y=model(x);y.square().mean().backward()
            else:
                with torch.no_grad():y=model(x)
            return y
        snapshots={};timings=[]
        for backend in ['cublas','cublaslt']:
            torch.backends.cuda.preferred_blas_library(backend)
            for _ in range(3):out=call()
            torch.cuda.synchronize();snapshots[backend]=[out.detach().clone()]+([p.grad.clone() for p in model.parameters()] if backward else [])
        for backend in ['cublas','cublaslt','cublaslt','cublas']*3:
            torch.backends.cuda.preferred_blas_library(backend);call();torch.cuda.synchronize();t=time.perf_counter()
            for _ in range(12):call()
            torch.cuda.synchronize();timings.append(dict(backend=backend,seconds=(time.perf_counter()-t)/12))
        checks=[dict(equal=torch.equal(a,b),max_error=float((a-b).abs().max()),relative_l2=float(torch.linalg.vector_norm(a-b)/torch.linalg.vector_norm(a))) for a,b in zip(snapshots['cublas'],snapshots['cublaslt'])]
        all_results.append(dict(part=part,count=count,backward=backward,shapes=[list(state[k].shape) for k in keys],checks=checks,timings=timings))
        (OUT/'blas-fp32-results.json').write_text(json.dumps(all_results,indent=2))
        print(json.dumps(all_results[-1]),flush=True)
    (OUT/'blas-fp32-complete.json').write_text(json.dumps(dict(checkpoint=backup,results=all_results,precision=torch.get_float32_matmul_precision(),allow_tf32=torch.backends.cuda.matmul.allow_tf32),indent=2))

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'blas-fp32-failure.txt').write_text(traceback.format_exc());raise

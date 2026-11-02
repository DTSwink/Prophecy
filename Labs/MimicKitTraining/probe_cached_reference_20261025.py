"""Use actual pinned motion/kinematics data without constructing physics worlds."""
import json
import os
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
OUT=HERE.parent
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(HERE),str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
os.chdir(ROOT)
import numpy as np
import torch
import warp as wp
import yaml
from anim.mjcf_char_model import MJCFCharModel
from anim.motion_lib import MotionLib
from fused_kinematics import install
from final_locomotion import FinalLocomotion
from cached_final_reference_probe import CachedFinalReference,FIELDS


def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    torch.set_float32_matmul_precision('highest');torch.backends.cuda.matmul.allow_tf32=False
    wp.init();wp.set_device('cuda:0')
    config=yaml.safe_load((ROOT/'prepared/env_config.yaml').read_text())
    model=MJCFCharModel('cuda:0');model.load(config['char_file']);install(model)
    library=MotionLib(config['motion_file'],model,'cuda:0')
    cfg=config['perturbed_motion']['final_phase']
    with np.load(cfg['initializations'],allow_pickle=False) as z:
        bank={k:torch.as_tensor(z[k].copy(),device='cuda') for k in z.files if k!='body_names'}
    worlds=2048
    ids=torch.arange(worlds,device='cuda')
    e=SimpleNamespace(_device='cuda:0',_motion_lib=library,_kin_char_model=model,
                      _motion_ids=ids%library.get_num_motions(),_motion_time_offsets=torch.zeros(worlds,device='cuda'))
    values=list(library.calc_motion_frame(e._motion_ids,torch.zeros(worlds,device='cuda')))
    values.append(library.joint_rot_to_dof(values[4]));values.extend(model.forward_kinematics(values[0],values[1],values[4]))
    for field,value in zip(FIELDS,values):setattr(e,field,value.clone())
    f=SimpleNamespace(env=e,cfg=cfg,bank=bank,pushed=(ids%10<2),plus=(ids%10>=3))
    for name in ['choice','kick_choice','first_foot','last_kick','kick_count']:
        setattr(f,name,torch.zeros(worlds,dtype=torch.long,device='cuda'))
    f.kick_error=torch.zeros(worlds,device='cuda');f.last_requested=torch.zeros(worlds,5,2,device='cuda')
    tensors=[getattr(e,n) for n in FIELDS]+[e._motion_time_offsets]+[getattr(f,n) for n in
               ['choice','kick_choice','first_foot','last_kick','kick_count','kick_error','last_requested']]
    saved=[x.clone() for x in tensors]
    def restore():
        for x,y in zip(tensors,saved):x.copy_(y)
    rng=torch.cuda.get_rng_state();begin=time.perf_counter();cached=CachedFinalReference(f);torch.cuda.synchronize()
    construction=time.perf_counter()-begin
    assert torch.equal(rng,torch.cuda.get_rng_state())
    original=lambda rows:FinalLocomotion.reference(f,rows)
    checks=[]
    for count in [0,1,7,63,128,511,2048]:
        rows=ids[:count];restore();rng=torch.cuda.get_rng_state();original(rows)
        expected=[x.clone() for x in tensors];expected_rng=torch.cuda.get_rng_state()
        restore();torch.cuda.set_rng_state(rng);cached(rows)
        for name,x,y in zip(list(FIELDS)+['time','choice','kick_choice','first_foot','last_kick','kick_count','kick_error','last_requested'],tensors,expected):
            assert torch.equal(x,y),(count,name,float((x-y).abs().max()))
        assert torch.equal(expected_rng,torch.cuda.get_rng_state())
        checks.append(dict(rows=count,exact=True,elements=sum(x.numel() for x in tensors),rng_exact=True))
    timings=[]
    for count in [16,128,512]:
        rows=ids[:count]
        for method in [original,cached]:
            for _ in range(5):method(rows)
        for name in ['original','cached','cached','original']*3:
            method=original if name=='original' else cached
            torch.cuda.synchronize();start=time.perf_counter()
            for _ in range(20):method(rows)
            torch.cuda.synchronize()
            timings.append(dict(rows=count,variant=name,milliseconds=(time.perf_counter()-start)*1000/20))
    result=dict(checks=checks,construction_seconds=construction,
                cache_bytes=sum(t.numel()*t.element_size() for ts in cached.cache.values() for t in ts),
                bank_shape={p:list(bank[p+'_motion_time'].shape) for p in ['push','plus']},
                timings=timings,production_changed=False,
                note='Actual reference data and fused FK; microbenchmark shares GPU with production, not an end-to-end speed claim.')
    (OUT/'complete.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='timings'}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc());raise

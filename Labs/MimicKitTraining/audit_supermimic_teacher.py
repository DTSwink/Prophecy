"""CPU-only heldout label/coverage diagnostics; no policy training or inference."""
import json,time
from pathlib import Path
import numpy as np
import torch


def score(y,p):
    return dict(explained_energy=float(1-(y-p).square().sum()/y.square().sum()),
                prediction_rms=float(p.square().mean().sqrt()),target_rms=float(y.square().mean().sqrt()))


def run(folder):
    started=time.perf_counter();torch.set_num_threads(2);folder=Path(folder)
    package=torch.load(folder/'teacher_data.pt',map_location='cpu',weights_only=False)
    data=package['data'];result=dict(shapes={k:[list(t.shape) for t in v] for k,v in data.items()},
        teacher_batches=package['teacher_batches'],scope='Frozen retained dataset; heldout worlds. kNN label predictability does not establish a policy learning bound.')
    tx,ty=data['teacher_train'];vx,vy=data['teacher_valid']
    # Every rollout stores eight consecutive frames in tick-major/world-major order.
    # Reconstruct independently by saved batch counts, validating label scale.
    starts={};start_targets={}
    for split in ['train','valid']:
        x,y=data['teacher_'+split];xs=[];ys=[];offset=0;maxerr=0
        for batch in package['teacher_batches']:
            count=batch['samples']['teacher_'+split];assert count%8==0
            bx=x[offset:offset+count].reshape(8,count//8,-1)
            by=y[offset:offset+count].reshape(8,count//8,-1)
            # Read the actual linear taper to zero at tick8 from the planner.
            # Check every saved label rather than assuming its ordering.
            from supermimic_planning_probe import residual_scale
            expected=torch.tensor([residual_scale(t) for t in range(8)])[:,None,None]*by[0]
            maxerr=max(maxerr,float((by-expected).abs().max()))
            xs.append(bx[0]);ys.append(by[0]);offset+=count
        assert offset==len(x) and maxerr<1e-6,(offset,len(x),maxerr)
        starts[split]=torch.cat(xs);start_targets[split]=torch.cat(ys)
        result[split+'_independent_starts']=len(starts[split])
        result[split+'_taper_max_error']=maxerr
    result['knn']={}
    for stage,(a,b,y,z) in dict(all_frames=(tx,vx,ty,vy),initial_frames=(starts['train'],starts['valid'],start_targets['train'],start_targets['valid'])).items():
        # Physical observation scales were already fixed during data collection.
        for space,cols in [('observation',slice(None)),('physical',slice(0,146)),('commands',slice(146,None))]:
            indices=[];distances=[]
            for v in b.split(128):
                d=torch.cdist(v[:,cols],a[:,cols]);values,ids=d.topk(32,largest=False)
                indices.append(ids);distances.append(values)
            ids=torch.cat(indices);dist=torch.cat(distances)
            item={str(k):score(z,y[ids[:,:k]].mean(1)) for k in [1,4,16,32]}
            item['nearest_observation_distance_quantiles']=torch.quantile(dist[:,0],torch.tensor([0.,.5,.9,1.])).tolist()
            item['mean_target']=score(z,y.mean(0).expand_as(z))
            result['knn'][stage+'_'+space]=item
    # At initial states labels reflect random optimizer proposals; measure how
    # much energy is in common directions versus per-start variation.
    y=start_targets['train'];energy=torch.linalg.svdvals(y).square()
    result['initial_target_spectrum']={str(k):float(energy[:k].sum()/energy.sum()) for k in [1,4,8,16]}
    result['initial_zero_label_fraction']=float((y.abs().max(1).values==0).float().mean())
    result['label_mean_energy_fraction']=float(y.mean(0).square().sum()/y.square().sum(1).mean())
    result['teacher_scores_retained']=False
    result['warning']='Dataset retains observation/residual only, not candidate scores or benefits over zero. Cannot weight labels by proven advantage or audit winner noise from this data.'
    result['seconds']=time.perf_counter()-started
    (folder/'teacher-audit.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    print(json.dumps(run('Saved/MimicKitSuperMimic/teacher-audit'),indent=2))

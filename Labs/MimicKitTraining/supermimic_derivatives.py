"""Directional-derivative supervision from nearby real transitions.

Adapted from CCreal/ddppo model_regular_on_jacobian.py (ICLR 2022).
Use exact Jacobian-vector products instead of materializing every Jacobian.
This tests its model regularizer, not the paper's full two-model algorithm.
"""
import hashlib,json,time
import torch


def directional_prediction(wm,u,du):
    size=len(wm.mean)
    return torch.func.jvp(lambda z:wm.step(z[:,:size],z[:,size:]),(u,),(du,))[1]


def directional_loss(wm,b):
    predicted=directional_prediction(wm,b['direction_u'],b['direction_du'])
    return (predicted-b['direction_dy']).square().mean()


@torch.no_grad()
def nearest_pairs(u,y,scale,neighbors=5,chunk=256):
    """Never pair with self or a duplicate input. Inputs are already normalized.

    Scaling affects neighbor selection only; derivatives retain model units.
    Both sides of every pair must belong to the same train/held-out split.
    """
    z=(u-u.mean(0))/scale
    pairs=[]
    for start in range(0,len(u),chunk):
        distance=torch.cdist(z[start:start+chunk],z)
        distance[distance<1e-3]=float('inf')
        ids=torch.arange(start,min(start+chunk,len(u)),device=u.device)
        distance[torch.arange(len(ids),device=u.device),ids]=float('inf')
        nearest=distance.topk(neighbors,largest=False).indices
        pairs.append(nearest)
    pairs=torch.cat(pairs)
    source=torch.arange(len(u),device=u.device)[:,None].expand_as(pairs).flatten()
    target=pairs.flatten()
    delta=u[target]-u[source]
    if not torch.isfinite(delta).all():raise RuntimeError('Nonfinite neighboring transitions')
    if not ((delta/scale).norm(dim=-1)>1e-3).all():raise RuntimeError('Duplicate derivative pair')
    return dict(direction_u=u[source],direction_du=delta,direction_dy=y[target]-y[source]),source,target


def prepare_pairs(buffer,train_count=8192,heldout_count=2048):
    started=time.perf_counter();b=buffer.data
    u=torch.cat((b['x'][:buffer.count],b['a'][:buffer.count]),-1).flatten(0,1);y=b['next_x'][:buffer.count].flatten(0,1)
    worlds=torch.arange(len(u),device=u.device)%buffer.n
    pools={};stats={}
    scale=u[worlds%10!=0].std(0).clamp_min(.01)
    generator=torch.Generator(device=u.device).manual_seed(418317)
    for name,count,mask in [('train',train_count,worlds%10!=0),('heldout',heldout_count,worlds%10==0)]:
        ids=mask.nonzero().flatten()
        ids=ids[torch.randperm(len(ids),device=u.device,generator=generator)[:count]]
        pairs,source,target=nearest_pairs(u[ids],y[ids],scale)
        assert bool(((worlds[ids[source]]%10==0)==(name=='heldout')).all())
        assert bool(((worlds[ids[target]]%10==0)==(name=='heldout')).all())
        pairs['source_index']=ids[source];pairs['target_index']=ids[target]
        pools[name]=pairs
        distance=(pairs['direction_du']/scale).norm(dim=-1)
        stats[name]=dict(anchors=len(ids),pairs=len(source),distance_median=float(distance.median()),
            distance_p95=float(torch.quantile(distance,.95)),target_change_mse=float(pairs['direction_dy'].square().mean()))
    stats['seconds']=time.perf_counter()-started
    print('MODEL_AUDIT_DIRECTION_PAIRS',json.dumps(stats),flush=True)
    return pools,stats


def sample_pairs(pool,batch,generator=None):
    ids=torch.randint(len(pool['direction_u']),(batch,),device=pool['direction_u'].device,generator=generator)
    return {key:value[ids] for key,value in pool.items() if key.startswith('direction_')}


def pair_hashes(pools):
    return {name:{key:hashlib.sha256(value.cpu().numpy().tobytes()).hexdigest()
                  for key,value in pool.items()} for name,pool in pools.items()}

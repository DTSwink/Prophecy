"""Pure, shared curriculum rules. Bit order matches the four observation flags."""
from itertools import combinations
import numpy as np

LIMBS = ('right_arm', 'left_arm', 'right_leg', 'left_leg')
PARTS = (('upper_arm','lower_arm','hand'), ('upper_arm','lower_arm','hand'),
         ('thigh','shin','foot'), ('thigh','shin','foot'))

def limb_bodies(limb):
    side = LIMBS[limb].split('_')[0]
    return tuple(side+'_'+part for part in PARTS[limb])

def valid_codes(name, count):
    result=[]
    for combo in combinations(range(4), count):
        if name.startswith('limpL') and (3 not in combo or 2 in combo): continue
        if name.startswith('limpR') and (2 not in combo or 3 in combo): continue
        if name == 'crawl' and (0 in combo or 1 in combo): continue
        if name.startswith('crawl') and 0 in combo and 1 in combo: continue
        result.append(sum(1 << j for j in combo))
    assert result or (name == 'crawl' and count == 3), (name,count)
    return result

def crawl_rate(code):
    arms = bool(code & 3)
    legs = int(bool(code & 4)) + int(bool(code & 8))
    # Mixed injuries use the slower factor, explicitly selected by the user.
    return min(.6 if arms else 1., (1., .9, .5)[legs])

def cohorts(motion_ids):
    """Exact rounded 10/30/30/30 quotas, evenly spread over fixed motion rows."""
    ids=np.asarray(motion_ids); n=len(ids)
    result=np.empty(n,dtype=np.int64)
    counts=np.floor(np.array([.1,.3,.3,.3])*n).astype(int)
    for k in np.argsort(-(np.array([.1,.3,.3,.3])*n-counts),kind='stable')[:n-counts.sum()]: counts[k]+=1
    motions=np.unique(ids); sizes=np.array([(ids==m).sum() for m in motions])
    ideal=sizes[:,None]*np.array([.1,.3,.3,.3]); table=np.floor(ideal).astype(int)
    base=table.copy(); extras=np.zeros_like(table)
    def add(k,seen):
        if k in seen:return False
        seen=seen|{k}
        order=sorted(range(len(motions)),key=lambda i: (ideal[i,k]-base[i,k],-i),reverse=True)
        for i in order:
            if extras[i,k] or ideal[i,k]-base[i,k]<1e-10:continue
            if (base[i]+extras[i]).sum()<sizes[i]:
                extras[i,k]=1;return True
            for other in np.flatnonzero(extras[i]):
                if add(int(other),seen):
                    extras[i,other]=0;extras[i,k]=1;return True
        return False
    for k,need in enumerate(counts-base.sum(0)):
        for _ in range(need):assert add(k,set()),'Cannot round cohort allocation'
    table=base+extras
    for i,m in enumerate(motions):
        slots=sorted(((j+.5)/c,k) for k,c in enumerate(table[i]) for j in range(c))
        for w,(_,k) in zip(np.flatnonzero(ids==m),slots): result[w]=k
    return result

def migrate_disabled_arm_flags(agent):
    """Old arms were always enabled: keep that input zero, scale new zeros to -1."""
    import torch
    norm=agent._obs_norm
    assert norm._mean.shape==(160,)
    old=norm._std[154:156].detach().clone()
    with torch.no_grad():
        # Do not transform first-layer weights: preserve all existing behavior
        # at flags=1, while making the previously unseen disabled value usable.
        assert bool(torch.allclose(norm._mean[154:156],torch.ones_like(old)))
        norm._std[154:156].clamp_(min=1.)
        if norm._mean_sq is not None:
            norm._mean_sq[154:156]=norm._mean[154:156].square()+norm._std[154:156].square()
    return dict(channels=[154,155],old_std=old.cpu().tolist(),new_std=norm._std[154:156].cpu().tolist(),
        mean_unchanged=True,weights_unchanged=True,vanilla_input_unchanged=True,
        reason='Previously constant enabled-arm flags; avoid saturating normalized input when disabled')

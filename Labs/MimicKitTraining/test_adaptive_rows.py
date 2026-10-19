"""Small deterministic contracts; no physics or training launched."""
import json
import time
from pathlib import Path
import numpy as np
import torch
from adaptive_rows import AdaptiveRows, allocate


def main():
    torch.set_num_threads(1)
    pools = torch.tensor([[0., 0., .25, .25, .25, .25], [.5, .5, 0., 0., 0., 0.]])
    assignments = torch.tensor([0, 1] + [2]*20 + [3]*20 + [4]*20 + [5]*20)
    sampler = AdaptiveRows(assignments, pools, 2)
    actual = assignments.clone()
    ids = torch.arange(len(actual))
    # Startup, evaluation, and the forced reset after evaluation do not count.
    sampler.record_reset(ids, actual, torch.zeros_like(ids), True)
    sampler.record_reset(ids, actual, torch.ones_like(ids), False)
    sampler.record_reset(ids, actual, torch.ones_like(ids), True)
    assert not sampler.counts.any()
    done = torch.where(actual == 2, 1, 3)
    sampler.record_reset(ids, actual, done, True)
    assert sampler.counts[0].sum() == len(ids) and sampler.counts[1].sum() == 20
    assert sampler.report(assignments, sampler.next_report-1) is None
    report = sampler.report(assignments, sampler.next_report)
    assert report['completed'] == [1,1,20,20,20,20]
    assert report['multiplier'] == [1,1,3,1,1,1]
    assert report['counts'][2:] == [40,14,13,13]
    assert report['reassigned'] == 20  # minimal changes, not a reshuffle
    assert torch.equal(actual, torch.tensor([0,1]+[2]*20+[3]*20+[4]*20+[5]*20))
    # Adopting pending assignments is per completed episode, not immediate.
    reset_ids = torch.tensor([0,25,45,65])
    untouched = actual.clone()
    actual[reset_ids] = assignments[reset_ids]
    mask = torch.ones(len(actual),dtype=torch.bool); mask[reset_ids]=False
    assert torch.equal(actual[mask],untouched[mask])
    # No repeated 3x multiplication; a clean minute returns to the base weight.
    sampler.record_reset(ids, assignments, torch.ones_like(ids), True)
    again = sampler.report(assignments, sampler.next_report)
    assert again['multiplier'] == [3]*6
    sampler.record_reset(ids, assignments, torch.full_like(ids,3), True)
    clean = sampler.report(assignments, sampler.next_report)
    assert clean['multiplier'] == [1]*6
    state = sampler.state(assignments)
    restored = AdaptiveRows(assignments, pools, 2)
    restored.restore(state, assignments)
    assert restored.report_number == sampler.report_number
    assert not restored.episode_training.any()
    # Actual 50-clip pool: quotas, idle exclusivity, all motions retained.
    root=Path(__file__).resolve().parents[2]
    manifest=json.loads((root/'Saved/MimicKitEquipment/package/prepared/manifest.json').read_text())['motions']
    import yaml
    weights=yaml.safe_load((root/'Saved/MimicKitEquipment/package/prepared/motions.yaml').read_text())['motions']
    by_id={x['id']:x for x in manifest}
    gaits=np.array([by_id[Path(x['file']).stem]['gait'] for x in weights])
    w=np.array([x['weight'] for x in weights]); pools_np=np.stack([w*(gaits!=-1),w*(gaits==-1)])
    pools_np/=pools_np.sum(-1,keepdims=True)
    original=np.concatenate([np.searchsorted(pool.cumsum(),(np.arange(n)+.5)/n) for pool,n in [(pools_np[1],31),(pools_np[0],481)]])
    for _ in range(100):
        multiplier=np.random.default_rng(_).uniform(1,3,len(gaits))
        updated=allocate(original,pools_np,31,multiplier)
        assert len(updated)==512 and np.all(gaits[updated[:31]]==-1) and np.all(gaits[updated[31:]]!=-1)
        assert len(np.unique(updated))==len(gaits)
        assert np.array_equal(allocate(updated,pools_np,31,multiplier),updated)
    print('PASS: training-only terminal counts, capped weights, reset adoption, minimal churn, state restore, actual 512-world quotas')


if __name__=='__main__':main()

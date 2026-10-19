"""Minute reports rebalance fixed motion assignments, never active episodes."""
import time
import numpy as np
import torch


def allocate(previous, pools, idle_rows, multiplier):
    """Largest-remainder quotas; retain as many existing assignments as possible."""
    result = np.asarray(previous, dtype=np.int64).copy()
    for begin, end, pool in ((0, idle_rows, pools[1]), (idle_rows, len(result), pools[0])):
        weights = np.asarray(pool) * multiplier
        eligible = np.flatnonzero(weights > 0)
        count = end - begin
        # Preserve coverage: each admitted motion gets at least one world.
        minimum = 1 if count >= len(eligible) else 0
        quota = weights[eligible] / weights[eligible].sum() * count
        counts = np.maximum(np.floor(quota).astype(int), minimum)
        while counts.sum() < count:
            counts[np.argmax(quota-counts)] += 1
        while counts.sum() > count:
            surplus = np.where(counts > minimum, counts-quota, -np.inf)
            counts[np.argmax(surplus)] -= 1
        desired = dict(zip(eligible.tolist(), counts.tolist()))
        spare = []
        for world in range(begin, end):
            motion = int(result[world])
            if desired.get(motion, 0):
                desired[motion] -= 1
            else:
                spare.append(world)
        replacements = [motion for motion, n in desired.items() for _ in range(n)]
        result[spare] = replacements
    return result


class AdaptiveRows:
    def __init__(self, assignments, pools, idle_rows, seconds=60., max_weight=3.):
        self.device = assignments.device
        self.pools = pools.cpu().numpy()
        self.idle_rows = idle_rows
        self.seconds, self.max_weight = seconds, max_weight
        self.counts = torch.zeros((2, pools.shape[1]), device=self.device, dtype=torch.int64)
        self.multiplier = np.ones(pools.shape[1])
        self.episode_training = torch.zeros(len(assignments), device=self.device, dtype=torch.bool)
        self.next_report = time.monotonic() + seconds
        self.report_number = 0

    def record_reset(self, ids, motion_ids, done, training):
        # Called before reset clears done flags. No GPU readback here.
        if training and len(ids):
            terminal = ((done[ids] == 1) | (done[ids] == 2) | (done[ids] == 3)) & self.episode_training[ids]
            self.counts[0].scatter_add_(0, motion_ids[ids], terminal.long())
            self.counts[1].scatter_add_(0, motion_ids[ids], (terminal & (done[ids] == 1)).long())
        self.episode_training[ids] = training

    def report(self, assignments, now=None):
        now = time.monotonic() if now is None else now
        if now < self.next_report:
            return None
        completed, failed = self.counts.cpu().numpy().copy()
        seen = completed > 0
        self.multiplier[seen] = 1 + (self.max_weight - 1) * failed[seen] / completed[seen]
        previous = assignments.cpu().numpy().copy()
        updated = allocate(previous, self.pools, self.idle_rows, self.multiplier)
        assignments.copy_(torch.as_tensor(updated, device=self.device))
        self.counts.zero_()
        self.report_number += 1
        result = dict(report=self.report_number, completed=completed.tolist(), failed=failed.tolist(),
                      multiplier=self.multiplier.tolist(), counts=np.bincount(updated, minlength=len(completed)).tolist(),
                      reassigned=int((previous != updated).sum()), interval_seconds=self.seconds,
                      elapsed_seconds=float(self.seconds + now - self.next_report))
        self.next_report = now + self.seconds
        return result

    def state(self, assignments):
        return dict(assignments=assignments.cpu(), counts=self.counts.cpu(),
                    multiplier=self.multiplier.tolist(), report_number=self.report_number,
                    seconds_remaining=max(0., self.next_report-time.monotonic()))

    def restore(self, state, assignments):
        assignments.copy_(state['assignments'].to(self.device))
        self.counts.copy_(state['counts'].to(self.device))
        self.multiplier = np.array(state['multiplier'])
        self.report_number = state['report_number']
        self.next_report = time.monotonic() + state['seconds_remaining']

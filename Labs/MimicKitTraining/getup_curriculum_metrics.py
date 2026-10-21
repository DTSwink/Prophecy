"""Read existing noiseless rollouts; no extra simulation or training work."""
import math


def summarize(replay):
    groups = {}
    for row in replay.get('replay_rows', []):
        if (not row.get('recovery_row') or row.get('perturbed_row', False)
                or abs(row.get('recovery_start_seconds', 1.)) > 1e-6
                or row.get('mode') != 'deterministic evaluation'):
            continue
        path = row.get('recovery_motion_file', '').lower()
        side = 'front' if 'front' in path else 'back' if 'back' in path else None
        if side is None:
            continue
        ticks = round(row['duration_seconds'] * row['fps'])
        flag = int(row['terminal_flag'])
        item = dict(side=side, drawn=bool(row['sword_drawn']), ticks=ticks,
                    survived_ticks=max(0, ticks - (flag == 1)), terminal_flag=flag,
                    completed=flag == 2 and bool(row.get('complete_episode')))
        groups.setdefault((side, item['drawn']), []).append(item)
    required = [(side, drawn) for side in ('front', 'back') for drawn in (False, True)]
    covered = all(key in groups for key in required)
    rows = [r for group in groups.values() for r in group]
    return dict(iteration=replay.get('iteration'), samples=replay.get('samples'),
                generated_unix=replay.get('generated_unix'), groups_covered=covered,
                rows=rows,
                both_reach_25=covered and all(r['survived_ticks'] >= 25 for r in rows),
                both_complete=covered and all(r['completed'] for r in rows))

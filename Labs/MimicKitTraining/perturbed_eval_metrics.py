"""Outcome percentages from recorded evaluation episodes, never training estimates."""


def outcome_scalars(rows):
    """Exclude incomplete/unknown episodes; flag1 is failure, flag3 is a reset."""
    rows = [r for r in rows if r.get('perturbed_row')
            and r.get('complete_episode')
            and r.get('mode') == 'deterministic evaluation'
            and r.get('terminal_flag') in (1, 2, 3)]
    loco = [r for r in rows if r.get('idle_row') is False]
    getups = [r for r in rows if r.get('recovery_row')]
    values = {}
    for label, group in [('all', rows), ('locomotion', loco)]:
        if group:
            values[label+'_no_failure_percent'] = 100 * sum(r['terminal_flag'] != 1 for r in group)/len(group)
            values[label+'_episodes'] = len(group)
    # Both head-height and timeout resets have flag3. Use the captured final
    # reason to distinguish them; missing reasons must never count as success.
    known = [r for r in getups if r.get('frame_reset_reason')
             and r['frame_reset_reason'][-1] in (1, 2, 3)]
    if known:
        values['getup_episodes'] = len(known)
        values['getup_failure_percent'] = 100 * sum(r['terminal_flag'] == 1 for r in known)/len(known)
        for label, reason in [('head_reset', 2), ('timeout', 3)]:
            values['getup_'+label+'_percent'] = 100 * sum(
                r['terminal_flag'] == 3 and r['frame_reset_reason'][-1] == reason
                for r in known)/len(known)
    return {'perturbed_eval_sample/'+key: value for key, value in values.items()}

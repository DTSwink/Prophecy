from perturbed_eval_metrics import outcome_scalars


def episode(flag, reason, idle=False, recovery=False, **kw):
    return dict(perturbed_row=True, complete_episode=True, mode='deterministic evaluation',
                terminal_flag=flag, frame_reset_reason=[0, reason],
                idle_row=idle, recovery_row=recovery, **kw)


def test_failures_are_distinct_from_resets():
    rows = [episode(1, 1), episode(3, 3), episode(3, 2, True, True),
            episode(3, 3, True, True), episode(3, 3, True)]
    result = outcome_scalars(rows)
    prefix = 'perturbed_eval_sample/'
    assert result[prefix+'all_no_failure_percent'] == 80
    assert result[prefix+'locomotion_no_failure_percent'] == 50
    assert result[prefix+'getup_head_reset_percent'] == 50
    assert result[prefix+'getup_timeout_percent'] == 50
    assert result[prefix+'getup_episodes'] == 2


def test_incomplete_normal_and_missing_reasons_are_not_success():
    rows = [dict(episode(3, 2, True, True), complete_episode=False),
            dict(episode(3, 3), perturbed_row=False),
            dict(episode(3, 2, True, True), frame_reset_reason=[])]
    result = outcome_scalars(rows)
    assert result['perturbed_eval_sample/all_episodes'] == 1
    assert 'perturbed_eval_sample/getup_head_reset_percent' not in result
    assert 'perturbed_eval_sample/locomotion_no_failure_percent' not in result


if __name__ == '__main__':
    test_failures_are_distinct_from_resets()
    test_incomplete_normal_and_missing_reasons_are_not_success()
    print('Outcome classification checks passed')

"""Episode handoff for P/P+, push-relative handoff for P-minus idle."""
import torch


def tracking_handoff(ticks, perturbed_rows, minus_rows, last_kick, ae_ticks, blend_ticks):
    episode = ((ticks - ae_ticks) / blend_ticks).clamp(0., 1.)
    result = torch.where(perturbed_rows, episode, 1.)
    since_push = ticks - last_kick
    pushed = ((since_push - ae_ticks) / blend_ticks).clamp(0., 1.)
    pushed = torch.where(last_kick >= 0, pushed, 1.)
    return torch.where(minus_rows, pushed, result)

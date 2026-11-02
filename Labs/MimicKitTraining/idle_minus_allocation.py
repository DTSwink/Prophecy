"""Reserve extra pushed-idle rows while retaining the other idle counts."""
import math


def idle_layout(config, worlds):
    fraction = float(config['idle_row_fraction'])
    normal_fraction = 1-float(config['perturbed_motion']['fraction'])
    idle = int(worlds*fraction+.5)
    normal_idle = round(round(worlds*normal_fraction)*fraction)
    old_minus = round(normal_idle*.5)
    minus = max(old_minus, math.ceil(worlds*config['perturbed_motion'].get('idle_minus_min_fraction', 0)))
    extra = minus-old_minus
    return idle+extra, normal_idle+extra, minus

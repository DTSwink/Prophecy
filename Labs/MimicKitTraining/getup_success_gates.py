"""Add opt-in feet-height and head-speed gates to the pinned recovery package."""
import ast
import hashlib
import json
import textwrap
import zipfile
from pathlib import Path

import torch
import yaml

HELPER = '''def getup_success_stability(feet_height, head_vertical_velocity, feet_limit, speed_limit):
    """World-Z body-origin measurements, strict bounds; no extra physics steps."""
    return (feet_height < feet_limit).all(dim=-1) & (head_vertical_velocity.abs() < speed_limit)


'''


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Unexpected source while patching: ' + old[:90])
    return source.replace(old, new)


def patch(source):
    source = replace_once(source, 'def blend_root_pose(', HELPER + 'def blend_root_pose(')
    anchor = "        self._head_reset_height = self._idle_head_height * float(cfg['getup_head_reset_fraction'])\n"
    source = replace_once(source, anchor, anchor + '''        self._success_feet_ids = [names.index('left_foot'), names.index('right_foot')]
        self._success_feet_limit = cfg.get('getup_success_max_feet_height_m')
        self._success_speed_limit = cfg.get('getup_success_max_head_vertical_speed_m_s')
        if (self._success_feet_limit is None) != (self._success_speed_limit is None):
            raise ValueError('Get-up success feet and head-speed limits must be configured together')
        if self._success_feet_limit is not None:
            if not all(math.isfinite(float(v)) and float(v) > 0 for v in (self._success_feet_limit, self._success_speed_limit)):
                raise ValueError('Get-up success limits must be finite and positive')
''')
    anchor = '        head_reset = self._perturbed_getup & head_up & (ticks > 0)\n'
    source = replace_once(source, anchor, anchor + '''        if self._success_feet_limit is not None:
            char = self._get_char_id()
            head_rot = self._engine.get_body_rot(char)[:, self._head_id]
            head_ang = self._engine.get_body_ang_vel(char)[:, self._head_id]
            # Engine velocity is at COM; the recorded head height/velocity use its body origin.
            head_offset = q.quat_rotate(head_rot, self._body_com[:, self._head_id])
            head_vel = self._engine.get_body_vel(char)[:, self._head_id] - torch.cross(head_ang, head_offset, dim=-1)
            feet_height = self._engine.get_body_pos(char)[:, self._success_feet_ids, 2]
            head_reset &= getup_success_stability(feet_height, head_vel[:, 2], self._success_feet_limit, self._success_speed_limit)
''')
    anchor = '            head_reset_height_m=float(self._head_reset_height[self._motion_ids[world]]) if getup else None,\n'
    source = replace_once(source, anchor, anchor + '''            success_max_feet_height_m=self._success_feet_limit if getup else None,
            success_max_head_vertical_speed_m_s=self._success_speed_limit if getup else None,
            success_measurement='world Z at body origins; absolute head vertical speed' if getup and self._success_feet_limit is not None else None,
''')
    ast.parse(source)
    return source


def patch_recorder(source):
    source = source.replace('\r\n', '\n')
    anchor = "                reset_reason_codes={'0':'none or normal-cohort rules','1':'failure','2':'head-height reset','3':'time reset (bootstrap)'})\n"
    return replace_once(source, anchor, anchor + '''        if self.prior_values is not None and getattr(self.env, '_success_feet_limit', None) is not None:
            metadata['reset_reason_codes']['2'] = 'standing success reset (head height, feet height, head speed)'
''')


def check(calibration):
    scope = {}
    exec(HELPER, {'torch': torch}, scope)
    gate = scope['getup_success_stability']
    f, v = calibration['max_feet_height_m'], calibration['max_head_vertical_speed_m_s']
    feet = torch.tensor([[calibration['left_foot_height_m'], calibration['right_foot_height_m']],
                         [f*.5, f*.5], [f*.5, f*2], [f*2, f*.5],
                         [f*.5, f*.5], [f*.5, f*.5], [f*.5, f*.5], [f, f*.5]], dtype=torch.float64)
    speed = torch.tensor([calibration['head_origin_vertical_velocity_m_s'], v*.5, 0., 0., v*2, -v*2, v, 0.], dtype=torch.float64)
    expected = [False, True, False, False, False, False, False, False]
    assert gate(feet, speed, f, v).tolist() == expected
    # Scope remains the existing perturbed/head-up/nonzero-tick mask.
    eligible = torch.tensor([False, True, True])
    assert (eligible & gate(torch.zeros((3,2)), torch.zeros(3), f, v)).tolist() == [False, True, True]


def prepare():
    import resume_getup_success as r
    from backup import verified_readback
    out = r.OUT
    calibration = json.loads((out/'getup-success-gates-calibration.json').read_text())
    check(calibration)
    plan = json.loads((out/'getup-success-prepared.json').read_text())
    (out/'getup-success-gates-previous-plan.json').write_text(json.dumps(plan, indent=2))
    with zipfile.ZipFile(plan['source']['local']) as z:
        entries = {n:z.read(n) for n in z.namelist()}
    entries['pipeline/perturbed_omni.py'] = patch(entries['pipeline/perturbed_omni.py'].decode()).encode()
    entries['pipeline/observe.py'] = patch_recorder(entries['pipeline/observe.py'].decode()).encode()
    cfg = yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion'].update(getup_success_max_feet_height_m=calibration['max_feet_height_m'],
        getup_success_max_head_vertical_speed_m_s=calibration['max_head_vertical_speed_m_s'])
    entries['prepared/env_config.yaml'] = yaml.safe_dump(cfg, sort_keys=False).encode()
    # Apply the same optional change locally without copying unrelated pinned source over it.
    for name, transform in [('perturbed_omni.py', patch), ('observe.py', patch_recorder)]:
        p = Path(__file__).with_name(name)
        p.write_text(transform(p.read_text()), encoding='utf-8')
    archive = out/'getup-success-gates-source.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, data in entries.items():z.writestr(n, data)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    key = 'mimickit/pipeline_20261014/equipment/getup-success-gates/source_'+digest[:12]+'.zip'
    c = r.cloud.s3()
    c.put_object(Bucket=r.cloud.rp.VOLUME_ID, Key=key, Body=archive.read_bytes())
    verified_readback(c, r.cloud.rp.VOLUME_ID, key, digest)
    plan['source'] = dict(local=str(archive), key=key, sha256=digest)
    plan['run_suffix'] = 'uefn_getup_success_gates_1024'
    (out/'getup-success-gates-prepared.json').write_text(json.dumps(plan, indent=2))
    print(json.dumps(dict(source=plan['source'], tests='passed', limits=calibration)), flush=True)


if __name__ == '__main__':
    prepare()

"""Turning upper inputs match Unreal's root-local contract, independently of world yaw."""
import gzip
import json
from pathlib import Path
from unittest.mock import patch
import nn_worker as W
import directional_nn as D

ROOT = Path(__file__).resolve().parent
torch = W.torch
fixture = json.loads(gzip.decompress((ROOT/'data/upper-heading-fixture.json.gz').read_bytes()))
owner = D.configure_direction(W.ResumeLocomotion('run'), 'run', 'left')
original_compile = W.compiled_step
errors = dict(bridge=0., upper=0., pelvis=0., base=0.)
calls = 0

def audited_compile(o, mode, seed_basis, seed_heading, example):
    step = original_compile(o, mode, seed_basis, seed_heading, example)
    bridge = seed_basis @ seed_heading.transpose(-1, -2)
    full = o.runtime.full_by_mode[mode]
    rest = o.runtime.rest_offsets_by_mode[mode][0]
    geometry = o.runtime.full_geometry_by_mode[mode]

    # Independent transcription of the game's LowerTransformToHeading and
    # BuildUpperBaseFromLower. Neither uses the root's changing world heading.
    def transform(lower, pos=0, rot=3):
        return torch.cat((lower[:, pos:pos+3] @ bridge[0],
            W.tl.rotmat_to_6d(W.tl.rotation_6d_to_matrix(lower[:, rot:rot+6]) @ bridge)), -1)

    def base(lower):
        pelvis_rot = W.tl.rotation_6d_to_matrix(lower[:, 3:9])
        rotation = W.tl.rotmat_to_6d(pelvis_rot @ bridge)
        chunks = [W.tl.rotmat_to_6d(torch.eye(3)).reshape(1, 6).repeat(1, 10)]
        for side in ('l', 'r'):
            hand = full.body_names.index('hand_'+side)
            point = lower[:, :3] + (rest[hand].reshape(1, 1, 3) @ pelvis_rot).squeeze(1)
            chunks.extend((point @ bridge[0], rotation, rotation))
        return W.upper_data.clean_upper_state(torch.cat(chunks, -1))

    def audited(*args):
        global calls
        previous, current, prev_upper, cur_upper, prev_pelvis, current_base, root, next_root, features, basis, heading, next_basis, next_heading = args
        actual = step(*args)
        following, upper, pelvis, next_base, pins = actual
        expected_pelvis = transform(following)
        expected_base = base(following)
        prior = W.upper_data.clean_upper_state(expected_base + cur_upper - base(current))
        inp = torch.cat((prev_upper, prior, transform(previous), transform(current), expected_pelvis,
            features, torch.tensor([[mode]]), transform(current, 9, 12), transform(current, 25, 28),
            transform(following, 9, 12), transform(following, 25, 28), torch.zeros(1, 2)), -1)
        expected_upper = W.upper_data.clean_upper_state(prior + o.agent(inp))
        expected_upper = W.upper_ctl.clamp_viewer_forearm_lengths(full, expected_upper, expected_pelvis,
            geometry['local_offsets'][0:1], geometry['ik_limb_lengths'][0:1])
        for key, a, b in [('bridge', next_basis @ next_heading.transpose(-1, -2), bridge),
                          ('upper', upper, expected_upper), ('pelvis', pelvis, expected_pelvis),
                          ('base', next_base, expected_base)]:
            errors[key] = max(errors[key], float((a-b).abs().max()))
            torch.testing.assert_close(a, b, atol=2e-5, rtol=1e-5)
        calls += 1
        return actual
    return audited

with W.inference_execution(), patch.object(W, 'compiled_step', audited_compile):
    fixed = D.generate_command(owner, dict(fixture['request'], verifyReference=True))
    straight = D.generate_command(owner, dict(fixture['request'], rootYawSpeed=0))

lower_names = ['pelvis', *[name+'_'+side for side in ('l','r') for name in ('thigh','calf','foot','ball')]]
indices = [fixed['names'].index(name) for name in lower_names]
for old, new in zip(fixture['before']['poses'], fixed['poses']):
    for channel in ('points', 'axes'):
        assert [old[channel][i] for i in indices] == [new[channel][i] for i in indices], channel
for channel in ('roots', 'pins', 'rootYawDegrees'):
    assert fixture['before'][channel] == fixed[channel], channel
for channel in ('poses', 'roots', 'pins'):
    assert fixture['straight'][channel] == straight[channel], 'nonturning '+channel

# Whole-world yaw must not alter a body-relative policy response. Includes a
# nonzero yaw seed and its previous pose, not just zero-heading initialization.
seed = fixture['resume']
seed['frames'] = 30
seed['roots'] = seed['roots'][:39]
seed['rootYawDegrees'] = seed['rootYawDegrees'][:39]
turned = json.loads(json.dumps(seed))
angle = 123.
rotation = W.tl.yaw_to_row_matrix(torch.tensor([-angle*torch.pi/180]))[0]
turned['roots'] = (torch.tensor(seed['roots']) @ rotation).tolist()
turned['rootYawDegrees'] = [x+angle for x in seed['rootYawDegrees']]
for pose in turned['seeds']:
    pose['points'] = (torch.tensor(pose['points']) @ rotation).tolist()
    pose['axes'] = (torch.tensor(pose['axes']) @ rotation).tolist()
with W.inference_execution():
    a = D.resume_in_course(owner, seed)
    b = D.resume_in_course(owner, turned)
equivariance = {}
for channel in ('points', 'axes'):
    expected = torch.tensor([p[channel] for p in a['poses']]) @ rotation
    actual = torch.tensor([p[channel] for p in b['poses']])
    equivariance[channel] = float((expected-actual).abs().max())
    torch.testing.assert_close(actual, expected, atol=2e-4, rtol=2e-4)

result = dict(passed=True, policySteps=calls, gameContractErrors=errors,
    rotatedWorldErrors=equivariance, originalLowerReference=fixed['referenceError'],
    rootWindowReference=fixed['windowReferenceError'],
    checks=['upper inputs/output match game equations each tick',
            'turning raw pelvis/legs/roots/pins byte-identical',
            'nonturning whole pose byte-identical',
            'rotating world and both history samples preserves body-relative motion'])
(ROOT/'snapshots/upper-heading-verification.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))

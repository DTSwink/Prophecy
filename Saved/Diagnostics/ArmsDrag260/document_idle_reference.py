from pathlib import Path
import json
p=Path(__file__).parent;root=p.parents[2]
d=json.loads((p/'idle_reference_analysis.json').read_text())
t=d['samples']['270'];before=t['before']['twist_idle_deg'];after=t['after']['twist_idle_deg']
entry=f'''**Idle-centered wrist reference, September30:** the user's intended center is the authored idle wrist, not the outgoing attack wrist. Recovery now decodes the existing `ProphecyUpperIdleSeed` (`M_Neutral_Stand_Idle_Loop`, frame0), stores `inverse(idle spine_05 rotation) * idle hand_r rotation`, and derives anatomical up from the same idle spine_05→neck_01. The allowed +/- limit is centered there and carried by the current spine. Recoil still begins at upper release, affects only right wrist rotation and shares the existing hold/blend. Swing remains governed by the existing orientation-damping rules; this is not a whole-pose return-to-idle feature.

The idle reference is decoded once on first active wrist recovery per agent and reused across attacks; no checkpoint inference, per-tick idle decoding, or disabled pose work. Separate cache preserves Live Coding layouts, is released on agent/world removal, and is shared by correction/debug measurement. Before that first recovery there is no cached wrist arc to preview. Left recoil remains disabled, cone-only recurrent feedback and all positional isolation remain intact.

Matched350-tick current **idle-after-attack** captures preserve the user's cone150/wrist60000/limit5/damping10/hold2.5/blend0.5. At270, idle-relative right twist changes {before:.6f}→{after:.6f}degrees; maximum absolute twist over230–300 is {d['max_abs_twist_230_300']:.6f}degrees. All six arm joint positions in future/presented match within {d['max_joint_position_difference_cm']:.9f}cm, left rotation within {d['max_left_rotation_difference_degrees']:.9f}degrees. Exactly one idle reference decode logged for the player. Solver target/realized error <= {d['max_solver_twist_error_deg']:.9f}degrees; all recorded transforms finite. Evidence `Saved/Diagnostics/ArmsDrag260/wrap_idle_before.json`, `wrap_idle_after.json`, native logs and `idle_reference_analysis.json`. Owned PIE ended/audits reset, BP values/wiring unchanged. Focused tests cover canonical idle, stationary outgoing twist recoiling toward idle, unchanged actual idle, cache reuse/cleanup, disabled and during-attack bypass, plus prior geometry/damping/invariants. No full suite or push.

'''
path=root/'Docs/ArmRepellantCone.md';s=path.read_text(encoding='utf-8')
s=s.replace('### Wrist twist recoil\n\n','### Wrist twist recoil\n\n'+entry,1)
s=s.replace('using the outgoing wrist pose as its reference.','using the authored idle wrist in spine space as its reference.')
s=s.replace('The reference is the outgoing wrist orientation at upper release and anatomical spine-up (spine_05 toward neck_01), stored in spine_05 space.','The reference is the authored idle wrist orientation and idle anatomical spine-up (spine_05 toward neck_01), stored in spine_05 space and first used at upper release.')
path.write_text(s,encoding='utf-8')
path=root/'ProjectJournal.md';s=path.read_text(encoding='utf-8')
summary=f'''- **Wrist recoil now centers on authored idle (September30):** user corrected the intended reference: end-of-attack wrist was wrong. Uses existing frame0 neutral idle seed, hand_r relative to idle spine_05, with idle anatomical up; carried by current spine. Idle is decoded once per agent on first active recovery, cached/reused across attacks; no additional NN inference or disabled pose work. Right-only, upper-release timing, hold/blend, rotation-only publication and no wrist recurrent feedback preserved. Same350-tick idle-after-attack setup at recoil60000/limit5/hold2.5: tick270 idle-relative twist {before:.3f}→{after:.3f}degrees; arm positions unchanged within {d['max_joint_position_difference_cm']:.9f}cm, left wrist unchanged. Evidence Saved/Diagnostics/ArmsDrag260/wrap_idle_before/wrap_idle_after and idle_reference_analysis.json. Owned PIE ended/audits0, no BP edits/save/full suite/push. Earlier outgoing-reference descriptions below are historical. [Contract and verification](Docs/ArmRepellantCone.md).

'''
s=s.replace('## Resume here\n\n','## Resume here\n\n'+summary,1);path.write_text(s,encoding='utf-8')
print('Updated idle-reference contract and journal')

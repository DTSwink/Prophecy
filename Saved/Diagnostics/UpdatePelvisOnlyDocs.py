from pathlib import Path
p=Path('Docs/AttackStartPelvisInertia.md');s=p.read_text();old=s[s.index('Normal editor build succeeded'):];s='''# Attack-start pelvis inertia

`Set Attack Start Pelvis Inertia`: Enabled; Translation Window Frames5 / Translation Inertia1; Rotation Window Frames5 / Rotation Inertia1. Off until configured. The foot-inertia experiment was removed completely at the user's request on2026-09-24, restoring the original pelvis-only implementation and Blueprint signature.

The previous displayed WORLD pelvis translation/angular deltas are latched once on a new full attack. Strength1 preserves each delta on the first frame, then linearly fades to the authored attack target by the corresponding final frame. Windows count unpaused game ticks (60 per authored second), not wall time or30Hz policy steps. Windows<=1 or strength0 bypass that channel. Retriggering an ongoing attack does not restart inertia. Half attacks retain locomotion pelvis ownership. End/cancel/reset clears motion; initial-agent reset restores captured pelvis settings.

The original MoveHip solve moves each hip with the corrected pelvis while preserving reachable authored ankles, their rotations and both segment lengths. Only unreachable ankles are projected to the original reach shell. The added independent ankle target, foot/toe rotation override, multi-body correction/history and generic post-clamp foot sampler are removed. Existing locomotion leg reconstruction, knee smoothing, calf recovery and clamps from before the experiment remain unchanged.

Disabled/all-zero configuration removes pelvis history and active correction, with no sampling, extra inference or timer. Enabled configuration retains only two pelvis presentation samples; readers share one correction per game tick. Physical and rendered targets use the original common pelvis correction. Raw checkpoint recurrence and root window remain unchanged.

## Rollback validation

Original source/leg solve/sampling restored; closed-editor build and focused checks pending. Walk raw-limit removal is deliberately retained as a separate requested change.

## Original pelvis-only validation

'''+old;p.write_text(s)
p=Path('ProjectJournal.md');s=p.read_text(encoding='utf-8');a=s.index('- **Attack-start lower-body inertia2026-09-24:**');b=s.index('\n',a);s=s[:a]+'''- **Attack-start pelvis inertia2026-09-24:** foot-inertia experiment fully removed at user request. Restored original pelvis-only Set Attack Start Pelvis Inertia signature/settings/history, ReadPelvisWorld sampler, original MoveHip leg handling and original tests. Removed ankle-target override, foot/toe rotation handling and generic foot sampler; pre-existing locomotion reconstruction/clamps/knee smoothing/calf recovery remain. Walk raw pin-limit removal retained separately. Original tick timing, latching/retrigger, disable/end/reset behavior unchanged. Rollback normal build/checks pending; using prior save/restart authorization, current pose BP saved with backup BP-BeforePelvisOnlyRollback.uasset. [Current contract](Docs/AttackStartPelvisInertia.md).'''+s[b:];p.write_text(s,encoding='utf-8')

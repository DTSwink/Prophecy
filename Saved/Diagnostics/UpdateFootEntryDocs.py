from pathlib import Path
p=Path('Docs/WalkPinningTolerance.md');s=p.read_text();a=s.index('**Set Walk Pinning Limit**');b=s.index('**Set Walk Pinning Tolerance**');s=s[:a]+'The raw-value Walk pinning limit was removed on2026-09-24 at the user\'s request. There is no setter/getter, stored threshold or implicit threshold2 veto. Ordinary selection, tolerance, temporal smoothing, geometric bounds/transfer and the reach guard remain.\n\n'+s[b:];s=s.replace(', subject to the subsequent raw-value limit above','').replace(', subject to the separate limit','');p.write_text(s)
p=Path('Docs/WalkPinningBackwardBound.md');s=p.read_text().replace('The existing raw-value limit remains a veto.','The former raw-value limit has been removed.');p.write_text(s)
p=Path('Docs/AttackStartPelvisInertia.md');s=p.read_text();s='''# Attack-start lower-body inertia

`Set Attack Start Pelvis Inertia` retains its identity and existing pelvis controls. It now also has independent left-foot and right-foot Translation Window Frames / Translation Inertia / Rotation Window Frames / Rotation Inertia. Added windows default5 and strengths default0, preserving existing behavior. Pelvis defaults remain5/1/5/1; Enabled controls all regions. Feet may be enabled while pelvis strengths are0.

Each enabled region captures its own previous world-space translation and angular increment. Strength1 carries that increment on the first frame, fading linearly to the authored attack pose by its window's final frame. Windows count unpaused game ticks (60 per authored second), never elapsed seconds or30Hz inference steps. Zero strength/windows<=1 bypass that channel. New full attacks latch settings; retargeting/repeated setter calls do not restart an active entry. Half attacks retain locomotion lower-body ownership. End/cancel/reset clears motion; initial-agent reset restores all captured settings.

Pelvis and both ankle corrections are combined in one connected solve per affected leg. Preserve authored segment lengths and transported bend frame; project an unreachable target onto the reach shell. Foot rotations carry the toe mount. Consequently an unreachable requested inertia displacement is constrained by leg reach. Upper attachments follow corrected pelvis. Physical and rendered targets share the correction in their respective coordinate spaces. Raw checkpoint recurrence, attack latches and root window are unchanged.

Configured regions retain two presentation samples; inactive regions do not sample. Fully disabled/all-zero configuration removes history and active corrections. There is no timer or extra inference, and completed entries retain no correction/chain work. A newly enabled region without two samples uses existing30Hz endpoint deltas divided by two. The optional entry solve does not replace locomotion's accepted recovery reconstruction.

## Validation

Foot extension and raw-limit removal: implementation ready; closed-editor build and tests pending. Native regression covers independent5/7 and4/6 foot retirement, feet-only configuration, exact world increments, duplicate updates, reset/disable, combined hip/ankle geometry, toe mounting, unreachable projection and render/physical parity.

## Earlier pelvis-only evidence

'''+s[s.index('Normal editor build succeeded'):];p.write_text(s)
p=Path('ProjectJournal.md');s=p.read_text();a=s.index('- **Walk raw pin limit added2026-09-20:**');b=s.index('\n',a);s=s[:a]+'- **Walk raw pin limit removed2026-09-24:** user no longer wants Set/Get Walk Pinning Limit. Removed the stored settings and both raw-value veto passes, including the implicit threshold2. Other pinning controls remain. Blueprint migration bypasses obsolete setter execution and removes those nodes; verification pending. [Pin controls](Docs/WalkPinningTolerance.md).'+s[b:];s=s.replace('existing raw-limit veto also retained','raw-limit veto subsequently removed at user request');p.write_text(s)
